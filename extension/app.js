import {normalizeProfile,parseConfig,mergeProfiles,MAX_BYTES,patternsFor} from './lib/model.js';
import {settingsGet,personalGet,readSource,readList,writeList,configText,createTeamFile,sourceRef} from './lib/sources.js';
import {handleGet,handleSet,handleEntryGet} from './lib/db.js';
import {requestFileAccess} from './lib/file-access.js';
import {onboardingState,onboardingStep,finishOnboarding} from './lib/onboarding.js';
import {normalizeAppearance,applyAppearance,ACCENT_PRESETS} from './lib/appearance.js';
import {icon} from './lib/icons.js';
import {parseBulkColumns,appendBulkProfiles,columnRows} from './lib/bulk.js';
const $=id=>document.getElementById(id);
for(const el of document.querySelectorAll('[data-icon]'))el.replaceChildren(icon(el.dataset.icon));
let sourceSnapshot=null,editBase=null,deleteBase=null,pendingBase=null,draftHandle=null,savingAccount=false,loadVersion=0,sourceReading=0;
let profiles=[],filtered=[],selectedId=null,sourceSettings,sourceLabel='',editing=null,pending=null,launching=false,job=null;
let appearance=normalizeAppearance(),revealed=new Set(),toastTimer,messageTimer;
let sourceError=null,accessEntry=null,accessBusy=false,automaticAccessTried=false,filePickerBlocked=false;
const selected=()=>profiles.find(p=>p.id===selectedId);
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,2400);}
function message(text,error=false){clearTimeout(messageTimer);$('message').textContent=text;$('message').classList.toggle('error',error);$('message').hidden=!text;if(text)messageTimer=setTimeout(()=>$('message').hidden=true,7000);}
function settingsMessage(text,error=false){$('settings-message').textContent=text;$('settings-message').hidden=!text;$('settings-message').classList.toggle('error',error);}
function guard(fn,settings=false){return async(...args)=>{try{await fn(...args);}catch(e){if(e.name==='AbortError')return;(settings?settingsMessage:message)(e.message||'작업을 완료하지 못했습니다.',true);}};}
function resetSecrets(){revealed.clear();for(const b of document.querySelectorAll('[data-reveal]')){b.setAttribute('aria-pressed','false');b.replaceChildren(icon('Eye'));}}
function canEdit(){return sourceSettings?.mode==='local'||sourceSnapshot?.writable===true;}
function canRequestEdit(){return canEdit()||!!(sourceSnapshot&&sourceSettings?.mode==='file');}
async function restoreTeamAccess(mode='read',entry=accessEntry){
 if(!entry?.handle||accessBusy)return false;
 accessBusy=true;$('restore-team').disabled=true;$('restore-team').textContent='접근 확인 중…';
 try{
  const granted=await requestFileAccess(entry.handle,mode);
  const current=await handleEntryGet();if(current.key!==entry.key)return false;
  return granted;
 }finally{accessBusy=false;$('restore-team').disabled=false;$('restore-team').textContent='팀 파일 열기';}
}
async function ensureEditable(){
 if(canEdit())return true;
 if(!sourceSnapshot)return false;
 const entry=accessEntry;const allowed=await restoreTeamAccess('readwrite',entry);await load();
 if(!allowed||!canEdit())throw new Error('편집하려면 브라우저에서 파일 쓰기를 허용해 주세요.');
 return true;
}
async function load({requestOnOpen=false}={}){
 const version=++loadVersion;sourceReading++;
 try{
  let settings,source,error;
  try{
   settings=await settingsGet();accessEntry=await handleEntryGet();
   source=await readList(settings.mode,settings);
  }catch(e){
   error=e;
   // A toolbar click can provide activation to the popup. Never repeatedly
   // prompt from periodic/focus refresh, and never grant browser permissions ourselves.
   if(e.code==='TEAM_PERMISSION'&&requestOnOpen&&!automaticAccessTried){
    automaticAccessTried=true;
    if(navigator.userActivation?.isActive){
    if(await restoreTeamAccess('readwrite',accessEntry)){
     try{source=await readList(settings.mode,settings);error=null;}catch(next){error=next;}
    }
    }
   }
  }
  if(version!==loadVersion)return;sourceSettings=settings;sourceError=error||null;sourceSnapshot=source||null;profiles=source?.profiles||[];sourceLabel=source?.label||accessEntry?.handle?.name||(settings?.mode==='file'?'팀 파일 연결 필요':'개인 저장소');message(error?.code==='TEAM_PERMISSION'?'':error?.message||'',!!error);
  $('source-label').textContent=settings?.mode==='file'?'팀 파일':'개인 저장소';$('source').title=sourceLabel;
  $('add').disabled=!canRequestEdit();$('add').title=canRequestEdit()?'계정 추가 (Alt + N)':'팀 파일 접근을 허용해 주세요.';
  resetSecrets();render();await updateStatus();
 }finally{sourceReading--;}
}
function render(){
  const q=$('search').value.trim().toLocaleLowerCase();
  filtered=profiles.filter(p=>[p.tenancy,p.name,p.username].some(v=>v.toLocaleLowerCase().includes(q))).sort((a,b)=>{
    const score=p=>[p.tenancy,p.name].some(v=>v.toLocaleLowerCase()===q)?0:[p.tenancy,p.name].some(v=>v.toLocaleLowerCase().startsWith(q))?1:2;
    return score(a)-score(b)||a.tenancy.localeCompare(b.tenancy);
  });
  if(!filtered.some(p=>p.id===selectedId))selectedId=filtered[0]?.id||null;
  $('count').textContent=sourceError?.code==='TEAM_PERMISSION'?'—':profiles.length;$('accounts').replaceChildren();
  if(!filtered.length&&sourceError?.code!=='TEAM_PERMISSION'&&(profiles.length||(sourceSettings?.mode==='file'&&!sourceSnapshot))){const e=document.createElement('p');e.className='empty';e.textContent=profiles.length?'검색 결과가 없습니다.':sourceSettings?.mode==='file'?'설정에서 팀 파일을 연결해 주세요.':'계정을 추가하거나 설정 파일을 가져오세요.';$('accounts').append(e);}
  for(const p of filtered){const row=document.createElement('button');row.type='button';row.className='account-row';row.role='option';row.id='row-'+p.id;row.dataset.id=p.id;row.setAttribute('aria-selected',String(p.id===selectedId));const mark=document.createElement('span');mark.className='tenant-mark';mark.textContent='O';const info=document.createElement('span');info.className='account-info';const title=document.createElement('strong');title.textContent=p.tenancy;title.title=p.tenancy;const sub=document.createElement('small');sub.textContent=p.name!==p.tenancy?p.name:p.username;sub.title=p.username;info.append(title,sub);row.append(mark,info);row.onclick=()=>select(p.id);row.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(!e.repeat){select(p.id);launch('login');}}};$('accounts').append(row);}
  renderDetails();
}
function select(id){if(id!==selectedId){selectedId=id;resetSecrets();$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');$('detail-content').querySelector('details').open=false;}for(const row of document.querySelectorAll('.account-row'))row.setAttribute('aria-selected',String(row.dataset.id===id));renderDetails();}
function renderDetails(){
  const p=selected();$('detail-content').hidden=!p;$('empty-detail').hidden=!!p;
  $('empty-add').hidden=!canRequestEdit();
  const recover=sourceSettings?.mode==='file'&&sourceError?.code==='TEAM_PERMISSION';$('team-access').hidden=!recover;$('team-file-label').textContent=recover?(accessEntry?.handle?.name||'연결된 팀 파일'):'';
  if(!p)return;
  $('detail-title').textContent=p.tenancy;$('detail-title').title=p.tenancy;$('detail-subtitle').textContent=[p.name!==p.tenancy?p.name:'',p.identityDomain||'기본 도메인'].filter(Boolean).join(' · ');
  $('username').textContent=p.username;
  for(const key of ['password','bypassCode']){$(key).textContent=revealed.has(key)?p[key]:'••••••••••••';$(key).classList.toggle('masked',!revealed.has(key));}
  $('detail-domain').textContent=p.identityDomain||'지정하지 않음';$('detail-name').textContent=p.name;$('detail-source').textContent=sourceLabel;
  $('edit').disabled=!canRequestEdit();$('delete').hidden=!canRequestEdit();renderJob();
}
function renderJob(){const p=selected();const active=job?.profileId===p?.id?job:null;$('job').hidden=!active;$('job-status').textContent=active?.message||'';$('cancel').hidden=!active?.running;$('login').disabled=launching||!!active?.running;$('login-label').textContent=launching?'연결 중…':active?.running?'로그인 진행 중…':'로그인';}
async function windowScope(){const w=await chrome.windows.getCurrent();return {windowId:w.id,incognito:w.incognito};}
async function updateStatus(){try{const r=await chrome.runtime.sendMessage({type:'STATUS',...await windowScope()});job=r.items?.find(x=>x.profileId===selectedId)||null;renderJob();}catch{/* popup can close while the worker wakes */}}
async function launch(mode){
  if(launching)return;const p=selected();if(!p)return;if(job?.profileId===p.id&&job.running)return;
  launching=true;renderJob();
  try{
    // Start both API calls during the original click/keypress gesture. Waiting
    // for a window lookup first can lose Chrome's permission-request gesture.
    const scopeTask=windowScope();const permissionTask=chrome.permissions.request({origins:patternsFor(p)});
    const scope=await scopeTask;
    if(!await permissionTask)throw new Error('OCI 화면 접근을 허용하면 자동 로그인을 사용할 수 있습니다.');
    const fresh=(await readSource()).profiles.find(x=>x.id===p.id);
    if(!fresh||['tenancy','username','identityDomain'].some(k=>fresh[k]!==p[k])){await load();throw new Error('선택한 계정이 변경되었습니다. 다시 선택해 주세요.');}
    const r=await chrome.runtime.sendMessage({type:'START',profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode,...scope});
    if(!r?.ok)throw new Error(r?.error||'로그인을 시작하지 못했습니다.');await updateStatus();
  }catch(e){message(e.message,true);}finally{launching=false;renderJob();}
}
$('search').oninput=()=>{selectedId=null;resetSecrets();render();updateStatus();};
$('search').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(!e.repeat)launch('login');}else if(['ArrowDown','ArrowUp'].includes(e.key)&&filtered.length){e.preventDefault();const i=filtered.findIndex(p=>p.id===selectedId);select(filtered[(i+(e.key==='ArrowDown'?1:-1)+filtered.length)%filtered.length].id);document.getElementById('row-'+selectedId)?.scrollIntoView({block:'nearest'});updateStatus();}};
$('login').onclick=()=>launch('login');$('fill').onclick=()=>{$('more-menu').hidden=true;launch('fill');};
$('diagnostics').onclick=guard(async()=>{const p=selected();if(!p)return;const r=await chrome.runtime.sendMessage({type:'DIAGNOSTICS',profileId:p.id,...await windowScope()});if(!r?.ok)throw new Error('진단 정보를 읽지 못했습니다. 확장을 다시 열어 주세요.');await navigator.clipboard.writeText(JSON.stringify(r.report,null,2));$('more-menu').hidden=true;toast('진단 정보를 복사했습니다');});
$('cancel').onclick=guard(async()=>{if(job){await chrome.runtime.sendMessage({type:'CANCEL',tabId:job.tabId});await updateStatus();}});
$('restore-team').onclick=guard(async()=>{const entry=accessEntry;automaticAccessTried=true;const allowed=await restoreTeamAccess('readwrite',entry);await load();if(!allowed&&sourceError?.code==='TEAM_PERMISSION')$('team-access-note').textContent='브라우저 승인 창에서 접근을 허용해 주세요. 파일 연결은 그대로 유지됩니다.';else $('team-access-note').textContent='승인 창에서 “방문할 때마다 허용”을 선택하면 다음에도 자동으로 열립니다.';});
$('choose-team').onclick=guard(()=>openSettings('storage'));
$('refresh').onclick=guard(load);
$('more').onclick=()=>{const open=$('more-menu').hidden;$('more-menu').hidden=!open;$('more').setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.target.closest('.more-wrap')){$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');resetSecrets();renderDetails();}});
for(const b of document.querySelectorAll('[data-reveal]'))b.onclick=()=>{const k=b.dataset.reveal;if(revealed.has(k))revealed.delete(k);else revealed.add(k);b.setAttribute('aria-pressed',String(revealed.has(k)));b.replaceChildren(icon(revealed.has(k)?'EyeOff':'Eye'));renderDetails();};
for(const b of document.querySelectorAll('[data-copy]'))b.onclick=guard(async()=>{const p=selected();if(!p)return;await navigator.clipboard.writeText(p[b.dataset.copy]);toast('복사했습니다');});
async function openEdit(p){if(!await ensureEditable())return;const base=await readSource();if(!base.writable)throw new Error('팀 파일 편집 권한을 확인해 주세요.');if(p){p=base.profiles.find(x=>x.id===p.id);if(!p){await load();throw new Error('계정이 변경되었습니다. 다시 선택해 주세요.');}}editBase=base;editing=p||null;$('edit-title').textContent=p?'계정 편집':'계정 추가';$('account-form').reset();$('account-form').querySelector('[type=submit]').textContent=base.target==='file'?'팀 파일에 저장':'저장';for(const [id,value] of Object.entries({'p-name':p?.name===p?.tenancy?'':p?.name||'','p-tenancy':p?.tenancy||'','p-domain':p?.identityDomain??'Default','p-username':p?.username||'','p-password':p?.password||'','p-bypass':p?.bypassCode||'','p-selectors':p&&Object.keys(p.selectors).length?JSON.stringify(p.selectors,null,2):''}))$(id).value=value;$('edit-error').textContent='';$('show-secrets').checked=false;toggleSecrets();$('edit-dialog').querySelector('details').open=false;$('edit-dialog').showModal();$('p-tenancy').focus();}
function closeEdit(){if(savingAccount)return;$('edit-dialog').close();$('account-form').reset();editing=null;editBase=null;}
function toggleSecrets(){for(const id of ['p-password','p-bypass'])$(id).type=$('show-secrets').checked?'text':'password';}
$('account-form').onsubmit=async e=>{e.preventDefault();if(savingAccount)return;savingAccount=true;const save=$('account-form').querySelector('[type=submit]');save.disabled=true;try{if(!editBase||(await settingsGet()).mode!==editBase.target)throw new Error('저장 위치가 변경되었습니다. 편집을 다시 열어 주세요.');let selectors;try{selectors=$('p-selectors').value.trim()?JSON.parse($('p-selectors').value):{};}catch{throw new Error('선택자 JSON 형식을 확인해 주세요.');}for(const value of Object.values(selectors||{}))if(typeof value==='string'&&value)document.querySelector(value);const targetSame=editing&&editing.tenancy===$('p-tenancy').value.trim()&&editing.username===$('p-username').value.trim()&&editing.identityDomain===$('p-domain').value.trim();const p=normalizeProfile({id:editing?.id||crypto.randomUUID(),name:$('p-name').value,tenancy:$('p-tenancy').value,identityDomain:$('p-domain').value,username:$('p-username').value,password:$('p-password').value,bypassCode:$('p-bypass').value,identityOrigins:targetSame?editing.identityOrigins:[],selectors});const old=editBase.profiles;await writeList(editBase,editing?old.map(x=>x.id===editing.id?p:x):[...old,p]);selectedId=p.id;$('search').value='';savingAccount=false;closeEdit();await load();toast('계정을 저장했습니다');}catch(err){$('edit-error').textContent=err.message;}finally{savingAccount=false;save.disabled=false;}};
document.addEventListener('keydown',e=>{if(e.altKey&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&e.code==='KeyN'){if(document.querySelector('dialog[open]'))return;e.preventDefault();if(!e.repeat)guard(()=>openEdit())();}},true);
$('add').onclick=guard(()=>openEdit());$('empty-add').onclick=guard(()=>openEdit());$('edit').onclick=guard(()=>openEdit(selected()));$('close-edit').onclick=closeEdit;$('cancel-edit').onclick=closeEdit;$('edit-dialog').addEventListener('cancel',e=>{e.preventDefault();closeEdit();});$('show-secrets').onchange=toggleSecrets;
let bulkDraft=null,bulkSaving=false,bulkSource=null;
function clearBulkReview(){bulkDraft=null;$('bulk-review').hidden=true;$('bulk-rows').replaceChildren();$('bulk-save').disabled=true;$('bulk-save').textContent='일괄 등록';$('bulk-error').textContent='';}
function closeBulk(){if(bulkSaving)return;$('bulk-dialog').close();$('bulk-form').reset();for(const t of document.querySelectorAll('[data-column]')){$('bulk-count-'+t.dataset.column).textContent='0행';}clearBulkReview();toggleBulkSecrets();}
function toggleBulkSecrets(){for(const k of ['password','bypassCode'])$('bulk-'+k).classList.toggle('secret-column',!$('bulk-show-secrets').checked);}
$('bulk-open').onclick=guard(async()=>{if(!await ensureEditable())throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');const base=await readSource();if(!base.writable)throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');bulkSource=sourceRef(base);clearBulkReview();$('bulk-dialog').showModal();$('bulk-tenancy').focus();});
for(const t of document.querySelectorAll('[data-column]'))t.oninput=()=>{clearBulkReview();try{$('bulk-count-'+t.dataset.column).textContent=columnRows(t.value,t.dataset.column).length+'행';}catch{$('bulk-count-'+t.dataset.column).textContent='확인 필요';}};
$('bulk-preview').onclick=async()=>{clearBulkReview();try{
  const raw=Object.fromEntries([...document.querySelectorAll('[data-column]')].map(t=>[t.dataset.column,t.value]));
  const draft=parseBulkColumns(raw);const current=await readSource();if(JSON.stringify(sourceRef(current))!==JSON.stringify(bulkSource))throw new Error('저장 위치가 변경되었습니다. 일괄 등록을 다시 열어 주세요.');appendBulkProfiles(current.profiles,draft);
  for(const t of document.querySelectorAll('[data-column]')){t.scrollTop=0;t.scrollLeft=0;}
  for(const [i,p] of draft.entries()){const tr=document.createElement('tr');for(const value of [i+1,p.tenancy,p.name===p.tenancy?'—':p.name,p.username,p.identityDomain]){const td=document.createElement('td');td.textContent=String(value);tr.append(td);}$('bulk-rows').append(tr);}
  bulkDraft=draft;$('bulk-summary').textContent=`${draft.length}개 계정을 추가할 준비가 됐습니다.`;$('bulk-review').hidden=false;$('bulk-save').disabled=false;$('bulk-save').textContent=draft.length+'개 등록';
}catch(e){$('bulk-error').textContent=e.message;}};
$('bulk-form').onsubmit=async e=>{e.preventDefault();if(!bulkDraft||bulkSaving)return;const submitted=bulkDraft;bulkSaving=true;$('bulk-preview').disabled=true;for(const t of document.querySelectorAll('[data-column]'))t.readOnly=true;$('bulk-save').disabled=true;$('bulk-save').textContent='등록 중…';try{
  const r=await chrome.runtime.sendMessage({type:'BULK_ADD',source:bulkSource,profiles:submitted});if(!r?.ok)throw new Error(r?.error||'일괄 등록을 완료하지 못했습니다.');
  const first=submitted[0].id;bulkSaving=false;closeBulk();selectedId=first;$('search').value='';await load();toast(r.count+'개 계정을 등록했습니다');
}catch(e){$('bulk-error').textContent=e.message;$('bulk-save').disabled=false;$('bulk-save').textContent='다시 등록';}finally{bulkSaving=false;$('bulk-preview').disabled=false;for(const t of document.querySelectorAll('[data-column]'))t.readOnly=false;}};
$('close-bulk').onclick=closeBulk;$('cancel-bulk').onclick=closeBulk;$('bulk-dialog').addEventListener('cancel',e=>{e.preventDefault();closeBulk();});$('bulk-show-secrets').onchange=toggleBulkSecrets;
window.addEventListener('pagehide',()=>{bulkDraft=null;for(const t of document.querySelectorAll('[data-column]'))t.value='';});
$('delete').onclick=guard(async()=>{const p=selected();if(!p||!await ensureEditable())return;deleteBase=await readSource();if(!deleteBase.writable)throw new Error('팀 파일 편집 권한을 확인해 주세요.');deleteBase={...deleteBase,deletingId:p.id};$('more-menu').hidden=true;$('delete-name').textContent=p.tenancy;$('delete-scope').textContent=deleteBase.target==='file'?'연결된 팀 파일에서 삭제합니다. 동기화 후 팀원에게도 반영됩니다.':'개인 저장소에서 이 계정을 삭제합니다.';$('delete-dialog').returnValue='';$('delete-dialog').showModal();});
$('delete-dialog').addEventListener('close',guard(async()=>{const base=deleteBase;deleteBase=null;if($('delete-dialog').returnValue!=='delete'||!base)return;await writeList(base,base.profiles.filter(p=>p.id!==base.deletingId));await load();toast('계정을 삭제했습니다');}));
function setSettingsTab(name){for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b.dataset.tab===name));for(const s of document.querySelectorAll('[data-panel]'))s.hidden=s.dataset.panel!==name;settingsMessage('');}
async function openSettings(tab='appearance'){await syncStorage();$('import-target').value=sourceSettings.mode;$('export-target').value=sourceSettings.mode;setSettingsTab(tab);syncAppearance();$('settings-dialog').showModal();}
$('settings').onclick=guard(()=>openSettings());$('source').onclick=guard(()=>openSettings('storage'));$('close-settings').onclick=()=>$('settings-dialog').close();for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>setSettingsTab(b.dataset.tab);
$('settings-dialog').addEventListener('close',()=>{pending=null;pendingBase=null;draftHandle=null;$('allow-updates').checked=false;$('import-file').value='';$('import-confirm').disabled=true;$('import-recheck').disabled=true;$('import-preview').textContent='';$('export-ack').checked=false;$('export').disabled=true;});
function syncAppearance(){applyAppearance(appearance);$('theme-mode').value=appearance.mode;$('theme-accent').value=appearance.accent;$('accent-value').textContent=appearance.accent.toUpperCase();for(const b of document.querySelectorAll('.swatch'))b.setAttribute('aria-pressed',String(b.dataset.color===appearance.accent));}
async function saveAppearance(next){appearance=normalizeAppearance(next);syncAppearance();await chrome.storage.local.set({appearance});}
for(const id of ['accent-presets','quick-presets'])for(const [i,color] of ACCENT_PRESETS.entries()){const b=document.createElement('button');b.type='button';b.className='swatch';b.dataset.color=color;b.style.setProperty('--swatch',color);b.setAttribute('aria-label',['퍼플','블루','민트','로즈','오렌지','그레이'][i]+' 테마색');b.onclick=guard(()=>saveAppearance({...appearance,accent:color}),id==='accent-presets');$(id).append(b);}
$('theme-mode').onchange=guard(()=>saveAppearance({...appearance,mode:$('theme-mode').value}),true);$('theme-accent').oninput=guard(()=>saveAppearance({...appearance,accent:$('theme-accent').value}),true);matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>applyAppearance(appearance));
async function teamPicker(kind){
 try{
  const options={id:'oci-team',types:[{description:'OCI 팀 목록',accept:{'application/json':['.json']}}]};
  const result=kind==='open'?await window.showOpenFilePicker({...options,multiple:false}):await window.showSaveFilePicker({...options,suggestedName:'oci-team-accounts.json'});
  filePickerBlocked=false;fileAccessView();return result;
 }catch(e){
  if(['SecurityError','NotAllowedError'].includes(e.name)){
   filePickerBlocked=true;fileAccessView();$('setup-file-help').hidden=false;
   throw new Error('파일 선택이 차단되었거나 승인이 거부되었습니다. 브라우저 권한과 조직 정책을 확인해 주세요.');
  }
  throw e;
 }
}
function fileAccessView(){
 const open=typeof window.showOpenFilePicker==='function',save=typeof window.showSaveFilePicker==='function';
 $('file-access-help').hidden=open&&save&&!filePickerBlocked;$('pick-file').disabled=!open;$('create-team').disabled=!save;
}
async function syncStorage(){sourceSettings=await settingsGet();document.querySelector(`[name=mode][value="${sourceSettings.mode==='file'?'file':'local'}"]`).checked=true;draftHandle=sourceSettings.fileKind==='native'?null:await handleGet();$('file-name').textContent=draftHandle?.name||'연결한 파일 없음';fileView();fileAccessView();}
function fileView(){$('file-settings').hidden=document.querySelector('[name=mode]:checked')?.value!=='file';}
for(const r of document.querySelectorAll('[name=mode]'))r.onchange=fileView;
$('pick-file').onclick=guard(async()=>{if(typeof window.showOpenFilePicker!=='function'){fileAccessView();throw new Error('아래 안내에 따라 브라우저 파일 접근을 켠 뒤 다시 시작해 주세요.');}const [h]=await teamPicker('open');const f=await h.getFile();if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');parseConfig(await f.text());await requestFileAccess(h,'readwrite');draftHandle=h;$('file-name').textContent=h.name;fileAccessView();settingsMessage('파일을 선택했습니다. 저장 위치 적용을 눌러 주세요.');},true);
$('create-team').onclick=guard(async()=>{if(typeof window.showSaveFilePicker!=='function'){fileAccessView();throw new Error('브라우저 파일 접근을 켠 뒤 다시 시작해 주세요.');}const h=await teamPicker('save');await createTeamFile(h);draftHandle=h;$('file-name').textContent=h.name;fileAccessView();settingsMessage('빈 팀 파일을 만들었습니다. 저장 위치 적용 후 계정을 추가하거나 가져오세요.');},true);
$('regrant').onclick=guard(async()=>{const h=draftHandle;if(!h)throw new Error('먼저 파일을 선택해 주세요.');if(!await requestFileAccess(h,'readwrite'))throw new Error('브라우저에서 파일 접근을 허용해 주세요.');await load();settingsMessage('접근을 복구했습니다. 승인 창에서 방문할 때마다 허용을 선택하면 다음에도 유지됩니다.');},true);
$('open-file-access').onclick=guard(async()=>{await chrome.tabs.create({url:'chrome://flags/#file-system-access-api'});},true);
$('copy-file-access').onclick=guard(async()=>{await navigator.clipboard.writeText('brave://flags/#file-system-access-api');settingsMessage('설정 주소를 복사했습니다. 주소창에 붙여 넣어 주세요.');},true);
$('storage-form').onsubmit=guard(async e=>{e.preventDefault();const next={mode:document.querySelector('[name=mode]:checked').value,fileKind:'picker'};if(next.mode==='file'){if(!draftHandle)throw new Error('팀 JSON 파일을 먼저 선택해 주세요.');const f=await draftHandle.getFile();if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');parseConfig(await f.text());await handleSet(draftHandle);}await chrome.storage.local.set({settings:next});selectedId=null;await load();settingsMessage('저장 위치를 적용했습니다.');$('source-result').textContent='';},true);
$('check-source').onclick=guard(async()=>{const r=await readSource();$('source-result').textContent=`${r.profiles.length}개 계정 · ${new Date(r.readAt).toLocaleTimeString('ko-KR')} 읽음 · ${r.label}`;},true);
async function prepareImport(){pendingBase=null;$('import-confirm').disabled=true;$('import-recheck').disabled=!pending;if(!pending)return;let base=await readList($('import-target').value);if(!base.writable&&base.target==='file'){if(await restoreTeamAccess('readwrite',await handleEntryGet()))base=await readList('file');}if(!base.writable)throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');pendingBase=base;$('import-preview').textContent=`${pending.length}개 계정 → ${base.target==='file'?'팀 파일':'개인 저장소'} (현재 ${base.profiles.length}개)`;$('import-confirm').disabled=false;}
$('import-file').onchange=guard(async()=>{pending=null;pendingBase=null;$('import-confirm').disabled=true;$('import-recheck').disabled=true;const f=$('import-file').files[0];if(!f)return;if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');pending=parseConfig(await f.text()).profiles;await prepareImport();},true);
$('import-target').onchange=guard(async()=>{$('allow-updates').checked=false;await prepareImport();},true);$('import-recheck').onclick=guard(prepareImport,true);
$('import-confirm').onclick=guard(async()=>{if(!pending||!pendingBase)return;const base=pendingBase;if(base.target!==$('import-target').value)throw new Error('가져올 위치를 다시 확인해 주세요.');$('import-confirm').disabled=true;try{const result=mergeProfiles(base.profiles,pending,$('allow-updates').checked);await writeList(base,result);pending=null;pendingBase=null;$('import-file').value='';$('import-recheck').disabled=true;$('import-preview').textContent='가져오기를 완료했습니다.';await load();settingsMessage(`${base.target==='file'?'팀 파일':'개인 저장소'}에 ${result.length}개 계정이 있습니다.`);}catch(e){$('import-confirm').disabled=false;throw e;}},true);
function download(name,value){const text=configText(value.profiles);const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}
$('export-ack').onchange=()=>$('export').disabled=!$('export-ack').checked;
$('export').onclick=guard(async()=>{if(!$('export-ack').checked)return;const target=$('export-target').value;const r=await readList(target);download(`oci-${target==='file'?'team':'personal'}-accounts-${new Date().toLocaleDateString('en-CA')}.json`,{schemaVersion:1,profiles:r.profiles});},true);
$('template').onclick=()=>download('oci-accounts.example.json',{schemaVersion:1,profiles:[{id:'replace-this-id',name:'서울 운영 계정',tenancy:'replace-tenancy',identityDomain:'Default',username:'replace-username',password:'REPLACE_PASSWORD',bypassCode:'REPLACE_ADMIN_BYPASS_CODE'}]});
let setupBusy=false,setupVersion=0;
function setupMessage(text=''){$('setup-error').textContent=text;}
function setupView(step){
 $('setup-choose').hidden=step!=='choose';$('setup-file').hidden=step!=='file';$('setup-back').hidden=step!=='file';$('setup-title').textContent=step==='file'?'팀 파일 연결':'저장 위치 선택';
 const open=typeof window.showOpenFilePicker==='function',save=typeof window.showSaveFilePicker==='function';
 $('setup-open-file').disabled=!open||setupBusy;$('setup-new-file').disabled=!save||setupBusy;$('setup-file-help').hidden=open&&save&&!filePickerBlocked;
 if(!setupBusy)(step==='choose'?$('setup-local'):save?$('setup-new-file'):open?$('setup-open-file'):$('setup-back')).focus();
}
async function closeSetup(){
 if($('setup-dialog').open)$('setup-dialog').close();await load();(profiles.length?$('search'):$('empty-add')).focus();
}
async function syncSetup(){
 const version=++setupVersion,s=await onboardingState();if(version!==setupVersion)return;if(s.complete){if($('setup-dialog').open&&!setupBusy)await closeSetup();return;}
 if(!$('setup-dialog').open)$('setup-dialog').showModal();setupView(s.step);
}
async function setupStep(step){setupMessage();const s=await onboardingStep(step);if(s.complete)await closeSetup();else setupView(s.step);}
async function setupAction(action){
 if(setupBusy)return;setupBusy=true;setupMessage();for(const b of document.querySelectorAll('#setup-dialog button'))b.disabled=true;
 try{await action();}
 catch(e){if(e.name!=='AbortError')setupMessage(e.message||'파일을 연결하지 못했습니다. 다시 선택해 주세요.');}
 finally{setupBusy=false;for(const b of document.querySelectorAll('#setup-dialog button'))b.disabled=false;await syncSetup();}
}
$('setup-local').onclick=()=>setupAction(async()=>{await finishOnboarding('local');await closeSetup();});
$('setup-team').onclick=guard(()=>setupStep('file'));
$('setup-back').onclick=guard(()=>setupStep('choose'));
$('setup-dialog').addEventListener('cancel',e=>e.preventDefault());
$('setup-new-file').onclick=()=>setupAction(async()=>{
 const h=await teamPicker('save');
 await createTeamFile(h);await finishOnboarding('file',h);await closeSetup();
});
$('setup-open-file').onclick=()=>setupAction(async()=>{
 const [h]=await teamPicker('open');
 const f=await h.getFile();if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');parseConfig(await f.text());
 await requestFileAccess(h,'readwrite');await finishOnboarding('file',h);await closeSetup();
});
$('setup-access-settings').onclick=guard(()=>chrome.tabs.create({url:'chrome://flags/#file-system-access-api'}));
$('setup-access-copy').onclick=guard(async()=>{await navigator.clipboard.writeText('brave://flags/#file-system-access-api');setupMessage('설정 주소를 복사했습니다. 주소창에 붙여 넣어 주세요.');});
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.onboarding?.newValue?.complete)syncSetup();if(area==='local'&&changes.appearance){appearance=normalizeAppearance(changes.appearance.newValue);syncAppearance();}if(area==='local'&&['profiles','settings','teamChangedAt'].some(k=>changes[k])&&!document.querySelector('dialog[open]'))load();if(area==='session'&&Object.keys(changes).some(k=>k.startsWith('status:')))updateStatus();});
setInterval(()=>{if(!document.hidden)updateStatus();},1500);
function refreshTeam(){if(!document.hidden&&sourceSettings?.mode==='file'&&!sourceReading&&!launching&&!document.querySelector('dialog[open]'))load();}
window.addEventListener('focus',refreshTeam);document.addEventListener('visibilitychange',refreshTeam);setInterval(refreshTeam,5000);
window.addEventListener('pagehide',()=>{resetSecrets();$('account-form').reset();pending=null;});
appearance=normalizeAppearance((await chrome.storage.local.get('appearance')).appearance);syncAppearance();await load({requestOnOpen:true});(sourceError?.code==='TEAM_PERMISSION'?$('restore-team'):$('search')).focus();await syncSetup();
