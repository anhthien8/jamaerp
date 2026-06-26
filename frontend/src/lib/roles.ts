/**
 * JAMA HOME CRM — Role-Based Access Control (RBAC)
 * Defines permissions for each user role.
 */

export type UserRole = 'admin' | 'leader' | 'data_entry' | 'accountant' | 'executive';

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
}

export const ROLE_PERMISSIONS: Record<UserRole, RolePermissions> = {
  admin: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: true, leadsScope: 'all',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true,
    canViewReports: true,
  },
  leader: {
    canViewDashboard: true, dashboardType: 'team',
    canViewLeads: true, leadsScope: 'team',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: true, canManageUsers: false,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true,
    canViewReports: true,
  },
  data_entry: {
    canViewDashboard: true, dashboardType: 'personal',
    canViewLeads: true, leadsScope: 'own',
    canViewAccounting: true, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: false, canViewInventory: false,
    canViewReports: true,
  },
  accountant: {
    canViewDashboard: true, dashboardType: 'financial',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: true, canViewPayroll: true, canViewCommissionOthers: true,
    canViewHR: true, canManageUsers: true,
    canViewContracts: true, canViewQuotations: true, canViewInventory: true,
    canViewReports: true,
  },
  executive: {
    canViewDashboard: true, dashboardType: 'executive',
    canViewLeads: false, leadsScope: 'none',
    canViewAccounting: false, canViewPayroll: false, canViewCommissionOthers: false,
    canViewHR: false, canManageUsers: false,
    canViewContracts: true, canViewQuotations: false, canViewInventory: false,
    canViewReports: true,
  },
};

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    admin: 'Giám đốc',
    leader: 'Trưởng phòng',
    data_entry: 'Nhân viên Sale',
    accountant: 'Kế toán / Nhân sự',
    executive: 'Ban Quản Trị',
  };
  return labels[role] || role;
}

export function getPermissions(role: UserRole): RolePermissions {
  return ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS.data_entry;
}
