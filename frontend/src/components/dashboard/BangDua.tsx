'use client';

/**
 * Mảnh giao diện kiểu «bảng đua» (24/11/2026) dùng chung cho Hũ doanh số ở Tổng quan và Bảng điều
 * khiển Kinh doanh: chữ tiêu đề đậm hẹp, đồng hồ cung có vạch mốc, đường đua xếp hạng.
 */

import type { ReactNode } from 'react';
import { Anton } from 'next/font/google';
import LineIcon from '@/components/ui/LineIcon';

// Phông chỉ nạp ở trang có dùng tệp này.
const chuTo = Anton({ subsets: ['latin', 'vietnamese'], weight: '400', display: 'swap' });
/** Con số lớn: giữ «tr», «tỷ», «đ» chữ thường cho dễ đọc. */
export const SO = `${chuTo.className} tracking-wide leading-none`;
/** Tiêu đề: chữ hoa. */
export const TO = `${SO} uppercase`;

// Theo biến theme: tối = vàng #C9A96E, Ngoài trời = đồng đậm (vàng nhạt không đọc nổi trên ngà)
export const VANG = 'var(--gold-500)';
const HUY_CHUONG = [VANG, '#C0C4CC', '#B87333'];

/** Đồng hồ cung nửa vòng: `giaTri` so với `tran`, có vạch + nhãn ở từng mốc. */
export function DongHo({ giaTri, tran, vach, hienThi, moTa }: {
  giaTri: number; tran: number; vach: { giaTri: number; nhan: string }[]; hienThi: string; moTa: string;
}) {
  const dinh = tran > 0 ? tran : 1;
  const pct = Math.max(0, Math.min(100, (giaTri / dinh) * 100));
  const diem = (tyLe: number, r: number) => {
    const goc = Math.PI * (1 - tyLe);
    return [100 + r * Math.cos(goc), 100 - r * Math.sin(goc)];
  };
  return (
    <svg viewBox="-34 -12 268 124" className="w-full max-w-[280px] h-auto" role="img" aria-label={moTa}>
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--surface-3)" strokeWidth="18" strokeLinecap="round" />
      {pct > 0 && (
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke={VANG} strokeWidth="18" strokeLinecap="round"
          pathLength={100} strokeDasharray={`${pct} 100`} style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(.2,.8,.2,1)' }} />
      )}
      {vach.map((m, i) => {
        const tyLe = Math.max(0, Math.min(1, m.giaTri / dinh));
        const [x1, y1] = diem(tyLe, 68);
        const [x2, y2] = diem(tyLe, 92);
        const [xt, yt] = diem(tyLe, 104);
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--text-primary)" strokeWidth="2" strokeLinecap="round" />
            <text x={xt} y={yt + 3} fontSize="9" fontWeight="600" fill="var(--text-secondary)" textAnchor={tyLe > 0.55 ? 'start' : tyLe < 0.45 ? 'end' : 'middle'}>{m.nhan}</text>
          </g>
        );
      })}
      <text x="100" y="92" textAnchor="middle" fontSize={hienThi.length > 9 ? 21 : 27} fill="var(--text-primary)" className={chuTo.className}>{hienThi}</text>
    </svg>
  );
}

export interface DongDua { id: string; ten: string; giaTri: number; hang: number; phu?: string }

/** Đường đua: huy chương hạng 1–3, thanh dày, con số lớn, % so với tổng. Dòng `idToi` tô vàng. */
export function DuongDua({ ds, tong, dinhDang, idToi, nhanTong, hauToToi }: {
  ds: DongDua[]; tong: number; dinhDang: (v: number) => string; idToi?: string | null; nhanTong: string; hauToToi?: string;
}) {
  const dau = Math.max(1, ...ds.map(r => r.giaTri));
  return (
    <ol className="space-y-1.5">
      {ds.map(r => {
        const toi = !!idToi && r.id === idToi;
        return (
          <li key={r.id} className="flex items-center gap-3 rounded-xl px-2.5 py-2"
            style={toi ? { border: `1px solid ${VANG}`, background: `color-mix(in srgb, ${VANG} 10%, transparent)` } : { border: '1px solid transparent' }}>
            <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
              style={r.hang <= 3 ? { background: HUY_CHUONG[r.hang - 1], color: '#111' } : { background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>{r.hang}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold truncate text-[var(--text-primary)]">{r.ten}{toi && hauToToi ? hauToToi : ''}</div>
              {r.phu && <div className="text-[11px] text-[var(--text-muted)] truncate">{r.phu}</div>}
              <div className="h-2.5 rounded-full mt-1" style={{ background: 'var(--surface-3)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.max(3, (r.giaTri / dau) * 100)}%`, background: toi || (!idToi && r.hang === 1) ? VANG : 'var(--text-muted)', transition: 'width 1.2s cubic-bezier(.2,.8,.2,1)' }} />
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className={`${SO} text-xl sm:text-2xl text-[var(--text-primary)]`}>{dinhDang(r.giaTri)}</div>
              {tong > 0 && <div className="text-[11px] text-[var(--text-muted)] mt-1">{Math.round((r.giaTri / tong) * 100)}% {nhanTong}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Dải câu thúc dưới đường đua. */
export function CauThuc({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 rounded-xl px-3 py-2.5 text-sm flex items-start gap-2 text-[var(--text-secondary)]" style={{ background: `color-mix(in srgb, ${VANG} 12%, transparent)` }}>
      <LineIcon name="trendUp" size={16} color={VANG} className="shrink-0 mt-0.5" />
      <span>{children}</span>
    </div>
  );
}
