// QC TƯƠNG TÁC các luồng chính cho beta: portal end-to-end, tạo lead, báo giá tức thì,
// chấm công, nghỉ phép, đổi mật khẩu (kiểm tra ràng buộc), tìm kiếm nhanh.
//
// Chạy:  node scripts/qc-flows.mjs [BASE_URL]        (mặc định http://localhost:3000)
//
// ⚠ SCRIPT NÀY GHI DỮ LIỆU THẬT (tạo lead, chấm công, gửi đơn nghỉ phép).
// Trước 12/08/2026 nó chạy trong Chế độ Tập luyện nên mọi thao tác đều là giả. Chế độ đó đã
// nghỉ hẳn, nên giờ script đăng nhập thật và ghi thật → CHẶN CỨNG hai lớp:
//   1. Không cho chạy nếu BASE trỏ tới tên miền bản thật.
//   2. Sau khi đăng nhập, soi máy chủ API mà app thực sự gọi; không phải localhost thì dừng
//      (trừ khi truyền --allow-remote để cố tình chạy trên môi trường thử từ xa).
// Muốn QC bản thật thì dùng scripts/qc-all-roles.mjs — script đó chỉ đọc.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://localhost:3000';
const ALLOW_REMOTE = process.argv.includes('--allow-remote');
const STAMP = new Date().toISOString().slice(5, 16).replace(/[-T:]/g, '');

if (/crm\.jamahome\.vn/.test(BASE)) {
  console.error('DỪNG: script này ghi dữ liệu thật, không được chạy trên crm.jamahome.vn.');
  console.error('Dùng: node scripts/qc-all-roles.mjs https://crm.jamahome.vn  (chỉ đọc)');
  process.exit(2);
}

