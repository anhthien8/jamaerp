// QA UX walker: 6 role × demo mode × desktop+mobile. Máy dò tự động + screenshot toàn bộ.
// Chạy: node scripts/_qa_walker.mjs  (từ thư mục frontend). Kết quả JSON: H:/tmp/qa-ux/walker-report.json
import { chromium } from 'playwright';
import fs from 'fs';

const BASE = process.argv[2] || 'https://frontend-jet-two-86.vercel.app';
const OUT = 'H:/tmp/qa-ux';

const ROLES = [
  { key: 'admin', email: 'admin@jamahome.vn', pages: ['/', '/leads', '/projects', '/pl', '/attendance', '/approvals', '/settings', '/users', '/hr', '/customers', '/contracts', '/quotations', '/inventory', '/accounting', '/kpi', '/reports', '/feedback'] },
  { key: 'executive', email: 'ceo@jamahome.vn', pages: ['/', '/pl', '/reports', '/kpi', '/feedback'] },
  { key: 'leader', email: 'leader@jamahome.vn', pages: ['/', '/leads', '/projects', '/hr', '/accounting', '/kpi'] },
  { key: 'sales', email: 'sales@jamahome.vn', pages: ['/', '/leads', '/quote-tool', '/quotations', '/customers', '/contracts'] },
  { key: 'accountant', email: 'accountant@jamahome.vn', pages: ['/', '/accounting', '/pl', '/hr', '/inventory', '/contracts'] },
  { key: 'supervisor', email: 'supervisor@jamahome.vn', pages: ['/', '/projects', '/inventory', '/attendance', '/approvals'] },
];

// Từ tiếng Anh hay sót trong UI (word-boundary, phân biệt hoa thường có chủ đích)
const EN_WORDS = ['Save', 'Cancel', 'Delete', 'Submit', 'Search', 'Loading', 'Error', 'Success', 'No data', 'Select', 'Status', 'Total', 'Edit', 'Add new', 'Close', 'Confirm', 'Required', 'Invalid', 'Failed', 'Name', 'Date', 'Amount', 'Description'];
// Nhiễu hợp lệ (brand, thuật ngữ đã chốt giữ tiếng Anh)
const EN_ALLOW = /JAMA|HOME|CRM|ERP|Zalo|Telegram|Google|Email|Dashboard|Kanban|Lead|KPI|OT|PIT|P&L|BOD|Portal|OK|Demo|Beta|Chat|App|Web|Admin|Sales|Deal|Pipeline|Import|Export|Excel|PDF|Logo|URL|QR|Bot|AI|Token|Feedback/gi;

const findings = [];
const browser = await chromium.launch();

async function login(page, email) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.click('text=Chế độ Tập luyện').catch(() => {});
  await page.waitForTimeout(400);
  await page.fill('#login-email', email);
  await page.fill('#login-password', 'demo123');
  await page.click('button[type=submit]');
  await page.waitForTimeout(3000);
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
  const onErr = e => jsErrors.push(e.message.slice(0, 150));
  page.on('pageerror', onErr);

  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(2200);
  await dismiss(page);
  await page.screenshot({ path: shot, fullPage: true }).catch(() => {});

  const auto = await page.evaluate((allowSrc) => {
    const out = { crash: false, crashDetail: null, overflowX: 0, brokenImgs: [], enTexts: [], emptyNoGuide: false, tinyButtons: 0 };
    const body = document.body.innerText;
    if (body.includes('Có lỗi xảy ra')) {
      out.crash = true;
      out.crashDetail = (document.querySelector('.font-mono.break-all') || {}).textContent || null;
    }
    out.overflowX = Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);
    for (const img of document.images) if (img.complete && img.naturalWidth === 0 && img.offsetWidth > 4) out.brokenImgs.push((img.src || '').slice(0, 100));
    // bảng trống không có hướng dẫn
    const tbodies = document.querySelectorAll('main tbody');
    for (const tb of tbodies) {
      if (tb.children.length === 0 && !/Chưa có|Không có|trống|Bấm|Tạo/i.test(body)) { out.emptyNoGuide = true; break; }
    }
    // nút bấm quá nhỏ (mobile)
    for (const b of document.querySelectorAll('main button')) {
      const r = b.getBoundingClientRect();
      if (r.width > 0 && (r.width < 32 || r.height < 32)) out.tinyButtons++;
    }
    return out;
  }).catch(() => null);

  // dò tiếng Anh sót trong text nhìn thấy
  const visText = await page.evaluate(() => document.body.innerText.slice(0, 20000)).catch(() => '');
  const cleaned = visText.replace(EN_ALLOW, '');
  const enHits = [];
  for (const w of EN_WORDS) {
    const re = new RegExp(`(?:^|\\n|[.!?]\\s|\\s{2})${w}\\b`, 'm');
    const m = cleaned.match(re);
    if (m) enHits.push(w);
  }

  page.off('pageerror', onErr);
  if (!auto) return;
  const where = `${role} ${path} (${vp})`;
  if (auto.crash) findings.push({ sev: 'blocker', where, what: 'CRASH ErrorBoundary', detail: auto.crashDetail, shot });
  if (jsErrors.length) findings.push({ sev: 'high', where, what: 'JS pageerror', detail: jsErrors.join(' | '), shot });
  if (auto.overflowX > 8) findings.push({ sev: vp === 'mobile' ? 'high' : 'medium', where, what: `Tràn ngang ${auto.overflowX}px`, shot });
  if (auto.brokenImgs.length) findings.push({ sev: 'high', where, what: 'Ảnh vỡ', detail: auto.brokenImgs.join(', '), shot });
  if (auto.emptyNoGuide) findings.push({ sev: 'medium', where, what: 'Bảng trống không có thông báo hướng dẫn', shot });
  if (enHits.length) findings.push({ sev: 'medium', where, what: 'Nghi tiếng Anh sót', detail: enHits.join(', '), shot });
  if (vp === 'mobile' && auto.tinyButtons > 2) findings.push({ sev: 'low', where, what: `${auto.tinyButtons} nút < 32px`, shot });
}

