'use client';

import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { GUIDE_SECTIONS, GUIDE_UPDATED, type GuideBlock } from '@/lib/huong-dan-content';

/**
 * Sổ tay sử dụng — bản đầy đủ trong app (sau đăng nhập), thay cho file guide
 * trên GitHub public. Nội dung nằm ở lib/huong-dan-content.ts; trang này chỉ
 * lo hiển thị: mục lục, tìm kiếm, render block.
 */

// Render **đậm** và `code` trong text — đủ dùng cho sổ tay, không cần lib markdown.
function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} className="font-semibold" style={{ color: 'var(--text-primary)' }}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`'))
      return <code key={i} className="px-1 rounded bg-white/10 text-[0.85em]">{part.slice(1, -1)}</code>;
    return part;
  });
}

function GuideBlockView({ block }: { block: GuideBlock }) {
  switch (block.type) {
    case 'h3':
      return <h3 className="text-sm font-semibold mt-4 mb-1.5" style={{ color: 'var(--text-primary)' }}>{renderInline(block.text || '')}</h3>;
    case 'p':
      return <p className="text-sm leading-relaxed mb-2.5" style={{ color: 'var(--text-secondary)' }}>{renderInline(block.text || '')}</p>;
    case 'list':
      return (
        <ul className="text-sm space-y-1.5 mb-3 pl-1">
          {(block.items || []).map((it, i) => (
            <li key={i} className="flex gap-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              <span style={{ color: '#C9A96E' }}>•</span><span>{renderInline(it)}</span>
            </li>
          ))}
        </ul>
      );
    case 'steps':
      return (
        <ol className="text-sm space-y-1.5 mb-3 pl-1">
          {(block.items || []).map((it, i) => (
            <li key={i} className="flex gap-2.5 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              <span className="shrink-0 w-5 h-5 rounded-full text-[11px] font-semibold flex items-center justify-center"
                style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>{i + 1}</span>
              <span>{renderInline(it)}</span>
            </li>
          ))}
        </ol>
      );
    case 'table':
      return (
        <div className="overflow-x-auto mb-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--surface-2)' }}>
                {(block.header || []).map((h, i) => (
                  <th key={i} className="text-left px-3 py-2 font-semibold whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>{renderInline(h)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(block.rows || []).map((row, i) => (
                <tr key={i} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  {row.map((cell, j) => (
                    <td key={j} className="px-3 py-2 align-top leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{renderInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case 'tip':
      return (
        <div className="text-sm leading-relaxed rounded-lg px-3 py-2.5 mb-3 flex gap-2"
          style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid rgba(201,169,110,0.25)', color: 'var(--text-secondary)' }}>
          <span>💡</span><span>{renderInline(block.text || '')}</span>
        </div>
      );
    case 'warn':
      return (
        <div className="text-sm leading-relaxed rounded-lg px-3 py-2.5 mb-3 flex gap-2"
          style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--text-secondary)' }}>
          <span>⚠️</span><span>{renderInline(block.text || '')}</span>
        </div>
      );
    default:
      return null;
  }
}

export default function HuongDanPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const q = query.trim().toLowerCase();
  const visibleSections = useMemo(() => {
    if (!q) return GUIDE_SECTIONS;
    return GUIDE_SECTIONS.filter(s => {
      if (s.title.toLowerCase().includes(q)) return true;
      return s.blocks.some(b =>
        (b.text || '').toLowerCase().includes(q) ||
        (b.items || []).some(it => it.toLowerCase().includes(q)) ||
        (b.rows || []).some(r => r.some(c => c.toLowerCase().includes(q)))
      );
    });
  }, [q]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-4 md:p-6 animate-in max-w-3xl">
        <h1 className="text-2xl font-bold mb-1 flex items-center gap-2.5">
          <LineIcon name="compass" size={22} />Sổ tay sử dụng
        </h1>
        <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
          Hướng dẫn đầy đủ mọi tính năng — cập nhật {GUIDE_UPDATED}. Nhân viên mới nên đọc kèm
          hướng dẫn từng bước theo vai trò (Cài đặt → «Xem lại hướng dẫn từng bước»).
        </p>

        {/* Tìm kiếm */}
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Tìm trong sổ tay… (vd: quên mật khẩu, chấm công, duyệt báo giá)"
          className="w-full mb-4 px-3.5 py-2.5 rounded-xl text-sm outline-none min-h-[44px]"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
        />

        {/* Mục lục — ẩn khi đang tìm */}
        {!q && (
          <div className="glass-card rounded-xl p-4 mb-5">
            <p className="text-xs font-semibold uppercase tracking-wide mb-2.5" style={{ color: 'var(--text-muted)' }}>Mục lục</p>
            <div className="flex flex-wrap gap-2">
              {GUIDE_SECTIONS.map(s => (
                <a key={s.id} href={`#${s.id}`}
                  className="text-xs px-2.5 py-1.5 rounded-lg transition-all hover:opacity-80 min-h-[32px] flex items-center gap-1.5"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                  <LineIcon name={s.icon} size={12} color="#C9A96E" />{s.title}
                </a>
              ))}
            </div>
          </div>
        )}

        {q && visibleSections.length === 0 && (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>
            Không tìm thấy «{query}» — thử từ khóa khác, hoặc hỏi nhóm kỹ thuật / bot Telegram <code className="px-1 rounded bg-white/10">/feedback</code>.
          </p>
        )}

        {/* Nội dung */}
        <div className="space-y-5">
          {visibleSections.map(s => (
            <section key={s.id} id={s.id} className="glass-card rounded-xl p-4 md:p-5" style={{ scrollMarginTop: '80px' }}>
              <div className="flex items-center gap-2.5 mb-1 flex-wrap">
                <LineIcon name={s.icon} size={18} color="#C9A96E" />
                <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{s.title}</h2>
                {(s.roles || []).map(r => (
                  <span key={r} className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{ background: 'rgba(96,165,250,0.12)', color: '#60A5FA', border: '1px solid rgba(96,165,250,0.3)' }}>{r}</span>
                ))}
              </div>
              <div className="mt-2.5">
                {s.blocks.map((b, i) => <GuideBlockView key={i} block={b} />)}
              </div>
            </section>
          ))}
        </div>

        {!q && GUIDE_SECTIONS.length > 0 && (
          <div className="mt-6 text-center">
            <a href="#" onClick={e => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
              className="text-xs" style={{ color: 'var(--text-muted)' }}>↑ Lên đầu trang</a>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
