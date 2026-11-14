// Headless check of the NUI chat panel (no game needed). Run: node tools/nui_check.js
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const posts = [];
  await page.route('https://jw_ainpc/**', (route) => { posts.push([route.request().url(), route.request().postData()]); route.fulfill({ body: '"ok"' }); });
  await page.goto('file://' + path.resolve(__dirname, '../jw_ainpc/html/index.html'));
  const send = (d) => page.evaluate((d) => window.postMessage(d, '*'), d);
  await send({ action: 'open', npcId: 'bar', name: 'Vinnie', role: 'bartender', maxChars: 200, strings: { placeholder: 'Say something...', send: 'Send', close_hint: 'ESC to leave', typing: 'is typing', dir: 'ltr' } });
  await page.waitForSelector('#panel:not(.hidden)');
  await page.fill('#input', 'Any gossip?');
  await page.press('#input', 'Enter');
  await page.waitForSelector('#typing:not(.hidden)');
  await send({ action: 'reply', npcId: 'bar', text: '<img src=x onerror=alert(1)> Quiet night, pal.' });
  await page.waitForSelector('.msg.them');
  const html = await page.$eval('.msg.them', (e) => e.innerHTML);
  if (html.includes('<img')) throw new Error('XSS: reply rendered as HTML');
  await page.waitForTimeout(400);
  await page.screenshot({ path: process.argv[2] || 'nui.png' });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  const urls = posts.map((p) => p[0]);
  if (!urls.some((u) => u.endsWith('/send'))) throw new Error('send not posted');
  if (!urls.some((u) => u.endsWith('/close'))) throw new Error('close not posted on ESC');
  console.log('NUI CHECK PASSED', JSON.stringify(posts));
  await browser.close();
})().catch((e) => { console.error('NUI CHECK FAILED', e); process.exit(1); });
