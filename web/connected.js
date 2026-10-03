'use strict';
const byId=id=>document.getElementById(id);
let csrf='',scope=null,pendingEvent=null,pendingUpload=null,generation=0,uploadRevision=0,entryRevision=0;
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
  const completeness=document.createElement('li');completeness.textContent='Entry completeness has not been verified. Check for income or expenses you have not entered. Add a missing transaction under Book entries; attach a missing receipt under Documents. Reviewing receipts does not confirm that every transaction is entered.';list.append(completeness);
  for(const id of draft.missing_receipts){const item=document.createElement('li');item.textContent='Missing receipt: '+id;list.append(item);}
  for(const id of draft.cash_explanations_missing){const item=document.createElement('li');item.textContent='Explain the cash entry: '+id;list.append(item);}
  const reviewReasons={not_reviewed:'Supporting information has not been reviewed',entry_changed:'The entry changed after review',document_changed:'The supporting document changed after review',needs_information:'The reviewer requested more information',receipt_required:'A current receipt is needed',cash_explanation_required:'Explain the cash entry'};
  for(const question of draft.support_review_queue||[]){const row=document.createElement('li');row.textContent=question.event_id+': '+question.reasons.map(reason=>reviewReasons[reason]||'Further review needed').join('; ');list.append(row);}
  if(draft.support_review_required.length&&!draft.support_review_queue){const item=document.createElement('li');item.textContent=draft.support_review_required.length+' entries still need their supporting information reviewed. A typed record ID does not establish reviewed support.';list.append(item);}
  const item=document.createElement('li');item.textContent='Confirm income, expense eligibility and support before final return preparation.';list.append(item);
  const entries=await loadEntries();if(current!==generation)return;
  await loadSupport(entries);
  if(current!==generation)return;
  status('Draft updated from recorded entries. Final tax calculations remain unavailable.');
}
function clearOpenCase({keepScopeForm=false}={}){
  generation++;uploadRevision++;entryRevision++;reviewRevision++;scope=null;
  pendingEvent=null;pendingUpload=null;pendingReview=null;canReview=false;supportEntries=[];
  byId('support-save').disabled=true;byId('support-access').textContent='Open permitted records to check review access.';
  for(const id of ['entry-form','document-form','support-form'])byId(id).reset();
  syncEntryMode();
  if(!keepScopeForm)byId('scope-form').reset();
  for(const id of ['support-history','support-entry','document-list','review-list','entry-history'])byId(id).replaceChildren();
  byId('support-document').replaceChildren(new Option('No document selected',''));
  byId('support-entry-detail').textContent='';byId('open-hatax').href='/tax';
  for(const id of ['income','expenses','profit','reserve','payments','revision','last-entry'])byId(id).textContent='—';
}
byId('scope-form').addEventListener('submit',async event=>{
  event.preventDefault();clearOpenCase({keepScopeForm:true});scope=Object.fromEntries(new FormData(event.target));
  byId('open-hatax').href='/tax?'+new URLSearchParams(scope);byId('support-access').textContent='Checking review access…';
  const current=generation;
  try{await refresh();if(current===generation)await listDocuments();}
  catch(error){if(current===generation)status(error.message);}
});
function syncEntryMode(){
  const form=byId('entry-form'),correction=form.elements.kind.value==='correction';
  form.elements.method.disabled=correction;form.elements.date.readOnly=correction&&Boolean(form.elements.date.value);form.elements.evidence.readOnly=correction;
  form.elements.date.required=!form.elements.date.readOnly;form.elements.reason.required=correction;
  byId('entry-correction-note').hidden=!correction;
  byId('entry-explanation-choice').hidden=!correction;
  const replacing=correction&&form.elements.explanation_mode.value==='replace';
  byId('entry-explanation-label').hidden=!replacing;form.elements.support_explanation.required=replacing;
}
byId('entry-form').elements.kind.addEventListener('change',syncEntryMode);
byId('entry-explanation-mode').addEventListener('change',syncEntryMode);
async function loadEntries(){
  const current=generation,list=byId('entry-history');list.replaceChildren();
  try{
    const result=await request('/api/connected/events?'+scopeQuery());if(current!==generation)return null;
    const replaced=new Set(result.events.filter(entry=>entry.kind==='correction').map(entry=>entry.replaces));
    const labels={income:'Business income',expense:'Business expense',owner_estimated_tax_payment:'Owner tax-payment record',employee_payroll_obligation:'Employee payroll obligation'};
    for(const entry of result.events){
      const item=document.createElement('li'),description=document.createElement('p');item.dataset.entry=entry.id;
      description.textContent=entry.posting_date+' | '+(labels[entry.effective_kind]||'Recorded entry')+' | '+money(entry.amount_minor)+' | '+(entry.category||'No category')+' | '+entry.id+' | '+(replaced.has(entry.id)?'Earlier entry':'Current entry');item.append(description);
      if(!replaced.has(entry.id)&&(['income','expense'].includes(entry.effective_kind)||(entry.effective_kind==='owner_estimated_tax_payment'&&entry.status==='recorded_unverified'&&!entry.government_confirmation))){
        const correct=document.createElement('button');correct.type='button';correct.textContent='Correct this entry';
        correct.onclick=()=>{
          if(current!==generation||!scope)return;
          const form=byId('entry-form');entryRevision++;pendingEvent=null;form.reset();
          form.elements.kind.value='correction';form.elements.replaces.value=entry.id;form.elements.date.value=entry.posting_date;
          form.elements.amount.value=Math.floor(entry.amount_minor/100)+'.'+String(entry.amount_minor%100).padStart(2,'0');
          form.elements.method.value=entry.method||'card';form.elements.category.value=entry.category||'';form.elements.evidence.value=entry.evidence||'';form.elements.support_explanation.value=typeof entry.explanation==='string'?entry.explanation:'';
          syncEntryMode();form.elements.reason.focus();status('Enter the corrected amount and a reason. The earlier entry will be preserved.');
        };item.append(correct);
      }
      list.append(item);
    }
    if(!result.events.length){const item=document.createElement('li');item.textContent='No entries recorded for this case yet.';list.append(item);}
    return result;
  }catch(error){if(current===generation){const item=document.createElement('li');item.textContent='Entry history could not be loaded.';list.append(item);}return {events:[]};}
}
byId('entry-form').addEventListener('input',()=>{entryRevision++;pendingEvent=null;});
byId('period-form').addEventListener('submit',async event=>{event.preventDefault();if(!scope){status('Open permitted records first.');return;}try{await refresh();}catch(error){status(error.message);}});
byId('entry-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!scope){status('Open a permitted client and business first.');return;}
  const values=Object.fromEntries(new FormData(event.target));
  if(!/^\d+(\.\d{1,2})?$/.test(values.amount)){status('Enter dollars and cents, for example 120.00.');return;}
  const [whole,cents='']=values.amount.split('.');const amount=Number(whole)*100+Number(cents.padEnd(2,'0'));
  if(!Number.isSafeInteger(amount)||amount>1e15){status('Amount is outside the supported range.');return;}
  if(!pendingEvent){const entered={id:crypto.randomUUID(),date:values.date,kind:values.kind,amount_minor:amount,method:values.method,category:values.category,evidence:values.evidence||null};
    if(values.kind==='correction'){entered.replaces=values.replaces;entered.reason=values.reason;
      if(values.explanation_mode==='replace')entered.support_changes={explanation:values.support_explanation};
      else if(values.explanation_mode==='clear')entered.support_changes={explanation:null};
    }
    if(values.kind==='owner_estimated_tax_payment'){entered.status='recorded_unverified';entered.government_confirmation=null;}
    if(values.method==='cash')entered.explanation=values.reason;
    pendingEvent={scope,event:entered};}
  const button=event.target.querySelector('button');button.disabled=true;
  const current=generation,revision=entryRevision,submission=pendingEvent;
  try{const saved=await request('/api/connected/events',submission);if(current!==generation)return;
    byId('last-entry').textContent='Saved entry ID: '+saved.id;
    if(pendingEvent===submission)pendingEvent=null;
    if(revision===entryRevision){event.target.reset();syncEntryMode();}
    await refresh();
    if(current===generation&&revision!==entryRevision)status('The earlier entry was saved. Your newer form changes remain; check the selected entry against the updated history.');
  }catch(error){if(current===generation)status(error.message+(revision===entryRevision?' Retry preserves the same entry ID.':' The earlier save failed; your newer form changes remain.'));}finally{button.disabled=false;}
});
async function listDocuments(){
  const current=generation;
  const list=byId('document-list');list.replaceChildren();
  try{const result=await request('/api/connected/documents?'+scopeQuery());if(current!==generation)return;
    const superseded=new Set(result.versions.map(version=>version.previous_version_id));
    for(const version of result.versions){
      const item=document.createElement('li');item.dataset.version=version.version_id;
      const description=document.createElement('p');description.textContent=version.document_id+' | '+version.created_at+' | '+(version.previous_version_id?'corrected version':'original')+' | '+(superseded.has(version.version_id)?'Earlier version':'Current version');item.append(description);
      const actions=document.createElement('div');actions.className='document-actions';
      const download=document.createElement('button');download.type='button';download.textContent='Download this version';download.onclick=()=>{if(current===generation)downloadDocument(version.document_id,version.version_id);};actions.append(download);
      if(!superseded.has(version.version_id)){
        const correct=document.createElement('button');correct.type='button';correct.textContent='Add a corrected version';
        correct.onclick=()=>{
          if(current!==generation||!scope)return;
          uploadRevision++;pendingUpload=null;byId('document-form').reset();byId('document-mode').value='correction';byId('correction-document').value=version.document_id;
          byId('correction-reason').focus();status('Explain what changed and choose the corrected file. The original will be preserved.');
        };actions.append(correct);
      }
      item.append(actions);list.append(item);
    }}
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
    pendingUpload=null;form.reset();await listDocuments();await refresh();
    if(current===generation)status(correction?'Corrected version saved. The original is preserved.':'Private document uploaded and linked to this case.');
  }catch(error){if(current===generation&&revision===uploadRevision)status(error.message);}finally{button.disabled=false;}
});
let caseGeneration=0;
async function loadCases(){
  const current=++caseGeneration;
  byId('case-open').disabled=true;byId('case-choice').replaceChildren(new Option('Checking access…',''));
  try{
    const result=await request('/api/connected/cases');if(current!==caseGeneration)return;
    if(scope&&!result.cases.some(item=>item.profile===scope.profile&&item.business===scope.business&&String(item.year)===String(scope.year))){
      clearOpenCase();status('Access to the open records is no longer available. Choose permitted records to continue.');
    }
    byId('case-choice').replaceChildren(new Option('Choose your records',''));
    for(const item of result.cases)byId('case-choice').append(new Option(item.profile+' · '+item.business+' · '+item.year,JSON.stringify(item)));
    byId('case-status').textContent=result.cases.length?'Choose a business and tax year to begin.':'No records are currently available through this session.';
    byId('case-open').disabled=!result.cases.length;
  }catch(error){if(current!==caseGeneration)return;clearOpenCase();status('Case access could not be confirmed. Reopen permitted records after refreshing access.');byId('case-choice').replaceChildren(new Option('Access unavailable',''));byId('case-status').textContent=error.message;}
}
byId('case-refresh').onclick=loadCases;
byId('case-form').addEventListener('submit',event=>{
  event.preventDefault();if(!byId('case-choice').value)return;
  const selected=JSON.parse(byId('case-choice').value),form=byId('scope-form');
  for(const name of ['profile','business','year'])form.elements[name].value=selected[name];
  form.requestSubmit();
});
byId('logout').addEventListener('click',async()=>{try{await request('/api/auth/logout',{});location.reload();}catch(error){status(error.message);}});
(async()=>{try{const health=await request('/api/health');if(!health.login_configured)byId('setup-message').textContent='Protected sign-in is not configured. This page cannot yet open client records.';
  const identity=await request('/api/auth/me');csrf=identity.csrf;byId('login-panel').hidden=true;byId('workspace').hidden=false;byId('logout').hidden=false;status('Signed in. Choose your permitted records.');await loadCases();
}catch(error){status(error.message);}})();

