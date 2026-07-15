'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, DashboardExecutive, AccountingSummary } from '@/lib/api';
import { formatCurrency, STAGE_CONFIG } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';
import AccessDenied from '@/components/ui/AccessDenied';

export default function ReportsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<DashboardExecutive | null>(null);
  const [summary, setSummary] = useState<AccountingSummary | null>(null);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      Promise.all([
        api.getExecutiveDashboard().catch(() => null),
        api.getAccountingSummary().catch(() => null),
      ]).then(([d, s]) => {
        setDashboard(d);
        setSummary(s);
      }).finally(() => setLoadingData(false));
    }
  }, [user]);

  if (loading) return null;
  if (!user) return null;

  const perms = getPermissions(user.role as UserRole);
  if (!perms.canViewReports) return <AccessDenied />;

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <h1 className="text-2xl font-bold mb-6">📈 Báo cáo</h1>

        {loadingData ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            Đang tải...
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Revenue Summary */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">Doanh thu</h2>
              {summary ? (
                <>
                  <div className="text-3xl font-bold gold-gradient">{formatCurrency(summary.total_income)}</div>
                  <p className="text-sm text-[var(--text-secondary)] mt-1">
                    Chi phí: {formatCurrency(summary.total_expense)} · Lợi nhuận: {formatCurrency(summary.net)}
                  </p>
                  {summary.by_category.length > 0 && (
                    <div className="mt-4 space-y-2">
                      {summary.by_category.filter(c => c.type === 'income').map((item, i) => {
                        const pct = summary.total_income > 0 ? (item.total / summary.total_income) * 100 : 0;
                        return (
                          <div key={i} className="flex items-center gap-3">
                            <span className="text-xs w-20 text-[var(--text-muted)] truncate">{item.category}</span>
                            <div className="flex-1 h-2 rounded-full bg-white/10">
                              <div className="h-full rounded-full bg-[#C9A96E]" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-xs font-medium w-16 text-right">{formatCurrency(item.total)}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Không có dữ liệu</p>
              )}
            </div>

            {/* Conversion Funnel */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">Phễu quy trình</h2>
              {dashboard ? (
                <>
                  <div className="flex items-center gap-4 mb-4">
                    <div className="relative w-24 h-24">
                      <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
                        <circle cx="48" cy="48" r="40" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="6" />
                        <circle
                          cx="48" cy="48" r="40" fill="none"
                          stroke="#C9A96E"
                          strokeWidth="6"
                          strokeDasharray={`${dashboard.conversion_rate * 2.51} 251`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold">{dashboard.conversion_rate.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm text-[var(--text-secondary)]">Tỷ lệ chuyển đổi</p>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        {dashboard.total_contracts} HĐ / {dashboard.total_leads} leads
                      </p>
                    </div>
                  </div>
                  {/* Stage funnel */}
                  {dashboard.stage_funnel && (
                    <div className="space-y-1.5">
                      {Object.entries(dashboard.stage_funnel).map(([stage, count]) => {
                        const config = STAGE_CONFIG[stage];
                        const maxCount = Math.max(...Object.values(dashboard.stage_funnel));
                        const width = maxCount > 0 ? (count / maxCount) * 100 : 0;
                        return (
                          <div key={stage} className="flex items-center gap-2">
                            <span className="text-[10px] w-24 text-[var(--text-muted)] truncate">{config?.label || stage}</span>
                            <div className="flex-1 h-2 rounded-full bg-white/10">
                              <div className="h-full rounded-full" style={{ width: `${width}%`, backgroundColor: config?.color || '#6B7280' }} />
                            </div>
                            <span className="text-[10px] font-medium w-6 text-right">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Không có dữ liệu</p>
              )}
            </div>

            {/* Team Performance */}
            <div className="glass-card p-6 md:col-span-2">
              <h2 className="text-lg font-semibold mb-4">Hiệu suất đội nhóm</h2>
              {dashboard?.team_performance && dashboard.team_performance.length > 0 ? (
                <>
                  {/* Mobile card view */}
                  <div className="md:hidden space-y-3">
                    {dashboard.team_performance.map((team, i) => (
                      <div key={i} className="p-3 rounded-xl flex justify-between items-center" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                        <div>
                          <p className="font-medium text-sm">{team.team}</p>
                          <p className="text-xs text-[var(--text-muted)] mt-0.5">Chuyển đổi: {team.conversion.toFixed(1)}%</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-mono">{team.total_leads} leads</p>
                          <p className="text-xs text-[#C9A96E] font-semibold">{team.signed} ký HĐ</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Desktop table view */}
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                          <th className="text-left p-2 text-xs text-[var(--text-muted)]">Đội</th>
                          <th className="text-right p-2 text-xs text-[var(--text-muted)]">Leads</th>
                          <th className="text-right p-2 text-xs text-[var(--text-muted)]">Ký HĐ</th>
                          <th className="text-right p-2 text-xs text-[var(--text-muted)]">Chuyển đổi</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.team_performance.map((team, i) => (
                          <tr key={i} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                            <td className="p-2 font-medium">{team.team}</td>
                            <td className="p-2 text-right">{team.total_leads}</td>
                            <td className="p-2 text-right text-[#C9A96E]">{team.signed}</td>
                            <td className="p-2 text-right">{team.conversion.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Chưa có dữ liệu đội nhóm</p>
              )}
            </div>

            {/* KPI Summary */}
            <div className="glass-card p-6 md:col-span-2">
              <h2 className="text-lg font-semibold mb-4">KPI tổng hợp</h2>
              {dashboard ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: 'Tổng leads', value: dashboard.total_leads, color: '#3B82F6' },
                    { label: 'Leads tháng này', value: dashboard.total_leads_month, color: '#8B5CF6' },
                    { label: 'Dự án active', value: dashboard.active_projects, color: '#10B981' },
                    { label: 'Giá trị pipeline', value: formatCurrency(dashboard.pipeline_value), color: '#C9A96E' },
                    { label: 'SLA Compliance', value: `${dashboard.sla_compliance?.toFixed(0) || 0}%`, color: '#10B981' },
                    { label: 'Leads quá hạn', value: dashboard.overdue_leads, color: '#EF4444' },
                    { label: 'HĐ ký', value: dashboard.total_contracts, color: '#C9A96E' },
                    { label: 'Giá trị HĐ', value: formatCurrency(dashboard.total_contract_value), color: '#10B981' },
                  ].map((kpi, i) => (
                    <div key={i} className="p-3 rounded-lg text-center border-l-2" style={{ background: 'var(--surface-2)', borderLeftColor: kpi.color }}>
                      <p className="text-xs text-[var(--text-muted)]">{kpi.label}</p>
                      <p className="text-lg font-bold mt-1" style={{ color: kpi.color }}>{kpi.value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Không có dữ liệu</p>
              )}
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
