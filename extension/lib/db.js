function db() { return new Promise((resolve,reject)=>{
  const req = indexedDB.open('oci-companion-files',1);
  req.onupgradeneeded=()=>req.result.createObjectStore('handles');
  req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(new Error('파일 연결 저장소를 열 수 없습니다.'));
}); }
export async function handleEntryGet(){const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction('handles'),s=t.objectStore('handles'),h=s.get('team'),k=s.get('team-key');t.oncomplete=()=>{d.close();resolve({handle:h.result,key:k.result||'legacy'});};t.onerror=()=>{d.close();reject(new Error('파일 연결을 읽을 수 없습니다.'));};});}
export async function handleGet(){return (await handleEntryGet()).handle;}
export async function handleSet(handle) {
  return navigator.locks.request('oci-companion-list-write',async()=>{const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction('handles','readwrite'),s=t.objectStore('handles');if(handle){s.put(handle,'team');s.put(crypto.randomUUID(),'team-key');}else{s.delete('team');s.delete('team-key');}t.oncomplete=()=>{d.close();resolve();};t.onerror=()=>{d.close();reject(new Error('파일 연결을 저장할 수 없습니다.'));};});});
}
