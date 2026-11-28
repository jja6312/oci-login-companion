// Cryptographic primitives are provided by the browser's Web Crypto API.
// Only this versioned envelope is persisted; passwords and unwrapped keys are not.
import {normalizeConfig, MAX_BYTES} from './model.js';

export const VAULT_FORMAT = 'oci-companion-vault';
export const VAULT_VERSION = 1;
export const KDF_ITERATIONS = 600000;
export const MAX_VAULT_BYTES = 1048576;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', {fatal:true});

export class VaultError extends Error {
  constructor(code, message, details={}) {super(message);this.name='VaultError';this.code=code;Object.assign(this,details);}
}
const invalid = () => new VaultError('VAULT_INVALID','금고 파일 형식이 올바르지 않습니다. 원본 파일을 확인해 주세요.');
const failed = () => new VaultError('VAULT_UNLOCK','금고 암호가 다르거나 파일이 손상되었습니다.');
function record(value, keys) {
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))throw invalid();
}
export function base64(bytes) {
  let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);
}
export function unbase64(value, min, max=min) {
  if(typeof value!=='string'||value.length>Math.ceil(max/3)*4||value.length%4!==0||! /^[A-Za-z0-9+/]*={0,2}$/.test(value))throw invalid();
  let data;try{data=Uint8Array.from(atob(value),c=>c.charCodeAt(0));}catch{throw invalid();}
  if(data.length<min||data.length>max||base64(data)!==value)throw invalid();return data;
}
export function validatePassword(password) {
  if(typeof password!=='string'||password.length>512||Array.from(password).length<12||!password.trim()||password.includes('\0'))throw new VaultError('VAULT_PASSWORD','금고 암호는 12자 이상으로 입력해 주세요. 긴 문장형 암호를 권장합니다.');
}
export function normalizeEnvelope(raw) {
  record(raw,['format','version','id','kdf','wrappedKey','payload']);
  if(raw.format!==VAULT_FORMAT||raw.version!==VAULT_VERSION||typeof raw.id!=='string'||! /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(raw.id))throw invalid();
  record(raw.kdf,['name','hash','iterations','salt']);
  if(raw.kdf.name!=='PBKDF2'||raw.kdf.hash!=='SHA-256'||!Number.isInteger(raw.kdf.iterations)||raw.kdf.iterations<KDF_ITERATIONS||raw.kdf.iterations>2000000)throw invalid();
  unbase64(raw.kdf.salt,16);
  for(const [name,min,max] of [['wrappedKey',48,48],['payload',16,MAX_BYTES+16]]){
    record(raw[name],['algorithm','iv','ciphertext']);if(raw[name].algorithm!=='AES-GCM')throw invalid();unbase64(raw[name].iv,12);unbase64(raw[name].ciphertext,min,max);
  }
  return {format:VAULT_FORMAT,version:VAULT_VERSION,id:raw.id,kdf:{name:'PBKDF2',hash:'SHA-256',iterations:raw.kdf.iterations,salt:raw.kdf.salt},wrappedKey:{algorithm:'AES-GCM',iv:raw.wrappedKey.iv,ciphertext:raw.wrappedKey.ciphertext},payload:{algorithm:'AES-GCM',iv:raw.payload.iv,ciphertext:raw.payload.ciphertext}};
}
export function inspectVaultText(text) {
  if(typeof text!=='string'||encoder.encode(text).length>MAX_VAULT_BYTES)throw invalid();
  if(!text.trim())return {kind:'empty',config:{schemaVersion:1,profiles:[]}};
  let raw;try{raw=JSON.parse(text.replace(/^\uFEFF/,''));}catch{throw invalid();}
  if(raw&&Object.hasOwn(raw,'format'))return {kind:'encrypted',envelope:normalizeEnvelope(raw)};
  return {kind:'legacy',config:normalizeConfig(raw)};
}
export function envelopeText(envelope) {return JSON.stringify(normalizeEnvelope(envelope),null,2)+'\n';}
function aad(envelope, purpose) {return encoder.encode(JSON.stringify([VAULT_FORMAT,VAULT_VERSION,envelope.id,purpose,envelope.kdf]));}
async function passwordKey(envelope, password) {
  if(typeof password!=='string'||password.length>512)throw failed();
  const bytes=encoder.encode(password);
  try{
    const material=await crypto.subtle.importKey('raw',bytes,'PBKDF2',false,['deriveKey']);
    return await crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt:unbase64(envelope.kdf.salt,16),iterations:envelope.kdf.iterations},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  }finally{bytes.fill(0);}
}
async function dataKey(raw) {
  const bytes=unbase64(raw,32);try{return await crypto.subtle.importKey('raw',bytes,'AES-GCM',false,['encrypt','decrypt']);}finally{bytes.fill(0);}
}
async function encryptPart(envelope, purpose, bytes, key) {
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const encrypted=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad(envelope,purpose),tagLength:128},key,bytes);
  return {algorithm:'AES-GCM',iv:base64(iv),ciphertext:base64(new Uint8Array(encrypted))};
}
async function decryptPart(envelope, purpose, part, key, min, max) {
  return new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:unbase64(part.iv,12),additionalData:aad(envelope,purpose),tagLength:128},key,unbase64(part.ciphertext,min,max)));
}
export async function decryptVault(raw, key) {
  const envelope=normalizeEnvelope(raw);let bytes;
  try{bytes=await decryptPart(envelope,'payload',envelope.payload,await dataKey(key),16,MAX_BYTES+16);return normalizeConfig(JSON.parse(decoder.decode(bytes)));}
  catch{throw failed();}finally{bytes?.fill(0);}
}
export async function unlockVault(raw, password) {
  const envelope=normalizeEnvelope(raw);let bytes;
  try{bytes=await decryptPart(envelope,'key',envelope.wrappedKey,await passwordKey(envelope,password),48,48);if(bytes.length!==32)throw failed();const key=base64(bytes);await decryptVault(envelope,key);return key;}
  catch{throw failed();}finally{bytes?.fill(0);}
}
export async function sealVault(raw, key, config) {
  const envelope=normalizeEnvelope(raw),bytes=encoder.encode(JSON.stringify(normalizeConfig(config)));
  try{return {...envelope,payload:await encryptPart(envelope,'payload',bytes,await dataKey(key))};}finally{bytes.fill(0);}
}
export async function createVault(config, password) {
  validatePassword(password);const normalized=normalizeConfig(config);
  const raw=crypto.getRandomValues(new Uint8Array(32));
  const envelope={format:VAULT_FORMAT,version:VAULT_VERSION,id:crypto.randomUUID(),kdf:{name:'PBKDF2',hash:'SHA-256',iterations:KDF_ITERATIONS,salt:base64(crypto.getRandomValues(new Uint8Array(16)))}};
  try{
    const key=base64(raw);envelope.wrappedKey=await encryptPart(envelope,'key',raw,await passwordKey(envelope,password));
    const bytes=encoder.encode(JSON.stringify(normalized));try{envelope.payload=await encryptPart(envelope,'payload',bytes,await dataKey(key));}finally{bytes.fill(0);}
    if(JSON.stringify(await decryptVault(envelope,key))!==JSON.stringify(normalized))throw failed();
    return {envelope:normalizeEnvelope(envelope),key};
  }finally{raw.fill(0);}
}
