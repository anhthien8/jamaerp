/**
 * Mảnh giao diện dùng chung cho các bảng điều khiển (tách từ /sale-dashboard
 * 20/11/2026 để /du-lieu-chung và /doi-chieu dùng lại, khỏi chép tay).
 */

import type { ReactNode } from 'react';
import { TO } from './BangDua';

/** Thanh tiến độ mảnh vẽ bằng div — app không dùng thư viện biểu đồ. */
export function Thanh({ pct, mau, cao = 6 }: { pct: number; mau: string; cao?: number }) {
  return (
    <div className="rounded-full overflow-hidden w-full" style={{ height: cao, background: 'var(--surface-3)' }}>
      <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(Math.max(pct, 0), 100)}%`, background: mau }} />
    </div>
  );
}

/** Thẻ khối có tiêu đề + dòng phụ. */
export function Khoi({ tieuDe, phu, children, className, id }: {
  tieuDe: string; phu?: string; children: ReactNode; className?: string; id?: string;
}) {
  return (
    <section id={id} className={`glass-card p-5 ${className || ''}`}>
      <div className="mb-4">
        <h2 className={`${TO} text-lg text-[var(--text-primary)]`}>{tieuDe}</h2>
        {phu && <p className="text-[11px] text-[var(--text-muted)] mt-1.5">{phu}</p>}
      </div>
      {children}
    </section>
  );
}

/** Trạng thái rỗng của một khối. */
export function Trong({ chu }: { chu: string }) {
  return <p className="text-xs text-[var(--text-muted)] py-6 text-center">{chu}</p>;
}
