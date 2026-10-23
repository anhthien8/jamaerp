/** Số tiền gọn kiểu fintech: 14,4 tỷ · 50tr · 300k (dùng cho Chế độ thưởng + Hũ doanh số). */
export function tien(v: number): string {
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} tỷ`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}tr`;
  if (Math.abs(v) >= 1e3) return `${Math.round(v / 1e3).toLocaleString('vi-VN')}k`;
  return `${Math.round(v).toLocaleString('vi-VN')}đ`;
}
