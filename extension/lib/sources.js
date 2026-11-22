import {DEFAULT_SETTINGS, MAX_BYTES, parseConfig, normalizeConfig} from './model.js';
import {handleGet} from './db.js';
export async function settingsGet() {return {...DEFAULT_SETTINGS,...(await chrome.storage.local.get('settings')).settings};}
export async function personalGet() {return normalizeConfig({schemaVersion:1,profiles:(await chrome.storage.local.get('profiles')).profiles || []}).profiles;}
export async function personalSet(profiles) {await chrome.storage.local.set({profiles:normalizeConfig({schemaVersion:1,profiles}).profiles});}
export async function readSource() {
  const settings = await settingsGet();
  if(settings.mode==='local')return {profiles:await personalGet(), label:'개인 저장소', readAt:Date.now()};
  if(settings.mode!=='file')throw new Error('저장 방식을 다시 선택해 주세요.');
  if(settings.fileKind==='native') {
    if(!settings.nativePath)throw new Error('팀 설정 파일의 전체 경로를 입력해 주세요.');
    if(!await chrome.permissions.contains({permissions:['nativeMessaging']}))throw new Error('설정에서 파일 보조 프로그램 사용을 허용해 주세요.');
    let result;
    try {result=await chrome.runtime.sendNativeMessage('cloudragon.oci_login_files',{action:'read',path:settings.nativePath});} catch {throw new Error('파일 보조 프로그램에 연결할 수 없습니다. Windows 설치 안내를 확인해 주세요.');}
    if(!result?.ok || typeof result.text!=='string')throw new Error('지정한 파일을 읽지 못했습니다. 경로와 폴더 접근 권한을 확인해 주세요.');
    return {profiles:parseConfig(result.text).profiles,label:settings.nativePath,readAt:Date.now()};
  }
  const handle=await handleGet();if(!handle)throw new Error('설정에서 팀 설정 파일을 연결해 주세요.');
  if(await handle.queryPermission({mode:'read'})!=='granted')throw new Error('파일 읽기 권한이 필요합니다. 설정에서 파일 접근을 다시 허용해 주세요.');
  let file;try {file=await handle.getFile();} catch {throw new Error('연결한 파일을 찾을 수 없습니다. 이동·교체된 파일을 다시 선택해 주세요.');}
  if(file.size>MAX_BYTES)throw new Error('설정 파일은 512 KiB 이하여야 합니다.');
  return {profiles:parseConfig(await file.text()).profiles,label:file.name,readAt:Date.now()};
}
