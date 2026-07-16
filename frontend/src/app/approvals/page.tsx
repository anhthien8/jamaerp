'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { getPermissions, UserRole } from '@/lib/roles';
import Sidebar from '@/components/layout/Sidebar';
import { api, ApprovalItem } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  pending: { label: 'Chờ duyệt', color: '#fbbf24' },
  approved: { label: 'Đã duyệt', color: '#34d399' },
  rejected: { label: 'Từ chối', color: '#f87171' },
  changes_requested: { label: 'Chờ sửa', color: '#60a5fa' },
  cancelled: { label: 'Đã hủy', color: 'var(--text-muted)' },
};

const TYPE_ICON: Record<string, string> = {
  leave: '🏖️',
  advance: '💸',
  payroll_period: '🧾',
  expense: '🚗',
  overtime: '⏰',
};

type Tab = 'pending' | 'mine' | 'handled';

export default function ApprovalsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [tab, setTab] = useState<Tab>('pending');
  const [pending, setPending] = useState<ApprovalItem[]>([]);
  const [mine, setMine] = useState<ApprovalItem[]>([]);
  const [handled, setHandled] = useState<ApprovalItem[]>([]);
  const [rejectTarget, setRejectTarget] = useState<ApprovalItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canViewApprovals) router.push('/');
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const [p, m, h] = await Promise.all([
        api.approvalsPendingForMe(),
        api.approvalsMyRequests(),
        api.approvalsHandled(),
      ]);
      setPending(p.items);
      setMine(m.items);
      setHandled(h.items);
    } catch (e) {
      toast(`Không tải được danh sách phê duyệt: ${e instanceof Error ? e.message : ''}`, 'error');
    }
  }, [toast]);

  useEffect(() => { if (user) void load(); }, [user, load]);

  const doApprove = async (item: ApprovalItem) => {
    setBusy(true);
    try {
      await api.approveRequest(item.id);
      toast(`✅ Đã duyệt: ${item.title}`, 'success');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
    } finally { setBusy(false); }
  };

  const doReject = async () => {
    if (!rejectTarget || rejectReason.trim().length < 2) {
      toast('Nhập lý do từ chối (≥2 ký tự)', 'error');
      return;
    }
    setBusy(true);
    try {
      await api.rejectRequest(rejectTarget.id, rejectReason.trim());
      toast(`Đã từ chối: ${rejectTarget.title}`, 'success');
      setRejectTarget(null);
      setRejectReason('');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
    } finally { setBusy(false); }
  };

  const doCancel = async (item: ApprovalItem) => {
    setBusy(true);
    try {
      await api.cancelRequest(item.id);
      toast('Đã hủy đơn', 'success');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
    } finally { setBusy(false); }
  };

  if (loading || !user) return null;

  const isOverdue = (item: ApprovalItem) =>
    item.due_at && item.status === 'pending' && new Date(item.due_at) < new Date();

  const renderCard = (item: ApprovalItem, mode: Tab) => (
    <div
      key={item.id}
      className="rounded-2xl p-4 border"
      style={{
        background: 'var(--bg-elevated)',
        borderColor: isOverdue(item) ? '#f87171' : 'var(--border-subtle)',
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span>{TYPE_ICON[item.type] || '📋'}</span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-base)', color: 'var(--text-muted)' }}>
              {item.type_label}
            </span>
            <span className="text-xs font-semibold" style={{ color: STATUS_BADGE[item.status]?.color }}>
              {STATUS_BADGE[item.status]?.label}
            </span>
            {item.total_steps > 1 && (
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>cấp {item.step}/{item.total_steps}</span>
            )}
            {item.delegated && <span className="text-xs" style={{ color: '#60a5fa' }}>(duyệt thay)</span>}
            {isOverdue(item) && <span className="text-xs font-semibold" style={{ color: '#f87171' }}>⏰ QUÁ HẠN</span>}
          </div>
          <div className="font-medium mt-1.5" style={{ color: 'var(--text-primary)' }}>{item.title}</div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {item.requester_name && `Người tạo: ${item.requester_name} · `}
            {item.created_at?.slice(0, 16)}
            {item.amount != null && ` · ${item.amount.toLocaleString('vi-VN')}đ`}
            {item.reason && ` · Lý do: ${item.reason}`}
          </div>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {mode === 'pending' && item.status === 'pending' && (
            <>
              <button onClick={() => doApprove(item)} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold disabled:opacity-40" style={{ background: '#34d399' }}>
                ✅ Duyệt
              </button>
              <button onClick={() => { setRejectTarget(item); setRejectReason(''); }} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold disabled:opacity-40" style={{ background: '#f87171' }}>
                ❌ Từ chối
              </button>
            </>
          )}
          {mode === 'mine' && (item.status === 'pending' || item.status === 'changes_requested') && (
            <button onClick={() => doCancel(item)} disabled={busy}
              className="px-3 py-1.5 rounded-lg text-sm border disabled:opacity-40"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
              Hủy đơn
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const lists: Record<Tab, ApprovalItem[]> = { pending, mine, handled };
  const emptyText: Record<Tab, string> = {
    pending: '🎉 Không có đơn nào chờ bạn duyệt',
    mine: 'Bạn chưa tạo đơn nào',
    handled: 'Chưa có đơn đã xử lý',
  };

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-4xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            ✅ Phê duyệt
            {pending.length > 0 && (
              <span className="ml-2 text-sm px-2 py-0.5 rounded-full text-white" style={{ background: '#f87171' }}>
                {pending.length}
              </span>
            )}
          </h1>
          <div className="flex gap-2">
            {(['pending', 'mine', 'handled'] as Tab[]).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className="px-3 py-1.5 rounded-lg text-sm font-medium transition"
                style={{
                  background: tab === t ? 'var(--gold-500)' : 'var(--bg-elevated)',
                  color: tab === t ? '#fff' : 'var(--text-secondary)',
                }}>
                {t === 'pending' ? `Chờ tôi (${pending.length})` : t === 'mine' ? 'Đơn của tôi' : 'Đã xử lý'}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          {lists[tab].length === 0 && (
            <div className="rounded-2xl p-8 text-center border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
              {emptyText[tab]}
            </div>
          )}
          {lists[tab].map(item => renderCard(item, tab))}
        </div>

        {/* Reject modal */}
        {rejectTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
            <div className="rounded-2xl p-5 w-full max-w-md border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
              <div className="font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Từ chối: {rejectTarget.title}</div>
              <textarea
                autoFocus
                rows={3}
                placeholder="Lý do từ chối (bắt buộc)..."
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border text-sm mb-3"
                style={{ background: 'var(--bg-base)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setRejectTarget(null)} className="px-4 py-2 rounded-xl text-sm border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                  Đóng
                </button>
                <button onClick={doReject} disabled={busy} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-40" style={{ background: '#f87171' }}>
                  Xác nhận từ chối
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
