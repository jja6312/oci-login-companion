"""Independent Python cryptography/Web Crypto interoperability, no customer data."""
import base64,hashlib,json,os,pathlib,subprocess,uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
R=pathlib.Path(__file__).resolve().parents[1];W=R/'work/v2.0.0/crypto';W.mkdir(parents=True,exist_ok=True)
NODE=os.environ.get('PLAYWRIGHT_NODEJS_PATH','/home/codex/.local/bin/node');PW='independent fixture passphrase';checks=[]
def js(script,data=None):return json.loads(subprocess.check_output([NODE,'--input-type=module','-e',script],cwd=R,input=None if data is None else json.dumps(data,ensure_ascii=False).encode()))
def ok(s):checks.append(s);print('PASS',s)
def b64(b):return base64.b64encode(b).decode()
def dec(s):return base64.b64decode(s,validate=True)
def compact(o):return json.dumps(o,ensure_ascii=False,separators=(',',':')).encode()
def aad(e,purpose):return compact([e['format'],e['version'],e['id'],purpose,e['kdf']])
fixture=js("import {createVault} from './extension/lib/vault-crypto.js';const c={schemaVersion:1,profiles:[{id:'interop',tenancy:'synthetic-tenant',name:'가상 🔑',identityDomain:'Default',username:'interop@example.invalid',password:'  exact spaces & < >  ',bypassCode:'000123',identityOrigins:[],selectors:{}}]};console.log(JSON.stringify({config:c,envelope:(await createVault(c,'"+PW+"')).envelope}));")
e=fixture['envelope'];wrapping=hashlib.pbkdf2_hmac('sha256',PW.encode(),dec(e['kdf']['salt']),e['kdf']['iterations'],32);key=AESGCM(wrapping).decrypt(dec(e['wrappedKey']['iv']),dec(e['wrappedKey']['ciphertext']),aad(e,'key'));assert len(key)==32;ok('Python independently unwraps the Web Crypto random data key using PBKDF2-HMAC-SHA256')
config=json.loads(AESGCM(key).decrypt(dec(e['payload']['iv']),dec(e['payload']['ciphertext']),aad(e,'payload')));assert config==fixture['config'];ok('Python independently authenticates and decrypts Web Crypto Unicode and exact secret text')
for name in ['wrappedKey','payload']:
 part=e[name];bad=bytearray(dec(part['ciphertext']));bad[-1]^=1
 try:AESGCM(wrapping if name=='wrappedKey' else key).decrypt(dec(part['iv']),bytes(bad),aad(e,'key' if name=='wrappedKey' else 'payload'));raise AssertionError('Modified tag accepted')
 except Exception as ex:
  assert ex.__class__.__name__=='InvalidTag';ok('Independent AES-GCM verifier rejects a modified '+name+' authentication tag')
new={**e,'id':str(uuid.uuid4()),'kdf':{**e['kdf'],'salt':b64(os.urandom(16))}};newkey=os.urandom(32);newwrap=hashlib.pbkdf2_hmac('sha256',PW.encode(),dec(new['kdf']['salt']),new['kdf']['iterations'],32)
for name,purpose,value,aes in [('wrappedKey','key',newkey,newwrap),('payload','payload',compact(config),newkey)]:
 iv=os.urandom(12);new[name]={'algorithm':'AES-GCM','iv':b64(iv),'ciphertext':b64(AESGCM(aes).encrypt(iv,value,aad(new,purpose)))}
actual=js("import {unlockVault,decryptVault} from './extension/lib/vault-crypto.js';let input='';for await(const x of process.stdin)input+=x;const d=JSON.parse(input);console.log(JSON.stringify(await decryptVault(d.e,await unlockVault(d.e,d.password))));",{'e':new,'password':PW});assert actual==config;ok('Web Crypto decrypts a separately generated Python envelope without a shared implementation')
report={'count':len(checks),'checks':checks,'scope':'Independent Python cryptography AESGCM and hashlib PBKDF2 versus shipped Web Crypto primitives; synthetic accounts only'};(W/'interop-report.json').write_text(json.dumps(report,indent=2)+'\n');print('CHECKS',len(checks))
