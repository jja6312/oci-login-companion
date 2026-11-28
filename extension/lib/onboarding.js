import {handleEntryGet,handleSet} from './db.js';
import {validateTeamFile} from './sources.js';
const lock='oci-companion-onboarding';
const completed=()=>({complete:true,version:1});
async function state(){
 const saved=await chrome.storage.local.get(['onboarding','settings','profiles']);
 if(saved.onboarding?.complete)return {complete:true};
 if(!saved.onboarding&&(['local','file'].includes(saved.settings?.mode)||(Array.isArray(saved.profiles)&&saved.profiles.length))){
  await chrome.storage.local.set({onboarding:completed()});return {complete:true};
 }
 return {complete:false,step:saved.onboarding?.step==='file'?'file':'choose'};
}
export function onboardingState(){return navigator.locks.request(lock,state);}
export function onboardingStep(step){return navigator.locks.request(lock,async()=>{
 const current=await state();if(current.complete)return current;
 await chrome.storage.local.set({onboarding:{complete:false,step:step==='file'?'file':'choose'}});
 return {complete:false,step:step==='file'?'file':'choose'};
});}
export function finishOnboarding(mode,handle){return navigator.locks.request(lock,async()=>{
 const current=await state();if(current.complete)return false;
 if(!['local','file'].includes(mode))throw new Error('저장 위치를 선택해 주세요.');
 if(mode==='file'){
  if(!handle)throw new Error('팀 JSON 파일을 선택해 주세요.');
  await validateTeamFile(handle);
  const old=await handleEntryGet();await handleSet(handle);
  try{await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker'},onboarding:completed()});}
  catch(e){await handleSet(old.handle);throw e;}
 }else await chrome.storage.local.set({settings:{mode:'local',fileKind:'picker'},onboarding:completed()});
 return true;
});}
