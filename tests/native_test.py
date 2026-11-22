"""Protocol tests use fixture-only files and PowerShell 7 on Linux, not Windows registry."""
import json, struct, subprocess, tempfile, pathlib, unittest,hashlib
from concurrent.futures import ThreadPoolExecutor
ROOT=pathlib.Path(__file__).resolve().parents[1]
PWSH='/home/codex/workspaces/tools/powershell-7.5.4/runtime/pwsh'
ORIGIN='chrome-extension://'+'a'*32+'/'
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        self.base=pathlib.Path(self.tmp.name)
        self.file=self.base/'팀 파일 & 회사 [1].json'
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
    def test_oversize_message(self): self.assertEqual(self.call({},prefix=struct.pack('<I',2097153))['error'],'REQUEST_TOO_LARGE')
    def writable(self):self.policy.write_text(json.dumps({'origin':ORIGIN,'path':str(self.file),'allowWrite':True}))
    def request(self,password=' changed password ',**extra):
        profile={'id':'fixture','name':'가상 팀','tenancy':'fixture-team','username':'operator@example.invalid','password':password,'bypassCode':'000123'}
        return {'action':'write','path':str(self.file),'expectedHash':hashlib.sha256(self.file.read_bytes()).hexdigest(),'text':json.dumps({'schemaVersion':1,'profiles':[profile]},ensure_ascii=False),**extra}
    def test_read_reports_exact_hash_and_readonly_capability(self):
        r=self.call({'action':'read','path':str(self.file)});self.assertEqual(r['sha256'],hashlib.sha256(self.file.read_bytes()).hexdigest());self.assertFalse(r['canWrite']);self.assertEqual(r['protocolVersion'],2)
    def test_opt_in_write_preserves_password_whitespace_unicode_and_zero_code(self):
        self.writable();q=self.request();r=self.call(q);self.assertTrue(r['ok'],r);self.assertEqual(self.file.read_text(),q['text']);self.assertEqual(r['sha256'],hashlib.sha256(self.file.read_bytes()).hexdigest());self.assertFalse(list(self.base.glob('*.tmp')))
    def test_stale_hash_preserves_external_change(self):
        self.writable();q=self.request();self.file.write_text('{"schemaVersion":1,"profiles":[],"note":"external change"}');before=self.file.read_bytes();self.assertEqual(self.call(q)['error'],'CONFLICT');self.assertEqual(self.file.read_bytes(),before);self.assertFalse(list(self.base.glob('*.tmp')))
    def test_write_still_checks_origin_and_exact_path(self):
        self.writable();q=self.request();before=self.file.read_bytes();self.assertEqual(self.call(q,'chrome-extension://'+'b'*32+'/')['error'],'ORIGIN_DENIED');q['path']=str(self.base/'other.json');self.assertEqual(self.call(q)['error'],'PATH_DENIED');self.assertEqual(self.file.read_bytes(),before);self.assertFalse((self.base/'other.json').exists())
    def test_write_requires_matching_hash(self):
        self.writable();q=self.request(expectedHash='');before=self.file.read_bytes();self.assertFalse(self.call(q)['ok']);self.assertEqual(self.file.read_bytes(),before)
    def test_invalid_json_never_replaces_file(self):
        self.writable();q=self.request(text='invalid JSON');before=self.file.read_bytes();self.assertFalse(self.call(q)['ok']);self.assertEqual(self.file.read_bytes(),before)
    def test_invalid_code_type_never_replaces_file(self):
        self.writable();q=self.request();v=json.loads(q['text']);v['profiles'][0]['bypassCode']=123;q['text']=json.dumps(v);before=self.file.read_bytes();self.assertFalse(self.call(q)['ok']);self.assertEqual(self.file.read_bytes(),before)
    def test_oversize_write_never_replaces_file(self):
        self.writable();q=self.request(text=' '*524289);before=self.file.read_bytes();self.assertFalse(self.call(q)['ok']);self.assertEqual(self.file.read_bytes(),before)
    def test_reads_replacement_at_same_path(self):
        self.call({'action':'read','path':str(self.file)});other=self.base/'replacement.json';other.write_text('{"schemaVersion":1,"profiles":[]}');other.replace(self.file);r=self.call({'action':'read','path':str(self.file)});self.assertEqual(r['text'],self.file.read_text());self.assertEqual(r['sha256'],hashlib.sha256(self.file.read_bytes()).hexdigest())
    def test_two_same_machine_writers_do_not_overwrite_a_new_revision(self):
        self.writable();qs=[self.request('writer one'),self.request('writer two')]
        with ThreadPoolExecutor(max_workers=2) as pool:rs=list(pool.map(self.call,qs))
        self.assertEqual(sum(r['ok'] for r in rs),1,rs);self.assertEqual(next(r['error'] for r in rs if not r['ok']),'CONFLICT');self.assertEqual(self.file.read_text(),qs[next(i for i,r in enumerate(rs) if r['ok'])]['text'])
if __name__=='__main__': unittest.main(verbosity=2)
