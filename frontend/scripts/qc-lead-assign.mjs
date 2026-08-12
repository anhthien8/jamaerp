// QC UI phân công lead (read-only — KHÔNG submit giao lead thật).
// Chạy: node scripts/qc-lead-assign.mjs https://crm.jamahome.vn
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let pass = 0, fail = 0;
const ok = (name, cond) => { if (cond) { pass++; console.log(`✅ ${name}`); } else { fail++; console.log(`❌ ${name}`); } };

const dismiss = async () => {
  try { await page.locator('button:has-text("Bỏ qua")').first().click({ timeout: 2500 }); } catch {}
};

async function login(email, password) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.click('#login-submit');
  await page.waitForURL(u => !String(u).includes('/login'), { timeout: 20000 });
}

async function openFirstLead() {
  await page.goto(`${BASE}/leads`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await dismiss();
  const card = page.locator('[draggable="true"]').first();
  await card.click();
  await page.waitForTimeout(1500);
}

// ── Admin: thấy nút Đổi + select có ứng viên ──
await login('admin', 'admin123');
await openFirstLead();
ok('Admin: dòng Phụ trách hiển thị', await page.locator('text=Phụ trách').first().isVisible().catch(() => false));
const doiBtn = page.locator('button:has-text("Đổi")').first();
ok('Admin: có nút Đổi', await doiBtn.isVisible().catch(() => false));
await doiBtn.click().catch(() => {});
await page.waitForTimeout(1500);
const select = page.locator('select').filter({ has: page.locator('option:has-text("Chọn nhân viên")') }).first();
const optCount = await select.locator('option').count().catch(() => 0);
ok(`Admin: select ứng viên mở, ${optCount} option (>1)`, optCount > 1);
await page.screenshot({ path: 'H:/tmp/qc-lead-assign-admin.png' });
// Đóng bằng nút Hủy — KHÔNG chọn ai
await page.locator('button:has-text("Hủy")').first().click().catch(() => {});

// ── Sales: chỉ xem, KHÔNG có nút Đổi ──
await login('sales', 'sales123');
await openFirstLead();
ok('Sales: dòng Phụ trách hiển thị', await page.locator('text=Phụ trách').first().isVisible().catch(() => false));
ok('Sales: KHÔNG có nút Đổi', !(await page.locator('button:has-text("Đổi")').first().isVisible({ timeout: 2000 }).catch(() => false)));
await page.screenshot({ path: 'H:/tmp/qc-lead-assign-sales.png' });

await browser.close();
console.log(`\n===== ${pass}/${pass + fail} PASS =====`);
process.exit(fail ? 1 : 0);
