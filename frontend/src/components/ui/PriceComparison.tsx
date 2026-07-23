'use client';

import type { PriceComparison } from '@/lib/api';

const fmt = (n: number) => n.toLocaleString('vi-VN');

const trendIcon: Record<string, { icon: string; color: string; label: string }> = {
  up: { icon: '▲', color: '#EF4444', label: 'Tang' },
  down: { icon: '▼', color: '#22C55E', label: 'Giam' },
  stable: { icon: '—', color: '#9CA3AF', label: 'On dinh' },
};

export default function PriceComparisonTable({ data }: { data: PriceComparison }) {
  if (!data.quotes.length) {
    return (
      <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
        Khong tim thay bao gia cho vat tu nay
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex gap-4 flex-wrap">
        <div className="px-4 py-3 rounded-xl flex-1 min-w-[140px]" style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid rgba(201,169,110,0.2)' }}>
          <p className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Gia re nhat</p>
          <p className="text-lg font-bold" style={{ color: 'var(--gold-400)' }}>{fmt(data.cheapest_price)}d/{data.unit}</p>
        </div>
        <div className="px-4 py-3 rounded-xl flex-1 min-w-[140px]" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
          <p className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Gia trung binh</p>
          <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{fmt(data.avg_price)}d/{data.unit}</p>
        </div>
        <div className="px-4 py-3 rounded-xl flex-1 min-w-[140px]" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
          <p className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>So luong NCC</p>
          <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{data.quotes.length}</p>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <th className="text-left py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Nha cung cap</th>
              <th className="text-right py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Don gia</th>
              <th className="text-right py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Chenh lech</th>
              <th className="text-center py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>SL toi thieu</th>
              <th className="text-center py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Giao hang</th>
              <th className="text-center py-3 px-3 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Xu huong</th>
            </tr>
          </thead>
          <tbody>
            {data.quotes
              .sort((a, b) => a.unit_price - b.unit_price)
              .map((q, idx) => {
                const diff = q.unit_price - data.cheapest_price;
                const diffPct = data.cheapest_price > 0 ? ((diff / data.cheapest_price) * 100) : 0;
                const trend = trendIcon[q.price_trend] || trendIcon.stable;
                return (
                  <tr
                    key={q.supplier_id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      background: q.is_cheapest ? 'rgba(34,197,94,0.06)' : 'transparent',
                    }}
                  >
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        {q.is_cheapest && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: 'rgba(34,197,94,0.15)', color: '#22C55E' }}>
                            RE NHAT
                          </span>
                        )}
                        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {q.supplier_name}
                        </span>
                        {idx === 0 && !q.is_cheapest && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}>
                            #1
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="text-right py-3 px-3">
                      <span className="font-semibold" style={{ color: q.is_cheapest ? '#22C55E' : 'var(--text-primary)' }}>
                        {fmt(q.unit_price)}d
                      </span>
                    </td>
                    <td className="text-right py-3 px-3">
                      {diff > 0 ? (
                        <span className="text-xs" style={{ color: '#EF4444' }}>+{fmt(diff)}d (+{diffPct.toFixed(1)}%)</span>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td className="text-center py-3 px-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {q.min_quantity || '-'}
                    </td>
                    <td className="text-center py-3 px-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {q.lead_time_days ? `${q.lead_time_days} ngay` : '-'}
                    </td>
                    <td className="text-center py-3 px-3">
                      <span className="text-xs" style={{ color: trend.color }} title={trend.label}>
                        {trend.icon}
                      </span>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {/* Note */}
      {data.quotes.some(q => q.valid_until) && (
        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          * Gia co hieu luc den ngay het han. Vui long lien he NCC de xac nhan gia hien tai.
        </p>
      )}
    </div>
  );
}
