function db() { return new Promise((resolve,reject)=>{
  const req = indexedDB.open('oci-companion-files',1);
  req.onupgradeneeded=()=>req.result.createObjectStore('handles');
  req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(new Error('파일 연결 저장소를 열 수 없습니다.'));
}); }
export async function handleGet() {
  const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction('handles');const r=t.objectStore('handles').get('team');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(new Error('파일 연결을 읽을 수 없습니다.'));t.oncomplete=()=>d.close();});
}
export async function handleSet(handle) {
  const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction('handles','readwrite');if(handle)t.objectStore('handles').put(handle,'team');else t.objectStore('handles').delete('team');t.oncomplete=()=>{d.close();resolve();};t.onerror=()=>reject(new Error('파일 연결을 저장할 수 없습니다.'));});
}
