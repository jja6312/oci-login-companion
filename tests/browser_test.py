from fixture_permissions import auth_permissions
"""Offline integration of shipped extension. Oracle hostnames use a loopback TLS fixture.
Fixture copy pregrants OCI permissions; native Chrome approval UI is not automated.
"""
import asyncio,json,pathlib,shutil,re,ssl,socket,subprocess,sys,time,os
from types import SimpleNamespace
from playwright.async_api import async_playwright,expect
ROOT=pathlib.Path(__file__).resolve().parents[1];WORK=ROOT/'work'/os.environ.get('OCI_TEST_RELEASE','v1.3.0');WORK.mkdir(exist_ok=True)
CHROME='/home/codex/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome'
IDENTITY='https://idcs-fixture.identity.oraclecloud.com';CONSOLE='https://cloud.oracle.com';BROKER='https://login.oci.oraclecloud.com';ENTRY='https://www.oracle.com';REGIONAL='https://login.us-ashburn-1.oraclecloud.com';REGIONAL_OCI='https://login.us-ashburn-1.oci.oraclecloud.com';OTHER_ROUTE='https://api.us-ashburn-1.oraclecloud.com'
PROFILE={'id':'fixture-seoul','name':'서울 운영 계정','tenancy':'cloudragon-prod','identityDomain':'Default','username':'operator@example.invalid','password':'fixture-password','bypassCode':'000123','identityOrigins':[],'selectors':{}}
checks=[]
def ok(s):checks.append(s);print('PASS',s,flush=True)
def html(b,s=''):return '<!doctype html><html><head><meta charset="utf-8"><title>OCI fixture</title></head><body>'+b+'<script>'+s+'</script></body></html>'
def form(fields,next_url,condition,label='Sign in'):
 return html('<form>'+fields+'<button>'+label+'</button></form>',f"document.querySelector('form').onsubmit=e=>{{e.preventDefault();if({condition})location.href={json.dumps(next_url)};else document.body.innerHTML='<p role=alert>Invalid credentials</p>';}}")
def mfa_fixture(scenario):
 # Generic reproduction of Oracle's icon row, sibling h5 and generic JET field.
 # No customer branding or vendor templates are copied into this offline suite.
 tag='oj-button' if scenario=='mfa-jet' else 'button'
 native='<button type="button"><span>우회 코드</span></button>' if tag=='oj-button' else '<span class="idcs-bypass-code"></span>'
 factor='SMS' if scenario=='mfa-other-factor' else 'BYPASSCODE';disabled=' disabled' if scenario=='mfa-disabled' else ''
 choice=f'<div><div><{tag} id="idcs-mfa-mfa-auth-bypasscode-backup-button" data-idcs-factor-type="{factor}" aria-label="{('우회 코드' if scenario=='mfa-other-factor' else '보안 질문')}" title="우회 코드"{disabled}>{native}</{tag}></div><div><h5>우회 코드</h5><span>우회 코드 사용</span></div></div>'
 if scenario=='mfa-duplicate-choice':choice+=choice
 inputs='<oj-input-text id="text-input"><input id="text-input|input" autocomplete="off"></oj-input-text>'
 if scenario=='mfa-duplicate-input':inputs+=inputs
 marker='unrelated-verify' if scenario=='mfa-missing-marker' else 'bypass-auth-text-input'
 opened=scenario!='mfa-icon';missing=scenario=='mfa-missing-marker'
 body='<section id="push-view"'+(' hidden' if missing else '')+'><form><label>SMS passcode<input id="sms" autocomplete="one-time-code"></label></form><h3>우회 코드</h3><button id="alternate">'+('대체 로그인 방법 숨기기' if opened else '대체 로그인 방법 보기')+'</button><div id="choices"'+('' if opened else ' hidden')+'><button data-idcs-factor-type="TOTP">모바일 애플리케이션</button>'+choice+'</div></section><section id="bypass-view"'+('' if missing else ' hidden')+'><form id="bypass-form">'+inputs+f'<oj-button id="{marker}"><button type="submit" disabled>확인</button></oj-button></form></section>'
 script="""globalThis.fixtureStats={choice:0,verify:0,smsWrites:0,other:0};document.getElementById('sms').oninput=()=>fixtureStats.smsWrites++;document.getElementById('alternate').onclick=()=>document.getElementById('choices').hidden=false;
 document.querySelector('[data-idcs-factor-type=TOTP]').onclick=()=>fixtureStats.other++;
 for(const e of document.querySelectorAll('[id="idcs-mfa-mfa-auth-bypasscode-backup-button"]'))(e.matches('oj-button')?e.querySelector('button'):e).onclick=()=>{fixtureStats.choice++;document.getElementById('push-view').hidden=true;document.getElementById('bypass-view').hidden=false;};
 const form=document.getElementById('bypass-form'),submit=form.querySelector('button');form.addEventListener('input',()=>setTimeout(()=>submit.disabled=false,200));form.onsubmit=e=>{e.preventDefault();fixtureStats.verify++;const values=[...form.querySelectorAll('input')];if(values.length===1&&values[0].value==='000123'&&fixtureStats.choice===1&&fixtureStats.verify===1&&!fixtureStats.smsWrites&&!fixtureStats.other)location.href=DEST;};""".replace('DEST',json.dumps(CONSOLE+'/done?mfa=1&choice=1&verify=1&sms=0&other=0'))
 return html(body,script)
def regional_domain_fixture(scenario,spa=False):
 options='<option value="other">Other</option><option value="default-ocid">Default</option>'
 if scenario=='regional-domain-preselected':options=options.replace('value="default-ocid"','value="default-ocid" selected')
 if scenario=='regional-domain-missing':options='<option value="other">Other</option>'
 if scenario=='regional-domain-ambiguous':options+='<option value="duplicate">Default</option>'
 tenant='wrong-tenant' if scenario=='regional-domain-wrong-tenant' else PROFILE['tenancy']
 controls='<div class="login-prompt"><p class="username-prompt">'+tenant+'</p></div><select name="domainSelect">'+options+'</select><input id="username"><input id="password" type="password"><input id="bypassCode"><a id="domain-next" href="#">'+('다음' if scenario=='regional-domain-ko' else 'Next')+'</a>'
 setup=f"globalThis.fixtureDomainClicks=0;document.getElementById('domain-next').onclick=e=>{{e.preventDefault();fixtureDomainClicks++;if({json.dumps(scenario!='regional-domain-guard')}&&document.querySelector('select').value==='default-ocid'&&!username.value&&!password.value&&!bypassCode.value)location.href='{IDENTITY}/credentials';}}"
 if spa:return html('<p>OAuth app shell</p>',"setTimeout(()=>{history.replaceState({},'', '/v2/ui/domains?referer=fixture');document.body.innerHTML="+json.dumps(controls)+";"+setup+"},1200);")
 return html(controls,setup)
