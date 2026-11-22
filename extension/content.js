(() => {
  if(globalThis.__ociCompanionRunning)return;
  globalThis.__ociCompanionRunning=true;
  let busy=false,stop=false,ctx=null;
  const claimed=new Set();
  const send=m=>chrome.runtime.sendMessage(m);
  const close=()=>{stop=true;observer.disconnect();clearInterval(timer);globalThis.__ociCompanionRunning=false;};
  async function tick() {
    if(busy||stop)return;busy=true;
    try {
      const response=await send({type:'CONTEXT'});
      if(!response?.ok){close();return;}ctx=response.context;
      if(Date.now()>ctx.expiresAt){close();return;}
      const plan=OCILoginEngine.describe(ctx);if(!plan)return;
      if(plan.error){await send({type:'ERROR'});close();return;}
      if(plan.complete){await send({type:'COMPLETE'});close();return;}
      if(claimed.has(plan.stage))return;
      // Wait for the matching submit control to finish rendering before claiming a step.
      if(ctx.mode==='login' && !plan.submit && !plan.button && !plan.radio && !plan.choice)return;
      if(ctx.mode==='fill' && (plan.button||plan.radio||plan.choice))return;
      const result=await send({type:'CLAIM',stage:plan.stage});
      claimed.add(plan.stage);
      if(!result?.ok)return;
      await OCILoginEngine.execute(plan,ctx,result.fields,()=>send({type:'APPLIED',stage:plan.stage}));
      // Keep secrets out of the content-script's long-lived state.
      for(const key of Object.keys(result.fields))result.fields[key]='';
    }catch{await send({type:'ERROR'}).catch(()=>{});close();}
    finally{busy=false;}
  }
  let queued=false;
  const observer=new MutationObserver(()=>{if(!queued){queued=true;setTimeout(()=>{queued=false;tick();},300);}});
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','disabled','style','class']});
  const timer=setInterval(tick,1200);
  tick();
})();
