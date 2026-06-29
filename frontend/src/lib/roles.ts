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
  canViewContracts: boolean;
  canViewQuotations: boolean;
  canViewInventory: boolean;
  canViewReports: boolean;
  canViewPnL: boolean;              // profit & loss statement
}

export const ROLE_PERMISSIONS: Record<UserRole, RolePermissions> = {
  admin: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: true, leadsScope: 'all',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true,
    canViewReports: true, canViewPnL: true,
  },
  leader: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: true, leadsScope: 'team',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: true, canManageUsers: false,
    canViewContracts: true, canViewQuotations: true, canViewInventory: false, // Restricted
    canViewReports: true, canViewPnL: false,
  },
  data_entry: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: true, leadsScope: 'own',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: false, canViewInventory: false,
    canViewReports: true, canViewPnL: false,
  },
  accountant: {
    canViewDashboard: true, dashboardType: 'financial',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true, // Accountant needs inventory for cost tracking
    canViewReports: true, canViewPnL: true,
  },
  executive: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: false, canViewInventory: false,
    canViewReports: true, canViewPnL: true,
  },
  purchasing: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: false, canViewInventory: true,
    canViewReports: false, canViewPnL: false,
  },
  designer: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: false, canViewQuotations: true, canViewInventory: false,
    canViewReports: false, canViewPnL: false,
  },
  pm: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true,
    canViewReports: true, canViewPnL: false,
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
