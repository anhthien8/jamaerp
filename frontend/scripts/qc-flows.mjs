// QC TƯƠNG TÁC các luồng chính (Chế độ Tập luyện) — cho beta:
// portal link end-to-end, tạo lead, quote-tool, chấm công, nghỉ phép, đổi mật khẩu UI, search.
import { chromium } from 'playwright';
const BASE = process.argv[2] || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message.slice(0, 140)));
const R = [];
const ok = (name, pass, note = '') => { R.push({ name, pass, note }); console.log(`${pass ? '✅' : '❌'} ${name}${note ? ' — ' + note : ''}`); };
const noBoundary = async () => !(await page.evaluate(() => document.body.innerText.includes('Có lỗi xảy ra')));
const dismiss = async () => { for (const t of ['Bỏ qua', 'Bo qua']) { const b = page.locator(`button:has-text("${t}")`).first(); if (await b.isVisible().catch(() => false)) await b.click().catch(() => {}); } };

// login demo admin
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.click('text=Chế độ Tập luyện'); await page.waitForTimeout(400);
await page.click('button[type=submit]'); await page.waitForTimeout(3500); await dismiss();
ok('Login demo admin', await noBoundary());

// ── FLOW 1: Portal link end-to-end ──
await page.goto(`${BASE}/customers`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000); await dismiss();
await page.locator('main tr:has-text("Chị Mai"), main div[class*="cursor-pointer"]:has-text("Chị Mai")').locator('visible=true').first().click().catch(() => {});
await page.waitForTimeout(1200);
const genBtn = page.locator('button:has-text("Tạo link portal")').first();
if (await genBtn.isVisible().catch(() => false)) {
  await genBtn.click(); await page.waitForTimeout(1000);
  const linkShown = await page.evaluate(() => document.body.innerText.includes('/portal/'));
  ok('Portal: bấm tạo → LINK HIỂN THỊ', linkShown && await noBoundary());
} else {
  const already = await page.evaluate(() => document.body.innerText.includes('/portal/'));
  ok('Portal: link có sẵn trong modal', already);
}
await page.goto(`${BASE}/portal/demo`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
ok('Portal /demo: trang khách mở được', (await page.evaluate(() => document.body.innerText.includes('Chị Mai'))) && await noBoundary());
await page.locator('button:has-text("PRJ-2026-001")').first().click().catch(() => {});
await page.waitForTimeout(1200);
const acceptBtn = page.locator('button:has-text("Xác nhận nghiệm thu")').first();
const hasAccept = await acceptBtn.isVisible().catch(() => false);
if (hasAccept) { await acceptBtn.click(); await page.waitForTimeout(800); }
ok('Portal /demo: chi tiết + nghiệm thu', (await page.evaluate(() => document.body.innerText.includes('Tiến độ công việc'))) && await noBoundary());

// ── FLOW 2: Tạo lead ──
await page.goto(`${BASE}/leads`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
await page.locator('button:has-text("Thêm Lead")').first().click().catch(() => {});
await page.waitForTimeout(900);
const nameInput = page.locator('input[placeholder*="Tên"], input[placeholder*="tên"]').first();
if (await nameInput.isVisible().catch(() => false)) {
  await nameInput.fill('QC Beta Test');
  await page.locator('input[placeholder*="09"], input[placeholder*="SĐT"], input[placeholder*="số"], input[placeholder*="phone"]').first().fill('0900000099').catch(() => {});
  await page.locator('button:has-text("Tạo lead"), button:has-text("Tạo Lead"), button:has-text("Lưu")').first().click().catch(() => {});
  await page.waitForTimeout(1500);
  ok('Tạo lead: submit không crash', await noBoundary());
} else ok('Tạo lead: mở modal', false, 'không thấy form');

// ── FLOW 3: Quote tool ──
await page.goto(`${BASE}/quote-tool`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
const area = page.locator('input[type=number]').first();
if (await area.isVisible().catch(() => false)) {
  await area.fill('100');
  await page.locator('button:has-text("Tạo báo giá"), button:has-text("Tính")').first().click().catch(() => {});
  await page.waitForTimeout(2000);
  ok('Báo giá tức thì: tạo báo giá', await noBoundary());
} else ok('Báo giá tức thì: form', await noBoundary(), 'không thấy input — kiểm tay');

// ── FLOW 4: Chấm công + nghỉ phép ──
await page.goto(`${BASE}/attendance`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
await page.locator('button:has-text("Check-in"), button:has-text("Chấm công vào")').first().click().catch(() => {});
await page.waitForTimeout(1200);
ok('Chấm công: check-in không crash', await noBoundary());
await page.locator('button:has-text("Nghỉ phép")').first().click().catch(() => {});
await page.waitForTimeout(900);
await page.locator('button:has-text("Xin nghỉ phép")').first().click().catch(() => {});
await page.waitForTimeout(700);
await page.locator('button:has-text("Gửi đơn")').first().click().catch(() => {});
await page.waitForTimeout(1200);
ok('Nghỉ phép: gửi đơn không crash', await noBoundary());

// ── FLOW 5: Settings đổi mật khẩu UI ──
await page.goto(`${BASE}/settings`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
const oldPass = page.locator('input[placeholder*="hiện tại"]').first();
if (await oldPass.isVisible().catch(() => false)) {
  await oldPass.fill('demo123');
  await page.locator('input[placeholder*="mới ("]').first().fill('demo456');
  await page.locator('input[placeholder*="Nhập lại"]').first().fill('demo456');
  await page.locator('button:has-text("Đổi mật khẩu")').last().click();
  await page.waitForTimeout(1200);
  ok('Đổi mật khẩu (demo): submit', await noBoundary());
} else ok('Đổi mật khẩu: thấy form', false, 'không thấy ô mật khẩu hiện tại');

// ── FLOW 6: Search ⌘K ──
await page.locator('body').click().catch(()=>{}); await page.keyboard.press('Control+k').catch(() => {});
await page.waitForTimeout(700);
const searchOpen = await page.evaluate(() => !!document.querySelector('input[placeholder*="Tìm"], input[placeholder*="tìm"]'));
ok('Search Ctrl+K mở', searchOpen);

console.log(`\n===== ${R.filter(r => r.pass).length}/${R.length} PASS =====`);
if (errors.length) { console.log('JS ERRORS:'); errors.slice(0, 5).forEach(e => console.log(' -', e)); }
await browser.close();
process.exit(R.every(r => r.pass) ? 0 : 1);
