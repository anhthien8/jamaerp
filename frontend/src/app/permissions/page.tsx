'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { UserRole, getRoleLabel, getRoleOverrides, loadRolePermissions, saveRolePermissions } from '@/lib/roles';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';

// 'executive' bị bỏ khỏi cột hiển thị từ 13/08/2026 — không ai mang vai trò này,
// để cột thừa chỉ gây rối. Vẫn còn trong DEFAULTS bên dưới (tương thích dữ liệu cũ).
// 'supervisor' bỏ khỏi cột từ 22/10/2026 (chốt V3: gộp vào TP Giám sát).
const ROLES: UserRole[] = ['admin', 'leader', 'data_entry', 'accountant'];

// Vai trò tùy chỉnh (admin tạo ở trang Tài khoản) — hiển thị thành cột riêng
interface CustomRoleInfo {
  role_key: string;
  role_name: string;
  permissions: Record<string, boolean>;
}

interface Feature {
  key: string;
  label: string;
  note?: string;
}

const FEATURES: Feature[] = [
  { key: 'canViewDashboard', label: 'Dashboard - Tổng quan' },
  // Bật quyền này là mở CẢ thẻ "Bảng xếp hạng" (top 5 hiện tên, còn lại ẩn danh
  // "Nhân viên #n") — ghi rõ để người bật biết mình đang cho thấy những gì.
  { key: 'canViewKPI', label: 'KPI (Cá nhân + Bảng xếp hạng)' },
  { key: 'canViewLeads', label: 'CRM - Quy trình' },
  { key: 'canViewApprovals', label: 'Phê duyệt' },
  { key: 'canViewProjects', label: 'Dự án' },
  { key: 'canViewAttendance', label: 'Chấm công' },
  { key: 'canViewLeads', label: 'Báo giá tức thì', note: '(quy trình)' },
  { key: 'canEditCustomers', label: 'Khách hàng', note: '(sửa hồ sơ)' },
  { key: 'canViewContracts', label: 'Hợp đồng' },
  { key: 'canViewQuotations', label: 'Báo giá' },
  { key: 'canViewInventory', label: 'Kho vật tư' },
  { key: 'canViewInventory', label: 'Nhà cung cấp', note: '(xem — theo kho)' },
  { key: 'canEditSuppliers', label: 'Nhà cung cấp', note: '(sửa hồ sơ)' },
  { key: 'canViewPnL', label: 'P&L' },
  { key: 'canViewAccounting', label: 'Kế toán' },
  { key: 'canViewHR', label: 'Nhân sự' },
  { key: 'canViewAccounting', label: 'Tài chính', note: '(kế toán)' },
  { key: 'canViewReports', label: 'Báo cáo' },
  { key: 'canViewFeedback', label: 'Góp ý' },
  { key: 'canManageUsers', label: 'Tài khoản' },
];

type PermissionMatrix = Record<string, Record<string, boolean>>;

// Hardcoded defaults (mirrors backend _ROLE_PERMISSION_DEFAULTS)
const DEFAULTS: Record<string, Record<string, boolean>> = {
  admin: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true, canViewHR: true, canManageUsers: true, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true, canViewReports: true, canViewPnL: true, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: true, canViewSettings: true , canEditSuppliers: true, canEditCustomers: true },
  executive: { canViewDashboard: true, canViewLeads: false, canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: false, canCreateQuotations: false, canViewInventory: false, canViewReports: true, canViewPnL: true, canCreateProjects: true, canCreateContracts: false, canCreateTasks: false, canEditTasks: false, canViewAttendance: false, canViewKPI: true, canViewApprovals: false, canViewFeedback: true, canViewSettings: true , canEditSuppliers: false, canEditCustomers: false },
  leader: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: true, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, canViewReports: true, canViewPnL: false, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false , canEditSuppliers: false, canEditCustomers: true },
  data_entry: { canViewDashboard: true, canViewLeads: true, canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, canViewReports: true, canViewPnL: false, canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false , canEditSuppliers: false, canEditCustomers: true },
  supervisor: { canViewDashboard: true, canViewLeads: false, canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false, canViewHR: false, canManageUsers: false, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true, canViewReports: true, canViewPnL: false, canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true, canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false , canEditSuppliers: true, canEditCustomers: false },
  accountant: { canViewDashboard: true, canViewLeads: false, canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true, canViewHR: true, canManageUsers: true, canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: false, canViewInventory: true, canViewReports: true, canViewPnL: true, canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false, canViewAttendance: true, canViewKPI: false, canViewApprovals: true, canViewFeedback: false, canViewSettings: false , canEditSuppliers: false, canEditCustomers: true },
};

