'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, AccountingSummary, DashboardData, Project } from '@/lib/api';
import { formatCurrency, STAGE_CONFIG } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';

// Spec 07 A3 — role → phòng ban nhận việc theo giai đoạn dự án
const ROLE_DEPT: Record<string, 'DESIGN' | 'PM' | 'PURCHASING'> = {
  supervisor: 'DESIGN',
};

type DeptProject = Project & { pending_tasks: number; days_left: number | null };

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [acctSummary, setAcctSummary] = useState<AccountingSummary | null>(null);
  const [deptProjects, setDeptProjects] = useState<DeptProject[]>([]);
  const [leaderCounts, setLeaderCounts] = useState<{ approvals: number; ot: number } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      const fetchFn = user.role === 'executive' || user.role === 'admin'
        ? api.getExecutiveDashboard()
        : api.getPersonalDashboard();
      fetchFn
        .then(setData)
        .catch((e) => setError(e.message));

      // Kế toán: thẻ Tổng Thu/Tổng Chi lấy từ sổ kế toán thật (không dùng pipeline_value)
      if (user.role === 'accountant') {
        api.getAccountingSummary().then(setAcctSummary).catch(() => setAcctSummary(null));
      }

      const dept = ROLE_DEPT[user.role];
      if (dept) {
        api.getProjectsByDepartment(dept, 5)
          .then(res => setDeptProjects(res?.items || []))
          .catch(() => setDeptProjects([]));
      }

      // Khối điều hành nhanh cho leader (spec 08 §2.4)
      if (user.role === 'leader' || user.role === 'admin') {
        Promise.all([api.approvalsPendingForMe(), api.pendingOT()])
          .then(([approvals, ot]) => setLeaderCounts({ approvals: approvals.count, ot: ot.items.length }))
          .catch(() => setLeaderCounts(null));
      }
    }
  }, [user]);

  if (loading) return (
    <Sidebar>
      <div className="p-6 space-y-6">
        <div className="skeleton h-8 w-64 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => (
            <div key={i} className="glass-card p-5">
              <div className="skeleton h-3 w-24 mb-3 rounded" />
              <div className="skeleton h-7 w-32 mb-2 rounded" />
              <div className="skeleton h-3 w-20 rounded" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card p-6"><div className="skeleton h-48 w-full rounded-xl" /></div>
          <div className="glass-card p-6"><div className="skeleton h-48 w-full rounded-xl" /></div>
        </div>
      </div>
    </Sidebar>
  );
  if (!user) return null;
  if (!data && !error) return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="inline-block w-8 h-8 rounded-full border-2 border-[var(--gold-400)] border-t-transparent animate-spin mb-3" />
          <p className="text-sm text-[var(--text-muted)]">Đang tải dữ liệu...</p>
        </div>
      </div>
    </Sidebar>
  );

  const perms = getPermissions(user.role as UserRole);
  const isFinancial = perms.dashboardType === 'financial';
  const isPersonal = perms.dashboardType === 'personal';
  const isExecRole = user.role === 'executive';

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              Xin chào, <span className="gold-gradient">{user.full_name}</span>
            </h1>
            <p className="text-[var(--text-secondary)] text-sm mt-1">
              {new Date().toLocaleDateString('vi-VN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm">
            ⚠️ Chưa kết nối API backend: {error}. Đang hiển thị demo data.
          </div>
        )}

        {/* KPI Cards — role-based */}
        {isExecRole ? (
          /* Executive: Financial KPI Cards — wired to API data */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Giá trị pipeline"
              value={formatCurrency(data?.pipeline_value)}
              subtitle={`${data?.conversion_rate ?? 0}% chuyển đổi`}
              icon="📈"
              color="var(--gold-500)"
            />
            <KPICard
              title="Tổng Lead"
              value={data?.total_leads ?? '—'}
              subtitle={`Tháng này: ${data?.total_leads_month ?? 0}`}
              icon="👥"
              color="#C9A96E"
              onClick={() => router.push('/leads')}
            />
            <KPICard
              title="Dự án Đang chạy"
              value={data?.active_projects ?? '—'}
              subtitle={`Tiến độ TB: ${data?.avg_project_progress ?? 0}%`}
              icon="🏗️"
              color="var(--stage-new)"
              onClick={() => router.push('/projects')}
            />
            <KPICard
              title="Hợp đồng"
              value={data?.total_contracts ?? '—'}
              subtitle={formatCurrency(data?.total_contract_value)}
              icon="📄"
              color="var(--stage-interested)"
              onClick={() => router.push('/contracts')}
            />
          </div>
        ) : isFinancial ? (
          /* Accountant: Financial summary cards */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Tổng Thu"
              value={acctSummary ? formatCurrency(acctSummary.total_income) : '—'}
              subtitle="Doanh thu kỳ này (sổ kế toán)"
              icon="💵"
              color="var(--stage-potential)"
              onClick={() => router.push('/accounting')}
            />
            <KPICard
              title="Tổng Chi"
              value={acctSummary ? formatCurrency(acctSummary.total_expense) : '—'}
              subtitle={acctSummary ? `Lãi ròng: ${formatCurrency(acctSummary.net)}` : 'Chi phí & lương'}
              icon="💸"
              color="#EF4444"
              onClick={() => router.push('/accounting')}
            />
            <KPICard
              title="Dự án Đang chạy"
              value={data?.active_projects ?? 0}
              subtitle={`Tiến độ TB: ${data?.avg_project_progress ?? 0}%`}
              icon="🏗️"
              color="#C9A96E"
              onClick={() => router.push('/projects')}
            />
            <KPICard
              title="Hợp đồng"
              value={data?.total_contracts ?? 0}
              subtitle={data?.total_contract_value ? formatCurrency(data.total_contract_value) : '—'}
              icon="📄"
              color="var(--stage-interested)"
              onClick={() => router.push('/contracts')}
            />
          </div>
        ) : isPersonal ? (
          /* Sales: Personal KPIs */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Lead Của Tôi"
              value={data?.total_active_leads ?? data?.total_leads ?? 0}
              subtitle="lead đang xử lý"
              icon="👥"
              color="var(--stage-new)"
              onClick={() => router.push('/leads')}
            />
            <KPICard
              title="Giá trị pipeline"
              value={data?.pipeline_value ? formatCurrency(data.pipeline_value) : '—'}
              subtitle={`${data?.conversion_rate ?? 0}% chuyển đổi`}
              icon="💰"
              color="#C9A96E"
              onClick={() => router.push('/leads')}
            />
            <KPICard
              title="Hợp đồng"
              value={data?.total_contracts ?? 0}
              subtitle={data?.total_contract_value ? formatCurrency(data.total_contract_value) : '—'}
              icon="📄"
              color="var(--stage-interested)"
              onClick={() => router.push('/contracts')}
            />
            <KPICard
              title="Hoa Hồng"
              value={data?.commission_month != null ? formatCurrency(data.commission_month) : '—'}
              subtitle="đã duyệt kỳ gần nhất"
              icon="💎"
              color="var(--stage-potential)"
              onClick={() => router.push('/accounting')}
            />
          </div>
        ) : (
          /* Admin/Leader: Executive KPIs */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Tổng Lead"
              value={data?.total_leads ?? 0}
              subtitle={`Tháng này: ${data?.total_leads_month ?? 0}`}
              icon="👥"
              color="var(--stage-new)"
              onClick={() => router.push('/leads')}
            />
            <KPICard
              title="Giá trị pipeline"
              value={formatCurrency(data?.pipeline_value)}
              subtitle={`${data?.conversion_rate ?? 0}% chuyển đổi`}
              icon="💰"
              color="#C9A96E"
              onClick={() => router.push('/leads')}
            />
            <KPICard
              title="Dự án Đang chạy"
              value={data?.active_projects ?? 0}
              subtitle={`Tiến độ TB: ${data?.avg_project_progress ?? 0}%`}
              icon="🏗️"
              color="var(--stage-potential)"
              onClick={() => router.push('/projects')}
            />
            <KPICard
              title="Hợp đồng"
              value={data?.total_contracts ?? 0}
              subtitle={formatCurrency(data?.total_contract_value)}
              icon="📄"
              color="var(--stage-interested)"
              onClick={() => router.push('/contracts')}
            />
          </div>
        )}

        {/* Pipeline Funnel + Team Performance (admin/leader only) */}
        {!isFinancial && !isPersonal && !isExecRole && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Pipeline Funnel */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">📊 Phễu quy trình</h2>
              <div className="space-y-3">
                {['new', 'interested', 'survey_scheduled', 'potential', 'signed_design'].map((stage) => {
                  const config = STAGE_CONFIG[stage];
                  const count = data?.stage_funnel?.[stage] ?? 0;
                  const maxCount = 20;
                  const pct = Math.min((count / maxCount) * 100, 100);
                  return (
                    <div key={stage} className="flex items-center gap-3 cursor-pointer hover:bg-white/5 rounded-lg px-1 py-0.5 transition-colors" onClick={() => router.push(`/leads?stage=${stage}`)}>
                      <span className="text-lg w-6">{config.emoji}</span>
                      <span className="text-sm w-32 text-[var(--text-secondary)]">{config.label}</span>
                      <div className="flex-1 h-6 rounded-full bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${pct}%`, backgroundColor: config.color }}
                        />
                      </div>
                      <span className="text-sm font-semibold w-8 text-right">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Team Performance */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">🏆 Hiệu suất Đội</h2>
              <div className="space-y-3">
                {(data?.team_performance ?? []).map((team: { team: string; total_leads: number; signed: number; conversion: number }, i: number) => (
                  <div key={i} className="flex items-center gap-4 p-3 rounded-xl bg-white/5 hover:bg-white/8 transition-colors">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-semibold" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{team.team}</p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {team.total_leads} lead · {team.signed} ký
                      </p>
                    </div>
                    <div className="text-right">
                      {/* 0% = chưa có số liệu, hiển thị trung tính — không phải lỗi để tô đỏ */}
                      <span
                        className="text-sm font-bold"
                        style={{ color: team.conversion > 0 ? 'var(--gold-500)' : 'var(--text-disabled)' }}
                      >
                        {team.conversion}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Personal: Today's Tasks */}
        {/* Spec 08 §2.4 — Điều hành nhanh cho leader/admin: 3 số + đi thẳng */}
        {leaderCounts && (leaderCounts.approvals > 0 || leaderCounts.ot > 0 || (data?.overdue_leads ?? 0) > 0) && (
          <div className="glass-card p-5">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-3">⚡ Cần xử lý ngay</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Vạch màu trái thay nền pastel nhiều màu (góp ý UI Designer A6) — màu ngữ nghĩa qua stage vars để hợp cả 2 theme */}
              <button onClick={() => router.push('/leads')}
                className="flex items-center justify-between p-3 rounded-xl transition-all hover:opacity-80 text-left min-h-[56px]"
                style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)', borderLeft: '3px solid var(--stage-lost)' }}>
                <span className="text-sm text-[var(--text-secondary)]">Khách quá hạn</span>
                <span className="text-xl font-bold" style={{ color: 'var(--stage-lost)' }}>{data?.overdue_leads ?? 0}</span>
              </button>
              <button onClick={() => router.push('/approvals')}
                className="flex items-center justify-between p-3 rounded-xl transition-all hover:opacity-80 text-left min-h-[56px]"
                style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)', borderLeft: '3px solid var(--stage-survey)' }}>
                <span className="text-sm text-[var(--text-secondary)]">Đơn chờ duyệt</span>
                <span className="text-xl font-bold" style={{ color: 'var(--stage-survey)' }}>{leaderCounts.approvals}</span>
              </button>
              <button onClick={() => router.push('/attendance')}
                className="flex items-center justify-between p-3 rounded-xl transition-all hover:opacity-80 text-left min-h-[56px]"
                style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)', borderLeft: '3px solid var(--stage-dormant)' }}>
                <span className="text-sm text-[var(--text-secondary)]">Tăng ca chờ</span>
                <span className="text-xl font-bold" style={{ color: 'var(--stage-dormant)' }}>{leaderCounts.ot}</span>
              </button>
            </div>
          </div>
        )}

        {/* Spec 07 A3 — Dự án đang đến phòng bạn (designer/pm/purchasing) */}
        {ROLE_DEPT[user.role] && deptProjects.length > 0 && (
          <div className="glass-card p-5">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-3">
              🏗️ Dự án đang đến phòng bạn
              <span className="ml-2 text-[10px] font-normal text-[var(--text-muted)]">ưu tiên: quá hạn → cận hạn → hợp đồng lớn</span>
            </h3>
            <div className="space-y-2">
              {deptProjects.map(p => (
                <div
                  key={p.id}
                  className="flex items-center gap-3 p-2.5 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors"
                  onClick={() => router.push('/projects')}
                >
                  <span className="text-[10px] font-mono text-[var(--text-muted)] flex-shrink-0">{p.code}</span>
                  <span className="flex-1 text-sm text-[var(--text-primary)] truncate">{p.name}</span>
                  <span className="text-[10px] text-[var(--text-muted)] flex-shrink-0">{p.pending_tasks} việc chờ</span>
                  {p.days_left !== null && p.days_left < 0 && (
                    <span className="text-[10px] font-bold text-red-400 flex-shrink-0">🔴 Quá hạn {-p.days_left}d</span>
                  )}
                  {p.days_left !== null && p.days_left >= 0 && p.days_left <= 14 && (
                    <span className="text-[10px] font-bold text-orange-400 flex-shrink-0">🟠 Còn {p.days_left}d</span>
                  )}
                  <span className="text-[10px] font-semibold text-white flex-shrink-0">{formatCurrency(p.total_value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {isPersonal && (
          <div className="glass-card p-5">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-3">📋 Việc cần làm hôm nay</h3>
            <div className="space-y-2">
              {/* Dynamic priorities from API */}
              {(data as Record<string, unknown>)?.priorities && Array.isArray((data as Record<string, unknown>).priorities) && ((data as Record<string, unknown>).priorities as Array<Record<string, string>>).length > 0 ? (
                ((data as Record<string, unknown>).priorities as Array<Record<string, string>>).map((item: Record<string, string>, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-white/5 hover:bg-white/8 cursor-pointer transition-colors"
                    onClick={() => item.href && router.push(item.href)}>
                    <span>{item.icon}</span>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-[var(--text-primary)] block truncate">{item.title}</span>
                      <span className="text-[10px] text-[var(--text-muted)] block truncate">{item.subtitle}</span>
                    </div>
                  </div>
                ))
              ) : (
                <>
                  {(data?.overdue_leads ?? 0) > 0 && (
                    <div className="flex items-center gap-3 p-2 rounded-lg bg-red-500/10">
                      <span className="text-red-400">⚠️</span>
                      <span className="text-sm text-red-400">{data?.overdue_leads ?? 0} leads quá hạn cần follow-up</span>
                    </div>
                  )}
                  <div className="flex items-center gap-3 p-2 rounded-lg bg-blue-500/10">
                    <span className="text-blue-400">🆕</span>
                    <span className="text-sm text-blue-400">Quy trình: {data?.total_leads ?? 0} leads đang quản lý</span>
                  </div>
                  <div className="flex items-center gap-3 p-2 rounded-lg bg-emerald-500/10">
                    <span className="text-emerald-400">💰</span>
                    <span className="text-sm text-emerald-400">Giá trị pipeline: {formatCurrency(data?.pipeline_value)}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Personal: Quick Actions */}
        {isPersonal && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">⚡ Hành động nhanh</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => router.push('/leads')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">🔄</span>
                <p className="text-sm font-medium mt-2">Xem quy trình</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Quản lý leads của bạn</p>
              </button>
              <button
                onClick={() => router.push('/contracts')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">📄</span>
                <p className="text-sm font-medium mt-2">Hợp đồng</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Xem hợp đồng đã ký</p>
              </button>
              <button
                onClick={() => router.push('/accounting')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">💰</span>
                <p className="text-sm font-medium mt-2">Hoa Hồng</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Xem hoa hồng của bạn</p>
              </button>
            </div>
          </div>
        )}

        {/* Financial: Financial Summary */}
        {isFinancial && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">📊 Tổng quan Tài chính</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => router.push('/accounting')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">💳</span>
                <p className="text-sm font-medium mt-2">Giao dịch</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Quản lý thu chi chi tiết</p>
              </button>
              <button
                onClick={() => router.push('/accounting')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">📋</span>
                <p className="text-sm font-medium mt-2">Bảng lương</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Quản lý lương & hoa hồng</p>
              </button>
              <button
                onClick={() => router.push('/hr')}
                className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <span className="text-2xl">👥</span>
                <p className="text-sm font-medium mt-2">Nhân sự</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Quản lý người dùng</p>
              </button>
            </div>
          </div>
        )}

        {/* SLA Alerts (admin/leader only) */}
        {!isFinancial && !isPersonal && !isExecRole && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-3">⚠️ Cảnh báo</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <AlertCard
                count={data?.overdue_leads ?? 4}
                label="Lead quá hạn liên hệ"
                color="#EF4444"
                onClick={() => router.push('/leads?filter=overdue')}
              />
              <AlertCard
                count={data?.stage_funnel?.['lost'] ?? 0}
                label="Lead mất trong tháng"
                color="#F59E0B"
                onClick={() => router.push('/leads?stage=lost')}
              />
              <AlertCard
                count={0}
                label="Việc quá hạn"
                color="var(--stage-new)"
                onClick={() => router.push('/projects')}
              />
            </div>
          </div>
        )}

        {/* Executive: Financial Analytics + Growth Metrics */}
        {isExecRole && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Financial Analytics */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">📊 Phân tích Tài chính</h2>
              <div className="space-y-3">
                {(() => {
                  const fs = data?.financial_summary;
                  const rev = fs?.total_revenue_ytd || 1;
                  return [
                    { label: 'Doanh thu lũy kế năm', value: formatCurrency(fs?.total_revenue_ytd), color: 'var(--stage-potential)', pct: 100 },
                    { label: 'Chi phí lũy kế năm', value: formatCurrency(fs?.total_cost_ytd), color: '#EF4444', pct: Math.round(((fs?.total_cost_ytd || 0) / rev) * 100) },
                    { label: 'Lợi nhuận ròng', value: formatCurrency(fs?.net_profit_ytd), color: 'var(--stage-new)', pct: Math.round(((fs?.net_profit_ytd || 0) / rev) * 100) },
                    { label: 'Dòng tiền', value: formatCurrency(fs?.cash_flow), color: '#C9A96E', pct: Math.round(((fs?.cash_flow || 0) / rev) * 100) },
                    { label: 'Phải thu', value: formatCurrency(fs?.outstanding_receivable), color: '#F59E0B', pct: Math.round(((fs?.outstanding_receivable || 0) / rev) * 100) },
                  ];
                })().map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-sm text-[var(--text-secondary)]">{item.label}</span>
                        <span className="text-sm font-semibold" style={{ color: item.color }}>{item.value}</span>
                      </div>
                      <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${item.pct}%`, backgroundColor: item.color }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Growth Metrics */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">🚀 Chỉ số Tăng trưởng</h2>
              <div className="space-y-3">
                {(() => {
                  const gm = data?.growth_metrics;
                  return [
                    { label: 'Tăng trưởng lead', value: gm ? `+${gm.lead_growth_rate}%` : '—', icon: '📈', color: 'var(--stage-potential)' },
                    { label: 'Cải thiện tỷ lệ chốt', value: gm ? `+${gm.conversion_improvement}%` : '—', icon: '🎯', color: 'var(--stage-new)' },
                    { label: 'Giá trị deal trung bình', value: formatCurrency(gm?.avg_deal_size), icon: '💎', color: '#C9A96E' },
                    { label: 'Chi phí thu hút KH', value: formatCurrency(gm?.customer_acquisition_cost), icon: '📢', color: '#F59E0B' },
                    { label: 'Giá trị vòng đời KH', value: formatCurrency(gm?.customer_lifetime_value), icon: '♻️', color: 'var(--stage-interested)' },
                  ];
                })().map((item, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/8 transition-colors">
                    <span className="text-xl">{item.icon}</span>
                    <span className="flex-1 text-sm text-[var(--text-secondary)]">{item.label}</span>
                    <span className="text-sm font-bold" style={{ color: item.color }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Executive: Risk Analysis + Forecast */}
        {isExecRole && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Hedging */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">🛡️ Phân tích Rủi ro</h2>
              <div className="space-y-3">
                {(() => {
                  const rh = data?.risk_hedging;
                  const riskLabel = rh?.concentration_risk === 'high' ? 'Cao' : rh?.concentration_risk === 'low' ? 'Thấp' : 'Trung bình';
                  return [
                    { label: 'Rủi ro tập trung KH', value: rh ? riskLabel : '—', detail: rh ? `KH lớn nhất chiếm ${rh.top_client_pct}%` : '', color: '#F59E0B', icon: '⚠️' },
                    { label: 'Độ phủ pipeline', value: rh ? `${rh.pipeline_coverage}x` : '—', detail: 'Mục tiêu: 3.0x', color: 'var(--stage-new)', icon: '📊' },
                    { label: 'Dự trữ tiền mặt', value: rh ? `${rh.cash_reserve_months} tháng` : '—', detail: 'Mục tiêu: 6 tháng', color: '#C9A96E', icon: '🏦' },
                    { label: 'Phải thu quá hạn', value: rh ? `${rh.overdue_receivable_pct}%` : '—', detail: 'Cần theo dõi', color: '#EF4444', icon: '⏰' },
                  ];
                })().map((item, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/8 transition-colors">
                    <span className="text-xl">{item.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[var(--text-secondary)]">{item.label}</p>
                      <p className="text-xs text-[var(--text-muted)]">{item.detail}</p>
                    </div>
                    <span className="text-sm font-bold" style={{ color: item.color }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Annual Forecast */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">🔮 Dự báo Doanh thu</h2>
              <div className="space-y-4">
                {(() => {
                  const fc = data?.forecast;
                  const toBil = (v?: number) => Math.round((v || 0) / 1_000_000_000);
                  const max = Math.max(toBil(fc?.full_year_2026), 1);
                  return [
                    { label: 'Q3/2026', value: toBil(fc?.q3_2026), max, color: 'var(--stage-potential)' },
                    { label: 'Q4/2026', value: toBil(fc?.q4_2026), max, color: 'var(--stage-new)' },
                    { label: 'Cả năm 2026', value: toBil(fc?.full_year_2026), max, color: '#C9A96E' },
                    { label: 'Cả năm 2025', value: toBil(fc?.full_year_2025), max, color: 'var(--stage-interested)' },
                  ];
                })().map((item, i) => (
                  <div key={i}>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm text-[var(--text-secondary)]">{item.label}</span>
                      <span className="text-sm font-bold" style={{ color: item.color }}>{item.value.toLocaleString('vi-VN')} tỷ</span>
                    </div>
                    <div className="h-3 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-1000"
                        style={{ width: `${(item.value / item.max) * 100}%`, backgroundColor: item.color }}
                      />
                    </div>
                  </div>
                ))}
                <div className="mt-4 p-3 rounded-xl bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.2)]">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📈</span>
                    <div>
                      <p className="text-sm font-semibold text-[#10B981]">Tăng trưởng: +{data?.financial_summary?.yoy_growth ?? '—'}%</p>
                      <p className="text-xs text-[var(--text-muted)]">So với năm 2025 — xu hướng tích cực</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}

function KPICard({ title, value, subtitle, icon, color, onClick }: {
  title: string;
  value: string | number;
  subtitle: string;
  icon: string;
  color: string;
  onClick?: () => void;
}) {
  return (
    <div
      className="stat-card glass-card p-5 cursor-pointer transition-all hover:scale-[1.02]"
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      aria-label={`${title}: ${value}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold mt-1" style={{ color }}>{value}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{subtitle}</p>
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
      <p className="text-[10px] text-[var(--text-disabled)] mt-2 flex items-center gap-1">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
        Xem chi tiết
      </p>
    </div>
  );
}

function AlertCard({ count, label, color, onClick }: { count: number; label: string; color: string; onClick?: () => void }) {
  return (
    <div
      className="flex items-center gap-3 p-3 rounded-xl bg-white/5 cursor-pointer transition-all hover:bg-white/8 hover:scale-[1.01]"
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      aria-label={`${count} ${label}`}
    >
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold text-white"
        style={{ backgroundColor: `${color}20` }}
      >
        <span style={{ color }}>{count}</span>
      </div>
      <div className="flex-1">
        <p className="text-sm text-[var(--text-secondary)]">{label}</p>
      </div>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
    </div>
  );
}
