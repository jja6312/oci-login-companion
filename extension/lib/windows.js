export function validateLaunchWindow(request,window){
  if(!Number.isInteger(request.windowId)||request.windowId<0||typeof request.incognito!=='boolean'||!window||window.id!==request.windowId||window.incognito!==request.incognito||!['normal','popup'].includes(window.type))throw new Error('로그인을 시작한 창을 찾지 못했습니다. 그 창에서 확장을 다시 열어 주세요.');
  return {windowId:window.id,incognito:window.incognito};
}
