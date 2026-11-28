import {DEFAULT_SETTINGS,normalizeConfig} from './model.js';
import {handleEntryGet} from './db.js';
import {TeamFileError,permissionError} from './file-access.js';
import {VaultError,MAX_VAULT_BYTES,normalizeEnvelope,inspectVaultText,envelopeText,createVault,unlockVault,decryptVault,sealVault} from './vault-crypto.js';
import {vaultSession,installVaultSession,lockEpoch,withLockEpoch,withVaultAccess,lockVaults} from './vault-session.js';

export async function settingsGet(){return {...DEFAULT_SETTINGS,...(await chrome.storage.local.get('settings')).settings};}
export async function personalGet(){return (await readList('local')).profiles;}
export async function personalSet(profiles){return writeList(await readList('local'),profiles);}
export function configText(profiles){return JSON.stringify(normalizeConfig({schemaVersion:1,profiles}),null,2)+'\n';}
export async function digest(bytes){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');}
const connection=key=>JSON.stringify(['picker',key||'legacy']);
const textDigest=text=>digest(new TextEncoder().encode(text));
export function sourceRef(s){return {target:s.target,connection:s.connection??null};}
export function secureSourceRef(s){return {...sourceRef(s),vaultId:s.vaultId,sessionEpoch:s.sessionEpoch};}
function current(check){if(!check())throw new VaultError('VAULT_LOCKED','금고 작업이 취소되었습니다. 다시 잠금 해제해 주세요.');}
function changed(){return new Error('목록이나 금고 연결이 변경되었습니다. 최신 목록을 다시 확인해 주세요.');}
function gate(d){return new VaultError(d.kind==='encrypted'?'VAULT_LOCKED':d.kind==='legacy'?'VAULT_MIGRATE':'VAULT_CREATE',d.kind==='encrypted'?'금고를 잠금 해제해 주세요.':'금고 암호를 설정해 주세요.',{target:d.target,revision:d.revision,connection:d.connection??null,vaultId:d.envelope?.id,label:d.label});}
async function fileData(handle){
 let file;try{file=await handle.getFile();}catch(e){if(['NotAllowedError','SecurityError'].includes(e.name))throw permissionError(handle);throw new TeamFileError('TEAM_FILE_MISSING','연결한 파일을 찾을 수 없습니다. 파일을 다시 선택해 주세요.',handle);}
 if(file.size>MAX_VAULT_BYTES)throw new Error('금고 파일은 1 MiB 이하여야 합니다.');
 const bytes=await file.arrayBuffer();if(bytes.byteLength>MAX_VAULT_BYTES)throw new Error('금고 파일은 1 MiB 이하여야 합니다.');
 let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new Error('UTF-8 JSON 금고 파일을 선택해 주세요.');}
 return {text,revision:await digest(bytes),label:file.name};
}
async function descriptor(target,settings){
 if(target==='local'){
  const saved=await chrome.storage.local.get(['personalVault','profiles']);
  if(Object.hasOwn(saved,'personalVault')){
   const envelope=normalizeEnvelope(saved.personalVault);return {target,kind:'encrypted',envelope,revision:await textDigest(envelopeText(envelope)),label:'개인 금고',writable:true};
  }
  const config=normalizeConfig({schemaVersion:1,profiles:saved.profiles||[]});
  return {target,kind:config.profiles.length?'legacy':'empty',config,revision:await textDigest(configText(config.profiles)),label:'개인 금고',writable:true};
 }
 if(target!=='file')throw new Error('저장 방식을 다시 선택해 주세요.');
 const s=settings||await settingsGet();if(s.fileKind==='native')throw new Error('팀 파일을 다시 선택해 주세요. 전체 경로 연결은 파일 선택으로 통합되었습니다.');
 const entry=await handleEntryGet(),handle=entry.handle;if(!handle)throw new TeamFileError('TEAM_NOT_CONNECTED','팀 금고 파일을 선택해 주세요.');
 if(await handle.queryPermission({mode:'read'})!=='granted')throw permissionError(handle);
 const data=await fileData(handle),parsed=inspectVaultText(data.text);
 if(parsed.kind!=='encrypted'&&(await chrome.storage.local.get('encryptedTeamBindings')).encryptedTeamBindings?.[connection(entry.key)])throw new VaultError('VAULT_DOWNGRADE','암호화된 팀 금고가 평문이나 빈 파일로 바뀌었습니다. 파일 변경 내역을 확인해 주세요.');
 return {target,...parsed,label:data.label,revision:data.revision,connection:connection(entry.key),handle,writable:await handle.queryPermission({mode:'readwrite'})==='granted'};
}
function sameRevision(a,b){if(a.target!==b.target||a.revision!==b.revision||(a.connection??null)!==(b.connection??null))throw changed();}
async function sameConnection(base){
 const s=await settingsGet(),entry=await handleEntryGet();if(s.fileKind==='native'||connection(entry.key)!==base.connection||!entry.handle||!await entry.handle.isSameEntry(base.handle))throw changed();
}
export async function readList(target,settings){
 if(target==='file'){
  const legacy=(await chrome.storage.local.get('profiles')).profiles;
  if(Array.isArray(legacy)&&legacy.length)throw gate(await descriptor('local'));
 }
 const d=await descriptor(target,settings);if(d.kind!=='encrypted')throw gate(d);
 const session=await vaultSession(d.envelope.id);if(!session)throw gate(d);
 let config;try{config=await decryptVault(d.envelope,session.key);}catch(e){await lockVaults();throw gate(d);}
 await withVaultAccess(d.envelope.id,session.epoch);
 return {...d,profiles:config.profiles,vaultId:d.envelope.id,sessionEpoch:session.epoch,readAt:Date.now()};
}
export async function readSource(){const s=await settingsGet();return readList(s.mode,s);}
async function cleanupLegacy(envelope,key){
 const saved=await chrome.storage.local.get(['personalVault','profiles']);
 if(JSON.stringify(normalizeEnvelope(saved.personalVault))!==JSON.stringify(envelope))throw changed();
 if(Object.hasOwn(saved,'profiles')){
  const legacy=normalizeConfig({schemaVersion:1,profiles:saved.profiles||[]});
  const current=await decryptVault(envelope,key);
  if(legacy.profiles.length&&JSON.stringify(legacy)!==JSON.stringify(current))throw new VaultError('VAULT_MIGRATION_CONFLICT','기존 평문 목록과 금고가 다릅니다. 두 데이터를 보존했습니다. 이전 작업을 확인해 주세요.');
  await chrome.storage.local.remove('profiles');
 }
}
async function pinTeam(base){
 if(base.target!=='file')return;
 const pins=(await chrome.storage.local.get('encryptedTeamBindings')).encryptedTeamBindings||{};
 await chrome.storage.local.set({encryptedTeamBindings:{...pins,[base.connection]:true}});
}
async function commitEnvelope(base,envelope,key){
 const text=envelopeText(envelope);sameRevision(base,await descriptor(base.target));
 if(base.target==='local')await chrome.storage.local.set({personalVault:envelope});
 else{
  if(!base.writable)throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');
  await sameConnection(base);let stream;
  try{
   stream=await base.handle.createWritable({keepExistingData:false,mode:'exclusive'});
   if((await fileData(base.handle)).revision!==base.revision)throw changed();
   await stream.write(text);await sameConnection(base);
   if((await fileData(base.handle)).revision!==base.revision)throw changed();
   await stream.close();stream=null;
  }catch(e){if(stream)await stream.abort().catch(()=>{});if(e.name==='NoModificationAllowedError')throw new Error('금고 파일이 사용 중이거나 쓰기가 차단되었습니다.');throw e;}
 }
 const saved=await descriptor(base.target);
 if(saved.kind!=='encrypted'||JSON.stringify(saved.envelope)!==JSON.stringify(envelope))throw changed();
 await decryptVault(saved.envelope,key);
 if(base.target==='local'&&base.kind!=='encrypted')await cleanupLegacy(saved.envelope,key);
 if(base.target==='file'){await pinTeam(saved);await chrome.storage.local.set({teamChangedAt:Date.now()});}
 return saved;
}
export async function writeList(base,profiles){
 const config=normalizeConfig({schemaVersion:1,profiles});
 return navigator.locks.request('oci-companion-list-write',async()=>{
  const fresh=await descriptor(base.target);sameRevision(base,fresh);if(fresh.kind!=='encrypted')throw gate(fresh);
  const session=await vaultSession(fresh.envelope.id);if(!session||session.epoch!==base.sessionEpoch)throw gate(fresh);
  const envelope=await sealVault(fresh.envelope,session.key,config);
  await withVaultAccess(fresh.envelope.id,session.epoch,()=>commitEnvelope(fresh,envelope,session.key));
  return readList(base.target);
 });
}
export async function provisionSource(target,password,expected,isCurrent=()=>true){
 const token=await lockEpoch(),base=await descriptor(target);if(expected)sameRevision(expected,base);if(base.kind==='encrypted')throw changed();
 const created=await createVault(base.config,password);current(isCurrent);
 await navigator.locks.request('oci-companion-list-write',()=>withLockEpoch(token,()=>{current(isCurrent);return commitEnvelope(base,created.envelope,created.key);}));
 current(isCurrent);await installVaultSession(created.envelope.id,created.key,token);return readList(target);
}
export async function unlockSource(target,password,expected,isCurrent=()=>true){
 const token=await lockEpoch(),base=await descriptor(target);if(expected)sameRevision(expected,base);if(base.kind!=='encrypted')throw gate(base);
 const key=await unlockVault(base.envelope,password);current(isCurrent);
 await navigator.locks.request('oci-companion-list-write',()=>withLockEpoch(token,async()=>{current(isCurrent);sameRevision(base,await descriptor(target));if(target==='local')await cleanupLegacy(base.envelope,key);else await pinTeam(base);}));
 current(isCurrent);await installVaultSession(base.envelope.id,key,token);return readList(target);
}
export async function changeVaultPassword(target,currentPassword,newPassword){
 const base=await readList(target),key=await unlockVault(base.envelope,currentPassword);
 const session=await vaultSession(base.vaultId);if(!session||session.key!==key||session.epoch!==base.sessionEpoch)throw gate(base);
 // A fresh data key and ID prevent someone with an old password/file from
 // using its old data key to decrypt future writes after a password change.
 const created=await createVault({schemaVersion:1,profiles:base.profiles},newPassword);
 await navigator.locks.request('oci-companion-list-write',()=>withVaultAccess(base.vaultId,base.sessionEpoch,()=>commitEnvelope(base,created.envelope,created.key)));
 await lockVaults();
}
export async function encryptedExport(target){
 const source=await readList(target);await withVaultAccess(source.vaultId,source.sessionEpoch);return envelopeText(source.envelope);
}
export async function decodeImport(text,password){
 const parsed=inspectVaultText(text);if(parsed.kind==='empty')throw new Error('빈 파일은 가져올 수 없습니다.');
 return parsed.kind==='encrypted'?decryptVault(parsed.envelope,await unlockVault(parsed.envelope,password)):parsed.config;
}
export async function validateTeamFile(handle){const data=await fileData(handle);return inspectVaultText(data.text);}
export async function createTeamFile(handle){if((await handle.getFile()).size)throw new Error('기존 파일은 덮어쓰지 않습니다. 파일 선택으로 연결해 주세요.');}
