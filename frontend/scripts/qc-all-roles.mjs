// QC toàn bộ 6 vai trò trên bản chạy thật: đăng nhập thật, đi từng trang, bắt crash + lỗi JS
// + MỌI phản hồi API >= 400 (bài học 12/08: trang trông vẫn "sạch" trong khi API chết 19 ngày),
// rồi thử mở phần tử đầu tiên để chắc chắn trang không vỡ khi tương tác.
//
// Chạy:  node scripts/qc-all-roles.mjs [BASE_URL]
// Mặc định chạy trên https://crm.jamahome.vn.
//
// CHỈ ĐỌC — không tạo/sửa/xoá dữ liệu. Bước thử tương tác cố tình bỏ qua mọi nút có chữ
// mang tính thay đổi dữ liệu (Xóa, Duyệt, Gửi, Lưu...) để an toàn khi chạy trên bản thật.
//
// Chế độ Tập luyện đã nghỉ hẳn 12/08/2026 (SHOW_DEMO_MODE=false) nên script chỉ còn
// đăng nhập thật; vòng lặp mode demo cũ đã bỏ.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'https://crm.jamahome.vn';

// Mật khẩu lấy từ biến môi trường nếu có (vd QC_PASS_ADMIN), không thì dùng mật khẩu seed.
const pw = (key, fallback) => process.env[`QC_PASS_${key.toUpperCase()}`] || fallback;

// Danh sách vai trò CÓ THẬT trên bản chạy (đối chiếu GET /users ngày 12/08/2026).
// Bản cũ liệt kê 'executive' và 'sales' — trên prod KHÔNG có vai trò executive
// (ceo@jamahome.vn thực chất là admin) và sales@jamahome.vn là data_entry, nên script
// báo LOGIN_FAIL oan và bỏ sót hẳn admin_cskh (3 người, nhóm dùng nhiều nhất).
const ROLES = [
  { key: 'admin',      user: 'admin@jamahome.vn',      pass: pw('admin', 'admin123'),        pages: ['/', '/leads', '/projects', '/pl', '/attendance', '/approvals', '/settings', '/users', '/permissions', '/hr', '/customers', '/contracts', '/quotations', '/inventory', '/suppliers', '/accounting', '/finance', '/kpi', '/reports', '/feedback', '/changelog'] },
  { key: 'leader',     user: 'leader@jamahome.vn',     pass: pw('leader', 'leader123'),      pages: ['/', '/leads', '/projects', '/attendance', '/approvals', '/hr', '/accounting', '/reports', '/kpi', '/settings', '/customers', '/contracts', '/quotations'] },
  { key: 'data_entry', user: 'sales@jamahome.vn',      pass: pw('sales', 'sales123'),        pages: ['/', '/leads', '/projects', '/attendance', '/approvals', '/accounting', '/reports', '/quotations', '/quote-tool', '/settings', '/customers', '/contracts'] },
  { key: 'accountant', user: 'accountant@jamahome.vn', pass: pw('accountant', 'account123'), pages: ['/', '/accounting', '/finance', '/pl', '/hr', '/attendance', '/approvals', '/inventory', '/suppliers', '/reports', '/settings', '/contracts', '/quotations', '/customers'] },
  { key: 'supervisor', user: 'supervisor@jamahome.vn', pass: pw('supervisor', 'super123'),   pages: ['/', '/projects', '/inventory', '/quotations', '/attendance', '/approvals', '/kpi', '/reports', '/settings', '/contracts', '/customers'] },
  // Điều phối KD (vai trò tùy chỉnh, bộ phận SALES). Mật khẩu do người dùng tự đổi nên KHÔNG
  // có mặc định — không đặt QC_PASS_CSKH thì bỏ qua hẳn, tránh báo LOGIN_FAIL giả.
  { key: 'admin_cskh', user: 'ngochanh@jamahome.vn',   pass: process.env.QC_PASS_CSKH || '', pages: ['/', '/leads', '/customers', '/quotations', '/quote-tool', '/reports', '/kpi', '/feedback', '/settings'] },
];

// Chữ trên nút = thao tác THAY ĐỔI dữ liệu → không bao giờ bấm thử.
const DESTRUCTIVE = /xóa|xoá|duyệt|từ chối|gửi|lưu|chốt|hủy|huỷ|đóng ca|kết thúc|thanh toán|tạo|thêm|sửa|chỉnh|cập nhật|phân công|giao|đổi/i;

const browser = await chromium.launch();
const results = [];
let workLogins = 0;

async function dismissOverlays(page) {
  for (const label of ['Bỏ qua', 'Bo qua']) {
    const btn = page.locator(`button:has-text("${label}")`).first();
    if (await btn.isVisible().catch(() => false)) await btn.click().catch(() => {});
  }
}

