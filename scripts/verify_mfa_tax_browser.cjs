// Rendered HATax against the live local MFA fixture; no mocked API routes.
// Receive the temporary session through stdin only. Never persist browser state.
const {chromium}=require(process.env.HA_PLAYWRIGHT_MODULE || 'C:/Users/mitch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
let stage='startup';
(async()=>{
  const started=performance.now();
  let raw='';for await(const chunk of process.stdin)raw+=chunk;
  const fixture=JSON.parse(raw);raw='';
  assert.equal(fixture.origin,'https://127.0.0.1:8844');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    // The disposable certificate is self-signed. Protocol verification runs
    // separately with an explicitly trusted CA; this browser probe does not
    // provide browser certificate-trust evidence.
    const context=await browser.newContext({ignoreHTTPSErrors:true});
    await context.addCookies([{name:'__Host-ha_session',value:fixture.cookie,
      domain:'127.0.0.1',path:'/',secure:true,httpOnly:true,sameSite:'Lax'}]);
    fixture.cookie='';
    const page=await context.newPage();const errors=[];
    page.on('pageerror',()=>errors.push('page error'));
    stage='books-open';
    await page.goto(fixture.origin+'/connected.html');
    await page.locator('#workspace').waitFor({state:'visible'});
    await page.locator('#scope-form [name=profile]').fill('orchard');
    await page.locator('#scope-form [name=business]').fill('business');
    await page.locator('#scope-form button').click();
    await page.waitForFunction(()=>document.querySelector('#document-list').children.length===4);
    stage='book-totals';
    assert.equal(await page.locator('#income').innerText(),'$1,500.00');
    assert.equal(await page.locator('#expenses').innerText(),'$320.00');
    assert.equal(await page.locator('#profit').innerText(),'$1,180.00');
    assert.match(await page.locator('#payments').innerText(),/recorded: \$100\.00.*confirmed: \$0\.00/);
    assert.match(await page.locator('#review-list').innerText(),/advertising:.*supporting document changed/);
    stage='period-totals';
    for(const period of ['month','quarter','year']){
      await page.locator('#period').selectOption(period);
      const updated=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/connected/draft');
      await page.locator('#period-form button').click();
      const response=await updated;assert.equal(response.status(),200);
      assert.equal((await response.json()).book_profit_minor,118000);
      await page.waitForLoadState('networkidle');
      assert.equal(await page.locator('#profit').innerText(),'$1,180.00');
      assert.equal(await page.locator('#expenses').innerText(),'$320.00');
    }
    stage='document-download';
    await page.locator('#support-document').selectOption(JSON.stringify([fixture.document,fixture.version]));
    const download=page.waitForEvent('download');
    await page.locator('#support-download').click();
    const stream=await (await download).createReadStream();let bytes=[];
    for await(const chunk of stream)bytes.push(chunk);
    assert.equal(Buffer.concat(bytes).toString(),'Fictional receipt correction');
    stage='foreign-scope';
    await page.locator('#scope-form [name=profile]').fill('cedar');
    await page.locator('#scope-form [name=business]').fill('cedar-business');
    await page.locator('#scope-form button').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='Resource unavailable');
    assert.equal(await page.locator('#profit').innerText(),'\u2014');
    assert.equal(await page.locator('#document-list li').count(),0);
    await page.locator('#scope-form [name=profile]').fill('orchard');
    await page.locator('#scope-form [name=business]').fill('business');
    await page.locator('#scope-form button').click();
    await page.waitForFunction(()=>document.querySelector('#document-list').children.length===4);
    stage='tax-handoff';
    await page.locator('#open-hatax').click();
    assert.equal(new URL(page.url()).pathname,'/tax');
    stage='tax-reopen';
    await page.locator('#tax-saving').waitFor({state:'visible'});
    await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    assert.equal(await page.locator('#save-input').isDisabled(),true);
    await page.locator('#reopen-input').click();
    await page.waitForFunction(()=>document.querySelector('[name=firstName]')?.value==='Fictional tax corrected');
    stage='tax-save';
    await page.locator('[name=firstName]').fill('Fictional browser correction');
    await page.locator('#save-reason').fill('Rendered browser correction with real MFA session');
    const saved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/connected/tax/inputs'&&r.request().method()==='POST');
    await page.locator('#save-input').click();assert.equal((await saved).status(),201);
    await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    stage='tax-reload';
    await page.reload();await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    await page.locator('#reopen-input').click();
    await page.waitForFunction(()=>document.querySelector('[name=firstName]')?.value==='Fictional browser correction');
    assert.equal(await page.locator('#saved-version option').count(),4);
    assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({rendered_tax_save_reload_reopen:'passed',rendered_books_periods_documents_handoff:'passed',
      rendered_foreign_scope_clears_data:true,api_mocking:false,
      authentication:'reused actual MFA-created opaque cookie',browser_certificate_trust:'not verified; disposable self-signed fixture',
      browser_storage_empty:true,mobile_overflow:false,
      elapsed_seconds:Math.round((performance.now()-started)/100)/10,
      timing_scope:'single local fictional browser run, excludes MFA/runtime startup'}));
  }finally{await browser.close();}
})().catch(()=>{console.error('Rendered local MFA tax verification failed at '+stage);process.exitCode=1;});
