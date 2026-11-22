export class TeamFileError extends Error {
 constructor(code,message,handle=null){super(message);this.name='TeamFileError';this.code=code;this.handle=handle;}
}
export function permissionError(handle){return new TeamFileError('TEAM_PERMISSION','팀 파일 접근을 허용해 주세요.',handle);}
export async function requestFileAccess(handle,mode='read'){
 if(!handle)return false;
 try{return await handle.requestPermission({mode})==='granted';}
 catch(e){if(['SecurityError','NotAllowedError','AbortError'].includes(e.name))return false;throw e;}
}