let supportEntries=[],pendingReview=null,reviewRevision=0,canReview=false;
function showSupportEntry(){
  const entry=supportEntries.find(e=>e.id===byId('support-entry').value);
  byId('support-entry-detail').textContent=entry?entry.posting_date+' · '+money(entry.amount_minor)+' · '+(entry.method||'Method not recorded')+' · '+(entry.category||'No category')+' · '+(entry.explanation||'No explanation'):'';
}
async function loadSupport(entries){
  const current=generation;pendingReview=null;canReview=false;byId('support-save').disabled=true;
  byId('support-entry').replaceChildren();byId('support-history').replaceChildren();
  byId('support-document').replaceChildren(new Option('No document selected',''));
  try{
    const [documents,history]=await Promise.all([
      request('/api/connected/documents?'+scopeQuery()),
      request('/api/connected/support/reviews?'+scopeQuery())]);
    if(current!==generation)return;
    canReview=history.can_review===true;byId('support-save').disabled=!canReview;byId('support-access').textContent=canReview?'You can record supporting-information decisions for this case.':'You can view supporting records. A permitted reviewer must record the decision.';
    const replaced=new Set(entries.events.filter(e=>e.kind==='correction').map(e=>e.replaces));
    supportEntries=entries.events.filter(e=>!replaced.has(e.id)&&['income','expense','employee_payroll_obligation'].includes(e.effective_kind));
    for(const e of supportEntries)byId('support-entry').append(new Option(e.posting_date+' · '+money(e.amount_minor)+' · '+e.id,e.id));
    const superseded=new Set(documents.versions.map(v=>v.previous_version_id));
    for(const v of documents.versions.filter(v=>!superseded.has(v.version_id)))byId('support-document').append(new Option(v.document_id+' · '+v.created_at,JSON.stringify([v.document_id,v.version_id])));
    for(const r of history.reviews){const item=document.createElement('li');item.textContent=r.recorded_at+' · '+r.event_id+' · '+(r.decision==='accepted'?'Support checked':'More information needed')+' · '+r.reason+' · '+r.actor;byId('support-history').append(item);}
    showSupportEntry();
  }catch(error){if(current===generation){byId('support-entry-detail').textContent=error.message;byId('support-access').textContent='Review access could not be confirmed.';}}
}
byId('support-entry').addEventListener('change',showSupportEntry);
byId('support-form').addEventListener('input',()=>{reviewRevision++;pendingReview=null;});
byId('support-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!scope||!canReview)return;
  const current=generation,revision=reviewRevision,button=byId('support-save');button.disabled=true;
  try{
    if(!pendingReview){const review={event_id:byId('support-entry').value,decision:byId('support-decision').value,reason:byId('support-reason').value,idempotency_key:crypto.randomUUID()};
      if(byId('support-document').value){const [document,version]=JSON.parse(byId('support-document').value);review.document_id=document;review.version_id=version;}
      pendingReview={scope:{...scope},review};}
    await request('/api/connected/support/reviews',pendingReview);
    if(current!==generation||revision!==reviewRevision)return;pendingReview=null;byId('support-reason').value='';await refresh();
    if(current===generation)status('Review decision recorded. Tax preparation and filing still require their own checks.');
  }catch(error){if(current===generation)status(error.message);}finally{button.disabled=!canReview;}
});

async function downloadDocument(documentId,version){
  if(!scope)return;
  const current=generation;
  try{const result=await request('/api/connected/document?'+scopeQuery()+'&'+new URLSearchParams({document:documentId,version}));
    if(current!==generation)return;
    const bytes=Uint8Array.from(atob(result.data),c=>c.charCodeAt(0));
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));
    const link=document.createElement('a');link.href=url;link.download='supporting-document';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){if(current===generation)status(error.message);}
}
byId('support-download').addEventListener('click',()=>{
  if(!scope||!byId('support-document').value){status('Select a document first.');return;}
  const [documentId,version]=JSON.parse(byId('support-document').value);downloadDocument(documentId,version);
});
