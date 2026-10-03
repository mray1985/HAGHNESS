const assert = require('node:assert/strict');
const { chromium } = require('C:/Users/mitch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(process.env.HA_TAX_BROWSER_URL || 'http://127.0.0.1:8770/tax');
    const profile = {
      firstName: 'Fictional', lastName: 'Example', ssn: '000-00-0000',
      birthday: '1990-01-01', address: '123 Example Street', city: 'Example',
      state: 'LA', zip: '70701'
    };
    for (const [name, value] of Object.entries(profile)) {
      await page.locator(`#profile-form [name="${name}"]`).fill(value);
    }
    await page.getByRole('button', { name: 'Continue to your forms' }).click();
    const names = () => page.locator('#catalog [data-form]').evaluateAll(
      elements => elements.map(element => element.dataset.form));
    assert.deepEqual(await names(), [
      'K-1 (1041)', 'K-1 (1065)', 'K-1 (1120-S)', 'RRB-1099',
      'Schedule 1', 'Schedule 2', 'Schedule 3', 'Schedule C', 'Schedule E',
      'Schedule F', 'SSA-1099', 'W-2', 'W-2G',
      '1095-A', '1098', '1098-E', '1098-T', '1099-B', '1099-DIV',
      '1099-G', '1099-INT', '1099-K', '1099-MISC', '1099-NEC',
      '1099-OID', '1099-Q', '1099-R', '1099-S', '5498'
    ]);
    await page.locator('#form-search').fill('1099');
    assert.deepEqual((await names()).slice(0, 2), ['RRB-1099', 'SSA-1099']);
    await page.locator('#form-search').fill('Schedule');
    assert.deepEqual(await names(), ['Schedule 1', 'Schedule 2', 'Schedule 3',
      'Schedule C', 'Schedule E', 'Schedule F']);
    await page.locator('#form-search').fill('');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.locator('#catalog [data-form="W-2"]').click();
    assert.match(await page.locator('#content').innerText(), /W.?2/);
    console.log('PASS: letter-first form catalog, numeric suffixes, filtered order, mobile fit and W-2 selection.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
