'use client';

/**
 * Hũ doanh số trên Tổng quan (23/10/2026) — kiểu «hũ tiền thưởng» Squid Game:
 * doanh số công ty leo qua từng mốc, mỗi mốc mở thêm quỹ thưởng, hũ vàng đầy dần.
 * Chỉ hiện khi Chế độ thưởng bật Hũ và người xem nằm trong «Ai thấy hũ» (backend quyết,
 * trả {hien:false} thì ẩn êm). Bảng xếp hạng chỉ có DOANH SỐ — không lộ tiền thưởng từng người.
 */

import { useEffect, useState } from 'react';
import { api, CdtHu } from '@/lib/api';
import { tien } from '@/lib/tien-gon';

// Theo biến theme: tối = vàng #C9A96E, Ngoài trời = đồng đậm (vàng nhạt không đọc nổi trên ngà)
const VANG = 'var(--gold-500)';
// Ký hiệu mốc kiểu Squid Game: ○ △ □ rồi lặp
const KY_HIEU = ['circle', 'triangle', 'square'] as const;

function KyHieu({ loai, dat, size = 18 }: { loai: (typeof KY_HIEU)[number]; dat: boolean; size?: number }) {
  const mau = dat ? VANG : 'var(--text-muted)';
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden style={{ color: mau }}>
      {loai === 'circle' && <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="2" fill={dat ? 'currentColor' : 'none'} />}
      {loai === 'triangle' && <path d="M10 2.5 L18 17 H2 Z" stroke="currentColor" strokeWidth="2" fill={dat ? 'currentColor' : 'none'} strokeLinejoin="round" />}
      {loai === 'square' && <rect x="3" y="3" width="14" height="14" stroke="currentColor" strokeWidth="2" fill={dat ? 'currentColor' : 'none'} />}
    </svg>
  );
}

