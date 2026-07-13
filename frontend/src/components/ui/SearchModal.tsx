'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, extractItems } from '@/lib/api';

interface SearchItem {
  id: string;
  type: 'lead' | 'project' | 'contact';
  title: string;
  subtitle: string;
  icon: string;
  href?: string;
  stage?: string;
  budget?: string;
}

// Quick actions (static)
const QUICK_ACTIONS: SearchItem[] = [
  { id: 'a1', type: 'contact', title: 'Tạo Lead mới', subtitle: 'Thêm khách hàng tiềm năng mới', icon: '➕', href: '/leads' },
  { id: 'a2', type: 'contact', title: 'Báo giá tức thì', subtitle: 'Báo giá xây mới / cải tạo', icon: '⚡', href: '/quote-tool' },
  { id: 'a3', type: 'contact', title: 'Xem báo cáo', subtitle: 'Doanh thu, pipeline, conversion', icon: '📊', href: '/reports' },
  { id: 'a4', type: 'contact', title: 'Kế toán', subtitle: 'Giao dịch, bảng lương, hoa hồng', icon: '💰', href: '/accounting' },
  { id: 'a5', type: 'contact', title: 'Cài đặt', subtitle: 'Thông tin cá nhân, Telegram Bot', icon: '⚙️', href: '/settings' },
];

function fuzzyMatch(text: string, query: string): boolean {
  const t = text.toLowerCase();
  const q = query.toLowerCase();
  // Check if all query chars exist in order
  let qi = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) qi++;
  }
  return qi === q.length;
}

function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span style={{ color: 'var(--gold-400)', fontWeight: 600 }}>{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  lead: { label: 'Lead', color: '#3B82F6' },
  project: { label: 'Dự án', color: '#10B981' },
  contact: { label: 'Hành động', color: '#C9A96E' },
};

export default function SearchModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [liveItems, setLiveItems] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Fetch live data when modal opens
  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    Promise.all([
      api.getLeads({ page_size: '100' }).then(r => extractItems(r)).catch(() => []),
      api.getProjects({ page_size: '100' }).then(r => extractItems(r)).catch(() => []),
    ]).then(([leads, projects]) => {
      const items: SearchItem[] = [
        ...(leads as unknown as Array<Record<string, unknown>>).map(l => ({
          id: String(l.id), type: 'lead' as const,
          title: String(l.name || ''),
          subtitle: `${l.phone || ''} · ${l.source || ''} · ${l.stage || ''}`,
          icon: '👤', href: '/leads',
        })),
        ...(projects as unknown as Array<Record<string, unknown>>).map(p => ({
          id: String(p.id), type: 'project' as const,
          title: `${p.code || ''} — ${p.name || ''}`,
          subtitle: `${p.client_name || ''} · ${p.progress ?? 0}%`,
          icon: '🏗️', href: '/projects',
        })),
      ];
      setLiveItems(items);
      setLoading(false);
    });
  }, [isOpen]);

  const allItems = [...liveItems, ...QUICK_ACTIONS];
  const results = query.length > 0
    ? allItems.filter(item =>
        fuzzyMatch(item.title, query) ||
        fuzzyMatch(item.subtitle, query)
      )
    : QUICK_ACTIONS;

  useEffect(() => {
    if (isOpen) {
      void Promise.resolve().then(() => {
        setQuery('');
        setSelectedIdx(0);
      });
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleSelect = useCallback((item: SearchItem) => {
    onClose();
    if (item.href) router.push(item.href);
  }, [onClose, router]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIdx]) {
      handleSelect(results[selectedIdx]);
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [results, selectedIdx, handleSelect, onClose]);

  useEffect(() => {
    void Promise.resolve().then(() => setSelectedIdx(0));
  }, [query]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-xl rounded-2xl overflow-hidden animate-in"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)', boxShadow: 'var(--shadow-xl)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Tìm lead, dự án, khách hàng... (Esc để đóng)"
            className="flex-1 bg-transparent border-none outline-none text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)]"
          />
          <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono" style={{ background: 'var(--surface-3)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto py-2">
          {results.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm text-[var(--text-muted)]">Không tìm thấy kết quả cho &quot;{query}&quot;</p>
            </div>
          ) : (
            <>
              {query.length === 0 && (
                <p className="px-4 py-1 text-[10px] text-[var(--text-disabled)] uppercase tracking-wide font-semibold">Hành động nhanh</p>
              )}
              {results.map((item, i) => {
                const typeInfo = TYPE_LABELS[item.type];
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIdx(i)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                    style={{
                      background: i === selectedIdx ? 'rgba(201,169,110,0.08)' : 'transparent',
                    }}
                  >
                    <span className="text-lg flex-shrink-0">{item.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                        {highlightMatch(item.title, query)}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] truncate">
                        {highlightMatch(item.subtitle, query)}
                      </p>
                    </div>
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold flex-shrink-0"
                      style={{ background: `${typeInfo.color}15`, color: typeInfo.color }}
                    >
                      {typeInfo.label}
                    </span>
                  </button>
                );
              })}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t flex items-center gap-4 text-[10px] text-[var(--text-disabled)]" style={{ borderColor: 'var(--border-subtle)' }}>
          <span>↑↓ di chuyển</span>
          <span>↵ chọn</span>
          <span>esc đóng</span>
          <span className="ml-auto">{results.length} kết quả</span>
        </div>
      </div>
    </div>
  );
}
