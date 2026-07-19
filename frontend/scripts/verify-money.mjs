import { chromium } from 'playwright';
const BASE = process.argv[2] || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('pageerror', e => console.log('[pageerror]', e.message.slice(0,120)));
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.click('text=Chế độ Tập luyện');
await page.waitForTimeout(400);
await page.click('button[type=submit]');
await page.waitForTimeout(3500);
// bỏ overlay tour/onboard
for (const t of ['Bỏ qua','Bo qua']) { const b = page.locator(`button:has-text("${t}")`).first(); if (await b.isVisible().catch(()=>false)) await b.click().catch(()=>{}); }
await page.goto(`${BASE}/projects`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
for (const t of ['Bỏ qua','Bo qua']) { const b = page.locator(`button:has-text("${t}")`).first(); if (await b.isVisible().catch(()=>false)) await b.click().catch(()=>{}); }
// mở card dự án đầu → nút Chỉnh sửa
const card = page.locator('main div:has-text("PRJ-2026")[class*="cursor-pointer"], main [class*="cursor-pointer"]:has-text("PRJ-")').first();
await card.click().catch(()=>{});
await page.waitForTimeout(1500);
const editBtn = page.locator('button:has-text("Chỉnh sửa")').first();
if (await editBtn.isVisible().catch(()=>false)) {
  await editBtn.click();
  await page.waitForTimeout(1000);
  const info = await page.evaluate(() => {
    const modal = [...document.querySelectorAll('div')].find(d => d.textContent?.includes('Chỉnh sửa dự án') && d.querySelector('input'));
    if (!modal) return 'no modal';
    const inputs = [...modal.querySelectorAll('input[type=number]')].map(i => i.value);
    const preview = [...modal.querySelectorAll('p')].filter(p => p.textContent?.startsWith('= ')).map(p => p.textContent);
    const labels = [...modal.querySelectorAll('label')].map(l => l.textContent).filter(t => t?.includes('nghìn đồng'));
    return { numberInputs: inputs, previews: preview, nghinLabels: labels };
  });
  console.log('MODAL:', JSON.stringify(info, null, 1));
} else console.log('không thấy nút Chỉnh sửa');
await browser.close();
