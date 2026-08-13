/**
 * JAMA HOME CRM — Role-Based Access Control (RBAC)
 * Defines permissions for each user role.
 */

export type UserRole = 'admin' | 'leader' | 'data_entry' | 'accountant' | 'executive' | 'supervisor';

// 6 vai trò hệ thống — mọi role khác là vai trò tùy chỉnh (tạo trong Phân quyền)
export const SYSTEM_ROLES: string[] = ['admin', 'leader', 'data_entry', 'accountant', 'executive', 'supervisor'];

/**
 * Điều phối KD: vai trò tùy chỉnh thuộc bộ phận Kinh doanh (vd: Admin CSKH).
 * Nhóm này nhập lead từ marketing rồi phân chia cho nhân viên KD.
 * PHẢI khớp is_sales_coordinator() trong backend/app/middleware/rbac.py.
 */
export function isSalesCoordinator(role?: string, department?: string): boolean {
  return !!role && !SYSTEM_ROLES.includes(role) && (department || '').toUpperCase() === 'SALES';
}

/** Ai được gắn/đổi nhân viên KD phụ trách lead — khớp can_assign_leads() backend. */
export function canAssignLeads(user?: { role?: string; department?: string } | null): boolean {
  if (!user) return false;
  return user.role === 'admin' || user.role === 'leader' || isSalesCoordinator(user.role, user.department);
}

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
    // canViewKPI bật 12/08/2026 (chủ dự án chốt): KPI vốn đã được ghim vào menu chính của
    // sale (ROLE_ESSENTIALS) mà quyền lại tắt ⇒ bấm vào là bị đá về Tổng quan.
    // Kèm theo: sale thấy thẻ Bảng xếp hạng — top 5 hiện tên, còn lại ẩn danh "Nhân viên #n".
    canViewAttendance: true, canViewKPI: true, canViewApprovals: true, canViewFeedback: false, canViewSettings: false,
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

// ── Vai trò tùy chỉnh (admin tạo ở trang Tài khoản, backend lưu system_settings) ──
// Cache module-level để getPermissions/getRoleLabel (sync) tra được sau khi tải.
// Không tải thì user vai trò custom bị fallback quyền data_entry — SAI phân quyền.
let _customRoles: Record<string, { role_name: string; permissions: Record<string, boolean | string> }> = {};

/** Tải vai trò tùy chỉnh từ backend. Trả về true nếu có ít nhất 1 vai trò. */
export async function loadCustomRoles(): Promise<boolean> {
  try {
    if (typeof window !== 'undefined' && localStorage.getItem('jama_demo') === 'true') return false;
    const token = typeof window !== 'undefined' ? localStorage.getItem('jama_token') : null;
    if (!token) return false;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    const res = await fetch(`${baseUrl}/users/roles/custom`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return false;
    const data = await res.json();
    _customRoles = {};
    for (const r of data.roles || []) {
      _customRoles[r.role_key] = { role_name: r.role_name, permissions: r.permissions || {} };
    }
    return Object.keys(_customRoles).length > 0;
  } catch {
    return false;
  }
}

/** Cache vai trò tùy chỉnh hiện có (đã tải qua loadCustomRoles). */
export function getCustomRoleCache(): Record<string, { role_name: string; permissions: Record<string, boolean | string> }> {
  return _customRoles;
}

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    admin: 'Giám đốc',
    leader: 'Trưởng phòng',
    data_entry: 'Nhân viên Sale',
    accountant: 'Kế toán / Nhân sự',
    executive: 'Ban Quản Trị',
    supervisor: 'Giám sát',
  };
  return labels[role] || _customRoles[role]?.role_name || role;
}

// ── Role-level permission overrides (loaded from API) ───────────────────
// When admin toggles permissions in the matrix, overrides are stored here.
let _roleOverrides: Partial<Record<UserRole, Partial<RolePermissions>>> = {};

