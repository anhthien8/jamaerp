'use client';

/**
 * «Việc cần Ban Giám đốc quyết» — khối đầu trang «Việc của tôi» của BGĐ (24/11/2026).
 *
 * Giám đốc không được giao đầu việc dự án nên trang của họ từng trống. Mỗi mục ở đây là
 * một quyết định hoặc một cuộc hỏi cụ thể; nội dung và mốc do backend dựng
 * (services/viec_bgd.py), màn hình chỉ trình bày.
 */

import Link from 'next/link';
import type { ViecBgd } from '@/lib/api';
import { mauNhat } from '@/lib/utils';
import LineIcon from '@/components/ui/LineIcon';

const MAU: Record<string, string> = { do: 'var(--danger)', vang: 'var(--warning)', xam: 'var(--text-muted)' };

export default function ViecCanBgdQuyet({ ds }: { ds: ViecBgd[] | null }) {
  if (ds === null) return <div className="skeleton h-28 rounded-2xl" />;

  if (!ds.length) {
    return (
      <div className="glass-card p-5 flex items-start gap-3">
        <span className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ background: mauNhat('var(--success)', 18) }}>
          <LineIcon name="check" size={16} color="var(--success)" />
        </span>
        <div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">Hôm nay không có việc nào cần Ban Giám đốc quyết</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
            Không có đơn kẹt duyệt, lead bị bỏ, dự án trễ hay chỉ số nào vượt mốc báo động.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <p className="text-sm font-semibold text-[var(--text-primary)]">Việc cần Ban Giám đốc quyết · {ds.length}</p>
      <p className="text-xs text-[var(--text-muted)] mt-1 mb-4">
        Chỉ nêu việc đã vượt tầm người phụ trách trực tiếp, xếp theo độ gấp. Xử lý xong là mục tự biến mất.
      </p>
      <ol className="space-y-5">
        {ds.map((v, i) => {
          const mau = MAU[v.muc] || 'var(--text-muted)';
          return (
            <li key={v.ma} className="flex gap-3">
              <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5"
                style={{ background: mauNhat(mau, 18), color: mau }}>{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--text-primary)]">{v.tieu_de}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{v.ly_do}</p>
                {v.dong.length > 0 && (
                  <ul className="mt-2.5 rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
                    {v.dong.map((d, j) => (
                      <li key={j} style={{ background: 'var(--surface-2)', borderTop: j ? '1px solid var(--border-subtle)' : undefined }}>
                        <Link href={d.href} className="flex items-center gap-2 px-3 py-2.5 min-h-[44px]">
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm text-[var(--text-primary)] truncate">{d.ten}</span>
                            <span className="block text-xs text-[var(--text-muted)] leading-snug">{d.phu}</span>
                          </span>
                          <span aria-hidden className="text-base text-[var(--text-muted)] shrink-0">›</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex items-center gap-3 flex-wrap mt-2.5">
                  <Link href={v.href} className="inline-flex items-center h-9 px-4 rounded-full text-xs font-medium"
                    style={{ border: '1px solid var(--gold-500)', color: 'var(--gold-500)' }}>
                    {v.nut}
                  </Link>
                  {v.tong > v.dong.length && v.dong.length > 0 && (
                    <span className="text-xs text-[var(--text-muted)]">Đang hiện {v.dong.length} trên {v.tong}</span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
