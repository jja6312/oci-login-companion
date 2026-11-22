import {normalizeProfile,parseConfig,mergeProfiles,MAX_BYTES,patternsFor} from './lib/model.js';
import {settingsGet,personalGet,personalSet,readSource} from './lib/sources.js';
import {handleGet,handleSet} from './lib/db.js';
import {normalizeAppearance,applyAppearance,ACCENT_PRESETS} from './lib/appearance.js';
import {icon} from './lib/icons.js';
import {parseBulkColumns,appendBulkProfiles,columnRows} from './lib/bulk.js';
const $=id=>document.getElementById(id);
for(const el of document.querySelectorAll('[data-icon]'))el.replaceChildren(icon(el.dataset.icon));
let profiles=[],filtered=[],selectedId=null,sourceSettings,sourceLabel='',editing=null,pending=null,launching=false,job=null;
let appearance=normalizeAppearance(),revealed=new Set(),toastTimer,messageTimer;
const selected=()=>profiles.find(p=>p.id===selectedId);
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,2400);}
function message(text,error=false){clearTimeout(messageTimer);$('message').textContent=text;$('message').classList.toggle('error',error);$('message').hidden=!text;if(text)messageTimer=setTimeout(()=>$('message').hidden=true,7000);}
function settingsMessage(text,error=false){$('settings-message').textContent=text;$('settings-message').hidden=!text;$('settings-message').classList.toggle('error',error);}
function guard(fn,settings=false){return async(...args)=>{try{await fn(...args);}catch(e){if(e.name==='AbortError')return;(settings?settingsMessage:message)(e.message||'작업을 완료하지 못했습니다.',true);}};}
function resetSecrets(){revealed.clear();for(const b of document.querySelectorAll('[data-reveal]')){b.setAttribute('aria-pressed','false');b.replaceChildren(icon('Eye'));}}
async function load(){
  try{sourceSettings=await settingsGet();const source=await readSource();profiles=source.profiles;sourceLabel=source.label;message('');}
  catch(e){profiles=[];sourceLabel=sourceSettings?.mode==='file'?'팀 파일 연결 필요':'개인 저장소';message(e.message,true);}
  $('source-label').textContent=sourceSettings?.mode==='file'?'팀 파일':'개인 저장소';$('source').title=sourceLabel;
  $('add').disabled=sourceSettings?.mode!=='local';$('add').title=$('add').disabled?'팀 파일은 읽기 전용입니다. 설정에서 개인 저장소로 변경하세요.':'계정 추가 (Alt + N)';
  resetSecrets();render();await updateStatus();
}
function render(){
  const q=$('search').value.trim().toLocaleLowerCase();
  filtered=profiles.filter(p=>[p.tenancy,p.name,p.username].some(v=>v.toLocaleLowerCase().includes(q))).sort((a,b)=>{
    const score=p=>[p.tenancy,p.name].some(v=>v.toLocaleLowerCase()===q)?0:[p.tenancy,p.name].some(v=>v.toLocaleLowerCase().startsWith(q))?1:2;
    return score(a)-score(b)||a.tenancy.localeCompare(b.tenancy);
  });
  if(!filtered.some(p=>p.id===selectedId))selectedId=filtered[0]?.id||null;
  $('count').textContent=profiles.length;$('accounts').replaceChildren();
  if(!filtered.length&&(profiles.length||sourceSettings?.mode==='file')){const e=document.createElement('p');e.className='empty';e.textContent=profiles.length?'검색 결과가 없습니다.':sourceSettings?.mode==='file'?'설정에서 팀 파일을 연결해 주세요.':'계정을 추가하거나 설정 파일을 가져오세요.';$('accounts').append(e);}
  for(const p of filtered){const row=document.createElement('button');row.type='button';row.className='account-row';row.role='option';row.id='row-'+p.id;row.dataset.id=p.id;row.setAttribute('aria-selected',String(p.id===selectedId));const mark=document.createElement('span');mark.className='tenant-mark';mark.textContent='O';const info=document.createElement('span');info.className='account-info';const title=document.createElement('strong');title.textContent=p.tenancy;title.title=p.tenancy;const sub=document.createElement('small');sub.textContent=p.name!==p.tenancy?p.name:p.username;sub.title=p.username;info.append(title,sub);row.append(mark,info);row.onclick=()=>select(p.id);row.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(!e.repeat){select(p.id);launch('login');}}};$('accounts').append(row);}
  renderDetails();
}
function select(id){if(id!==selectedId){selectedId=id;resetSecrets();$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');$('detail-content').querySelector('details').open=false;}for(const row of document.querySelectorAll('.account-row'))row.setAttribute('aria-selected',String(row.dataset.id===id));renderDetails();}
function renderDetails(){
  const p=selected();$('detail-content').hidden=!p;$('empty-detail').hidden=!!p;
  $('empty-add').hidden=sourceSettings?.mode!=='local';
  if(!p)return;
  $('detail-title').textContent=p.tenancy;$('detail-title').title=p.tenancy;$('detail-subtitle').textContent=[p.name!==p.tenancy?p.name:'',p.identityDomain||'기본 도메인'].filter(Boolean).join(' · ');
  $('username').textContent=p.username;
  for(const key of ['password','bypassCode']){$(key).textContent=revealed.has(key)?p[key]:'••••••••••••';$(key).classList.toggle('masked',!revealed.has(key));}
  $('detail-domain').textContent=p.identityDomain||'지정하지 않음';$('detail-name').textContent=p.name;$('detail-source').textContent=sourceLabel;
  $('edit').disabled=sourceSettings?.mode!=='local';$('delete').hidden=sourceSettings?.mode!=='local';renderJob();
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
$('refresh').onclick=guard(load);
$('more').onclick=()=>{const open=$('more-menu').hidden;$('more-menu').hidden=!open;$('more').setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.target.closest('.more-wrap')){$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('more-menu').hidden=true;$('more').setAttribute('aria-expanded','false');resetSecrets();renderDetails();}});
for(const b of document.querySelectorAll('[data-reveal]'))b.onclick=()=>{const k=b.dataset.reveal;if(revealed.has(k))revealed.delete(k);else revealed.add(k);b.setAttribute('aria-pressed',String(revealed.has(k)));b.replaceChildren(icon(revealed.has(k)?'EyeOff':'Eye'));renderDetails();};
for(const b of document.querySelectorAll('[data-copy]'))b.onclick=guard(async()=>{const p=selected();if(!p)return;await navigator.clipboard.writeText(p[b.dataset.copy]);toast('복사했습니다');});
function openEdit(p){if(sourceSettings?.mode!=='local')return;editing=p||null;$('edit-title').textContent=p?'계정 편집':'계정 추가';$('account-form').reset();for(const [id,value] of Object.entries({'p-name':p?.name===p?.tenancy?'':p?.name||'','p-tenancy':p?.tenancy||'','p-domain':p?.identityDomain??'Default','p-username':p?.username||'','p-password':p?.password||'','p-bypass':p?.bypassCode||'','p-selectors':p&&Object.keys(p.selectors).length?JSON.stringify(p.selectors,null,2):''}))$(id).value=value;$('edit-error').textContent='';$('show-secrets').checked=false;toggleSecrets();$('edit-dialog').querySelector('details').open=false;$('edit-dialog').showModal();$('p-tenancy').focus();}
function closeEdit(){$('edit-dialog').close();$('account-form').reset();editing=null;}
function toggleSecrets(){for(const id of ['p-password','p-bypass'])$(id).type=$('show-secrets').checked?'text':'password';}
$('account-form').onsubmit=async e=>{e.preventDefault();try{if((await settingsGet()).mode!=='local')throw new Error('개인 저장소를 선택한 뒤 편집해 주세요.');let selectors;try{selectors=$('p-selectors').value.trim()?JSON.parse($('p-selectors').value):{};}catch{throw new Error('선택자 JSON 형식을 확인해 주세요.');}for(const value of Object.values(selectors||{}))if(typeof value==='string'&&value)document.querySelector(value);const targetSame=editing&&editing.tenancy===$('p-tenancy').value.trim()&&editing.username===$('p-username').value.trim()&&editing.identityDomain===$('p-domain').value.trim();const p=normalizeProfile({id:editing?.id||crypto.randomUUID(),name:$('p-name').value,tenancy:$('p-tenancy').value,identityDomain:$('p-domain').value,username:$('p-username').value,password:$('p-password').value,bypassCode:$('p-bypass').value,identityOrigins:targetSame?editing.identityOrigins:[],selectors});const personal=await personalGet();await personalSet(editing?personal.map(x=>x.id===editing.id?p:x):[...personal,p]);selectedId=p.id;$('search').value='';closeEdit();await load();toast('계정을 저장했습니다');}catch(err){$('edit-error').textContent=err.message;}};
document.addEventListener('keydown',e=>{if(e.altKey&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&e.code==='KeyN'){if(document.querySelector('dialog[open]'))return;e.preventDefault();if(!e.repeat)openEdit();}},true);
$('add').onclick=()=>openEdit();$('empty-add').onclick=()=>openEdit();$('edit').onclick=()=>openEdit(selected());$('close-edit').onclick=closeEdit;$('cancel-edit').onclick=closeEdit;$('edit-dialog').addEventListener('cancel',e=>{e.preventDefault();closeEdit();});$('show-secrets').onchange=toggleSecrets;
let bulkDraft=null,bulkSaving=false;
function clearBulkReview(){bulkDraft=null;$('bulk-review').hidden=true;$('bulk-rows').replaceChildren();$('bulk-save').disabled=true;$('bulk-save').textContent='일괄 등록';$('bulk-error').textContent='';}
function closeBulk(){if(bulkSaving)return;$('bulk-dialog').close();$('bulk-form').reset();for(const t of document.querySelectorAll('[data-column]')){$('bulk-count-'+t.dataset.column).textContent='0행';}clearBulkReview();toggleBulkSecrets();}
function toggleBulkSecrets(){for(const k of ['password','bypassCode'])$('bulk-'+k).classList.toggle('secret-column',!$('bulk-show-secrets').checked);}
$('bulk-open').onclick=guard(async()=>{if((await settingsGet()).mode!=='local')throw new Error('팀 파일은 읽기 전용입니다. 개인 저장소에서 일괄 등록한 뒤 JSON으로 내보낼 수 있습니다.');clearBulkReview();$('bulk-dialog').showModal();$('bulk-tenancy').focus();});
for(const t of document.querySelectorAll('[data-column]'))t.oninput=()=>{clearBulkReview();try{$('bulk-count-'+t.dataset.column).textContent=columnRows(t.value,t.dataset.column).length+'행';}catch{$('bulk-count-'+t.dataset.column).textContent='확인 필요';}};
$('bulk-preview').onclick=async()=>{clearBulkReview();try{
  const raw=Object.fromEntries([...document.querySelectorAll('[data-column]')].map(t=>[t.dataset.column,t.value]));
  const draft=parseBulkColumns(raw);appendBulkProfiles(await personalGet(),draft);
  for(const t of document.querySelectorAll('[data-column]')){t.scrollTop=0;t.scrollLeft=0;}
  for(const [i,p] of draft.entries()){const tr=document.createElement('tr');for(const value of [i+1,p.tenancy,p.name===p.tenancy?'—':p.name,p.username,p.identityDomain]){const td=document.createElement('td');td.textContent=String(value);tr.append(td);}$('bulk-rows').append(tr);}
  bulkDraft=draft;$('bulk-summary').textContent=`${draft.length}개 계정을 추가할 준비가 됐습니다.`;$('bulk-review').hidden=false;$('bulk-save').disabled=false;$('bulk-save').textContent=draft.length+'개 등록';
}catch(e){$('bulk-error').textContent=e.message;}};
$('bulk-form').onsubmit=async e=>{e.preventDefault();if(!bulkDraft||bulkSaving)return;const submitted=bulkDraft;bulkSaving=true;$('bulk-preview').disabled=true;for(const t of document.querySelectorAll('[data-column]'))t.readOnly=true;$('bulk-save').disabled=true;$('bulk-save').textContent='등록 중…';try{
  const r=await chrome.runtime.sendMessage({type:'BULK_ADD',profiles:submitted});if(!r?.ok)throw new Error(r?.error||'일괄 등록을 완료하지 못했습니다.');
  const first=submitted[0].id;bulkSaving=false;closeBulk();selectedId=first;$('search').value='';await load();toast(r.count+'개 계정을 등록했습니다');
}catch(e){$('bulk-error').textContent=e.message;$('bulk-save').disabled=false;$('bulk-save').textContent='다시 등록';}finally{bulkSaving=false;$('bulk-preview').disabled=false;for(const t of document.querySelectorAll('[data-column]'))t.readOnly=false;}};
$('close-bulk').onclick=closeBulk;$('cancel-bulk').onclick=closeBulk;$('bulk-dialog').addEventListener('cancel',e=>{e.preventDefault();closeBulk();});$('bulk-show-secrets').onchange=toggleBulkSecrets;
window.addEventListener('pagehide',()=>{bulkDraft=null;for(const t of document.querySelectorAll('[data-column]'))t.value='';});
$('delete').onclick=()=>{const p=selected();if(!p)return;$('more-menu').hidden=true;$('delete-name').textContent=p.tenancy;$('delete-dialog').showModal();};
$('delete-dialog').addEventListener('close',guard(async()=>{if($('delete-dialog').returnValue!=='delete')return;if((await settingsGet()).mode!=='local')throw new Error('팀 파일은 읽기 전용입니다.');await personalSet((await personalGet()).filter(p=>p.id!==selectedId));await load();toast('계정을 삭제했습니다');}));
function setSettingsTab(name){for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b.dataset.tab===name));for(const s of document.querySelectorAll('[data-panel]'))s.hidden=s.dataset.panel!==name;settingsMessage('');}
async function openSettings(tab='appearance'){await syncStorage();setSettingsTab(tab);syncAppearance();$('settings-dialog').showModal();}
$('settings').onclick=guard(()=>openSettings());$('source').onclick=guard(()=>openSettings('storage'));$('close-settings').onclick=()=>$('settings-dialog').close();for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>setSettingsTab(b.dataset.tab);
$('settings-dialog').addEventListener('close',()=>{pending=null;$('import-file').value='';$('import-confirm').disabled=true;$('import-preview').textContent='';$('export-ack').checked=false;$('export').disabled=true;});
function syncAppearance(){applyAppearance(appearance);$('theme-mode').value=appearance.mode;$('theme-accent').value=appearance.accent;$('accent-value').textContent=appearance.accent.toUpperCase();for(const b of document.querySelectorAll('.swatch'))b.setAttribute('aria-pressed',String(b.dataset.color===appearance.accent));}
async function saveAppearance(next){appearance=normalizeAppearance(next);syncAppearance();await chrome.storage.local.set({appearance});}
for(const id of ['accent-presets','quick-presets'])for(const [i,color] of ACCENT_PRESETS.entries()){const b=document.createElement('button');b.type='button';b.className='swatch';b.dataset.color=color;b.style.setProperty('--swatch',color);b.setAttribute('aria-label',['퍼플','블루','민트','로즈','오렌지','그레이'][i]+' 테마색');b.onclick=guard(()=>saveAppearance({...appearance,accent:color}),id==='accent-presets');$(id).append(b);}
$('theme-mode').onchange=guard(()=>saveAppearance({...appearance,mode:$('theme-mode').value}),true);$('theme-accent').oninput=guard(()=>saveAppearance({...appearance,accent:$('theme-accent').value}),true);matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>applyAppearance(appearance));
async function syncStorage(){sourceSettings=await settingsGet();document.querySelector(`[name=mode][value="${sourceSettings.mode==='file'?'file':'local'}"]`).checked=true;$('file-kind').value=sourceSettings.fileKind==='native'?'native':'picker';$('native-path').value=sourceSettings.nativePath||'';const h=await handleGet();$('file-name').textContent=h?.name||'연결한 파일 없음';fileView();}
function fileView(){$('file-settings').hidden=document.querySelector('[name=mode]:checked')?.value!=='file';$('picker-settings').hidden=$('file-kind').value!=='picker';$('native-settings').hidden=$('file-kind').value!=='native';}
for(const r of document.querySelectorAll('[name=mode]'))r.onchange=fileView;$('file-kind').onchange=fileView;
$('pick-file').onclick=guard(async()=>{if(!window.showOpenFilePicker)throw new Error('이 브라우저에서는 전체 경로 연결을 사용해 주세요.');const [h]=await showOpenFilePicker({types:[{description:'OCI 계정 JSON',accept:{'application/json':['.json']}}],multiple:false});const f=await h.getFile();if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');parseConfig(await f.text());await handleSet(h);$('file-name').textContent=h.name;settingsMessage('파일을 연결했습니다. 저장 위치 적용을 눌러 주세요.');},true);
$('regrant').onclick=guard(async()=>{const h=await handleGet();if(!h)throw new Error('먼저 파일을 선택해 주세요.');if(await h.requestPermission({mode:'read'})!=='granted')throw new Error('파일 읽기 권한이 필요합니다.');settingsMessage('파일 읽기 권한을 허용했습니다.');},true);
$('allow-native').onclick=guard(async()=>{if(!await chrome.permissions.request({permissions:['nativeMessaging']}))throw new Error('보조 프로그램 권한을 허용해 주세요.');settingsMessage('보조 프로그램 사용을 허용했습니다.');},true);
$('storage-form').onsubmit=guard(async e=>{e.preventDefault();const next={mode:document.querySelector('[name=mode]:checked').value,fileKind:$('file-kind').value,nativePath:$('native-path').value.trim()};if(next.mode==='file'&&next.fileKind==='native'&&!next.nativePath)throw new Error('전체 경로를 입력해 주세요.');await chrome.storage.local.set({settings:next});selectedId=null;await load();settingsMessage('저장 위치를 적용했습니다.');$('source-result').textContent='';},true);
$('check-source').onclick=guard(async()=>{const r=await readSource();$('source-result').textContent=`${r.profiles.length}개 계정을 읽었습니다. ${r.label}`;},true);
$('import-file').onchange=guard(async()=>{pending=null;$('import-confirm').disabled=true;const f=$('import-file').files[0];if(!f)return;if(f.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');pending=parseConfig(await f.text()).profiles;$('import-preview').textContent=`${pending.length}개 계정을 확인했습니다.`;$('import-confirm').disabled=false;},true);
$('import-confirm').onclick=guard(async()=>{if(!pending)return;const result=mergeProfiles(await personalGet(),pending,$('allow-updates').checked);await personalSet(result);pending=null;$('import-file').value='';$('import-confirm').disabled=true;$('import-preview').textContent='가져오기를 완료했습니다.';await load();settingsMessage(`개인 저장소에 ${result.length}개 계정이 있습니다.`);},true);
function download(name,value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}
$('export-ack').onchange=()=>$('export').disabled=!$('export-ack').checked;
$('export').onclick=guard(async()=>{if(!$('export-ack').checked)return;const r=await readSource();download(`oci-accounts-${new Date().toISOString().slice(0,10)}.json`,{schemaVersion:1,profiles:r.profiles});},true);
$('template').onclick=()=>download('oci-accounts.example.json',{schemaVersion:1,profiles:[{id:'replace-this-id',name:'서울 운영 계정',tenancy:'replace-tenancy',identityDomain:'Default',username:'replace-username',password:'REPLACE_PASSWORD',bypassCode:'REPLACE_ADMIN_BYPASS_CODE'}]});
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.appearance){appearance=normalizeAppearance(changes.appearance.newValue);syncAppearance();}if(area==='session'&&Object.keys(changes).some(k=>k.startsWith('status:')))updateStatus();});
setInterval(()=>{if(!document.hidden)updateStatus();},1500);
window.addEventListener('pagehide',()=>{resetSecrets();$('account-form').reset();pending=null;});
appearance=normalizeAppearance((await chrome.storage.local.get('appearance')).appearance);syncAppearance();await load();$('search').focus();
