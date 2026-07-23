'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { UserRole, getRoleLabel, getRoleOverrides, loadRolePermissions, saveRolePermissions } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';

const ROLES: UserRole[] = ['admin', 'executive', 'leader', 'data_entry', 'supervisor', 'accountant'];

interface Feature {
  key: string;
  label: string;
  note?: string;
}

const FEATURES: Feature[] = [
  { key: 'canViewDashboard', label: 'Dashboard - Tổng quan' },
  { key: 'canViewKPI', label: 'KPI (Cá nhân)' },
  { key: 'canViewLeads', label: 'CRM - Quy trình' },
  { key: 'canViewApprovals', label: 'Phê duyệt' },
  { key: 'canViewProjects', label: 'Dự án' },
  { key: 'canViewAttendance', label: 'Chấm công' },
  { key: 'canViewLeads', label: 'Báo giá tức thì', note: '(quy trình)' },
  { key: '__skip__', label: 'Khách hàng' },
  { key: 'canViewContracts', label: 'Hợp đồng' },
  { key: 'canViewQuotations', label: 'Báo giá' },
  { key: 'canViewInventory', label: 'Kho vật tư' },
  { key: 'canViewInventory', label: 'Nhà cung cấp', note: '(kho)' },
  { key: 'canViewPnL', label: 'P&L' },
  { key: 'canViewAccounting', label: 'Kế toán' },
  { key: 'canViewHR', label: 'Nhân sự' },
  { key: 'canViewAccounting', label: 'Tài chính', note: '(kế toán)' },
  { key: 'canViewReports', label: 'Báo cáo' },
  { key: 'canViewFeedback', label: 'Góp ý' },
  { key: 'canManageUsers', label: 'Tài khoản' },
];

type PermissionMatrix = Partial<Record<UserRole, Record<string, boolean>>>;

// Hardcoded defaults (mirrors backend _ROLE_PERMISSION_DEFAULTS)
const DEFAULTS: Record<string, Record<string, boolean>> = {
  admin: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true, canViewHR: true, canManageUsers: true, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true, canViewReports: true, canViewPnL: true, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: true, canViewSettings: true },
  executive: { canViewDashboard: true, canViewLeads: false, canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: false, canCreateQuotations: false, canViewInventory: false, canViewReports: true, canViewPnL: true, canCreateProjects: true, canCreateContracts: false, canCreateTasks: false, canEditTasks: false, canViewAttendance: false, canViewKPI: true, canViewApprovals: false, canViewFeedback: true, canViewSettings: true },
  leader: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: true, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, canViewReports: true, canViewPnL: false, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false },
  data_entry: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, canViewReports: true, canViewPnL: false, canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false, canViewAttendance: true, canViewKPI: false, canViewApprovals: true, canViewFeedback: false, canViewSettings: false },
  supervisor: { canViewDashboard: true, canViewLeads: false, canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true, canViewReports: true, canViewPnL: false, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false },
  accountant: { canViewDashboard: true, canViewLeads: false, canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true, canViewHR: true, canManageUsers: true, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: false, canViewInventory: true, canViewReports: true, canViewPnL: true, canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false, canViewAttendance: true, canViewKPI: false, canViewApprovals: true, canViewFeedback: false, canViewSettings: false },
};

