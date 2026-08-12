// QC nút + (Tạo vai trò mới) trong form Tạo tài khoản (read-only — KHÔNG tạo role/tài khoản thật).
// Bài học 12/08: isVisible() không phát hiện element bị che — phải CLICK thật (hit-target check)
// và so bounding box không chồng lấn ô Bộ phận.
// Chạy: node scripts/qc-users-roleplus.mjs https://crm.jamahome.vn
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let pass = 0, fail = 0;
const ok = (name, cond) => { if (cond) { pass++; console.log(`✅ ${name}`); } else { fail++; console.log(`❌ ${name}`); } };

async function login(email, password) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.click('#login-submit');
  await page.waitForURL(u => !String(u).includes('/login'), { timeout: 20000 });
}

// ── Admin: mở form Tạo tài khoản → nút + phải bấm ĐƯỢC và mở modal vai trò ──
await login('admin', 'admin123');
await page.goto(`${BASE}/users`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
try { await page.locator('button:has-text("Bỏ qua")').first().click({ timeout: 2000 }); } catch {}
await page.locator('button:has-text("Tạo tài khoản")').first().click();
await page.waitForTimeout(1200);
ok('Admin: modal Tạo tài khoản mới mở', await page.locator('text=Tạo tài khoản mới').isVisible().catch(() => false));

const plusBtn = page.locator('button[title="Tạo vai trò mới"]');
ok('Admin: nút + có trong DOM', await plusBtn.isVisible().catch(() => false));

// Không chồng lấn: mép phải nút + phải ≤ mép trái select Bộ phận
// (data-qc thay vì label:has-text — modal Tạo vai trò cũng có label "Bộ phận", sẽ đụng strict mode)
const plusBox = await plusBtn.boundingBox().catch(() => null);
const deptSelect = page.locator('[data-qc="dept-select"]');
const deptBox = await deptSelect.boundingBox().catch(() => null);
ok(
  `Admin: nút + KHÔNG bị select Bộ phận che (+right=${plusBox ? Math.round(plusBox.x + plusBox.width) : '?'} ≤ deptLeft=${deptBox ? Math.round(deptBox.x) : '?'})`,
  !!plusBox && !!deptBox && plusBox.x + plusBox.width <= deptBox.x + 1
);
await page.screenshot({ path: 'H:/tmp/qc-roleplus-form.png' });

// Click thật — Playwright fail nếu element bị element khác hứng pointer
let clicked = false;
try { await plusBtn.click({ timeout: 5000, trial: false }); clicked = true; } catch {}
ok('Admin: bấm được nút +', clicked);
await page.waitForTimeout(1000);
ok('Admin: modal "Tạo vai trò mới" mở sau khi bấm +', await page.locator('text=Tạo vai trò mới').last().isVisible().catch(() => false));
await page.screenshot({ path: 'H:/tmp/qc-roleplus-admin.png' });

// Đóng hết — KHÔNG tạo gì. Modal trang này không bắt Escape; đóng bằng click backdrop góc (8,8).
for (let i = 0; i < 3; i++) {
  if (await page.locator('.fixed.inset-0.z-50').first().isVisible({ timeout: 800 }).catch(() => false)) {
    await page.mouse.click(8, 8);
    await page.waitForTimeout(500);
  }
}

await browser.close();
console.log(`\n===== ${pass}/${pass + fail} PASS =====`);
process.exit(fail ? 1 : 0);
