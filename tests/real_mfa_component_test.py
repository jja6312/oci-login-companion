"""Anonymous Oracle MFA templates in a dummy view, with authentication disabled.

The public URL is supplied at runtime; no customer URL or vendor code is shipped.
"""
import argparse,asyncio,hashlib,json,pathlib,urllib.parse
from playwright.async_api import async_playwright
R=pathlib.Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--baseline-engine',required=True);ap.add_argument('--baseline-only',action='store_true');ap.add_argument('--output',default='work/v1.2.3/real-mfa-component-proof.json');args=ap.parse_args()
u=urllib.parse.urlsplit(args.url)
if u.scheme!='https' or u.username or u.password or u.port or not u.hostname.endswith('.identity.oraclecloud.com') or u.path!='/ui/v1/signin' or u.query or u.fragment:raise SystemExit('Public HTTPS Identity Domain signin URL without credentials/query required')
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/codex/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome',headless=True,args=['--no-sandbox'])
  c=await b.new_context(locale='ko-KR');page=await c.new_page()
  await c.route('**/*',lambda r:r.continue_() if r.request.method=='GET' else r.abort())
  await page.goto(args.url,wait_until='domcontentloaded',timeout=45000)
  await page.wait_for_function("typeof require==='function'",timeout=20000)
  templates=await page.evaluate('''()=>new Promise((ok,no)=>require(['text!mfaModule/view/mfa-auth/template/auth.tmpl.html','text!mfaModule/view/mfa-auth/template/bypass-auth.tmpl.html','knockout','ojs/ojinputtext','ojs/ojbutton'],(choice,bypass,ko)=>{globalThis.fixtureKO=ko;globalThis.fixtureTemplates={choice,bypass};ok({choice,bypass});},no))''')
  result={'templateSha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in templates.items()},'variants':[]}
  for variant in ['icon-row','jet-button']:
   await page.evaluate('''(variant)=>{const ko=fixtureKO;if(document.getElementById('fixture-root'))ko.cleanNode(document.getElementById('fixture-root'));document.body.replaceChildren();
    const d=new DOMParser().parseFromString(fixtureTemplates.choice,'text/html');const find=(root,s)=>root.querySelector(s)||[...root.querySelectorAll('template')].map(t=>find(t.content,s)).find(Boolean);const button=find(d,(variant==='icon-row'?'button':'oj-button')+'#idcs-mfa-mfa-auth-bypasscode-backup-button');if(!button)throw Error('Public factor template changed');
    const row=variant==='icon-row'?button.parentElement.parentElement:button.parentElement;const root=document.createElement('main');root.id='fixture-root';root.innerHTML='<section id="fixture-choice">'+row.outerHTML+'</section><section id="fixture-input" hidden>'+fixtureTemplates.bypass+'</section>';document.body.append(root);
    const style=document.createElement('style');style.textContent='[hidden]{display:none!important}button{min-width:48px;min-height:32px}';document.head.append(style);
    const choices=document.getElementById('fixture-choice'),input=document.getElementById('fixture-input');globalThis.fixtureCounts={choice:0,verify:0};const vm={isNewSigninUx:false,enableBackupMethods:()=>false,isTrustThisComputerShown:()=>false,isBackupFactorHidden:true,toggle:()=>false,passCode:ko.observable(''),verificationCheck:ko.observable(true),bundle:key=>({'mfa.auth.generic.qa':'보안 질문','mfa.auth.generic.bypass':'우회 코드','mfa.auth.generic.bypass-code':'우회 코드 사용','mfa.auth.generic.bypass-code-label':'우회 코드','mfa.auth.generic.authHeader':'2단계 인증','mfa.auth.generic.verify':'확인'}[key]||'인증')};
    vm.changeCurrentAuthType=vm.changeCurrentAuthFactorType=()=>{fixtureCounts.choice++;choices.hidden=true;input.hidden=false;};vm.rawBypasscodeChangeHandler=e=>vm.verificationCheck(!e.detail?.value?.trim());vm.bypasscodeChange=()=>{};vm.verify=()=>{if(vm.passCode()==='000123')fixtureCounts.verify++;};globalThis.fixtureVM=vm;ko.applyBindings(vm,root);
   }''',variant)
   await page.wait_for_function("document.querySelector('#fixture-input oj-input-text input')&&document.querySelector('#fixture-input oj-button button')")
   if variant=='icon-row':await c.route('**/*',lambda r:r.abort())
   await page.add_script_tag(content=pathlib.Path(args.baseline_engine).read_text())
   baseline=await page.evaluate('''()=>{const ctx={identity:true,broker:false,mode:'login',selectors:{},identityDomain:'Default'};const choice=OCILoginEngine.describe(ctx);document.getElementById('fixture-choice').hidden=true;document.getElementById('fixture-input').hidden=false;const input=OCILoginEngine.describe(ctx);document.getElementById('fixture-choice').hidden=false;document.getElementById('fixture-input').hidden=true;return {choiceStage:choice?.stage||null,inputStage:input?.stage||null};}''')
   if variant=='icon-row':assert baseline['choiceStage'] is None,baseline
   assert baseline['inputStage'] is None,baseline
   proof={'variant':variant,'baseline':baseline}
   if not args.baseline_only:
    session=await c.new_cdp_session(page);frame=(await session.send('Page.getFrameTree'))['frameTree']['frame']['id'];world=(await session.send('Page.createIsolatedWorld',{'frameId':frame,'worldName':'mfa-component-'+variant}))['executionContextId']
    await session.send('Runtime.evaluate',{'expression':(R/'extension/engine.js').read_text(),'contextId':world})
    code="""(async()=>{const ctx={identity:true,broker:false,mode:'login',selectors:{},identityDomain:'Default',expiresAt:Date.now()+15000};const choice=OCILoginEngine.describe(ctx);if(choice?.stage!=='bypassChoice')throw Error('factor not recognized');await OCILoginEngine.execute(choice,ctx,{});await new Promise(r=>setTimeout(r,300));const input=OCILoginEngine.describe(ctx);if(input?.stage!=='bypass')throw Error('bypass input not recognized');await OCILoginEngine.execute(input,ctx,{value:'000123'});return {choiceStage:choice.stage,inputStage:input.stage,nativeInput:input.input instanceof HTMLInputElement};})()"""
    actual=await session.send('Runtime.evaluate',{'expression':code,'contextId':world,'awaitPromise':True,'returnByValue':True});assert not actual.get('exceptionDetails'),actual.get('exceptionDetails',{}).get('text')
    state=await page.evaluate("()=>({choiceActions:fixtureCounts.choice,verifyActions:fixtureCounts.verify,committed:fixtureVM.passCode()==='000123',enabled:!document.getElementById('bypass-auth-text-input').disabled})")
    assert state=={'choiceActions':1,'verifyActions':1,'committed':True,'enabled':True},state
    proof.update({'fixedIsolatedWorld':actual['result']['value'],'componentState':state});await session.detach()
   result['variants'].append(proof)
  result.update({'checksPassed':2 if args.baseline_only else 6,'actualAuthenticationSubmitted':False,'scope':'Anonymous public Oracle MFA choice subtree and full bypass template, actual JET/Knockout components, fictitious value, dummy handlers only. No account sign-in, tokens, API submission or original branding. Vendor templates are fetched at runtime and not redistributed.'})
  out=pathlib.Path(args.output);out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));await b.close()
asyncio.run(main())