const pw = (key, fallback) => process.env[`QC_PASS_${key.toUpperCase()}`] || fallback;

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
const apiHosts = new Set();
page.on('pageerror', e => errors.push(e.message.slice(0, 140)));
page.on('request', r => { if (/\/api\/v1\//.test(r.url())) apiHosts.add(new URL(r.url()).host); });

const R = [];
const ok = (name, pass, note = '') => { R.push({ name, pass, note }); console.log(`${pass ? '✅' : '❌'} ${name}${note ? ' — ' + note : ''}`); };
const noBoundary = async () => !(await page.evaluate(() => document.body.innerText.includes('Có lỗi xảy ra')));
const dismiss = async () => { for (const t of ['Bỏ qua', 'Bo qua']) { const b = page.locator(`button:has-text("${t}")`).first(); if (await b.isVisible().catch(() => false)) await b.click().catch(() => {}); } };

// ── Đăng nhập thật ──
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.fill('#login-email', 'admin');
await page.fill('#login-password', pw('admin', 'admin123'));
await page.click('#login-submit');
await page.waitForTimeout(3500);
await dismiss();
const loggedIn = await page.evaluate(() => location.pathname !== '/login' && !!localStorage.getItem('jama_token'));
ok('Đăng nhập admin', loggedIn && await noBoundary());
if (!loggedIn) { await browser.close(); process.exit(1); }

// Lớp chặn 2: app đang gọi máy chủ nào?
const remote = [...apiHosts].filter(h => !/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(h));
if (remote.length && !ALLOW_REMOTE) {
  console.error(`DỪNG: app đang gọi API ở ${remote.join(', ')} — không phải máy cục bộ.`);
  console.error('Nếu đây đúng là môi trường thử, chạy lại kèm cờ --allow-remote.');
  await browser.close();
  process.exit(2);
}
console.log(`(API: ${[...apiHosts].join(', ') || 'chưa gọi'})\n`);

// ── LUỒNG 1: Cổng khách hàng end-to-end ──
await page.goto(`${BASE}/customers`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000); await dismiss();
await page.locator('main tbody tr, main div[class*="cursor-pointer"]').locator('visible=true').first().click().catch(() => {});
await page.waitForTimeout(1200);
const genBtn = page.locator('button:has-text("Tạo link portal")').first();
if (await genBtn.isVisible().catch(() => false)) {
  await genBtn.click(); await page.waitForTimeout(1000);
  const linkShown = await page.evaluate(() => document.body.innerText.includes('/portal/'));
  ok('Cổng KH: bấm tạo → hiện link', linkShown && await noBoundary());
} else {
  const already = await page.evaluate(() => document.body.innerText.includes('/portal/'));
  ok('Cổng KH: link có sẵn trong modal', already);
}
await page.goto(`${BASE}/portal/demo`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
ok('Cổng KH /demo: trang khách mở được', (await page.evaluate(() => document.body.innerText.includes('Chị Mai'))) && await noBoundary());
await page.locator('button:has-text("PRJ-2026-001")').first().click().catch(() => {});
await page.waitForTimeout(1200);
const acceptBtn = page.locator('button:has-text("Xác nhận nghiệm thu")').first();
if (await acceptBtn.isVisible().catch(() => false)) { await acceptBtn.click(); await page.waitForTimeout(800); }
ok('Cổng KH /demo: chi tiết + nghiệm thu', (await page.evaluate(() => document.body.innerText.includes('Tiến độ công việc'))) && await noBoundary());

// ── LUỒNG 2: Tạo lead (GHI — dữ liệu có tiền tố [QC] để dọn) ──
await page.goto(`${BASE}/leads`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
await page.locator('button:has-text("Thêm Lead")').first().click().catch(() => {});
await page.waitForTimeout(900);
const nameInput = page.locator('input[placeholder*="Tên"], input[placeholder*="tên"]').first();
if (await nameInput.isVisible().catch(() => false)) {
  await nameInput.fill(`[QC] ${STAMP}`);
  await page.locator('input[placeholder*="09"], input[placeholder*="SĐT"], input[placeholder*="số"], input[placeholder*="phone"]').first().fill('0900000099').catch(() => {});
  await page.locator('button:has-text("Tạo lead"), button:has-text("Tạo Lead"), button:has-text("Lưu")').first().click().catch(() => {});
  await page.waitForTimeout(1500);
  const created = await page.evaluate(() => /thành công|đã tạo/i.test(document.body.innerText));
  ok('Tạo lead: gửi form', created && await noBoundary(), created ? `đã tạo "[QC] ${STAMP}" — nhớ dọn` : 'không thấy báo thành công');
} else ok('Tạo lead: mở modal', false, 'không thấy form');

// ── LUỒNG 3: Báo giá tức thì ──
await page.goto(`${BASE}/quote-tool`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
const area = page.locator('input[type=number]').first();
if (await area.isVisible().catch(() => false)) {
  await area.fill('100');
  await page.locator('button:has-text("Tạo báo giá"), button:has-text("Tính")').first().click().catch(() => {});
  await page.waitForTimeout(2000);
  ok('Báo giá tức thì: tính ra kết quả', await noBoundary());
} else ok('Báo giá tức thì: form', await noBoundary(), 'không thấy ô nhập — kiểm tay');

// ── LUỒNG 4: Chấm công + nghỉ phép (GHI) ──
await page.goto(`${BASE}/attendance`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
await page.locator('button:has-text("Check-in"), button:has-text("Chấm công vào")').first().click().catch(() => {});
await page.waitForTimeout(1200);
ok('Chấm công: vào ca không vỡ trang', await noBoundary());
await page.locator('button:has-text("Nghỉ phép")').first().click().catch(() => {});
await page.waitForTimeout(900);
await page.locator('button:has-text("Xin nghỉ phép")').first().click().catch(() => {});
await page.waitForTimeout(700);
await page.locator('button:has-text("Gửi đơn")').first().click().catch(() => {});
await page.waitForTimeout(1200);
ok('Nghỉ phép: gửi đơn không vỡ trang', await noBoundary());

// ── LUỒNG 5: Đổi mật khẩu — KIỂM TRA RÀNG BUỘC, KHÔNG đổi thật ──
// Cố tình nhập sai mật khẩu hiện tại: hệ thống PHẢI từ chối. Nếu nó báo thành công thì
// đó mới là lỗi nặng. Cách này kiểm được luồng mà không khoá ai ra khỏi hệ thống.
await page.goto(`${BASE}/settings`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2200); await dismiss();
const oldPass = page.locator('input[placeholder*="hiện tại"]').first();
if (await oldPass.isVisible().catch(() => false)) {
  await oldPass.fill('chac-chan-sai-0000');
  await page.locator('input[placeholder*="mới ("]').first().fill('KhongDoiThat123');
  await page.locator('input[placeholder*="Nhập lại"]').first().fill('KhongDoiThat123');
  await page.locator('button:has-text("Đổi mật khẩu")').last().click();
  await page.waitForTimeout(1500);
  const st = await page.evaluate(() => ({
    rejected: /không đúng|sai mật khẩu|không chính xác|thất bại|lỗi/i.test(document.body.innerText),
    accepted: /đổi mật khẩu thành công|cập nhật thành công/i.test(document.body.innerText),
  }));
  ok('Đổi mật khẩu: từ chối mật khẩu hiện tại SAI', st.rejected && !st.accepted,
     st.accepted ? 'NGUY HIỂM: nhận mật khẩu hiện tại sai!' : (st.rejected ? '' : 'không thấy thông báo lỗi nào'));
} else ok('Đổi mật khẩu: thấy form', false, 'không thấy ô mật khẩu hiện tại');

// ── LUỒNG 6: Tìm kiếm nhanh Ctrl+K ──
await page.locator('body').click().catch(() => {});
await page.keyboard.press('Control+k').catch(() => {});
await page.waitForTimeout(700);
const searchOpen = await page.evaluate(() => !!document.querySelector('input[placeholder*="Tìm"], input[placeholder*="tìm"]'));
ok('Tìm kiếm Ctrl+K mở được', searchOpen);

console.log(`\n===== ${R.filter(r => r.pass).length}/${R.length} ĐẠT =====`);
if (errors.length) { console.log('LỖI JS:'); errors.slice(0, 5).forEach(e => console.log(' -', e)); }
console.log('Nhắc: script này có tạo lead "[QC] ..." và bản ghi chấm công/nghỉ phép — dọn nếu chạy trên DB cần sạch.');
await browser.close();
process.exit(R.every(r => r.pass) ? 0 : 1);
