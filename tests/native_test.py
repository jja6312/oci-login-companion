"""Protocol tests use fixture-only files and PowerShell 7 on Linux, not Windows registry."""
import json, struct, subprocess, tempfile, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PWSH='/home/codex/workspaces/tools/powershell-7.5.4/runtime/pwsh'
ORIGIN='chrome-extension://'+'a'*32+'/'
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        self.base=pathlib.Path(self.tmp.name)
        self.file=self.base/'team.json'
        self.file.write_text('{"schemaVersion":1,"profiles":[],"note":"한국어"}',encoding='utf8')
        self.policy=self.base/'allowed.json'
        self.policy.write_text(json.dumps({'origin':ORIGIN,'path':str(self.file)}))
    def tearDown(self): self.tmp.cleanup()
    def call(self,request,origin=ORIGIN,prefix=None):
        data=json.dumps(request).encode()
        p=subprocess.run([PWSH,'-NoLogo','-NoProfile','-NonInteractive','-File',str(ROOT/'windows/Host.ps1'),'-Origin',origin,'-ConfigFile',str(self.policy)],input=(prefix or struct.pack('<I',len(data)))+data,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr.decode())
        self.assertGreaterEqual(len(p.stdout),4)
        size=struct.unpack('<I',p.stdout[:4])[0]
        self.assertEqual(len(p.stdout)-4,size)
        return json.loads(p.stdout[4:])
    def test_read_unicode(self): self.assertIn('한국어',self.call({'action':'read','path':str(self.file)})['text'])
    def test_other_origin(self): self.assertEqual(self.call({'action':'read','path':str(self.file)},'chrome-extension://'+'b'*32+'/')['error'],'ORIGIN_DENIED')
    def test_other_path(self): self.assertEqual(self.call({'action':'read','path':str(self.base/'other.json')})['error'],'PATH_DENIED')
    def test_write_denied(self): self.assertEqual(self.call({'action':'write','path':str(self.file)})['error'],'READ_ONLY')
    def test_missing_file(self): self.file.unlink();self.assertFalse(self.call({'action':'read','path':str(self.file)})['ok'])
    def test_oversize_file(self): self.file.write_bytes(b' '*524289);self.assertFalse(self.call({'action':'read','path':str(self.file)})['ok'])
    def test_oversize_message(self): self.assertEqual(self.call({},prefix=struct.pack('<I',32769))['error'],'REQUEST_TOO_LARGE')
if __name__=='__main__': unittest.main(verbosity=2)
