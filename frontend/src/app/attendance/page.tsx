'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { getPermissions, UserRole } from '@/lib/roles';
import Sidebar from '@/components/layout/Sidebar';
import {
  api, ApiError, AttendanceRecord, AttendanceSummary, TeamAttendanceRow,
  LeaveItem, LeaveBalanceInfo, PayrollRow,
} from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { monthLabelVN } from '@/lib/labels';
import LineIcon from '@/components/ui/LineIcon';

const fmtMoney = (v: number) => `${v.toLocaleString('vi-VN')}đ`;
// Kỳ theo GIỜ VN — toISOString là UTC, sáng sớm ngày 1 (00:00-06:59 VN) sẽ lùi nhầm kỳ tháng trước
const currentPeriod = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' }).slice(0, 7);

/** ISO "2026-07-14" → "14/07" — chỉ đổi hiển thị, giữ nguyên data gốc. */
const fmtDateVN = (isoDate: string | null | undefined): string => {
  if (!isoDate) return '—';
  const m = String(isoDate).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}` : isoDate;
};

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
  pending: { label: 'OT ghi nhận', color: '#34d399' },
  approved: { label: 'OT ghi nhận', color: '#34d399' },
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
      detail: needsReview > 0 ? `Còn ${needsReview} ca quên tan ca — sửa ở bảng công bên dưới` : 'Sạch',
    },
    {
      key: 'ot', label: '2. Tăng ca (tự ghi nhận)', done: otPending === 0,
      detail: 'Sạch',
    },
    {
      key: 'generate', label: '3. Sinh bảng lương', done: !!status,
      detail: status ? `Đã sinh (${payroll?.items.length ?? 0} người · thực lĩnh ${fmtMoney(payroll?.total_net ?? 0)})` : 'Chưa sinh',
      action: !status && (
        <button disabled={busy} onClick={() => run(async () => {
          const res = await api.payrollGenerate(period) as { missing_grade?: number };
          // Không gán bậc lương = lương 0đ — báo ngay để kế toán biết đường xử lý
          if (res?.missing_grade) {
            toast(`⚠️ ${res.missing_grade} nhân viên CHƯA gán bậc lương (lương = 0đ) — vào Tài khoản → Sửa để gán trước khi trình duyệt`, 'error');
          }
          return res;
        }, `Đã sinh bảng lương kỳ ${period}`)}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40" style={{ background: 'var(--gold-500)' }}>
          Sinh bảng lương
        </button>
      ),
    },
    {
      key: 'submit', label: '4. Trình Giám đốc duyệt', done: !!status && status !== 'draft',
      detail: status === 'draft' ? 'Bảng lương đang ở bản nháp' :
              status === 'pending_approval' ? '⏳ Đang chờ Giám đốc duyệt (nhắc qua Telegram sau 72h)' :
              status === 'approved' ? 'Đã duyệt — kỳ đã KHÓA' :
              status === 'paid' ? 'Đã chi + phiếu lương đã gửi' : '—',
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
              status === 'paid' ? 'Hoàn tất kỳ' : 'Chờ bước 4',
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
      <div className="font-bold mb-3" style={{ color: 'var(--text-primary)' }}><LineIcon name="receipt" size={16} className="inline-block align-[-2px] mr-1.5" />Chốt sổ kỳ {monthLabelVN(period)} <span className="text-xs font-normal" style={{ color: 'var(--text-muted)' }}>(dành cho Kế toán — đi từ trên xuống)</span></div>
      <div className="space-y-2">
        {steps.map(s => (
          <div key={s.key} className="flex items-center justify-between gap-3 p-2.5 rounded-xl" style={{ background: 'var(--surface-2)' }}>
            <div className="min-w-0">
              <div className="text-sm font-semibold" style={{ color: s.done ? '#34d399' : 'var(--text-primary)' }}>
                {s.done ? <LineIcon name="check" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" /> : <span className="inline-block w-3.5 h-3.5 rounded-full border align-[-2px] mr-1.5" style={{ borderColor: 'var(--border-strong)' }} />}{s.label}
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
  // Đồng hồ «Đang làm» trên thẻ hôm nay — nhảy mỗi phút
  const [bayGio, setBayGio] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  // Leave state
  const [balance, setBalance] = useState<LeaveBalanceInfo | null>(null);
  const [myLeaves, setMyLeaves] = useState<LeaveItem[]>([]);
  const [leaveForm, setLeaveForm] = useState({
    leave_type: 'annual', start_date: '', end_date: '', half_day: false, reason: '',
  });
  const [showLeaveForm, setShowLeaveForm] = useState(false);

  // Payslip state
  const [payslips, setPayslips] = useState<PayrollRow[]>([]);

  // sale_leader (trưởng nhóm KD — vai trò tùy chỉnh) được duyệt OT team mình
  // từ 09/09/2026 — backend đã mở cùng phạm vi (is_team_lead + team scope)
  const isApprover = user && ['admin', 'leader', 'accountant', 'sale_leader'].includes(user.role);
  const canSeeTeam = isApprover;

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canViewAttendance) router.push('/');
  }, [user, loading, router]);

  const loadAttendance = useCallback(async () => {
    try {
      const [t, me] = await Promise.all([api.attendanceToday(), api.myAttendance(period)]);
      setToday(t.record);
      setSummary(me.summary);
      setRecords(me.records);
      if (canSeeTeam) {
        const [team, ot] = await Promise.all([api.teamAttendance(period), Promise.resolve({ items: [] })]);
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
      if (action.type === 'checkin') {
        // Gửi lại từ hàng đợi offline cũng xin GPS — không thì bản ghi retry
        // không bao giờ được gắn nhãn ✓VP
        const gps = await layGPS();
        await api.attendanceCheckin(gps.latitude != null ? gps : undefined);
      } else await api.attendanceCheckout();
      localStorage.removeItem(QUEUE_KEY);
      toast('✅ Đã gửi lại chấm công thành công (lúc trước mất mạng)', 'success');
      await loadAttendance();
    } catch (e) {
      // Server từ chối hẳn (vd. ngoài bán kính GPS văn phòng) → bỏ hàng đợi,
      // báo rõ để nhân viên tự vào ca lại; lỗi mạng thì giữ queue chờ lần sau
      if (e instanceof ApiError && e.status === 400) {
        localStorage.removeItem(QUEUE_KEY);
        toast(`Lần chấm công lúc mất mạng không gửi được: ${e.message}`, 'error');
      }
    }
  }, [toast, loadAttendance]);

  useEffect(() => {
    void flushQueue(); // thử gửi lại khi mở trang
    window.addEventListener('online', flushQueue);
    return () => window.removeEventListener('online', flushQueue);
  }, [flushQueue]);

  const isNetworkError = (e: unknown) =>
    e instanceof TypeError || (e instanceof Error && /fetch|network|Failed/i.test(e.message));

  // GPS để đối chiếu bán kính văn phòng. Chốt 22/10/2026: vào ca văn phòng phải
  // trong 20 m (backend chặn; bộ phận hiện trường & mạng văn phòng được miễn) —
  // nên xin vị trí CHÍNH XÁC và mới (20 m không chịu được vị trí cũ 2 phút).
  const layGPS = (): Promise<{ latitude?: number; longitude?: number }> =>
    new Promise(resolve => {
      if (!navigator.geolocation) return resolve({});
      const timer = setTimeout(() => resolve({}), 9000);
      navigator.geolocation.getCurrentPosition(
        pos => { clearTimeout(timer); resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }); },
        () => { clearTimeout(timer); resolve({}); },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 },
      );
    });

  const doCheckin = async () => {
    setBusy(true);
    try {
      const gps = await layGPS();
      const res = await api.attendanceCheckin(gps.latitude != null ? gps : undefined);
      toast(res.message, res.created ? 'success' : 'info');
      await loadAttendance();
    } catch (e) {
      if (isNetworkError(e)) {
        localStorage.setItem(QUEUE_KEY, JSON.stringify({ type: 'checkin', at: Date.now() }));
        toast('📶 Mất mạng — sẽ tự vào ca lại khi có sóng. Hoặc dùng Telegram: /checkin', 'info');
      } else {
        const msg = e instanceof Error ? e.message : '';
        toast(
          /GPS|vị trí|cách văn phòng/i.test(msg)
            ? `📍 ${msg}. Nếu chưa bật: biểu tượng 🔒 cạnh địa chỉ web → Vị trí → Cho phép, rồi bấm lại.`
            : `Vào ca lỗi: ${msg}`,
          'error',
        );
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

  if (loading || !user) return null;

  const checkedIn = !!today?.check_in;
  const checkedOut = !!today?.check_out;
  const phutDangLam = checkedIn && !checkedOut && today?.check_in
    ? Math.max(0, Math.floor((bayGio - new Date(today.check_in).getTime()) / 60_000))
    : null;

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-6xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}><LineIcon name="clock" size={20} className="inline-block align-[-2px] mr-1.5" />Chấm công & Nghỉ phép</h1>
          <div className="flex gap-2">
            {(['attendance', 'leave', 'payslip'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="px-3 py-1.5 rounded-lg text-sm font-medium transition"
                style={{
                  background: tab === t ? 'var(--gold-500)' : 'var(--surface-2)',
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
            <div className="rounded-2xl p-5 border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Hôm nay</div>
                  <div className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {checkedIn ? `Vào: ${fmtTimeVN(today?.check_in)}` : 'Chưa vào ca'}
                    {checkedOut && ` · Ra: ${fmtTimeVN(today?.check_out)} · ${today?.work_hours}h`}
                    {today && today.ot_hours > 0 && ` · OT ${today.ot_hours}h (${OT_BADGE[today.ot_status]?.label})`}
                  </div>
                  {phutDangLam != null && (
                    <div className="text-sm mt-0.5" style={{ color: 'var(--gold-500)' }}>
                      <LineIcon name="hourglass" size={16} className="inline-block align-[-2px] mr-1.5" />Đang làm: <b>{Math.floor(phutDangLam / 60)}h{String(phutDangLam % 60).padStart(2, '0')}</b>
                      {phutDangLam >= 480 && <span style={{ color: 'var(--text-muted)' }}> · đủ 8h công, phần sau ghi nhận OT (điểm chuyên cần)</span>}
                    </div>
                  )}
                  {summary && period === currentPeriod() && (
                    <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                      Ngày công tháng này: <b style={{ color: 'var(--text-primary)' }}>{summary.work_days_fraction.toLocaleString('vi-VN')} / {summary.standard_days ?? 22}</b> (không gồm OT)
                    </div>
                  )}
                </div>
                {/* Hai nút cùng cỡ, cùng dáng viên thuốc; nút của BƯỚC KẾ TIẾP mới tô vàng
                    (chưa vào ca → Vào ca, đã vào → Tan ca). Bản cũ: Vào ca vàng chữ trắng,
                    Tan ca viền gần như vô hình → lệch nhau trên điện thoại (23/10/2026). */}
                <div className="grid grid-cols-2 gap-2 w-full sm:w-auto sm:min-w-[260px]">
                  <button
                    onClick={doCheckin}
                    disabled={busy || checkedIn}
                    className={`${!checkedIn ? 'btn-primary' : 'btn-ghost'} w-full justify-center disabled:opacity-40`}
                    style={{ minHeight: 44 }}
                  ><LineIcon name="check" size={16} className="inline-block align-[-2px] mr-1.5" />Vào ca</button>
                  <button
                    onClick={doCheckout}
                    disabled={busy || !checkedIn || checkedOut}
                    className={`${checkedIn && !checkedOut ? 'btn-primary' : 'btn-ghost'} w-full justify-center disabled:opacity-40`}
                    style={{ minHeight: 44 }}
                  ><LineIcon name="flag" size={16} className="inline-block align-[-2px] mr-1.5" />Tan ca</button>
                </div>
              </div>
              <div className="text-xs mt-2 p-2 rounded-lg" style={{ color: 'var(--text-secondary)', background: 'rgba(201,169,110,0.08)', border: '1px solid rgba(201,169,110,0.2)' }}>
                <LineIcon name="star" size={16} className="inline-block align-[-2px] mr-1.5" /><b>Cách nhanh nhất — Telegram:</b> nhắn <code className="px-1 rounded bg-white/10">/checkin</code> với bot (công trường: <code className="px-1 rounded bg-white/10">/checkin [Mã dự án]</code> kèm GPS, tan ca: <code className="px-1 rounded bg-white/10">/checkout</code>). Vào ca văn phòng cần bật vị trí và đứng trong bán kính văn phòng (mặc định 20 m), hoặc dùng mạng văn phòng.
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
                style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
              {summary && (
                <div className="flex flex-wrap gap-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span>Ngày công: <b style={{ color: 'var(--text-primary)' }}>{summary.work_days_fraction.toLocaleString('vi-VN')}{summary.standard_days ? ` / ${summary.standard_days}` : ''}</b> <span style={{ color: 'var(--text-muted)' }}>(không gồm OT)</span></span>
                  <span>Giờ: <b style={{ color: 'var(--text-primary)' }}>{summary.total_hours}h</b></span>
                  <span>OT ghi nhận (điểm chuyên cần, không tính tiền): <b style={{ color: 'var(--text-primary)' }}>{summary.ot_approved_hours}h</b></span>
                  {summary.needs_review > 0 && <span style={{ color: '#fbbf24' }}><LineIcon name="alert" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{summary.needs_review} ca cần xác nhận</span>}
                </div>
              )}
            </div>

            {/* Records table */}
            <div className="rounded-2xl border overflow-x-auto" style={{ borderColor: 'var(--border-subtle)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: 'var(--text-muted)', background: 'var(--surface-2)' }}>
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
                        {fmtDateVN(r.work_date)}{r.needs_review && <LineIcon name="alert" size={14} color="#fbbf24" className="inline-block align-[-2px] ml-1" />}
                      </td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtTimeVN(r.check_in)}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtTimeVN(r.check_out)}</td>
                      <td className="px-4 py-2.5 text-right" style={{ color: 'var(--text-primary)' }}>{r.work_hours}h</td>
                      <td className="px-4 py-2.5" style={{ color: OT_BADGE[r.ot_status]?.color }}>
                        {r.ot_hours > 0 ? `${r.ot_hours}h · ${OT_BADGE[r.ot_status]?.label}` : '—'}
                        {r.ot_hours > 0 && r.ot_decided_by_name && (
                          <span className="block text-[10px]" style={{ color: 'var(--text-muted)' }}>
                            bởi {r.ot_decided_by_name} · {fmtTimeVN(r.ot_decided_at ?? null)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-muted)' }}>
                        {r.source}
                        {(r.ip_ok || r.gps_ok) && (
                          <span title={r.ip_ok ? 'Trùng mạng văn phòng' : 'GPS trong bán kính văn phòng'} style={{ color: 'var(--success)' }}> ✓VP</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>


            {/* Team summary (leader/admin/accountant) */}
            {canSeeTeam && teamRows.length > 0 && (
              <div className="rounded-2xl border overflow-x-auto" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="px-4 py-3 font-semibold" style={{ color: 'var(--text-primary)', background: 'var(--surface-2)' }}>
                  <LineIcon name="users" size={16} className="inline-block align-[-2px] mr-1.5" />Bảng công {['leader', 'sale_leader'].includes(user.role) ? 'team' : 'toàn công ty'} — kỳ {monthLabelVN(period)}
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: 'var(--text-muted)' }}>
                      <th className="text-left px-4 py-2">Nhân viên</th>
                      <th className="text-right px-4 py-2">Công</th>
                      <th className="text-right px-4 py-2">Giờ</th>
                      <th className="text-right px-4 py-2">OT ghi nhận</th>
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
                  <div key={c.label} className="rounded-2xl p-4 border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{c.label}</div>
                    <div className="text-xl font-bold" style={{ color: c.color }}>{c.value}</div>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => {
                // Đóng lại thì reset form về mặc định để lần mở sau sạch.
                if (showLeaveForm) setLeaveForm({ leave_type: 'annual', start_date: '', end_date: '', half_day: false, reason: '' });
                setShowLeaveForm(v => !v);
              }}
              className="px-4 py-2 rounded-xl font-semibold text-white"
              style={{ background: 'var(--gold-500)' }}
            >+ Xin nghỉ phép</button>

            {showLeaveForm && (
              <div className="rounded-2xl p-5 border space-y-3" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Loại phép</label>
                    <select
                      value={leaveForm.leave_type}
                      onChange={e => setLeaveForm(f => ({ ...f, leave_type: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border text-sm"
                      style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                    >
                      <option value="annual">Phép năm (có lương)</option>
                      <option value="sick">Nghỉ ốm</option>
                      <option value="unpaid">Không lương</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Từ ngày</label>
                    <input type="date" value={leaveForm.start_date} onChange={e => setLeaveForm(f => ({ ...f, start_date: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Đến ngày</label>
                    <input type="date" value={leaveForm.end_date} onChange={e => setLeaveForm(f => ({ ...f, end_date: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Tùy chọn</label>
                    <label className="flex items-center gap-2 text-sm h-[38px]" style={{ color: 'var(--text-secondary)' }}>
                      <input type="checkbox" checked={leaveForm.half_day} onChange={e => setLeaveForm(f => ({ ...f, half_day: e.target.checked }))} />
                      Nửa ngày
                    </label>
                  </div>
                </div>
                <textarea
                  placeholder="Lý do nghỉ..."
                  value={leaveForm.reason}
                  onChange={e => setLeaveForm(f => ({ ...f, reason: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border text-sm"
                  rows={2}
                  style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
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
                  <tr style={{ color: 'var(--text-muted)', background: 'var(--surface-2)' }}>
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
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtDateVN(l.start_date)}</td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>{fmtDateVN(l.end_date)}</td>
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
              <LineIcon name="lock" size={16} className="inline-block align-[-2px] mr-1.5" />Phiếu lương chỉ hiển thị các kỳ <b>đã chi</b> và chỉ của chính bạn. Phiếu chi tiết cũng được gửi qua Telegram chat riêng.
            </div>
            {payslips.length === 0 && (
              <div className="rounded-2xl p-8 text-center border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
                Chưa có phiếu lương nào
              </div>
            )}
            {payslips.map(p => (
              <div key={p.id} className="rounded-2xl p-5 border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' }}>
                <div className="flex flex-wrap justify-between items-center mb-3">
                  <div className="font-bold" style={{ color: 'var(--text-primary)' }}>Kỳ {monthLabelVN(p.period)}</div>
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
