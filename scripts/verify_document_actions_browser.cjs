// Rendered document controls with fictional API responses; no MFA/storage claim.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.HA_PLAYWRIGHT_MODULE);
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage();page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',()=>errors.push('page error'));
 const scope={profile:'orchard',business:'business',year:2026};let granted=true,delay=false,release,started,downloads=0;
 page.on('download',()=>downloads++);
 const versions=[{document_id:'fictional-receipt',version_id:'v1',created_at:'2026-10-02',previous_version_id:null},{document_id:'fictional-receipt',version_id:'v2',created_at:'2026-10-03',previous_version_id:'v1'}];
 await page.route('http://127.0.0.1:9877/**',async route=>{const url=new URL(route.request().url());let data;
  if(url.pathname==='/api/health')data={login_configured:true};
  else if(url.pathname==='/api/auth/me')data={csrf:'fictional'};
  else if(url.pathname==='/api/connected/cases')data={cases:granted?[scope]:[]};
  else if(url.pathname==='/api/connected/draft')data={income_minor:0,expense_minor:0,book_profit_minor:0,ledger_revision:0,source_event_ids:[],reserve_scenario_minor:0,owner_payments_recorded_minor:0,owner_payments_confirmed_minor:0,missing_receipts:[],cash_explanations_missing:[],support_review_required:[]};
  else if(url.pathname==='/api/connected/events')data={events:[]};
  else if(url.pathname==='/api/connected/documents')data={versions};
  else if(url.pathname==='/api/connected/support/reviews')data={can_review:false,reviews:[]};
  else if(url.pathname==='/api/connected/document'){
   assert.equal(url.searchParams.get('profile'),scope.profile);assert.equal(url.searchParams.get('business'),scope.business);assert.equal(url.searchParams.get('year'),'2026');assert.equal(url.searchParams.get('document'),'fictional-receipt');
   if(delay){started();await new Promise(resolve=>release=resolve);}
   data={data:Buffer.from(url.searchParams.get('version')==='v1'?'Fictional original':'Fictional correction').toString('base64')};
  }else if(['/connected.html','/connected.css','/connected.js'].includes(url.pathname))return route.fulfill({status:200,contentType:url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(path.join('web',url.pathname.slice(1)))});
  else throw Error('Unexpected fixture request');
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('http://127.0.0.1:9877/connected.html');await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===2);await page.selectOption('#case-choice',JSON.stringify(scope));await page.click('#case-open');
 await page.waitForFunction(()=>document.querySelector('#document-list').children.length===2);
 const rows=page.locator('#document-list li');assert.match(await rows.nth(0).innerText(),/Earlier version/);assert.match(await rows.nth(1).innerText(),/Current version/);
 assert.equal(await rows.nth(0).getByRole('button',{name:'Add a corrected version'}).count(),0);
 for(const [index,expected] of [[0,'Fictional original'],[1,'Fictional correction']]){const pending=page.waitForEvent('download');await rows.nth(index).getByRole('button',{name:'Download this version'}).click();const stream=await(await pending).createReadStream();const bytes=[];for await(const chunk of stream)bytes.push(chunk);assert.equal(Buffer.concat(bytes).toString(),expected);}
 await page.fill('#correction-reason','Old reason');await page.setInputFiles('#document-form [name=file]',{name:'fictional.txt',mimeType:'text/plain',buffer:Buffer.from('Fictional old selection')});
 await rows.nth(1).getByRole('button',{name:'Add a corrected version'}).click();assert.equal(await page.inputValue('#document-mode'),'correction');assert.equal(await page.inputValue('#correction-document'),'fictional-receipt');assert.equal(await page.inputValue('#correction-reason'),'');assert.equal(await page.inputValue('#document-form [name=file]'),'');
 delay=true;const begun=new Promise(resolve=>started=resolve);await rows.nth(0).getByRole('button',{name:'Download this version'}).click();await begun;granted=false;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#document-list').children.length===0);release();await page.waitForLoadState('networkidle');assert.equal(downloads,2);assert.equal(await page.inputValue('#correction-document'),'');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({fixture:'synthetic API only',original_and_correction_download_exact:true,current_version_correction_prefilled:true,old_file_and_reason_cleared:true,revoked_case_late_download_ignored:true,mobile_overflow:false,page_errors:errors}));
}finally{await browser.close();}})().catch(error=>{console.error(error.message);process.exitCode=1;});
