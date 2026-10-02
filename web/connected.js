'use strict';
const byId=id=>document.getElementById(id);
let csrf='',scope=null,pendingEvent=null,pendingUpload=null,generation=0,uploadRevision=0;
const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value/100);
function status(message){byId('status').textContent=message;}
async function request(path,body){
  const options={credentials:'same-origin',headers:{}};
  if(body){options.method='POST';options.headers={'Content-Type':'application/json','X-HA-CSRF':csrf};options.body=JSON.stringify(body);}
  const response=await fetch(path,options);const result=await response.json();
  if(!response.ok)throw new Error(result.error||'This request could not be completed.');
  return result;
}
function scopeQuery(){return new URLSearchParams(scope).toString();}
async function refresh(){
  const current=generation;
  const draft=await request('/api/connected/draft?'+scopeQuery()+'&'+new URLSearchParams({period:byId('period').value,month:byId('month').value}));
  if(current!==generation)return;
  byId('income').textContent=money(draft.income_minor);byId('expenses').textContent=money(draft.expense_minor);byId('profit').textContent=money(draft.book_profit_minor);
  byId('revision').textContent='Ledger revision '+draft.ledger_revision+' · source entries: '+draft.source_event_ids.join(', ');
  byId('reserve').textContent='Optional 25% of recorded receipts reserve scenario: '+money(draft.reserve_scenario_minor)+'. No money moved.';
  byId('payments').textContent='Owner payments recorded: '+money(draft.owner_payments_recorded_minor)+' · government-confirmed: '+money(draft.owner_payments_confirmed_minor);
  const list=byId('review-list');list.replaceChildren();
  for(const id of draft.missing_receipts){const item=document.createElement('li');item.textContent='Missing receipt: '+id;list.append(item);}
  for(const id of draft.cash_explanations_missing){const item=document.createElement('li');item.textContent='Explain the cash entry: '+id;list.append(item);}
  if(draft.support_review_required.length){const item=document.createElement('li');item.textContent=draft.support_review_required.length+' entries still need their supporting information reviewed. A typed record ID does not establish reviewed support.';list.append(item);}
  const item=document.createElement('li');item.textContent='Confirm income, expense eligibility and support before final return preparation.';list.append(item);
  status('Draft updated from recorded entries. Final tax calculations remain unavailable.');
}
byId('scope-form').addEventListener('submit',async event=>{event.preventDefault();generation++;uploadRevision++;pendingEvent=null;pendingUpload=null;scope=Object.fromEntries(new FormData(event.target));byId('open-hatax').href='/tax?'+new URLSearchParams(scope);for(const id of ['income','expenses','profit','reserve','payments','revision','last-entry'])byId(id).textContent='—';byId('document-list').replaceChildren();byId('review-list').replaceChildren();const current=generation;try{await refresh();if(current===generation)await listDocuments();}catch(error){if(current===generation)status(error.message);}});
byId('entry-form').addEventListener('input',()=>{pendingEvent=null;});
byId('period-form').addEventListener('submit',async event=>{event.preventDefault();if(!scope){status('Open permitted records first.');return;}try{await refresh();}catch(error){status(error.message);}});
byId('entry-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!scope){status('Open a permitted client and business first.');return;}
  const values=Object.fromEntries(new FormData(event.target));
  if(!/^\d+(\.\d{1,2})?$/.test(values.amount)){status('Enter dollars and cents, for example 120.00.');return;}
  const [whole,cents='']=values.amount.split('.');const amount=Number(whole)*100+Number(cents.padEnd(2,'0'));
  if(!Number.isSafeInteger(amount)||amount>1e15){status('Amount is outside the supported range.');return;}
  if(!pendingEvent){const entered={id:crypto.randomUUID(),date:values.date,kind:values.kind,amount_minor:amount,method:values.method,category:values.category,evidence:values.evidence||null};
    if(values.kind==='correction'){entered.replaces=values.replaces;entered.reason=values.reason;}
    if(values.kind==='owner_estimated_tax_payment'){entered.status='recorded_unverified';entered.government_confirmation=null;}
    if(values.method==='cash')entered.explanation=values.reason;
    pendingEvent={scope,event:entered};}
  const button=event.target.querySelector('button');button.disabled=true;
  const current=generation;
  try{const saved=await request('/api/connected/events',pendingEvent);if(current!==generation)return;byId('last-entry').textContent='Saved entry ID: '+saved.id;pendingEvent=null;event.target.reset();await refresh();}
  catch(error){if(current===generation)status(error.message+' Retry preserves the same entry ID.');}finally{button.disabled=false;}
});
async function listDocuments(){
  const current=generation;
  const list=byId('document-list');list.replaceChildren();
  try{const result=await request('/api/connected/documents?'+scopeQuery());if(current!==generation)return;for(const version of result.versions){const item=document.createElement('li');item.textContent=version.document_id+' · '+version.created_at+' · '+(version.previous_version_id?'corrected version':'original');list.append(item);}}
  catch(error){if(current!==generation)return;const item=document.createElement('li');item.textContent=error.message;list.append(item);}
}
byId('document-form').addEventListener('input',()=>{uploadRevision++;pendingUpload=null;});
byId('document-form').addEventListener('change',()=>{uploadRevision++;pendingUpload=null;});
byId('document-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!scope){status('Open a permitted client and business first.');return;}
  const form=event.target;const file=form.elements.file.files[0];
  if(!file||file.size>20*1024*1024){status('Choose a file no larger than 20 MiB.');return;}
  const correction=form.elements.mode.value==='correction';
  const documentId=form.elements.document.value.trim(),reason=form.elements.reason.value.trim();
  if(correction&&(!documentId||!reason)){status('Enter the original document ID and explain what changed.');return;}
  const button=form.querySelector('button');button.disabled=true;
  const current=generation,revision=uploadRevision,uploadScope={...scope};
  const path=correction?'/api/connected/document/corrections':'/api/connected/documents';
  try{if(!pendingUpload){const bytes=new Uint8Array(await file.arrayBuffer());
      if(current!==generation||revision!==uploadRevision)return;
      let raw='';for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));
      pendingUpload={scope:uploadScope,mime:file.type,data:btoa(raw),idempotency_key:crypto.randomUUID()};
      if(correction){pendingUpload.document=documentId;pendingUpload.reason=reason;}}
    if(current!==generation||revision!==uploadRevision)return;
    await request(path,pendingUpload);
    if(current!==generation||revision!==uploadRevision)return;
    pendingUpload=null;form.reset();await listDocuments();
    if(current===generation)status(correction?'Corrected version saved. The original is preserved.':'Private document uploaded and linked to this case.');
  }catch(error){if(current===generation&&revision===uploadRevision)status(error.message);}finally{button.disabled=false;}
});
byId('logout').addEventListener('click',async()=>{try{await request('/api/auth/logout',{});location.reload();}catch(error){status(error.message);}});
(async()=>{try{const health=await request('/api/health');if(!health.login_configured)byId('setup-message').textContent='Protected sign-in is not configured. This page cannot yet open client records.';
  const identity=await request('/api/auth/me');csrf=identity.csrf;byId('login-panel').hidden=true;byId('workspace').hidden=false;byId('logout').hidden=false;status('Signed in. Open a client and business you are permitted to access.');
}catch(error){status(error.message);}})();
