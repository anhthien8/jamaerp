'use client';

/**
 * Nhãn vai trò/phòng ban DÙNG CHUNG cho Nhân sự, Hồ sơ 360°, Cài đặt (24/10/2026).
 * Trước đây mỗi trang một bảng riêng → admin hiện «Giám đốc» ở Nhân sự nhưng
 * «Quản trị» ở Cài đặt, vai trò tùy chỉnh hiện mã thô (giam_sat_thi_cong).
 * Vai trò tùy chỉnh lấy tên từ GET /users/roles/custom (ai đăng nhập cũng gọi được),
 * tải 1 lần/phiên trang rồi dùng lại.
 */

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export interface RoleStyle { label: string; color: string; bg: string }

export const NHAN_SU_ROLES: Record<string, RoleStyle> = {
  admin: { label: 'Giám đốc', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  executive: { label: 'Ban Quản Trị', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
  leader: { label: 'Trưởng phòng', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  sale_leader: { label: 'Trưởng nhóm KD', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  data_entry: { label: 'Nhân viên Sale', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  supervisor: { label: 'Giám sát', color: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
  accountant: { label: 'Kế toán / Nhân sự', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
};

const ROLE_KHAC: Omit<RoleStyle, 'label'> = { color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' };

export const NHAN_SU_DEPTS: Record<string, string> = {
  EXEC: 'Ban Giám đốc', BOD: 'Ban Giám đốc',
  SALES: 'Kinh doanh',
  DESIGN: 'Thiết kế',
  OPS: 'Giám sát / Vận hành', CONSTRUCTION: 'Thi công',
  ACCT: 'Kế toán', ACCOUNTING: 'Kế toán',
  PURCHASING: 'Thu mua', PROCUREMENT: 'Thu mua',
  HR: 'Nhân sự', OTHER: 'Khác',
  // dữ liệu cũ còn lưu chữ thường
  sales: 'Kinh doanh', design: 'Thiết kế', construction: 'Thi công',
  accounting: 'Kế toán', management: 'Ban lãnh đạo',
};

/** Thứ tự phòng ban trên sơ đồ: BGĐ trước, rồi các khối nghiệp vụ. */
export const DEPT_ORDER = ['EXEC', 'BOD', 'SALES', 'DESIGN', 'OPS', 'CONSTRUCTION', 'PURCHASING', 'PROCUREMENT', 'ACCT', 'ACCOUNTING', 'HR'];

export function deptLabel(d?: string | null): string {
  if (!d) return 'Khác';
  return NHAN_SU_DEPTS[d] || d;
}

export interface VaiTroTuyChinh { role_key: string; role_name: string; department: string }

let _customCache: Promise<VaiTroTuyChinh[]> | null = null;

function taiVaiTroTuyChinh(): Promise<VaiTroTuyChinh[]> {
  if (!_customCache) {
    _customCache = api.getCustomRoles()
      .then(res => (res.roles || []).map(r => ({ role_key: r.role_key, role_name: r.role_name, department: r.department })))
      .catch(() => { _customCache = null; return []; });
  }
  return _customCache;
}

/** Danh sách vai trò tùy chỉnh (cho ô chọn vai trò ở form thêm nhân viên). */
export function useCustomRoles(): VaiTroTuyChinh[] {
  const [list, setList] = useState<VaiTroTuyChinh[]>([]);
  useEffect(() => {
    let alive = true;
    void taiVaiTroTuyChinh().then(l => { if (alive) setList(l); });
    return () => { alive = false; };
  }, []);
  return list;
}

/** Hook trả hàm `roleOf(role)` → {label,color,bg}, đã gồm tên vai trò tùy chỉnh. */
export function useRoleLabels() {
  const list = useCustomRoles();
  return (role?: string | null): RoleStyle => {
    const r = role || '';
    if (NHAN_SU_ROLES[r]) return NHAN_SU_ROLES[r];
    const c = list.find(x => x.role_key === r);
    return { label: c?.role_name || r || '—', ...ROLE_KHAC };
  };
}

/** Nén ảnh giấy tờ phía client: cạnh dài ≤1600px, JPG — giảm chất lượng tới khi ≤500KB. */
export async function compressImage(file: File): Promise<{ base64: string; mime: string } | null> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return null;
  const maxDim = 1600;
  const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  // PNG trong suốt ép sang JPG sẽ ra nền ĐEN nếu không tô trắng trước
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.82, 0.65, 0.5, 0.35]) {
    const dataUrl = canvas.toDataURL('image/jpeg', quality);
    const base64 = dataUrl.split(',')[1];
    if (base64.length * 0.75 <= 500_000) return { base64, mime: 'image/jpeg' };
  }
  return null;
}

/** Bám đúng VAI_TRO_TRUONG_PHONG / VAI_TRO_TRUONG_NHOM ở backend/app/middleware/rbac.py. */
const TRUONG_PHONG: Record<string, string[]> = {
  DESIGN: ['leader'], OPS: ['operation_leader'], PURCHASING: ['dutoan_thumua_leader'], SALES: ['leader'],
};
const TRUONG_NHOM: Record<string, string[]> = {
  SALES: ['sale_leader'], DESIGN: ['design_leader', '2d_leader'],
};

export type CapBac = 'bgd' | 'tp' | 'tn' | 'nv';

/** Tầng trên sơ đồ: Ban Giám đốc → Trưởng phòng → Trưởng nhóm → Nhân viên. */
export function capBac(u: { role: string; department?: string | null }): CapBac {
  const d = (u.department || '').toUpperCase();
  if (u.role === 'admin' || u.role === 'executive' || d === 'EXEC' || d === 'BOD') return 'bgd';
  if ((TRUONG_PHONG[d] || []).includes(u.role) || (!TRUONG_PHONG[d] && u.role === 'leader')) return 'tp';
  if ((TRUONG_NHOM[d] || []).includes(u.role)) return 'tn';
  return 'nv';
}

export const CAP_BAC_LABEL: Record<CapBac, string> = {
  bgd: 'Ban Giám đốc', tp: 'Trưởng phòng', tn: 'Trưởng nhóm', nv: 'Nhân viên',
};
