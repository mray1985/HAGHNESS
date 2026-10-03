// Actual disposable Keycloak screens; only HA callback is intercepted.
// This proves rendered enrollment, not an HA session or browser certificate trust.
const {chromium}=require(process.env.HA_PLAYWRIGHT_MODULE||'C:/Users/mitch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),crypto=require('node:crypto'),path=require('node:path'),fs=require('node:fs');
let stage='startup',failureView={otp_error_visible:false,password_screen_visible:false,setup_secret_submitted_matches:false,fresh_code_submitted_matches:false,fresh_code_differs_setup:false};
function otp(secret,now=Date.now()){const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(now/30000)));const digest=crypto.createHmac('sha1',secret).update(counter).digest();const offset=digest[digest.length-1]&15;return String((digest.readUInt32BE(offset)&0x7fffffff)%1000000).padStart(6,'0');}
if(process.argv.includes('--self-test')){
 const clock=Date.now;Date.now=()=>59000;assert.equal(otp('12345678901234567890'),'287082');Date.now=clock;console.log('RFC6238 SHA1 six-digit vector passed');
}else (async()=>{
 let raw='';for await(const chunk of process.stdin)raw+=chunk;const fixture=JSON.parse(raw);raw='';
 const clockOffset=fixture.server_time_ms-Date.now();assert.ok(Number.isFinite(clockOffset)&&Math.abs(clockOffset)<60000);const fixtureNow=()=>Date.now()+clockOffset;
 assert.equal(fixture.origin,'https://127.0.0.1:8843');assert.equal(fixture.username,'ha-fictional-rendered-enrollment');
 const browser=await chromium.launch({channel:'msedge',headless:true});let page;
 try{
  const context=await browser.newContext({ignoreHTTPSErrors:true});page=await context.newPage();
  const errors=[];page.on('pageerror',()=>errors.push('page error'));
  let callbacks=0,state='';
  await page.route('https://127.0.0.1:8844/api/auth/callback?*',async route=>{
   const query=new URL(route.request().url()).searchParams;assert.equal(query.get('state'),state);assert.equal(query.getAll('code').length,1);assert.ok(!query.has('error'));callbacks++;
   await route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>Fictional enrollment callback</title><p>Fictional verification completed. No HA session created.</p>'});
  });
  async function destination(field){const action=new URL(await page.locator('form').filter({has:page.locator('[name='+field+']')}).getAttribute('action'),page.url());assert.equal(action.origin,fixture.origin);assert.ok(action.pathname.startsWith('/realms/ha/login-actions/'));}
  async function login(){
   const fresh=stage==='fresh-login';
   state=crypto.randomBytes(24).toString('base64url');const verifier=crypto.randomBytes(32).toString('base64url');
   const parameters=new URLSearchParams({client_id:'ha-connected',redirect_uri:'https://127.0.0.1:8844/api/auth/callback',response_type:'code',scope:'openid',state,nonce:crypto.randomBytes(24).toString('base64url'),max_age:'0',code_challenge_method:'S256',code_challenge:crypto.createHash('sha256').update(verifier).digest('base64url'),claims:JSON.stringify({id_token:{acr:{essential:true,values:['2']}}})});
   await page.goto(fixture.origin+'/realms/ha/protocol/openid-connect/auth?'+parameters);
   if(fresh)stage='fresh-password';await page.locator('[name=password]').waitFor();await destination('password');
   await page.locator('[name=username]').fill(fixture.username);await page.locator('[name=password]').fill(fixture.password);
   await page.locator('input[type=submit],button[type=submit]').first().click();
  }
  stage='setup';await login();await page.locator('[name=totp]').waitFor();await destination('totp');
  assert.ok(await page.title());assert.equal(callbacks,0);assert.ok(await page.locator('#kc-totp-settings').isVisible());assert.ok(await page.locator('#kc-totp-secret-qr-code').isVisible());
  let secret=await page.locator('[name=totpSecret]').inputValue();assert.ok(secret.length>=20&&secret.length<=128);
  const setupSecret=secret;let expectedFresh='',setupCode='',setupCounter=0;
  page.on('request',request=>{
   const url=new URL(request.url());if(request.method()!=='POST'||url.origin!==fixture.origin||!url.pathname.startsWith('/realms/ha/login-actions/'))return;
   const values=new URLSearchParams(request.postData()||'');
   if(values.has('totpSecret'))failureView.setup_secret_submitted_matches=values.get('totpSecret')===setupSecret;
   if(values.has('otp')&&expectedFresh)failureView.fresh_code_submitted_matches=values.get('otp')===expectedFresh;
  });
  // Mask the entire QR/instructions section and code field; never save secrets.
  const screenshot=path.join(__dirname,'..','output','otp-enrollment-masked.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});
  await page.screenshot({path:screenshot,mask:[page.locator('#kc-totp-settings'),page.locator('[name=totp]')]});
  stage='invalid-setup';await page.locator('[name=totp]').fill(String((Number(otp(secret,fixtureNow()))+1)%1000000).padStart(6,'0'));
  await page.locator('[name=userLabel]').fill('Fictional browser device');await page.locator('input[type=submit],button[type=submit]').first().click();
  stage='invalid-feedback';await page.locator('#input-error-otp-code').waitFor();assert.equal(callbacks,0);assert.equal(await page.locator('[name=totpSecret]').inputValue(),secret);await destination('totp');
  stage='valid-setup';setupCounter=Math.floor(fixtureNow()/30000);setupCode=otp(secret,fixtureNow());await page.locator('[name=totp]').fill(setupCode);await page.locator('input[type=submit],button[type=submit]').first().click();
  stage='setup-callback';await page.waitForURL('https://127.0.0.1:8844/api/auth/callback?*');assert.equal(callbacks,1);
  await new Promise(resolve=>setTimeout(resolve,45000-fixtureNow()%30000));
  await context.clearCookies(); // Fresh browser session, not a reauthentication screen using existing SSO.
  stage='fresh-login';await login();stage='fresh-otp';await page.locator('[name=otp]').waitFor();await destination('otp');assert.equal(callbacks,1);
  // Clock originates in the Linux identity fixture, carried privately through stdin.
  assert.ok(Math.floor(fixtureNow()/30000)>setupCounter);
  const clockDifference=Math.floor(Date.now()/30000)!==Math.floor(fixtureNow()/30000);
  expectedFresh=otp(secret,fixtureNow());failureView.fresh_code_differs_setup=expectedFresh!==setupCode;assert.ok(failureView.fresh_code_differs_setup);
  await page.locator('[name=otp]').fill(expectedFresh);secret='';fixture.password='';await page.locator('input[type=submit],button[type=submit]').first().click();
  stage='fresh-callback';await page.waitForURL('https://127.0.0.1:8844/api/auth/callback?*');stage='callback-count';assert.equal(callbacks,2);stage='page-errors';assert.deepEqual(errors,[]);
  console.log(JSON.stringify({setup_instructions_and_qr_rendered:true,invalid_setup_code_keeps_challenge:true,valid_setup_completes:true,fresh_password_requires_otp:true,fresh_enrolled_otp_completes:true,client_server_counter_differed:clockDifference,code_clock:'Linux identity fixture timestamp; Windows/WSL fixture only',identity_routes_mocked:false,ha_callback:'intercepted only for rendered fixture; no HA session claim',browser_certificate_trust:'not verified; disposable self-signed fixture',screenshot:'masked setup evidence; QR/instructions and code field concealed',page_errors:errors}));
 }catch(error){
  if(page){
   failureView={...failureView,otp_error_visible:await page.locator('#input-error-otp-code').isVisible().catch(()=>false),password_screen_visible:await page.locator('[name=password]').isVisible().catch(()=>false)};
   await page.screenshot({path:path.join(__dirname,'..','output','otp-enrollment-failure-masked.png'),fullPage:true,mask:[page.locator('#kc-totp-settings'),page.locator('[name=otp]'),page.locator('[name=totp]'),page.locator('[name=password]'),page.locator('[name=username]')]}).catch(()=>{});
  }
  throw error;
 }finally{await browser.close();}
})().catch(error=>{const kind=['TimeoutError','AssertionError'].includes(error.name)?error.name:'Error';console.error(JSON.stringify({stage,error:'rendered enrollment verification failed',kind,...failureView}));process.exitCode=1;});