async def main():
 ext=WORK/'extension-fixture';shutil.rmtree(ext,ignore_errors=True);shutil.copytree(ROOT/'extension',ext)
 if '--session-only' in sys.argv:
  # Model Chrome leaving executeScript pending without altering production
  # timeouts or timer APIs. The shipped worker must release its per-tab queue.
  worker_path=ext/'worker.js';worker_path.write_text(worker_path.read_text()+"\nconst fixtureExecute=chrome.scripting.executeScript.bind(chrome.scripting),fixtureRegister=chrome.scripting.registerContentScripts.bind(chrome.scripting);chrome.scripting.executeScript=async(args)=>{const frame=await chrome.webNavigation.getFrame({tabId:args.target.tabId,frameId:0}).catch(()=>null);if(globalThis.fixtureHoldSessionInjection&&frame?.url.includes('/v2/ui/sessionPicker'))return new Promise(()=>{});return fixtureExecute(args);};chrome.scripting.registerContentScripts=scripts=>fixtureRegister(scripts.map(s=>({...s,matches:s.matches.filter(x=>!globalThis.fixtureNoBrokerDriver||x!=='https://login.oci.oraclecloud.com/*')})));\n")
 m=json.loads((ext/'manifest.json').read_text());m['host_permissions']=auth_permissions(ext);(ext/'manifest.json').write_text(json.dumps(m))
 profdir=WORK/'browser-profile';shutil.rmtree(profdir,ignore_errors=True)
 shots=WORK/'screenshots';shots.mkdir(exist_ok=True);errors=[];scenario='session-match' if '--session-only' in sys.argv else 'normal';requests=[]
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 cert=WORK/'fixture-cert.pem';key=WORK/'fixture-key.pem'
 if not cert.exists():subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','2','-subj','/CN=oci-offline-fixture'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
 async with async_playwright() as p:
  async def launch_browser():return await p.chromium.launch_persistent_context(str(profdir),executable_path=CHROME,headless=True,args=['--no-sandbox','--disable-extensions-except='+str(ext),'--load-extension='+str(ext),'--ignore-certificate-errors','--host-resolver-rules=MAP cloud.oracle.com 127.0.0.1:'+str(port)+', MAP www.oracle.com 127.0.0.1:'+str(port)+', MAP login.oci.oraclecloud.com 127.0.0.1:'+str(port)+', MAP login.us-ashburn-1.oraclecloud.com 127.0.0.1:'+str(port)+', MAP login.us-ashburn-1.oci.oraclecloud.com 127.0.0.1:'+str(port)+', MAP api.us-ashburn-1.oraclecloud.com 127.0.0.1:'+str(port)+', MAP *.identity.oraclecloud.com 127.0.0.1:'+str(port)],ignore_https_errors=True,viewport={'width':1200,'height':820})
  ctx=await launch_browser()
  async def route(r):
   url=r.request.url.split('?',1)[0];requests.append(r.request.url)
   if url==CONSOLE+'/':
    if scenario in ['regional-unverified','regional-domain-unverified']:body=html('<p>Continue</p>',f"location.replace('{BROKER}/v1/oauth2/authorize');")
    elif scenario=='redirect-http':await r.fulfill(status=302,headers={'Location':ENTRY+'/cloud/sign-in.html'});return
    elif scenario=='session-entry':body=html('<p>Redirecting</p>',f"location.replace('{ENTRY}/cloud/sign-in.html');")
    elif scenario.startswith('session-'):body=html('<p>Redirecting</p>',f"location.replace('{BROKER}/v2/ui/sessionPicker');")
    elif scenario=='hold':body=html('<p>Waiting for tenancy UI</p>')
    else:body=form('<input id="cloudAccountName">',CONSOLE+'/domain',"cloudAccountName.value==='cloudragon-prod'",'Next')
   elif url==CONSOLE+'/regional-domain-route':body=html('<p>Continue</p>',f"location.replace('{BROKER}/v1/oauth2/authorize');")
   elif url==CONSOLE+'/retry-entry':body=form('<input id="cloudAccountName">',CONSOLE+'/domain',"cloudAccountName.value==='cloudragon-prod'",'Next')
   elif url==CONSOLE+'/domain':
    if scenario=='custom':body=html('<button id="identityDomain" role="combobox" aria-label="Identity domain">Choose domain</button><div id="choices" hidden><button role="option">Default</button></div><button id="next" disabled>Continue</button>',f"identityDomain.onclick=()=>choices.hidden=false;document.querySelector('[role=option]').onclick=()=>{{identityDomain.textContent='Default';choices.hidden=true;next.disabled=false;}};next.onclick=()=>location.href='{IDENTITY}/credentials';")
    elif scenario.startswith('regional-'):body=form('<select id="identityDomain"><option>Other</option><option>Default</option></select>',BROKER+'/v1/oauth2/authorize',"identityDomain.value==='Default'",'Continue')
    else:body=form('<select id="identityDomain"><option>Other</option><option>Default</option></select>',IDENTITY+'/credentials',"identityDomain.value==='Default'",'Continue')
   elif url==ENTRY+'/cloud/sign-in.html':
    # Public Oracle entry uses an anchor outside a form, not a submit button.
    if scenario in ['regional-unverified','regional-domain-unverified']:body=html('<p>Continue</p>',f"location.replace('{BROKER}/v1/oauth2/authorize');")
    elif scenario.startswith('session-') and scenario!='session-entry':body=html('<p>Unexpected session redirect fixture</p>',f"location.replace('{BROKER}/v2/ui/sessionPicker');")
    elif scenario=='hold':body=html('<p>Waiting for tenancy UI</p>')
    else:
     next_url=CONSOLE+'/regional-domain-route' if scenario.startswith('regional-domain') else BROKER+'/v2/ui/domains' if scenario=='session-entry' else CONSOLE+'/domain'
     body=html('<input type="search" aria-label="Site search"><input id="cloudAccountName" type="input" value="previous-fixture-tenant"><div class="rc63submit inActive"><div class="obttn"><a id="cloudAccountButton" href="javascript:void(0)">Next</a></div></div>',f"cloudAccountButton.onclick=()=>{{if(cloudAccountName.value==='cloudragon-prod')location.href='{next_url}';}}")
   elif url==BROKER+'/v1/oauth2/authorize':
    hop=OTHER_ROUTE if scenario=='regional-other' else REGIONAL_OCI if scenario in ['regional-oci','regional-domain-oci'] else REGIONAL
    body=html('<p>Authorize</p>',f"location.href='{hop}/v1/oauth2/authorize';")
   elif url in [REGIONAL+'/v1/oauth2/authorize',REGIONAL_OCI+'/v1/oauth2/authorize']:
    if scenario=='regional-domain-spa':body=regional_domain_fixture(scenario,spa=True)
    elif scenario.startswith('regional-domain'):body=html('<p>Continue</p>',"location.href='/v2/ui/domains?referer=fixture';")
    elif scenario in ['regional-guard','regional-manual']:body=html('<input name="username"><input type="password" name="password"><input id="bypassCode"><button>Sign in</button>')
    else:
     origin=url.split('/v1/',1)[0];body=html('<form action="'+origin+'/v1/forward" method="post"><input type="hidden" name="fixture" value="oauth-only"></form>',"document.forms[0].submit();")
   elif url in [REGIONAL+'/v2/ui/domains',REGIONAL_OCI+'/v2/ui/domains']:
    body=regional_domain_fixture(scenario)
   elif url in [REGIONAL+'/v1/forward',REGIONAL_OCI+'/v1/forward']:await r.fulfill(status=302,headers={'Location':IDENTITY+'/credentials'});return
   elif url==OTHER_ROUTE+'/v1/oauth2/authorize':body=html('<input name="username"><input type="password" name="password"><button>Sign in</button>')
   elif url==BROKER+'/v2/ui/sessionPicker':
    if scenario=='session-guard':body=html('<input id="username"><input id="password" type="password"><input id="bypassCode"><button>Sign in</button>')
    else:
     import html as escape_html
     rows=[('other-tenant',PROFILE['username'],'Default','other-tenant'),('other-domain',PROFILE['username'],'Other',PROFILE['tenancy']),('other-user','other@example.invalid','Default',PROFILE['tenancy'])]
     if scenario in ['session-match','session-expired','session-ambiguous']:rows.append(('target',PROFILE['username'],'Default',PROFILE['tenancy']))
     if scenario=='session-ambiguous':rows.append(('duplicate',PROFILE['username'],'Default',PROFILE['tenancy']))
     cards=[]
     for i,(key,user,domain,tenant) in enumerate(rows):
      target=IDENTITY+'/credentials' if key=='target' and scenario=='session-expired' else CONSOLE+'/done?fixture='+key
      cards.append('<button class="oui-button-outline oui-button henosis-button session-button" data-testid="btn-session-'+str(i)+'" onclick="location.href=\''+target+'\'"><div class="session-icon">O</div><div class="session-body"><div class="user-name">'+escape_html.escape(user)+'</div><div class="domain-name key-value"><div class="key">도메인:</div><div class="value">'+domain+'</div></div><div class="tenant-name key-value"><div class="key">테넌트:</div><div class="value">'+tenant+'</div></div></div></button>')
     different='' if scenario=='session-no-control' else '<button onclick="location.href=\''+BROKER+'/v2/ui/changeTenant\'"><div class="session-change">Sign in with a different user account</div></button>'
     root='unrecognized-session-layout' if scenario in ['session-recovery-layout','session-recovery-idle'] else 'session-picker-dialog'
     body=html('<h3>You have active sessions</h3><div id="'+root+'"><div class="login-input session-list">'+''.join(cards)+'</div>'+different+'</div>')
   elif url==BROKER+'/v2/ui/changeTenant':body=form('<input id="tenant" name="tenant">',BROKER+'/v2/ui/domains',"tenant.value==='cloudragon-prod'",'Continue')
   elif url==BROKER+'/v2/ui/domains':body=form('<select name="domainSelect" data-testid="identity-domain-dropdown"><option value="other">Other</option><option value="default-ocid">Default</option></select>',BROKER+'/v2/ui/native' if scenario=='session-native' else IDENTITY+'/credentials',"document.querySelector('select').value==='default-ocid'",'Continue')
   elif url==BROKER+'/v2/ui/native':body=form('<input id="username"><input id="password" type="password">',BROKER+'/v2/ui/native-bypass',"username.value==='operator@example.invalid'&&password.value==='fixture-password'")
   elif url==BROKER+'/v2/ui/native-bypass':body=form('<label>Bypass Code<input id="bypassCode"></label>',CONSOLE+'/done',"bypassCode.value==='000123'",'Verify')
   elif url==IDENTITY+'/credentials' and scenario.startswith('redirect-'):await r.fulfill(status=302,headers={'Location':IDENTITY+'/ui/v1/signin'});return
   elif url==IDENTITY+'/slow-fixture.svg':await asyncio.sleep(8);await r.fulfill(body='<svg xmlns="http://www.w3.org/2000/svg"/>',content_type='image/svg+xml');return
   elif url==IDENTITY+'/ui/v1/signin':
    wrap=scenario!='redirect-korean'
    user='<input id="idcs-signin-basic-signin-form-username|input" name="username" autocomplete="username">'
    password='<input id="idcs-signin-basic-signin-form-password|input" name="password" type="password" autocomplete="current-password">'
    if wrap:user='<oj-input-text id="idcs-signin-basic-signin-form-username">'+user+'</oj-input-text>';password='<oj-input-password id="idcs-signin-basic-signin-form-password">'+password+'</oj-input-password>'
    if scenario=='redirect-ambiguous':user=user.replace('</oj-input-text>','<input name="username" autocomplete="username"></oj-input-text>')
    disabled='' if scenario=='redirect-korean' else ' disabled'
    action='<oj-button id="idcs-signin-basic-signin-form-submit"><button id="signin" type="button"'+disabled+'><span>사인인</span></button></oj-button>'
    extra='<img src="'+IDENTITY+'/slow-fixture.svg">' if scenario=='redirect-slow' else ''
    script="const form=document.querySelector('form'),u=document.querySelector('input[name=username]'),p=document.querySelector('input[name=password]');form.addEventListener('input',()=>{setTimeout(()=>{if("+json.dumps(scenario!='redirect-disabled')+"&&u.value&&p.value)signin.disabled=false;},250);});signin.onclick=()=>{if(u.value==='operator@example.invalid'&&p.value==='fixture-password')location.href='"+IDENTITY+"/mfa';};"
    body=html('<form>'+user+password+action+'</form>'+extra,script)
   elif url==IDENTITY+'/credentials':body=form('<input id="username" autocomplete="username"><input id="password" type="password" autocomplete="current-password">',IDENTITY+'/mfa',"username.value==='operator@example.invalid'&&password.value==='fixture-password'")
   elif url==IDENTITY+'/mfa':
    if scenario.startswith('mfa-'):body=mfa_fixture(scenario)
    elif scenario=='sms':body=html('<form><h1>SMS verification</h1><input id="otp" autocomplete="one-time-code"><button>Verify</button></form><button>Use a bypass code</button>')
    elif scenario=='duplicate':body=html('<input id="username"><input name="username"><input id="password" type="password"><button>Sign in</button>')
    elif scenario=='invalid':body=html('<p role="alert">Invalid credentials</p><input id="password" type="password">')
    else:body=html('<button id="next">'+('다른 인증 방법' if scenario=='custom' else 'Show alternative login methods')+'</button>',f"next.onclick=()=>location.href='{IDENTITY}/choice';")
   elif url==IDENTITY+'/choice':
    if scenario=='custom':body=html('<form><label><input id="factor" name="factor" type="radio" hidden>Bypass Code</label><button>Continue</button></form>',f"document.querySelector('form').onsubmit=e=>{{e.preventDefault();if(factor.checked)location.href='{IDENTITY}/bypass';}}")
    else:body=html('<button id="next"><h3>Use a bypass code</h3></button>',f"next.onclick=()=>location.href='{IDENTITY}/bypass';")
   elif url==IDENTITY+'/bypass':body=form('<label>Bypass Code<input id="verificationCode" autocomplete="one-time-code"></label>',CONSOLE+'/done',"verificationCode.value==='000123'",'Verify')
   elif url==CONSOLE+'/done':body=html('<main data-testid="oci-console">Oracle Cloud Console fixture</main>')
   elif url=='https://idcs-untrusted.identity.oraclecloud.com/credentials':body=html('<input id="username"><input id="password" type="password"><button>Sign in</button>')
   else:await r.abort();return
   await r.fulfill(status=200,content_type='text/html',body=body,headers={'cache-control':'no-store'})
  # A loopback-only TLS fixture avoids Chromium/Playwright target-interception races.
  # Official hostnames resolve to this server only in this disposable browser.
  class LocalRoute:
   def __init__(self,url,writer):self.request=SimpleNamespace(url=url);self.writer=writer
   async def fulfill(self,status=200,body='',content_type='text/html',headers=None):
    data=body.encode();extra=''.join(k+': '+v+'\r\n' for k,v in (headers or {}).items());self.writer.write(f'HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(data)}\r\nConnection: close\r\nCache-Control: no-store\r\n{extra}\r\n'.encode()+data);await self.writer.drain()
   async def abort(self):await self.fulfill(status=404,body='Fixture route missing')
  async def serve(reader,writer):
   try:
    raw=(await reader.readuntil(b'\r\n\r\n')).decode();lines=raw.split('\r\n');path=lines[0].split()[1];host=next(x.split(':',1)[1].strip() for x in lines if x.lower().startswith('host:'));await route(LocalRoute('https://'+host+path,writer))
   except (asyncio.IncompleteReadError,ConnectionError):pass
   finally:
    writer.close()
    try:await writer.wait_closed()
    except ConnectionError:pass
  tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key);server=await asyncio.start_server(serve,'127.0.0.1',port,ssl=tls)

  worker=ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event('serviceworker');await worker.evaluate("chrome.storage.local.set({onboarding:{complete:true,version:1}})");eid=worker.url.split('/')[2]
  page=await ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
  await page.goto(f'chrome-extension://{eid}/options.html');await page.locator('#add').wait_for();await page.wait_for_timeout(300)
  if '--session-only' in sys.argv:
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE)
   await worker.evaluate("()=>{globalThis.fixtureObservedKinds=new Set();chrome.storage.onChanged.addListener((changes,area)=>{if(area==='session')for(const [key,v] of Object.entries(changes))if(key.startsWith('job:'))for(const event of v.newValue?.trace||[])fixtureObservedKinds.add(event.kind);});}")
   async def session_start():
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
    r=await page.evaluate('async(p)=>chrome.runtime.sendMessage({type:"START",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito})),profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"})',PROFILE);assert r['ok'],r;return r['tabId']
   async def session_end(tid):
    for _ in range(240):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:return st
     await page.wait_for_timeout(120)
    raise AssertionError({'status':st,'requests':requests[-12:]})
   for scenario in ['session-match','session-none','session-entry','session-native','session-expired','session-ambiguous','session-no-control']:
    begin=len(requests);tid=await session_start();st=await session_end(tid);recent=requests[begin:]
    assert not any('fixture=other' in u or 'fixture=duplicate' in u for u in recent),recent
    if scenario=='session-match':assert st['step']=='complete' and '기존 세션' in st['message'] and not any(u.startswith(IDENTITY) for u in recent),st;ok('real Oracle session-card DOM selects only exact tenancy, case-sensitive username and domain; no new credentials')
    elif scenario in ['session-none','session-entry','session-native','session-expired']:assert st['step']=='complete' and any(u in [IDENTITY+'/bypass',BROKER+'/v2/ui/native-bypass'] for u in recent),st;ok(scenario+' continues through actual broker tenancy/domain, credentials, bypass and console')
    else:assert st['step']=='stopped' and not any('fixture=' in u or u==BROKER+'/v2/ui/changeTenant' for u in recent),st;ok(scenario+' stops without choosing a different account')
    assert not await page.evaluate('(id)=>chrome.storage.session.get("job:"+id)',tid)
   for scenario in ['session-recovery-layout','session-recovery-pending-injection','session-recovery-no-driver']:
    await worker.evaluate('fixtureObservedKinds.clear()')
    await worker.evaluate('(v)=>{globalThis.fixtureHoldSessionInjection=v.hold;globalThis.fixtureNoBrokerDriver=v.noDriver;}',{'hold':not scenario.endswith('layout'),'noDriver':scenario.endswith('no-driver')})
    begin=len(requests);tid=await session_start();st=await session_end(tid);recent=requests[begin:]
    assert st['step']=='complete' and BROKER+'/v2/ui/changeTenant' in recent and IDENTITY+'/bypass' in recent,st
    assert not any('fixture=' in u for u in recent),recent
    kinds=await worker.evaluate('[...fixtureObservedKinds]')
    assert ('content-ready' if scenario.endswith('pending-injection') else 'session-recovery') in kinds,(st,kinds)
    assert not await worker.evaluate('(id)=>chrome.alarms.get("recover-session:"+id)',tid)
    ok(scenario+' automatically recovers the broker/no-applied-step state through tenancy, credentials and bypass')
   await worker.evaluate('globalThis.fixtureHoldSessionInjection=false;globalThis.fixtureNoBrokerDriver=false')
   # A queued alarm must not take over manual navigation or a cancelled task.
   for manual in [False,True]:
    scenario='session-recovery-idle';tid=await session_start()
    for _ in range(80):
     alarm=await worker.evaluate('(id)=>chrome.alarms.get("recover-session:"+id)',tid)
     if alarm:break
     await page.wait_for_timeout(50)
    else:raise AssertionError('Missing recovery alarm')
    if manual:
     await page.evaluate('(id)=>chrome.tabs.update(id,{url:"https://idcs-untrusted.identity.oraclecloud.com/credentials"})',tid)
     await session_end(tid)
    else:await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid)
    begin=len(requests);await page.wait_for_timeout(5600)
    assert BROKER+'/v2/ui/changeTenant' not in requests[begin:]
    assert not await worker.evaluate('(id)=>chrome.alarms.get("recover-session:"+id)',tid)
    ok('session recovery respects '+('manual navigation away from the tracked document' if manual else 'cancellation before the alarm'))
   scenario='session-guard';tid=await session_start()
   for _ in range(100):
    tabs=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
    if tabs.get('url','').startswith(BROKER) and tabs.get('status')=='complete':break
    await page.wait_for_timeout(100)
   denied=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:async()=>({credentials:await chrome.runtime.sendMessage({type:'CLAIM',stage:'credentials'}),bypass:await chrome.runtime.sendMessage({type:'CLAIM',stage:'bypass'})})}))[0].result''',tid)
   assert not denied['credentials']['ok'] and not denied['bypass']['ok'];ok('unverified session broker is denied password and bypass claims')
   await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid)
   unit=await ctx.new_page();await unit.set_content(html('<div id="session-picker-dialog"><button data-testid="btn-session-0"><div class="user-name">operator@example.invalid</div><div class="domain-name"><div class="value">Default</div></div><div class="tenant-name"><div class="value">cloudragon-prod</div></div></button></div>'));await unit.add_script_tag(path=str(ROOT/'extension/engine.js'))
   safe=await unit.evaluate('''async(p)=>{let clicked=false;const b=document.querySelector('button');b.onclick=()=>clicked=true;const c={...p,broker:true,identity:false,mode:'login',selectors:{}};const plan=OCILoginEngine.describe(c);document.querySelector('.user-name').textContent='changed@example.invalid';try{await OCILoginEngine.execute(plan,c,{},async()=>({ok:true}));}catch{}return !clicked;}''',PROFILE);assert safe;ok('changed session metadata is rechecked before any click')
   assert not errors,errors
   (WORK/'session-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'network':'Loopback-only TLS fixtures; Oracle public script used only to identify DOM selectors; zero customer session data in tests','scope':'Linux Chromium shipped worker/content/engine; actual user logged-in session not controlled'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--team-only' in sys.argv:
   await page.evaluate('''async(p)=>{const {handleSet}=await import('./lib/db.js');const h=await(await navigator.storage.getDirectory()).getFileHandle('worker-team.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[p]}));await w.close();await handleSet(h);await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker',nativePath:''}});}''',PROFILE)
   async def launch_team():return await page.evaluate('async(p)=>chrome.runtime.sendMessage({type:"START",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito})),profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"})',PROFILE)
   async def end_team(tid):
    for _ in range(200):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:return st
     await page.wait_for_timeout(120)
    raise AssertionError(st)
   r=await launch_team();assert r['ok'],r;assert (await end_team(r['tabId']))['step']=='complete';ok('worker logs in from persisted team FileSystemFileHandle with no personal accounts')
   await page.evaluate('''async(p)=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('worker-team.json');const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[{...p,password:'changed-on-disk'}]}));await w.close();}''',PROFILE)
   for old in list(ctx.pages):
    if old!=page and old.url.startswith('https://'):await old.close()
   r=await launch_team();assert r['ok'],r;assert (await end_team(r['tabId']))['step']=='stopped';ok('worker uses changed team password rather than previous successful credentials')
   await page.evaluate('''async()=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('worker-team.json');const w=await h.createWritable();await w.write('broken JSON');await w.close();}''')
   r=await launch_team();assert not r['ok'];ok('worker rejects unreadable team config before creating a login job')
   assert not errors,errors
   (WORK/'team-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'scope':'Loopback TLS fixtures; persisted OPFS file handle; Linux Chromium'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--features-only' in sys.argv:
   await expect(page.locator('#quick-presets .swatch')).to_have_count(6)
   await page.locator('#quick-presets [data-color="#65a8ff"]').click();await page.reload();await page.locator('#bulk-open').wait_for()
   assert await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")=='#65a8ff';assert not await page.locator('#settings-dialog').is_visible();ok('six circular preset colors change and persist from main UI without opening settings')
   await page.locator('#add').click();assert await page.locator('#p-name').is_visible();await page.locator('#cancel-edit').click();ok('customer alias is a basic account field outside advanced settings')
   await page.locator('#bulk-open').click()
   vals={'tenancy':'\n'.join(['cloudragon-prod']+['fixture-tenant-'+str(i) for i in range(1,25)]),'username':'\n'.join(['operator@example.invalid']*25),'password':'\n'.join(['fixture-password']*25),'bypassCode':'\n'.join(['000123']*25),'name':'\n'.join(['가상고객 운영']+['가상고객 '+str(i) for i in range(1,25)]),'identityDomain':''}
   for k,v in vals.items():await page.locator('#bulk-'+k).fill(v+'\n' if v else '')
   await page.locator('#bulk-password').fill('too-few');await page.locator('#bulk-preview').click();assert '행' in await page.locator('#bulk-error').inner_text();assert await page.locator('#bulk-save').is_disabled();assert not (await page.evaluate("async()=> (await chrome.storage.local.get('profiles')).profiles"));ok('mismatched pasted columns block entire registration without saving any account')
   broken=['fixture-password']*25;broken[6]='';await page.locator('#bulk-password').fill('\n'.join(broken)+'\n');await page.locator('#bulk-preview').click();assert '7행' in await page.locator('#bulk-error').inner_text();ok('empty password cell identifies its row and never shifts the following credentials')
   await page.locator('#bulk-password').fill(vals['password']+'\n');await page.locator('#bulk-preview').click();await expect(page.locator('#bulk-rows tr')).to_have_count(25)
   review=await page.locator('#bulk-review').inner_text();assert 'fixture-password' not in review and '000123' not in review;assert await page.locator('#bulk-password').evaluate("e=>getComputedStyle(e).webkitTextSecurity")=='disc';ok('25-row preview preserves order and aliases while masking secrets and omitting them from table')
   await page.screenshot(path=str(shots/'bulk-desktop.png'))
   await page.locator('#bulk-name').fill(vals['name']+'\n');assert await page.locator('#bulk-save').is_disabled();await page.locator('#bulk-preview').click();await page.locator('#bulk-save').click();await expect(page.locator('#bulk-dialog')).not_to_be_visible();await expect(page.locator('.account-row')).to_have_count(25)
   saved=await page.evaluate("async()=> (await chrome.storage.local.get('profiles')).profiles");assert len(saved)==25 and saved[0]['bypassCode']=='000123' and saved[24]['name']=='가상고객 24';assert await page.locator('#bulk-password').input_value()=='';ok('one confirmation appends all25 accounts atomically and clears pasted credentials afterward')
   await page.locator('#search').fill('가상고객 24');await expect(page.locator('.account-row')).to_have_count(1);assert await page.locator('#detail-title').inner_text()=='fixture-tenant-24';await page.reload();await page.locator('#search').fill('가상고객 운영');await expect(page.locator('.account-row')).to_have_count(1);assert '가상고객 운영' in await page.locator('#detail-subtitle').inner_text();ok('customer alias search and display persist through reload with legacy name schema')
   await page.locator('#edit').click();await page.locator('#p-name').fill('가상고객 변경');await page.locator('#account-form button[type=submit]').click();await page.locator('#search').fill('가상고객 변경');await expect(page.locator('.account-row')).to_have_count(1);ok('editing customer alias updates subsequent search without changing authentication target')
   await page.locator('#bulk-open').click()
   for k in ['tenancy','username','password','bypassCode']:await page.locator('#bulk-'+k).fill(vals[k].split('\n')[0])
   await page.locator('#bulk-preview').click();assert '중복' in await page.locator('#bulk-error').inner_text();assert await page.locator('#bulk-save').is_disabled();await page.keyboard.press('Escape');assert not await page.locator('#bulk-dialog').is_visible();assert await page.locator('#bulk-bypassCode').input_value()=='';ok('duplicate target is rejected and Escape clears the whole unsaved batch')
   await page.evaluate("""async()=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('bulk-write-denied.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[]}));await w.close();await(await import('./lib/db.js')).handleSet(h);await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker'}})}""")
   await worker.evaluate("()=>{globalThis.fixturePermissionQuery=FileSystemFileHandle.prototype.queryPermission;FileSystemFileHandle.prototype.queryPermission=function(x){return x?.mode==='readwrite'?Promise.resolve('denied'):fixturePermissionQuery.call(this,x);};}");denied=await page.evaluate('async(p)=>{const s=await import("./lib/sources.js");return chrome.runtime.sendMessage({type:"BULK_ADD",source:s.sourceRef(await s.readSource()),profiles:[p]});}',PROFILE);await worker.evaluate("()=>{FileSystemFileHandle.prototype.queryPermission=fixturePermissionQuery;}");assert not denied['ok'] and '팀' in denied['error'];assert len(await page.evaluate("async()=> (await chrome.storage.local.get('profiles')).profiles"))==25;ok('worker rejects bulk writes when active team source is read-only')
   await page.evaluate("chrome.storage.local.set({settings:{mode:'local',fileKind:'picker',nativePath:''}})")
   # Enable private access through the real extension settings in this disposable browser.
   settings=await ctx.new_page();await settings.goto('chrome://extensions/?id='+eid);await settings.locator('#allow-incognito').click()
   # COMMAND_LINE test extensions unload when this preference changes; relaunch
   # the same disposable profile so Chromium loads the granted extension again.
   await ctx.close();ctx=await launch_browser();page=await ctx.new_page();await page.goto(f'chrome-extension://{eid}/options.html');await page.locator('#bulk-open').wait_for();worker=ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event('serviceworker');assert await page.evaluate('chrome.extension.isAllowedIncognitoAccess()')
   normal_scope=await page.evaluate('async()=>{const w=await chrome.windows.getCurrent();return {windowId:w.id,incognito:w.incognito};}')
   normal=await ctx.new_page();await normal.goto(CONSOLE+'/done');await normal.evaluate("document.cookie='fixture-normal-only=normal; path=/; secure'")
   private=await page.evaluate('chrome.windows.create({incognito:true,url:"about:blank",focused:false})');assert private['incognito'];scope={'windowId':private['id'],'incognito':True}
   await page.evaluate('(id)=>chrome.windows.update(id,{focused:true})',normal_scope['windowId'])
   await page.evaluate('''async(p)=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('private-team.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[p]}));await w.close();await(await import('./lib/db.js')).handleSet(h);await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker',nativePath:''}});}''',PROFILE)
   before_meta=await page.evaluate('chrome.storage.local.get(["identityBindings","lastUsed"])')
   scenario='regional-domain-ko'
   entry_begin=len(requests)
   r=await page.evaluate('(x)=>chrome.runtime.sendMessage({type:"START",profileId:x.p.id,expected:{tenancy:x.p.tenancy,username:x.p.username,identityDomain:x.p.identityDomain},mode:"login",...x.scope})',{'p':PROFILE,'scope':scope});assert r['ok'],r;tid=r['tabId']
   for _ in range(260):
    st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
    if st and not st['running']:break
    await page.wait_for_timeout(120)
   assert st['step']=='complete',{'status':st,'requests':requests[-12:]}
   target=await page.evaluate('(id)=>chrome.tabs.get(id)',tid);assert target['windowId']==private['id'] and target['incognito'] and target['url']==CONSOLE+'/done';assert requests[entry_begin]==ENTRY+'/cloud/sign-in.html' and CONSOLE+'/' not in requests[entry_begin:];ok('real Chromium private window passes regional domain selection and completes password/bypass in exact initiating private window')
   scenario='session-recovery-layout'
   r=await page.evaluate('(x)=>chrome.runtime.sendMessage({type:"START",profileId:x.p.id,expected:{tenancy:x.p.tenancy,username:x.p.username,identityDomain:x.p.identityDomain},mode:"login",...x.scope})',{'p':PROFILE,'scope':scope});assert r['ok'],r;recovered=r['tabId']
   for _ in range(260):
    recovery=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',recovered)
    if recovery and not recovery['running']:break
    await page.wait_for_timeout(120)
   target=await page.evaluate('(id)=>chrome.tabs.get(id)',recovered)
   assert recovery['step']=='complete' and target['windowId']==private['id'] and target['incognito'] and target['url']==CONSOLE+'/done',recovery
   scenario='normal';ok('stalled session recovery completes tenancy/password/bypass in the same initiating private window')
   cookie=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:()=>{const before=document.cookie;document.cookie='fixture-private-only=private; path=/; secure';return before;}}))[0].result''',tid);assert 'fixture-normal-only' not in cookie;assert 'fixture-private-only' not in await normal.evaluate('document.cookie');ok('normal and private OCI cookie jars stay separate during automatic login')
   assert await page.evaluate('chrome.storage.local.get(["identityBindings","lastUsed"])')==before_meta;ok('private login reads shared vault/team handle but does not persist learned identity or last-used browsing metadata')
   visible=await page.evaluate('(s)=>chrome.runtime.sendMessage({type:"STATUS",...s})',normal_scope);hidden=await page.evaluate('(s)=>chrome.runtime.sendMessage({type:"STATUS",...s})',scope);assert not any(x['tabId']==tid for x in visible['items']) and any(x['tabId']==tid for x in hidden['items']);ok('private job status is excluded from normal-window UI')
   await page.evaluate('(id)=>chrome.windows.remove(id)',private['id']);before_tabs=await page.evaluate('chrome.tabs.query({})')
   missing=await page.evaluate('(x)=>chrome.runtime.sendMessage({type:"START",profileId:x.p.id,expected:{tenancy:x.p.tenancy,username:x.p.username,identityDomain:x.p.identityDomain},mode:"login",...x.scope})',{'p':PROFILE,'scope':scope});assert not missing['ok'];assert len(await page.evaluate('chrome.tabs.query({})'))==len(before_tabs);ok('closed private origin window fails without opening a replacement normal tab')
   await page.evaluate("chrome.storage.local.set({settings:{mode:'local',fileKind:'picker',nativePath:''}})");await page.locator('#refresh').click();await page.locator('#search').fill('가상고객 변경')
   await page.screenshot(path=str(shots/'vault-quick-palette.png'))
   for width in [768,390]:
    await page.set_viewport_size({'width':width,'height':850});await page.locator('#bulk-open').click();await page.screenshot(path=str(shots/('bulk-'+str(width)+'.png')));assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth');await page.locator('#cancel-bulk').click()
   await page.set_viewport_size({'width':780,'height':580});popup=await ctx.new_page();await popup.set_viewport_size({'width':780,'height':580});await popup.goto(f'chrome-extension://{eid}/popup.html');await popup.locator('#quick-presets .swatch').first.wait_for();assert not await popup.evaluate('document.documentElement.scrollHeight>innerHeight');ok('bulk dialog fits desktop/tablet/mobile and quick palette fits actual780x580 popup')
   for count in [25,300]:
    sample=saved if count==25 else [{**PROFILE,'id':'scroll-'+str(i),'tenancy':'fixture-'+str(i),'name':'가상고객 '+str(i)} for i in range(count)]
    await popup.evaluate('(ps)=>chrome.storage.local.set({profiles:ps})',sample);await popup.locator('#refresh').click();await popup.locator('#search').fill('');await expect(popup.locator('.account-row')).to_have_count(count)
    dims=await popup.evaluate('''()=>{const list=document.querySelector('#accounts'),f=document.querySelector('.sidebar-footer');return {height:list.clientHeight,scroll:list.scrollHeight,footer:f.getBoundingClientRect().bottom};}''');assert 100<dims['height']<580 and dims['scroll']>dims['height'] and dims['footer']<=580,dims
    await popup.locator('#search').press('ArrowUp');last=popup.locator('.account-row').last;assert await last.get_attribute('aria-selected')=='true';box=await last.bounding_box();area=await popup.locator('#accounts').bounding_box();assert box['y']>=area['y']-1 and box['y']+box['height']<=area['y']+area['height']+1
    await popup.locator('#search').press('ArrowDown')
   await popup.evaluate('(ps)=>chrome.storage.local.set({profiles:ps})',saved);await popup.locator('#refresh').click();await popup.screenshot(path=str(shots/'popup-quick-palette.png'));ok('25 and300 account lists scroll within popup, retain footer, and reach last account by keyboard')
   assert not errors,errors
   (WORK/'features-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'network':'Loopback-only TLS fixtures; real disposable Chromium normal/private windows and cookie jars','scope':'Linux Chromium; incognito toggle enabled on disposable browser settings; API START uses originating window snapshot; actual Windows/Brave shortcut popup remains unverified'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--injection-only' in sys.argv:
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE)
   await worker.evaluate("()=>{globalThis.realExec=chrome.scripting.executeScript;globalThis.realRegister=chrome.scripting.registerContentScripts;globalThis.realContains=chrome.permissions.contains;}")
   for fault in ['stale','transient','permission','persistent']:
    await page.evaluate('chrome.storage.local.remove("identityBindings")')
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
    await worker.evaluate('''(fault)=>{globalThis.faultCount=0;chrome.scripting.registerContentScripts=async()=>{};chrome.permissions.contains=q=>fault==='permission'&&q.origins?.length===1?Promise.resolve(false):realContains(q);chrome.scripting.executeScript=async(q)=>{if(q.files&&(fault==='permission'||fault==='persistent'||faultCount===0)){faultCount++;if(fault==='stale'){const done=new Promise(ok=>{const listener=d=>{if(d.tabId===q.target.tabId&&d.frameId===0&&d.url==='https://cloud.oracle.com/retry-entry'){chrome.webNavigation.onCommitted.removeListener(listener);ok();}};chrome.webNavigation.onCommitted.addListener(listener);});await chrome.tabs.update(q.target.tabId,{url:'https://cloud.oracle.com/retry-entry'});await done;}throw new Error('Controlled injection failure');}return realExec(q);};}''',fault)
    r=await page.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"START",windowId:w.id,incognito:w.incognito,profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"});}',PROFILE);assert r['ok'],r;tid=r['tabId']
    for _ in range(180):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:break
     await page.wait_for_timeout(100)
    failures=await worker.evaluate('faultCount')
    if fault in ['stale','transient']:assert st['step']=='complete' and failures==1,st;ok(fault+' injection race recovers without aborting the login job')
    else:assert st['step']=='stopped' and st['reason']==('access-denied' if fault=='permission' else 'injection-failed'),st;ok(fault+' injection failure stops explicitly and does not loop forever')
    await worker.evaluate("()=>{chrome.scripting.executeScript=realExec;chrome.scripting.registerContentScripts=realRegister;chrome.permissions.contains=realContains;}")
   assert not errors,errors
   (WORK/'injection-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'scope':'Disposable Chromium extension with deterministic API failure hooks; stale document, transient, permission-revoked and persistent same-document cases'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--mfa-only' in sys.argv:
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE)
   for scenario in ['mfa-icon','mfa-open','mfa-jet','mfa-missing-marker','mfa-other-factor','mfa-disabled','mfa-duplicate-choice','mfa-duplicate-input']:
    await page.evaluate('chrome.storage.local.remove("identityBindings")')
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
    r=await page.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"START",windowId:w.id,incognito:w.incognito,profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"});}',PROFILE);assert r['ok'],r;tid=r['tabId']
    for _ in range(160):
     tab=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
     if tab.get('url','').startswith(IDENTITY+'/mfa') or tab.get('url','').startswith(CONSOLE+'/done'):break
     await page.wait_for_timeout(100)
    for _ in range(90 if scenario in ['mfa-icon','mfa-open','mfa-jet'] else 30):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:break
     await page.wait_for_timeout(100)
    if scenario in ['mfa-icon','mfa-open','mfa-jet']:
     assert st['step']=='complete',st;tab=await page.evaluate('(id)=>chrome.tabs.get(id)',tid);assert tab['url']==CONSOLE+'/done?mfa=1&choice=1&verify=1&sms=0&other=0';ok(scenario+' selects bypass before filling generic JET field and verifies once, with no SMS/TOTP write')
    else:
     target=next(x for x in ctx.pages if x.url==IDENTITY+'/mfa');state=await target.evaluate('()=>({stats:fixtureStats,values:[...document.querySelectorAll("input")].map(e=>e.value)})');assert all(v=='' for v in state['values']) and state['stats']['verify']==0 and state['stats']['smsWrites']==0,state
     if scenario in ['mfa-duplicate-choice','mfa-duplicate-input']:assert st['step']=='stopped',st
     else:assert st['running'],st
     if scenario!='mfa-duplicate-input':assert state['stats']['choice']==0,state
     await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid);ok(scenario+' leaves unverified/ambiguous controls empty without submitting')
   assert not errors,errors
   (WORK/'mfa-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'scope':'Linux Chromium shipped extension, loopback TLS, same-document push→factor→generic JET-shaped bypass view; real public JET template proof is separate'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--regional-only' in sys.argv:
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE);await page.locator('#refresh').click()
   async def start_regional():
    await page.evaluate('chrome.storage.local.remove("identityBindings")')
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
    r=await page.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"START",windowId:w.id,incognito:w.incognito,profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"});}',PROFILE);assert r['ok'],r;return r['tabId']
   async def wait_regional(tid):
    for _ in range(160):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:return st
     await page.wait_for_timeout(100)
    raise AssertionError(st)
   for scenario in ['regional-forward','regional-oci','regional-unverified','regional-other']:
    tid=await start_regional();st=await wait_regional(tid)
    if scenario in ['regional-forward','regional-oci']:
     assert st['step']=='complete',st;bindings=await page.evaluate('chrome.storage.local.get("identityBindings")');assert list(bindings['identityBindings'].values())[0]['origin']==IDENTITY;ok(scenario+' tracks global→regional→IDCS and completes without binding broker as identity')
    else:assert st['step']=='stopped' and st['reason']==('unverified-tenancy' if scenario=='regional-unverified' else 'unsupported-origin'),st;ok(scenario+' still stops with an explicit privacy-safe reason')
   for scenario in ['regional-domain-default','regional-domain-preselected','regional-domain-oci','regional-domain-ko','regional-domain-spa','regional-domain-missing','regional-domain-ambiguous','regional-domain-wrong-tenant']:
    tid=await start_regional();st=await wait_regional(tid)
    if scenario in ['regional-domain-missing','regional-domain-ambiguous','regional-domain-wrong-tenant']:
     assert st['step']=='stopped' and st['reason']=='page-error',st
     target=next(x for x in ctx.pages if '/v2/ui/domains' in x.url)
     assert await target.evaluate("fixtureDomainClicks===0&&[...document.querySelectorAll('input')].every(e=>e.value==='')")
     ok(scenario+' stops without submitting or filling any credentials')
    else:
     assert st['step']=='complete' and 'domain' in st['debug']['applied'] and 'bypass' in st['debug']['applied'],st
     ok(scenario+' selects exact saved domain, clicks Next once with empty credentials and completes identity/bypass login')
   scenario='regional-domain-guard';tid=await start_regional()
   for _ in range(160):
    target=next((x for x in ctx.pages if '/v2/ui/domains' in x.url),None)
    if target and await target.evaluate('globalThis.fixtureDomainClicks===1'):break
    await page.wait_for_timeout(100)
   assert target
   denied=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:async()=>({context:await chrome.runtime.sendMessage({type:'CONTEXT'}),claims:await Promise.all(['tenancy','sessionPick','newLogin','credentials','username','bypass','alternative','bypassChoice'].map(stage=>chrome.runtime.sendMessage({type:'CLAIM',stage}))),applied:await chrome.runtime.sendMessage({type:'APPLIED',stage:'credentials'}),complete:await chrome.runtime.sendMessage({type:'COMPLETE'})})}))[0].result''',tid)
   context=denied['context']['context'];assert context['domainOnly'] and not context['identity'] and not context['broker'] and 'username' not in context
   assert all(not x['ok'] for x in denied['claims']) and not denied['applied']['ok'] and not denied['complete']['ok']
   assert all(v not in json.dumps(denied) for v in [PROFILE['username'],PROFILE['password'],PROFILE['bypassCode']])
   assert await target.evaluate("fixtureDomainClicks===1&&[...document.querySelectorAll('input')].every(e=>e.value==='')")
   ok('regional domain page receives only tenancy/domain metadata, denies every secret claim and submits exactly once')
   await target.evaluate("history.pushState({},'', '/v2/ui/native')")
   context=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:()=>chrome.runtime.sendMessage({type:'CONTEXT'})}))[0].result''',tid)
   assert not context['ok'];ok('same-document regional path change immediately loses access to context')
   await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid)
   scenario='regional-domain-unverified';tid=await start_regional()
   for _ in range(160):
    target=next((x for x in ctx.pages if '/v2/ui/domains' in x.url),None)
    if target and await target.evaluate("!!document.querySelector('select')"):break
    await page.wait_for_timeout(100)
   assert target;await page.wait_for_timeout(1500)
   denied=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:async()=>({context:await chrome.runtime.sendMessage({type:'CONTEXT'}),domain:await chrome.runtime.sendMessage({type:'CLAIM',stage:'domain'})})}))[0].result''',tid)
   assert not denied['context']['ok'] and not denied['domain']['ok'] and await target.evaluate("fixtureDomainClicks===0&&[...document.querySelectorAll('input')].every(e=>e.value==='')")
   ok('unverified tenancy cannot obtain even a domain claim on a regional chooser')
   await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid)
   scenario='regional-guard';tid=await start_regional()
   for _ in range(120):
    tab=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
    if tab.get('url')==REGIONAL+'/v1/oauth2/authorize' and tab.get('status')=='complete':break
    await page.wait_for_timeout(100)
   denied=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:async()=>({injected:!!globalThis.OCILoginEngine,context:await chrome.runtime.sendMessage({type:'CONTEXT'}),credentials:await chrome.runtime.sendMessage({type:'CLAIM',stage:'credentials'}),bypass:await chrome.runtime.sendMessage({type:'CLAIM',stage:'bypass'})})}))[0].result''',tid)
   assert not denied['injected'] and all(not denied[k]['ok'] for k in ['context','credentials','bypass']);ok('regional broker is navigation-only: no automatic injection, context, password or bypass even after verified tenancy')
   registered=await page.evaluate('chrome.scripting.getRegisteredContentScripts()');regional_matches=[x for row in registered for x in row['matches'] if REGIONAL in x or REGIONAL_OCI in x];assert regional_matches and all(x.endswith('/v2/ui/domains*') for x in regional_matches);ok('regional content registration is limited to the domain chooser and excludes OAuth/native pages')
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[{...p,identityOrigins:["https://login.us-ashburn-1.oraclecloud.com"]}]})',PROFILE)
   fill=await page.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"START",windowId:w.id,incognito:w.incognito,profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"fill"});}',PROFILE);assert not fill['ok'];await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE);ok('regional broker refuses fill-only even if an imported profile explicitly lists it as an identity')

   await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid)
   scenario='regional-manual';tid=await start_regional()
   for _ in range(120):
    tab=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
    if tab.get('url')==REGIONAL+'/v1/oauth2/authorize' and tab.get('status')=='complete':break
    await page.wait_for_timeout(100)
   target=next(x for x in ctx.pages if x.url==tab['url']);await target.goto('https://idcs-untrusted.identity.oraclecloud.com/credentials');st=await wait_regional(tid);assert st['step']=='stopped';assert await target.locator('#password').input_value()=='';ok('typed identity navigation from a regional broker cannot become a trusted identity')
   report=await page.evaluate('async(p)=>{const w=await chrome.windows.getCurrent();return chrome.runtime.sendMessage({type:"DIAGNOSTICS",windowId:w.id,incognito:w.incognito,profileId:p.id});}',PROFILE)
   encoded=json.dumps(report);assert report['ok'] and report['report']['version']==json.loads((ROOT/'extension/manifest.json').read_text())['version'] and report['report']['reason']=='unsupported-origin';assert all(v not in encoded for v in [PROFILE['tenancy'],PROFILE['username'],PROFILE['password'],PROFILE['bypassCode'],IDENTITY,REGIONAL]);ok('diagnostics export contains routing categories and reason but no account, hostname or secret')
   await page.locator('#more').click();await page.locator('#diagnostics').click();await expect(page.locator('#toast')).to_have_text('진단 정보를 복사했습니다');ok('user-triggered diagnostic copy works from existing account menu')
   assert not errors,errors
   (WORK/'regional-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'scope':'Linux Chromium loopback fixtures mirroring actual global link→regional hidden form→IDCS HTTP302; test-only exact regional grants; domain chooser full flow and OAuth/secret/same-document deny checks'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  if '--redirect-only' in sys.argv:
   await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',PROFILE)
   for scenario in ['redirect-korean','redirect-jet','redirect-http','redirect-slow','redirect-disabled','redirect-ambiguous']:
    await page.evaluate('chrome.storage.local.remove("identityBindings")')
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
    start=time.monotonic();r=await page.evaluate('async(p)=>chrome.runtime.sendMessage({type:"START",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito})),profileId:p.id,expected:{tenancy:p.tenancy,username:p.username,identityDomain:p.identityDomain},mode:"login"})',PROFILE);assert r['ok'],r;tid=r['tabId']
    for _ in range(160):
     st=await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
     if st and not st['running']:break
     await page.wait_for_timeout(100)
    elapsed=time.monotonic()-start
    if scenario in ['redirect-disabled','redirect-ambiguous']:assert st['step']=='stopped',st;ok(scenario+' stops safely without repeating an invalid submission')
    else:assert st['step']=='complete',st;ok(scenario+' completes HTTP redirects, native/wrapped inputs, Korean sign-in and bypass')
    if scenario=='redirect-slow':assert elapsed<8,elapsed;ok('DOMContentLoaded injection completes login before slow subresource load finishes')
   await page.evaluate('chrome.storage.local.set({profiles:[]})');await page.locator('#refresh').click();assert not await page.locator('#empty-detail h2:visible,#empty-detail p:visible,.account-list .empty:visible').count();await expect(page.locator('#empty-add')).to_be_visible()
   await page.keyboard.press('Alt+n');await expect(page.locator('#edit-dialog')).to_be_visible();await page.keyboard.press('Alt+n');assert await page.locator('dialog[open]').count()==1;await page.locator('#cancel-edit').click();await page.locator('#empty-add').click();await expect(page.locator('#edit-dialog')).to_be_visible();await page.locator('#cancel-edit').click();ok('empty view is one add button; Alt+N and button open the same editor without stacked dialogs')
   await page.set_viewport_size({'width':780,'height':580});popup=await ctx.new_page();await popup.set_viewport_size({'width':780,'height':580});await popup.goto(f'chrome-extension://{eid}/popup.html');await popup.locator('#empty-add').wait_for();await popup.screenshot(path=str(shots/'empty-popup.png'))
   assert not errors,errors
   (WORK/'redirect-report.json').write_text(json.dumps({'count':len(checks),'checks':checks,'scope':'Actual Linux Chromium extension and loopback TLS fixtures, HTTP302, JET-shaped native controls, initially-disabled Korean button, delayed resource; public real-JET component proof separate'},ensure_ascii=False,indent=2)+'\n')
   await ctx.close();server.close();await server.wait_closed();return
  assert not await page.locator('#empty-detail h2:visible,#empty-detail p:visible,.account-list .empty:visible').count();await expect(page.locator('#empty-add')).to_be_visible();ok('completed local setup has only add-account action and its shortcut')
  await page.locator('#add').click()
  for k,v in {'p-tenancy':PROFILE['tenancy'],'p-username':PROFILE['username'],'p-password':PROFILE['password'],'p-bypass':PROFILE['bypassCode']}.items():await page.locator('#'+k).fill(v)
  assert not await page.locator('#p-login').count();await page.locator('#account-form button[type=submit]').click();await page.wait_for_timeout(300)
  saved=await page.evaluate("async()=> (await chrome.storage.local.get('profiles')).profiles");assert len(saved)==1 and saved[0]['bypassCode']=='000123' and 'loginUrl' not in saved[0];profile=saved[0];ok('four-field editor saves leading-zero bypass code without website URL')
  assert await page.locator('#bypassCode').inner_text()=='••••••••••••';await page.locator('[data-reveal=bypassCode]').click();assert await page.locator('#bypassCode').inner_text()=='000123';ok('bypass reveal is explicit and masked on reload')
  await page.locator('[data-copy=username]').click();await expect(page.locator('#toast')).to_have_text('복사했습니다');ok('user-triggered copy shows confirmation')
  await page.locator('#settings').click();await page.locator('#theme-mode').select_option('light');await page.locator('#theme-accent').fill('#176b61');await page.locator('#theme-accent').dispatch_event('input');await page.locator('#close-settings').click();await page.reload();await page.wait_for_timeout(200)
  assert await page.locator('html').get_attribute('data-theme')=='light';assert await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")=='#176b61';assert await page.locator('#bypassCode').inner_text()!='000123';ok('custom color and light mode persist independently of credentials')
  # Import/export and conflicts.
  await page.locator('#settings').click();await page.locator('[data-tab=transfer]').click();await page.locator('#export-ack').check()
  async with page.expect_download() as d:await page.locator('#export').click()
  dl=await d.value;assert json.loads(pathlib.Path(await dl.path()).read_text())['profiles'][0]['password']=='fixture-password';ok('explicit export includes selected source')
  incoming={'schemaVersion':1,'profiles':[{**profile,'password':'changed'}]}
  await page.locator('#import-file').set_input_files({'name':'fixture.json','mimeType':'application/json','buffer':json.dumps(incoming).encode()});await page.locator('#import-confirm').click();await page.wait_for_timeout(100);assert '같은 ID' in await page.locator('#settings-message').inner_text();ok('import conflict preserves account')
  await page.locator('#allow-updates').check();await page.locator('#import-confirm').click();await page.wait_for_timeout(150);assert (await page.evaluate("async()=> (await chrome.storage.local.get('profiles')).profiles"))[0]['password']=='changed';ok('explicit import update succeeds')
  await page.locator('#close-settings').click();await page.evaluate('(p)=>chrome.storage.local.set({profiles:[p]})',profile);await page.locator('#refresh').click();await page.wait_for_timeout(150)
  async def status(tid):return await page.evaluate('(id)=>chrome.storage.session.get("status:"+id).then(x=>x["status:"+id])',tid)
  async def direct_start(p=profile,mode='login'):
   if mode=='login':
    for old in list(ctx.pages):
     if old!=page and old.url.startswith('https://'):await old.close()
   r=await page.evaluate('async(x)=>chrome.runtime.sendMessage({type:"START",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito})),profileId:x.p.id,expected:{tenancy:x.p.tenancy,username:x.p.username,identityDomain:x.p.identityDomain},mode:x.mode})',{'p':p,'mode':mode});assert r.get('ok'),r
   if mode=='login':
    for _ in range(200):
     latest=await page.evaluate('(id)=>chrome.tabs.get(id).then(t=>({url:t.url,status:t.status}))',r['tabId'])
     if latest.get('status')=='complete' and latest.get('url','').startswith('https://'):break
     await page.wait_for_timeout(100)
   return r['tabId']
  async def wait_end(tid):
   for _ in range(240):
    s=await status(tid)
    if s and not s['running']:return s
    await page.wait_for_timeout(120)
   raise AssertionError({'status':s,'urls':[x.url for x in ctx.pages],'requests':requests[-20:]})
  async def find_tab(tid):
   for _ in range(80):
    t=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
    target=next((x for x in reversed(ctx.pages) if x.url==t.get('url') and x!=page),None)
    if target and t.get('status')=='complete':return target
    await page.wait_for_timeout(100)
   raise AssertionError(t)
  # Start using actual tenancy search + Enter, with no URL or preconfigured identity.
  entry_begin=len(requests)
  await page.locator('#search').fill('cloudragon-prod')
  await page.locator('#search').press('Enter')
  for _ in range(80):
   items=await page.evaluate('async()=>chrome.runtime.sendMessage({type:"STATUS",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito}))})')
   if items.get('items'):break
   await page.wait_for_timeout(100)
  tid=items['items'][0]['tabId'];s=await wait_end(tid);assert s['step']=='complete',s;assert not await page.evaluate('(id)=>chrome.storage.session.get("job:"+id)',tid);ok('tenancy search + Enter completes tenancy, domain, credentials, alternative, bypass and console')
  assert requests[entry_begin]==ENTRY+'/cloud/sign-in.html' and CONSOLE+'/' not in requests[entry_begin:] and BROKER+'/v2/ui/sessionPicker' not in requests[entry_begin:];assert s['debug']['route'][0]=='account-entry';ok('normal login starts at official tenancy entry, replaces a remembered tenancy and avoids the console-first session picker')
  bindings=await page.evaluate("async()=> (await chrome.storage.local.get('identityBindings')).identityBindings");assert list(bindings.values())[0]['origin']==IDENTITY;ok('verified identity metadata is learned without storing a website field')
  tid=await direct_start();assert (await wait_end(tid))['step']=='complete';ok('same reusable admin bypass code succeeds on second login')
  scenario='custom';tid=await direct_start();assert (await wait_end(tid))['step']=='complete';ok('custom domain picker, Korean alternate label and styled bypass radio complete')
  registered=await page.evaluate('()=>chrome.scripting.getRegisteredContentScripts()');assert all('*.' not in x for r in registered for x in r['matches']);ok('automatic scripts registered only for exact granted origins')
  for case in ['sms','duplicate','invalid']:
   scenario=case;tid=await direct_start()
   if case=='sms':
    for _ in range(150):
     t=await page.evaluate('(id)=>chrome.tabs.get(id)',tid)
     if t.get('url')==IDENTITY+'/mfa' and t.get('status')=='complete':break
     await page.wait_for_timeout(100)
    target=await find_tab(tid);await page.wait_for_timeout(1500);assert await target.locator('#otp').input_value()=='';await page.evaluate('(id)=>chrome.runtime.sendMessage({type:"CANCEL",tabId:id})',tid);ok('SMS challenge with bypass link never receives static code')
   else:
    s=await wait_end(tid);assert s['step']=='stopped';target=await find_tab(tid);assert await target.locator('#password').input_value()=='';ok(case+' screen stops before secret entry')
  scenario='hold';tid=await direct_start();target=await find_tab(tid);await target.goto('https://idcs-untrusted.identity.oraclecloud.com/credentials');await page.wait_for_timeout(600);assert await target.locator('#password').input_value()=='';assert (await status(tid))['step']=='stopped';ok('unverified navigation to another identity receives no credentials')
  # Expected metadata must still match the worker fresh source.
  r=await page.evaluate('async(p)=>chrome.runtime.sendMessage({type:"START",...await chrome.windows.getCurrent().then(w=>({windowId:w.id,incognito:w.incognito})),profileId:p.id,expected:{tenancy:"changed",username:p.username,identityDomain:p.identityDomain}})',profile);assert not r['ok'] and '변경' in r['error'];ok('changed target metadata aborts login')
  # Fill-only in verified identity, with no submit.
  target=await ctx.new_page();await target.goto(IDENTITY+'/credentials');await target.bring_to_front();tid=await direct_start(mode='fill');await page.wait_for_timeout(1600);assert await target.locator('#password').input_value()=='fixture-password' and target.url==IDENTITY+'/credentials';ok('fill-only populates credentials without submitting')
  access=await worker.evaluate('''async(id)=>(await chrome.scripting.executeScript({target:{tabId:id},func:async()=>{try{await chrome.storage.local.get(null);return 'exposed';}catch{return 'denied';}}}))[0].result''',tid);assert access=='denied';ok('content script cannot read local vault storage')
  await page.evaluate('''async(id)=>{const k='job:'+id;const j=(await chrome.storage.session.get(k))[k];j.expiresAt=Date.now()-1;await chrome.storage.session.set({[k]:j});}''',tid);await page.wait_for_timeout(1500);assert not await page.evaluate('(id)=>chrome.storage.session.get("job:"+id)',tid);ok('expired job secrets are removed')
  # Team file handles persist; always re-read current bytes; errors do not fallback.
  await page.evaluate('''async(p)=>{const {handleSet}=await import('./lib/db.js');const d=await navigator.storage.getDirectory();const h=await d.getFileHandle('fixture-team.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[p]}));await w.close();await handleSet(h);await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker',nativePath:''}});}''',profile)
  await page.reload();await page.wait_for_timeout(200);assert await page.locator('#add').is_enabled() and await page.locator('#edit').is_enabled();ok('connected team source is editable by default without an application checkbox')
  await page.evaluate('''async(p)=>{const d=await navigator.storage.getDirectory();const h=await d.getFileHandle('fixture-team.json');const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:[{...p,name:'변경된 팀 계정'}]}));await w.close();}''',profile);await page.locator('#refresh').click();await page.wait_for_timeout(200);assert '변경된 팀 계정' in await page.locator('#accounts').inner_text();ok('file handle persists and changed team bytes are reread')
  await page.evaluate('''async()=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('fixture-team.json');const w=await h.createWritable();await w.write('broken JSON');await w.close();}''');await page.locator('#refresh').click();await page.wait_for_timeout(150);assert not await page.locator('.account-row').count();ok('invalid team file never falls back to personal credentials')
  # Real UI edit/delete, sample preview data never includes user credentials.
  demos=[{**profile,'id':'preview-prod','name':'서울 운영 계정'},{**profile,'id':'preview-dev','tenancy':'cloudragon-dev','name':'개발 · 테스트','username':'developer@example.invalid'},{**profile,'id':'preview-lab','tenancy':'personal-lab','name':'개인 실습','username':'lab@example.invalid'}]
  await page.evaluate('(ps)=>chrome.storage.local.set({profiles:ps,settings:{mode:"local",fileKind:"picker",nativePath:""},appearance:{mode:"dark",accent:"#a477ff"}})',demos);await page.reload();await page.wait_for_timeout(250)
  await page.locator('#search').fill('prod');assert await page.locator('.account-row').count()==1;await page.locator('#search').fill('없는테넌시');assert '검색 결과' in await page.locator('#accounts').inner_text();await page.locator('#search').fill('');await page.locator('[data-id=preview-prod]').click();ok('tenancy search selects matching accounts and handles no results')
  await page.locator('#edit').click();await page.locator('#p-tenancy').fill('cloudragon-production');await page.locator('#account-form button[type=submit]').click();await page.wait_for_timeout(180);assert await page.locator('#detail-title').inner_text()=='cloudragon-production';ok('account editing updates the selected tenancy')
  await page.locator('#more').click();await page.locator('#delete').click();await page.locator('#delete-confirm').click();await expect(page.locator('.account-row')).to_have_count(2);ok('explicit account deletion removes only selected account')
  await page.evaluate('(ps)=>chrome.storage.local.set({profiles:ps})',demos);await page.locator('#refresh').click();await page.wait_for_timeout(150);await page.locator('[data-id=preview-prod]').click();await page.locator('#search').blur()
  for width,height in [(1200,820),(768,820),(390,844)]:
   await page.set_viewport_size({'width':width,'height':height});assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth');await page.screenshot(path=str(shots/f'vault-dark-{width}.png'),full_page=True)
  ok('vault fits desktop, tablet and 390px without horizontal overflow')
  await page.set_viewport_size({'width':1200,'height':820});await page.locator('#settings').click()
  for tab in ['appearance','storage','transfer','help']:
   await page.locator('[data-tab='+tab+']').click();await page.screenshot(path=str(shots/f'settings-{tab}.png'))
  await page.locator('[data-tab=appearance]').click();await page.locator('#theme-mode').select_option('light');await page.locator('#theme-accent').fill('#176b61');await page.locator('#theme-accent').dispatch_event('input');await page.locator('#close-settings').click();await page.screenshot(path=str(shots/'vault-light.png'))
  popup=await ctx.new_page();await popup.set_viewport_size({'width':780,'height':580});await popup.goto(f'chrome-extension://{eid}/popup.html');await popup.wait_for_timeout(200);assert await popup.locator('html').get_attribute('data-theme')=='light';ok('appearance is shared between popup and options')
  await popup.evaluate("()=>chrome.storage.local.set({appearance:{mode:'dark',accent:'#a477ff'}})");await popup.locator('[data-id=preview-prod]').click();await popup.locator('#search').blur();await popup.screenshot(path=str(shots/'popup-dark.png'));assert not await popup.evaluate('document.documentElement.scrollHeight>innerHeight');ok('actual 780x580 popup fits approved two-column layout')
  assert not errors,errors;ok('extension UI has no JavaScript or CSP console errors')
  snapshot=await page.content();snapshot=re.sub(r'<script\b[^>]*>.*?</script>','',snapshot,flags=re.S);snapshot=snapshot.replace('href="ui.css"','href="../../extension/ui.css"');(WORK/'inspect-vault.html').write_text(snapshot)
  await ctx.close();server.close();await server.wait_closed()
 report={'count':len(checks),'checks':checks,'network':'OCI hostnames mapped to loopback-only TLS fixture; no real Oracle traffic','scope':'Linux Chromium; fixture permissions pregranted; OPFS file handles; real OCI, Windows native launch and Chrome permission dialog unverified'};(WORK/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
asyncio.run(main())
