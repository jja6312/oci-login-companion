import {REGIONAL_DOMAIN_PATTERNS} from './regions.js';
export const MAX_BYTES = 524288;
export const MAX_PROFILES = 300;
export const SELECTOR_KEYS = ['tenancy','domain','username','password','bypass','submitTenancy','submitDomain','submitCredentials','alternative','bypassChoice','submitBypass'];
export const DEFAULT_SETTINGS = Object.freeze({mode:'local', fileKind:'picker'});
export const CONSOLE_ORIGIN = 'https://cloud.oracle.com';
export const ENTRY_ORIGIN='https://www.oracle.com';
export const ENTRY_PATH='/cloud/sign-in.html';
export const LOGIN_ENTRY_URL=ENTRY_ORIGIN+ENTRY_PATH;
export const ENTRY_PATTERN=ENTRY_ORIGIN+ENTRY_PATH+'*';
export const BROKER_ORIGIN = 'https://login.oci.oraclecloud.com';
// A stalled session picker can always return to Oracle's own account-entry
// route. Keep the original OAuth request intact and never infer a tenancy here.
export function sessionRecoveryURL(job,frame) {
  if(!job||job.mode!=='login'||job.activeOrigin!==BROKER_ORIGIN||job.sessionRecoveryAttempted||!job.documentId||frame?.documentId!==job.documentId||frame.errorOccurred||Object.keys(job.claims||{}).length||Object.keys(job.applied||{}).length)return null;
  try {
    const u=new URL(frame.url);
    if(u.origin!==BROKER_ORIGIN||u.pathname!=='/v2/ui/sessionPicker'||u.username||u.password||u.port)return null;
    u.pathname='/v2/ui/changeTenant';u.hash='';return u.href;
  }catch{return null;}
}
export const AUTO_AUTH_PATTERNS = [ENTRY_PATTERN,'https://cloud.oracle.com/*','https://login.oci.oraclecloud.com/*','https://*.identity.oraclecloud.com/*','https://login.oraclecloud.com/*','https://signin.oraclecloud.com/*',...REGIONAL_DOMAIN_PATTERNS];
function str(value, label, limit=1000, required=false) {
  if (typeof value !== 'string' || value.length > limit || (required && !value.trim()) || /\u0000/.test(value)) throw new Error(`${label} 값을 확인해 주세요.`);
  return value;
}
export function oracleURL(value) {
  let u; try { u = new URL(value); } catch { throw new Error('올바른 OCI HTTPS 주소를 입력해 주세요.'); }
  if (u.protocol !== 'https:' || u.username || u.password || u.port || u.hostname.includes('*') || !(u.hostname === 'cloud.oracle.com' || u.hostname.endsWith('.oraclecloud.com'))) throw new Error('cloud.oracle.com 또는 oraclecloud.com 하위의 HTTPS 주소만 사용할 수 있습니다.');
  return u;
}
export function exactOrigin(value) {
  const u = oracleURL(value);
  if (u.pathname !== '/' || u.search || u.hash) throw new Error('인증 도메인은 경로 없이 https://호스트 형식으로 입력해 주세요.');
  if (u.hostname === 'cloud.oracle.com') throw new Error('콘솔 주소 대신 실제 인증 도메인을 입력해 주세요.');
  return u.origin;
}
export function normalizeProfile(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('계정 형식이 올바르지 않습니다.');
  const id = str(raw.id, '계정 ID', 80, true);
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error('계정 ID에는 영문, 숫자, 밑줄, 하이픈만 사용할 수 있습니다.');
  const tenancy = str(raw.tenancy, '테넌시', 150, true).trim();
  const rawOrigins=raw.identityOrigins??[];
  if (!Array.isArray(rawOrigins) || rawOrigins.length > 8) throw new Error('인증 도메인 목록을 확인해 주세요.');
  const identityOrigins = [...new Set(rawOrigins.map(exactOrigin))];
  // Read old exports safely. New logins use Oracle's fixed tenancy-entry page.
  if(raw.loginUrl){const start=oracleURL(raw.loginUrl);if(start.origin!==CONSOLE_ORIGIN&&!identityOrigins.includes(start.origin))throw new Error('기존 로그인 주소의 인증 도메인을 확인해 주세요.');}
  const selectors = {};
  if (raw.selectors !== undefined) {
    if (!raw.selectors || typeof raw.selectors !== 'object' || Array.isArray(raw.selectors)) throw new Error('고급 선택자 형식을 확인해 주세요.');
    for (const [key,value] of Object.entries(raw.selectors)) {
      if (!SELECTOR_KEYS.includes(key)) throw new Error(`지원하지 않는 선택자: ${key}`);
      selectors[key] = str(value, '선택자', 500);
    }
  }
  return {id, name:str(raw.name || tenancy, '계정 이름', 120, true).trim(), tenancy,
    identityDomain:str(raw.identityDomain ?? 'Default', 'Identity Domain', 150).trim(),
    username:str(raw.username, '아이디', 320, true).trim(), password:str(raw.password, '비밀번호', 2000, true),
    bypassCode:str(raw.bypassCode, 'Bypass Code', 1000, true), identityOrigins, selectors};
}
export function normalizeConfig(raw) {
  if (!raw || raw.schemaVersion !== 1 || !Array.isArray(raw.profiles) || raw.profiles.length > MAX_PROFILES) throw new Error('schemaVersion: 1과 profiles 배열이 있는 설정 파일이 필요합니다. 최대 300개 계정까지 지원합니다.');
  const profiles = raw.profiles.map(normalizeProfile);
  if (new Set(profiles.map(p=>p.id)).size !== profiles.length) throw new Error('중복된 계정 ID가 있습니다.');
  const result={schemaVersion:1,profiles};
  if(new TextEncoder().encode(JSON.stringify(result)).length>MAX_BYTES)throw new Error('계정 목록은 512 KiB 이하여야 합니다.');
  return result;
}
export function parseConfig(text) {
  if (new TextEncoder().encode(text).length > MAX_BYTES) throw new Error('설정 파일은 512 KiB 이하여야 합니다.');
  let raw; try {raw = JSON.parse(text.replace(/^\uFEFF/,''));} catch {throw new Error('JSON 파일 형식을 확인해 주세요.');}
  return normalizeConfig(raw);
}
export function originsFor(p) { return [CONSOLE_ORIGIN,...p.identityOrigins]; }
export function patternsFor(p) { return [...new Set([...AUTO_AUTH_PATTERNS,...p.identityOrigins.map(x=>`${x}/*`)])]; }
export function bindingKey(p) { return JSON.stringify([p.id,p.tenancy.toLowerCase(),p.identityDomain,p.username]); }
export function isAutoIdentityOrigin(value) {try{const u=new URL(exactOrigin(value));return u.hostname.endsWith('.identity.oraclecloud.com')||['login.oraclecloud.com','signin.oraclecloud.com'].includes(u.hostname);}catch{return false;}}
export function isBrokerOrigin(value){try{const u=new URL(exactOrigin(value));return u.hostname==='login.oci.oraclecloud.com'||/^login\.[a-z][a-z0-9-]*-\d+(?:\.oci)?\.oraclecloud\.com$/.test(u.hostname);}catch{return false;}}
export function routingKind(value){try{const origin=new URL(value).origin;if(origin===CONSOLE_ORIGIN)return 'console';if(origin===ENTRY_ORIGIN)return 'account-entry';if(isBrokerOrigin(origin))return origin===BROKER_ORIGIN?'broker':'regional-broker';if(isAutoIdentityOrigin(origin))return 'identity';}catch{}return 'other';}
export function isOAuthBridge(value){try{const u=new URL(value);return (isBrokerOrigin(u.origin)||isAutoIdentityOrigin(u.origin))&&/^\/(?:v\d+\/oauth2|oauth2)(?:\/|$)/.test(u.pathname);}catch{return false;}}
export function canLearnIdentity(job,details) {
  const q=details.transitionQualifiers||[];
  let origin;try{origin=new URL(details.url).origin;}catch{return false;}
  return details.frameId===0 && job.tenancyVerified===true && ([CONSOLE_ORIGIN,ENTRY_ORIGIN].includes(job.activeOrigin)||isBrokerOrigin(job.activeOrigin)) && !job.activeIdentity && isAutoIdentityOrigin(origin) && !q.includes('from_address_bar') && !q.includes('forward_back') && (q.includes('server_redirect')||q.includes('client_redirect')||['link','form_submit'].includes(details.transitionType));
}
export function matchesOrigin(p, url) { try {const u=new URL(url);return u.protocol==='https:' && !u.username && !u.password && originsFor(p).includes(u.origin);} catch {return false;} }
export function mergeProfiles(oldProfiles, incoming, allowUpdates=false) {
  const map = new Map(oldProfiles.map(p=>[p.id,p]));
  for (const p of incoming) {
    if (map.has(p.id) && JSON.stringify(map.get(p.id)) !== JSON.stringify(p) && !allowUpdates) throw new Error('같은 ID의 계정이 있습니다. 갱신을 허용하거나 ID를 변경해 주세요.');
    map.set(p.id,p);
  }
  return normalizeConfig({schemaVersion:1, profiles:[...map.values()]}).profiles;
}

export function canEnterBroker(job,details){const q=details.transitionQualifiers||[];let u;try{u=new URL(details.url);}catch{return false;}return details.frameId===0&&isBrokerOrigin(u.origin)&&([CONSOLE_ORIGIN,ENTRY_ORIGIN,job.activeIdentity].filter(Boolean).includes(job.activeOrigin)||isBrokerOrigin(job.activeOrigin))&&!q.includes('from_address_bar')&&!q.includes('forward_back')&&(q.includes('server_redirect')||q.includes('client_redirect')||['link','form_submit'].includes(details.transitionType));}

export function canEnterEntry(job,d){let u;try{u=new URL(d.url);}catch{return false;}const q=d.transitionQualifiers||[];return d.frameId===0&&u.origin===ENTRY_ORIGIN&&u.pathname===ENTRY_PATH&&[CONSOLE_ORIGIN,ENTRY_ORIGIN].includes(job.activeOrigin)&&!q.includes('from_address_bar')&&!q.includes('forward_back')&&(q.includes('server_redirect')||q.includes('client_redirect')||['link','form_submit'].includes(d.transitionType));}
