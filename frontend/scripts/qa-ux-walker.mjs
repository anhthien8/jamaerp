// QA UX walker: 6 vai trò × (desktop + điện thoại). Máy dò tự động + chụp màn hình toàn bộ.
//
// Chạy:  node scripts/qa-ux-walker.mjs [BASE_URL]
// Mặc định https://crm.jamahome.vn. Kết quả JSON: H:/tmp/qa-ux/walker-report.json
//
// AN TOÀN DỮ LIỆU: mặc định CHỈ ĐỌC. Bước dò form (mở modal Tạo và bấm gửi khi trống) chỉ chạy
// khi BASE không phải bản chạy thật VÀ có cờ --probe-forms. Trên bản thật, gửi form trống mà
// backend thiếu ràng buộc sẽ đẻ ra bản ghi rác — không đánh đổi.
//
// Chế độ Tập luyện đã nghỉ hẳn 12/08/2026 nên walker đăng nhập thật; mật khẩu có thể truyền
// qua biến môi trường QC_PASS_<VAI_TRÒ> thay cho mật khẩu seed mặc định.
import { chromium } from 'playwright';
import fs from 'fs';

const BASE = process.argv[2] || 'https://crm.jamahome.vn';
const OUT = 'H:/tmp/qa-ux';
const IS_PROD = /crm\.jamahome\.vn|vercel\.app/.test(BASE);
const PROBE_FORMS = process.argv.includes('--probe-forms') && !IS_PROD;

const pw = (key, fallback) => process.env[`QC_PASS_${key.toUpperCase()}`] || fallback;

const ROLES = [
  { key: 'admin', user: 'admin', pass: pw('admin', 'admin123'), pages: ['/', '/leads', '/projects', '/pl', '/attendance', '/approvals', '/settings', '/users', '/permissions', '/hr', '/customers', '/contracts', '/quotations', '/inventory', '/suppliers', '/accounting', '/finance', '/kpi', '/reports', '/feedback'] },
  { key: 'executive', user: 'ceo', pass: pw('ceo', 'ceo123'), pages: ['/', '/pl', '/reports', '/kpi', '/feedback'] },
  { key: 'leader', user: 'leader', pass: pw('leader', 'leader123'), pages: ['/', '/leads', '/projects', '/hr', '/accounting', '/kpi'] },
  { key: 'sales', user: 'sales', pass: pw('sales', 'sales123'), pages: ['/', '/leads', '/quote-tool', '/quotations', '/customers', '/contracts'] },
  { key: 'accountant', user: 'accountant', pass: pw('accountant', 'account123'), pages: ['/', '/accounting', '/finance', '/pl', '/hr', '/inventory', '/contracts'] },
  { key: 'supervisor', user: 'supervisor', pass: pw('supervisor', 'super123'), pages: ['/', '/projects', '/inventory', '/attendance', '/approvals'] },
];

// Từ tiếng Anh hay sót trong UI (word-boundary, phân biệt hoa thường có chủ đích)
const EN_WORDS = ['Save', 'Cancel', 'Delete', 'Submit', 'Search', 'Loading', 'Error', 'Success', 'No data', 'Select', 'Status', 'Total', 'Edit', 'Add new', 'Close', 'Confirm', 'Required', 'Invalid', 'Failed', 'Name', 'Date', 'Amount', 'Description'];
// Nhiễu hợp lệ (thương hiệu, thuật ngữ đã chốt giữ tiếng Anh)
const EN_ALLOW = /JAMA|HOME|CRM|ERP|Zalo|Telegram|Google|Email|Dashboard|Kanban|Lead|KPI|OT|PIT|P&L|BOD|Portal|OK|Demo|Beta|Chat|App|Web|Admin|Sales|Deal|Pipeline|Import|Export|Excel|PDF|Logo|URL|QR|Bot|AI|Token|Feedback/gi;

const findings = [];
const browser = await chromium.launch();
let logins = 0;

fs.mkdirSync(OUT, { recursive: true });
for (const r of ROLES) fs.mkdirSync(`${OUT}/${r.key}`, { recursive: true });

async function login(page, role) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  // Backend giới hạn 5 lần đăng nhập/phút — nghỉ cho khỏi bị 429 rồi báo nhầm thành lỗi đăng nhập.
  if (logins > 0 && logins % 4 === 0) { console.log('   (nghỉ 65s né giới hạn đăng nhập...)'); await page.waitForTimeout(65000); }
  logins++;
  await page.fill('#login-email', role.user);
  await page.fill('#login-password', role.pass);
  await page.click('#login-submit');
  await page.waitForTimeout(3500);
  return page.evaluate(() => location.pathname !== '/login' && !!localStorage.getItem('jama_token'));
}

