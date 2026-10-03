// Fictional browser regression checks. Does not prove hosted MFA.
const {chromium}=require('C:/Users/mitch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage();const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    let release;
    const delayed=new Promise(resolve=>release=resolve);
    await page.route('**/api/**',async route=>{
      const url=new URL(route.request().url());
      let body={};let status=200;
      if(url.pathname==='/api/health')body={login_configured:true};
      else if(url.pathname==='/api/auth/me')body={csrf:'fictional-test-only'};
      else if(url.pathname==='/api/connected/cases')body={cases:[]};
      else if(url.pathname==='/api/connected/documents')body={versions:[]};
      else if(url.pathname==='/api/connected/draft'){
        if(url.searchParams.get('profile')==='first')await delayed;
        else {status=404;body={error:'Resource unavailable'};}
        if(status===200)body={income_minor:150000,expense_minor:32000,book_profit_minor:118000,
          ledger_revision:6,source_event_ids:[],reserve_scenario_minor:37500,
          owner_payments_recorded_minor:10000,owner_payments_confirmed_minor:0,missing_receipts:[]};
      }
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
    });
    await page.goto('http://127.0.0.1:8766/');
    await page.locator('#workspace').waitFor({state:'visible'});
    await page.locator('#manual-scope summary').click();
    await page.locator('[name=profile]').fill('first');
    await page.locator('[name=business]').fill('business');
    await page.locator('#scope-form button').click();
    await page.locator('[name=profile]').fill('denied');
    await page.locator('#scope-form button').click();
    await page.waitForFunction(()=>document.getElementById('status').textContent==='Resource unavailable');
    release();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#income').innerText(),'—');
    assert.equal(await page.locator('#profit').innerText(),'—');
    assert.equal(await page.locator('#status').innerText(),'Resource unavailable');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log('PASS: reversed responses and denied scope cannot show earlier client totals; mobile fits; no page errors. Synthetic API only.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
