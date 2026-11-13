'use client';

/**
 * Biểu đồ của AI Tiến Hoá (13/11/2026) — SVG tự vẽ, không thêm thư viện.
 *
 * Theo quy tắc dataviz: nét 2px, cột ≤24px bo 4px ở đầu dữ liệu, vùng tô 10%, chấm r=4 có
 * viền màu nền 2px, lưới mảnh, một trục. Màu chuỗi lấy từ `--viz-1/--viz-2` (đã qua bộ
 * kiểm bảng màu cho cả nền tối lẫn Ngoài trời); chữ luôn ăn màu chữ, không ăn màu chuỗi.
 * Rê chuột / chạm / phím mũi tên đều xem được từng điểm; mỗi biểu đồ có bảng số đi kèm.
 */

import { type KeyboardEvent, type PointerEvent, type ReactNode, useEffect, useRef, useState } from 'react';
import type { AiTienHoa, AiTienHoaTuan } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';

export const MAU_1 = 'var(--viz-1)';
export const MAU_2 = 'var(--viz-2)';
const LUOI = 'var(--viz-grid)';
const NEN = 'var(--card-bg)';

/** 0.625 → «63%»; chưa có mẫu → «—». */
export function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v * 100)}%`;
}

const so = (n: number) => n.toLocaleString('vi-VN');

/** Theo dõi bề rộng thật của khung để vẽ SVG đúng pixel (chữ, chấm không bị méo). */
function useDoRong<T extends HTMLElement>(macDinh = 560) {
  const ref = useRef<T>(null);
  const [rong, setRong] = useState(macDinh);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setRong(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, rong] as const;
}

/** Chú giải: ô màu cạnh chữ — chữ vẫn màu chữ. */
export function ChuGiai({ muc }: { muc: { mau: string; nhan: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
      {muc.map(m => (
        <span key={m.nhan} className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-[3px]" style={{ background: m.mau }} aria-hidden />
          {m.nhan}
        </span>
      ))}
    </div>
  );
}

/** Nút gạt «Biểu đồ / Bảng» — bảng là đường vào số liệu cho người không đọc được hình. */
export function GatBang({ bang, onDoi }: { bang: boolean; onDoi: (b: boolean) => void }) {
  return (
    <div className="inline-flex rounded-full bg-[var(--surface-3)] p-0.5 text-xs" role="group" aria-label="Cách xem">
      {([[false, 'Biểu đồ'], [true, 'Bảng']] as const).map(([k, n]) => (
        <button key={n} type="button" onClick={() => onDoi(k)} aria-pressed={bang === k}
          className={`px-3 py-1 rounded-full min-h-[28px] ${bang === k ? 'bg-[var(--text-primary)] text-[var(--surface-0)] font-semibold' : 'text-[var(--text-secondary)]'}`}>
          {n}
        </button>
      ))}
    </div>
  );
}

/** Chênh lệch theo điểm phần trăm — có mũi tên + chữ, không chỉ dựa vào màu. */
export function ChenhLech({ v, so_voi }: { v: number | null; so_voi: string }) {
  if (v == null) return <span className="text-xs text-[var(--text-muted)]">chưa đủ dữ liệu để so với {so_voi}</span>;
  const diem = Math.round(v * 100);
  const mau = diem > 0 ? 'var(--success)' : diem < 0 ? 'var(--danger)' : 'var(--text-muted)';
  return (
    <span className="inline-flex items-center gap-1 text-xs" style={{ color: mau }}>
      {diem !== 0 && <LineIcon name={diem > 0 ? 'trendUp' : 'trendDown'} size={14} color="currentColor" className="shrink-0" />}
      <b className="font-semibold whitespace-nowrap">{diem > 0 ? '+' : ''}{diem} điểm</b>
      <span className="text-[var(--text-muted)]">so với {so_voi}</span>
    </span>
  );
}

type Diem = { i: number; v: number };

/** Cắt chuỗi thành các đoạn liền — tuần chưa có phản hồi là khoảng trống, không nối bừa. */
function catDoan(gt: (number | null)[]): Diem[][] {
  const doan: Diem[][] = [];
  let cur: Diem[] = [];
  gt.forEach((v, i) => {
    if (v == null) {
      if (cur.length) doan.push(cur);
      cur = [];
    } else cur.push({ i, v });
  });
  if (cur.length) doan.push(cur);
  return doan;
}

/** Đường nhỏ 12 điểm cho ô số: màu nhạt, điểm hiện tại mới tô màu nhấn. */
export function Sparkline({ gt, rong = 128, cao = 36, nhan }: { gt: (number | null)[]; rong?: number; cao?: number; nhan: string }) {
  const n = gt.length;
  const pad = 6;
  const x = (i: number) => pad + (n <= 1 ? (rong - 2 * pad) / 2 : (i * (rong - 2 * pad)) / (n - 1));
  const y = (v: number) => pad + (cao - 2 * pad) * (1 - v);
  const doan = catDoan(gt);
  const cuoi = doan.length ? doan[doan.length - 1][doan[doan.length - 1].length - 1] : null;
  return (
    <svg width={rong} height={cao} viewBox={`0 0 ${rong} ${cao}`} role="img" aria-label={nhan} className="shrink-0">
      {doan.map((d, k) => d.length > 1 ? (
        <path key={k} d={d.map((p, j) => `${j ? 'L' : 'M'}${x(p.i)},${y(p.v)}`).join('')}
          fill="none" stroke="var(--text-muted)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      ) : (
        <circle key={k} cx={x(d[0].i)} cy={y(d[0].v)} r={2} fill="var(--text-muted)" />
      ))}
      {cuoi && <circle cx={x(cuoi.i)} cy={y(cuoi.v)} r={4} fill={MAU_1} stroke={NEN} strokeWidth={2} />}
    </svg>
  );
}

/** Tỷ lệ sale làm theo gợi ý theo tuần — một chuỗi, trục 0–100%. */
export function DuongLamTheo({ tuan, cao = 220 }: { tuan: AiTienHoaTuan[]; cao?: number }) {
  const [ref, rong] = useDoRong<HTMLDivElement>();
  const [chon, setChon] = useState<number | null>(null);
  const L = 40, R = 46, T = 12, B = 26;
  const iw = Math.max(60, rong - L - R);
  const ih = cao - T - B;
  const n = tuan.length;
  const buocX = n <= 1 ? 0 : iw / (n - 1);
  const x = (i: number) => L + (n <= 1 ? iw / 2 : i * buocX);
  const y = (v: number) => T + ih * (1 - v);
  const gt = tuan.map(t => t.ty_le_lam_theo);
  const doan = catDoan(gt);
  const cuoi = doan.length ? doan[doan.length - 1][doan[doan.length - 1].length - 1] : null;
  // Nhãn trục X thưa theo bề rộng; luôn giữ nhãn tuần cuối
  const cachNhan = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(iw / 52))));

  const chonTheoX = (e: PointerEvent<SVGSVGElement>) => {
    if (!n) return;
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    const i = buocX ? Math.round((px - L) / buocX) : 0;
    setChon(Math.max(0, Math.min(n - 1, i)));
  };
  const phim = (e: KeyboardEvent<SVGSVGElement>) => {
    if (!n) return;
    const hien = chon ?? n - 1;
    if (e.key === 'ArrowLeft') { setChon(Math.max(0, hien - 1)); e.preventDefault(); }
    else if (e.key === 'ArrowRight') { setChon(Math.min(n - 1, hien + 1)); e.preventDefault(); }
    else if (e.key === 'Home') { setChon(0); e.preventDefault(); }
    else if (e.key === 'End') { setChon(n - 1); e.preventDefault(); }
    else if (e.key === 'Escape') setChon(null);
  };

  const t = chon != null ? tuan[chon] : null;
  const xChon = chon != null ? x(chon) : 0;
  const neo = xChon < 110 ? 'trai' : xChon > rong - 110 ? 'phai' : 'giua';

  return (
    <div ref={ref} className="relative w-full select-none">
      <svg width={rong} height={cao} className="block outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold-500)] rounded-lg"
        role="img" tabIndex={0}
        aria-label={`Tỷ lệ làm theo gợi ý ${n} tuần, tuần gần nhất ${pct(cuoi?.v)}. Dùng phím mũi tên để xem từng tuần.`}
        onPointerMove={chonTheoX} onPointerDown={chonTheoX} onPointerLeave={() => setChon(null)}
        onKeyDown={phim} onFocus={() => setChon(c => c ?? (n ? n - 1 : null))} onBlur={() => setChon(null)}
        style={{ touchAction: 'pan-y' }}>
        {[0, 0.25, 0.5, 0.75, 1].map(v => (
          <g key={v}>
            <line x1={L} x2={L + iw} y1={y(v)} y2={y(v)} stroke={LUOI} strokeWidth={1} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fill="var(--text-muted)" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {Math.round(v * 100)}%
            </text>
          </g>
        ))}
        {tuan.map((w, i) => ((n - 1 - i) % cachNhan === 0) && (
          <text key={w.tuan} x={x(i)} y={cao - 6} textAnchor="middle" fontSize={11} fill="var(--text-muted)" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {w.nhan}
          </text>
        ))}

        {doan.filter(d => d.length > 1).map((d, k) => (
          <path key={`a${k}`} fill={MAU_1} fillOpacity={0.1}
            d={`M${x(d[0].i)},${y(0)}` + d.map(p => `L${x(p.i)},${y(p.v)}`).join('') + `L${x(d[d.length - 1].i)},${y(0)}Z`} />
        ))}
        {doan.filter(d => d.length > 1).map((d, k) => (
          <path key={`l${k}`} fill="none" stroke={MAU_1} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
            d={d.map((p, j) => `${j ? 'L' : 'M'}${x(p.i)},${y(p.v)}`).join('')} />
        ))}

        {chon != null && <line x1={xChon} x2={xChon} y1={T} y2={T + ih} stroke="var(--border-strong)" strokeWidth={1} />}

        {/* Chấm: điểm đứng lẻ (không có đường), điểm cuối, điểm đang xem */}
        {doan.filter(d => d.length === 1).map(d => (
          <circle key={`o${d[0].i}`} cx={x(d[0].i)} cy={y(d[0].v)} r={4} fill={MAU_1} stroke={NEN} strokeWidth={2} />
        ))}
        {cuoi && (
          <>
            <circle cx={x(cuoi.i)} cy={y(cuoi.v)} r={4} fill={MAU_1} stroke={NEN} strokeWidth={2} />
            <text x={x(cuoi.i) + 9} y={y(cuoi.v) + 4} fontSize={12} fontWeight={600} fill="var(--text-primary)">{pct(cuoi.v)}</text>
          </>
        )}
        {t && t.ty_le_lam_theo != null && (
          <circle cx={xChon} cy={y(t.ty_le_lam_theo)} r={5} fill={MAU_1} stroke={NEN} strokeWidth={2} />
        )}
      </svg>

      {t && (
        <div className="absolute pointer-events-none z-10 rounded-xl px-3 py-2 text-xs shadow-lg border border-[var(--border-default)] bg-[var(--surface-2)] min-w-[160px]"
          style={{
            top: 4,
            left: neo === 'phai' ? undefined : neo === 'trai' ? xChon + 10 : xChon,
            right: neo === 'phai' ? rong - xChon + 10 : undefined,
            transform: neo === 'giua' ? 'translateX(-50%)' : undefined,
          }}>
          <div className="text-[var(--text-muted)] mb-1">Tuần từ {t.nhan}</div>
          <div className="flex items-center gap-1.5 text-[var(--text-primary)]">
            <span className="inline-block w-3 h-0.5 rounded" style={{ background: MAU_1 }} aria-hidden />
            Làm theo <b className="ml-auto font-semibold">{t.ty_le_lam_theo == null ? 'chưa có phản hồi' : pct(t.ty_le_lam_theo)}</b>
          </div>
          <div className="text-[var(--text-secondary)] mt-1">{so(t.lam)} đã làm · {so(t.bo_qua)} bỏ qua</div>
          <div className="text-[var(--text-muted)]">{so(t.chay)} lần AI chạy</div>
        </div>
      )}
    </div>
  );
}

/** Bảng số đi kèm biểu đồ tuần. */
export function BangTuan({ tuan }: { tuan: AiTienHoaTuan[] }) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm min-w-[480px]">
        <thead>
          <tr className="text-xs text-[var(--text-muted)] text-left">
            <th className="font-medium py-2 px-1">Tuần từ</th>
            <th className="font-medium py-2 px-1 text-right">Làm theo</th>
            <th className="font-medium py-2 px-1 text-right">Đã làm</th>
            <th className="font-medium py-2 px-1 text-right">Bỏ qua</th>
            <th className="font-medium py-2 px-1 text-right">Lần chạy</th>
            <th className="font-medium py-2 px-1 text-right">Dùng lại</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-subtle)]" style={{ fontVariantNumeric: 'tabular-nums' }}>
          {[...tuan].reverse().map(t => (
            <tr key={t.tuan}>
              <td className="py-1.5 px-1">{t.nhan}</td>
              <td className="py-1.5 px-1 text-right font-semibold">{pct(t.ty_le_lam_theo)}</td>
              <td className="py-1.5 px-1 text-right">{so(t.lam)}</td>
              <td className="py-1.5 px-1 text-right">{so(t.bo_qua)}</td>
              <td className="py-1.5 px-1 text-right">{so(t.chay)}</td>
              <td className="py-1.5 px-1 text-right">{so(t.dung_lai)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Lần chạy theo từng trợ lý AI, tách phần do LLM và phần do bộ luật trả lời. */
export function CotTroLy({ rows }: { rows: AiTienHoa['theo_agent'] }) {
  const [chon, setChon] = useState<string | null>(null);
  const max = Math.max(1, ...rows.map(r => r.chay));
  return (
    <ul className="space-y-3">
      {rows.map(r => {
        const dangXem = chon === r.agent;
        const phan: { k: string; n: number; mau: string; nhan: string }[] = [
          { k: 'llm', n: r.llm, mau: MAU_1, nhan: 'AI (LLM)' },
          { k: 'rule', n: r.rule, mau: MAU_2, nhan: 'Bộ luật' },
        ].filter(p => p.n > 0);
        return (
          <li key={r.agent} className="relative outline-none rounded-lg focus-visible:ring-2 focus-visible:ring-[var(--gold-500)]"
            tabIndex={0}
            aria-label={`${r.ten}: ${r.chay} lần chạy, ${r.llm} do LLM, ${r.rule} do bộ luật, ${r.dung_lai} lần dùng lại bộ nhớ`}
            onPointerEnter={() => setChon(r.agent)} onPointerLeave={() => setChon(null)}
            onFocus={() => setChon(r.agent)} onBlur={() => setChon(null)}
            onClick={() => setChon(c => (c === r.agent ? null : r.agent))}>
            <div className="text-sm text-[var(--text-secondary)] truncate">{r.ten}</div>
            <div className="flex items-center gap-2 mt-1 py-1">
              <div className="flex h-[14px] gap-[2px]" style={{ width: `max(4px, calc((100% - 3.5rem) * ${r.chay / max}))` }}>
                {phan.map((p, j) => (
                  <div key={p.k} style={{ flex: `${p.n} 1 0`, background: p.mau, borderRadius: j === phan.length - 1 ? '0 4px 4px 0' : 0, opacity: chon && !dangXem ? 0.45 : 1 }} />
                ))}
              </div>
              <span className="text-sm font-semibold text-[var(--text-primary)]" style={{ fontVariantNumeric: 'tabular-nums' }}>{so(r.chay)}</span>
            </div>
            {dangXem && (
              <div className="absolute left-0 top-full mt-1 z-10 pointer-events-none rounded-xl px-3 py-2 text-xs shadow-lg border border-[var(--border-default)] bg-[var(--surface-2)] min-w-[180px]">
                <div className="text-[var(--text-primary)] font-medium mb-1">{r.ten}</div>
                {[{ mau: MAU_1, nhan: 'AI (LLM)', n: r.llm }, { mau: MAU_2, nhan: 'Bộ luật', n: r.rule }].map(p => (
                  <div key={p.nhan} className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <span className="inline-block w-2.5 h-2.5 rounded-[3px]" style={{ background: p.mau }} aria-hidden />
                    {p.nhan}<b className="ml-auto text-[var(--text-primary)]">{so(p.n)}</b>
                  </div>
                ))}
                <div className="text-[var(--text-muted)] mt-1">{so(r.dung_lai)} lần dùng lại bộ nhớ</div>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Bảng số đi kèm biểu đồ trợ lý. */
export function BangTroLy({ rows }: { rows: AiTienHoa['theo_agent'] }) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm min-w-[420px]">
        <thead>
          <tr className="text-xs text-[var(--text-muted)] text-left">
            <th className="font-medium py-2 px-1">Trợ lý</th>
            <th className="font-medium py-2 px-1 text-right">Lần chạy</th>
            <th className="font-medium py-2 px-1 text-right">LLM</th>
            <th className="font-medium py-2 px-1 text-right">Bộ luật</th>
            <th className="font-medium py-2 px-1 text-right">Dùng lại</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-subtle)]" style={{ fontVariantNumeric: 'tabular-nums' }}>
          {rows.map(r => (
            <tr key={r.agent}>
              <td className="py-1.5 px-1">{r.ten}</td>
              <td className="py-1.5 px-1 text-right font-semibold">{so(r.chay)}</td>
              <td className="py-1.5 px-1 text-right">{so(r.llm)}</td>
              <td className="py-1.5 px-1 text-right">{so(r.rule)}</td>
              <td className="py-1.5 px-1 text-right">{so(r.dung_lai)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Khung thẻ có tiêu đề + phụ đề + chỗ cho nút bên phải. */
export function The({ tieuDe, phu, phai, children, className, id }: {
  tieuDe: string; phu?: ReactNode; phai?: ReactNode; children: ReactNode; className?: string; id?: string;
}) {
  return (
    <section id={id} className={`card p-4 sm:p-5 ${className || ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{tieuDe}</h2>
          {phu && <div className="text-xs text-[var(--text-muted)] mt-0.5">{phu}</div>}
        </div>
        {phai}
      </div>
      {children}
    </section>
  );
}
