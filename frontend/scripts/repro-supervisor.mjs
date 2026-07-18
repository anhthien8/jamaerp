// Repro lỗi supervisor trên production: login thật qua UI → bắt pageerror/console.
// Chạy: node scripts/repro-supervisor.mjs [baseUrl]
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'https://frontend-jet-two-86.vercel.app';

const browser = await chromium.launch();
const page = await browser.newPage();

const errors = [];
page.on('pageerror', (err) => errors.push(`[pageerror] ${err.message}\n${(err.stack || '').split('\n').slice(0, 6).join('\n')}`));
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`[console.error] ${msg.text().slice(0, 500)}`);
});

console.log('1. Mở login...');
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });

console.log('2. Điền supervisor/super123 (Work mode mặc định)...');
await page.fill('#login-email', 'supervisor');
await page.fill('#login-password', 'super123');
await page.click('button[type=submit]');

console.log('3. Chờ điều hướng sau login...');
await page.waitForTimeout(6000);

const state = await page.evaluate(() => ({
  path: location.pathname,
  hasBoundary: document.body.innerText.includes('Có lỗi xảy ra'),
  boundaryDetail: (document.querySelector('.font-mono.break-all') || {}).textContent || null,
  bodySample: document.body.innerText.slice(0, 200).replace(/\n+/g, ' | '),
}));
console.log('TRẠNG THÁI:', JSON.stringify(state, null, 1));

console.log('\n=== LỖI BẮT ĐƯỢC (' + errors.length + ') ===');
for (const e of errors) console.log(e, '\n---');

// Điều hướng thêm vài trang chính nếu chưa crash
if (!state.hasBoundary) {
  for (const p of ['/projects', '/attendance', '/settings']) {
    await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(2500);
    const s = await page.evaluate(() => ({ path: location.pathname, boundary: document.body.innerText.includes('Có lỗi xảy ra') }));
    console.log(`page ${p}:`, JSON.stringify(s));
    if (s.boundary) break;
  }
  console.log('\n=== LỖI SAU KHI ĐIỀU HƯỚNG (' + errors.length + ') ===');
  for (const e of errors) console.log(e, '\n---');
}

await browser.close();
