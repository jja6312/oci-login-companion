import {normalizeProfile,patternsFor,CONSOLE_ORIGIN,bindingKey,canLearnIdentity,isAutoIdentityOrigin,isBrokerOrigin,routingKind,isOAuthBridge,BROKER_ORIGIN,canEnterBroker,ENTRY_ORIGIN,ENTRY_PATH,ENTRY_PATTERN,canEnterEntry} from './lib/model.js';
import {readSource,writeList,sourceRef} from './lib/sources.js';
import {appendBulkProfiles} from './lib/bulk.js';
import {validateLaunchWindow} from './lib/windows.js';
import {trace,snapshot,diagnosticReport} from './lib/diagnostics.js';
const ready=Promise.all([chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}),chrome.storage.session.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'})]);
const queues=new Map(),ttl=180000;
class UserError extends Error{}
const isUI=s=>s.id===chrome.runtime.id&&['popup.html','options.html'].some(p=>s.url?.split(/[?#]/)[0]===chrome.runtime.getURL(p));
function queue(key,fn){const task=(queues.get(key)||Promise.resolve()).catch(()=>{}).then(async()=>{await ready;return fn();});queues.set(key,task);task.finally(()=>{if(queues.get(key)===task)queues.delete(key);}).catch(()=>{});return task;}
async function getJob(id){const key=`job:${id}`,j=(await chrome.storage.session.get(key))[key];if(j&&j.expiresAt<=Date.now()){await finish(id,'시간이 지났습니다. 다시 로그인해 주세요.','stopped','expired');return null;}return j;}
async function putJob(id,j){await chrome.storage.session.set({[`job:${id}`]:j});}
async function status(id,message,step='waiting',extra={}){const j=(await chrome.storage.session.get(`job:${id}`))[`job:${id}`];await chrome.storage.session.set({[`status:${id}`]:{tabId:id,profileId:j?.profile.id,tenancy:j?.profile.tenancy,incognito:!!j?.incognito,message,step,at:Date.now(),running:!!j,reason:'none',debug:snapshot(j),...extra}});}
async function finish(id,message,step='stopped',reason='none'){
  const j=(await chrome.storage.session.get(`job:${id}`))[`job:${id}`];const prior=(await chrome.storage.session.get(`status:${id}`))[`status:${id}`];
  if(j)trace(j,step==='complete'?'complete':'stopped');
  await chrome.storage.session.remove(`job:${id}`);await chrome.alarms.clear(`expire:${id}`);
  await chrome.storage.session.set({[`status:${id}`]:{tabId:id,profileId:j?.profile.id??prior?.profileId,tenancy:j?.profile.tenancy??prior?.tenancy,incognito:j?.incognito??prior?.incognito??false,message,step,at:Date.now(),running:false,reason,debug:j?snapshot(j):prior?.debug}});
  await chrome.action.setBadgeText({tabId:id,text:''}).catch(()=>{});
}
async function register(){const p=await chrome.permissions.getAll();const matches=(p.origins||[]).filter(x=>/^https:\/\/[^*]+\/\*$/.test(x)).filter(x=>!isBrokerOrigin(new URL(x).origin)||new URL(x).origin===BROKER_ORIGIN).map(x=>x.startsWith(ENTRY_ORIGIN+'/')?ENTRY_PATTERN:x);await chrome.scripting.unregisterContentScripts().catch(()=>{});if(matches.length)await chrome.scripting.registerContentScripts([{id:'oci-flow',matches,js:['engine.js','content.js'],runAt:'document_idle',allFrames:false,persistAcrossSessions:true}]);}
async function committed(d){
  if(d.frameId!==0||d.url==='about:blank'||d.url===chrome.runtime.getURL('launch.html'))return;
  const j=await getJob(d.tabId);if(!j)return;
  let origin;try{origin=new URL(d.url).origin;}catch{return;}
  trace(j,'navigate',{host:routingKind(origin),transition:d.transitionType,qualifiers:d.transitionQualifiers});await putJob(d.tabId,j);
  if(origin===CONSOLE_ORIGIN){j.activeOrigin=origin;j.documentId=d.documentId;await putJob(d.tabId,j);return;}
  if(origin===ENTRY_ORIGIN){if(!canEnterEntry(j,d)){await finish(d.tabId,'확인되지 않은 Oracle 페이지에서 중지했습니다.');return;}j.activeOrigin=origin;j.documentId=d.documentId;await putJob(d.tabId,j);return;}
  if(isBrokerOrigin(origin)){if(!canEnterBroker(j,d)){await finish(d.tabId,'확인되지 않은 세션 선택 이동에서 중지했습니다. 다시 로그인해 주세요.','stopped','navigation-rejected');return;}j.activeOrigin=origin;j.documentId=d.documentId;await putJob(d.tabId,j);await status(d.tabId,origin===BROKER_ORIGIN?'OCI 세션 선택 또는 새 로그인 화면을 확인하는 중입니다.':'OCI 인증 서버를 거쳐 이동하는 중입니다.','broker');return;}
  if(j.profile.identityOrigins.includes(origin)||j.activeIdentity===origin){j.activeIdentity=origin;j.activeOrigin=origin;j.documentId=d.documentId;await putJob(d.tabId,j);return;}
  if(canLearnIdentity(j,d)){j.activeIdentity=origin;j.activeOrigin=origin;j.documentId=d.documentId;j.learned=true;trace(j,'identity-ready');await putJob(d.tabId,j);await status(d.tabId,'OCI 인증 화면을 확인했습니다.','identity');return;}
  await finish(d.tabId,'확인되지 않은 인증 화면에서 중지했습니다. 메뉴의 진단 정보 복사를 사용해 주세요.','stopped',isAutoIdentityOrigin(origin)&&!j.tenancyVerified?'unverified-tenancy':'unsupported-origin');
}
async function inject(id,url,documentId){
  const j=await getJob(id);if(!j||!url||url==='about:blank')return;
  if(documentId&&j.documentId!==documentId)return;
  const origin=new URL(url).origin;
  if(isOAuthBridge(url))return;
  if(isBrokerOrigin(origin)&&origin!==BROKER_ORIGIN)return;
  // Regional OAuth brokers forward the browser themselves. Track their trusted
  // navigation only; inject no code and provide them no credentials or metadata.
  if(origin!==CONSOLE_ORIGIN&&origin!==BROKER_ORIGIN&&origin!==ENTRY_ORIGIN&&origin!==j.activeIdentity)return;
  if(origin===ENTRY_ORIGIN&&new URL(url).pathname!==ENTRY_PATH)return;
  try{trace(j,'injected');await putJob(id,j);await chrome.scripting.executeScript({target:{tabId:id,...(j.documentId?{documentIds:[j.documentId]}:{})},files:['engine.js','content.js'],injectImmediately:true});}
  catch{
    const current=await getJob(id);if(!current||current.expiresAt!==j.expiresAt)return;
    const frame=await chrome.webNavigation.getFrame({tabId:id,frameId:0}).catch(()=>null);
    // A self-submitting OAuth document can disappear while its script request
    // is queued. The next committed document gets its own readiness event.
    if(!frame||frame.documentId!==j.documentId){trace(current,'injection-stale');await putJob(id,current);return;}
    const granted=await chrome.permissions.contains({origins:[origin===ENTRY_ORIGIN?ENTRY_PATTERN:origin+'/*']}).catch(()=>false);
    if(!granted){await finish(id,'OCI 화면 접근 권한을 확인해 주세요.','stopped','access-denied');return;}
    const failures=current.injectionFailure?.documentId===j.documentId?current.injectionFailure.count+1:1;
    if(failures>=3){await finish(id,'OCI 입력 코드를 실행하지 못했습니다. 메뉴의 진단 정보 복사를 사용해 주세요.','stopped','injection-failed');return;}
    current.injectionFailure={documentId:j.documentId,count:failures};trace(current,'injection-retry');await putJob(id,current);
    setTimeout(()=>queue(id,()=>inject(id,frame.url,frame.documentId)).catch(()=>{}),250);
  }
}
async function start(m){
  let scope;
  try{scope=validateLaunchWindow(m,await chrome.windows.get(m.windowId));}catch{throw new UserError('로그인을 시작한 창을 찾지 못했습니다. 그 창에서 확장을 다시 열어 주세요.');}
  if(scope.incognito&&!await chrome.extension.isAllowedIncognitoAccess())throw new UserError('확장 관리 화면에서 시크릿 모드 사용을 먼저 허용해 주세요.');
  const source=await readSource();const found=source.profiles.find(p=>p.id===m.profileId);
  if(!found)throw new UserError('계정이 변경되었습니다. 목록을 다시 읽어 주세요.');
  const profile=normalizeProfile(found);
  if(!m.expected||['tenancy','username','identityDomain'].some(k=>m.expected[k]!==profile[k]))throw new UserError('선택한 계정이 변경되었습니다. 목록을 다시 읽고 선택해 주세요.');
  const bindings=(await chrome.storage.local.get('identityBindings')).identityBindings||{};
  const prior=bindings[bindingKey(profile)];
  if(prior?.origin&&isAutoIdentityOrigin(prior.origin))profile.identityOrigins=[...new Set([...profile.identityOrigins,prior.origin])];
  if(!await chrome.permissions.contains({origins:patternsFor(profile)}))throw new UserError('OCI 로그인 화면 접근을 먼저 허용해 주세요.');
  let tab,activeIdentity=null,documentId=null;
  if(m.mode==='fill'){
    tab=(await chrome.tabs.query({active:true,windowId:scope.windowId}))[0];
    if(!tab||tab.incognito!==scope.incognito)throw new UserError('같은 창의 OCI 로그인 탭에서 다시 실행해 주세요.');
    const origin=tab?.url?new URL(tab.url).origin:'';
    if((isBrokerOrigin(origin)&&origin!==BROKER_ORIGIN)||(origin!==CONSOLE_ORIGIN&&!profile.identityOrigins.includes(origin)))throw new UserError('이 계정으로 확인한 OCI 로그인 탭에서 사용해 주세요. 먼저 자동 로그인을 한 번 실행할 수 있습니다.');
    if(origin!==CONSOLE_ORIGIN)activeIdentity=origin;
    documentId=(await chrome.webNavigation.getFrame({tabId:tab.id,frameId:0}))?.documentId;
  }else{
    // A spanning extension cannot load its own page in a private tab. The blank
    // placeholder stays in the caller's actual window and carries no secrets.
    tab=await chrome.tabs.create({windowId:scope.windowId,url:scope.incognito?'about:blank':chrome.runtime.getURL('launch.html'),active:true});
    if(tab.windowId!==scope.windowId||tab.incognito!==scope.incognito){await chrome.tabs.remove(tab.id);throw new UserError('같은 창에 로그인 탭을 열지 못했습니다. 다시 실행해 주세요.');}
    // tabs.create resolves before the first document finishes loading. Wait for
    // our own document before replacing it, so its initial navigation cannot
    // overwrite the OCI navigation in a newly attached browser target.
    await new Promise((resolve,reject)=>{
      let done=false;
      const end=error=>{if(done)return;done=true;clearTimeout(timer);chrome.tabs.onUpdated.removeListener(listener);error?reject(error):resolve();};
      const listener=(id,change)=>{if(id===tab.id&&change.status==='complete')end();};
      const timer=setTimeout(()=>end(new UserError('로그인 탭을 준비하지 못했습니다. 다시 실행해 주세요.')),10000);
      chrome.tabs.onUpdated.addListener(listener);
      chrome.tabs.get(tab.id).then(t=>{if(t.status==='complete')end();},()=>end(new UserError('로그인 탭이 닫혔습니다.')));
    });
  }
  // The first HTTP redirect can commit directly at Oracle's account entry:
  // cloud.oracle.com itself need not produce a committed document.
  const j={profile,...scope,mode:m.mode==='fill'?'fill':'login',expiresAt:Date.now()+ttl,claims:{},applied:{},tenancyVerified:false,activeOrigin:m.mode==='fill'?new URL(tab.url).origin:CONSOLE_ORIGIN,activeIdentity,documentId};
  trace(j,'start');
  await putJob(tab.id,j);await chrome.alarms.create(`expire:${tab.id}`,{when:j.expiresAt});await status(tab.id,'테넌시 로그인 화면을 여는 중입니다.');
  await chrome.action.setBadgeText({tabId:tab.id,text:'…'});await register();
  if(m.mode==='fill')await inject(tab.id,tab.url);else await chrome.tabs.update(tab.id,{url:CONSOLE_ORIGIN+'/'});
  return {ok:true,tabId:tab.id};
}
const stages=['sessionPick','newLogin','changeTenancy','tenancy','domainOpen','domainPick','domain','credentials','username','alternative','bypassChoice','bypass'];
const stageText={sessionPick:'일치하는 기존 OCI 세션 선택',newLogin:'다른 계정으로 새 로그인 시작',changeTenancy:'테넌시 선택 화면 열기',tenancy:'테넌시 입력',domainOpen:'Identity Domain 목록 열기',domainPick:'Identity Domain 항목 선택',domain:'Identity Domain 확인',credentials:'아이디·비밀번호 입력',username:'아이디 입력',alternative:'다른 인증 방식 선택',bypassChoice:'Bypass Code 방식 선택',bypass:'Bypass Code 입력'};
async function handle(m,s){
  if(isUI(s)){
    if(m.type==='START')return start(m);
    if(m.type==='STATUS'){const scope=validateLaunchWindow(m,await chrome.windows.get(m.windowId));const all=await chrome.storage.session.get(null);return {ok:true,items:Object.entries(all).filter(([k])=>k.startsWith('status:')).map(([,v])=>v).filter(v=>!!v.incognito===scope.incognito).sort((a,b)=>b.at-a.at).slice(0,12)};}
    if(m.type==='DIAGNOSTICS'){
      const scope=validateLaunchWindow(m,await chrome.windows.get(m.windowId));const all=await chrome.storage.session.get(null);const st=Object.entries(all).filter(([k])=>k.startsWith('status:')).map(([,v])=>v).filter(v=>v.profileId===m.profileId&&!!v.incognito===scope.incognito).sort((a,b)=>b.at-a.at)[0];
      const job=st&&all[`job:${st.tabId}`];return {ok:true,report:diagnosticReport(job?{...st,debug:snapshot(job)}:st,chrome.runtime.getManifest().version,scope.incognito)};
    }
    if(m.type==='BULK_ADD'){
      try{const base=await readSource();if(!base.writable)throw new Error('브라우저에서 팀 파일 쓰기를 허용해 주세요.');const ref=sourceRef(base);if(!m.source||m.source.target!==ref.target||(m.source.connection??null)!==ref.connection)throw new Error('저장 위치가 변경되었습니다. 일괄 등록을 다시 열어 주세요.');const next=appendBulkProfiles(base.profiles,m.profiles);await writeList(base,next);return {ok:true,count:m.profiles.length};}catch(e){throw new UserError(e.message);}
    }
    if(m.type==='CANCEL'){await finish(m.tabId,'자동 로그인을 중지했습니다.','stopped','cancelled');return {ok:true};}
    if(m.type==='REGISTER'){await register();return {ok:true};}
    return {ok:false};
  }
  if(s.id!==chrome.runtime.id||!s.tab?.id||s.frameId!==0)return {ok:false};
  const id=s.tab.id,j=await getJob(id);if(!j||!!s.tab.incognito!==!!j.incognito)return {ok:false};
  const origin=new URL(s.url).origin;
  if(isOAuthBridge(s.url))return {ok:false};
  if((origin===ENTRY_ORIGIN&&new URL(s.url).pathname!==ENTRY_PATH)||origin!==j.activeOrigin||(j.documentId&&s.documentId!==j.documentId))return {ok:false};
  if(isBrokerOrigin(origin)&&origin!==BROKER_ORIGIN)return {ok:false};
  const broker=origin===BROKER_ORIGIN;
  const identity=(!broker&&origin===j.activeIdentity)||(broker&&j.tenancyVerified&&!!(j.applied.tenancy||j.sessionVerified));
  if(m.type==='CONTEXT')return {ok:true,context:{tenancy:j.profile.tenancy,identityDomain:j.profile.identityDomain,selectors:j.profile.selectors,identity,broker,username:broker?j.profile.username:undefined,mode:j.mode,expiresAt:j.expiresAt,tenancyVerified:j.tenancyVerified,applied:Object.keys(j.applied)}};
  if(m.type==='CLAIM'){
    if(!stages.includes(m.stage)||j.claims[m.stage]||(['sessionPick','newLogin'].includes(m.stage)&&!broker)||(['credentials','username','alternative','bypassChoice','bypass'].includes(m.stage)&&!identity))return {ok:false};
    j.claims[m.stage]=true;trace(j,'claim',{stage:m.stage});await putJob(id,j);
    const fields={tenancy:{value:j.profile.tenancy},domain:{value:j.profile.identityDomain},credentials:{username:j.profile.username,password:j.profile.password},username:{value:j.profile.username},bypass:{value:j.profile.bypassCode}};
    await status(id,stageText[m.stage]+' 중',m.stage);return {ok:true,fields:fields[m.stage]||{}};
  }
  if(m.type==='APPLIED'){
    if(!j.claims[m.stage])return {ok:false};j.applied[m.stage]=true;
    trace(j,'applied',{stage:m.stage});
    if(m.stage==='tenancy'&&[CONSOLE_ORIGIN,ENTRY_ORIGIN,BROKER_ORIGIN].includes(origin))j.tenancyVerified=true;
    if(m.stage==='sessionPick'&&broker){j.sessionVerified=true;j.tenancyVerified=true;}
    await putJob(id,j);return {ok:true};
  }
  if(m.type==='ERROR'){await finish(id,'로그인 화면에서 오류나 모호한 입력란을 발견했습니다. 화면을 확인한 뒤 다시 시작해 주세요.','stopped','page-error');return {ok:true};}
  if(m.type==='COMPLETE'){
    if(origin!==CONSOLE_ORIGIN)return {ok:false};
    if(j.applied.credentials||j.sessionVerified){
      if(!j.incognito){const meta=await chrome.storage.local.get(['identityBindings','lastUsed']);const bindings=meta.identityBindings||{};const last=meta.lastUsed||{};
      if(j.activeIdentity&&(j.tenancyVerified||j.profile.identityOrigins.includes(j.activeIdentity)))bindings[bindingKey(j.profile)]={origin:j.activeIdentity,at:Date.now()};
      last[j.profile.id]=Date.now();await chrome.storage.local.set({identityBindings:bindings,lastUsed:last});}
      await finish(id,j.sessionVerified&&!j.applied.credentials?'선택한 계정과 일치하는 기존 세션으로 콘솔 이동을 확인했습니다.':'콘솔 이동을 확인했습니다. 로그인된 계정은 콘솔에서 확인해 주세요.','complete');
    }else await finish(id,'이미 열려 있는 OCI 콘솔입니다. 계정을 확인하거나 로그아웃한 뒤 다시 시작해 주세요.','existing');
    return {ok:true};
  }
  return {ok:false};
}
chrome.runtime.onMessage.addListener((m,s,reply)=>{queue(s.tab?.id??'ui',()=>handle(m||{},s)).then(reply,e=>reply({ok:false,error:e instanceof UserError?e.message:'설정 파일과 OCI 접근 권한을 확인해 주세요.'})).catch(()=>{});return true;});
chrome.webNavigation.onCommitted.addListener(d=>queue(d.tabId,()=>committed(d)).catch(()=>{}));
chrome.webNavigation.onDOMContentLoaded.addListener(d=>{if(d.frameId===0)queue(d.tabId,()=>inject(d.tabId,d.url,d.documentId)).catch(()=>{});});
chrome.tabs.onUpdated.addListener((id,c,t)=>{if(c.status==='complete')queue(id,()=>inject(id,t.url)).catch(()=>{});});
chrome.tabs.onRemoved.addListener(id=>queue(id,async()=>{await chrome.storage.session.remove([`job:${id}`,`status:${id}`]);await chrome.alarms.clear(`expire:${id}`);}).catch(()=>{}));
chrome.alarms.onAlarm.addListener(a=>{if(a.name.startsWith('expire:'))queue(Number(a.name.slice(7)),()=>finish(Number(a.name.slice(7)),'시간이 지났습니다. 다시 로그인해 주세요.')).catch(()=>{});});
chrome.permissions.onRemoved.addListener(()=>register().catch(()=>{}));
chrome.runtime.onInstalled.addListener(details=>ready.then(async()=>{if(details.reason==='update')await navigator.locks.request('oci-companion-onboarding',async()=>{const saved=await chrome.storage.local.get('onboarding');if(!Object.hasOwn(saved,'onboarding'))await chrome.storage.local.set({onboarding:{complete:true,version:1}});});await register();}).catch(()=>{}));
chrome.runtime.onStartup.addListener(()=>ready.then(register).catch(()=>{}));
