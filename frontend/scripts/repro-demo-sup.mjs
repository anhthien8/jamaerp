import { chromium } from 'playwright';
const BASE = process.argv[2] || 'https://frontend-jet-two-86.vercel.app';
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(`[pageerror] ${e.message}\n${(e.stack||'').split('\n').slice(0,5).join('\n')}`));
page.on('console', m => { if (m.type()==='error') errors.push(`[console] ${m.text().slice(0,300)}`); });

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
// Chuyển Demo mode rồi login supervisor demo
await page.click('text=Chế độ Tập luyện');
await page.waitForTimeout(500);
await page.fill('#login-email', 'supervisor@jamahome.vn');
await page.fill('#login-password', 'demo123');
await page.click('button[type=submit]');
await page.waitForTimeout(5000);
const s = await page.evaluate(() => ({ path: location.pathname, boundary: document.body.innerText.includes('Có lỗi xảy ra'), detail: (document.querySelector('.font-mono.break-all')||{}).textContent||null, sample: document.body.innerText.slice(0,150).replace(/\n+/g,' | ') }));
console.log('DEMO SUPERVISOR:', JSON.stringify(s, null, 1));
console.log('ERRORS('+errors.length+'):'); errors.forEach(e=>console.log(e,'\n---'));
if (!s.boundary) {
  for (const p of ['/projects','/attendance','/settings','/quotations','/inventory','/kpi']) {
    await page.goto(`${BASE}${p}`).catch(()=>{});
    await page.waitForTimeout(2000);
    const r = await page.evaluate(() => ({ path: location.pathname, boundary: document.body.innerText.includes('Có lỗi xảy ra'), detail: (document.querySelector('.font-mono.break-all')||{}).textContent||null }));
    console.log(p, JSON.stringify(r));
    if (r.boundary) break;
  }
  console.log('ERRORS sau điều hướng ('+errors.length+'):'); errors.forEach(e=>console.log(e,'\n---'));
}
await browser.close();
