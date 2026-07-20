'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, SalaryGrade, FixedCost, VariableCost, CommissionStructure } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';
import { DEMO_SALARY_GRADES, DEMO_FIXED_COSTS, DEMO_VARIABLE_COSTS, DEMO_COMMISSION_STRUCTURES as DEMO_COMMISSIONS } from '@/lib/demo-data';
import { labelOf, COMMISSION_TYPE_LABELS, DEPARTMENT_LABELS } from '@/lib/labels';

type Tab = 'salary-grades' | 'fixed-costs' | 'variable-costs' | 'commissions';

export default function FinancePage() {
  const { user, loading, isDemo } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>('salary-grades');
  const [salaryGrades, setSalaryGrades] = useState<SalaryGrade[]>([]);
  const [fixedCosts, setFixedCosts] = useState<FixedCost[]>([]);
  const [variableCosts, setVariableCosts] = useState<VariableCost[]>([]);
  const [commissions, setCommissions] = useState<CommissionStructure[]>([]);
  const [selectedMonth, setSelectedMonth] = useState('2026-06');
  const [loadingData, setLoadingData] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [projectsList, setProjectsList] = useState<Array<{id: string, name: string}>>([]);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user) {
      const perms = getPermissions(user.role as UserRole);
      if (!perms.canViewAccounting) router.push('/');
    }
  }, [user, loading, router]);

  const loadData = useCallback(async () => {
    setLoadingData(true);
    try {
      if (isDemo) {
        setSalaryGrades(DEMO_SALARY_GRADES);
        setFixedCosts(DEMO_FIXED_COSTS);
        setVariableCosts(DEMO_VARIABLE_COSTS);
        setCommissions(DEMO_COMMISSIONS);
      } else {
        try {
          const [sg, fc, vc, cs] = await Promise.all([
            api.getSalaryGrades(),
            api.getFixedCosts(selectedMonth),
            api.getVariableCosts(selectedMonth),
            api.getCommissionStructures(),
          ]);
          setSalaryGrades(sg);
          setFixedCosts(fc);
          setVariableCosts(vc);
          setCommissions(cs);
        } catch {
          setSalaryGrades(DEMO_SALARY_GRADES);
          setFixedCosts(DEMO_FIXED_COSTS);
          setVariableCosts(DEMO_VARIABLE_COSTS);
          setCommissions(DEMO_COMMISSIONS);
        }
        try {
          const pResult = await api.getProjects();
          const pItems = Array.isArray(pResult) ? pResult : (pResult as any).items || [];
          setProjectsList(pItems.map((p: any) => ({ id: p.id, name: p.name })));
        } catch {}
      }
    } finally {
      setLoadingData(false);
    }
  }, [isDemo, selectedMonth]);

  useEffect(() => { if (user) void Promise.resolve().then(loadData); }, [user, loadData]);

  if (loading) return <Sidebar><div className="p-6"><div className="skeleton h-8 w-64 rounded-xl" /></div></Sidebar>;
  if (!user) return null;

  const projectMap = projectsList.reduce((acc, p) => { acc[p.id] = p.name; return acc; }, {} as Record<string, string>);

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'salary-grades', label: 'Bậc lương', icon: '💰' },
    { key: 'fixed-costs', label: 'Chi phí cố định', icon: '🏢' },
    { key: 'variable-costs', label: 'Chi phí biến phí', icon: '📊' },
    { key: 'commissions', label: 'Cơ cấu hoa hồng', icon: '🎁' },
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
          {isDemo && <span className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>🎯 TẬP LUYỆN</span>}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-5 border-l-2 border-l-emerald-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">🏢 Chi phí cố định ({selectedMonth})</p>
            <p className="text-xl font-bold text-emerald-400">{formatCurrency(totalFixedCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-amber-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">📊 Chi phí biến phí ({selectedMonth})</p>
            <p className="text-xl font-bold text-amber-400">{formatCurrency(totalVariableCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-blue-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">💰 Tổng chi phí</p>
            <p className="text-xl font-bold text-blue-400">{formatCurrency(totalFixedCosts + totalVariableCosts)}</p>
          </div>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--surface-2)' }}>
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={cn('flex-1 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
                tab === t.key ? 'bg-[#C9A96E]/20 text-[#C9A96E]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]')}>
              {t.icon} {t.label}
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
                  <h3 className="text-sm font-bold">💰 Bậc lương ({salaryGrades.length} bậc)</h3>
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
                  <h3 className="text-sm font-bold">🏢 Chi phí cố định — {selectedMonth}</h3>
                  <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                    className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {fixedCosts.map(c => (
                    <div key={c.id} className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div>
                        <p className="font-medium text-sm">{c.category}</p>
                        {c.notes && <p className="text-xs text-[var(--text-muted)] mt-0.5">{c.notes}</p>}
                      </div>
                      <span className="text-amber-400 font-mono font-bold text-sm">{formatCurrency(c.amount)}</span>
                    </div>
                  ))}
                  <div className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid var(--gold-500)' }}>
                    <span className="font-bold text-sm gold-gradient">TỔNG CỘNG</span>
                    <span className="text-[var(--gold-400)] font-mono font-bold">{formatCurrency(totalFixedCosts)}</span>
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
                      </tr>
                    </thead>
                    <tbody>
                      {fixedCosts.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.category}</td>
                          <td className="p-3 text-right text-amber-400 font-mono">{formatCurrency(c.amount)}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.notes || '—'}</td>
                        </tr>
                      ))}
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3 text-right text-[var(--gold-400)] font-mono">{formatCurrency(totalFixedCosts)}</td>
                        <td></td>
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
                  <h3 className="text-sm font-bold">📊 Chi phí biến phí — {selectedMonth}</h3>
                  <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                    className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-3">
                  {variableCosts.length === 0 ? (
                    <p className="text-center py-8 text-sm text-[var(--text-muted)]">Chưa có chi phí biến phí</p>
                  ) : variableCosts.map(c => (
                    <div key={c.id} className="p-3 rounded-xl space-y-1" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex justify-between items-center">
                        <span className="font-medium text-sm">{c.category}</span>
                        <span className="text-amber-400 font-mono font-bold text-sm">{formatCurrency(c.amount)}</span>
                      </div>
                      <div className="flex gap-3 text-xs text-[var(--text-muted)]">
                        <span>📁 {c.project_id ? (projectMap[c.project_id] || 'Dự án chung') : 'Chung'}</span>
                        {c.notes && <span>📝 {c.notes}</span>}
                      </div>
                    </div>
                  ))}
                  <div className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'rgba(201,169,110,0.08)', border: '1px solid var(--gold-500)' }}>
                    <span className="font-bold text-sm gold-gradient">TỔNG CỘNG</span>
                    <span className="text-[var(--gold-400)] font-mono font-bold">{formatCurrency(totalVariableCosts)}</span>
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
                      </tr>
                    </thead>
                    <tbody>
                      {variableCosts.length === 0 ? (
                        <tr><td colSpan={4} className="text-center p-8 text-[var(--text-muted)]">Chưa có chi phí biến phí</td></tr>
                      ) : variableCosts.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.category}</td>
                          <td className="p-3 text-right text-amber-400 font-mono">{formatCurrency(c.amount)}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.project_id ? (projectMap[c.project_id] || 'Dự án chung') : 'Chung'}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.notes || '—'}</td>
                        </tr>
                      ))}
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3 text-right text-[var(--gold-400)] font-mono">{formatCurrency(totalVariableCosts)}</td>
                        <td></td>
                        <td></td>
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
                  <h3 className="text-sm font-bold">🎁 Cơ cấu hoa hồng theo phòng ban</h3>
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
      </div>
    </Sidebar>
  );
}
