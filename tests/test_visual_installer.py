"""Real CMD/Windows PowerShell tests with disposable installation directories."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PS=str(Path(os.environ.get('WINDIR','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')
BUILD=ROOT/'dist/windows-visual-r19'


def q(p):return "'"+str(p).replace("'","''")+"'"


@unittest.skipUnless(os.name=='nt','Windows PowerShell 5.1 and CMD required')
class VisualSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)/"설치 & O'Neil [test]";self.base.mkdir()
        self.local=self.base/'local';self.root=self.local/'Cloudragon/OCICompanion'
        self.payload=(BUILD/'_support/payload.zip').read_bytes()

    def tearDown(self):self.temp.cleanup()

    def call(self,launch=False,payload=None):
        data=self.payload if payload is None else payload
        file=self.base/'payload.zip';file.write_bytes(data)
        prefix='[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);. '+q(ROOT/'windows/setup-visual/Update.Core.ps1')+';. '+q(ROOT/'windows/setup-visual/Install.Core.ps1')+';'
        if launch:prefix+='$global:Calls=@();function Start-Process{param($FilePath,$ArgumentList)$global:Calls+=@($FilePath)};'
        code=prefix+'try{$r=Install-OrUpdateOciCompanion -Payload ([IO.File]::ReadAllBytes('+q(file)+')) -ExpectedHash '+q(hashlib.sha256(data).hexdigest())+' -LocalData '+q(self.local)+('' if launch else ' -NoLaunch')+";Write-Output ('RESULT:'+(@{ok=$true;result=$r;calls=$global:Calls}|ConvertTo-Json -Depth 4 -Compress))}catch{Write-Output ('RESULT:'+(@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Compress))}"
        result=subprocess.run([PS,'-NoLogo','-NoProfile','-NonInteractive','-Command',code],capture_output=True)
        out=result.stdout.decode('utf-8',errors='replace');self.assertEqual(result.returncode,0,out+result.stderr.decode(errors='replace'))
        return json.loads(next(line[7:] for line in out.splitlines() if line.startswith('RESULT:')))

    def previous_r7(self, fixture='managed-r7-payload.zip', version='1.2.3', fresh_visual=False):
        data=(ROOT/'tests/fixtures'/fixture).read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            baseline=json.loads(z.read('payload/baseline.json'))
            for entry in z.namelist():
                if entry.startswith('payload/extension/'):
                    file=self.root/entry[8:];file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(z.read(entry))
        (self.root/'.oci-companion-setup.json').write_text(json.dumps({'payloadSha256':hashlib.sha256(data).hexdigest() if fresh_visual else baseline['setupHash']}))
        (self.root/'.oci-companion-update.json').write_text(json.dumps({'version':version,'payloadSha256':hashlib.sha256(data).hexdigest()}))

    def test_current_130_managed_r8_is_accepted_and_keeps_backup(self):
        self.previous_r7('managed-v1.3.0-r8-payload.zip','1.3.0')
        before=(self.root/'extension/worker.js').read_bytes()
        result=self.call();self.assertTrue(result['ok'],result)
        self.assertEqual((Path(result['result']['backupPath'])/'worker.js').read_bytes(),before)
        self.assertEqual((self.root/'extension/worker.js').read_bytes(),(ROOT/'extension/worker.js').read_bytes())

    def test_previous_visual_fresh_install_can_upgrade_without_reset(self):
        self.previous_r7('visual-v1.2.3-r8-payload.zip',fresh_visual=True)
        result=self.call();self.assertTrue(result['ok'],result)
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')

    def test_published_130_r9_fresh_install_upgrades_and_keeps_receipt_backup(self):
        self.previous_r7('visual-v1.3.0-r9-payload.zip','1.3.0',fresh_visual=True)
        before=(self.root/'extension/app.js').read_bytes();receipt=(self.root/'.oci-companion-update.json').read_bytes()
        result=self.call();self.assertTrue(result['ok'],result);backup=Path(result['result']['backupPath'])
        self.assertEqual((backup/'app.js').read_bytes(),before);self.assertEqual(Path(str(backup)+'.json').read_bytes(),receipt)
        self.assertEqual((self.root/'extension/app.js').read_bytes(),(ROOT/'extension/app.js').read_bytes())
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')

    def test_local_131_r9_update_is_accepted_without_resetting_files(self):
        self.previous_r7('managed-v1.3.0-r8-payload.zip','1.3.0')
        with zipfile.ZipFile(ROOT/'tests/fixtures/visual-v1.3.1-r10-payload.zip') as z:
            for entry in z.namelist():
                if entry.startswith('payload/extension/'):
                    file=self.root/entry[8:];file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(z.read(entry))
        (self.root/'.oci-companion-update.json').write_text(json.dumps({'version':'1.3.1','payloadSha256':'dd7c7d75d8e754d011f1e9c4a0390e00d47f5042dda4c32da89a6641045409aa'}))
        result=self.call();self.assertTrue(result['ok'],result)
        self.assertEqual((self.root/'extension/app.js').read_bytes(),(ROOT/'extension/app.js').read_bytes())

    def test_fresh_then_repeat_keeps_same_extension_path_and_extra_files(self):
        first=self.call();self.assertTrue(first['ok'],first)
        note=self.root/'extension/my-note.txt';note.write_text('keep')
        second=self.call();self.assertTrue(second['ok'],second)
        self.assertEqual(first['result']['extensionPath'],second['result']['extensionPath'])
        self.assertEqual(note.read_text(),'keep')
        self.assertIn('<svg',Path(second['result']['guidePath']).read_text(encoding='utf-8'))

    def test_actual_published_r7_receipt_is_accepted_and_backup_is_kept(self):
        self.previous_r7();before=(self.root/'extension/worker.js').read_bytes()
        old=(self.root/'.oci-companion-update.json').read_bytes()
        result=self.call();self.assertTrue(result['ok'],result)
        self.assertEqual((self.root/'extension/worker.js').read_bytes(),(ROOT/'extension/worker.js').read_bytes())
        backup=Path(result['result']['backupPath'])
        self.assertEqual((backup/'worker.js').read_bytes(),before)
        self.assertEqual(Path(str(backup)+'.json').read_bytes(),old)

    def test_modified_r7_is_preserved(self):
        self.previous_r7();file=self.root/'extension/worker.js';file.write_text('// mine')
        self.assertFalse(self.call()['ok']);self.assertEqual(file.read_text(),'// mine')

    def test_actual_cmd_upgrades_published_131_r10(self):
        self.previous_r7('visual-v1.3.1-r10-payload.zip','1.3.1',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_132_r11(self):
        self.previous_r7('visual-v1.3.2-r11-payload.zip','1.3.2',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_133_r12(self):
        self.previous_r7('visual-v1.3.3-r12-payload.zip','1.3.3',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_134_r13(self):
        self.previous_r7('visual-v1.3.4-r13-payload.zip','1.3.4',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_135_r14(self):
        self.previous_r7('visual-v1.3.5-r14-payload.zip','1.3.5',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_136_r15(self):
        self.previous_r7('visual-v1.3.6-r15-payload.zip','1.3.6',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_137_r16(self):
        self.previous_r7('visual-v1.3.7-r16-payload.zip','1.3.7',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_138_r17(self):
        self.previous_r7('visual-v1.3.8-r17-payload.zip','1.3.8',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_actual_cmd_upgrades_published_139_r18(self):
        self.previous_r7('visual-v1.3.9-r18-payload.zip','1.3.9',fresh_visual=True)
        before=(self.root/'.oci-companion-update.json').read_bytes()
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')
        receipt=json.loads((self.root/'.oci-companion-update.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(receipt['backupPath']+'.json').read_bytes(),before)

    def test_modified_public_r9_installation_is_preserved(self):
        self.previous_r7('visual-v1.3.0-r9-payload.zip','1.3.0',fresh_visual=True)
        file=self.root/'extension/app.js';file.write_text('// preserve user changes')
        receipt=(self.root/'.oci-companion-update.json').read_bytes()
        self.assertFalse(self.call()['ok']);self.assertEqual(file.read_text(),'// preserve user changes')
        self.assertEqual((self.root/'.oci-companion-update.json').read_bytes(),receipt)

    def test_real_cmd_updates_public_r9_without_ui(self):
        self.previous_r7('visual-v1.3.0-r9-payload.zip','1.3.0',fresh_visual=True)
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual((self.root/'extension/app.js').read_bytes(),(ROOT/'extension/app.js').read_bytes())
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')

    def test_launch_opens_only_guide_without_explorer(self):
        result=self.call(launch=True);self.assertTrue(result['ok'],result)
        self.assertEqual(result['calls'],[result['result']['guidePath']])
        self.assertFalse(result['result']['explorerLaunchRequested'])
        self.assertTrue(result['result']['guideLaunchRequested'])

    def test_unowned_folder_and_unsafe_zip_are_preserved(self):
        self.root.mkdir(parents=True);note=self.root/'mine';note.write_text('keep')
        self.assertFalse(self.call()['ok']);self.assertEqual(note.read_text(),'keep')
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('payload/../../escape.txt','bad')
        self.assertFalse(self.call(payload=buf.getvalue())['ok'])

    def test_real_cmd_installs_from_unicode_ampersand_path_without_ui(self):
        file=self.base/'Install.cmd';file.write_bytes((BUILD/'Install.cmd').read_bytes())
        env={**os.environ,'CLOUDRAGON_SETUP_LOCAL_DATA':str(self.local),'CLOUDRAGON_SETUP_NO_LAUNCH':'1','CLOUDRAGON_SETUP_NO_PAUSE':'1'}
        command='"'+str(Path(os.environ['WINDIR'])/'System32/cmd.exe')+'" /d /s /c ""'+str(file)+'""'
        result=subprocess.run(command,env=env,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text(encoding='utf-8'))['version'],'2.0.0')


if __name__=='__main__':unittest.main()
