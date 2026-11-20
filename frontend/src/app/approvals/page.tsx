'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import { getPermissions, UserRole } from '@/lib/roles';
import Sidebar from '@/components/layout/Sidebar';
import { api, ApprovalItem } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';
import { UyQuyenDuyet } from '@/components/attendance/UyQuyenDuyet';

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  pending: { label: 'Chờ duyệt', color: '#fbbf24' },
  approved: { label: 'Đã duyệt', color: '#34d399' },
  rejected: { label: 'Từ chối', color: '#f87171' },
  changes_requested: { label: 'Chờ sửa', color: '#60a5fa' },
  cancelled: { label: 'Đã hủy', color: 'var(--text-muted)' },
};

const TYPE_ICON: Record<string, string> = {
  leave: 'calendar',
  advance: 'cash',
  payroll_period: 'receipt',
  expense: 'truck',
  overtime: 'alarm',
  bonus_batch: 'trophy',
};

type Tab = 'pending' | 'mine' | 'handled';

// Lý do từ chối bấm sẵn — vẫn sửa được chữ sau khi bấm
const LY_DO_NGHI = ['Trùng lịch công trình', 'Team thiếu người ngày đó', 'Hết phép năm — đổi sang không lương', 'Thiếu chứng từ'];
const LY_DO_TIEN = ['Thiếu chứng từ', 'Sai số tiền'];

/** Tách "{loại} {n} ngày (YYYY-MM-DD → YYYY-MM-DD) — {tên}" (leaves.py) → số ngày + khoảng ngày; không khớp → null */
function tachDonNghi(title: string): { days: string; tu: string; den: string } | null {
  const m = title.match(/(\d+(?:\.\d+)?) ngày \((\d{4}-\d{2}-\d{2}) → (\d{4}-\d{2}-\d{2})\)/);
  return m ? { days: m[1], tu: m[2], den: m[3] } : null;
}
const ddmm = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;

