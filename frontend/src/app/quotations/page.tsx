'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Quotation, extractItems } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Nháp', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
  approved: { label: 'Duyệt', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  sent: { label: 'Đã gửi', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  rejected: { label: 'Từ chối', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  expired: { label: 'Hết hạn', color: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
};

const TYPE_MAP: Record<string, string> = {
  design: 'Thiết kế',
  construction: 'Thi công',
};

function fmtVND(n?: number) {
  if (!n) return '—';
  return new Intl.NumberFormat('vi-VN').format(n) + ' ₫';
}

export default function QuotationsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [selected, setSelected] = useState<Quotation | null>(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const data = extractItems(await api.getQuotations());
      setQuotations(data);
    } catch { toast('Không thể tải báo giá', 'error'); } finally {
      setLoadingData(false);
    }
  }, [toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  const handleApprove = async (id: string) => {
    try {
      const updated = await api.approveQuotation(id);
      setQuotations(prev => prev.map(q => q.id === updated.id ? updated : q));
      setSelected(updated);
    } catch { toast('Duyệt báo giá thất bại', 'error'); }
  };

  if (loading || !user) return null;

  const filtered = filter === 'all' ? quotations : quotations.filter(q => q.type === filter);

  return (
    <Sidebar>
    <div className="p-6 space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Báo giá</h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">{quotations.length} báo giá</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {[
          { key: 'all', label: 'Tất cả' },
          { key: 'design', label: 'Thiết kế' },
          { key: 'construction', label: 'Thi công' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            style={{
              background: filter === tab.key ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
              color: filter === tab.key ? 'var(--gold-400)' : 'var(--text-tertiary)',
              border: `1px solid ${filter === tab.key ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grid cards */}
      {loadingData ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
      ) : filtered.length === 0 ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Chưa có báo giá nào</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(q => {
            const st = STATUS_MAP[q.status] || STATUS_MAP.draft;
            return (
              <div
                key={q.id}
                className="rounded-2xl p-5 cursor-pointer transition-all hover:scale-[1.01]"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
                onClick={() => setSelected(q)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-mono text-xs text-[var(--gold-400)]">{q.code}</p>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-1">{q.title}</h3>
                  </div>
                  <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                  <span>{TYPE_MAP[q.type] || q.type}</span>
                  <span className="font-semibold text-sm text-[var(--text-primary)]">{fmtVND(q.total_amount)}</span>
                </div>
                <div className="flex items-center justify-between mt-3 pt-3 text-xs text-[var(--text-muted)]" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <span>Rev. {q.revision}</span>
                  <span>{q.valid_until ? `HH: ${new Date(q.valid_until).toLocaleDateString('vi-VN')}` : '—'}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center pt-[6vh] px-4" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg mx-4 rounded-2xl p-6 max-h-[80vh] overflow-y-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
            <button onClick={() => setSelected(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-[rgba(255,255,255,0.05)]">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
            <p className="font-mono text-xs text-[var(--gold-400)]">{selected.code}</p>
            <h2 className="text-xl font-bold text-[var(--text-primary)] mt-1 mb-4">{selected.title}</h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              {[
                ['Loại', TYPE_MAP[selected.type] || selected.type],
                ['Trạng thái', STATUS_MAP[selected.status]?.label || selected.status],
                ['Tổng giá', fmtVND(selected.total_amount)],
                ['Thuế', fmtVND(selected.tax_amount)],
                ['Phiên bản', `Rev. ${selected.revision}`],
                ['Hiệu lực', selected.valid_until ? new Date(selected.valid_until).toLocaleDateString('vi-VN') : '—'],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{value}</p>
                </div>
              ))}
            </div>

            {selected.notes && (
              <div className="rounded-xl p-3 mb-4" style={{ background: 'var(--surface-2)' }}>
                <p className="text-xs text-[var(--text-muted)] mb-1">Ghi chú</p>
                <p className="text-sm text-[var(--text-secondary)]">{selected.notes}</p>
              </div>
            )}

            {selected.status === 'draft' && (
              <button
                onClick={() => handleApprove(selected.id)}
                className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all"
                style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}
              >
                Duyệt báo giá
              </button>
            )}
          </div>
        </div>
      )}
    </div>
    </Sidebar>
  );
}
