'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import {
  api, AttendanceRecord, AttendanceSummary, TeamAttendanceRow,
  LeaveItem, LeaveBalanceInfo, PayrollRow,
} from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

const fmtMoney = (v: number) => `${v.toLocaleString('vi-VN')}đ`;
const currentPeriod = () => new Date().toISOString().slice(0, 7);

/** Backend trả datetime UTC dạng "2026-07-15 01:00:00[.ffffff]" (naive) —
 *  PHẢI đổi sang giờ VN trước khi hiển thị (bug cũ: slice chuỗi UTC → sai 7 tiếng). */
const fmtTimeVN = (utcStr: string | null | undefined): string => {
  if (!utcStr) return '—';
  const iso = utcStr.includes('T') ? utcStr : utcStr.replace(' ', 'T');
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
  if (Number.isNaN(d.getTime())) return utcStr.slice(11, 16) || '—';
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });
};

const OT_BADGE: Record<string, { label: string; color: string }> = {
  none: { label: '—', color: 'var(--text-muted)' },
  pending: { label: 'OT chờ duyệt', color: '#fbbf24' },
  approved: { label: 'OT đã duyệt', color: '#34d399' },
  rejected: { label: 'OT từ chối', color: '#f87171' },
};

const LEAVE_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Chờ duyệt', color: '#fbbf24' },
  approved: { label: 'Đã duyệt', color: '#34d399' },
  rejected: { label: 'Từ chối', color: '#f87171' },
  cancelled: { label: 'Đã hủy', color: 'var(--text-muted)' },
};

type Tab = 'attendance' | 'leave' | 'payslip';

/** Chế độ chốt sổ mùng 1 cho Kế toán (spec 08 §2.3) — stepper đi đúng trình tự,
 *  đồng thời là UI vận hành bảng lương (generate → submit → pay, API có sẵn). */
