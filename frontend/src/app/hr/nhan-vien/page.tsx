'use client';

import { useCallback, useEffect, useState, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';
import { api, type EmployeeProfileData, type EmployeeDocumentMeta, type EmployeeFinanceData, type HandoverItem, type AttendanceRecord, type AttendanceSummary } from '@/lib/api';
import { ROLE_LABELS, labelOf } from '@/lib/labels';
import { formatCurrency } from '@/lib/utils';

/**
 * Hồ sơ nhân viên 360° (/hr/nhan-vien?id=...) — 09/09/2026.
 * Tab: Hồ sơ+HĐLĐ · Tiền (chỉ Admin/Kế toán/chính chủ) · Chấm công · Nghỉ phép
 * · Bàn giao (Admin/Kế toán) · Nhật ký (Admin). Mỗi tab tự tải khi mở (lazy).
 */

const DEPT_LABELS: Record<string, string> = {
  SALES: 'Kinh doanh', DESIGN: 'Thiết kế', CONSTRUCTION: 'Thi công',
  PROCUREMENT: 'Thu mua', ACCOUNTING: 'Kế toán', BOD: 'Ban giám đốc', OTHER: 'Khác',
};

const CONTRACT_LABELS: Record<string, string> = {
  probation: 'Thử việc', fixed_1y: 'Xác định 1 năm', fixed_2y: 'Xác định 2 năm', indefinite: 'Không thời hạn',
};

const DOC_LABELS: Record<string, string> = {
  cccd_front: 'CCCD mặt trước', cccd_back: 'CCCD mặt sau', contract: 'HĐLĐ (scan)', other: 'Khác',
};

// Cột check_in/check_out lưu UTC naive — hiển thị +7
function vnTime(s?: string | null): string {
  if (!s) return '—';
  const d = new Date(s.replace(' ', 'T') + 'Z');
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });
}

/** Nén ảnh phía client: cạnh dài ≤1600px, JPG — thử giảm chất lượng tới khi ≤500KB. */
async function compressImage(file: File): Promise<{ base64: string; mime: string } | null> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return null;
  const maxDim = 1600;
  const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  // PNG trong suốt ép sang JPG sẽ ra nền ĐEN nếu không tô trắng trước
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.82, 0.65, 0.5, 0.35]) {
    const dataUrl = canvas.toDataURL('image/jpeg', quality);
    const base64 = dataUrl.split(',')[1];
    if (base64.length * 0.75 <= 500_000) return { base64, mime: 'image/jpeg' };
  }
  return null;
}

const TABS = [
  { key: 'ho-so', label: 'Hồ sơ & HĐLĐ', icon: 'user' },
  { key: 'tien', label: 'Tiền', icon: 'wallet' },
  { key: 'cham-cong', label: 'Chấm công', icon: 'clock' },
  { key: 'nghi-phep', label: 'Nghỉ phép', icon: 'compass' },
  { key: 'ban-giao', label: 'Bàn giao', icon: 'send' },
  { key: 'nhat-ky', label: 'Nhật ký', icon: 'shield' },
] as const;

function NhanVienContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const targetId = searchParams.get('id') || '';

  const isHR = user?.role === 'admin' || user?.role === 'accountant';
  const isSelf = user?.id === targetId;

  const [tab, setTab] = useState<string>('ho-so');
  const [header, setHeader] = useState<{ full_name: string; email: string; phone: string | null; role: string; department: string | null; is_active: boolean; resign_date: string | null } | null>(null);
  const [profile, setProfile] = useState<EmployeeProfileData>({});
  const [docs, setDocs] = useState<EmployeeDocumentMeta[]>([]);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EmployeeProfileData>({});
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState('');

  const [finance, setFinance] = useState<EmployeeFinanceData | null>(null);
  const [attendance, setAttendance] = useState<{ summary: AttendanceSummary; records: AttendanceRecord[] } | null>(null);
  // Kỳ theo giờ VN (toISOString là UTC — sáng sớm ngày 1 sẽ lùi nhầm tháng)
  const [attPeriod, setAttPeriod] = useState(() =>
    new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' }).slice(0, 7));
  const [leaves, setLeaves] = useState<Awaited<ReturnType<typeof api.getEmployeeLeaves>> | null>(null);
  const [handovers, setHandovers] = useState<{ given: HandoverItem[]; received: HandoverItem[] } | null>(null);
  const [auditRows, setAuditRows] = useState<{ id: string; action: string; actor_name: string | null; note: string | null; created_at: string }[] | null>(null);
  const [docView, setDocView] = useState<{ filename: string; src: string } | null>(null);
  const [tabLoading, setTabLoading] = useState(false);
  // Trưởng nhóm xem lính: backend trả view rút gọn (limited) — ẩn tab Hồ sơ,
  // mở thẳng tab Chấm công cho đúng việc họ cần
  const [limited, setLimited] = useState(false);

  useEffect(() => {
    if (user === null) router.push('/login');
  }, [user, router]);

  const loadProfile = useCallback(async () => {
    if (!targetId) return;
    try {
      const data = await api.getEmployeeProfile(targetId);
      setHeader(data.user);
      setProfile(data.profile);
      setForm(data.profile);
      setDocs(data.documents);
      setCanEdit(data.can_edit);
      const isLimited = !!(data as { limited?: boolean }).limited;
      setLimited(isLimited);
      if (isLimited) {
        setTab('cham-cong');
        setAttendance(await api.getEmployeeAttendance(targetId, attPeriod));
      }
      setLoadError('');
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Không tải được hồ sơ');
    }
  }, [targetId]);

  useEffect(() => { void loadProfile(); }, [loadProfile]);

  const openTab = async (key: string) => {
    setTab(key);
    setTabLoading(true);
    try {
      if (key === 'tien' && !finance) setFinance(await api.getEmployeeFinance(targetId));
      if (key === 'cham-cong' && !attendance) setAttendance(await api.getEmployeeAttendance(targetId, attPeriod));
      if (key === 'nghi-phep' && !leaves) setLeaves(await api.getEmployeeLeaves(targetId));
      if (key === 'ban-giao' && !handovers) setHandovers(await api.getEmployeeHandovers(targetId));
      if (key === 'nhat-ky' && !auditRows) setAuditRows((await api.getEmployeeAudit(targetId)).items);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không tải được dữ liệu', 'error');
    } finally {
      setTabLoading(false);
    }
  };

  const changeAttPeriod = async (period: string) => {
    setAttPeriod(period);
    setTabLoading(true);
    try {
      setAttendance(await api.getEmployeeAttendance(targetId, period));
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không tải được bảng công', 'error');
    } finally {
      setTabLoading(false);
    }
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      const res = await api.updateEmployeeProfile(targetId, form);
      setProfile(res.profile);
      setEditing(false);
      toast('Đã lưu hồ sơ', 'success');
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lưu thất bại', 'error');
    } finally {
      setSaving(false);
    }
  };

  const uploadDoc = async (docType: string, file: File) => {
    const compressed = await compressImage(file);
    if (!compressed) {
      toast('Không đọc/nén được ảnh — chọn file JPG/PNG', 'error');
      return;
    }
    try {
      await api.uploadEmployeeDocument(targetId, {
        doc_type: docType, filename: file.name.replace(/\.[^.]+$/, '') + '.jpg',
        mime: compressed.mime, data_base64: compressed.base64,
      });
      toast('Đã tải lên', 'success');
      await loadProfile();
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Tải lên thất bại', 'error');
    }
  };

  const viewDoc = async (d: EmployeeDocumentMeta) => {
    try {
      const data = await api.getEmployeeDocument(targetId, d.id);
      setDocView({ filename: data.filename, src: `data:${data.mime};base64,${data.data_base64}` });
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không mở được file', 'error');
    }
  };

  if (!user) return null;
  if (!targetId) {
    return (
      <Sidebar>
        <div className="p-6"><p className="text-sm" style={{ color: 'var(--text-muted)' }}>Thiếu mã nhân viên — quay lại trang <a className="underline" href="/hr">Nhân sự</a> và bấm vào một người.</p></div>
      </Sidebar>
    );
  }

  const visibleTabs = TABS.filter(t => {
    if (t.key === 'ho-so') return !limited;
    if (t.key === 'tien') return isHR || isSelf;
    if (t.key === 'ban-giao') return isHR;
    if (t.key === 'nhat-ky') return user.role === 'admin';
    return true; // công/phép — backend tự chặn nếu ngoài phạm vi
  });

  const inputCls = 'w-full px-3 py-2 rounded-lg text-sm outline-none min-h-[40px]';
  const inputStyle = { background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' } as const;

  const field = (label: string, key: keyof EmployeeProfileData, type: 'text' | 'date' = 'text') => (
    <div>
      <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>{label}</label>
      {editing ? (
        <input
          type={type} value={(form[key] as string) || ''}
          onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
          className={inputCls} style={inputStyle}
        />
      ) : (
        <p className="text-sm min-h-[20px]" style={{ color: 'var(--text-primary)' }}>
          {key === 'contract_type' ? labelOf(CONTRACT_LABELS, profile[key] as string) : ((profile[key] as string) || '—')}
        </p>
      )}
    </div>
  );

  return (
    <Sidebar>
      <div className="p-4 md:p-6 animate-in max-w-4xl space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3 flex-wrap">
          <button onClick={() => router.push('/hr')} className="text-sm px-2.5 py-1.5 rounded-lg min-h-[36px]" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>← Nhân sự</button>
          {header && (
            <>
              <div className="w-11 h-11 rounded-full flex items-center justify-center text-lg font-bold" style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>
                {header.full_name.charAt(0)}
              </div>
              <div>
                <h1 className="text-xl font-bold flex items-center gap-2">
                  {header.full_name}
                  {!header.is_active && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(248,113,113,0.12)', color: '#F87171', border: '1px solid rgba(248,113,113,0.3)' }}>
                      Đã nghỉ việc{header.resign_date ? ` ${new Date(header.resign_date).toLocaleDateString('vi-VN')}` : ''}
                    </span>
                  )}
                </h1>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {labelOf(ROLE_LABELS, header.role)} · {labelOf(DEPT_LABELS, header.department)} · {header.email}{header.phone ? ` · ${header.phone}` : ''}
                </p>
              </div>
            </>
          )}
        </div>

        {loadError && (
          <div className="rounded-xl px-4 py-3 text-sm flex items-center justify-between" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--text-secondary)' }}>
            <span>⚠️ {loadError}</span>
            <button onClick={() => void loadProfile()} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}>Tải lại</button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 flex-wrap">
          {visibleTabs.map(t => (
            <button key={t.key} onClick={() => void openTab(t.key)}
              className="px-3 py-2 rounded-lg text-sm font-medium min-h-[40px] flex items-center gap-1.5 transition-all"
              style={tab === t.key
                ? { background: 'rgba(201,169,110,0.15)', color: '#C9A96E', border: '1px solid rgba(201,169,110,0.4)' }
                : { background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
              <LineIcon name={t.icon} size={14} color={tab === t.key ? '#C9A96E' : 'currentColor'} />{t.label}
            </button>
          ))}
        </div>

        {tabLoading && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Đang tải…</p>}

        {/* ── Tab Hồ sơ & HĐLĐ ── */}
        {tab === 'ho-so' && (
          <div className="space-y-4">
            <div className="glass-card rounded-xl p-4 md:p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold">Thông tin cá nhân</h2>
                {canEdit && !editing && (
                  <button onClick={() => { setForm(profile); setEditing(true); }} className="text-xs px-3 py-1.5 rounded-lg font-semibold min-h-[32px]" style={{ background: 'rgba(201,169,110,0.12)', color: '#C9A96E', border: '1px solid rgba(201,169,110,0.3)' }}>Sửa</button>
                )}
                {editing && (
                  <div className="flex gap-2">
                    <button onClick={() => setEditing(false)} className="text-xs px-3 py-1.5 rounded-lg min-h-[32px]" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>Hủy</button>
                    <button onClick={() => void saveProfile()} disabled={saving} className="text-xs px-3 py-1.5 rounded-lg font-semibold min-h-[32px]" style={{ background: '#C9A96E', color: '#1a1a1a' }}>{saving ? 'Đang lưu…' : 'Lưu'}</button>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {field('Số CCCD', 'national_id')}
                {field('Ngày cấp', 'national_id_issued_date', 'date')}
                {field('Nơi cấp', 'national_id_issued_place')}
                {field('Ngày sinh', 'date_of_birth', 'date')}
                {field('Địa chỉ', 'address')}
                {field('Liên hệ khẩn cấp (tên + SĐT)', 'emergency_contact')}
                {field('Số TK ngân hàng', 'bank_account')}
                {field('Ngân hàng', 'bank_name')}
                {field('Số sổ BHXH', 'social_insurance_no')}
              </div>
            </div>

            <div className="glass-card rounded-xl p-4 md:p-5">
              <h2 className="text-sm font-bold mb-3">Hợp đồng lao động</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {field('Ngày vào làm', 'hire_date', 'date')}
                <div>
                  <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Loại hợp đồng</label>
                  {editing ? (
                    <select value={form.contract_type || ''} onChange={e => setForm(f => ({ ...f, contract_type: e.target.value || null }))} className={inputCls} style={inputStyle}>
                      <option value="">— Chọn —</option>
                      {Object.entries(CONTRACT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  ) : (
                    <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{labelOf(CONTRACT_LABELS, profile.contract_type)}</p>
                  )}
                </div>
                {field('Ngày ký', 'contract_signed_date', 'date')}
                {field('Ngày hết hạn (trống = không thời hạn)', 'contract_end_date', 'date')}
                {field('Ghi chú', 'note')}
              </div>
            </div>

            <div className="glass-card rounded-xl p-4 md:p-5">
              <h2 className="text-sm font-bold mb-1">Giấy tờ (CCCD, HĐLĐ scan)</h2>
              <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>Ảnh JPG — app tự nén khi chọn. Chỉ Admin/Kế toán và chính chủ xem được.</p>
              <div className="space-y-2">
                {docs.map(d => (
                  <div key={d.id} className="flex items-center gap-2 text-sm flex-wrap">
                    <button onClick={() => void viewDoc(d)} className="underline" style={{ color: '#60A5FA' }}>{labelOf(DOC_LABELS, d.doc_type)}</button>
                    <span style={{ color: 'var(--text-muted)' }} className="text-xs">{d.filename} · {(d.size_bytes / 1024).toFixed(0)}KB · {d.uploaded_by_name || ''}</span>
                    {canEdit && (
                      <button onClick={() => { if (confirm(`Xóa ${d.filename}?`)) { void api.deleteEmployeeDocument(targetId, d.id).then(() => loadProfile()); } }} className="text-xs" style={{ color: '#F87171' }}>Xóa</button>
                    )}
                  </div>
                ))}
                {docs.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có giấy tờ nào.</p>}
              </div>
              {canEdit && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {Object.entries(DOC_LABELS).map(([k, v]) => (
                    <label key={k} className="text-xs px-3 py-2 rounded-lg cursor-pointer min-h-[36px] flex items-center" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px dashed var(--border-subtle)' }}>
                      + {v}
                      <input type="file" accept="image/jpeg,image/png" className="hidden"
                        onChange={e => { const f = e.target.files?.[0]; if (f) void uploadDoc(k, f); e.target.value = ''; }} />
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Tab Tiền ── */}
        {tab === 'tien' && finance && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Lương thực nhận (đã chi)', value: finance.totals.net_paid },
                { label: 'Hoa hồng đã trả', value: finance.totals.commission_paid },
                { label: 'Hoa hồng chờ/duyệt', value: finance.totals.commission_pending },
                { label: 'Tạm ứng đang treo', value: finance.totals.advance_open },
              ].map(s => (
                <div key={s.label} className="glass-card rounded-xl p-3">
                  <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
                  <p className="text-base font-bold mt-0.5" style={{ color: 'var(--text-primary)' }}>{formatCurrency(s.value)}</p>
                </div>
              ))}
            </div>

            <div className="glass-card rounded-xl p-4">
              <h2 className="text-sm font-bold mb-2">Lịch sử lương theo kỳ</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr style={{ color: 'var(--text-muted)' }} className="text-xs text-left"><th className="py-1.5 pr-3">Kỳ</th><th className="pr-3">Lương cơ bản</th><th className="pr-3">Hoa hồng</th><th className="pr-3">Thưởng</th><th className="pr-3">OT</th><th className="pr-3">Thực nhận</th><th>Trạng thái</th></tr></thead>
                  <tbody>
                    {finance.payrolls.map(p => (
                      <tr key={p.id} className="border-t" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                        <td className="py-1.5 pr-3">{p.period}</td>
                        <td className="pr-3">{formatCurrency(p.base_salary)}</td>
                        <td className="pr-3">{formatCurrency(p.commission_total)}</td>
                        <td className="pr-3">{formatCurrency(p.bonus)}</td>
                        <td className="pr-3">{formatCurrency(p.ot_pay)}</td>
                        <td className="pr-3 font-semibold" style={{ color: 'var(--text-primary)' }}>{formatCurrency(p.net)}</td>
                        <td>{p.status === 'paid' ? '✅ Đã chi' : p.status === 'approved' ? 'Đã duyệt' : p.status}</td>
                      </tr>
                    ))}
                    {finance.payrolls.length === 0 && <tr><td colSpan={7} className="py-3 text-center" style={{ color: 'var(--text-muted)' }}>Chưa có kỳ lương nào</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="glass-card rounded-xl p-4">
                <h2 className="text-sm font-bold mb-2">Hoa hồng ({finance.commissions.length})</h2>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {finance.commissions.map(c => (
                    <div key={c.id} className="flex justify-between text-sm gap-2">
                      <span style={{ color: 'var(--text-secondary)' }}>{c.period || c.created_at.slice(0, 10)} · {c.type.includes('design') ? 'Thiết kế' : c.type.includes('construction') ? 'Thi công' : 'Override'}</span>
                      <span className="whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>{formatCurrency(c.amount)} {c.status === 'paid' ? '✅' : c.status === 'approved' ? '🟡' : '⏳'}</span>
                    </div>
                  ))}
                  {finance.commissions.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có</p>}
                </div>
              </div>
              <div className="glass-card rounded-xl p-4">
                <h2 className="text-sm font-bold mb-2">Tạm ứng ({finance.advances.length})</h2>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {finance.advances.map(a => (
                    <div key={a.id} className="flex justify-between text-sm gap-2">
                      <span style={{ color: 'var(--text-secondary)' }}>{a.created_at.slice(0, 10)} · {a.reason}</span>
                      <span className="whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>{formatCurrency(a.amount)} {a.status === 'deducted' ? '✅ đã trừ' : a.status}</span>
                    </div>
                  ))}
                  {finance.advances.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có</p>}
                </div>
              </div>
            </div>

            <div className="glass-card rounded-xl p-4">
              <h2 className="text-sm font-bold mb-2">Giao dịch sổ kế toán gắn nhân viên ({finance.transactions.length})</h2>
              <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>Chỉ gồm giao dịch kế toán nhập có gắn người (Lương/Hoa hồng) — lương chi qua kỳ xem ở bảng trên.</p>
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {finance.transactions.map(t => (
                  <div key={t.id} className="flex justify-between text-sm gap-2">
                    <span style={{ color: 'var(--text-secondary)' }}>{t.transaction_date.slice(0, 10)} · {t.description}</span>
                    <span className="whitespace-nowrap" style={{ color: t.type === 'expense' ? '#F87171' : '#34D399' }}>{t.type === 'expense' ? '−' : '+'}{formatCurrency(t.amount)}</span>
                  </div>
                ))}
                {finance.transactions.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có</p>}
              </div>
            </div>
          </div>
        )}

        {/* ── Tab Chấm công ── */}
        {tab === 'cham-cong' && attendance && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <input type="month" value={attPeriod} onChange={e => void changeAttPeriod(e.target.value)} className={inputCls + ' w-auto'} style={inputStyle} />
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Công: <b style={{ color: 'var(--text-primary)' }}>{attendance.summary.work_days_fraction ?? attendance.summary.work_days}</b> ·
                Giờ: <b style={{ color: 'var(--text-primary)' }}>{attendance.summary.total_hours}</b> ·
                OT duyệt: <b style={{ color: 'var(--text-primary)' }}>{(attendance.summary as unknown as { ot_approved_hours?: number }).ot_approved_hours ?? '—'}</b>
              </p>
            </div>
            <div className="glass-card rounded-xl p-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-xs text-left" style={{ color: 'var(--text-muted)' }}><th className="py-1.5 pr-3">Ngày</th><th className="pr-3">Vào</th><th className="pr-3">Ra</th><th className="pr-3">Giờ</th><th className="pr-3">OT</th><th className="pr-3">Nguồn</th><th>Ghi chú</th></tr></thead>
                <tbody>
                  {attendance.records.map(r => (
                    <tr key={r.id} className="border-t" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                      <td className="py-1.5 pr-3 whitespace-nowrap">{r.work_date.slice(5)}</td>
                      <td className="pr-3">{vnTime(r.check_in)}</td>
                      <td className="pr-3">{vnTime(r.check_out)}</td>
                      <td className="pr-3">{r.work_hours}</td>
                      <td className="pr-3 whitespace-nowrap">
                        {r.ot_hours > 0 ? (
                          <>
                            {r.ot_hours}h {r.ot_status === 'approved' ? '✅' : r.ot_status === 'rejected' ? '❌' : '⏳'}
                            {r.ot_decided_by_name && (
                              <span className="block text-[10px]" style={{ color: 'var(--text-muted)' }}>
                                {r.ot_status === 'approved' ? 'duyệt' : 'từ chối'} bởi {r.ot_decided_by_name} · {vnTime(r.ot_decided_at)}
                              </span>
                            )}
                          </>
                        ) : '—'}
                      </td>
                      <td className="pr-3 whitespace-nowrap">
                        {r.source === 'leave' ? 'Nghỉ phép' : r.source === 'device' ? 'Máy chấm công' : r.source === 'telegram' ? 'Telegram' : 'Web'}
                        {(r.ip_ok || r.gps_ok) && <span title={r.ip_ok ? 'Trùng mạng văn phòng' : 'GPS trong bán kính văn phòng'} style={{ color: '#34D399' }}> ✓VP</span>}
                      </td>
                      <td className="text-xs">{r.needs_review ? '⚠️ ' : ''}{r.note || ''}</td>
                    </tr>
                  ))}
                  {attendance.records.length === 0 && <tr><td colSpan={7} className="py-3 text-center" style={{ color: 'var(--text-muted)' }}>Không có bản ghi trong kỳ</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Tab Nghỉ phép ── */}
        {tab === 'nghi-phep' && leaves && (
          <div className="space-y-3">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Phép năm {leaves.balance.year}: đã dùng <b style={{ color: 'var(--text-primary)' }}>{leaves.balance.annual_used}/{leaves.balance.annual_total}</b> ngày
              · Ốm: {leaves.balance.sick_used} · Không lương: {leaves.balance.unpaid_used}
            </p>
            <div className="glass-card rounded-xl p-4 space-y-2">
              {leaves.requests.map(r => (
                <div key={r.id} className="flex justify-between gap-2 text-sm border-t first:border-t-0 pt-2 first:pt-0" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {new Date(r.start_date).toLocaleDateString('vi-VN')} → {new Date(r.end_date).toLocaleDateString('vi-VN')} · {r.days} ngày · {r.leave_type === 'annual' ? 'Phép năm' : r.leave_type === 'sick' ? 'Ốm' : 'Không lương'} · {r.reason}
                  </span>
                  <span className="whitespace-nowrap">{r.status === 'approved' ? '✅' : r.status === 'rejected' ? '❌' : r.status === 'cancelled' ? '🚫' : '⏳'}</span>
                </div>
              ))}
              {leaves.requests.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có đơn nghỉ phép nào.</p>}
            </div>
          </div>
        )}

        {/* ── Tab Bàn giao ── */}
        {tab === 'ban-giao' && handovers && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { title: `Đã giao đi (${handovers.given.length})`, rows: handovers.given, dir: 'to' as const },
              { title: `Đã nhận về (${handovers.received.length})`, rows: handovers.received, dir: 'from' as const },
            ].map(g => (
              <div key={g.title} className="glass-card rounded-xl p-4">
                <h2 className="text-sm font-bold mb-2">{g.title}</h2>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {g.rows.map(h => (
                    <div key={h.id} className="text-sm border-t first:border-t-0 pt-2 first:pt-0" style={{ borderColor: 'var(--border-subtle)' }}>
                      <p style={{ color: 'var(--text-primary)' }}>
                        {h.entity_type === 'lead' ? '👤' : '📋'} {h.entity_name}
                        <span className="text-xs ml-1.5" style={{ color: 'var(--text-muted)' }}>({h.entity_type === 'lead' ? 'khách' : 'đầu việc'})</span>
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {g.dir === 'to' ? `→ ${h.to_user_name}` : `← từ ${h.from_user_name}`} · {h.reason === 'resign' ? 'nghỉ việc' : 'thủ công'} · {new Date(h.created_at.replace(' ', 'T') + 'Z').toLocaleDateString('vi-VN')}
                      </p>
                    </div>
                  ))}
                  {g.rows.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Không có</p>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Tab Nhật ký ── */}
        {tab === 'nhat-ky' && auditRows && (
          <div className="glass-card rounded-xl p-4 space-y-2">
            {auditRows.map(l => (
              <div key={l.id} className="text-sm border-t first:border-t-0 pt-2 first:pt-0" style={{ borderColor: 'var(--border-subtle)' }}>
                <p style={{ color: 'var(--text-primary)' }}>{l.action}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{l.actor_name || 'Hệ thống'} · {vnTime(l.created_at)}{l.note ? ` · ${l.note}` : ''}</p>
              </div>
            ))}
            {auditRows.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có nhật ký.</p>}
          </div>
        )}

        {/* Modal xem giấy tờ */}
        {docView && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setDocView(null)}>
            <div className="max-w-2xl w-full rounded-xl overflow-hidden" style={{ background: 'var(--surface-1)' }} onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between px-4 py-2.5">
                <p className="text-sm font-semibold">{docView.filename}</p>
                <button onClick={() => setDocView(null)} className="text-lg px-2" style={{ color: 'var(--text-muted)' }}>✕</button>
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={docView.src} alt={docView.filename} className="w-full max-h-[75vh] object-contain" />
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}

export default function NhanVienPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">⏳</div>}>
      <NhanVienContent />
    </Suspense>
  );
}
