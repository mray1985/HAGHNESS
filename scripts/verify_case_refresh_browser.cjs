const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.HA_PLAYWRIGHT_MODULE);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let granted=true,late=false,unavailable=false,release,started;
 const scope={profile:'orchard',business:'business',year:2026};
 const draft={income_minor:150000,expense_minor:32000,book_profit_minor:118000,ledger_revision:1,source_event_ids:['fictional'],reserve_scenario_minor:37500,owner_payments_recorded_minor:10000,owner_payments_confirmed_minor:0,missing_receipts:['fictional'],cash_explanations_missing:[],support_review_required:[]};
 await page.route('http://127.0.0.1:9876/**',async route=>{
  const url=new URL(route.request().url());let data;
  if(url.pathname==='/api/health')data={login_configured:true};
  else if(url.pathname==='/api/auth/me')data={csrf:'fictional'};
  else if(url.pathname==='/api/connected/cases'){if(unavailable)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Resource unavailable'})});data={cases:granted?[scope]:[]};}
  else if(url.pathname==='/api/connected/draft'){
   if(late){started();await new Promise(resolve=>release=resolve);}
   data=draft;
  }
  else if(url.pathname==='/api/connected/events')data={events:[]};
  else if(url.pathname==='/api/connected/documents')data={versions:[{document_id:'fictional-receipt',version_id:'v1',created_at:'2026-10-02'}]};
  else if(url.pathname==='/api/connected/support/reviews')data={can_review:true,reviews:[]};
  else if(['/connected.html','/connected.css','/connected.js'].includes(url.pathname))return route.fulfill({status:200,contentType:url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(path.join('web',url.pathname.slice(1)))});
  else throw Error('Unexpected fixture request '+url.pathname);
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('http://127.0.0.1:9876/connected.html');assert.match(await page.title(),/Connected review/);
 await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===2);
 await page.selectOption('#case-choice',JSON.stringify(scope));await page.click('#case-open');
 await page.waitForFunction(()=>document.querySelector('#profit').textContent==='$1,180.00'&&document.querySelector('#document-list').children.length===1);
 await page.fill('#support-reason','Fictional confidential note');
 await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===2);assert.equal(await page.textContent('#profit'),'$1,180.00');assert.equal(await page.inputValue('#support-reason'),'Fictional confidential note');
 granted=false;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===1&&!document.querySelector('#case-choice').textContent.includes('Checking'));
 assert.equal(await page.textContent('#profit'),'—');assert.equal(await page.locator('#document-list li').count(),0);assert.equal(await page.locator('#review-list li').count(),0);assert.equal(await page.inputValue('#support-reason'),'');assert.equal(await page.inputValue('#scope-form [name=profile]'),'');assert.equal(await page.inputValue('#scope-form [name=business]'),'');assert.equal(await page.getAttribute('#open-hatax','href'),'/tax');assert.equal(await page.isDisabled('#support-save'),true);
 granted=true;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===2);
 late=true;const began=new Promise(resolve=>started=resolve);await page.selectOption('#case-choice',JSON.stringify(scope));await page.click('#case-open');await began;
 granted=false;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-open').disabled&&document.querySelector('#case-status').textContent.includes('No records'));
 release();await page.waitForLoadState('networkidle');assert.equal(await page.textContent('#profit'),'—');assert.equal(await page.locator('#document-list li').count(),0);assert.deepEqual(errors,[]);
 late=false;granted=true;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-choice').options.length===2);await page.selectOption('#case-choice',JSON.stringify(scope));await page.click('#case-open');await page.waitForFunction(()=>document.querySelector('#profit').textContent==='$1,180.00');
 unavailable=true;await page.click('#case-refresh');await page.waitForFunction(()=>document.querySelector('#case-choice').textContent==='Access unavailable');assert.equal(await page.textContent('#profit'),'—');assert.equal(await page.locator('#document-list li').count(),0);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:process.env.HA_CASE_REFRESH_SCREENSHOT||'output/case-access-refresh.png',fullPage:true});
 console.log(JSON.stringify({fixture:'rendered UI with synthetic API responses; no authentication claim',revoked_case_cleared:true,late_response_ignored:true,valid_refresh_preserves_work:true,unavailable_access_cleared:true,mobile_overflow:false,page_errors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
