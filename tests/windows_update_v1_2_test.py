"""Update transaction tests in PS7/Linux, not native Windows execution."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];W=ROOT/'work/v1.2.0';B=ROOT/'dist/windows-update-r4';PS='/home/codex/workspaces/tools/powershell-7.5.4/runtime/pwsh';OLD=ROOT/'dist/windows-setup-r2/setup-payload.zip';CORE=ROOT/'windows/update-v1.2.0/Update.Core.ps1'
def q(s):return "'"+str(s).replace("'","''")+"'"
def sha(b):return hashlib.sha256(b).hexdigest()
class UpdateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  subprocess.run(['python3','scripts/build_windows_update_v1_2.py'],cwd=ROOT,check=True,capture_output=True);cls.payload=(B/'update-payload.zip').read_bytes()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=W);self.base=pathlib.Path(self.tmp.name);self.local=self.base/"업데이트 & O'Neil [1]";self.root=self.local/'Cloudragon/OCICompanion';self.p=self.base/'payload.zip';self.p.write_bytes(self.payload)
 def tearDown(self):self.tmp.cleanup()
 def ps(self,s):
  p=subprocess.run([PS,'-NoLogo','-NoProfile','-NonInteractive','-Command',s],capture_output=True,text=True,timeout=35);self.assertEqual(p.returncode,0,p.stdout+p.stderr);return p.stdout
 def old(self):
  self.ps('. '+q(ROOT/'windows/setup/Setup.Core.ps1')+';Install-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(OLD)+')) -ExpectedHash '+q(sha(OLD.read_bytes()))+' -LocalData '+q(self.local)+' -NoLaunch|Out-Null;')
 def update(self,extra='',data=None,expected=None):
  if data is not None:self.p.write_bytes(data)
  code='. '+q(CORE)+';'+extra+';try{$r=Update-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(self.p)+')) -ExpectedHash '+q(expected or sha(self.p.read_bytes()))+' -LocalData '+q(self.local)+" -NoLaunch;Write-Output ('RESULT:'+(@{ok=$true;result=$r}|ConvertTo-Json -Compress));}catch{Write-Output ('RESULT:'+(@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Compress));}"
  out=self.ps(code);return json.loads(next(x[7:] for x in out.splitlines() if x.startswith('RESULT:')))
 def test_update_keeps_path_and_exact_previous_backup(self):
  self.old();before=(self.root/'extension/worker.js').read_bytes();r=self.update();self.assertTrue(r['ok'],r);self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text())['version'],'1.2.0');self.assertEqual((pathlib.Path(r['result']['backupPath'])/'worker.js').read_bytes(),before);self.assertEqual(r['result']['extensionPath'],str(self.root/'extension'))
 def test_extra_files_preserved_in_same_path_and_backup(self):
  self.old();p=self.root/'extension/my-config.json';p.write_text('{"fixture":"preserve"}');r=self.update();self.assertTrue(r['ok'],r);self.assertEqual(p.read_text(),'{"fixture":"preserve"}');self.assertEqual((pathlib.Path(r['result']['backupPath'])/'my-config.json').read_text(),p.read_text())
 def test_modified_managed_file_stops_without_swapping(self):
  self.old();p=self.root/'extension/worker.js';p.write_text('// modified');r=self.update();self.assertFalse(r['ok']);self.assertEqual(p.read_text(),'// modified');self.assertFalse(list(self.root.glob('extension-backup-*')))
 def test_unknown_installation_preserved(self):
  (self.root/'extension').mkdir(parents=True);p=self.root/'extension/manifest.json';p.write_text('keep');r=self.update();self.assertFalse(r['ok']);self.assertEqual(p.read_text(),'keep')
 def test_no_installation_does_not_create_one_in_new_path(self):
  r=self.update();self.assertFalse(r['ok']);self.assertFalse(self.local.exists())
 def test_tampered_payload_fails_before_mutation(self):
  self.old();before=(self.root/'extension/worker.js').read_bytes();r=self.update(data=b'bad',expected=sha(self.payload));self.assertFalse(r['ok']);self.assertEqual((self.root/'extension/worker.js').read_bytes(),before)
 def test_second_run_reuses_current_update_without_another_backup(self):
  self.old();self.assertTrue(self.update()['ok']);r=self.update();self.assertTrue(r['ok'],r);self.assertEqual(len(list(self.root.glob('extension-backup-*'))),1);self.assertIsNone(r['result']['backupPath'])
 def test_modified_current_update_is_not_overwritten(self):
  self.old();self.assertTrue(self.update()['ok']);p=self.root/'extension/worker.js';p.write_text('// changed update');self.assertFalse(self.update()['ok']);self.assertEqual(p.read_text(),'// changed update')
 def test_file_swap_failure_rolls_back_original(self):
  self.old();before=(self.root/'extension/worker.js').read_bytes();(self.root/'.oci-companion-update.json').mkdir();r=self.update();self.assertFalse(r['ok']);self.assertEqual((self.root/'extension/worker.js').read_bytes(),before);self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text())['version'],'1.1.0')
 def test_symlink_extra_is_not_followed_or_changed(self):
  self.old();outside=self.base/'outside.txt';outside.write_text('keep');(self.root/'extension/link.txt').symlink_to(outside);r=self.update();self.assertFalse(r['ok']);self.assertEqual(outside.read_text(),'keep');self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text())['version'],'1.1.0')
 def test_user_guide_file_in_root_preserved(self):
  self.old();p=self.root/'Update-Guide.html';p.write_text('user guide');r=self.update();self.assertTrue(r['ok'],r);self.assertEqual(p.read_text(),'user guide');self.assertNotEqual(r['result']['guidePath'],str(p))
 def test_literal_minified_cmd_bootstrap_updates_full_package(self):
  self.old();cmd=next(B.glob('*.cmd'));copy=self.base/"업데이트 & O'Neil.cmd";copy.write_bytes(cmd.read_bytes());line=next(x for x in cmd.read_text().splitlines() if ' -Command "' in x);self.assertLess(len(line),7900);code=line.split(' -Command "',1)[1][:-1]
  prefix="$env:OS='Windows_NT';$env:LOCALAPPDATA="+q(self.local)+";$env:WINDIR="+q(self.base)+";$env:OCI_COMPANION_UPDATE_SELF="+q(copy)+";function Start-Process {param($FilePath,$ArgumentList);};"
  out=self.ps(prefix+code);self.assertIn('UPDATED_RELOAD_EXISTING_EXTENSION',out);self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text())['version'],'1.2.0')
 def test_embedded_zip_and_all_new_files_match_release(self):
  cmd=next(B.glob('*.cmd')).read_bytes();self.assertEqual(base64.b64decode(cmd.rsplit(b'::OCI_UPDATE_PAYLOAD',1)[1]),self.payload)
  with zipfile.ZipFile(B/'update-payload.zip') as u,zipfile.ZipFile(ROOT/'dist/OCI-Login-Companion-v1.2.0-webstore.zip') as z:
   for n in z.namelist():self.assertEqual(z.read(n),u.read('payload/extension/'+n))
 def previous_update(self):
  p=ROOT/'dist/windows-update-r3/update-payload.zip'
  self.ps('. '+q(ROOT/'windows/update/Update.Core.ps1')+';Update-OciCompanion -Payload ([IO.File]::ReadAllBytes('+q(p)+')) -ExpectedHash '+q(sha(p.read_bytes()))+' -LocalData '+q(self.local)+' -NoLaunch|Out-Null;')
 def test_upgrade_from_r3_keeps_previous_receipt_and_backup(self):
  self.old();self.previous_update();receipt=(self.root/'.oci-companion-update.json').read_bytes();before=(self.root/'extension/worker.js').read_bytes();r=self.update();self.assertTrue(r['ok'],r);backup=pathlib.Path(r['result']['backupPath']);self.assertEqual((backup/'worker.js').read_bytes(),before);self.assertEqual(pathlib.Path(str(backup)+'.json').read_bytes(),receipt);self.assertEqual(json.loads((self.root/'extension/manifest.json').read_text())['version'],'1.2.0')
 def test_upgrade_from_r3_rolls_back_old_receipt_and_extension_on_late_failure(self):
  self.old();self.previous_update();receipt=(self.root/'.oci-companion-update.json').read_bytes();before=(self.root/'extension/worker.js').read_bytes()
  # Force new receipt move to fail after old receipt was preserved and folder swapped.
  global CORE
  code=CORE.read_text().replace('[IO.File]::Move($receipt,$rp);',"throw 'forced receipt failure';")
  mock=self.base/'forced.ps1';mock.write_text(code);original=CORE;CORE=mock
  try:r=self.update()
  finally:CORE=original
  self.assertFalse(r['ok']);self.assertEqual((self.root/'extension/worker.js').read_bytes(),before);self.assertEqual((self.root/'.oci-companion-update.json').read_bytes(),receipt)
 def test_explicit_compression_loads_before_archive_use(self):
  s=CORE.read_text();self.assertLess(s.index('Add-Type -AssemblyName System.IO.Compression;'),s.index('Add-Type -AssemblyName System.IO.Compression.FileSystem;'));self.assertNotIn('-ExecutionPolicy',s);self.assertNotIn('Invoke-Expression',s)
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UpdateTests));(W/'update-report.json').write_text(json.dumps({'tests':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors),'failures':len(r.failures),'errors':len(r.errors),'scope':'PowerShell7/Linux actual file swaps/backups/rollback and literal minified CMD PowerShell; process launches mocked; Windows CMD/PS5.1 not executed'},indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