/** ISO -> "dd/MM HH:mm" kiểu Việt, giữ nguyên giờ đã lưu (không lệch múi giờ). */
function fmtDateVN(s?: string | null): string {
  if (!s) return '';
  const m = s.match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (!m) return s.slice(0, 16);
  const [, , mo, d, h, mi] = m;
  return `${d}/${mo} ${h}:${mi}`;
}

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
  const [loadingData, setLoadingData] = useState(true);
  const [gop, setGop] = useState<Set<string> | null>(null); // đơn nghỉ đang tích trong hộp duyệt gộp

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
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
    } finally {
      setLoadingData(false);
    }
  }, [toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  const doApprove = async (item: ApprovalItem) => {
    setBusy(true);
    try {
      await api.approveRequest(item.id);
      toast(`Đã duyệt: ${item.title}`, 'success');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
    } finally { setBusy(false); }
  };

  // Duyệt gộp — CHỈ đơn nghỉ phép (loại có tiền vẫn duyệt từng đơn). Bỏ đơn của chính mình (server trả 403).
  const donNghiGop = pending.filter(i => i.type === 'leave' && i.status === 'pending' && i.requester_id !== user?.id);
  const doApproveGop = async () => {
    if (!gop || gop.size === 0) return;
    const ds = donNghiGop.filter(i => gop.has(i.id));
    setBusy(true);
    let chot = 0, chuyenCap = 0, boQua = 0;
    const loi: string[] = [];
    try {
      // Tuần tự: mỗi lần duyệt cuối ghi bảng chấm công + khoá hàng
      for (const it of ds) {
        try {
          const r = await api.approveRequest(it.id);
          if (r.request?.status === 'pending') chuyenCap++; else chot++;
        } catch (e) {
          const msg = e instanceof Error ? e.message : '';
          if (msg.includes('đã được xử lý')) boQua++;
          else loi.push(`${it.requester_name || it.title}: ${msg || 'lỗi'}`);
        }
      }
    } finally {
      setBusy(false);
      setGop(null);
      await load();
    }
    const tom = [`Đã duyệt ${chot} đơn`, chuyenCap ? `${chuyenCap} đơn chuyển cấp duyệt tiếp` : '', boQua ? `${boQua} đơn đã được xử lý trước đó` : '']
      .filter(Boolean).join(' · ');
    toast(loi.length ? `${tom}. Lỗi: ${loi.join('; ')}` : tom, loi.length ? 'error' : 'success');
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

  const doResubmit = async (item: ApprovalItem) => {
    setBusy(true);
    try {
      await api.resubmitRequest(item.id);
      toast('Đã nộp lại — người duyệt được báo', 'success');
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
        background: 'var(--surface-2)',
        borderColor: isOverdue(item) ? '#f87171' : 'var(--border-subtle)',
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <LineIcon name={TYPE_ICON[item.type] || 'clipboard'} size={18} />
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}>
              {item.type_label}
            </span>
            <span className="text-xs font-semibold" style={{ color: STATUS_BADGE[item.status]?.color }}>
              {STATUS_BADGE[item.status]?.label}
            </span>
            {item.total_steps > 1 && (
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>cấp {item.step}/{item.total_steps}</span>
            )}
            {item.delegated && <span className="text-xs" style={{ color: '#60a5fa' }}>(duyệt thay)</span>}
            {isOverdue(item) && <span className="text-xs font-semibold" style={{ color: '#f87171' }}><LineIcon name="alarm" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />QUÁ HẠN</span>}
          </div>
          <div className="font-medium mt-1.5" style={{ color: 'var(--text-primary)' }}>{item.title}</div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {item.requester_name && `Người tạo: ${item.requester_name} · `}
            {fmtDateVN(item.created_at)}
            {item.amount != null && ` · ${item.amount.toLocaleString('vi-VN')}đ`}
            {item.reason && ` · Lý do: ${item.reason}`}
          </div>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {mode === 'pending' && item.status === 'pending' && (
            <>
              <button onClick={() => doApprove(item)} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold disabled:opacity-40" style={{ background: '#34d399' }}>
                <LineIcon name="check" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Duyệt
              </button>
              <button onClick={() => { setRejectTarget(item); setRejectReason(''); }} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold disabled:opacity-40" style={{ background: '#f87171' }}>
                <LineIcon name="xCircle" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Từ chối
              </button>
            </>
          )}
          {mode === 'mine' && item.status === 'changes_requested' && (
            <button onClick={() => doResubmit(item)} disabled={busy}
              className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold disabled:opacity-40" style={{ background: 'var(--gold-500)' }}>
              Đã sửa, nộp lại
            </button>
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
    pending: 'Không có đơn nào chờ bạn duyệt',
    mine: 'Bạn chưa tạo đơn nào',
    handled: 'Chưa có đơn đã xử lý',
  };

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-4xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            <LineIcon name="check" size={20} className="inline-block align-[-2px] mr-1.5" />Phê duyệt
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
                  background: tab === t ? 'var(--gold-500)' : 'var(--surface-2)',
                  color: tab === t ? '#fff' : 'var(--text-secondary)',
                }}>
                {t === 'pending' ? `Chờ tôi (${pending.length})` : t === 'mine' ? 'Đơn của tôi' : 'Đã xử lý'}
              </button>
            ))}
          </div>
        </div>

        <UyQuyenDuyet />

        {tab === 'pending' && !loadingData && donNghiGop.length >= 2 && (
          <button onClick={() => setGop(new Set(donNghiGop.map(i => i.id)))} disabled={busy}
            className="w-full mb-3 px-4 rounded-full text-sm font-semibold disabled:opacity-40"
            style={{ background: 'var(--gold-400)', color: '#000', minHeight: 44 }}>
            <LineIcon name="check" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />
            Duyệt {donNghiGop.length} đơn nghỉ phép
          </button>
        )}

        <div className="space-y-3">
          {loadingData ? (
            [0, 1, 2].map(i => (
              <div key={i} className="rounded-2xl p-4 border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
                <div className="h-3 w-24 rounded mb-3" style={{ background: 'var(--border-subtle)' }} />
                <div className="h-4 w-2/3 rounded mb-2" style={{ background: 'var(--border-subtle)' }} />
                <div className="h-3 w-1/2 rounded" style={{ background: 'var(--border-subtle)' }} />
              </div>
            ))
          ) : lists[tab].length === 0 ? (
            <div className="rounded-2xl p-8 text-center border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
              {emptyText[tab]}
            </div>
          ) : (
            lists[tab].map(item => renderCard(item, tab))
          )}
        </div>

        {/* Duyệt gộp đơn nghỉ */}
        {gop && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
            <div className="rounded-2xl p-5 w-full max-w-md border max-h-[85vh] overflow-y-auto" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
              <div className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Duyệt cấp của bạn cho {gop.size} đơn nghỉ</div>
              <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                Bỏ tích đơn chưa muốn duyệt. Đơn nhiều cấp sẽ chuyển tiếp cho người duyệt cấp sau.
              </p>
              <div className="space-y-2 mb-4">
                {donNghiGop.map(it => {
                  const t = tachDonNghi(it.title);
                  const trung = !!t && donNghiGop.some(o => {
                    if (o.id === it.id) return false;
                    const u = tachDonNghi(o.title);
                    return !!u && u.tu <= t.den && t.tu <= u.den;
                  });
                  return (
                    <label key={it.id} className="flex items-start gap-3 rounded-xl p-3 border text-sm cursor-pointer"
                      style={{ borderColor: trung ? '#fbbf24' : 'var(--border-subtle)', minHeight: 44 }}>
                      <input type="checkbox" className="mt-1" checked={gop.has(it.id)}
                        onChange={e => {
                          const on = e.target.checked;
                          setGop(s => {
                            const n = new Set(s);
                            if (on) n.add(it.id); else n.delete(it.id);
                            return n;
                          });
                        }} />
                      <span style={{ color: 'var(--text-primary)' }}>
                        <b>{it.requester_name || ''}</b>
                        {t ? ` · ${t.days} ngày (${ddmm(t.tu)}${t.tu !== t.den ? ` → ${ddmm(t.den)}` : ''})` : ` · ${it.title}`}
                        {it.delegated && <span className="ml-1 text-xs" style={{ color: 'var(--text-muted)' }}>(duyệt thay)</span>}
                        {trung && <span className="block text-xs" style={{ color: '#fbbf24' }}>Trùng ngày với đơn khác trong danh sách</span>}
                      </span>
                    </label>
                  );
                })}
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setGop(null)} disabled={busy} className="px-4 rounded-full text-sm border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)', minHeight: 44 }}>
                  Đóng
                </button>
                <button onClick={doApproveGop} disabled={busy || gop.size === 0} className="px-4 rounded-full text-sm font-semibold disabled:opacity-40"
                  style={{ background: 'var(--gold-400)', color: '#000', minHeight: 44 }}>
                  {busy ? 'Đang duyệt…' : `Duyệt ${gop.size} đơn`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Reject modal */}
        {rejectTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
            <div className="rounded-2xl p-5 w-full max-w-md border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
              <div className="font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Từ chối: {rejectTarget.title}</div>
              {['leave', 'advance', 'expense'].includes(rejectTarget.type) && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {(rejectTarget.type === 'leave' ? LY_DO_NGHI : LY_DO_TIEN).map(c => (
                    <button key={c} type="button" onClick={() => setRejectReason(c)}
                      className="px-3 py-1.5 rounded-full text-xs border"
                      style={{ borderColor: rejectReason === c ? 'var(--gold-400)' : 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                      {c}
                    </button>
                  ))}
                </div>
              )}
              <textarea
                autoFocus
                rows={3}
                placeholder="Lý do từ chối (bắt buộc)..."
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border text-sm mb-3"
                style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
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
