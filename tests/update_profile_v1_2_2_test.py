"""Actual persistent Chromium data survives installer-managed path-preserving update."""
import asyncio,json,pathlib,subprocess,tempfile,hashlib
from playwright.async_api import async_playwright,expect
R=pathlib.Path(__file__).resolve().parents[1];W=R/'work/v1.2.2';PS='/home/codex/workspaces/tools/powershell-7.5.4/runtime/pwsh'
def q(s):return "'"+str(s).replace("'","''")+"'"
def run(s):
 p=subprocess.run([PS,'-NoLogo','-NoProfile','-NonInteractive','-Command',s],capture_output=True,text=True,timeout=35);assert p.returncode==0,p.stdout+p.stderr
async def main():
 with tempfile.TemporaryDirectory(dir=W) as temp:
  b=pathlib.Path(temp);local=b/'local-app-data';ext=local/'Cloudragon/OCICompanion/extension';old=R/'dist/windows-setup-r2/setup-payload.zip';new=R/'dist/windows-update-r6/update-payload.zip'
  run('. '+q(R/'windows/setup/Setup.Core.ps1')+';Install-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(old)+')) -ExpectedHash '+q(hashlib.sha256(old.read_bytes()).hexdigest())+' -LocalData '+q(local)+' -NoLaunch|Out-Null;')
  prior=R/'dist/windows-update-r5/update-payload.zip'
  run('. '+q(R/'windows/update-v1.2.1/Update.Core.ps1')+';Update-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(prior)+')) -ExpectedHash '+q(hashlib.sha256(prior.read_bytes()).hexdigest())+' -LocalData '+q(local)+' -NoLaunch|Out-Null;')
  fixture={'profiles':[{'id':'persist-fixture','tenancy':'fixture-tenant','name':'가상 계정','username':'fixture@example.invalid','password':'fixture-unchanged','bypassCode':'000123'}],'appearance':{'mode':'light','accent':'#176b61'},'settings':{'mode':'file','fileKind':'picker','nativePath':''}}
  async with async_playwright() as p:
   async def launch():
    c=await p.chromium.launch_persistent_context(str(b/'browser-profile'),executable_path='/home/codex/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome',headless=True,args=['--no-sandbox','--disable-extensions-except='+str(ext),'--load-extension='+str(ext)]);w=c.service_workers[0] if c.service_workers else await c.wait_for_event('serviceworker');return c,w.url.split('/')[2]
   c,first=await launch();a=await c.new_page();await a.goto('chrome-extension://'+first+'/options.html');await a.evaluate('(f)=>chrome.storage.local.set(f)',fixture);await a.evaluate('''async(p)=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('fixture-team.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:p}));await w.close();await(await import('./lib/db.js')).handleSet(h);}''',fixture['profiles']);await c.close()
   run('. '+q(R/'windows/update-v1.2.2/Update.Core.ps1')+';Update-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(new)+')) -ExpectedHash '+q(hashlib.sha256(new.read_bytes()).hexdigest())+' -LocalData '+q(local)+' -NoLaunch|Out-Null;')
   c,second=await launch();assert second==first;a=await c.new_page();await a.goto('chrome-extension://'+second+'/options.html');await expect(a.locator('.account-row')).to_have_count(1);stored=await a.evaluate('()=>chrome.storage.local.get(["profiles","appearance","settings"])');assert stored==fixture;assert await a.evaluate("async()=> (await (await import('./lib/sources.js')).readSource()).profiles[0].password")==fixture['profiles'][0]['password'];assert await a.evaluate('chrome.runtime.getManifest().version')=='1.2.2';assert await a.locator('html').get_attribute('data-theme')=='light';assert await a.locator('#quick-presets .swatch').count()==6;assert await a.locator('#detail-subtitle').inner_text()=='가상 계정 · Default';await c.close()
 (W/'profile-update-report.json').write_text(json.dumps({'checks':['extension ID unchanged at same path after managed update','all fictional account values, theme and source settings retained','new manifest1.2.2 and stored light theme render after update','persisted team FileSystemFileHandle still reads the same fictional source'],'count':4,'scope':'Disposable persistent Linux Chromium plus actual PS7 file transaction; not user PC/Windows native reload'},indent=2)+'\n');print('PASS unchanged extension ID, account/source/theme storage and new version after path-preserving update')
asyncio.run(main())