async function dismiss(page) {
  for (let i = 0; i < 2; i++) {
    const btn = page.locator('button:has-text("Bỏ qua")').first();
    if (await btn.isVisible().catch(() => false)) { await btn.click().catch(() => {}); await page.waitForTimeout(300); } else break;
  }
}

async function checkPage(page, role, path, vp) {
  const slug = (path === '/' ? 'home' : path.replace(/\//g, '_').slice(1));
  const shot = `${OUT}/${role}/${slug}-${vp}.png`;
  const jsErrors = [];
  const apiFails = [];
  const onErr = e => jsErrors.push(e.message.slice(0, 150));
  const onRes = r => { if (r.status() >= 400 && /\/api\//.test(r.url())) apiFails.push(`${r.status()} ${r.url().replace(/^https?:\/\/[^/]+/, '').slice(0, 80)}`); };
  page.on('pageerror', onErr);
  page.on('response', onRes);

  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(2200);
  await dismiss(page);
  await page.screenshot({ path: shot, fullPage: true }).catch(() => {});

  const auto = await page.evaluate(() => {
    const out = { crash: false, crashDetail: null, loadError: false, overflowX: 0, brokenImgs: [], emptyNoGuide: false, tinyButtons: 0, occluded: [] };
    const body = document.body.innerText;
    if (body.includes('Có lỗi xảy ra')) {
      out.crash = true;
      out.crashDetail = (document.querySelector('.font-mono.break-all') || {}).textContent || null;
    }
    out.loadError = /Không thể tải|Vui lòng thử lại/.test(body);
    out.overflowX = Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);
    for (const img of document.images) if (img.complete && img.naturalWidth === 0 && img.offsetWidth > 4) out.brokenImgs.push((img.src || '').slice(0, 100));
    const tbodies = document.querySelectorAll('main tbody');
    for (const tb of tbodies) {
      if (tb.children.length === 0 && !/Chưa có|Không có|trống|Bấm|Tạo/i.test(body)) { out.emptyNoGuide = true; break; }
    }
    for (const b of document.querySelectorAll('main button')) {
      const r = b.getBoundingClientRect();
      if (r.width > 0 && (r.width < 32 || r.height < 32)) out.tinyButtons++;
    }
    // Bug 12/08: nút bị phần tử khác đè lên (select giãn quá khổ). Dò bằng elementFromPoint
    // tại tâm nút — nếu điểm đó thuộc về cây DOM khác thì người dùng không bấm được.
    for (const b of document.querySelectorAll('main button, main a[href]')) {
      const r = b.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) continue;
      if (r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth) continue;
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (hit && hit !== b && !b.contains(hit) && !hit.contains(b)) {
        out.occluded.push(`${(b.innerText || b.getAttribute('aria-label') || b.tagName).slice(0, 24)} ← bị ${hit.tagName.toLowerCase()}${hit.className ? '.' + String(hit.className).split(' ')[0] : ''} đè`);
      }
    }
    out.occluded = out.occluded.slice(0, 4);
    return out;
  }).catch(() => null);

  const visText = await page.evaluate(() => document.body.innerText.slice(0, 20000)).catch(() => '');
  const cleaned = visText.replace(EN_ALLOW, '');
  const enHits = [];
  for (const w of EN_WORDS) {
    const re = new RegExp(`(?:^|\\n|[.!?]\\s|\\s{2})${w}\\b`, 'm');
    if (cleaned.match(re)) enHits.push(w);
  }

  page.off('pageerror', onErr);
  page.off('response', onRes);
  if (!auto) return;
  const where = `${role} ${path} (${vp})`;
  if (auto.crash) findings.push({ sev: 'blocker', where, what: 'VỠ TRANG (ErrorBoundary)', detail: auto.crashDetail, shot });
  if (apiFails.length) findings.push({ sev: 'blocker', where, what: 'API lỗi khi tải trang', detail: apiFails.slice(0, 4).join(' | '), shot });
  if (auto.loadError) findings.push({ sev: 'high', where, what: 'Thẻ báo không tải được dữ liệu', shot });
  if (jsErrors.length) findings.push({ sev: 'high', where, what: 'Lỗi JS', detail: jsErrors.join(' | '), shot });
  if (auto.occluded.length) findings.push({ sev: 'high', where, what: 'Nút bị che, không bấm được', detail: auto.occluded.join(' ; '), shot });
  if (auto.overflowX > 8) findings.push({ sev: vp === 'mobile' ? 'high' : 'medium', where, what: `Tràn ngang ${auto.overflowX}px`, shot });
  if (auto.brokenImgs.length) findings.push({ sev: 'high', where, what: 'Ảnh vỡ', detail: auto.brokenImgs.join(', '), shot });
  if (auto.emptyNoGuide) findings.push({ sev: 'medium', where, what: 'Bảng trống không có thông báo hướng dẫn', shot });
  if (enHits.length) findings.push({ sev: 'medium', where, what: 'Nghi tiếng Anh sót', detail: enHits.join(', '), shot });
  if (vp === 'mobile' && auto.tinyButtons > 2) findings.push({ sev: 'low', where, what: `${auto.tinyButtons} nút < 32px`, shot });
}

// Dò form: mở modal Tạo/Thêm đầu tiên, gửi khi trống, xem có báo lỗi không.
// CHỈ chạy ngoài bản thật (xem PROBE_FORMS) vì đây là thao tác GHI.
async function probeCreateForm(page, role, path) {
  const opener = page.locator('main button:has-text("Tạo"), main button:has-text("Thêm"), button[class*="fab"]').first();
  if (!(await opener.isVisible().catch(() => false))) return;
  await opener.click().catch(() => {});
  await page.waitForTimeout(900);
  const modal = page.locator('[role="dialog"], .fixed.inset-0, [class*="modal"]').last();
  if (!(await modal.isVisible().catch(() => false))) return;
  const shot = `${OUT}/${role}/${path === '/' ? 'home' : path.replace(/\//g, '_').slice(1)}-modal.png`;
  await page.screenshot({ path: shot }).catch(() => {});
  const submit = modal.locator('button[type=submit], button:has-text("Lưu"), button:has-text("Tạo")').last();
  if (await submit.isVisible().catch(() => false)) {
    await submit.click().catch(() => {});
    await page.waitForTimeout(1200);
    const state = await page.evaluate(() => ({
      modalGone: !document.querySelector('[role="dialog"]') && !document.querySelector('.fixed.inset-0 form'),
      hasErrText: /bắt buộc|không được để trống|vui lòng|thiếu|không hợp lệ/i.test(document.body.innerText),
      toastOk: /thành công/i.test(document.body.innerText),
    })).catch(() => null);
    if (state) {
      if (state.toastOk) findings.push({ sev: 'high', where: `${role} ${path}`, what: 'Gửi form TRỐNG vẫn báo thành công', shot });
      else if (state.modalGone && !state.hasErrText) findings.push({ sev: 'medium', where: `${role} ${path}`, what: 'Gửi form trống: modal đóng im lặng, không báo lỗi', shot });
      else if (!state.modalGone && !state.hasErrText) findings.push({ sev: 'medium', where: `${role} ${path}`, what: 'Gửi form trống: không hiện thông báo lỗi', shot });
    }
  }
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);
  const still = await page.locator('[role="dialog"] form, .fixed.inset-0 form').first().isVisible().catch(() => false);
  if (still) {
    findings.push({ sev: 'low', where: `${role} ${path}`, what: 'Modal không đóng bằng Escape', shot });
    await page.locator('button:has-text("Hủy"), button:has-text("Đóng"), [aria-label*="close" i], button:has-text("✕"), button:has-text("×")').first().click().catch(() => {});
    await page.mouse.click(8, 8).catch(() => {});
  }
}

console.log(`Walker chạy trên ${BASE} — dò form: ${PROBE_FORMS ? 'CÓ' : 'KHÔNG (chỉ đọc)'}`);

for (const role of ROLES) {
  let ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  let page = await ctx.newPage();
  if (!(await login(page, role))) {
    findings.push({ sev: 'blocker', where: `${role.key} (đăng nhập)`, what: 'ĐĂNG NHẬP THẤT BẠI' });
    await ctx.close(); continue;
  }
  for (const p of role.pages) {
    await checkPage(page, role.key, p, 'desktop');
    if (PROBE_FORMS && ['/leads', '/projects', '/customers', '/contracts', '/quotations', '/users'].includes(p)) {
      await probeCreateForm(page, role.key, p).catch(() => {});
    }
  }
  await ctx.close();

  ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  page = await ctx.newPage();
  if (await login(page, role)) {
    for (const p of role.pages.slice(0, 5)) await checkPage(page, role.key, p, 'mobile');
  }
  await ctx.close();
  console.log(`=== ${role.key} xong — tổng phát hiện hiện tại: ${findings.length}`);
}

await browser.close();
fs.writeFileSync(`${OUT}/walker-report.json`, JSON.stringify(findings, null, 2));
console.log(`\n===== WALKER XONG: ${findings.length} phát hiện =====`);
for (const f of findings) console.log(`[${f.sev}] ${f.where}: ${f.what}${f.detail ? ' — ' + String(f.detail).slice(0, 110) : ''}`);
