'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';

// ── Types ──────────────────────────────────────────────────
interface ProjectPL {
  project_id: string;
  project_code: string;
  project_name: string;
  revenue: number;
  costs: number;
  profit: number;
  margin: number;
  status: string;
  cost_breakdown?: {
    materials: number;
    transactions: number;
    commissions: number;
  };
}

interface CompanyPLSummary {
  total_revenue: number;
  total_costs: number;
  net_profit: number;
  margin: number;
  project_count: number;
  profitable_projects: number;
  loss_projects: number;
}

// ── Mock data for demo mode ────────────────────────────────
const MOCK_COMPANY_SUMMARY: CompanyPLSummary = {
  total_revenue: 3_680_000_000,
  total_costs: 982_000_000,
  net_profit: 2_698_000_000,
  margin: 73.3,
  project_count: 5,
  profitable_projects: 4,
  loss_projects: 1,
};

const MOCK_PROJECT_PL: ProjectPL[] = [
  {
    project_id: 'proj-001',
    project_code: 'JMH-0601',
    project_name: 'Biệt thự An Lạc - Long An',
    revenue: 1_250_000_000,
    costs: 285_000_000,
    profit: 965_000_000,
    margin: 77.2,
    status: 'in_progress',
    cost_breakdown: { materials: 180_000_000, transactions: 75_000_000, commissions: 30_000_000 },
  },
  {
    project_id: 'proj-002',
    project_code: 'JMH-0587',
    project_name: 'Nhà phố Sunrise - Q7',
    revenue: 890_000_000,
    costs: 248_000_000,
    profit: 642_000_000,
    margin: 72.1,
    status: 'in_progress',
    cost_breakdown: { materials: 155_000_000, transactions: 68_000_000, commissions: 25_000_000 },
  },
  {
    project_id: 'proj-003',
    project_code: 'JMH-0593',
    project_name: 'Căn hộ Penthouse - Thủ Đức',
    revenue: 680_000_000,
    costs: 195_000_000,
    profit: 485_000_000,
    margin: 71.3,
    status: 'completed',
    cost_breakdown: { materials: 120_000_000, transactions: 50_000_000, commissions: 25_000_000 },
  },
  {
    project_id: 'proj-004',
    project_code: 'JMH-0610',
    project_name: 'Villa The Manor - Bình Chánh',
    revenue: 520_000_000,
    costs: 189_000_000,
    profit: 331_000_000,
    margin: 63.7,
    status: 'in_progress',
    cost_breakdown: { materials: 115_000_000, transactions: 49_000_000, commissions: 25_000_000 },
  },
  {
    project_id: 'proj-005',
    project_code: 'JMH-0615',
    project_name: 'Shophouse Bến Thành - Q1',
    revenue: 340_000_000,
    costs: 65_000_000,
    profit: -15_000_000,
    margin: -4.4,
    status: 'at_risk',
    cost_breakdown: { materials: 40_000_000, transactions: 15_000_000, commissions: 10_000_000 },
  },
];

// ── Access denied view ─────────────────────────────────────
function AccessDenied() {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <span className="text-5xl block mb-4">🔒</span>
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Trang này chỉ dành cho Ban Giám đốc, Kế toán và Ban Quản trị.
          </p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2.5 rounded-xl text-sm font-medium transition-all"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: '#fff' }}
          >
            Quay về Dashboard
          </button>
        </div>
      </div>
    </Sidebar>
  );
}

// ── Skeleton loader ────────────────────────────────────────
function PLSkeleton() {
  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        <div className="skeleton h-8 w-72 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="glass-card p-5">
              <div className="skeleton h-3 w-24 mb-3 rounded" />
              <div className="skeleton h-7 w-32 mb-2 rounded" />
              <div className="skeleton h-3 w-20 rounded" />
            </div>
          ))}
        </div>
        <div className="glass-card p-6">
          <div className="skeleton h-4 w-40 mb-4 rounded" />
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="flex items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="skeleton h-4 w-20 rounded" />
              <div className="skeleton h-4 w-40 rounded" />
              <div className="skeleton h-4 w-24 rounded ml-auto" />
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-4 w-16 rounded" />
            </div>
          ))}
        </div>
      </div>
    </Sidebar>
  );
}