async function qcRole(role) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errors = [];
  const apiFails = [];
  page.on('pageerror', e => errors.push(e.message.slice(0, 160)));
  page.on('console', m => { if (m.type() === 'error') errors.push(`[console] ${m.text().slice(0, 140)}`); });
  // Bài học 12/08: trang có thể "trông ổn" trong khi API chết → luôn soi mã phản hồi.
  page.on('response', r => {
    if (r.status() >= 400 && /\/api\//.test(r.url())) {
      apiFails.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, '').slice(0, 90)}`);
    }
  });

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  // Backend chặn 5 lần đăng nhập/phút → nghỉ giữa chừng cho khỏi bị 429 báo nhầm thành lỗi.
  if (workLogins > 0 && workLogins % 4 === 0) { console.log('   (nghỉ 65s né giới hạn đăng nhập...)'); await page.waitForTimeout(65000); }
  workLogins++;
  await page.fill('#login-email', role.user);
  await page.fill('#login-password', role.pass);
  apiFails.length = 0;
  await page.click('#login-submit');
  await page.waitForTimeout(4500);

  const loggedIn = await page.evaluate(() => location.pathname !== '/login' && !!localStorage.getItem('jama_token'));
  if (!loggedIn) {
    const errTxt = await page.evaluate(() => document.body.innerText.slice(0, 120).replace(/\n+/g, ' '));
    results.push({ role: role.key, page: '(đăng nhập)', status: 'LOGIN_FAIL', detail: errTxt, apiFails: apiFails.splice(0) });
    await ctx.close();
    return;
  }

  for (const p of role.pages) {
    apiFails.length = 0;
    await page.goto(`${BASE}${p}`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1800);
    await dismissOverlays(page);
    let s = await page.evaluate(() => ({
      boundary: !!document.querySelector('[data-error-boundary]'),
      // Thẻ lỗi tải dữ liệu của các trang (không phải error boundary)
      loadError: /Không thể tải|Vui lòng thử lại|Đã xảy ra lỗi/.test(document.body.innerText),
      detail: (document.querySelector('.font-mono.break-all') || {}).textContent || null,
    }));
    let interacted = false;
    if (!s.boundary) {
      const el = page.locator('main [class*="cursor-pointer"], main tbody tr').first();
      const txt = await el.innerText({ timeout: 1500 }).catch(() => '');
      if (txt && !DESTRUCTIVE.test(txt) && await el.isVisible().catch(() => false)) {
        await el.click({ timeout: 2000 }).catch(() => {});
        interacted = true;
        await page.waitForTimeout(1200);
        s = await page.evaluate(() => ({
          boundary: !!document.querySelector('[data-error-boundary]'),
          loadError: /Không thể tải|Vui lòng thử lại|Đã xảy ra lỗi/.test(document.body.innerText),
          detail: (document.querySelector('.font-mono.break-all') || {}).textContent || null,
        }));
        await page.keyboard.press('Escape').catch(() => {});
        // Nhiều modal của app không bắt Escape — click backdrop góc cho chắc.
        if (await page.locator('.fixed.inset-0.z-50').first().isVisible({ timeout: 500 }).catch(() => false)) {
          await page.mouse.click(8, 8).catch(() => {});
        }
      }
    }
    const fails = apiFails.splice(0);
    const status = s.boundary ? 'CRASH' : fails.length ? 'API_FAIL' : s.loadError ? 'LOAD_ERROR' : 'OK';
    results.push({ role: role.key, page: p, status, interacted, detail: s.detail, jsErrors: errors.splice(0).slice(0, 2), apiFails: fails.slice(0, 4) });
  }
  await ctx.close();
}

for (const role of ROLES) {
  if (!role.pass) {
    console.log(`=== QC ${role.key} === BỎ QUA (chưa đặt mật khẩu — xuất QC_PASS_CSKH để quét vai trò này)`);
    continue;
  }
  console.log(`=== QC ${role.key} ===`);
  await qcRole(role);
  const rr = results.filter(r => r.role === role.key);
  const fails = rr.filter(r => r.status !== 'OK');
  console.log(`   ${rr.length - fails.length}/${rr.length} OK${fails.length ? ' — LỖI: ' + fails.map(f => `${f.page}(${f.status})`).join(', ') : ''}`);
  for (const f of fails) {
    if (f.apiFails && f.apiFails.length) console.log(`   [api] ${f.page}: ${f.apiFails.join(' | ')}`);
    if (f.detail) console.log(`   [chi tiết] ${f.page}: ${String(f.detail).slice(0, 120)}`);
  }
  for (const w of rr.filter(r => r.jsErrors && r.jsErrors.length)) console.log(`   [jsError] ${w.page}: ${w.jsErrors.join(' | ')}`);
}

const totalFail = results.filter(r => r.status !== 'OK');
console.log(`\n===== TỔNG KẾT: ${results.length - totalFail.length}/${results.length} OK, ${totalFail.length} LỖI =====`);
for (const f of totalFail) console.log(`LỖI ${f.role}${f.page}: ${f.status} ${(f.apiFails || []).join(' | ')} ${f.detail || ''}`);
await browser.close();
process.exit(totalFail.length ? 1 : 0);
