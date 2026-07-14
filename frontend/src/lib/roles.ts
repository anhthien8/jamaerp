/**
 * JAMA HOME CRM — Role-Based Access Control (RBAC)
 * Defines permissions for each user role.
 */

export type UserRole = 'admin' | 'leader' | 'data_entry' | 'accountant' | 'executive' | 'purchasing' | 'designer' | 'pm';

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
  },
  leader: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: true, leadsScope: 'team',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: true, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false, // Restricted
    canViewReports: true, canViewPnL: false,
    canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true,
  },
  data_entry: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: true, leadsScope: 'own',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false,
    canViewReports: true, canViewPnL: false,
    canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false,
  },
  accountant: {
    canViewDashboard: true, dashboardType: 'financial',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: false, canViewInventory: true, // Accountant needs inventory for cost tracking
    canViewReports: true, canViewPnL: true,
    canCreateProjects: false, canCreateContracts: true, canCreateTasks: false, canEditTasks: false,
  },
  executive: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: false, canCreateQuotations: false, canViewInventory: false,
    canViewReports: true, canViewPnL: true,
    canCreateProjects: true, canCreateContracts: false, canCreateTasks: false, canEditTasks: false,
  },
  purchasing: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: false, canCreateQuotations: false, canViewInventory: true,
    canViewReports: false, canViewPnL: false,
    canCreateProjects: false, canCreateContracts: false, canCreateTasks: false, canEditTasks: true, // task status on procurement tasks
  },
  designer: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: false, canViewQuotations: true, canCreateQuotations: true, canViewInventory: false,
    canViewReports: false, canViewPnL: false,
    canCreateProjects: false, canCreateContracts: false, canCreateTasks: true, canEditTasks: true,
  },
  pm: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewProjects: true, canViewContracts: true, canViewQuotations: true, canCreateQuotations: true, canViewInventory: true,
    canViewReports: true, canViewPnL: false,
    canCreateProjects: true, canCreateContracts: true, canCreateTasks: true, canEditTasks: true,
  },
};

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    admin: 'Giám đốc',
    leader: 'Trưởng phòng',
    data_entry: 'Nhân viên Sale',
    accountant: 'Kế toán / Nhân sự',
    executive: 'Ban Quản Trị',
    purchasing: 'Nhân viên Thu mua',
    designer: 'Nhân viên Thiết kế',
    pm: 'Trưởng Dự án',
  };
  return labels[role] || role;
}

export function getPermissions(role: UserRole): RolePermissions {
  return ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS.data_entry;
}