function ClosingStepper({ period, needsReview, otPending, onRefresh }: {
  period: string; needsReview: number; otPending: number; onRefresh: () => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [payroll, setPayroll] = useState<{ status: string | null; total_net: number; items: unknown[] } | null>(null);

  const loadPayroll = useCallback(async () => {
    try {
      const res = await api.payrollList(period);
      setPayroll({ status: res.status, total_net: res.total_net, items: res.items });
    } catch { setPayroll(null); }
  }, [period]);

  useEffect(() => { void loadPayroll(); }, [loadPayroll]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      toast(ok, 'success');
      await loadPayroll();
      onRefresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lỗi', 'error');
    } finally { setBusy(false); }
  };

  const status = payroll?.status;
  const steps = [
    {
      key: 'review', label: `1. Rà ca cần xác nhận`, done: needsReview === 0,
      detail: needsReview > 0 ? `⚠️ Còn ${needsReview} ca quên tan ca — sửa ở bảng công bên dưới` : 'Sạch',
    },
    {
      key: 'ot', label: '2. Duyệt tăng ca tồn', done: otPending === 0,
      detail: otPending > 0 ? `⏳ Còn ${otPending} OT chờ duyệt` : 'Sạch',
    },
    {
      key: 'generate', label: '3. Sinh bảng lương', done: !!status,
      detail: status ? `Đã sinh (${payroll?.items.length ?? 0} người · thực lĩnh ${fmtMoney(payroll?.total_net ?? 0)})` : 'Chưa sinh',
      action: !status && (
        <button disabled={busy} onClick={() => run(() => api.payrollGenerate(period), `Đã sinh bảng lương kỳ ${period}`)}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40" style={{ background: 'var(--gold-500)' }}>
          Sinh bảng lương
        </button>
      ),
    },
    {
      key: 'submit', label: '4. Trình Giám đốc duyệt', done: !!status && status !== 'draft',
      detail: status === 'draft' ? 'Bảng lương đang ở bản nháp' :
              status === 'pending_approval' ? '⏳ Đang chờ Giám đốc duyệt (nhắc qua Telegram sau 72h)' :
              status === 'approved' ? '✅ Đã duyệt — kỳ đã KHÓA' :
              status === 'paid' ? '💵 Đã chi + phiếu lương đã gửi' : '—',
      action: status === 'draft' && (
        <button disabled={busy} onClick={() => run(() => api.payrollSubmit(period), 'Đã trình duyệt — Giám đốc sẽ nhận thông báo')}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40" style={{ background: 'var(--gold-500)' }}>
          Trình duyệt
        </button>
      ),
    },
    {
      key: 'pay', label: '5. Chi lương + gửi phiếu', done: status === 'paid',
      detail: status === 'approved' ? 'Sẵn sàng chi — phiếu lương sẽ gửi Telegram RIÊNG từng người' :
              status === 'paid' ? '✅ Hoàn tất kỳ' : 'Chờ bước 4',
      action: status === 'approved' && (
        <button disabled={busy}
          onClick={() => run(() => api.payrollPay(period), 'Đã chi — phiếu lương đang gửi từng người')}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40" style={{ background: '#34d399' }}>
          Xác nhận đã chi
        </button>
      ),
    },
  ];

  return (
    <div className="rounded-2xl p-4 border" style={{ background: 'rgba(201,169,110,0.05)', borderColor: 'rgba(201,169,110,0.3)' }}>
      <div className="font-bold mb-3" style={{ color: 'var(--text-primary)' }}>🧾 Chốt sổ kỳ {period} <span className="text-xs font-normal" style={{ color: 'var(--text-muted)' }}>(dành cho Kế toán — đi từ trên xuống)</span></div>
      <div className="space-y-2">
        {steps.map(s => (
          <div key={s.key} className="flex items-center justify-between gap-3 p-2.5 rounded-xl" style={{ background: 'var(--bg-elevated, rgba(255,255,255,0.03))' }}>
            <div className="min-w-0">
              <div className="text-sm font-semibold" style={{ color: s.done ? '#34d399' : 'var(--text-primary)' }}>
                {s.done ? '✅' : '○'} {s.label}
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{s.detail}</div>
            </div>
            {s.action || null}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AttendancePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [tab, setTab] = useState<Tab>('attendance');
  const [period, setPeriod] = useState(currentPeriod());
  const [today, setToday] = useState<AttendanceRecord | null>(null);
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [teamRows, setTeamRows] = useState<TeamAttendanceRow[]>([]);
  const [pendingOT, setPendingOT] = useState<(AttendanceRecord & { full_name: string })[]>([]);
  const [busy, setBusy] = useState(false);

  // Leave state
  const [balance, setBalance] = useState<LeaveBalanceInfo | null>(null);
  const [myLeaves, setMyLeaves] = useState<LeaveItem[]>([]);
  const [leaveForm, setLeaveForm] = useState({
    leave_type: 'annual', start_date: '', end_date: '', half_day: false, reason: '',
  });
  const [showLeaveForm, setShowLeaveForm] = useState(false);

  // Payslip state
  const [payslips, setPayslips] = useState<PayrollRow[]>([]);

  const isApprover = user && ['admin', 'leader', 'accountant'].includes(user.role);
  const canSeeTeam = isApprover;

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const loadAttendance = useCallback(async () => {
    try {
      const [t, me] = await Promise.all([api.attendanceToday(), api.myAttendance(period)]);
      setToday(t.record);
      setSummary(me.summary);
      setRecords(me.records);
      if (canSeeTeam) {
        const [team, ot] = await Promise.all([api.teamAttendance(period), api.pendingOT()]);
        setTeamRows(team.items);
        setPendingOT(ot.items);
      }
    } catch (e) {
      toast(`Không tải được bảng công: ${e instanceof Error ? e.message : ''}`, 'error');
    }
  }, [period, canSeeTeam, toast]);

  const loadLeave = useCallback(async () => {
    try {
      const [b, l] = await Promise.all([api.myLeaveBalance(), api.myLeaves()]);
      setBalance(b);
      setMyLeaves(l.items);
    } catch (e) {
      toast(`Không tải được dữ liệu phép: ${e instanceof Error ? e.message : ''}`, 'error');
    }
  }, [toast]);

  const loadPayslips = useCallback(async () => {
    try {
      const p = await api.myPayslips();
      setPayslips(p.items);
    } catch (e) {
      toast(`Không tải được phiếu lương: ${e instanceof Error ? e.message : ''}`, 'error');
    }
  }, [toast]);

  useEffect(() => {
    if (!user) return;
    if (tab === 'attendance') void loadAttendance();
    if (tab === 'leave') void loadLeave();
    if (tab === 'payslip') void loadPayslips();
  }, [user, tab, loadAttendance, loadLeave, loadPayslips]);

  // Offline-queue (spec 08 §1.1): 4G rớt giữa chừng — lưu lại, tự gửi khi có mạng.
  // Backend idempotent (1 bản ghi/ngày) nên retry an toàn tuyệt đối.
  const QUEUE_KEY = 'jama_attendance_queue';

  const flushQueue = useCallback(async () => {
    if (typeof window === 'undefined') return;
    const pending = localStorage.getItem(QUEUE_KEY);
    if (!pending) return;
    try {
      const action = JSON.parse(pending) as { type: 'checkin' | 'checkout' };
      if (action.type === 'checkin') await api.attendanceCheckin();
      else await api.attendanceCheckout();
      localStorage.removeItem(QUEUE_KEY);
      toast('✅ Đã gửi lại chấm công thành công (lúc trước mất mạng)', 'success');
      await loadAttendance();
    } catch {
      /* vẫn chưa có mạng — giữ queue, chờ lần sau */
    }
  }, [toast, loadAttendance]);

  useEffect(() => {
    void flushQueue(); // thử gửi lại khi mở trang
    window.addEventListener('online', flushQueue);
    return () => window.removeEventListener('online', flushQueue);
  }, [flushQueue]);

  const isNetworkError = (e: unknown) =>
    e instanceof TypeError || (e instanceof Error && /fetch|network|Failed/i.test(e.message));

  const doCheckin = async () => {
    setBusy(true);
    try {
      const res = await api.attendanceCheckin();
      toast(res.message, res.created ? 'success' : 'info');
      await loadAttendance();
    } catch (e) {
      if (isNetworkError(e)) {
        localStorage.setItem(QUEUE_KEY, JSON.stringify({ type: 'checkin', at: Date.now() }));
        toast('📶 Mất mạng — sẽ tự vào ca lại khi có sóng. Hoặc dùng Telegram: /checkin', 'info');
      } else {
        toast(`Vào ca lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
      }
    } finally { setBusy(false); }
  };

  const doCheckout = async () => {
    setBusy(true);
    try {
      const res = await api.attendanceCheckout();
      toast(res.message, 'success');
      await loadAttendance();
    } catch (e) {
      if (isNetworkError(e)) {
        localStorage.setItem(QUEUE_KEY, JSON.stringify({ type: 'checkout', at: Date.now() }));
        toast('📶 Mất mạng — sẽ tự tan ca lại khi có sóng. Hoặc dùng Telegram: /checkout', 'info');
      } else {
        toast(`Tan ca lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
      }
    } finally { setBusy(false); }
  };

  const submitLeave = async () => {
    if (!leaveForm.start_date || !leaveForm.end_date || leaveForm.reason.length < 3) {
      toast('Điền đủ ngày và lý do (≥3 ký tự)', 'error');
      return;
    }
    setBusy(true);
    try {
      await api.createLeave(leaveForm);
      toast('Đã gửi đơn nghỉ phép — chờ duyệt', 'success');
      setShowLeaveForm(false);
      setLeaveForm({ leave_type: 'annual', start_date: '', end_date: '', half_day: false, reason: '' });
      await loadLeave();
    } catch (e) {
      toast(`Không gửi được đơn: ${e instanceof Error ? e.message : ''}`, 'error');
    } finally { setBusy(false); }
  };

  const handleOT = async (id: string, ok: boolean) => {
    try {
      if (ok) await api.approveOT(id); else await api.rejectOT(id);
      toast(ok ? 'Đã duyệt OT' : 'Đã từ chối OT', 'success');
      await loadAttendance();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : ''}`, 'error');
    }
  };

  if (loading || !user) return null;

  const checkedIn = !!today?.check_in;
  const checkedOut = !!today?.check_out;

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-6xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>⏱️ Chấm công & Nghỉ phép</h1>
          <div className="flex gap-2">
            {(['attendance', 'leave', 'payslip'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="px-3 py-1.5 rounded-lg text-sm font-medium transition"
                style={{
                  background: tab === t ? 'var(--gold-500)' : 'var(--bg-elevated)',
                  color: tab === t ? '#fff' : 'var(--text-secondary)',
                }}
              >
                {t === 'attendance' ? 'Chấm công' : t === 'leave' ? 'Nghỉ phép' : 'Phiếu lương'}
              </button>
            ))}
          </div>
        </div>

        {tab === 'attendance' && (
          <div className="space-y-5">
            {/* Check-in/out card */}
            <div className="rounded-2xl p-5 border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Hôm nay</div>
                  <div className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {checkedIn ? `Vào: ${fmtTimeVN(today?.check_in)}` : 'Chưa vào ca'}
                    {checkedOut && ` · Ra: ${fmtTimeVN(today?.check_out)} · ${today?.work_hours}h`}
                    {today && today.ot_hours > 0 && ` · OT ${today.ot_hours}h (${OT_BADGE[today.ot_status]?.label})`}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={doCheckin}
                    disabled={busy || checkedIn}
                    className="px-4 py-2 rounded-xl font-semibold text-white disabled:opacity-40"
                    style={{ background: 'var(--gold-500)' }}
                  >✅ Vào ca</button>
                  <button
                    onClick={doCheckout}
                    disabled={busy || !checkedIn || checkedOut}
                    className="px-4 py-2 rounded-xl font-semibold disabled:opacity-40 border"
                    style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                  >🏁 Tan ca</button>
                </div>
              </div>
              <div className="text-xs mt-2 p-2 rounded-lg" style={{ color: 'var(--text-secondary)', background: 'rgba(201,169,110,0.08)', border: '1px solid rgba(201,169,110,0.2)' }}>
                ⭐ <b>Cách nhanh nhất — Telegram:</b> nhắn <code className="px-1 rounded bg-white/10">/checkin</code> với bot (công trường: <code className="px-1 rounded bg-white/10">/checkin [Mã dự án]</code> kèm GPS, tan ca: <code className="px-1 rounded bg-white/10">/checkout</code>). Nút trên web dùng khi đang ngồi máy tính.
              </div>
            </div>

            {/* Chốt sổ — Kế toán/Admin (spec 08 §2.3, cũng là UI vận hành bảng lương) */}
            {(user.role === 'accountant' || user.role === 'admin') && (
              <ClosingStepper
                period={period}
                needsReview={teamRows.reduce((sum, row) => sum + (row.needs_review || 0), 0)}
                otPending={pendingOT.length}
                onRefresh={loadAttendance}
              />
            )}

            {/* Month summary */}
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="month"
                value={period}
                onChange={e => setPeriod(e.target.value)}
                className="px-3 py-1.5 rounded-lg border text-sm"
                style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
              {summary && (
                <div className="flex flex-wrap gap-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span>Công: <b style={{ color: 'var(--text-primary)' }}>{summary.work_days_fraction}</b></span>
                  <span>Giờ: <b style={{ color: 'var(--text-primary)' }}>{summary.total_hours}h</b></span>
                  <span>OT duyệt: <b style={{ color: 'var(--text-primary)' }}>{summary.ot_approved_hours}h</b></span>
                  {summary.needs_review > 0 && <span style={{ color: '#fbbf24' }}>⚠️ {summary.needs_review} ca cần xác nhận</span>}
                </div>
              )}
            </div>

            {/* Records table */}
            <div className="rounded-2xl border overflow-x-auto" style={{ borderColor: 'var(--border-subtle)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: 'var(--text-muted)', background: 'var(--bg-elevated)' }}>
                    <th className="text-left px-4 py-2.5">Ngày</th>
                    <th className="text-left px-4 py-2.5">Vào</th>
                    <th className="text-left px-4 py-2.5">Ra</th>
                    <th className="text-right px-4 py-2.5">Giờ công</th>
                    <th className="text-left px-4 py-2.5">OT</th>
                    <th className="text-left px-4 py-2.5">Nguồn</th>
                  </tr>
                </thead>
                <tbody>
                  {records.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center" style={{ color: 'var(--text-muted)' }}>Chưa có dữ liệu chấm công kỳ này</td></tr>
                  )}
                  {records.map(r => (
                    <tr key={r.id} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-primary)' }}>
                        {r.work_date}{r.needs_review && ' ⚠️'}
                      </td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtTimeVN(r.check_in)}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtTimeVN(r.check_out)}</td>
                      <td className="px-4 py-2.5 text-right" style={{ color: 'var(--text-primary)' }}>{r.work_hours}h</td>
                      <td className="px-4 py-2.5" style={{ color: OT_BADGE[r.ot_status]?.color }}>
                        {r.ot_hours > 0 ? `${r.ot_hours}h · ${OT_BADGE[r.ot_status]?.label}` : '—'}
                      </td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-muted)' }}>{r.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* OT pending (approvers) */}
            {isApprover && pendingOT.length > 0 && (
              <div className="rounded-2xl p-4 border" style={{ borderColor: '#fbbf24', background: 'rgba(251,191,36,0.05)' }}>
                <div className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>⏳ OT chờ duyệt ({pendingOT.length})</div>
                <div className="space-y-2">
                  {pendingOT.map(r => (
                    <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span style={{ color: 'var(--text-secondary)' }}>
                        <b style={{ color: 'var(--text-primary)' }}>{r.full_name}</b> · {r.work_date} · {r.ot_hours}h
                      </span>
                      <span className="flex gap-2">
                        <button onClick={() => handleOT(r.id, true)} className="px-3 py-1 rounded-lg text-white text-xs font-semibold" style={{ background: '#34d399' }}>✅ Duyệt</button>
                        <button onClick={() => handleOT(r.id, false)} className="px-3 py-1 rounded-lg text-white text-xs font-semibold" style={{ background: '#f87171' }}>❌ Từ chối</button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Team summary (leader/admin/accountant) */}
            {canSeeTeam && teamRows.length > 0 && (
              <div className="rounded-2xl border overflow-x-auto" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="px-4 py-3 font-semibold" style={{ color: 'var(--text-primary)', background: 'var(--bg-elevated)' }}>
                  👥 Bảng công {user.role === 'leader' ? 'team' : 'toàn công ty'} — kỳ {period}
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: 'var(--text-muted)' }}>
                      <th className="text-left px-4 py-2">Nhân viên</th>
                      <th className="text-right px-4 py-2">Công</th>
                      <th className="text-right px-4 py-2">Giờ</th>
                      <th className="text-right px-4 py-2">OT duyệt</th>
                      <th className="text-right px-4 py-2">Cần xác nhận</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamRows.map(row => (
                      <tr key={row.user_id} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                        <td className="px-4 py-2" style={{ color: 'var(--text-primary)' }}>{row.full_name}</td>
                        <td className="px-4 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{row.work_days_fraction}</td>
                        <td className="px-4 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{row.total_hours}h</td>
                        <td className="px-4 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{row.ot_approved_hours}h</td>
                        <td className="px-4 py-2 text-right" style={{ color: row.needs_review ? '#fbbf24' : 'var(--text-muted)' }}>{row.needs_review || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === 'leave' && (
          <div className="space-y-5">
            {/* Balance */}
            {balance && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: 'Phép năm còn lại', value: `${balance.annual_remaining}/${balance.annual_total}`, color: 'var(--gold-500)' },
                  { label: 'Đã dùng', value: balance.annual_used, color: 'var(--text-primary)' },
                  { label: 'Nghỉ ốm', value: balance.sick_used, color: 'var(--text-primary)' },
                  { label: 'Không lương', value: balance.unpaid_used, color: 'var(--text-primary)' },
                ].map(c => (
                  <div key={c.label} className="rounded-2xl p-4 border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{c.label}</div>
                    <div className="text-xl font-bold" style={{ color: c.color }}>{c.value}</div>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowLeaveForm(v => !v)}
              className="px-4 py-2 rounded-xl font-semibold text-white"
              style={{ background: 'var(--gold-500)' }}
            >+ Xin nghỉ phép</button>

            {showLeaveForm && (
              <div className="rounded-2xl p-5 border space-y-3" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
                  <select
                    value={leaveForm.leave_type}
                    onChange={e => setLeaveForm(f => ({ ...f, leave_type: e.target.value }))}
                    className="px-3 py-2 rounded-lg border text-sm"
                    style={{ background: 'var(--bg-base)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                  >
                    <option value="annual">Phép năm (có lương)</option>
                    <option value="sick">Nghỉ ốm</option>
                    <option value="unpaid">Không lương</option>
                  </select>
                  <input type="date" value={leaveForm.start_date} onChange={e => setLeaveForm(f => ({ ...f, start_date: e.target.value }))}
                    className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--bg-base)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} />
                  <input type="date" value={leaveForm.end_date} onChange={e => setLeaveForm(f => ({ ...f, end_date: e.target.value }))}
                    className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--bg-base)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} />
                  <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <input type="checkbox" checked={leaveForm.half_day} onChange={e => setLeaveForm(f => ({ ...f, half_day: e.target.checked }))} />
                    Nửa ngày
                  </label>
                </div>
                <textarea
                  placeholder="Lý do nghỉ..."
                  value={leaveForm.reason}
                  onChange={e => setLeaveForm(f => ({ ...f, reason: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border text-sm"
                  rows={2}
                  style={{ background: 'var(--bg-base)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                />
                <button onClick={submitLeave} disabled={busy} className="px-4 py-2 rounded-xl font-semibold text-white disabled:opacity-40" style={{ background: 'var(--gold-500)' }}>
                  Gửi đơn
                </button>
              </div>
            )}

            {/* My leaves */}
            <div className="rounded-2xl border overflow-x-auto" style={{ borderColor: 'var(--border-subtle)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: 'var(--text-muted)', background: 'var(--bg-elevated)' }}>
                    <th className="text-left px-4 py-2.5">Loại</th>
                    <th className="text-left px-4 py-2.5">Từ</th>
                    <th className="text-left px-4 py-2.5">Đến</th>
                    <th className="text-right px-4 py-2.5">Số ngày</th>
                    <th className="text-left px-4 py-2.5">Trạng thái</th>
                    <th className="text-left px-4 py-2.5">Lý do</th>
                  </tr>
                </thead>
                <tbody>
                  {myLeaves.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center" style={{ color: 'var(--text-muted)' }}>Chưa có đơn nghỉ phép nào</td></tr>
                  )}
                  {myLeaves.map(l => (
                    <tr key={l.id} className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-primary)' }}>{l.leave_type_label}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{l.start_date}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{l.end_date}</td>
                      <td className="px-4 py-2.5 text-right" style={{ color: 'var(--text-primary)' }}>{l.days}</td>
                      <td className="px-4 py-2.5" style={{ color: LEAVE_STATUS[l.status]?.color }}>{LEAVE_STATUS[l.status]?.label || l.status}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-muted)' }}>{l.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'payslip' && (
          <div className="space-y-4">
            <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
              🔒 Phiếu lương chỉ hiển thị các kỳ <b>đã chi</b> và chỉ của chính bạn. Phiếu chi tiết cũng được gửi qua Telegram chat riêng.
            </div>
            {payslips.length === 0 && (
              <div className="rounded-2xl p-8 text-center border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
                Chưa có phiếu lương nào
              </div>
            )}
            {payslips.map(p => (
              <div key={p.id} className="rounded-2xl p-5 border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
                <div className="flex flex-wrap justify-between items-center mb-3">
                  <div className="font-bold" style={{ color: 'var(--text-primary)' }}>Kỳ {p.period}</div>
                  <div className="text-lg font-bold" style={{ color: 'var(--gold-500)' }}>{fmtMoney(p.net_salary)}</div>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span>Lương CB: {fmtMoney(p.base_salary)}</span>
                  <span>Công: {p.work_days}/{p.standard_days}</span>
                  {p.ot_pay > 0 && <span>OT ({p.ot_hours}h): +{fmtMoney(p.ot_pay)}</span>}
                  {p.commission_total > 0 && <span>Hoa hồng: +{fmtMoney(p.commission_total)}</span>}
                  {p.bonus > 0 && <span>Thưởng: +{fmtMoney(p.bonus)}</span>}
                  {p.allowance > 0 && <span>Phụ cấp: +{fmtMoney(p.allowance)}</span>}
                  <span>Gross: {fmtMoney(p.gross_salary)}</span>
                  <span>BHXH: −{fmtMoney(p.bhxh_employee)}</span>
                  <span>Thuế TNCN: −{fmtMoney(p.pit)}</span>
                  {p.advance_deduction > 0 && <span>Tạm ứng: −{fmtMoney(p.advance_deduction)}</span>}
                  {p.deductions > 0 && <span>Khấu trừ: −{fmtMoney(p.deductions)}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Sidebar>
  );
}