/** Load role-level permission overrides from backend (admin only). */
export async function loadRolePermissions(): Promise<void> {
  try {
    // Demo mode: load from localStorage
    if (typeof window !== 'undefined' && localStorage.getItem('jama_demo') === 'true') {
      const overrides: Partial<Record<UserRole, Partial<RolePermissions>>> = {};
      for (const role of ['admin', 'executive', 'leader', 'data_entry', 'accountant', 'supervisor'] as UserRole[]) {
        const stored = localStorage.getItem(`jama_role_perms_${role}`);
        if (stored) {
          try { overrides[role] = JSON.parse(stored); } catch {}
        }
      }
      if (Object.keys(overrides).length > 0) _roleOverrides = overrides;
      return;
    }
    const token = typeof window !== 'undefined' ? localStorage.getItem('jama_token') : null;
    if (!token) return;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    const res = await fetch(`${baseUrl}/users/permissions/roles`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    if (data.roles) {
      const overrides: Partial<Record<UserRole, Partial<RolePermissions>>> = {};
      for (const [role, info] of Object.entries(data.roles) as Array<[string, { overrides?: Partial<RolePermissions> | null }]>) {
        if (info.overrides && Object.keys(info.overrides).length > 0) {
          overrides[role as UserRole] = info.overrides;
        }
      }
      _roleOverrides = overrides;
    }
  } catch {
    // Silently ignore — defaults will be used
  }
}

/**
 * Tải quyền hiệu lực của CHÍNH người đang đăng nhập từ backend
 * (GET /users/permissions/me — mở cho mọi người, thêm 13/08/2026).
 *
 * Backend mới là nơi thật sự chặn API; menu vẽ theo bản này thì cái gì thấy được
 * là gọi được. Trước đây người thường không đọc nổi /permissions/roles (chỉ admin)
 * nên override sếp đặt trên trang Phân quyền không bao giờ tới được menu của họ.
 * Trả null khi demo / mất mạng — bên gọi tự rơi về bản tính cục bộ.
 */
export async function loadMyPermissions(): Promise<RolePermissions | null> {
  try {
    if (typeof window !== 'undefined' && localStorage.getItem('jama_demo') === 'true') return null;
    const token = typeof window !== 'undefined' ? localStorage.getItem('jama_token') : null;
    if (!token) return null;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    const res = await fetch(`${baseUrl}/users/permissions/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.permissions) return data.permissions as RolePermissions;
  } catch {
    // Silently ignore — defaults will be used
  }
  return null;
}

/** Save role-level permission overrides for a specific role. */
export async function saveRolePermissions(role: UserRole, permissions: Record<string, boolean>): Promise<void> {
  // Demo mode: save to localStorage
  if (typeof window !== 'undefined' && localStorage.getItem('jama_demo') === 'true') {
    localStorage.setItem(`jama_role_perms_${role}`, JSON.stringify(permissions));
    _roleOverrides[role] = permissions as Partial<RolePermissions>;
    return;
  }
  const token = typeof window !== 'undefined' ? localStorage.getItem('jama_token') : null;
  if (!token) throw new Error('Not authenticated');
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const res = await fetch(`${baseUrl}/users/permissions/roles/${role}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ permissions }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  _roleOverrides[role] = permissions as Partial<RolePermissions>;
}

/** Get current role-level overrides (for the matrix UI). */
export function getRoleOverrides(): Partial<Record<UserRole, Partial<RolePermissions>>> {
  return _roleOverrides;
}

export function getPermissions(role: UserRole): RolePermissions {
  // Vai trò custom: quyền lấy từ định nghĩa đã lưu (phủ lên khung data_entry
  // để không thiếu key) — KHÔNG được rơi thẳng về data_entry như trước.
  const custom = _customRoles[role as string];
  const base = ROLE_PERMISSIONS[role]
    || (custom ? ({ ...ROLE_PERMISSIONS.data_entry, ...custom.permissions } as RolePermissions) : ROLE_PERMISSIONS.data_entry);
  const overrides = _roleOverrides[role];
  if (overrides && Object.keys(overrides).length > 0) {
    return { ...base, ...overrides } as RolePermissions;
  }
  return base;
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
  { key: 'canViewKPI', label: 'Xem KPI (kèm Bảng xếp hạng)' },
  { key: 'canViewApprovals', label: 'Xem Phê duyệt' },
  { key: 'canViewFeedback', label: 'Xem Góp ý (đọc + trả lời)' },
  { key: 'canViewSettings', label: 'Xem Cài đặt' },
];
