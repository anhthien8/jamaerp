'use client';

/**
 * Popup thông báo trong app (21/11/2026) — khi chuông vừa nhận một thông báo MỚI chưa đọc,
 * hiện một ô nhỏ trên màn hình thay vì chỉ tăng con số đỏ (người ít mở chuông không biết).
 * • Tối đa 3 ô chồng nhau, mới nhất ở trên.
 * • Tự ẩn sau 12 giây; rê chuột vào thì dừng đếm (điện thoại không dừng → không che lâu).
 * • Máy tính: góc trên phải, dưới nút chuông. Điện thoại: trên cùng, ngay dưới thanh tiêu đề,
 *   chừa vùng tai thỏ (safe-area).
 * • Lớp z-[48]: trên thanh tiêu đề (z-30), nút chuông (z-40), thanh cài app (z-45); DƯỚI các
 *   hộp/biểu mẫu `fixed inset-0 z-50` (vd Tạo lead) và ngăn menu mobile — popup không được
 *   đè nút đóng/tiêu đề của một biểu mẫu đang nhập dở (bấm «Mở» là rời trang, mất dữ liệu).
 * Nội dung lấy từ NotificationCenter — ở đây chỉ vẽ + đếm giờ.
 */

import { useEffect, useRef, useState } from 'react';
import LineIcon from '@/components/ui/LineIcon';

export interface MucPopup {
  /** id dạng `srv-<id>` giống danh sách chuông. */
  id: string;
  tieuDe: string;
  dong: string;
  icon: string;
  /** null = thông báo không có link → «Mở» mở khung chuông. */
  link: string | null;
}

export const TOI_DA_POPUP = 3;
const THOI_GIAN_HIEN = 12_000;

const THUC_THE: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

/** Giải mã thực thể HTML (`&amp;`, `&#39;`…) → chữ thường. Không đụng tới thẻ. */
export function giaiMaThucThe(s: string): string {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (goc, ma: string) => {
    if (ma[0] === '#') {
      const so = ma[1] === 'x' || ma[1] === 'X' ? parseInt(ma.slice(2), 16) : parseInt(ma.slice(1), 10);
      return Number.isFinite(so) && so > 0 && so <= 0x10ffff ? String.fromCodePoint(so) : goc;
    }
    return THUC_THE[ma.toLowerCase()] ?? goc;
  });
}

/** Bỏ thẻ HTML (thân tin Telegram có `<a>`, `<b>`) và giải mã thực thể HTML → chữ thường. */
export function vanBanThuan(html: string): string {
  return giaiMaThucThe(html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li)>/gi, '\n')
    .replace(/<[^>]*>/g, ''));
}

/** Dòng đầu (khác rỗng) của thân thông báo, đã làm sạch. */
export function dongDauThongBao(body: string | null | undefined): string {
  if (!body) return '';
  return vanBanThuan(body).split('\n').map(s => s.trim()).find(Boolean) || '';
}

export default function PopupThongBao({ ds, onMo, onDong }: {
  ds: MucPopup[];
  onMo: (m: MucPopup) => void;
  onDong: (id: string) => void;
}) {
  // Vùng aria-live luôn có sẵn (kể cả rỗng) để trình đọc màn hình đọc được ô mới chèn vào.
  return (
    <div
      role="region"
      aria-label="Thông báo mới"
      aria-live="polite"
      className="fixed z-[48] left-3 right-3 top-[calc(4rem+env(safe-area-inset-top))] lg:left-auto lg:right-6 lg:top-[72px] lg:w-[360px] flex flex-col gap-2 pointer-events-none"
    >
      {ds.slice(0, TOI_DA_POPUP).map(m => (
        <OThongBao key={m.id} m={m} onMo={onMo} onDong={onDong} />
      ))}
      <style>{`
        @keyframes popupThongBaoVao { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
        .popup-thong-bao-vao { animation: popupThongBaoVao 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
      `}</style>
    </div>
  );
}

function OThongBao({ m, onMo, onDong }: { m: MucPopup; onMo: (m: MucPopup) => void; onDong: (id: string) => void }) {
  const [dungDem, setDungDem] = useState(false);
  const conLai = useRef(THOI_GIAN_HIEN);
  const onDongRef = useRef(onDong);
  useEffect(() => { onDongRef.current = onDong; });

  // Đếm ngược phần thời gian còn lại; rê chuột vào thì dừng, rời ra thì đếm tiếp.
  useEffect(() => {
    if (dungDem) return;
    const batDau = Date.now();
    const hen = setTimeout(() => onDongRef.current(m.id), Math.max(conLai.current, 0));
    return () => {
      clearTimeout(hen);
      conLai.current -= Date.now() - batDau;
    };
  }, [dungDem, m.id]);

  return (
    <div
      className="popup-thong-bao-vao pointer-events-auto rounded-2xl pl-3 py-2 flex items-center gap-3"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-default, var(--border-subtle))',
        boxShadow: '0 12px 32px rgba(0,0,0,0.35)',
      }}
      onPointerEnter={e => { if (e.pointerType === 'mouse') setDungDem(true); }}
      onPointerLeave={e => { if (e.pointerType === 'mouse') setDungDem(false); }}
    >
      <span className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'var(--surface-2)' }}>
        <LineIcon name={m.icon} size={18} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold leading-snug text-[var(--text-primary)] line-clamp-2">{m.tieuDe}</p>
        {m.dong && <p className="text-[11px] text-[var(--text-muted)] truncate mt-0.5">{m.dong}</p>}
      </div>
      <button
        type="button"
        onClick={() => onMo(m)}
        className="shrink-0 min-h-[44px] px-4 rounded-full text-xs font-semibold"
        style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}
      >
        Mở
      </button>
      <button
        type="button"
        onClick={() => onDong(m.id)}
        className="shrink-0 w-11 h-11 rounded-full flex items-center justify-center"
        aria-label="Đóng thông báo"
      >
        <LineIcon name="x" size={16} color="var(--text-muted)" />
      </button>
    </div>
  );
}
