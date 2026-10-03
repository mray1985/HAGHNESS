// Run against fictional local previews. No hosted login or real client facts.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const taxOrigin = process.env.HA_TAX_URL || 'http://127.0.0.1:8765';
const booksOrigin = process.env.HA_BOOKS_URL || 'http://127.0.0.1:8766';
(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.HA_BROWSER_EXECUTABLE ? {executablePath:process.env.HA_BROWSER_EXECUTABLE} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1024,height:1536}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(taxOrigin+'/');
    await page.waitForLoadState('networkidle');
    assert.match(await page.locator('#purpose-title').innerText(), /Good help brings understanding/);
    assert.equal(await page.locator('h1').count(), 1);
    assert.equal(await page.locator('#learn .learning-card').count(), 4);
    const guides = page.locator('#learn details');
    for (let i = 0; i < await guides.count(); i++) {
      await guides.nth(i).locator('summary').focus();
      await page.keyboard.press('Enter');
      assert.equal(await guides.nth(i).getAttribute('open'), '');
      assert.equal(await guides.nth(i).locator('.guide-next').isVisible(), true);
      await page.keyboard.press('Enter');
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const screenshotDir = process.env.HA_SCREENSHOT_DIR;
    if (screenshotDir) {
      fs.mkdirSync(screenshotDir,{recursive:true});
      await page.screenshot({path:path.join(screenshotDir,'desktop.png'),fullPage:true});
    }
    await page.locator('nav [data-open-previews]').click();
    await page.locator('#preview-dialog').waitFor({state:'visible'});
    assert.match(await page.locator('#preview-dialog [data-tax-link]').getAttribute('href'), /\/tax$/);
    assert.match(await page.locator('#preview-dialog [data-books-link]').getAttribute('href'), /:8766\/connected.html$/);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#preview-dialog').isVisible(),false);
    assert.equal(await page.evaluate(() => document.activeElement.hasAttribute('data-open-previews')),true);
    await page.locator('.faq details summary').first().click();
    assert.equal(await page.locator('.faq details').first().getAttribute('open'),'');
    await page.locator('.faq details summary').first().click();
    for (const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
      await page.locator('.menu-button').click();
      assert.equal(await page.locator('.menu-button').getAttribute('aria-expanded'),'true');
      await page.locator('nav a[href="#services"]').click();
      assert.equal(await page.locator('.menu-button').getAttribute('aria-expanded'),'false');
      await page.locator('#understand-your-taxes summary').click();
      assert.equal(await page.locator('#understand-your-taxes .guide-next').isVisible(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
      await page.locator('#understand-your-taxes summary').click();
      await page.locator('#purpose [data-open-previews]').click();
      assert.equal(await page.evaluate(() => document.querySelector('dialog').scrollWidth > document.querySelector('dialog').clientWidth),false);
      await page.locator('.dialog-close').click();
      await page.evaluate(() => scrollTo(0,0));
      if (screenshotDir && width===390) await page.screenshot({path:path.join(screenshotDir,'mobile.png'),fullPage:true});
    }
    await page.setViewportSize({width:1280,height:900});
    await page.goto(taxOrigin+'/');
    await page.locator('nav [data-open-previews]').click();
    await page.locator('#preview-dialog [data-tax-link]').click();
    await page.locator('nav[aria-label="Return steps"]').waitFor({state:'visible'});
    assert.match(await page.title(), /HATax/);
    await page.locator('a[aria-label="Return to HA home"]').click();
    await page.locator('nav [data-open-previews]').click();
    // Cross-service default is the documented standard port. The verifier
    // supports isolated ephemeral services without claiming that default is live.
    await page.goto(booksOrigin+'/connected.html');
    await page.locator('#login-panel').waitFor({state:'visible'});
    assert.equal(await page.locator('#workspace').isVisible(),false);
    await page.locator('a[aria-label="Return to HA home"]').click();
    await page.locator('nav [data-open-previews]').click();
    await page.waitForFunction(() => document.querySelector('#preview-dialog [data-tax-link]').getAttribute('href') === '/tax');
    assert.equal(await page.locator('#preview-dialog [data-books-link]').getAttribute('href'),'/connected.html');
    await page.locator('#preview-dialog [data-tax-link]').click();
    assert.equal(new URL(page.url()).origin, booksOrigin);
    await page.locator('a[href="/connected.html"]').waitFor({state:'visible'});
    await page.locator('nav[aria-label="Return steps"]').waitFor({state:'visible'});
    await page.locator('a[aria-label="Return to HA home"]').click();
    await page.locator('nav [data-open-previews]').click();
    await page.keyboard.press('Escape');
    assert.deepEqual(errors, []);

    // Hosted-mode checks use the actual static files and synthetic health only.
    const hosted = await browser.newPage();
    let healthCase = {};
    await hosted.route('https://ha.example/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/api/health') return route.fulfill({status:healthCase.failed?503:200,
        contentType:'application/json',body:JSON.stringify(healthCase.health)});
      const file = url.pathname==='/'?'home.html':url.pathname.slice(1);
      if (!['home.html','home.js','home.css'].includes(file)) return route.fulfill({status:404,body:'Not found'});
      return route.fulfill({contentType:{html:'text/html',js:'text/javascript',css:'text/css'}[file.split('.').pop()],body:fs.readFileSync(path.join(root,'web',file))});
    });
    for (const scenario of [
      {health:{connected:true,tax_workspace:true,login_configured:false},tax:true,books:true},
      {health:{connected:true,login_configured:false},tax:false,books:true},
      {health:{connected:false,tax_workspace:true},tax:true,books:false},
      {failed:true,health:{},tax:false,books:false}
    ]) {
      healthCase=scenario;
      await hosted.goto('https://ha.example/');
      await hosted.waitForLoadState('networkidle');
      assert.equal(await hosted.locator('#preview-dialog [data-tax-link]').getAttribute('href'), scenario.tax?'/tax':null);
      assert.equal(await hosted.locator('#preview-dialog [data-books-link]').getAttribute('href'), scenario.books?'/connected.html':null);
      for (const link of await hosted.locator('#preview-dialog a[href]').all()) {
        assert.equal(new URL(await link.evaluate(el=>el.href)).origin,'https://ha.example');
      }
    }
    const noJS = await browser.newPage({javaScriptEnabled:false});
    await noJS.goto(taxOrigin+'/');
    assert.equal(await noJS.locator('#previews').isVisible(),true);
    await noJS.locator('#get-help summary').click();
    assert.equal(await noJS.locator('#get-help .guide-next').isVisible(),true);
    await noJS.locator('.faq details summary').first().click();
    assert.equal(await noJS.locator('.faq details').first().getAttribute('open'),'');
    console.log('PASS: desktop/mobile, educational guides with keyboard and no-JS access, menu, FAQ, modal focus/escape, both preview paths with current connected HATax, protected locked entrance, and hosted unavailable destinations.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
