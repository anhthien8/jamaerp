'use client';

import { useXacNhan } from '@/components/ui/XacNhan';
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, SalaryGrade, FixedCost, VariableCost, CommissionStructure } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';
import { labelOf, COMMISSION_TYPE_LABELS, DEPARTMENT_LABELS } from '@/lib/labels';
import LineIcon from '@/components/ui/LineIcon';
import MoneyInput from '@/components/ui/MoneyInput';

type Tab = 'salary-grades' | 'fixed-costs' | 'variable-costs' | 'commissions';
type LoaiChiPhi = 'fixed' | 'variable';
type FormChiPhi = { loai: LoaiChiPhi; id?: string; category: string; amount: string; project_id: string; notes: string };
const DUONG: Record<LoaiChiPhi, string> = { fixed: '/fixed-costs', variable: '/variable-costs' };
/** Số tiền viết đủ cho dòng chi tiết (thẻ tổng vẫn dùng số gọn). */
const tienDu = (v?: number | null) => (v == null ? '—' : `${Math.round(v).toLocaleString('vi-VN')} đ`);

export default function FinancePage() {
  const xacNhan = useXacNhan();
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>('salary-grades');
  const [salaryGrades, setSalaryGrades] = useState<SalaryGrade[]>([]);
  const [fixedCosts, setFixedCosts] = useState<FixedCost[]>([]);
  const [variableCosts, setVariableCosts] = useState<VariableCost[]>([]);
  const [commissions, setCommissions] = useState<CommissionStructure[]>([]);
  // Đóng đinh '2026-06' làm tab chi phí luôn mở vào tháng cũ — ai không để ý bộ lọc
  // sẽ tưởng tháng này chưa nhập gì. Mặc định = tháng hiện tại theo giờ máy người dùng.
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });
  const [loadingData, setLoadingData] = useState(true);
  const [loadError, setLoadError] = useState('');
  // Thêm / sửa / xoá khoản chi (24/11): trang này trước đó chỉ đọc dù máy chủ đã có đủ lệnh — kế toán phải nhờ kỹ thuật.
  const [form, setForm] = useState<FormChiPhi | null>(null);
  const [dangLuu, setDangLuu] = useState(''); // '' | 'luu' | 'chep' | id khoản đang xoá
  const [projectsList, setProjectsList] = useState<Array<{id: string, name: string}>>([]);

  // /salary-grades backend gác CHẶT HƠN canViewPnL (chỉ admin/kế toán) — executive
  // gọi là 403 làm vỡ cả Promise.all. Gọi API + hiện tab «Bậc lương» theo đúng cổng đó.
  const canViewSalary = user ? getPermissions(user.role as UserRole).canViewPayroll : false;

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
    if (!loading && user) {
      const perms = getPermissions(user.role as UserRole);
      // Khớp với cổng backend: 4 API trang này gọi đều gác canViewPnL (hoặc chặt hơn).
      // Trước 13/08/2026 gác canViewAccounting ⇒ trưởng phòng/sale vào được trang
      // nhưng API trả toàn 403, rơi về số demo tưởng là thật.
      if (!perms.canViewPnL) router.push('/');
    }
  }, [user, loading, router]);

  const loadData = useCallback(async () => {
    setLoadingData(true);
    try {
      try {
        const [sg, fc, vc, cs] = await Promise.all([
          canViewSalary ? api.getSalaryGrades() : Promise.resolve([] as SalaryGrade[]),
          api.getFixedCosts(selectedMonth),
          api.getVariableCosts(selectedMonth),
          api.getCommissionStructures(),
        ]);
        setSalaryGrades(sg);
        setFixedCosts(fc);
        setVariableCosts(vc);
        setCommissions(cs);
        setLoadError('');
      } catch {
        // TUYỆT ĐỐI không rơi về số mẫu — người dùng sẽ nhìn
        // số bịa tưởng là thật (audit 13/08). Hiện lỗi rõ ràng, bảng để trống.
        setSalaryGrades([]);
        setFixedCosts([]);
        setVariableCosts([]);
        setCommissions([]);
        setLoadError('Không tải được số liệu tài chính từ máy chủ. Vui lòng tải lại trang hoặc báo kỹ thuật.');
      }
      try {
        const pResult = await api.getProjects();
        const pItems: Array<{ id: string; name: string }> = Array.isArray(pResult) ? pResult : pResult.items || [];
        setProjectsList(pItems.map(p => ({ id: p.id, name: p.name })));
      } catch {}
    } finally {
      setLoadingData(false);
    }
  }, [selectedMonth, canViewSalary]);

  useEffect(() => { if (user) void Promise.resolve().then(loadData); }, [user, loadData]);

  // Không có quyền bậc lương thì tab mặc định rơi về Chi phí cố định
  useEffect(() => {
    if (user && !canViewSalary && tab === 'salary-grades') void Promise.resolve().then(() => setTab('fixed-costs'));
  }, [user, canViewSalary, tab]);

  if (loading) return <Sidebar><div className="p-6"><div className="skeleton h-8 w-64 rounded-xl" /></div></Sidebar>;
  if (!user) return null;

  // Khớp cổng máy chủ: chỉ Admin / Kế toán ghi được chi phí.
  const canSuaChiPhi = user.role === 'admin' || user.role === 'accountant';
  const loiCua = (e: unknown, mac: string) => (e instanceof Error && e.message ? e.message : mac);

  // Sửa thẳng danh sách đang có, không tải lại ngay sau khi ghi (lượt tải đó hay trả về số cũ).
  const luuChiPhi = async () => {
    if (!form || dangLuu) return;
    const so = Number(form.amount) || 0;
    if (!form.category.trim()) { toast('Nhập tên khoản mục', 'error'); return; }
    if (!(so > 0)) { toast('Nhập số tiền', 'error'); return; }
    setDangLuu('luu');
    try {
      const dong = { category: form.category.trim(), amount: so, month: selectedMonth, notes: form.notes.trim() || undefined, project_id: form.loai === 'variable' ? form.project_id || undefined : undefined };
      const body = { ...dong, notes: dong.notes ?? null, ...(form.loai === 'variable' ? { project_id: dong.project_id ?? null } : {}) };
      const r = await api.request<{ id: string }>(form.id ? `${DUONG[form.loai]}/${form.id}` : DUONG[form.loai], { method: form.id ? 'PUT' : 'POST', body });
      const ghi = <T extends FixedCost | VariableCost>(prev: T[]): T[] => form.id
        ? prev.map(c => (c.id === form.id ? { ...c, ...dong } : c))
        : [...prev, { ...dong, id: r.id, created_at: new Date().toISOString() } as T];
      if (form.loai === 'fixed') setFixedCosts(ghi); else setVariableCosts(ghi);
      toast(form.id ? 'Đã sửa khoản chi' : 'Đã thêm khoản chi', 'success');
      setForm(null);
    } catch (e) { toast(loiCua(e, 'Không lưu được khoản chi'), 'error'); }
    finally { setDangLuu(''); }
  };
  const xoaChiPhi = async (loai: LoaiChiPhi, c: FixedCost | VariableCost) => {
    if (dangLuu || !await xacNhan(`Xoá khoản «${c.category}» ${tienDu(c.amount)} của ${selectedMonth}?`)) return;
    setDangLuu(c.id);
    try {
      await api.request(`${DUONG[loai]}/${c.id}`, { method: 'DELETE' });
      if (loai === 'fixed') setFixedCosts(prev => prev.filter(x => x.id !== c.id)); else setVariableCosts(prev => prev.filter(x => x.id !== c.id));
      toast('Đã xoá khoản chi', 'success');
    } catch (e) { toast(loiCua(e, 'Không xoá được'), 'error'); }
    finally { setDangLuu(''); }
  };
  /** Định phí tháng nào cũng gần như nhau (thuê VP, điện, lương cứng…) → chép các khoản của tháng trước sang tháng đang
   *  xem rồi sửa số nếu khác. Khoản trùng tên đã có trong tháng thì bỏ qua, bấm lại không sinh đôi. */
  const chepThangTruoc = async () => {
    if (dangLuu) return;
    const [nam, thang] = selectedMonth.split('-').map(Number);
    const truoc = thang === 1 ? `${nam - 1}-12` : `${nam}-${String(thang - 1).padStart(2, '0')}`;
    setDangLuu('chep');
    const moi: FixedCost[] = [];
    try {
      const cu = await api.getFixedCosts(truoc);
      const daCo = new Set(fixedCosts.map(c => c.category.trim().toLowerCase()));
      const can = cu.filter(c => !daCo.has(c.category.trim().toLowerCase()));
      if (!cu.length) { toast(`Tháng ${truoc} chưa có khoản nào để chép`, 'info'); return; }
      if (!can.length) { toast(`Các khoản của ${truoc} đã có đủ trong ${selectedMonth}`, 'info'); return; }
      if (!await xacNhan(`Chép ${can.length} khoản từ ${truoc} sang ${selectedMonth}, tổng ${tienDu(can.reduce((s, c) => s + c.amount, 0))}?\nKhoản nào khác số thì bấm sửa sau.`)) return;
      for (const c of can) {
        const r = await api.request<{ id: string }>(DUONG.fixed, { method: 'POST', body: { category: c.category, amount: c.amount, month: selectedMonth, notes: c.notes ?? null } });
        moi.push({ ...c, id: r.id, month: selectedMonth, created_at: new Date().toISOString() });
      }
      toast(`Đã chép ${moi.length} khoản từ ${truoc}`, 'success');
    } catch (e) { toast(`${moi.length ? `Đã chép ${moi.length} khoản rồi dừng: ` : ''}${loiCua(e, 'Không chép được')}`, 'error'); }
    finally { if (moi.length) setFixedCosts(prev => [...prev, ...moi]); setDangLuu(''); }
  };
  const nutDong = (loai: LoaiChiPhi, c: FixedCost | VariableCost) => canSuaChiPhi && (
    <span className="inline-flex items-center gap-0.5 shrink-0">
      <button type="button" aria-label={`Sửa ${c.category}`} title="Sửa" disabled={!!dangLuu}
        onClick={() => setForm({ loai, id: c.id, category: c.category, amount: String(c.amount), project_id: ('project_id' in c ? c.project_id : '') || '', notes: c.notes || '' })}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--gold-400)] disabled:opacity-40"><LineIcon name="edit" size={15} color="currentColor" /></button>
      <button type="button" aria-label={`Xoá ${c.category}`} title="Xoá" disabled={!!dangLuu} onClick={() => xoaChiPhi(loai, c)}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-red-400 disabled:opacity-40"><LineIcon name="trash" size={15} color="currentColor" /></button>
    </span>
  );
  const nutThem = (loai: LoaiChiPhi) => canSuaChiPhi && (
    <button type="button" disabled={!!dangLuu} onClick={() => setForm({ loai, category: '', amount: '', project_id: '', notes: '' })}
      className="px-3 min-h-[36px] rounded-xl text-xs font-semibold disabled:opacity-50" style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}>
      <LineIcon name="plus" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />Thêm khoản
    </button>
  );

  const projectMap = projectsList.reduce((acc, p) => { acc[p.id] = p.name; return acc; }, {} as Record<string, string>);

  const tabs: { key: Tab; label: string; icon: string }[] = [
    ...(canViewSalary ? [{ key: 'salary-grades' as Tab, label: 'Bậc lương', icon: 'money' }] : []),
    { key: 'fixed-costs', label: 'Chi phí cố định', icon: 'building' },
    { key: 'variable-costs', label: 'Chi phí biến phí', icon: 'chart' },
    { key: 'commissions', label: 'Cơ cấu hoa hồng', icon: 'gift' },
  ];

  const totalFixedCosts = fixedCosts.reduce((s, c) => s + c.amount, 0);
  const totalVariableCosts = variableCosts.reduce((s, c) => s + c.amount, 0);

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Tài chính — Lương &amp; Hoa hồng</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">Quản lý lương, chi phí, hoa hồng</p>
          </div>
        </div>

        {loadError && (
          <div className="p-4 rounded-xl text-sm" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', color: '#F87171' }}>
            <LineIcon name="alert" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{loadError}
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-5 border-l-2 border-l-emerald-500">
            <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="building" size={16} className="inline-block align-[-2px] mr-1.5" />Chi phí cố định ({selectedMonth})</p>
            <p className="text-xl font-bold text-emerald-400">{formatCurrency(totalFixedCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-amber-500">
            <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="chart" size={16} className="inline-block align-[-2px] mr-1.5" />Chi phí biến phí ({selectedMonth})</p>
            <p className="text-xl font-bold text-amber-400">{formatCurrency(totalVariableCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-blue-500">
            <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="money" size={16} className="inline-block align-[-2px] mr-1.5" />Tổng chi phí</p>
            <p className="text-xl font-bold text-blue-400">{formatCurrency(totalFixedCosts + totalVariableCosts)}</p>
          </div>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--surface-2)' }}>
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={cn('flex-1 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
                tab === t.key ? 'bg-[var(--gold-500)]/20 text-[var(--gold-500)]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]')}>
              <LineIcon name={t.icon} size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />{t.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {loadingData ? (
          <div className="text-center py-20 text-[var(--text-muted)]">Đang tải...</div>
        ) : (
          <>
            {/* Salary Grades Tab */}
            {tab === 'salary-grades' && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold"><LineIcon name="money" size={16} className="inline-block align-[-2px] mr-1.5" />Bậc lương ({salaryGrades.length} bậc)</h3>
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {salaryGrades.map(g => {
                    const totalDeduct = g.base_salary * (g.bhxh_rate + g.bhyt_rate + g.bhtn_rate) / 100;
                    return (
                      <div key={g.id} className="p-3 rounded-xl space-y-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                        <div className="flex justify-between items-center">
                          <span className="font-semibold text-sm">{g.grade_name}</span>
                          <span className="text-emerald-400 font-mono font-bold text-sm">{formatCurrency(g.base_salary)}</span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div><span className="text-[var(--text-muted)]">BHXH</span><br/><span className="text-red-400 font-mono">{g.bhxh_rate}%</span></div>
                          <div><span className="text-[var(--text-muted)]">BHYT</span><br/><span className="text-red-400 font-mono">{g.bhyt_rate}%</span></div>
                          <div><span className="text-[var(--text-muted)]">BHTN</span><br/><span className="text-red-400 font-mono">{g.bhtn_rate}%</span></div>
                        </div>
                        <div className="flex justify-between text-xs pt-1" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                          <span className="text-[var(--text-muted)]">Tổng khấu trừ</span>
                          <span className="text-amber-400 font-mono font-semibold">{formatCurrency(totalDeduct)}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Bậc</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Lương gross</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHXH NLĐ</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHYT</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHTN</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Tổng khấu trừ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salaryGrades.map(g => {
                        const totalDeduct = g.base_salary * (g.bhxh_rate + g.bhyt_rate + g.bhtn_rate) / 100;
                        return (
                          <tr key={g.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                            <td className="p-3 font-medium">{g.grade_name}</td>
                            <td className="p-3 text-right text-emerald-400 font-mono">{formatCurrency(g.base_salary)}</td>
                            <td className="p-3 text-right text-red-400 font-mono text-xs">{g.bhxh_rate}%</td>
                            <td className="p-3 text-right text-red-400 font-mono text-xs">{g.bhyt_rate}%</td>
                            <td className="p-3 text-right text-red-400 font-mono text-xs">{g.bhtn_rate}%</td>
                            <td className="p-3 text-right text-amber-400 font-mono text-xs">{formatCurrency(totalDeduct)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Fixed Costs Tab */}
            {tab === 'fixed-costs' && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold"><LineIcon name="building" size={16} className="inline-block align-[-2px] mr-1.5" />Chi phí cố định — {selectedMonth}</h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                      className="px-3 min-h-[36px] rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                    {canSuaChiPhi && (
                      <button type="button" disabled={!!dangLuu} onClick={chepThangTruoc}
                        className="px-3 min-h-[36px] rounded-xl text-xs font-medium disabled:opacity-50" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                        <LineIcon name="copy" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />{dangLuu === 'chep' ? 'Đang chép…' : 'Chép từ tháng trước'}
                      </button>
                    )}
                    {nutThem('fixed')}
                  </div>
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {fixedCosts.length === 0 && <p className="text-center py-6 text-sm text-[var(--text-muted)]">Tháng này chưa có khoản nào{canSuaChiPhi ? ' — bấm «Chép từ tháng trước» hoặc «Thêm khoản».' : '.'}</p>}
                  {fixedCosts.map(c => (
                    <div key={c.id} className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div>
                        <p className="font-medium text-sm">{c.category}</p>
                        {c.notes && <p className="text-xs text-[var(--text-muted)] mt-0.5">{c.notes}</p>}
                      </div>
                      <span className="flex items-center gap-1 shrink-0"><span className="text-amber-400 font-mono font-bold text-sm">{tienDu(c.amount)}</span>{nutDong('fixed', c)}</span>
                    </div>
                  ))}
                  <div className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid var(--gold-500)' }}>
                    <span className="font-bold text-sm gold-gradient">TỔNG CỘNG</span>
                    <span className="text-[var(--gold-400)] font-mono font-bold">{tienDu(totalFixedCosts)}</span>
                  </div>
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Khoản mục</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Số tiền</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ghi chú</th>
                        {canSuaChiPhi && <th className="p-3" aria-label="Thao tác" />}
                      </tr>
                    </thead>
                    <tbody>
                      {fixedCosts.length === 0 && (
                        <tr><td colSpan={canSuaChiPhi ? 4 : 3} className="text-center p-8 text-[var(--text-muted)]">Tháng này chưa có khoản nào{canSuaChiPhi ? ' — bấm «Chép từ tháng trước» hoặc «Thêm khoản».' : '.'}</td></tr>
                      )}
                      {fixedCosts.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.category}</td>
                          <td className="p-3 text-right text-amber-400 font-mono">{tienDu(c.amount)}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.notes || '—'}</td>
                          {canSuaChiPhi && <td className="px-3 py-1 text-right">{nutDong('fixed', c)}</td>}
                        </tr>
                      ))}
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3 text-right text-[var(--gold-400)] font-mono">{tienDu(totalFixedCosts)}</td>
                        <td colSpan={canSuaChiPhi ? 2 : 1}></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Variable Costs Tab */}
            {tab === 'variable-costs' && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold"><LineIcon name="chart" size={16} className="inline-block align-[-2px] mr-1.5" />Chi phí biến phí — {selectedMonth}</h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                      className="px-3 min-h-[36px] rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                    {nutThem('variable')}
                  </div>
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {variableCosts.length === 0 ? (
                    <p className="text-center py-8 text-sm text-[var(--text-muted)]">Chưa có chi phí biến phí</p>
                  ) : variableCosts.map(c => (
                    <div key={c.id} className="p-3 rounded-xl space-y-1" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex justify-between items-center">
                        <span className="font-medium text-sm">{c.category}</span>
                        <span className="flex items-center gap-1 shrink-0"><span className="text-amber-400 font-mono font-bold text-sm">{tienDu(c.amount)}</span>{nutDong('variable', c)}</span>
                      </div>
                      <div className="flex gap-3 text-xs text-[var(--text-muted)]">
                        <span><LineIcon name="layers" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />{c.project_id ? (projectMap[c.project_id] || 'Dự án chung') : 'Chung'}</span>
                        {c.notes && <span><LineIcon name="edit" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />{c.notes}</span>}
                      </div>
                    </div>
                  ))}
                  <div className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid var(--gold-500)' }}>
                    <span className="font-bold text-sm gold-gradient">TỔNG CỘNG</span>
                    <span className="text-[var(--gold-400)] font-mono font-bold">{tienDu(totalVariableCosts)}</span>
                  </div>
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Khoản mục</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Số tiền</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Dự án</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ghi chú</th>
                        {canSuaChiPhi && <th className="p-3" aria-label="Thao tác" />}
                      </tr>
                    </thead>
                    <tbody>
                      {variableCosts.length === 0 ? (
                        <tr><td colSpan={canSuaChiPhi ? 5 : 4} className="text-center p-8 text-[var(--text-muted)]">Chưa có chi phí biến phí</td></tr>
                      ) : variableCosts.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.category}</td>
                          <td className="p-3 text-right text-amber-400 font-mono">{tienDu(c.amount)}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.project_id ? (projectMap[c.project_id] || 'Dự án chung') : 'Chung'}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.notes || '—'}</td>
                          {canSuaChiPhi && <td className="px-3 py-1 text-right">{nutDong('variable', c)}</td>}
                        </tr>
                      ))}
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3 text-right text-[var(--gold-400)] font-mono">{tienDu(totalVariableCosts)}</td>
                        <td colSpan={canSuaChiPhi ? 3 : 2}></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Commission Structures Tab */}
            {tab === 'commissions' && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold"><LineIcon name="gift" size={16} className="inline-block align-[-2px] mr-1.5" />Cơ cấu hoa hồng theo phòng ban</h3>
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {commissions.map(c => (
                    <div key={c.id} className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div>
                        <p className="font-medium text-sm">{labelOf(DEPARTMENT_LABELS, c.department)}</p>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">{labelOf(COMMISSION_TYPE_LABELS, c.commission_type)}</p>
                        <p className="text-xs text-[var(--text-muted)]">Từ {c.effective_date}</p>
                      </div>
                      <span className="text-[var(--gold-400)] font-mono font-bold text-lg">{(c.rate * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Phòng ban</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Loại HH</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Tỷ lệ</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Áp dụng từ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {commissions.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{labelOf(DEPARTMENT_LABELS, c.department)}</td>
                          <td className="p-3 text-xs text-[var(--text-secondary)]">{labelOf(COMMISSION_TYPE_LABELS, c.commission_type)}</td>
                          <td className="p-3 text-right text-[var(--gold-400)] font-mono font-bold">{(c.rate * 100).toFixed(1)}%</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.effective_date}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {form && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[8vh]">
            <div className="absolute inset-0 bg-black/70" />
            <div className="relative w-full max-w-md rounded-2xl p-5 space-y-3" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}>
              <div>
                <h3 className="text-base font-bold text-[var(--text-primary)]">{form.id ? 'Sửa khoản chi' : 'Thêm khoản chi'}</h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{form.loai === 'fixed' ? 'Chi phí cố định' : 'Chi phí biến phí'} · tháng {selectedMonth}</p>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Khoản mục</label>
                <input autoFocus list="ds-khoan-muc" value={form.category} onChange={e => setForm(f => f && ({ ...f, category: e.target.value }))}
                  placeholder={form.loai === 'fixed' ? 'VD: Thuê văn phòng' : 'VD: Vận chuyển vật tư'}
                  className="w-full px-3 py-2 rounded-xl text-base sm:text-sm outline-none" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }} />
                <datalist id="ds-khoan-muc">
                  {Array.from(new Set((form.loai === 'fixed' ? fixedCosts : variableCosts).map(x => x.category))).map(k => <option key={k} value={k} />)}
                </datalist>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Số tiền (nghìn đồng)</label>
                <MoneyInput valueDong={form.amount} onChangeDong={v => setForm(f => f && ({ ...f, amount: v }))} placeholder="VD: 25000 = 25 triệu"
                  className="w-full px-3 py-2 rounded-xl text-base sm:text-sm pr-24" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }} />
              </div>
              {form.loai === 'variable' && (
                <div>
                  <label className="text-xs text-[var(--text-muted)] mb-1 block">Dự án</label>
                  <select value={form.project_id} onChange={e => setForm(f => f && ({ ...f, project_id: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-base sm:text-sm outline-none" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}>
                    <option value="">Chung (không gắn dự án)</option>
                    {projectsList.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Ghi chú</label>
                <input value={form.notes} onChange={e => setForm(f => f && ({ ...f, notes: e.target.value }))} placeholder="Không bắt buộc"
                  className="w-full px-3 py-2 rounded-xl text-base sm:text-sm outline-none" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }} />
              </div>
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={() => setForm(null)} disabled={!!dangLuu} className="flex-1 min-h-[40px] rounded-xl text-sm font-medium" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>Hủy</button>
                <button type="button" onClick={luuChiPhi} disabled={!!dangLuu || !form.category.trim() || !Number(form.amount)}
                  className="flex-1 min-h-[40px] rounded-xl text-sm font-semibold disabled:opacity-40" style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}>
                  {dangLuu === 'luu' ? 'Đang lưu…' : form.id ? 'Lưu thay đổi' : 'Thêm khoản'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
