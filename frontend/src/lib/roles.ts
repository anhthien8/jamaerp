/**
 * JAMA HOME CRM — Role-Based Access Control (RBAC)
 * Defines permissions for each user role.
 */

export type UserRole = 'admin' | 'leader' | 'data_entry' | 'accountant' | 'executive' | 'supervisor';

export interface RolePermissions {
  canViewDashboard: boolean;
  dashboardType: 'executive' | 'team' | 'personal' | 'financial';
  canViewLeads: boolean;
  leadsScope: 'all' | 'team' | 'own' | 'none';
  canViewAccounting: boolean;
  canViewPayroll: boolean;         // salary/commission details
  canViewCommissionOthers: boolean; // see OTHER people's commission
  canViewHR: boolean;
  canManageUsers: boolean;
  canViewProjects: boolean;        // view projects (designer: assigned only)
  canViewContracts: boolean;
  canViewQuotations: boolean;
  canCreateQuotations: boolean;
  canViewInventory: boolean;
  canViewReports: boolean;
  canViewPnL: boolean;              // profit & loss statement
  canCreateProjects: boolean;
  canCreateContracts: boolean;
  canCreateTasks: boolean;
  canEditTasks: boolean;            // designer: own tasks only
  canViewAttendance: boolean;       // attendance & leave management
  canViewKPI: boolean;              // KPI performance metrics
  canViewApprovals: boolean;        // approval management (pending queue)
  canViewFeedback: boolean;         // feedback admin (view all + reply)
  canViewSettings: boolean;         // system settings (admin sections)
}

export const ROLE_PERMISSIONS: Record<UserRole, RolePermissions> = {
  admin: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: true, leadsScope: 'all',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true,
    canViewReports: true, canViewPnL: true,
    canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true,
    canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: true, canViewSettings: true,
  },
  leader: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: true, leadsScope: 'team',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: true, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, // Restricted
    canViewReports: true, canViewPnL: false,
    canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true,
    canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false,
  },
  data_entry: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: true, leadsScope: 'own',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false,
    canViewReports: true, canViewPnL: false,
    canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false,
    canViewAttendance: true, canViewKPI: false, canViewApprovals: true, canViewFeedback: false, canViewSettings: false,
  },
  accountant: {
    canViewDashboard: true, dashboardType: 'financial',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: false, canViewInventory: true, // Accountant needs inventory for cost tracking
    canViewReports: true, canViewPnL: true,
    canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false,
    canViewAttendance: true, canViewKPI: false, canViewApprovals: true, canViewFeedback: false, canViewSettings: false,
  },
  executive: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: false, canCreateQuotations: false, canViewInventory: false,
    canViewReports: true, canViewPnL: true,
    canCreateProjects: true, canCreateContracts: false, canCreateTasks: false, canEditTasks: false,
    canViewAttendance: false, canViewKPI: true, canViewApprovals: false, canViewFeedback: true, canViewSettings: true,
  },
  supervisor: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true,
    canViewReports: true, canViewPnL: false,
    canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true,
    canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false,
  },
};

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    admin: 'Giám đốc',
    leader: 'Trưởng phòng',
    data_entry: 'Nhân viên Sale',
    accountant: 'Kế toán / Nhân sự',
    executive: 'Ban Quản Trị',
    supervisor: 'Giám sát',
  };
  return labels[role] || role;
}

export function getPermissions(role: UserRole): RolePermissions {
  return ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS.data_entry;
}

/**
 * Merge role defaults with per-user custom overrides.
 * Custom overrides take precedence over role defaults.
 * This enables admin to toggle individual permissions for each user.
 */
export function getEffectivePermissions(
  role: UserRole,
  customPermissions?: Record<string, boolean> | null,
): RolePermissions {
  const defaults = getPermissions(role);
  if (!customPermissions || Object.keys(customPermissions).length === 0) {
    return defaults;
  }
  // Custom overrides take precedence
  return { ...defaults, ...customPermissions } as RolePermissions;
}

/**
 * All permission keys (used to render the permissions checklist UI).
 */
export const ALL_PERMISSION_KEYS: Array<{ key: keyof RolePermissions; label: string }> = [
  { key: 'canViewDashboard', label: 'Xem Dashboard' },
  { key: 'canViewLeads', label: 'Xem Leads' },
  { key: 'canViewAccounting', label: 'Xem Kế toán' },
  { key: 'canViewPayroll', label: 'Xem Lương' },
  { key: 'canViewCommissionOthers', label: 'Xem hoa hồng người khác' },
  { key: 'canViewHR', label: 'Xem Nhân sự' },
  { key: 'canManageUsers', label: 'Quản lý Users' },
  { key: 'canViewProjects', label: 'Xem Dự án' },
  { key: 'canViewContracts', label: 'Xem Hợp đồng' },
  { key: 'canViewQuotations', label: 'Xem Báo giá' },
  { key: 'canCreateQuotations', label: 'Tạo Báo giá' },
  { key: 'canViewInventory', label: 'Xem Kho' },
  { key: 'canViewReports', label: 'Xem Báo cáo' },
  { key: 'canViewPnL', label: 'Xem Lợi nhuận (P&L)' },
  { key: 'canCreateProjects', label: 'Tạo Dự án' },
  { key: 'canCreateContracts', label: 'Tạo Hợp đồng' },
  { key: 'canCreateTasks', label: 'Tạo Công việc' },
  { key: 'canEditTasks', label: 'Sửa Công việc' },
  { key: 'canViewAttendance', label: 'Xem Chấm công' },
  { key: 'canViewKPI', label: 'Xem KPI' },
  { key: 'canViewApprovals', label: 'Xem Phê duyệt' },
  { key: 'canViewFeedback', label: 'Xem Feedback' },
  { key: 'canViewSettings', label: 'Xem Cài đặt' },
];
