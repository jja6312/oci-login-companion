import asyncio,json,pathlib,argparse,urllib.parse
from playwright.async_api import async_playwright
R=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Anonymous real Oracle JET component-only test; no authentication or customer form submission')
parser.add_argument('--url',required=True);parser.add_argument('--baseline-engine');parser.add_argument('--output',default='work/v1.2.1/real-jet-component-proof.json');args=parser.parse_args()
u=urllib.parse.urlsplit(args.url)
if u.scheme!='https' or u.username or u.password or u.port or not u.hostname.endswith('.identity.oraclecloud.com') or u.path!='/ui/v1/signin' or u.query or u.fragment:raise SystemExit('Supply a public HTTPS Identity Domain /ui/v1/signin URL without credentials/query/fragment.')
W=pathlib.Path(args.output).resolve().parent;W.mkdir(parents=True,exist_ok=True)
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/codex/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome',headless=True,args=['--no-sandbox'])
  c=await b.new_context(locale='ko-KR');page=await c.new_page()
  await page.goto(args.url,wait_until='domcontentloaded',timeout=45000)
  await page.wait_for_function("typeof require==='function'",timeout=20000)
  await page.evaluate("new Promise((ok,no)=>require(['ojs/ojinputtext','ojs/ojbutton'],ok,no))")
  await page.evaluate('''()=>{document.body.replaceChildren();const form=document.createElement('form');form.id='generic-fixture';form.onsubmit=e=>e.preventDefault();form.innerHTML='<oj-input-text id="idcs-signin-basic-signin-form-username" label-hint="사용자 이름" autocomplete="username"></oj-input-text><oj-input-password id="idcs-signin-basic-signin-form-password" label-hint="비밀번호" autocomplete="current-password"></oj-input-password><oj-button id="idcs-signin-basic-signin-form-submit" disabled>사인인</oj-button>';document.body.append(form);globalThis.fixtureClicks=0;const u=form.querySelector('oj-input-text'),p=form.querySelector('oj-input-password'),b=form.querySelector('oj-button');const update=()=>{b.disabled=!(u.value&&p.value);};u.addEventListener('valueChanged',update);p.addEventListener('valueChanged',update);b.addEventListener('ojAction',()=>fixtureClicks++);}''')
  await page.evaluate("new Promise((ok,no)=>require(['knockout'],ko=>{try{ko.applyBindings({},document.getElementById('generic-fixture'));ok();}catch(e){no(e);}},no))")
  await page.wait_for_function("document.querySelector('oj-input-text input')&&document.querySelector('oj-input-password input')&&document.querySelector('oj-button button')",timeout=20000)
  await c.route('**/*',lambda r:r.abort())
  await page.add_script_tag(content=pathlib.Path(args.baseline_engine).read_text() if args.baseline_engine else (R/'extension/engine.js').read_text())
  result=await page.evaluate('''async()=>{const ctx={identity:true,broker:false,mode:'login',selectors:{},identityDomain:'Default'};let outcome;try{const plan=OCILoginEngine.describe(ctx);outcome={stage:plan?.stage,hasSubmit:!!plan?.submit};}catch(e){outcome={error:e.message};}return {framework:typeof customElements.get('oj-input-text'),inputs:[...document.querySelectorAll('input')].map(e=>({id:e.id,type:e.type,autocomplete:e.autocomplete})),buttons:[...document.querySelectorAll('button')].map(e=>({id:e.id,disabled:e.disabled,label:e.textContent.trim()})),baseline:outcome};}''')
  session=await c.new_cdp_session(page);world=(await session.send('Page.createIsolatedWorld',{'frameId':(await session.send('Page.getFrameTree'))['frameTree']['frame']['id'],'worldName':'oci-component-test'}))['executionContextId']
  await session.send('Runtime.evaluate',{'expression':(R/'extension/engine.js').read_text(),'contextId':world})
  expr="(async()=>{const ctx={identity:true,broker:false,mode:'login',selectors:{},identityDomain:'Default',expiresAt:Date.now()+10000};const plan=OCILoginEngine.describe(ctx);await OCILoginEngine.execute(plan,ctx,{username:'fixture@example.invalid',password:'fixture-password'});return {stage:plan.stage,nativeInputs:plan.input instanceof HTMLInputElement&&plan.password instanceof HTMLInputElement,hasSubmit:!!plan.submit};})()"
  actual=await session.send('Runtime.evaluate',{'expression':expr,'contextId':world,'awaitPromise':True,'returnByValue':True})
  state=await page.evaluate("()=>({usernameCommitted:document.querySelector('oj-input-text').value==='fixture@example.invalid',passwordCommitted:document.querySelector('oj-input-password').value==='fixture-password',buttonEnabled:!document.querySelector('oj-button').disabled,actionCount:fixtureClicks})")
  result['fixedIsolatedWorld']=actual.get('result',{}).get('value',{'error':actual.get('exceptionDetails',{}).get('text','missing result')});result['jetState']=state;result['exceptionType']=actual.get('exceptionDetails',{}).get('exception',{}).get('className')
  assert result['fixedIsolatedWorld']=={'stage':'credentials','nativeInputs':True,'hasSubmit':True},result
  assert all(state[k] for k in ['usernameCommitted','passwordCommitted','buttonEnabled']) and state['actionCount']==1,state
  result['checksPassed']=3;result['scope']='Anonymous public Oracle JET components re-created in a dummy form; actual extension engine in CDP isolated world, fictitious values, network blocked after components loaded; no real authentication'
  pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));await b.close()
asyncio.run(main())