export default function PermissionsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [overrides, setOverrides] = useState<PermissionMatrix>({});
  const [customRoles, setCustomRoles] = useState<CustomRoleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  const allRoleKeys: string[] = [...ROLES, ...customRoles.map(r => r.role_key)];
  const findCustom = (role: string) => customRoles.find(r => r.role_key === role);
  const roleLabelOf = (role: string) => findCustom(role)?.role_name || getRoleLabel(role as UserRole);

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
    // Vai trò tùy chỉnh: lấy danh sách + quyền đã lưu để hiển thị cột riêng
    try {
      const cr = await api.getCustomRoles();
      setCustomRoles((cr.roles || []).map(r => ({
        role_key: r.role_key,
        role_name: r.role_name,
        permissions: (r.permissions || {}) as Record<string, boolean>,
      })));
    } catch {
      setCustomRoles([]);
    }
    const ov = getRoleOverrides();
    // Convert Partial<RolePermissions> to Record<string, boolean> for local state
    const normalized: PermissionMatrix = {};
    for (const [role, perms] of Object.entries(ov)) {
      if (perms) {
        normalized[role] = {};
        for (const [k, v] of Object.entries(perms)) {
          if (typeof v === 'boolean') {
            normalized[role][k] = v;
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

  // Check if a permission is on for a role (defaults + overrides).
  // Vai trò tùy chỉnh: "defaults" chính là quyền lưu trong định nghĩa role.
  const isPermOn = (role: string, key: string): boolean => {
    const override = overrides[role]?.[key];
    if (override !== undefined) return override;
    const custom = findCustom(role);
    if (custom) return Boolean(custom.permissions[key]);
    return DEFAULTS[role]?.[key] ?? false;
  };

  const handleToggle = (role: string, featureKey: string) => {
    if (featureKey === '__skip__') return;
    const current = isPermOn(role, featureKey);
    const newOverrides = { ...overrides };
    if (!newOverrides[role]) newOverrides[role] = {};
    newOverrides[role][featureKey] = !current;
    setOverrides(newOverrides);
    setHasChanges(true);
  };

  const handleSaveRole = async (role: string, skipReset = false) => {
    setSaving(role);
    try {
      const roleOverrides = overrides[role] || {};
      const isCustom = Boolean(findCustom(role));
      const payload: Record<string, boolean> = {};
      if (isCustom) {
        // Vai trò tùy chỉnh: gửi TRỌN bộ quyền hiện tại (backend ghi đè vào định nghĩa role)
        for (const f of FEATURES) {
          if (f.key === '__skip__') continue;
          payload[f.key] = isPermOn(role, f.key);
        }
      } else {
        // Vai trò hệ thống: chỉ gửi khác biệt so với mặc định (overrides)
        for (const f of FEATURES) {
          if (f.key === '__skip__') continue;
          if (roleOverrides[f.key] !== undefined) {
            payload[f.key] = roleOverrides[f.key];
          }
        }
      }
      await saveRolePermissions(role as UserRole, payload);
      if (isCustom) {
        // Đồng bộ state local để cột custom hiển thị đúng sau khi lưu
        setCustomRoles(prev => prev.map(r => r.role_key === role
          ? { ...r, permissions: { ...r.permissions, ...payload } }
          : r));
        setOverrides(prev => { const next = { ...prev }; delete next[role]; return next; });
      }
      toast(`Đã lưu phân quyền vai trò ${roleLabelOf(role)}`, 'success');
      if (!skipReset) setHasChanges(false);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lưu thất bại', 'error');
    } finally {
      setSaving(null);
    }
  };

  const handleSaveAll = async () => {
    for (const role of allRoleKeys) {
      await handleSaveRole(role, true); // pass true to skip individual hasChanges reset
    }
    setHasChanges(false);
  };

  const handleResetRole = (role: string) => {
    const newOverrides = { ...overrides };
    delete newOverrides[role];
    setOverrides(newOverrides);
    setHasChanges(true);
  };

  if (user?.role !== 'admin') {
    return (
      <Sidebar>
        <div className="p-8 text-center">
          <p className="text-[var(--text-muted)]">Chỉ admin mới có quyền truy cập trang này.</p>
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
              Phân quyền vai trò
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              Cấu hình quyền truy cập cho từng vai trò. Bật/tắt quyền cho mỗi tính năng.
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
              Tải lại
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
                Lưu tất cả thay đổi
              </button>
            )}
          </div>
        </div>

        {/* Matrix Table */}
        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <div className="inline-block w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--text-muted)', borderTopColor: 'transparent' }} />
              <p className="text-sm mt-3" style={{ color: 'var(--text-muted)' }}>Đang tải dữ liệu...</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  {/* Hàng nhóm: tách «có sẵn» và «tùy chỉnh» thay vì gắn nhãn từng cột (24/10/2026) */}
                  <tr>
                    <th
                      rowSpan={2}
                      className="text-left px-4 py-3 font-semibold sticky left-0 z-10 align-bottom"
                      style={{ background: 'var(--surface-1)', color: 'var(--text-primary)', minWidth: 180, borderBottom: '1px solid var(--border-subtle)' }}
                    >
                      Tính năng
                    </th>
                    <th colSpan={ROLES.length} className="px-3 pt-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-center" style={{ color: 'var(--text-muted)' }}>
                      Vai trò có sẵn
                    </th>
                    {customRoles.length > 0 && (
                      <th colSpan={customRoles.length} className="px-3 pt-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-center" style={{ color: 'var(--gold-500)', borderLeft: '1px solid var(--border-subtle)' }}>
                        Vai trò tự tạo <span className="normal-case font-normal" style={{ color: 'var(--text-muted)' }}>· thêm ở trang Tài khoản</span>
                      </th>
                    )}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    {allRoleKeys.map((role, i) => {
                      const tuyChinh = !!findCustom(role);
                      return (
                        <th
                          key={role}
                          className="text-center px-2 pb-3 pt-1 font-semibold align-top"
                          style={{
                            color: 'var(--text-primary)', minWidth: 96,
                            borderLeft: i === ROLES.length ? '1px solid var(--border-subtle)' : undefined,
                          }}
                        >
                          <div className="flex flex-col items-center justify-between gap-1 min-h-[60px]">
                            <span className="text-[13px] leading-tight">{roleLabelOf(role)}</span>
                            {!tuyChinh && (
                              <button
                                onClick={() => handleResetRole(role)}
                                className="inline-flex items-center justify-center w-6 h-6 rounded-full opacity-60 hover:opacity-100 transition-opacity"
                                style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}
                                title={`Khôi phục quyền mặc định cho ${roleLabelOf(role)}`}
                                aria-label={`Khôi phục quyền mặc định cho ${roleLabelOf(role)}`}
                              >
                                <LineIcon name="refresh" size={12} color="currentColor" />
                              </button>
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {FEATURES.map((feature, idx) => (
                    <tr
                      key={`${feature.key}-${idx}`}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        background: idx % 2 === 0 ? 'transparent' : 'var(--surface-2)',
                      }}
                    >
                      <td
                        className="px-4 py-2.5 font-medium sticky left-0 z-10"
                        style={{
                          background: idx % 2 === 0 ? 'var(--surface-1)' : 'var(--surface-2)',
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
                              luôn mở
                            </span>
                          )}
                        </span>
                      </td>
                      {allRoleKeys.map((role, i) => (
                        <td key={role} className="text-center px-3 py-2.5" style={i === ROLES.length ? { borderLeft: '1px solid var(--border-subtle)' } : undefined}>
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
                              title={`${roleLabelOf(role)}: ${feature.label} = ${isPermOn(role, feature.key) ? 'Bật' : 'Tắt'}`}
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
            <span>Bật</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded border-2" style={{ borderColor: 'var(--border-subtle)' }} />
            <span>Tắt</span>
          </div>
          <span>Nhấn vào ô để bật/tắt. Nút <LineIcon name="refresh" size={11} color="currentColor" className="inline-block align-[-1px]" /> dưới tên vai trò = khôi phục quyền mặc định.</span>
        </div>
      </div>
    </Sidebar>
  );
}
