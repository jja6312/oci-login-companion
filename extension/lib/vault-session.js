// chrome.storage.session is browser memory, never chrome.storage.local/sync/IDB.
import {VaultError,unbase64} from './vault-crypto.js';
export const VAULT_TIMEOUT_MS=300000;
export const SESSION_KEYS=['vaultKeys','vaultLease','vaultLockEpoch'];
const mutex='oci-companion-vault-session';
const locked=()=>new VaultError('VAULT_LOCKED','금고가 잠겼습니다. 다시 잠금 해제해 주세요.');
async function state(){
  const s=await chrome.storage.session.get(SESSION_KEYS);
  if(!s.vaultLockEpoch){s.vaultLockEpoch=crypto.randomUUID();await chrome.storage.session.set({vaultLockEpoch:s.vaultLockEpoch});}
  return s;
}
async function clearWithin(){
  const all=await chrome.storage.session.get(null);
  const jobs=Object.entries(all).filter(([k])=>k.startsWith('job:')).map(([k])=>Number(k.slice(4)));
  await chrome.storage.session.set({vaultLease:null,vaultLockEpoch:crypto.randomUUID()});
  await chrome.storage.session.remove(['vaultKeys','identityBindings','lastUsed',...Object.keys(all).filter(k=>k.startsWith('job:')||k.startsWith('status:'))]);
  await chrome.alarms.clear('vault-expire');
  for(const tabId of jobs){chrome.tabs.sendMessage(tabId,{type:'VAULT_LOCKED'},{frameId:0}).catch(()=>{});chrome.action.setBadgeText({tabId,text:''}).catch(()=>{});}
}
async function live(s){
  if(!s.vaultLease||s.vaultLease.expiresAt<=Date.now()){
    if(s.vaultLease||Object.keys(s.vaultKeys||{}).length)await clearWithin();return false;
  }
  return true;
}
export function lockVaults(){return navigator.locks.request(mutex,clearWithin);}
export function lockEpoch(){return navigator.locks.request(mutex,async()=>{let s=await state();if(s.vaultLease&&!await live(s))s=await state();return s.vaultLockEpoch;});}
export function vaultSession(id){return navigator.locks.request(mutex,async()=>{const s=await state();if(!await live(s))return null;const key=s.vaultKeys?.[id];return key?{...key,expiresAt:s.vaultLease.expiresAt}:null;});}
export function installVaultSession(id,key,expectedLockEpoch){return navigator.locks.request(mutex,async()=>{
  unbase64(key,32);const s=await state();if(s.vaultLockEpoch!==expectedLockEpoch)throw locked();
  const valid=await live(s);if(valid===false&&s.vaultLease)throw locked();
  if((await state()).vaultLockEpoch!==expectedLockEpoch)throw locked();
  const keys=valid?{...s.vaultKeys}:{};keys[id]={key,epoch:keys[id]?.key===key?keys[id].epoch:crypto.randomUUID()};
  const lease={expiresAt:Date.now()+VAULT_TIMEOUT_MS};await chrome.storage.session.set({vaultKeys:keys,vaultLease:lease});await chrome.alarms.create('vault-expire',{when:lease.expiresAt});return keys[id].epoch;
});}
export function withLockEpoch(expected,fn){return navigator.locks.request(mutex,async()=>{if((await state()).vaultLockEpoch!==expected)throw locked();return fn();});}
export function withVaultAccess(id,epoch,fn=()=>true){return navigator.locks.request(mutex,async()=>{
  const s=await state();if(!await live(s)||!s.vaultKeys?.[id]||s.vaultKeys[id].epoch!==epoch)throw locked();return fn();
});}
export function touchVaults(){return navigator.locks.request(mutex,async()=>{
  const s=await state();if(!await live(s)||!Object.keys(s.vaultKeys||{}).length)return false;
  const lease={expiresAt:Date.now()+VAULT_TIMEOUT_MS};await chrome.storage.session.set({vaultLease:lease});await chrome.alarms.create('vault-expire',{when:lease.expiresAt});return true;
});}
export async function expireVaults(){const s=await chrome.storage.session.get('vaultLease');if(s.vaultLease?.expiresAt<=Date.now())await lockVaults();}
