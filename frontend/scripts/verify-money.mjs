// Kiểm tra cách hiển thị số tiền trong modal "Chỉnh sửa dự án": ô nhập, dòng xem trước "= ...",
// và nhãn đơn vị "nghìn đồng" — bắt lỗi lệch đơn vị (nghìn/triệu) trước khi kế toán nhập sai.
//
// Chạy:  node scripts/verify-money.mjs [BASE_URL]      (mặc định https://crm.jamahome.vn)
// CHỈ ĐỌC: mở modal, đọc giá trị rồi thoát — không bấm Lưu.
//
// Chế độ Tập luyện đã nghỉ hẳn 12/08/2026 → đăng nhập thật.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'https://crm.jamahome.vn';
const PASS = process.env.QC_PASS_ADMIN || 'admin123';

const browser = await chromium.launch();
const page = await browser.newPage();
page.on('pageerror', e => console.log('[pageerror]', e.message.slice(0, 120)));

const dismiss = async () => { for (const t of ['Bỏ qua', 'Bo qua']) { const b = page.locator(`button:has-text("${t}")`).first(); if (await b.isVisible().catch(() => false)) await b.click().catch(() => {}); } };

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await page.fill('#login-email', 'admin');
await page.fill('#login-password', PASS);
await page.click('#login-submit');
await page.waitForTimeout(3500);
await dismiss();
if (!(await page.evaluate(() => !!localStorage.getItem('jama_token')))) {
  console.log('ĐĂNG NHẬP THẤT BẠI — dừng.');
  await browser.close();
  process.exit(1);
}

await page.goto(`${BASE}/projects`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
await dismiss();

const card = page.locator('main div:has-text("PRJ-2026")[class*="cursor-pointer"], main [class*="cursor-pointer"]:has-text("PRJ-")').first();
await card.click().catch(() => {});
await page.waitForTimeout(1500);
const editBtn = page.locator('button:has-text("Chỉnh sửa")').first();
if (await editBtn.isVisible().catch(() => false)) {
  await editBtn.click();
  await page.waitForTimeout(1000);
  const info = await page.evaluate(() => {
    const modal = [...document.querySelectorAll('div')].find(d => d.textContent?.includes('Chỉnh sửa dự án') && d.querySelector('input'));
    if (!modal) return 'không thấy modal';
    const inputs = [...modal.querySelectorAll('input[type=number]')].map(i => i.value);
    const preview = [...modal.querySelectorAll('p')].filter(p => p.textContent?.startsWith('= ')).map(p => p.textContent);
    const labels = [...modal.querySelectorAll('label')].map(l => l.textContent).filter(t => t?.includes('nghìn đồng'));
    return { oNhapSo: inputs, xemTruoc: preview, nhanNghinDong: labels };
  });
  console.log('MODAL:', JSON.stringify(info, null, 1));
} else console.log('không thấy nút Chỉnh sửa');

// Thoát không lưu.
await page.keyboard.press('Escape').catch(() => {});
await page.mouse.click(8, 8).catch(() => {});
await browser.close();
