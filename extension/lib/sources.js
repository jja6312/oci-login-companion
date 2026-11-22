import {DEFAULT_SETTINGS,MAX_BYTES,parseConfig,normalizeConfig} from './model.js';
import {handleEntryGet} from './db.js';
import {TeamFileError,permissionError} from './file-access.js';
export async function settingsGet(){return {...DEFAULT_SETTINGS,...(await chrome.storage.local.get('settings')).settings};}
export async function personalGet(){return normalizeConfig({schemaVersion:1,profiles:(await chrome.storage.local.get('profiles')).profiles||[]}).profiles;}
export async function personalSet(profiles){await chrome.storage.local.set({profiles:normalizeConfig({schemaVersion:1,profiles}).profiles});}
export function configText(profiles){const c=normalizeConfig({schemaVersion:1,profiles});const p=JSON.stringify(c,null,2)+'\n';const text=new TextEncoder().encode(p).length<=MAX_BYTES?p:JSON.stringify(c);return text;}
export async function digest(bytes){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');}
const connection=key=>JSON.stringify(['picker',key||'legacy']);
export function sourceRef(s){return {target:s.target,connection:s.connection??null};}
function changed(){return new Error('목록이 변경되었습니다. 최신 목록을 다시 확인한 뒤 저장해 주세요.');}
async function fileData(handle){
 let file;try{file=await handle.getFile();}catch(e){if(['NotAllowedError','SecurityError'].includes(e.name))throw permissionError(handle);throw new TeamFileError('TEAM_FILE_MISSING','연결한 파일을 찾을 수 없습니다. 파일을 다시 선택해 주세요.',handle);}
 if(file.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');
 const bytes=await file.arrayBuffer();if(bytes.byteLength>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');
 let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new Error('UTF-8 JSON 파일을 선택해 주세요.');}
 return {text,revision:await digest(bytes),label:file.name};
}
export async function readList(target,settings){
 if(target==='local'){const profiles=await personalGet();return {target,profiles,label:'개인 저장소',revision:await digest(new TextEncoder().encode(JSON.stringify(profiles))),readAt:Date.now(),writable:true};}
 if(target!=='file')throw new Error('저장 방식을 다시 선택해 주세요.');
 const s=settings||await settingsGet();let data,handle,canWrite,key;
 if(s.fileKind==='native')throw new Error('팀 파일을 다시 선택해 주세요. 전체 경로 연결은 파일 선택 방식으로 통합되었습니다.');
 const entry=await handleEntryGet();handle=entry.handle;key=entry.key;if(!handle)throw new TeamFileError('TEAM_NOT_CONNECTED','팀 파일을 선택해 주세요.');
 if(await handle.queryPermission({mode:'read'})!=='granted')throw permissionError(handle);
 data=await fileData(handle);canWrite=await handle.queryPermission({mode:'readwrite'})==='granted';
 return {target,profiles:parseConfig(data.text).profiles,label:data.label,revision:data.revision,connection:connection(key),handle,readAt:Date.now(),writable:canWrite};
}
export async function readSource(){const s=await settingsGet();return readList(s.mode,s);}
async function sameConnection(base){
 const s=await settingsGet();const entry=await handleEntryGet();if(s.fileKind==='native'||connection(entry.key)!==base.connection)throw changed();
 if(base.handle){const h=entry?.handle;if(!h||!await h.isSameEntry(base.handle))throw changed();}
 return s;
}
export async function writeList(base,profiles){
 const text=configText(profiles);
 return navigator.locks.request('oci-companion-list-write',async()=>{
  if(base.target==='local'){
   const current=await readList('local');if(current.revision!==base.revision)throw changed();
   await personalSet(parseConfig(text).profiles);return readList('local');
  }
  const s=await sameConnection(base);const fresh=await readList('file');if(fresh.revision!==base.revision||fresh.connection!==base.connection)throw changed();await sameConnection(base);
  if(!fresh.writable)throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');
  {
   let stream;
   try{
    stream=await fresh.handle.createWritable({keepExistingData:false,mode:'exclusive'});
    if((await fileData(fresh.handle)).revision!==base.revision)throw changed();
    await stream.write(text);await sameConnection(base);
    if((await fileData(fresh.handle)).revision!==base.revision)throw changed();
    await stream.close();stream=null;
   }catch(e){if(stream)await stream.abort().catch(()=>{});if(e.name==='NoModificationAllowedError')throw new Error('파일에 쓸 수 없습니다. 다른 작업의 사용 여부와 파일 쓰기 권한을 확인해 주세요.');throw e;}
  }
  const saved=await readList('file');if(JSON.stringify(saved.profiles)!==JSON.stringify(parseConfig(text).profiles))throw new Error('저장 후 파일이 다시 변경되었습니다. 최신 목록을 확인해 주세요.');
  await chrome.storage.local.set({teamChangedAt:Date.now()});return saved;
 });
}
export async function createTeamFile(handle){
 const original=await handle.getFile();if(original.size)throw new Error('기존 파일은 덮어쓰지 않습니다. 파일 선택으로 연결해 주세요.');
 const stream=await handle.createWritable({keepExistingData:false,mode:'exclusive'});
 try{if((await handle.getFile()).size)throw changed();await stream.write(configText([]));await stream.close();}catch(e){await stream.abort().catch(()=>{});throw e;}
}
