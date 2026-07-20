'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, FeedbackItem } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { getPermissions, UserRole } from '@/lib/roles';

const CATEGORY_LABELS: Record<string, string> = {
  bug: 'Bug / Lỗi', feature_request: 'Tính năng mới',
  workflow_improvement: 'Cải thiện workflow', other: 'Khác',
};
const STATUS_LABELS: Record<string, string> = {
  new: 'Mới', in_review: 'Đang xem', done: 'Đã xử lý', rejected: 'Từ chối',
};
const STATUS_COLORS: Record<string, string> = {
  new: '#3B82F6', in_review: '#F59E0B', done: '#10B981', rejected: '#EF4444',
};

export default function FeedbackPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [selected, setSelected] = useState<FeedbackItem | null>(null);
  const [replyText, setReplyText] = useState('');

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canViewFeedback) router.push('/');
  }, [user, loading, router]);

  const loadFeedback = useCallback(async () => {
    const params: Record<string, string> = { page: String(page), page_size: '20' };
    if (statusFilter) params.status = statusFilter;
    if (categoryFilter) params.category = categoryFilter;
    try {
      const data = await api.getFeedback(params);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch { toast('Không thể tải danh sách góp ý', 'error'); }
  }, [page, statusFilter, categoryFilter, toast]);

  useEffect(() => { loadFeedback(); }, [loadFeedback]);

  const updateFeedback = async (id: string, status?: string, adminReply?: string) => {
    const body: { status?: string; admin_reply?: string } = {};
    if (status) body.status = status;
    if (adminReply !== undefined) body.admin_reply = adminReply;
    await api.updateFeedback(id, body);
    setReplyText('');
    setSelected(null);
    loadFeedback();
  };

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <h1 className="text-2xl font-bold mb-1">Góp ý từ nhân sự</h1>
        <p className="text-sm text-[var(--text-muted)] mb-6">{total} phản hồi · gửi qua bot Telegram lệnh /feedback</p>

        {/* Filters */}
        <div className="flex gap-3 mb-4 flex-wrap">
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-xl text-sm" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}>
            <option value="">Tất cả trạng thái</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-xl text-sm" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}>
            <option value="">Tất cả loại</option>
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {/* Table */}
        <div className="rounded-2xl overflow-x-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <th className="text-left px-4 py-3 text-[var(--text-muted)]">Người gửi</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)]">Loại</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)]">Nội dung</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)]">Trạng thái</th>
                <th className="text-left px-4 py-3 text-[var(--text-muted)]">Ngày</th>
              </tr>
            </thead>
            <tbody>
              {items.map(fb => (
                <tr key={fb.id} className="cursor-pointer hover:bg-white/[0.03] transition-colors"
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  onClick={() => { setSelected(fb); setReplyText(fb.admin_reply || ''); }}>
                  <td className="px-4 py-3 text-[var(--text-primary)]">{fb.user_name || 'N/A'}</td>
                  <td className="px-4 py-3"><span className="text-xs px-2 py-1 rounded-full bg-white/5">{CATEGORY_LABELS[fb.category] || fb.category}</span></td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] max-w-[200px] truncate">{fb.content.substring(0, 80)}{fb.content.length > 80 ? '...' : ''}</td>
                  <td className="px-4 py-3"><span className="text-xs px-2 py-1 rounded-full font-medium" style={{ background: `${STATUS_COLORS[fb.status]}20`, color: STATUS_COLORS[fb.status] }}>{STATUS_LABELS[fb.status]}</span></td>
                  <td className="px-4 py-3 text-xs text-[var(--text-muted)] whitespace-nowrap">{fb.created_at.substring(8, 10)}/{fb.created_at.substring(5, 7)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {total > 20 && (
          <div className="flex justify-center gap-2 mt-4">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 rounded-lg text-sm disabled:opacity-40 bg-white/5">Trước</button>
            <span className="px-3 py-1 text-sm text-[var(--text-muted)]">Trang {page}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={items.length < 20} className="px-3 py-1 rounded-lg text-sm disabled:opacity-40 bg-white/5">Sau</button>
          </div>
        )}

        {/* Detail Modal */}
        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative w-full max-w-lg rounded-2xl p-6" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <h3 className="text-lg font-bold mb-4">Chi tiết Feedback</h3>
              <div className="space-y-3 text-sm">
                <div><span className="text-[var(--text-muted)]">Người gửi: </span>{selected.user_name || 'N/A'}</div>
                <div><span className="text-[var(--text-muted)]">Loại: </span>{CATEGORY_LABELS[selected.category]}</div>
                <div className="p-3 rounded-xl whitespace-pre-wrap" style={{ background: 'var(--surface-2)' }}>{selected.content}</div>
                <div>
                  <span className="text-[var(--text-muted)]">Trạng thái: </span>
                  <div className="flex gap-2 mt-1">
                    {Object.entries(STATUS_LABELS).map(([k, v]) => (
                      <button key={k} onClick={() => updateFeedback(selected.id, k)}
                        className="text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ background: selected.status === k ? `${STATUS_COLORS[k]}20` : 'var(--surface-3)', color: selected.status === k ? STATUS_COLORS[k] : 'var(--text-muted)', border: `1px solid ${selected.status === k ? STATUS_COLORS[k] : 'transparent'}` }}>{v}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Phản hồi admin:</span>
                  <textarea value={replyText} onChange={e => setReplyText(e.target.value)} rows={3}
                    className="w-full mt-1 p-3 rounded-xl text-sm resize-none" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                    placeholder="Nhập phản hồi..." />
                </div>
                <div className="flex gap-2 pt-2">
                  <button onClick={() => updateFeedback(selected.id, undefined, replyText)}
                    className="px-4 py-2 rounded-xl text-sm font-medium" style={{ background: 'var(--gold-500)', color: '#000' }}>Gửi phản hồi</button>
                  <button onClick={() => setSelected(null)} className="px-4 py-2 rounded-xl text-sm bg-white/5">Đóng</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
