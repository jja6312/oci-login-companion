import asyncio,json,pathlib,shutil,uuid,argparse
from playwright.async_api import async_playwright
R=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Public OCI tenancy-only routing test; all credential CLAIM stages blocked')
parser.add_argument('--tenancy',required=True);parser.add_argument('--baseline-extension');parser.add_argument('--output',default='work/v1.2.2/actual-routing-proof.json');args=parser.parse_args()
W=pathlib.Path(args.output).resolve().parent;W.mkdir(parents=True,exist_ok=True)
async def run(p,label,source):
 ext=W/(label+'-readonly-extension')
 if ext.exists():shutil.rmtree(ext)
 shutil.copytree(source,ext);m=json.loads((ext/'manifest.json').read_text());m['host_permissions']=['https://www.oracle.com/*','https://cloud.oracle.com/*','https://login.oci.oraclecloud.com/*','https://*.identity.oraclecloud.com/*','https://login.oraclecloud.com/*','https://signin.oraclecloud.com/*'];(ext/'manifest.json').write_text(json.dumps(m))
 code=(ext/'worker.js').read_text();needle="  if(m.type==='CLAIM'){";assert code.count(needle)==1
 code=code.replace(needle,needle+"if(['credentials','username','bypass','alternative','bypassChoice'].includes(m.stage)){globalThis.observeDenied=globalThis.observeDenied||[];observeDenied.push(m.stage);return {ok:false};}")
 marker='readonly-'+uuid.uuid4().hex;code="globalThis.__readonlyTestBuild="+json.dumps(marker)+";\n"+code
 (ext/'worker.js').write_text(code)
 profile={'id':'readonly-fixture','tenancy':args.tenancy,'name':'Readonly public route fixture','identityDomain':'Default','username':'readonly-fixture@example.invalid','password':'NEVER_RELEASE_THIS_PASSWORD','bypassCode':'NEVER_RELEASE_THIS_CODE','identityOrigins':[],'selectors':{}}
 profile_dir=W/(label+'-readonly-profile-'+uuid.uuid4().hex)
 c=await p.chromium.launch_persistent_context(str(profile_dir),executable_path='/home/codex/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome',headless=True,args=['--no-sandbox','--disable-extensions-except='+str(ext),'--load-extension='+str(ext)])
 worker=c.service_workers[0] if c.service_workers else await c.wait_for_event('serviceworker');assert await worker.evaluate('globalThis.__readonlyTestBuild')==marker;eid=worker.url.split('/')[2];ui=await c.new_page();await ui.goto('chrome-extension://'+eid+'/options.html');await ui.locator('#add').wait_for();await ui.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',profile)
 await worker.evaluate("()=>{globalThis.routeKinds=[];globalThis.regionalOrigins=new Set();chrome.webNavigation.onCommitted.addListener(d=>{if(d.frameId===0){const u=new URL(d.url);const h=u.hostname;if(/^login\\.[a-z][a-z0-9-]*-\\d+(?:\\.oci)?\\.oraclecloud\\.com$/.test(h))regionalOrigins.add(u.origin);routeKinds.push(h==='cloud.oracle.com'?'console':h==='www.oracle.com'?'account-entry':h==='login.oci.oraclecloud.com'?'broker':/^login\\.[a-z][a-z0-9-]*-\\d+(?:\\.oci)?\\.oraclecloud\\.com$/.test(h)?'regional-broker':h.endsWith('.identity.oraclecloud.com')?'identity':'other');}});}")
 started=await ui.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"START",windowId:w.id,incognito:w.incognito,profileId:p.id,mode:"login",expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain}});}',profile);assert started['ok'],started
 tid=started['tabId'];st=None;denied=[]
 for _ in range(240):
  st=await ui.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid);denied=await worker.evaluate('globalThis.observeDenied||[]')
  if denied or (st and not st['running']):break
  await ui.wait_for_timeout(250)
 state=await ui.evaluate('''async(id)=>{const all=await chrome.storage.session.get(null);const j=all['job:'+id];return {tenancyVerified:j?.tenancyVerified===true,identityReady:!!j?.activeIdentity,credentialClaimApproved:j?.claims?.credentials===true,bypassClaimApproved:j?.claims?.bypass===true};}''',tid)
 routes=await worker.evaluate('routeKinds');target=await ui.evaluate('(id)=>chrome.tabs.get(id)',tid);page=next((x for x in c.pages if x.url==target.get('url')),None);empty=None
 if page and '.identity.oraclecloud.com' in page.url:empty=await page.evaluate("[...document.querySelectorAll('input[type=password],input[autocomplete=username]')].every(e=>e.value==='')")
 result={'label':label,'version':m['version'],'status':st.get('step') if st else None,'message':st.get('message') if st else None,'routeKinds':routes,'state':state,'deniedSecretStages':denied,'authInputsEmpty':empty,'regionalPermissionGranted':await worker.evaluate("async()=>{for(const origin of regionalOrigins){if(await chrome.permissions.contains({origins:[origin+'/*']}))return true;}return false;}"),'actualCredentialSubmission':False,'injectionFailures':await worker.evaluate('globalThis.observeInjectionFailures||[]'),'debug':st.get('debug') if st else None}
 (W/(label+'-real-route-proof.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');await c.close();shutil.rmtree(profile_dir);return result
async def main():
 async with async_playwright() as p:
  old=await run(p,'baseline',pathlib.Path(args.baseline_extension)) if args.baseline_extension else None;new=await run(p,'candidate',R/'extension')
 if old:assert old['status']=='stopped' and 'regional-broker' in old['routeKinds'],old
 assert new['state']['tenancyVerified'] and new['state']['identityReady'] and new['deniedSecretStages'] and new['authInputsEmpty'],new
 assert not new['state']['credentialClaimApproved'] and not new['state']['bypassClaimApproved'] and not new['regionalPermissionGranted'],new
 proof={'baseline':old,'candidate':new,'scope':'Fresh anonymous public OCI tenancy-only route; instrumented workers deny all username/password/bypass stages; no credentials entered or authenticated; no regional host permission granted','checksPassed':3}
 pathlib.Path(args.output).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False))
asyncio.run(main())