/** Hũ thủy tinh: mức vàng = quỹ đã mở / quỹ tối đa. */
function Hu({ pct }: { pct: number }) {
  const h = 104 * Math.max(0, Math.min(1, pct));
  return (
    <svg viewBox="0 0 120 150" className="w-24 sm:w-28 h-auto shrink-0" aria-hidden style={{ color: 'var(--text-primary)' }}>
      <defs>
        <clipPath id="hu-than"><path d="M28 30 Q20 34 20 48 V128 Q20 142 34 142 H86 Q100 142 100 128 V48 Q100 34 92 30 Z" /></clipPath>
        <linearGradient id="hu-vang" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F3D9A4" />
          <stop offset="1" stopColor="#A9824A" />
        </linearGradient>
      </defs>
      <g clipPath="url(#hu-than)">
        <rect x="0" y={142 - h} width="120" height={h} fill="url(#hu-vang)" style={{ transition: 'all 1.2s cubic-bezier(.2,.8,.2,1)' }} />
        {h > 6 && <path d={`M20 ${142 - h} q10 -4 20 0 t20 0 t20 0 t20 0 t20 0`} stroke="#FFF3D6" strokeOpacity=".6" strokeWidth="2" fill="none" />}
      </g>
      <path d="M28 30 Q20 34 20 48 V128 Q20 142 34 142 H86 Q100 142 100 128 V48 Q100 34 92 30" stroke="currentColor" strokeOpacity=".55" strokeWidth="3" fill="none" />
      <rect x="32" y="14" width="56" height="14" rx="4" fill="currentColor" fillOpacity=".1" stroke="currentColor" strokeOpacity=".55" strokeWidth="2" />
      <path d="M32 50 V118" stroke="currentColor" strokeOpacity=".18" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export default function HuDoanhSo() {
  const [hu, setHu] = useState<CdtHu | null>(null);
  const [xem, setXem] = useState<'ca_nhan' | 'doi'>('ca_nhan');

  useEffect(() => {
    api.cdtHu().then(setHu).catch(() => setHu({ hien: false }));
  }, []);

  if (!hu || !hu.hien) return null;

  const mocCuoi = hu.moc[hu.moc.length - 1]?.doanh_so || 1;
  const tran = Math.max(mocCuoi * 1.05, hu.doanh_so);
  const pctDoanhSo = Math.min(100, (hu.doanh_so / tran) * 100);
  const pctHu = hu.quy_toi_da > 0 ? hu.quy_mo / hu.quy_toi_da : 0;
  const conNgay = Math.max(0, hu.so_ngay - hu.ngay_da_qua);
  const bang = xem === 'ca_nhan'
    ? hu.ca_nhan.map(x => ({ id: x.user_id, ten: x.ten, doanh_so: x.doanh_so }))
    : hu.doi.map(x => ({ id: x.team_id, ten: x.ten, doanh_so: x.doanh_so }));
  const dauBang = bang[0]?.doanh_so || 1;

  return (
    <section className="card p-4 sm:p-6 overflow-hidden relative" aria-label="Hũ doanh số">
      <div className="absolute -right-16 -top-16 w-56 h-56 rounded-full blur-3xl opacity-20 pointer-events-none" style={{ background: VANG }} />

      <div className="flex items-start gap-4 sm:gap-6">
        <Hu pct={pctHu} />
        <div className="min-w-0 flex-1">
          <div className="text-overline text-[var(--text-muted)]">Hũ thưởng {hu.nhan_ky}</div>
          <div className="font-mono font-bold leading-none mt-1 text-[2rem] sm:text-[2.75rem]" style={{ color: VANG }}>
            {tien(hu.quy_mo)}
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-1">
            đã mở / tối đa {tien(hu.quy_toi_da)} · còn {conNgay} ngày
          </div>
          <div className="mt-3 text-sm">
            Doanh số <b className="font-mono">{tien(hu.doanh_so)}</b>
            {hu.moc_tiep ? (
              <> — còn <b className="font-mono" style={{ color: VANG }}>{tien(hu.con_thieu)}</b> tới «{hu.moc_tiep.nhan}» mở thêm <b className="font-mono">{tien(hu.moc_tiep.quy)}</b></>
            ) : <> — <b style={{ color: VANG }}>đã phá đảo mọi mốc!</b></>}
          </div>
        </div>
      </div>

      {/* Đường đua mốc */}
      <div className="mt-6 mb-2 px-2">
        <div className="relative h-2 rounded-full bg-white/10">
          <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pctDoanhSo}%`, background: `linear-gradient(90deg, #8a6a3a, ${VANG})`, transition: 'width 1.2s cubic-bezier(.2,.8,.2,1)' }} />
          {hu.moc.map((m, i) => {
            const left = Math.min(100, (m.doanh_so / tran) * 100);
            return (
              <div key={i} className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: `${left}%` }}>
                <div className="bg-[var(--card-bg)] rounded-full p-0.5"><KyHieu loai={KY_HIEU[i % 3]} dat={!!m.dat} /></div>
              </div>
            );
          })}
        </div>
        <div className="relative h-10 mt-2 text-[10px] sm:text-[11px]">
          {hu.moc.map((m, i) => {
            const left = Math.min(100, (m.doanh_so / tran) * 100);
            return (
              <div key={i} className="absolute -translate-x-1/2 text-center whitespace-nowrap" style={{ left: `${left}%` }}>
                <div className={`font-mono ${m.dat ? '' : 'text-[var(--text-muted)]'}`} style={m.dat ? { color: VANG } : undefined}>{tien(m.quy)}</div>
                <div className="text-[var(--text-muted)] font-mono">{tien(m.doanh_so)}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bảng xếp hạng doanh số — không ghi tiền thưởng */}
      {(hu.ca_nhan.length > 0 || hu.doi.length > 0) && (
        <div className="mt-3 pt-4 border-t border-white/5">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-sm font-medium">Ai đang đẩy hũ</span>
            {hu.doi.length > 0 && (
              <div className="inline-flex rounded-full bg-white/5 p-0.5 text-xs">
                {([['ca_nhan', 'Cá nhân'], ['doi', 'Nhóm']] as const).map(([k, n]) => (
                  <button key={k} onClick={() => setXem(k)}
                    className={`px-3 py-1 rounded-full ${xem === k ? 'bg-white text-black font-semibold' : 'text-[var(--text-secondary)]'}`}>{n}</button>
                ))}
              </div>
            )}
          </div>
          <ol className="space-y-1.5">
            {bang.slice(0, 5).map((r, i) => (
              <li key={r.id} className="flex items-center gap-3 text-sm">
                <span className="w-5 text-center font-mono text-xs" style={i === 0 ? { color: VANG } : { color: 'var(--text-muted)' }}>{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <span className="truncate">{r.ten}</span>
                    <span className="font-mono shrink-0">{tien(r.doanh_so)}</span>
                  </div>
                  <div className="h-1 rounded-full bg-white/5 mt-1">
                    <div className="h-full rounded-full" style={{ width: `${Math.max(3, (r.doanh_so / dauBang) * 100)}%`, background: i === 0 ? VANG : 'var(--text-muted)' }} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
