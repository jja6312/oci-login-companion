"""Disposable Chromium storage and visual guide checks; no customer sign-in."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from playwright.async_api import async_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
PS=os.environ.get('OCI_TEST_POWERSHELL') or str(Path(os.environ.get('WINDIR','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')
CHROMIUM=os.environ.get('OCI_TEST_CHROMIUM')
def browser_options():return {'executable_path':CHROMIUM} if CHROMIUM else {'channel':'chromium'}
def q(v):return "'"+str(v).replace("'","''")+"'"


async def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='oci-profile-check-') as temporary:
        base=Path(temporary);local=base/'local';target=local/'Cloudragon/OCICompanion';ext=target/'extension'
        data=(ROOT/'tests/fixtures/visual-v1.3.2-r11-payload.zip').read_bytes()
        with zipfile.ZipFile(ROOT/'tests/fixtures/visual-v1.3.2-r11-payload.zip') as z:
            baseline=json.loads(z.read('payload/baseline.json'))
            for name in z.namelist():
                if name.startswith('payload/extension/'):
                    file=target/name[8:];file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(z.read(name))
        (target/'.oci-companion-setup.json').write_text(json.dumps({'payloadSha256':hashlib.sha256(data).hexdigest()}))
        (target/'.oci-companion-update.json').write_text(json.dumps({'version':'1.3.2','payloadSha256':hashlib.sha256(data).hexdigest()}))
        fixture={'profiles':[{'id':'demo-profile','tenancy':'example-tenant','name':'데모 계정','username':'demo@example.invalid','password':'synthetic-value','bypassCode':'000123'}],
                 'appearance':{'mode':'light','accent':'#176b61'},'settings':{'mode':'file','fileKind':'picker','nativePath':'','teamWritable':False}}
        async with async_playwright() as p:
            async def launch(profile='browser-profile'):
                context=await p.chromium.launch_persistent_context(str(base/profile),headless=True,**browser_options(),
                    args=(['--no-sandbox'] if os.name!='nt' else [])+['--disable-extensions-except='+str(ext),'--load-extension='+str(ext)])
                worker=context.service_workers[0] if context.service_workers else await context.wait_for_event('serviceworker')
                return context,worker.url.split('/')[2]
            context,first=await launch();page=await context.new_page();await page.goto('chrome-extension://'+first+'/options.html')
            await page.evaluate('(f)=>chrome.storage.local.set(f)',fixture)
            await page.evaluate("""async(p)=>{const h=await(await navigator.storage.getDirectory()).getFileHandle('demo-team.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({schemaVersion:1,profiles:p}));await w.close();await(await import('./lib/db.js')).handleSet(h);} """,fixture['profiles'])
            await context.close()
            env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
            cmd=ROOT/'dist/windows-visual-r12/Install.cmd'
            if os.name=='nt':
                command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(cmd)+'""'
                result=subprocess.run(command,env=env,capture_output=True,timeout=60)
                report['installer_execution']='Actual Windows CMD/PowerShell'
            else:
                payload=ROOT/'dist/windows-visual-r12/_support/payload.zip'
                code='. '+q(ROOT/'windows/setup-visual/Update.Core.ps1')+';. '+q(ROOT/'windows/setup-visual/Install.Core.ps1')+';Install-OrUpdateOciCompanion -Payload ([IO.File]::ReadAllBytes('+q(payload)+')) -ExpectedHash '+q(hashlib.sha256(payload.read_bytes()).hexdigest())+' -LocalData '+q(local)+' -NoLaunch|Out-Null'
                result=subprocess.run([PS,'-NoLogo','-NoProfile','-NonInteractive','-Command',code],env=env,capture_output=True,timeout=60)
                report['installer_execution']='Actual Linux PowerShell7 transaction; Windows CMD boundary separately checked by Windows CI'
            assert result.returncode==0,result.stdout.decode(errors='replace')
            context,second=await launch();assert first==second
            page=await context.new_page();await page.goto('chrome-extension://'+second+'/options.html')
            assert await page.evaluate('()=>chrome.storage.local.get(["profiles","appearance","settings"])')==fixture
            await expect(page.locator('#detail-title')).to_have_text('example-tenant')
            for _ in range(100):
                if await page.evaluate('async()=> (await chrome.storage.local.get("onboarding")).onboarding?.complete===true'):break
                await page.wait_for_timeout(50)
            else:raise AssertionError('Existing setup was not migrated')
            await expect(page.locator('#setup-dialog')).not_to_be_visible()
            report['existing_setup_skipped_and_team_editable_by_default']=True
            await expect(page.locator('#edit')).to_be_enabled()
            assert await page.evaluate("async()=> (await (await import('./lib/sources.js')).readSource()).profiles[0].username")=='demo@example.invalid'
            await context.close()
            report['same_extension_id']=True;report['accounts_theme_source_and_opfs_handle_preserved']=True
            browser=await p.chromium.launch(**browser_options(),args=(['--no-sandbox'] if os.name!='nt' else []));context=await browser.new_context(viewport={'width':1180,'height':900})
            await context.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async(t)=>{window.copiedText=t}}});")
            page=await context.new_page();await page.goto((ROOT/'dist/windows-visual-r12/_support/Guide-Preview.html').as_uri())
            await expect(page.locator('h1')).to_have_text('빨간 박스를 따라 설정하세요.')
            await page.locator('#copy-path').click();assert await page.evaluate('window.copiedText')==r'%LOCALAPPDATA%\Cloudragon\OCICompanion\extension'
            await page.locator('[data-scheme=brave]').click();await page.locator('#copy-manager').click();assert await page.evaluate('window.copiedText')=='brave://extensions'
            await page.locator('#update-mode').click();await expect(page.locator('.update-only')).to_be_visible();await expect(page.locator('.new-only').first).to_be_hidden()
            await page.locator('#new-mode').click()
            for width in (1180,768,390):
                await page.set_viewport_size({'width':width,'height':900})
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            await page.set_viewport_size({'width':1180,'height':900})
            out=ROOT/'work/guide';out.mkdir(parents=True,exist_ok=True)
            await page.screenshot(path=str(out/'guide-preview.png'),full_page=True)
            report['guide_copy_handlers_new_update_modes_and_three_viewports']=True
            report['guide_native_clipboard_changed']=False
            await browser.close()
    out=ROOT/'work/visual-validation.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':asyncio.run(main())
