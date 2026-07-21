'use client';

import { useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { RELEASES } from '@/lib/releases';

/**
 * Trang "Có gì mới" — ghi chú thay đổi giữa các bản cập nhật, viết cho NHÂN VIÊN
 * (không phải dev): mỗi bản gồm Tính năng mới / Đã sửa / Anh em test giúp.
 * Cập nhật mảng RELEASES mỗi lần deploy tính năng đáng chú ý.
 */

const SECTION_META = {
  news: { icon: 'star', label: 'Tính năng mới', color: '#C9A96E' },
  fixes: { icon: 'check', label: 'Đã sửa', color: '#34D399' },
  test: { icon: 'eye', label: 'Anh em test giúp', color: '#60A5FA' },
} as const;

export default function ChangelogPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-6 animate-in max-w-3xl">
        <h1 className="text-2xl font-bold mb-1 flex items-center gap-2.5"><LineIcon name="bell" size={22} />Có gì mới</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Ghi chú thay đổi giữa các bản cập nhật — đọc mục <span style={{ color: '#60A5FA' }}>&quot;Anh em test giúp&quot;</span> rồi vọc thử nhé.
          Gặp lỗi: chụp màn hình (khung lỗi tự hiện chi tiết) gửi nhóm kỹ thuật hoặc bot Telegram <code className="px-1 rounded bg-white/10">/feedback</code>.
        </p>

        <div className="space-y-6">
          {RELEASES.map(rel => (
            <div key={rel.date} className="glass-card p-6">
              <div className="flex items-center gap-3 flex-wrap mb-4">
                <span className="text-sm font-mono px-2.5 py-1 rounded-lg" style={{ background: 'rgba(201,169,110,0.12)', color: '#C9A96E' }}>{rel.date}</span>
                <h2 className="text-lg font-semibold">{rel.title}</h2>
                {rel.tag && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: 'rgba(52,211,153,0.15)', color: '#34D399' }}>{rel.tag}</span>
                )}
              </div>
              {(['news', 'fixes', 'test'] as const).map(key => {
                const items = rel[key];
                if (!items?.length) return null;
                const meta = SECTION_META[key];
                return (
                  <div key={key} className="mb-4 last:mb-0">
                    <div className="flex items-center gap-2 mb-2">
                      <LineIcon name={meta.icon} size={15} color={meta.color} />
                      <span className="text-xs font-bold uppercase tracking-wide" style={{ color: meta.color }}>{meta.label}</span>
                    </div>
                    <ul className="space-y-1.5">
                      {items.map((it, i) => (
                        <li key={i} className="flex gap-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                          <span className="flex-shrink-0 mt-0.5" style={{ color: meta.color }}>•</span>
                          <span>{it}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <p className="text-xs text-center mt-8" style={{ color: 'var(--text-muted)' }}>
          JAMA HOME · Thiết kế cho cuộc sống mới
        </p>
      </div>
    </Sidebar>
  );
}
