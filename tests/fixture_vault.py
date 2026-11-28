"""Seed synthetic encrypted fixtures; unlock UI/migration is tested separately."""
PASSWORD='integration fixture vault passphrase'

async def seed_personal(page,profiles):
    await page.evaluate('''async(x)=>{
      const {lockVaults,lockEpoch,installVaultSession}=await import('./lib/vault-session.js');
      const {createVault}=await import('./lib/vault-crypto.js');
      await lockVaults();const token=await lockEpoch();const v=await createVault({schemaVersion:1,profiles:x.profiles},x.password);
      await chrome.storage.local.set({personalVault:v.envelope});await chrome.storage.local.remove('profiles');
      await installVaultSession(v.envelope.id,v.key,token);
    }''',{'profiles':profiles,'password':PASSWORD})

async def seed_team(page,profiles,bind=True):
    await page.evaluate('''async(x)=>{
      const {createVault,inspectVaultText,unlockVault,sealVault,envelopeText}=await import('./lib/vault-crypto.js');
      const {lockEpoch,installVaultSession}=await import('./lib/vault-session.js');
      const h=await(await navigator.storage.getDirectory()).getFileHandle('fixture-team.json',{create:true});
      const old=await(await h.getFile()).text();let v;
      if(old){const parsed=inspectVaultText(old);const key=await unlockVault(parsed.envelope,x.password);v={key,envelope:await sealVault(parsed.envelope,key,{schemaVersion:1,profiles:x.profiles})};}
      else v=await createVault({schemaVersion:1,profiles:x.profiles},x.password);
      const w=await h.createWritable();await w.write(envelopeText(v.envelope));await w.close();
      if(x.bind){await(await import('./lib/db.js')).handleSet(h);await installVaultSession(v.envelope.id,v.key,await lockEpoch());await chrome.storage.local.set({settings:{mode:'file',fileKind:'picker'}});}
    }''',{'profiles':profiles,'password':PASSWORD,'bind':bind})