// ── Main Page ──────────────────────────────────────────────
export default function PLPage() {
  const { user, loading, isDemo } = useAuth();
  const router = useRouter();
  const [summary, setSummary] = useState<CompanyPLSummary | null>(null);
  const [projects, setProjects] = useState<ProjectPL[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [sortBy, setSortBy] = useState<'revenue' | 'profit' | 'margin'>('revenue');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      // In demo mode or when API not available, use inline mock data
      if (isDemo) {
        setSummary(MOCK_COMPANY_SUMMARY);
        setProjects(MOCK_PROJECT_PL);
      } else {
        // Try fetching from real API endpoints
        try {
          const s = await api.getPnLSummary();
          const p = await api.getPnLProjects();
          // Normalize field names: backend uses margin_pct, page uses margin
          const normalizedProjects = (p || []).map(item => ({
            project_id: item.project_id || '',
            project_code: item.project_code || '',
            project_name: item.project_name || '',
            revenue: item.revenue || 0,
            costs: item.costs || 0,
            profit: item.profit || 0,
            margin_pct: item.margin_pct || 0,
            margin: item.margin_pct || 0,
            status: 'active',
          }));
          setSummary({
            total_revenue: s.total_revenue,
            total_costs: s.total_costs,
            net_profit: s.net_profit,
            margin: s.margin_pct,
            project_count: normalizedProjects.length,
            profitable_projects: normalizedProjects.filter(proj => proj.profit > 0).length,
            loss_projects: normalizedProjects.filter(proj => proj.profit < 0).length,
          });
          setProjects(normalizedProjects);
        } catch {
          // Fallback to mock data if API endpoints don't exist yet
          setSummary(MOCK_COMPANY_SUMMARY);
          setProjects(MOCK_PROJECT_PL);
        }
      }
    } catch (e) {
      console.warn('P&L API error:', e);
    } finally {
      setLoadingData(false);
    }
  }, [isDemo]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchData);
  }, [user, fetchData]);

  // Auth gate
  if (loading) return <PLSkeleton />;
  if (!user) return null;

  // Role check
  const perms = getPermissions(user.role as UserRole);
  if (!perms.canViewPnL) return <AccessDenied />;

  // Sort handler
  const sortedProjects = [...projects].sort((a, b) => {
    const diff = a[sortBy] - b[sortBy];
    return sortAsc ? diff : -diff;
  });

  const toggleSort = (field: 'revenue' | 'profit' | 'margin') => {
    if (sortBy === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(field);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ field }: { field: string }) => (
    <span className="ml-1 inline-block text-[10px]" style={{ opacity: sortBy === field ? 1 : 0.3 }}>
      {sortBy === field ? (sortAsc ? '▲' : '▼') : '▲▼'}
    </span>
  );

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              P&L <span className="gold-gradient">&mdash; Tổng quan Lợi nhuận</span>
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Phân tích lợi nhuận theo dự án và toàn công ty
            </p>
          </div>
          {isDemo && (
            <div className="px-3 py-1.5 rounded-lg text-center" style={{ background: 'var(--warning-bg)', border: '1px solid rgba(251,191,36,0.2)' }}>
              <span className="text-[0.6875rem] font-semibold" style={{ color: 'var(--warning)' }}>DEMO MODE</span>
            </div>
          )}
        </div>

        {loadingData ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Đang tải dữ liệu P&L...
          </div>
        ) : (
          <>
            {/* ── Company Summary Cards ── */}
            {summary && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Total Revenue */}
                <div className="glass-card p-5 border-l-2 border-l-emerald-500">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Tổng Doanh thu</p>
                      <p className="text-2xl font-bold text-emerald-400">{formatCurrency(summary.total_revenue)}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">{summary.project_count} dự án</p>
                    </div>
                    <span className="text-2xl">&#x1F4B5;</span>
                  </div>
                </div>

                {/* Total Costs */}
                <div className="glass-card p-5 border-l-2 border-l-red-500">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Tổng Chi phí</p>
                      <p className="text-2xl font-bold text-red-400">{formatCurrency(summary.total_costs)}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">
                        {((summary.total_costs / summary.total_revenue) * 100).toFixed(1)}% doanh thu
                      </p>
                    </div>
                    <span className="text-2xl">&#x1F4B8;</span>
                  </div>
                </div>

                {/* Net Profit */}
                <div className="glass-card p-5 border-l-2 border-l-blue-500">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Lợi nhuận ròng</p>
                      <p className={cn('text-2xl font-bold', summary.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {formatCurrency(summary.net_profit)}
                      </p>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">
                        {summary.profitable_projects} lãi / {summary.loss_projects} lỗ
                      </p>
                    </div>
                    <span className="text-2xl">&#x1F4C8;</span>
                  </div>
                </div>

                {/* Margin */}
                <div className="glass-card p-5 border-l-2" style={{ borderLeftColor: summary.margin >= 50 ? '#10B981' : summary.margin >= 20 ? '#F59E0B' : '#EF4444' }}>
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Biên lợi nhuận</p>
                      <p
                        className="text-2xl font-bold"
                        style={{ color: summary.margin >= 50 ? '#10B981' : summary.margin >= 20 ? '#F59E0B' : '#EF4444' }}
                      >
                        {(summary.margin ?? 0).toFixed(1)}%
                      </p>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">TB toàn công ty</p>
                    </div>
                    <span className="text-2xl">&#x1F3AF;</span>
                  </div>
                </div>
              </div>
            )}

            {/* ── Visual Summary Bar ── */}
            {summary && (
              <div className="glass-card p-5">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Cơ cấu Thu - Chi</h3>
                <div className="h-8 rounded-full overflow-hidden flex" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <div
                    className="h-full transition-all duration-1000 rounded-l-full"
                    style={{
                      width: `${Math.min(100, (summary.total_costs / summary.total_revenue) * 100)}%`,
                      background: 'linear-gradient(90deg, rgba(239,68,68,0.4), rgba(239,68,68,0.2))',
                    }}
                  />
                </div>
                <div className="flex justify-between mt-2">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(16,185,129,0.4)' }} />
                    <span className="text-xs text-[var(--text-secondary)]">
                      Doanh thu: {formatCurrency(summary.total_revenue)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(239,68,68,0.4)' }} />
                    <span className="text-xs text-[var(--text-secondary)]">
                      Chi phí: {formatCurrency(summary.total_costs)} ({((summary.total_costs / summary.total_revenue) * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(59,130,246,0.4)' }} />
                    <span className="text-xs text-[var(--text-secondary)]">
                      Lợi nhuận: {formatCurrency(summary.net_profit)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* ── Per-Project P&L ── */}
            <div className="glass-card overflow-hidden">
              <div className="p-5 pb-0">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">Lợi nhuận theo Dự án</h3>
              </div>
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                      <th className="text-left p-3 text-xs text-[var(--text-muted)]">Dự án</th>
                      <th className="text-left p-3 text-xs text-[var(--text-muted)]">Trạng thái</th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('revenue')}
                      >
                        Doanh thu <SortIcon field="revenue" />
                      </th>
                      <th className="text-right p-3 text-xs text-[var(--text-muted)]">Chi phí</th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('profit')}
                      >
                        Lợi nhuận <SortIcon field="profit" />
                      </th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('margin')}
                      >
                        Margin <SortIcon field="margin" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedProjects.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center p-8 text-[var(--text-muted)]">Chưa có dữ liệu dự án</td>
                      </tr>
                    ) : sortedProjects.map((p) => (
                      <tr
                        key={p.project_id}
                        className="border-b hover:bg-white/[0.03] transition-colors"
                        style={{ borderColor: 'var(--border-subtle)' }}
                      >
                        <td className="p-3">
                          <div>
                            <span className="font-mono text-xs text-[var(--gold-400)]">{p.project_code}</span>
                            <p className="text-sm font-medium mt-0.5">{p.project_name}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <StatusBadge status={p.status} margin={p.margin} />
                        </td>
                        <td className="p-3 text-right font-semibold text-emerald-400">
                          {formatCurrency(p.revenue)}
                        </td>
                        <td className="p-3 text-right text-red-400">
                          {formatCurrency(p.costs)}
                        </td>
                        <td className={cn('p-3 text-right font-bold', p.profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {p.profit >= 0 ? '+' : ''}{formatCurrency(p.profit)}
                        </td>
                        <td className="p-3 text-right">
                          <span
                            className={cn(
                              'text-xs font-bold px-2 py-1 rounded-lg',
                              p.margin >= 50 ? 'bg-emerald-500/15 text-emerald-400' :
                              p.margin >= 20 ? 'bg-amber-500/15 text-amber-400' :
                              'bg-red-500/15 text-red-400'
                            )}
                          >
                            {p.margin >= 0 ? '+' : ''}{p.margin.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {/* Totals row */}
                  {sortedProjects.length > 0 && (
                    <tfoot>
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3"></td>
                        <td className="p-3 text-right text-emerald-400">
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.revenue, 0))}
                        </td>
                        <td className="p-3 text-right text-red-400">
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.costs, 0))}
                        </td>
                        <td className={cn('p-3 text-right', sortedProjects.reduce((s, p) => s + p.profit, 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.profit, 0))}
                        </td>
                        <td className="p-3 text-right">
                          <span className="text-xs font-bold px-2 py-1 rounded-lg bg-[#C9A96E]/15 text-[#C9A96E]">
                            {(() => {
                              const totalRev = sortedProjects.reduce((s, p) => s + p.revenue, 0);
                              const totalCost = sortedProjects.reduce((s, p) => s + p.costs, 0);
                              return totalRev > 0 ? ((totalRev - totalCost) / totalRev * 100).toFixed(1) : '0.0';
                            })()}%
                          </span>
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>

            {/* ── Mobile Cards (visible below lg) ── */}
            <div className="lg:hidden space-y-3">
              {sortedProjects.map((p) => (
                <div key={p.project_id} className="glass-card p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <span className="font-mono text-xs text-[var(--gold-400)]">{p.project_code}</span>
                      <p className="text-sm font-medium mt-0.5">{p.project_name}</p>
                    </div>
                    <StatusBadge status={p.status} margin={p.margin} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Doanh thu</p>
                      <p className="text-sm font-semibold text-emerald-400">{formatCurrency(p.revenue)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Chi phí</p>
                      <p className="text-sm text-red-400">{formatCurrency(p.costs)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Lợi nhuận</p>
                      <p className={cn('text-sm font-bold', p.profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {p.profit >= 0 ? '+' : ''}{formatCurrency(p.profit)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Margin</p>
                      <span
                        className={cn(
                          'text-xs font-bold px-2 py-0.5 rounded',
                          p.margin >= 50 ? 'bg-emerald-500/15 text-emerald-400' :
                          p.margin >= 20 ? 'bg-amber-500/15 text-amber-400' :
                          'bg-red-500/15 text-red-400'
                        )}
                      >
                        {p.margin >= 0 ? '+' : ''}{p.margin.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Sidebar>
  );
}

// ── Status Badge Component ─────────────────────────────────
function StatusBadge({ status, margin }: { status: string; margin: number }) {
  // Use margin for color, status for label
  if (margin < 0) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-red-500/15 text-red-400">
        Lỗ
      </span>
    );
  }
  if (margin < 30) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-500/15 text-amber-400">
        Margin thấp
      </span>
    );
  }
  if (status === 'completed') {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">
        Hoàn thành
      </span>
    );
  }
  if (status === 'at_risk') {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-red-500/15 text-red-400">
        Rủi ro
      </span>
    );
  }
  return (
    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
      Đang chạy
    </span>
  );
}
