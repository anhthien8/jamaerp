// QC toàn bộ role × mode trên production: login thật, đi từng trang, bắt crash/pageerror,
// probe click phần tử tương tác đầu tiên. Né rate-limit login backend (5/phút): delay 13s giữa các work-login.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'https://frontend-jet-two-86.vercel.app';

const ROLES = [
  { key: 'admin',      user: 'admin',      pass: 'admin123',  pages: ['/', '/leads', '/projects', '/pl', '/attendance', '/approvals', '/settings', '/users', '/hr', '/customers', '/contracts', '/quotations', '/inventory', '/accounting', '/kpi', '/reports', '/feedback'] },
  { key: 'executive',  user: 'ceo',        pass: 'ceo123',    pages: ['/', '/pl', '/reports', '/kpi', '/feedback', '/projects', '/contracts', '/settings'] },
  { key: 'leader',     user: 'leader',     pass: 'leader123', pages: ['/', '/leads', '/projects', '/attendance', '/approvals', '/hr', '/accounting', '/reports', '/kpi', '/settings', '/customers', '/contracts', '/quotations'] },
  { key: 'sales',      user: 'sales',      pass: 'sales123',  pages: ['/', '/leads', '/projects', '/attendance', '/approvals', '/accounting', '/reports', '/quotations', '/quote-tool', '/settings', '/customers', '/contracts'] },
  { key: 'accountant', user: 'accountant', pass: 'account123',pages: ['/', '/accounting', '/pl', '/hr', '/attendance', '/approvals', '/inventory', '/reports', '/settings', '/contracts', '/quotations', '/customers'] },
  { key: 'supervisor', user: 'supervisor', pass: 'super123',  pages: ['/', '/projects', '/inventory', '/quotations', '/attendance', '/approvals', '/kpi', '/reports', '/settings', '/contracts', '/customers'] },
];

const browser = await chromium.launch();
const results = [];
let workLogins = 0;

async function dismissOverlays(page) {
  for (const label of ['Bỏ qua', 'Bo qua']) {
    const btn = page.locator(`button:has-text("${label}")`).first();
    if (await btn.isVisible().catch(() => false)) await btn.click().catch(() => {});
  }
}

async function qcRole(role, mode) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(`${e.message.slice(0, 160)}`));

  // Login
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  if (mode === 'demo') {
    await page.click('text=Chế độ Tập luyện').catch(() => {});
    await page.waitForTimeout(400);
    await page.fill('#login-email', `${role.key === 'sales' ? 'sales' : role.key === 'executive' ? 'ceo' : role.key}@jamahome.vn`);
    await page.fill('#login-password', 'demo123');
  } else {
    if (workLogins > 0 && workLogins % 4 === 0) { console.log('   (nghỉ 65s né rate-limit login...)'); await page.waitForTimeout(65000); }
    workLogins++;
    await page.fill('#login-email', role.user);
    await page.fill('#login-password', role.pass);
  }
  await page.click('button[type=submit]');
  await page.waitForTimeout(4500);

  const loggedIn = await page.evaluate(() => location.pathname !== '/login' && !!localStorage.getItem('jama_token'));
  if (!loggedIn) {
    const errTxt = await page.evaluate(() => document.body.innerText.slice(0, 120).replace(/\n+/g, ' '));
    results.push({ role: role.key, mode, page: '(login)', status: 'LOGIN_FAIL', detail: errTxt });
    await ctx.close();
    return;
  }

  for (const p of role.pages) {
    await page.goto(`${BASE}${p}`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1800);
    await dismissOverlays(page);
    let s = await page.evaluate(() => ({ boundary: document.body.innerText.includes('Có lỗi xảy ra'), detail: (document.querySelector('.font-mono.break-all') || {}).textContent || null }));
    let interacted = false;
    if (!s.boundary) {
      // probe: click phần tử tương tác đầu tiên trong main
      const el = page.locator('main [class*="cursor-pointer"], main tbody tr').first();
      if (await el.isVisible().catch(() => false)) {
        await el.click({ timeout: 2000 }).catch(() => {});
        interacted = true;
        await page.waitForTimeout(1200);
        s = await page.evaluate(() => ({ boundary: document.body.innerText.includes('Có lỗi xảy ra'), detail: (document.querySelector('.font-mono.break-all') || {}).textContent || null }));
        await page.keyboard.press('Escape').catch(() => {});
      }
    }
    results.push({ role: role.key, mode, page: p, status: s.boundary ? 'CRASH' : 'OK', interacted, detail: s.detail, jsErrors: errors.splice(0).slice(0, 2) });
  }
  await ctx.close();
}

for (const mode of ['work', 'demo']) {
  for (const role of ROLES) {
    console.log(`=== QC ${role.key} (${mode}) ===`);
    await qcRole(role, mode);
    const roleResults = results.filter(r => r.role === role.key && r.mode === mode);
    const fails = roleResults.filter(r => r.status !== 'OK');
    console.log(`   ${roleResults.length - fails.length}/${roleResults.length} OK${fails.length ? ' — FAIL: ' + fails.map(f => `${f.page}(${f.status}${f.detail ? ':' + String(f.detail).slice(0, 60) : ''})`).join(', ') : ''}`);
    const withJs = roleResults.filter(r => r.jsErrors && r.jsErrors.length);
    for (const w of withJs) console.log(`   [jsError] ${w.page}: ${w.jsErrors.join(' | ')}`);
  }
}

const totalFail = results.filter(r => r.status !== 'OK');
console.log(`\n===== TỔNG KẾT: ${results.length - totalFail.length}/${results.length} OK, ${totalFail.length} FAIL =====`);
for (const f of totalFail) console.log(`FAIL ${f.role}/${f.mode}${f.page}: ${f.status} ${f.detail || ''}`);
await browser.close();
