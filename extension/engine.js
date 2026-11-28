/* Shared with fixture tests. Runs only in Chrome's isolated content-script world. */
(() => {
  if (globalThis.OCILoginEngine?.version==='2.0.0') return;
  const rendered=e=>e && !e.hidden && e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden' && getComputedStyle(e).display!=='none';
  const visible=e=>rendered(e)&&!e.disabled&&e.getAttribute('aria-disabled')!=='true';
  const text=e=>(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');
  const all=(s,root=document)=>[...root.querySelectorAll(s)].filter(visible);
  const patterns={
    tenancy:/^(next|continue|다음|계속|테넌시로 이동)$/i,
    changeTenancy:/^(change tenancy|change cloud account|테넌시 변경|클라우드 계정 변경)$/i,
    domain:/^(next|continue|sign in|사인인|로그인|다음|계속)$/i,
    credentials:/^(sign in|log in|login|사인인|로그인|다음|next|verify|확인)$/i,
    bypass:/^(verify|continue|sign in|submit|사인인|확인|인증|검증|로그인|계속)$/i,
    alternative:/^(show alternative login methods|show alternative sign-in methods|try another (way|method)|use (a )?(backup|another|alternative) (verification|authentication)?\s?(method|option)?|다른 (방법|인증 방법|로그인 방법)(으로 인증| 사용| 보기| 표시)?|대체 (인증|로그인) 방법( 사용| 보기| 표시)?|백업 인증 방법( 사용)?)$/i,
    bypassChoice:/^(use (a )?bypass code|bypass code|우회 코드( 사용)?|바이패스 코드( 사용)?)$/i
  };
  const defaults={
    tenancy:['#cloudAccountName','#tenant','#tenancy','input[name="tenant"]','input[name="tenancy"]','input[name="cloudAccountName"]','input[autocomplete="organization"]'],
    domain:['select#identityDomain','select[name="identityDomain"]','select#domain','select[name="domain"]','select[name="domainSelect"]','select[data-testid="identity-domain-dropdown"]'],
    username:['#idcs-signin-basic-signin-form-username','#userid','#username','input[name="username"]','input[name="userid"]','input[autocomplete="username"]'],
    password:['#idcs-signin-basic-signin-form-password','#password','input[name="password"]','input[autocomplete="current-password"]'],
    bypass:['#bypasscode','#bypassCode','input[name="bypassCode"]','input[name="bypasscode"]']
  };
  function nativeFields(e) {
    if(e.matches('input,textarea,select'))return [e];
    // Normalize public JET IDs to the underlying native form control.
    if(e.matches('oj-input-text,oj-input-password,oj-text-area,oj-select-single,oj-select-one'))return all('input:not([type="hidden"]),textarea,select',e);
    return [];
  }
  function field(key,ctx) {
    const selectors=ctx.selectors[key]?[ctx.selectors[key]]:(defaults[key]||[]);
    const found=[...new Set(selectors.flatMap(s=>all(s)).flatMap(nativeFields))];
    if(found.length>1)throw new Error('ambiguous field');
    return found[0];
  }
  function button(key,ctx,root=document) {
    if(ctx.selectors[key]) {const found=all(ctx.selectors[key]);if(found.length>1)throw new Error('ambiguous button');return found[0];}
    const re=patterns[key];const includeDisabled=['tenancy','domain','credentials','bypass'].includes(key);const candidates=[...root.querySelectorAll('button,input[type="submit"],input[type="button"],a,[role="button"],[role="option"],[role="radio"]')].filter(e=>(includeDisabled?rendered(e):visible(e))&&(re?.test(e.getAttribute('aria-label')||text(e))||[...e.querySelectorAll('h3,h4,label')].some(x=>re?.test(text(x))))).filter(e=>key!=='bypassChoice'||!e.closest('[data-idcs-factor-type]')||e.closest('[data-idcs-factor-type]').getAttribute('data-idcs-factor-type')==='BYPASSCODE');
    if(key==='bypassChoice') {
      // The legacy Oracle icon button has no text, a sibling h5, and even an
      // unrelated accessibility label. Its factor marker identifies the action.
      const marked=[...root.querySelectorAll('button[data-idcs-factor-type="BYPASSCODE"],oj-button[data-idcs-factor-type="BYPASSCODE"],#idcs-mfa-mfa-auth-bypasscode-backup-button')].filter(e=>e.matches('button,oj-button')&&(!e.hasAttribute('data-idcs-factor-type')||e.getAttribute('data-idcs-factor-type')==='BYPASSCODE'));
      for(const e of marked){const action=e.matches('oj-button')?e.querySelector('button'):e;if(visible(e)&&visible(action)&&!candidates.includes(action))candidates.push(action);}
    }
    const found=candidates.filter(e=>!candidates.some(other=>other!==e&&e.contains(other)));
    if(found.length>1)throw new Error('ambiguous button');return found[0];
  }
  function submit(key,ctx,input) {
    const override='submit'+key[0].toUpperCase()+key.slice(1);
    if(ctx.selectors[override])return button(override,ctx);
    const root=input?.form||document;
    const b=button(key,ctx,root);if(b)return b;
    const options=all('button[type="submit"],input[type="submit"]',root);
    return options.length===1?options[0]:undefined;
  }
  function domainPlan(ctx){
    if(!ctx.identityDomain)return null;
    let domain=field('domain',ctx);
    if(!domain){const candidates=all('select').filter(e=>[...e.options].some(o=>o.value===ctx.identityDomain||o.text.trim()===ctx.identityDomain));if(candidates.length>1)throw new Error('ambiguous domain');domain=candidates[0];}
    if(domain)return {stage:'domain',input:domain,submit:submit('domain',ctx,domain)};
    const combos=all('[role="combobox"]').filter(e=>/identity|domain|도메인/i.test([e.id,e.getAttribute('aria-label'),e.getAttribute('name'),e.closest('label')?.textContent||''].join(' ')));
    if(combos.length>1)throw new Error('ambiguous domain picker');
    const combo=combos[0];if(!combo)return null;
    const options=all('[role="option"]').filter(e=>text(e)===ctx.identityDomain||e.getAttribute('data-value')===ctx.identityDomain);
    if(options.length>1)throw new Error('ambiguous domain option');
    const next=submit('domain',ctx,combo);
    if(options[0])return {stage:'domainPick',choice:options[0]};
    if(combo.value===ctx.identityDomain||text(combo)===ctx.identityDomain)return {stage:'domain',submit:next};
    return {stage:'domainOpen',button:combo};
  }
  function regionalDomainPlan(ctx){
    const tenants=all('.login-prompt .username-prompt');
    if(!tenants.length)return null; // Wait for the actual tenancy prompt.
    const matches=()=>{const current=all('.login-prompt .username-prompt');return current.length===1&&text(current[0]).toLowerCase()===ctx.tenancy.trim().toLowerCase();};
    if(!matches())throw new Error('regional tenancy mismatch');
    const plan=domainPlan(ctx);if(plan)plan.verify=matches;return plan;
  }
  function sessionValues(card){return {tenancy:card.querySelector('.tenant-name .value')?.textContent.trim(),username:card.querySelector('.user-name')?.textContent.trim(),identityDomain:card.querySelector('.domain-name .value')?.textContent.trim()};}
  function sameSession(card,ctx){const v=sessionValues(card);return visible(card)&&v.tenancy?.toLowerCase()===ctx.tenancy.trim().toLowerCase()&&v.username===ctx.username?.trim()&&v.identityDomain===ctx.identityDomain?.trim();}
  function sessionPlan(ctx){
    const root=document.getElementById('session-picker-dialog');if(!visible(root))return null;
    const cards=all('button[data-testid^="btn-session-"]',root);
    const matches=cards.filter(c=>sameSession(c,ctx));
    if(matches.length>1)throw new Error('ambiguous existing session');
    if(matches.length===1){const card=matches[0];return {stage:'sessionPick',button:card,verify:()=>sameSession(card,ctx)};}
    const different=[...new Set(all('.session-change',root).map(e=>e.closest('button')).filter(visible))];
    if(different.length>1)throw new Error('ambiguous new login');
    if(different[0])return {stage:'newLogin',button:different[0]};
    throw new Error('no matching session or new-login control');
  }
  function setValue(el,value) {
    const jet=el.closest('oj-input-text,oj-input-password,oj-text-area');
    if(jet)el.focus({preventScroll:true});
    if(el instanceof HTMLSelectElement) {
      const options=[...el.options].filter(x=>x.value===value || x.text.trim()===value);
      if(options.length!==1)throw new Error('unknown domain');el.value=options[0].value;
    } else {
      const proto=el instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
      if(!setter)throw new Error('unsupported field');setter.call(el,value);
    }
    el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
    // JET commits rawValue to its validated value on blur. Updating only the
    // native input leaves the view-model empty and keeps sign-in disabled.
    if(jet)el.blur();
  }
  function describe(ctx) {
    const error=all('[role="alert"],.oj-message-error,.idcs-error-message,.opcSignInErrorContainer,.opcRedirectUriInvalidError').some(e=>/invalid|incorrect|expired|too many|locked|didn.t work|잘못|틀렸|만료|잠겼|실패|유효하지/i.test(text(e)));
    if(error)return {error:true};
    if(ctx.domainOnly)return regionalDomainPlan(ctx);
    if(ctx.broker){const session=sessionPlan(ctx);if(session)return session;}
    if(!ctx.identity) {
      const tenancy=field('tenancy',ctx);
      if(tenancy)return {stage:'tenancy',input:tenancy,submit:submit('tenancy',ctx,tenancy)};
      if(!ctx.tenancyVerified){const change=button('changeTenancy',ctx);if(change)return {stage:'changeTenancy',button:change};}
      const domain=domainPlan(ctx);if(domain)return domain;
      if(document.querySelector('[data-testid="oci-console"],#console-shell,[aria-label="Oracle Cloud Console"]'))return {complete:true};
      return null;
    }
    // Never place a reusable bypass code into an unlabelled SMS/TOTP challenge.
    let bypass=field('bypass',ctx);
    if(!bypass) {
      const bypassText=/bypass code|우회 코드|바이패스 코드/i;
      // Oracle's actual bypass view uses the generic JET ID text-input. Accept
      // it only with its unique bypass verification control in the same view.
      const oracleSubmit=[...document.querySelectorAll('#bypass-auth-text-input')].filter(e=>rendered(e)&&e.matches('button,oj-button'));
      if(oracleSubmit.length>1)throw new Error('ambiguous bypass submit');
      const oracleFields=oracleSubmit.length===1?all('#text-input').flatMap(nativeFields):[];
      const found=[...new Set([...all('input[autocomplete="one-time-code"],input[name="otpCode"],input[name="passcode"],#idcs-mfa-mfa-authenticate-bypasscode-input,#bypass-code'),...oracleFields])].filter(e=>{
        const labelled=[...e.labels||[]].map(text).join(' ');
        const aria=[e.getAttribute('aria-label'),e.getAttribute('placeholder'),...(e.getAttribute('aria-labelledby')||'').split(/\s+/).map(id=>document.getElementById(id)?.textContent||'')].join(' ');
        // A nearby alternative-method heading does not label an SMS/TOTP input.
        return oracleFields.includes(e) || bypassText.test(labelled+' '+aria) || /bypass/i.test(e.id);
      });
      if(found.length>1)throw new Error('ambiguous bypass');bypass=found[0];
    }
    if(bypass)return {stage:'bypass',input:bypass,submit:submit('bypass',ctx,bypass)};
    const pw=field('password',ctx);
    const user=field('username',ctx);
    if(pw && pw.autocomplete!=='new-password' && all('input[type="password"]').length===1)return {stage:'credentials',input:user,password:pw,submit:submit('credentials',ctx,pw)};
    if(user && !pw)return {stage:'username',input:user,submit:submit('credentials',ctx,user)};
    const choice=button('bypassChoice',ctx);
    if(choice)return {stage:'bypassChoice',button:choice};
    // Oracle sometimes renders the factor choice as a labelled radio row.
    const radios=[...document.querySelectorAll('input[type="radio"]')].filter(r=>!r.disabled&&[...r.labels||[]].some(l=>visible(l)&&patterns.bypassChoice.test(text(l))));
    if(radios.length>1)throw new Error('ambiguous factor');
    if(radios[0])return {stage:'bypassChoice',radio:radios[0],submit:submit('domain',ctx,radios[0])};
    const alt=button('alternative',ctx);if(alt)return {stage:'alternative',button:alt};
    const domain=domainPlan(ctx);if(domain)return domain;
    return null;
  }
  async function execute(plan,ctx,fields,ack=async()=>({ok:true}),canContinue=()=>true) {
    const active=()=>{if(!canContinue())throw new Error('vault locked');};active();
    if(plan.verify&&!plan.verify())throw new Error('page target changed');
    if(plan.stage==='credentials') {if(plan.input)setValue(plan.input,fields.username);setValue(plan.password,fields.password);}
    else if(plan.input)setValue(plan.input,fields.value);
    if(plan.input&&plan.stage==='tenancy'&&plan.input.value.trim().toLowerCase()!==fields.value.trim().toLowerCase())throw new Error('tenancy input did not apply');
    if(plan.choice){active();plan.choice.click();await new Promise(r=>setTimeout(r,120));active();}
    if(plan.verify&&!plan.verify())throw new Error('session changed');
    const applied=await ack();active();if(!applied?.ok)throw new Error('step expired');
    if(ctx.mode==='fill')return;
    if(plan.radio){active();plan.radio.click();await new Promise(r=>setTimeout(r,120));active();}
    const action=plan.button||plan.submit;if(action){
      // Validation can enable an Oracle JET button only after fields are filled.
      // Do not require an enabled button before supplying those field values.
      const until=Math.min(ctx.expiresAt||Infinity,Date.now()+5000);
      do{await new Promise(r=>setTimeout(r,100));active();}while(action.isConnected&&!visible(action)&&Date.now()<until);
      if(plan.verify&&!plan.verify())throw new Error('session changed');
      if(!action.isConnected||!visible(action))throw new Error('submit unavailable');
      active();action.click();
    }
  }
  globalThis.OCILoginEngine={version:'2.0.0',describe,execute,visible};
})();
