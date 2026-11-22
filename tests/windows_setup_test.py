"""Installer-core checks in PowerShell 7/Linux. Windows shell launch is mocked.
No claim of real CMD/Windows PowerShell 5.1/Chrome registration is made.
"""
import base64,hashlib,io,json,os,pathlib,subprocess,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];PWSH='/home/codex/workspaces/tools/powershell-7.5.4/runtime/pwsh';BUILD=ROOT/'dist/windows-setup-r2';WORK=ROOT/'work/windows-setup-20261122-r2';CORE=ROOT/'windows/setup/Setup.Core.ps1'
def quote(s):return "'"+str(s).replace("'","''")+"'"
def digest(b):return hashlib.sha256(b).hexdigest()
def archive(entries):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in entries.items():z.writestr(name,value)
 return b.getvalue()
def minimal(extra=None):
 e={'payload/extension/manifest.json':json.dumps({'manifest_version':3,'name':'OCI Login Companion','version':'1.1.0'}),'payload/Install-Guide.template.html':'<textarea>{{EXTENSION_PATH}}</textarea>','payload/extension/test.js':'// fixture only'}
 e.update(extra or {});return archive(e)
class SetupTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  WORK.mkdir(parents=True,exist_ok=True)
  subprocess.run(['python3','scripts/build_windows_setup.py'],cwd=ROOT,check=True,capture_output=True)
  cls.actual=(BUILD/'setup-payload.zip').read_bytes();cls.expected=digest(cls.actual)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=WORK);self.base=pathlib.Path(self.tmp.name);self.local=self.base/"한국어 팀 & O'Neil [ops]";self.payload=self.base/'payload.zip';self.payload.write_bytes(self.actual)
 def tearDown(self):self.tmp.cleanup()
 def run_ps(self,script,extra_env=None):
  r=subprocess.run([PWSH,'-NoLogo','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,env={**os.environ,**(extra_env or {})},timeout=35)
  self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr);return r.stdout
 def install(self,data=None,expected=None,launch=False,extra=''):
  data=self.actual if data is None else data;self.payload.write_bytes(data);h=expected or digest(data)
  s='. '+quote(CORE)+'; '+extra+'; try {$r=Install-OciCompanion -Payload ([IO.File]::ReadAllBytes('+quote(self.payload)+')) -ExpectedHash '+quote(h)+' -LocalData '+quote(self.local)+('' if launch else ' -NoLaunch')+"; Write-Output ('OCI_RESULT:'+(@{ok=$true;result=$r;calls=$global:Calls;clip=$global:Clip}|ConvertTo-Json -Depth 6 -Compress));} catch {Write-Output ('OCI_RESULT:'+(@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Compress));}"
  out=self.run_ps(s);return json.loads(next(x[11:] for x in out.splitlines() if x.startswith('OCI_RESULT:')))
 @property
 def target(self):return self.local/'Cloudragon/OCICompanion'
 def test_parse_literal_powershell(self):
  cmd=next(BUILD.glob('*.cmd')).read_text();line=next(x for x in cmd.splitlines() if ' -Command \"' in x);code=line.split(' -Command "',1)[1][:-1];self.assertLess(len(line),7900)
  ps="$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseInput("+quote(code)+",[ref]$t,[ref]$e)|Out-Null;if($e.Count){$e|ForEach-Object{Write-Error $_};exit 1;}"
  self.run_ps(ps)
 def test_cmd_embedded_payload_matches_reviewed_zip(self):
  cmd=next(BUILD.glob('*.cmd')).read_bytes();b=base64.b64decode(cmd.rsplit(b'::OCI_PAYLOAD_BEGIN',1)[1]);self.assertEqual(b,self.actual)
  report=json.loads((BUILD/'build-report.json').read_text());self.assertEqual(digest(cmd),report['cmdSha256']);self.assertNotIn(b'Invoke-Expression',cmd);self.assertNotIn(b'-EncodedCommand',cmd);self.assertNotIn(b'-ExecutionPolicy',cmd);self.assertIn(b'DisableDelayedExpansion',cmd)
 def test_fresh_install_full_payload_unicode_path(self):
  r=self.install();self.assertTrue(r['ok'],r);self.assertEqual(r['result']['state'],'FILES_READY_USER_REGISTRATION_REQUIRED');self.assertFalse(r['result']['chromeLaunchRequested']);self.assertTrue((self.target/'extension/worker.js').exists());self.assertTrue((self.target/'windows/Host.ps1').exists());self.assertFalse(list((self.local/'Cloudragon').glob('.oci-setup-*')))
 def test_repeat_identical_install_keeps_extra_user_file(self):
  self.assertTrue(self.install()['ok']);f=self.target/'my-note.txt';f.write_text('keep me');before=(self.target/'.oci-companion-setup.json').read_bytes();self.assertTrue(self.install()['ok']);self.assertEqual(f.read_text(),'keep me');self.assertEqual(before,(self.target/'.oci-companion-setup.json').read_bytes())
 def test_checksum_mismatch_creates_no_local_directory(self):
  r=self.install(b'changed',expected=self.expected);self.assertFalse(r['ok']);self.assertIn('checksum',r['error']);self.assertFalse(self.local.exists())
 def test_unowned_target_preserved(self):
  self.target.mkdir(parents=True);f=self.target/'original.txt';f.write_text('keep');r=self.install();self.assertFalse(r['ok']);self.assertEqual(f.read_text(),'keep');self.assertFalse((self.target/'extension').exists())
 def test_changed_extension_preserved(self):
  self.assertTrue(self.install()['ok']);f=self.target/'extension/worker.js';f.write_text('// locally changed');r=self.install();self.assertFalse(r['ok']);self.assertEqual(f.read_text(),'// locally changed')
 def test_different_owned_version_preserved(self):
  self.assertTrue(self.install()['ok']);p=self.target/'.oci-companion-setup.json';d=json.loads(p.read_text());d['payloadSha256']='0'*64;p.write_text(json.dumps(d));r=self.install();self.assertFalse(r['ok']);self.assertIn('Different installation',r['error']);self.assertEqual(json.loads(p.read_text())['payloadSha256'],'0'*64)
 def test_changed_guide_preserved(self):
  self.assertTrue(self.install()['ok']);p=self.target/'Install-Guide.html';p.write_text('my guide');r=self.install();self.assertFalse(r['ok']);self.assertEqual(p.read_text(),'my guide')
 def test_zip_traversal_rejected_before_install(self):
  for n in ['payload/../../escape.txt','/absolute.txt','payload/extension/C:evil','payload/extension/../evil','payload\\extension\\evil']:
   with self.subTest(n=n):r=self.install(minimal({n:'bad'}));self.assertFalse(r['ok']);self.assertFalse(self.target.exists())
 def test_zip_symlink_rejected(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   i=zipfile.ZipInfo('payload/link');i.create_system=3;i.external_attr=0o120777<<16;z.writestr(i,'outside')
  r=self.install(b.getvalue());self.assertFalse(r['ok']);self.assertIn('Unsafe',r['error'])
 def test_wrong_manifest_cleans_staging(self):
  r=self.install(minimal({'payload/extension/manifest.json':json.dumps({'manifest_version':3,'name':'Other','version':'9'})}));self.assertFalse(r['ok']);self.assertFalse(self.target.exists());self.assertFalse(list((self.local/'Cloudragon').glob('.oci-setup-*')))
 def test_oversized_zip_rejected_before_install(self):
  r=self.install(minimal({'payload/too-large':'a'*8388609}));self.assertFalse(r['ok']);self.assertFalse(self.local.exists())
 def test_case_duplicate_zip_rejected(self):
  r=self.install(minimal({'payload/EXTENSION/TEST.JS':'duplicate'}));self.assertFalse(r['ok']);self.assertIn('Duplicate',r['error'])
 def test_root_junction_or_symlink_preserved(self):
  outside=self.base/'outside';outside.mkdir();(self.local/'Cloudragon').parent.mkdir(parents=True);(self.local/'Cloudragon').symlink_to(outside,target_is_directory=True);r=self.install();self.assertFalse(r['ok']);self.assertEqual(list(outside.iterdir()),[])
 def test_html_path_escaped_without_changing_actual_folder(self):
  r=self.install();self.assertTrue(r['ok'],r);s=(self.target/'Install-Guide.html').read_text();self.assertNotIn('{{EXTENSION_PATH}}',s);self.assertIn('&amp;',s);self.assertIn('&#39;',s);self.assertTrue((self.target/'extension/manifest.json').is_file())
 def mock_launch(self,chrome=True):
  win=self.base/'Windows';win.mkdir();(win/'explorer.exe').write_bytes(b'')
  if chrome:
   p=self.local/'Google/Chrome/Application';p.mkdir(parents=True);(p/'chrome.exe').write_bytes(b'')
  return "$env:OS='Windows_NT';$env:WINDIR="+quote(win)+";$global:Calls=[Collections.Generic.List[object]]::new();function Start-Process {param($FilePath,$ArgumentList);$global:Calls.Add(@{file=$FilePath;args=@($ArgumentList)});};function Set-Clipboard {param($Value);$global:Clip=$Value;}"
 def test_mocked_windows_launch_opens_normal_chrome_and_explorer(self):
  r=self.install(launch=True,extra=self.mock_launch());self.assertTrue(r['ok'],r);self.assertTrue(r['result']['chromeLaunchRequested']);self.assertTrue(r['result']['explorerLaunchRequested']);self.assertEqual(r['clip'],str(self.target/'extension'));chrome=next(x for x in r['calls'] if x['file'].endswith('chrome.exe'));self.assertIn('chrome://extensions/',chrome['args']);self.assertTrue(chrome['args'][0].startswith('file:///'));self.assertNotIn('--load-extension',' '.join(chrome['args']))
 def test_missing_chrome_never_falls_back_to_another_browser(self):
  r=self.install(launch=True,extra=self.mock_launch(chrome=False));self.assertTrue(r['ok'],r);self.assertFalse(r['result']['chromeLaunchRequested']);self.assertEqual(len(r['calls']),1);self.assertTrue(r['calls'][0]['file'].endswith('explorer.exe'))
 def test_literal_cmd_bootstrap_extracts_own_payload(self):
  cmd=next(BUILD.glob('*.cmd'));self_file=self.base/"설치 & O'Neil [r1].cmd";self_file.write_bytes(cmd.read_bytes());line=next(x for x in cmd.read_text().splitlines() if ' -Command \"' in x);code=line.split(' -Command "',1)[1][:-1]
  prefix="$env:OS='Windows_NT';$env:LOCALAPPDATA="+quote(self.local)+";$env:WINDIR="+quote(self.base/'missing-windir')+";$env:ProgramFiles='';${env:ProgramFiles(x86)}='';$env:OCI_COMPANION_SETUP_SELF="+quote(self_file)+";function Set-Clipboard {param($Value);}; "
  out=self.run_ps(prefix+code);self.assertIn('FILES_READY_USER_REGISTRATION_REQUIRED',out);self.assertTrue((self.target/'extension/manifest.json').exists())
 def cold_loader(self):
  return "$global:OciCompressionLoaded=$false;function Add-Type {param([string]$AssemblyName);if($AssemblyName -eq 'System.IO.Compression.FileSystem' -and -not $global:OciCompressionLoaded){throw 'Modeled cold .NET Framework: System.IO.Compression.ZipArchive type unavailable';};Microsoft.PowerShell.Utility\\Add-Type -AssemblyName $AssemblyName;if($AssemblyName -eq 'System.IO.Compression'){$global:OciCompressionLoaded=$true;};}"
 def test_modeled_net_framework_old_loader_fails_before_file_changes(self):
  core=CORE.read_text();new="    Add-Type -AssemblyName System.IO.Compression;\n    Add-Type -AssemblyName System.IO.Compression.FileSystem;";self.assertIn(new,core);old=core.replace(new,'    Add-Type -AssemblyName System.IO.Compression.FileSystem;');copy=self.base/'old-loader.ps1';copy.write_text(old)
  r=self.install(extra='. '+quote(copy)+'; '+self.cold_loader());self.assertFalse(r['ok']);self.assertIn('ZipArchive type unavailable',r['error']);self.assertFalse(self.local.exists())
 def test_modeled_net_framework_explicit_loader_extracts_actual_package(self):
  r=self.install(extra=self.cold_loader());self.assertTrue(r['ok'],r);self.assertTrue((self.target/'extension/worker.js').is_file());self.assertTrue((self.target/'Install-Guide.html').is_file())
 def test_cmd_failure_footer_does_not_claim_completion(self):
  s=next(BUILD.glob('*.cmd')).read_text();self.assertIn('OCI Companion Windows Setup r2 - offline, current user',s);self.assertIn('if not "%OCI_COMPANION_SETUP_EXIT%"=="0" (',s);self.assertIn('Setup did not complete. No Chrome registration was performed.',s);self.assertNotIn('Chrome registration is completed by you',s)
 def test_release_extension_bytes_unchanged(self):
  report=json.loads((BUILD/'build-report.json').read_text());self.assertEqual(digest((ROOT/'dist/OCI-Login-Companion-v1.1.0.zip').read_bytes()),report['releaseInputSha256'])
  with zipfile.ZipFile(io.BytesIO(self.actual)) as p,zipfile.ZipFile(ROOT/'dist/OCI-Login-Companion-v1.1.0-webstore.zip') as z:
   for n in z.namelist():self.assertEqual(z.read(n),p.read('payload/extension/'+n))
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(SetupTests);r=unittest.TextTestRunner(verbosity=2).run(suite);(WORK/'test-report.json').write_text(json.dumps({'tests':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors),'failures':len(r.failures),'errors':len(r.errors),'scope':'PowerShell 7/Linux installer core and literal CMD PowerShell command; Windows native launches mocked; cold .NET Framework dependency behavior modeled; real CMD/PS5.1/Chrome registration not executed'},indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