export default function PermissionsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [overrides, setOverrides] = useState<PermissionMatrix>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Redirect if not admin
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push('/');
    }
  }, [user, router]);

  // Load role permissions
  const loadPermissions = useCallback(async () => {
    setLoading(true);
    await loadRolePermissions();
    const ov = getRoleOverrides();
    // Convert Partial<RolePermissions> to Record<string, boolean> for local state
    const normalized: PermissionMatrix = {};
    for (const [role, perms] of Object.entries(ov)) {
      if (perms) {
        normalized[role as UserRole] = {};
        for (const [k, v] of Object.entries(perms)) {
          if (typeof v === 'boolean') {
            normalized[role as UserRole]![k] = v;
          }
        }
      }
    }
    setOverrides(normalized);
    setLoading(false);
    setHasChanges(false);
  }, []);

  useEffect(() => {
    if (user?.role === 'admin') {
      loadPermissions();
    }
  }, [user, loadPermissions]);

  // Check if a permission is on for a role (defaults + overrides)
  const isPermOn = (role: UserRole, key: string): boolean => {
    const override = overrides[role]?.[key];
    if (override !== undefined) return override;
    return DEFAULTS[role]?.[key] ?? false;
  };

  const handleToggle = (role: UserRole, featureKey: string) => {
    if (featureKey === '__skip__') return;
    const current = isPermOn(role, featureKey);
    const newOverrides = { ...overrides };
    if (!newOverrides[role]) newOverrides[role] = {};
    newOverrides[role]![featureKey] = !current;
    setOverrides(newOverrides);
    setHasChanges(true);
  };

  const handleSaveRole = async (role: UserRole) => {
    setSaving(role);
    try {
      const roleOverrides = overrides[role] || {};
      // Only send keys that differ from defaults
      const relevantOverrides: Record<string, boolean> = {};
      for (const f of FEATURES) {
        if (f.key === '__skip__') continue;
        if (roleOverrides[f.key] !== undefined) {
          relevantOverrides[f.key] = roleOverrides[f.key]!;
        }
      }
      await saveRolePermissions(role, relevantOverrides);
      toast(`Da luu phan quyen vai tro ${getRoleLabel(role)}`, 'success');
      setHasChanges(false);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Luu that bai', 'error');
    } finally {
      setSaving(null);
    }
  };

  const handleSaveAll = async () => {
    for (const role of ROLES) {
      await handleSaveRole(role);
    }
  };

  const handleResetRole = (role: UserRole) => {
    const newOverrides = { ...overrides };
    delete newOverrides[role];
    setOverrides(newOverrides);
    setHasChanges(true);
  };

  if (user?.role !== 'admin') {
    return (
      <Sidebar>
        <div className="p-8 text-center">
          <p className="text-[var(--text-muted)]">Chi admin moi co quyen truy cap trang nay.</p>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Phan quyen vai tro
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              Cau hinh quyen truy cap cho tung vai tro. Bat/tat quyen cho moi tinh nang.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadPermissions}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              style={{
                background: 'var(--surface-2)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-muted)',
              }}
            >
              Tai lai
            </button>
            {hasChanges && (
              <button
                onClick={handleSaveAll}
                className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
                style={{
                  background: 'linear-gradient(135deg, #C9A96E, #B8944F)',
                  color: '#000',
                }}
              >
                Luu tat ca thay doi
              </button>
            )}
          </div>
        </div>

        {/* Matrix Table */}
        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <div className="inline-block w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--text-muted)', borderTopColor: 'transparent' }} />
              <p className="text-sm mt-3" style={{ color: 'var(--text-muted)' }}>Dang tai du lieu...</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <th
                      className="text-left px-4 py-3 font-semibold sticky left-0 z-10"
                      style={{
                        background: 'var(--surface-1)',
                        color: 'var(--text-primary)',
                        minWidth: 180,
                      }}
                    >
                      Tinh nang
                    </th>
                    {ROLES.map(role => (
                      <th
                        key={role}
                        className="text-center px-3 py-3 font-semibold"
                        style={{ color: 'var(--text-primary)', minWidth: 100 }}
                      >
                        <div className="flex flex-fill items-center gap-1">
                          <span>{getRoleLabel(role)}</span>
                          <button
                            onClick={() => handleResetRole(role)}
                            className="text-[10px] px-2 py-0.5 rounded-lg opacity-50 hover:opacity-100 transition-opacity"
                            style={{
                              background: 'var(--surface-2)',
                              color: 'var(--text-muted)',
                            }}
                            title="Reset ve mac dinh"
                          >
                            Reset
                          </button>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {FEATURES.map((feature, idx) => (
                    <tr
                      key={`${feature.key}-${idx}`}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                      }}
                    >
                      <td
                        className="px-4 py-2.5 font-medium sticky left-0 z-10"
                        style={{
                          background: idx % 2 === 0 ? 'var(--surface-1)' : 'rgba(255,255,255,0.02)',
                          color: 'var(--text-primary)',
                        }}
                      >
                        <span className="flex items-center gap-1">
                          {feature.label}
                          {feature.note && (
                            <span className="text-[10px] opacity-50">{feature.note}</span>
                          )}
                          {feature.key === '__skip__' && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                              luon mo
                            </span>
                          )}
                        </span>
                      </td>
                      {ROLES.map(role => (
                        <td key={role} className="text-center px-3 py-2.5">
                          {feature.key === '__skip__' ? (
                            <span className="text-xs" style={{ color: 'var(--text-disabled)' }}>-</span>
                          ) : (
                            <button
                              onClick={() => handleToggle(role, feature.key)}
                              className="w-5 h-5 rounded-md border-2 transition-all duration-200 flex items-center justify-center mx-auto"
                              style={{
                                borderColor: isPermOn(role, feature.key) ? '#C9A96E' : 'var(--border-subtle)',
                                background: isPermOn(role, feature.key)
                                  ? 'linear-gradient(135deg, #C9A96E, #B8944F)'
                                  : 'transparent',
                              }}
                              title={`${getRoleLabel(role)}: ${feature.label} = ${isPermOn(role, feature.key) ? 'Bat' : 'Tat'}`}
                            >
                              {isPermOn(role, feature.key) && (
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                  <polyline points="20 6 9 17 4 12" />
                                </svg>
                              )}
                            </button>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2" style={{ borderColor: '#C9A96E', background: 'linear-gradient(135deg, #C9A96E, #B8944F)' }} />
            <span>Bat</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2" style={{ borderColor: 'var(--border-subtle)' }} />
            <span>Tat</span>
          </div>
          <span>Nhan vao o de chuyen doi. Nhan &quot;Reset&quot; de khoi phuc mac dinh vai tro.</span>
        </div>
      </div>
    </Sidebar>
  );
}
