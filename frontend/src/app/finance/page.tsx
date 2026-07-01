'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, SalaryGrade, FixedCost, VariableCost, CommissionStructure } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';

type Tab = 'salary-grades' | 'fixed-costs' | 'variable-costs' | 'commissions';

// Demo data
const DEMO_SALARY_GRADES: SalaryGrade[] = [
  { id: 'sg-1', grade_name: 'Bac 1', base_salary: 8000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-2', grade_name: 'Bac 2', base_salary: 10000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-3', grade_name: 'Bac 3', base_salary: 12000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-4', grade_name: 'Bac 4', base_salary: 15000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-5', grade_name: 'Bac 5', base_salary: 20000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-6', grade_name: 'Bac 6', base_salary: 25000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];

const DEMO_FIXED_COSTS: FixedCost[] = [
  { id: 'fc-1', category: 'Tien mat bang', amount: 15000000, month: '2026-06', notes: 'Van phong Q1', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-2', category: 'Dien nuoc', amount: 3500000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-3', category: 'Internet', amount: 1200000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-4', category: 'Bao hiem office', amount: 2000000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
];

const DEMO_VARIABLE_COSTS: VariableCost[] = [
  { id: 'vc-1', category: 'Di lai du an', amount: 5000000, month: '2026-06', notes: 'Xang xe thang 6', created_at: '2026-06-01T00:00:00Z' },
  { id: 'vc-2', category: 'Vun thi cong', amount: 3200000, month: '2026-06', notes: 'Hao hut vat lieu', created_at: '2026-06-01T00:00:00Z' },
];

const DEMO_COMMISSIONS: CommissionStructure[] = [
  { id: 'cs-1', department: 'sales', commission_type: 'design_contract', rate: 0.03, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-2', department: 'sales', commission_type: 'construction_contract', rate: 0.02, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-3', department: 'leader', commission_type: 'leader_override', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-4', department: 'design', commission_type: 'design_fee', rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-5', department: 'pm', commission_type: 'project_value', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];

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
    { key: 'salary-grades', label: 'Bac luong', icon: '💰' },
    { key: 'fixed-costs', label: 'Chi phi co dinh', icon: '🏢' },
    { key: 'variable-costs', label: 'Chi phi bien phi', icon: '📊' },
    { key: 'commissions', label: 'Co cau hoa hong', icon: '🎁' },
  ];

  const totalFixedCosts = fixedCosts.reduce((s, c) => s + c.amount, 0);
  const totalVariableCosts = variableCosts.reduce((s, c) => s + c.amount, 0);

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">💰 Finance — Quan ly Tai chinh</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">Quan ly luong, chi phi, hoa hong</p>
          </div>
          {isDemo && <span className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>🎯 DEMO MODE</span>}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-5 border-l-2 border-l-emerald-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">🏢 Chi phi co dinh ({selectedMonth})</p>
            <p className="text-xl font-bold text-emerald-400">{formatCurrency(totalFixedCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-amber-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">📊 Chi phi bien phi ({selectedMonth})</p>
            <p className="text-xl font-bold text-amber-400">{formatCurrency(totalVariableCosts)}</p>
          </div>
          <div className="glass-card p-5 border-l-2 border-l-blue-500">
            <p className="text-xs text-[var(--text-muted)] mb-1">💰 Tong chi phi</p>
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
          <div className="text-center py-20 text-[var(--text-muted)]">Dang tai...</div>
        ) : (
          <>
            {/* Salary Grades Tab */}
            {tab === 'salary-grades' && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold">💰 Bac luong ({salaryGrades.length} bac)</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Bac</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Luong gross</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHXH NLD</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHYT</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">BHTN</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Tong khau tru</th>
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
                <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold">🏢 Chi phi co dinh — {selectedMonth}</h3>
                  <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                    className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Khoan muc</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">So tien</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ghi chu</th>
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
                        <td className="p-3 text-sm gold-gradient">TONG CONG</td>
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
                <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                  <h3 className="text-sm font-bold">📊 Chi phi bien phi — {selectedMonth}</h3>
                  <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
                    className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Khoan muc</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">So tien</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Du an</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ghi chu</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variableCosts.length === 0 ? (
                        <tr><td colSpan={4} className="text-center p-8 text-[var(--text-muted)]">Chua co chi phi bien phi</td></tr>
                      ) : variableCosts.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.category}</td>
                          <td className="p-3 text-right text-amber-400 font-mono">{formatCurrency(c.amount)}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.project_id ? (projectMap[c.project_id] || 'Dự án chung') : 'Chung'}</td>
                          <td className="p-3 text-xs text-[var(--text-muted)]">{c.notes || '—'}</td>
                        </tr>
                      ))}
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TONG CONG</td>
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
                  <h3 className="text-sm font-bold">🎁 Co cau hoa hong theo phong ban</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Phong ban</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Loai HH</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Ty le</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ap dung tu</th>
                      </tr>
                    </thead>
                    <tbody>
                      {commissions.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium capitalize">{c.department}</td>
                          <td className="p-3 text-xs text-[var(--text-secondary)]">{c.commission_type}</td>
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
