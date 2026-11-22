import {MAX_BYTES,MAX_PROFILES,normalizeConfig,normalizeProfile} from './model.js';
const labels={tenancy:'테넌시',username:'아이디',password:'비밀번호',bypassCode:'Bypass Code',name:'고객사명',identityDomain:'Identity Domain'};
const required=['tenancy','username','password','bypassCode'];
export function columnRows(text,label){
  if(typeof text!=='string'||new TextEncoder().encode(text).length>MAX_BYTES)throw new Error(`${label}: 붙여넣을 값은 512 KiB 이하여야 합니다.`);
  if(text.includes('\t'))throw new Error(`${label}: 엑셀에서 한 열만 복사해 붙여넣어 주세요.`);
  if(!text)return [];
  const rows=text.replace(/\r\n?/g,'\n').split('\n');
  // Excel adds a record delimiter. Remove only that delimiter, never trim secrets
  // or filter empty interior cells: that would silently pair different rows.
  if(rows.at(-1)==='')rows.pop();
  return rows;
}
export function parseBulkColumns(raw,makeId=()=>crypto.randomUUID()){
  const cols=Object.fromEntries(Object.entries(labels).map(([k,label])=>[k,columnRows(raw[k]??'',label)]));
  const count=cols.tenancy.length;
  if(!count)throw new Error('테넌시 열을 먼저 붙여넣어 주세요.');
  if(count>MAX_PROFILES)throw new Error(`한 번에 최대 ${MAX_PROFILES}개 계정을 등록할 수 있습니다.`);
  for(const [key,rows] of Object.entries(cols))if((required.includes(key)||rows.length)&&rows.length!==count)throw new Error(`${labels[key]} ${rows.length}행 · 테넌시 ${count}행입니다. 같은 순서와 행 수로 붙여넣어 주세요.`);
  const profiles=[];
  for(let i=0;i<count;i++){
    const item=Object.fromEntries(Object.keys(labels).map(k=>[k,cols[k][i]??'']));
    if(!item.identityDomain.trim())item.identityDomain='Default';
    try{profiles.push(normalizeProfile({id:makeId(),...item}));}
    catch{throw new Error(`${i+1}행: 필수값과 각 항목의 길이를 확인해 주세요. 빈 셀을 지우지 말고 같은 행을 수정하세요.`);}
  }
  return normalizeConfig({schemaVersion:1,profiles}).profiles;
}
const key=p=>JSON.stringify([p.tenancy.toLowerCase(),p.identityDomain,p.username]);
export function appendBulkProfiles(existing,incoming){
  const before=normalizeConfig({schemaVersion:1,profiles:existing}).profiles;
  const added=normalizeConfig({schemaVersion:1,profiles:incoming}).profiles;
  if(!added.length)throw new Error('등록할 계정이 없습니다.');
  const seen=new Set(before.map(key));
  for(const [i,p] of added.entries()){
    const k=key(p);
    if(seen.has(k))throw new Error(`${i+1}행: 같은 테넌시·아이디·도메인의 계정이 이미 있거나 붙여넣은 목록에서 중복됩니다.`);
    seen.add(k);
  }
  return normalizeConfig({schemaVersion:1,profiles:[...before,...added]}).profiles;
}
