/**
 * Bộ lọc theo kỳ — DÙNG CHUNG cho trang Quy trình và Tổng quan.
 *
 * Trước 22/09/2026 mấy hàm này nằm riêng trong `app/leads/page.tsx`. Khi thêm
 * bộ lọc cho Tổng quan thì hoặc phải chép sang (hai bản trôi lệch — đúng lớp
 * lỗi đã phải gom lại 2 lần trong dự án này), hoặc tách ra đây. Chọn tách.
 *
 * Quy ước: mọi mốc là NGÀY THEO GIỜ VIỆT NAM, dạng `YYYY-MM-DD`. Backend nhận
 * đúng dạng này rồi tự quy đổi sang UTC (xem `khoang_ngay` trong
 * `backend/app/api/dashboard.py`) — không truyền ISO datetime để khỏi lệch múi giờ.
 */

export const DATE_PRESETS: { value: string; label: string }[] = [
  { value: 'all', label: 'Mọi lúc' },
  { value: 'today', label: 'Hôm nay' },
  { value: 'yesterday', label: 'Hôm qua' },
  { value: '7d', label: '7 ngày qua' },
  { value: '30d', label: '30 ngày qua' },
  { value: 'this_month', label: 'Tháng này' },
  { value: 'last_month', label: 'Tháng trước' },
  { value: 'this_quarter', label: 'Quý này' },
  { value: 'this_year', label: 'Năm nay' },
  { value: 'custom', label: 'Tùy chọn…' },
];

export function dayKey(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function toDayKey(value?: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : dayKey(d);
}

export function daysAgoKey(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return dayKey(d);
}

export function formatDayKey(key: string): string {
  const [y, m, d] = key.split('-');
  return `${d}/${m}/${y}`;
}

/** Đổi preset + 2 ô ngày tùy chọn thành khoảng [from, to] dạng YYYY-MM-DD. null = không lọc. */
export function resolveDateRange(preset: string, from: string, to: string): { from: string; to: string } | null {
  const today = dayKey(new Date());
  const n = new Date();
  switch (preset) {
    case 'today': return { from: today, to: today };
    case 'yesterday': { const y = daysAgoKey(1); return { from: y, to: y }; }
    case '7d': return { from: daysAgoKey(6), to: today };
    case '30d': return { from: daysAgoKey(29), to: today };
    case 'this_month': return { from: dayKey(new Date(n.getFullYear(), n.getMonth(), 1)), to: today };
    case 'last_month': {
      // Ngày 0 của tháng này = ngày cuối tháng trước, khỏi phải đếm 28/30/31.
      const dau = new Date(n.getFullYear(), n.getMonth() - 1, 1);
      const cuoi = new Date(n.getFullYear(), n.getMonth(), 0);
      return { from: dayKey(dau), to: dayKey(cuoi) };
    }
    case 'this_quarter': {
      const quy = Math.floor(n.getMonth() / 3);
      return { from: dayKey(new Date(n.getFullYear(), quy * 3, 1)), to: today };
    }
    case 'this_year': return { from: dayKey(new Date(n.getFullYear(), 0, 1)), to: today };
    case 'custom': {
      if (!from && !to) return null;
      // Nhập ngược (từ > đến) thì tự đảo, khỏi ra bảng trống mà không hiểu vì sao.
      if (from && to && from > to) return { from: to, to: from };
      return { from: from || '0000-01-01', to: to || '9999-12-31' };
    }
    default: return null;
  }
}

/** Nhãn ngắn của kỳ đang lọc — dùng cho chip bộ lọc và phụ đề thẻ số liệu. */
export function nhanKy(preset: string, from: string, to: string): string | null {
  const range = resolveDateRange(preset, from, to);
  if (!range) return null;
  if (preset !== 'custom') return DATE_PRESETS.find(p => p.value === preset)?.label || null;
  if (!to) return `từ ${formatDayKey(range.from)}`;
  if (!from) return `đến ${formatDayKey(range.to)}`;
  return `${formatDayKey(range.from)} → ${formatDayKey(range.to)}`;
}