// probe form: mở modal Tạo/Thêm đầu tiên, submit trống, xem có báo lỗi không
async function probeCreateForm(page, role, path) {
  const opener = page.locator('main button:has-text("Tạo"), main button:has-text("Thêm"), button[class*="fab"]').first();
  if (!(await opener.isVisible().catch(() => false))) return;
  await opener.click().catch(() => {});
  await page.waitForTimeout(900);
  const modal = page.locator('[role="dialog"], .fixed.inset-0, [class*="modal"]').last();
  if (!(await modal.isVisible().catch(() => false))) return;
  const shot = `H:/tmp/qa-ux/${role}/${path === '/' ? 'home' : path.replace(/\//g, '_').slice(1)}-modal.png`;
  await page.screenshot({ path: shot }).catch(() => {});
  const submit = modal.locator('button[type=submit], button:has-text("Lưu"), button:has-text("Tạo")').last();
  if (await submit.isVisible().catch(() => false)) {
    const before = await page.evaluate(() => document.body.innerText.length);
    await submit.click().catch(() => {});
    await page.waitForTimeout(1200);
    const state = await page.evaluate(() => ({
      modalGone: !document.querySelector('[role="dialog"]') && !document.querySelector('.fixed.inset-0 form'),
      hasErrText: /bắt buộc|không được để trống|vui lòng|thiếu|không hợp lệ|required/i.test(document.body.innerText),
      toastOk: /thành công/i.test(document.body.innerText),
    })).catch(() => null);
    if (state) {
      if (state.toastOk) findings.push({ sev: 'high', where: `${role} ${path}`, what: 'Submit form TRỐNG vẫn toast thành công', shot });
      else if (state.modalGone && !state.hasErrText) findings.push({ sev: 'medium', where: `${role} ${path}`, what: 'Submit form trống: modal đóng im lặng, không báo lỗi', shot });
      else if (!state.modalGone && !state.hasErrText) findings.push({ sev: 'medium', where: `${role} ${path}`, what: 'Submit form trống: không có thông báo lỗi hiển thị', shot });
    }
  }
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);
  // modal không đóng được bằng Escape?
  const still = await page.locator('[role="dialog"] form, .fixed.inset-0 form').first().isVisible().catch(() => false);
  if (still) {
    findings.push({ sev: 'low', where: `${role} ${path}`, what: 'Modal không đóng bằng Escape', shot });
    await page.locator('button:has-text("Hủy"), button:has-text("Đóng"), [aria-label*="close" i], button:has-text("✕"), button:has-text("×")').first().click().catch(() => {});
  }
}

for (const role of ROLES) {
  // Desktop
  let ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  let page = await ctx.newPage();
  if (!(await login(page, role.email))) {
    findings.push({ sev: 'blocker', where: `${role.key} (login demo)`, what: 'LOGIN DEMO FAIL' });
    await ctx.close(); continue;
  }
  for (const p of role.pages) {
    await checkPage(page, role.key, p, 'desktop');
    if (['/leads', '/projects', '/customers', '/contracts', '/quotations', '/users'].includes(p)) {
      await probeCreateForm(page, role.key, p).catch(() => {});
    }
  }
  await ctx.close();
  // Mobile (5 trang đầu)
  ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  page = await ctx.newPage();
  if (await login(page, role.email)) {
    for (const p of role.pages.slice(0, 5)) await checkPage(page, role.key, p, 'mobile');
  }
  await ctx.close();
  console.log(`=== ${role.key} xong — tổng findings hiện tại: ${findings.length}`);
}

await browser.close();
fs.writeFileSync(`${OUT}/walker-report.json`, JSON.stringify(findings, null, 2));
console.log(`\n===== WALKER XONG: ${findings.length} findings =====`);
for (const f of findings) console.log(`[${f.sev}] ${f.where}: ${f.what}${f.detail ? ' — ' + String(f.detail).slice(0, 100) : ''}`);
