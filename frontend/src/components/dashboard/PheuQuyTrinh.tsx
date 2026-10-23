'use client';

/**
 * Phễu quy trình trên Tổng quan (23/10/2026) — kiểu bảng độ sâu BloFin: thanh mảnh một tông
 * vàng đậm dần về «Deal đã thắng», số mono canh phải, cột % tỷ trọng. Độ dài thanh so với
 * giai đoạn đông nhất (trước đây chia cứng cho 20 nên lead > 20 là thanh nào cũng đầy).
 * Mỗi dòng là nút ≥ 44px, bấm mở danh sách lead đúng giai đoạn.
 */

import { STAGE_CONFIG } from '@/lib/utils';

const GIAI_DOAN = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design'];
// Vàng nhạt → đậm theo độ sâu phễu; giai đoạn thắng sáng nhất
const DO_DAM = [0.35, 0.5, 0.65, 0.8, 1];

export default function PheuQuyTrinh({ funnel, onChon }: {
  funnel: Record<string, number>;
  onChon: (stage: string) => void;
}) {
  const so = GIAI_DOAN.map(s => funnel[s] ?? 0);
  const tong = so.reduce((a, b) => a + b, 0);
  const lonNhat = Math.max(1, ...so);
  const thang = so[so.length - 1];

  return (
    <div className="glass-card p-4 sm:p-6">
      <div className="flex items-end justify-between gap-3 mb-3 sm:mb-4">
        <div>
          <h2 className="text-base sm:text-lg font-semibold">Phễu quy trình</h2>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
            <span className="font-mono tabular-nums">{tong.toLocaleString('vi-VN')}</span> lead đang ở 5 giai đoạn
          </p>
        </div>
        <div className="text-right">
          <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Tỷ trọng thắng</p>
          <p className="font-mono tabular-nums text-lg sm:text-xl font-semibold leading-tight" style={{ color: 'var(--gold-500)' }}>
            {tong ? ((thang / tong) * 100).toFixed(1).replace('.', ',') : '0'}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-[1fr_auto_auto] text-[10px] uppercase tracking-wider px-2 pb-1.5 gap-x-2 sm:gap-x-3"
        style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
        <span>Giai đoạn</span>
        <span className="w-10 sm:w-12 text-right">Lead</span>
        <span className="w-10 sm:w-12 text-right">%</span>
      </div>

      <ul className="mt-1">
        {GIAI_DOAN.map((stage, i) => {
          const n = so[i];
          const laThang = i === GIAI_DOAN.length - 1;
          const dam = DO_DAM[i];
          return (
            <li key={stage}>
              <button
                type="button"
                onClick={() => onChon(stage)}
                className="block w-full min-h-[44px] px-2 py-2 rounded-lg text-left transition-colors hover:bg-[var(--surface-2)] active:bg-[var(--surface-3)] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[var(--gold-500)]"
              >
                <div className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-2 sm:gap-x-3">
                  <span className="flex items-baseline gap-2 min-w-0">
                    <span className="hidden sm:inline font-mono text-[10px] tabular-nums" style={{ color: 'var(--text-disabled)' }}>0{i + 1}</span>
                    <span className="text-[13px] sm:text-sm truncate" style={{ color: laThang ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {STAGE_CONFIG[stage]?.label ?? stage}
                    </span>
                  </span>
                  <span className="w-10 sm:w-12 text-right font-mono tabular-nums text-sm font-semibold"
                    style={{ color: laThang ? 'var(--gold-500)' : 'var(--text-primary)' }}>
                    {n.toLocaleString('vi-VN')}
                  </span>
                  <span className="w-10 sm:w-12 text-right font-mono tabular-nums text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    {tong ? Math.round((n / tong) * 100) : 0}%
                  </span>
                </div>
                <div className="mt-1.5 h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-3)' }}>
                  <div
                    className="h-full rounded-full origin-left animate-[pheuGrow_.7s_cubic-bezier(.2,.8,.2,1)_both]"
                    style={{
                      width: `${(n / lonNhat) * 100}%`,
                      animationDelay: `${i * 60}ms`,
                      background: laThang
                        ? 'linear-gradient(90deg, var(--gold-600), var(--gold-300))'
                        : `rgba(201, 169, 110, ${dam})`,
                      boxShadow: laThang ? '0 0 8px rgba(228, 187, 118, 0.35)' : undefined,
                    }}
                  />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
