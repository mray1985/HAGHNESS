// Rendered HATax against the live local MFA fixture; no mocked API routes.
// Receive the temporary session through stdin only. Never persist browser state.
const {chromium}=require(process.env.HA_PLAYWRIGHT_MODULE || 'C:/Users/mitch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
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
    await page.goto(fixture.origin+'/tax?profile=orchard&business=business&year=2026');
    await page.locator('#tax-saving').waitFor({state:'visible'});
    await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    assert.equal(await page.locator('#save-input').isDisabled(),true);
    await page.locator('#reopen-input').click();
    await page.waitForFunction(()=>document.querySelector('[name=firstName]')?.value==='Fictional tax corrected');
    await page.locator('[name=firstName]').fill('Fictional browser correction');
    await page.locator('#save-reason').fill('Rendered browser correction with real MFA session');
    const saved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/connected/tax/inputs'&&r.request().method()==='POST');
    await page.locator('#save-input').click();assert.equal((await saved).status(),201);
    await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    await page.reload();await page.waitForFunction(()=>!document.querySelector('#reopen-input').disabled);
    await page.locator('#reopen-input').click();
    await page.waitForFunction(()=>document.querySelector('[name=firstName]')?.value==='Fictional browser correction');
    assert.equal(await page.locator('#saved-version option').count(),4);
    assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({rendered_tax_save_reload_reopen:'passed',api_mocking:false,
      authentication:'reused actual MFA-created opaque cookie',browser_certificate_trust:'not verified; disposable self-signed fixture',
      browser_storage_empty:true,mobile_overflow:false}));
  }finally{await browser.close();}
})().catch(()=>{console.error('Rendered local MFA tax verification failed');process.exitCode=1;});
