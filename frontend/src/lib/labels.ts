/**
 * Bản đồ nhãn tiếng Việt dùng chung — thay cho việc hiển thị key enum thô (design_contract,
 * wood, EXEC...) ra giao diện. App thuần Việt cho ~100 nhân viên (quyết định công ty).
 * Dùng: labelOf(TX_CATEGORY_LABELS, value) — key lạ sẽ trả về nguyên văn thay vì crash.
 */

export const TX_CATEGORY_LABELS: Record<string, string> = {
  design_contract: 'HĐ thiết kế',
  construction_contract: 'HĐ thi công',
  material: 'Vật liệu',
  labor: 'Nhân công',
  salary: 'Lương',
  commission: 'Hoa hồng',
  equipment: 'Thiết bị',
  rent: 'Mặt bằng',
  marketing: 'Marketing',
  other: 'Khác',
};

export const MATERIAL_CATEGORY_LABELS: Record<string, string> = {
  wood: 'Gỗ',
  stone: 'Đá',
  paint: 'Sơn',
  metal: 'Kim loại',
  glass: 'Kính',
  electrical: 'Điện',
  fabric: 'Vải',
  plumbing: 'Nước',
  furniture: 'Phụ kiện nội thất',
  other: 'Khác',
};

export const COMMISSION_TYPE_LABELS: Record<string, string> = {
  design_commission: 'HH thiết kế',
  construction_commission: 'HH thi công',
  design_contract: 'HH thiết kế',
  construction_contract: 'HH thi công',
  leader_override: 'HH trưởng nhóm',
  design_fee: 'Phí thiết kế',
  project_value: 'Theo giá trị dự án',
};

export const MILESTONE_LABELS: Record<string, string> = {
  signing: 'Ký HĐ',
  rough_complete: 'Nghiệm thu thô',
  interior_complete: 'Hoàn thiện nội thất',
  handover: 'Bàn giao',
};

export const DEPARTMENT_LABELS: Record<string, string> = {
  EXEC: 'Ban Giám đốc',
  SALES: 'Kinh doanh',
  DESIGN: 'Thiết kế',
  ACCT: 'Kế toán',
  OPS: 'Vận hành',
  HR: 'Nhân sự',
  sales: 'Kinh doanh',
  design: 'Thiết kế',
  leader: 'Trưởng nhóm',
  supervisor: 'Giám sát',
  accounting: 'Kế toán',
  construction: 'Thi công',
  procurement: 'Thu mua',
  quotation: 'Báo giá',
};

export const ROLE_LABELS: Record<string, string> = {
  admin: 'Quản trị',
  executive: 'Giám đốc',
  leader: 'Trưởng nhóm',
  data_entry: 'Kinh doanh',
  sales: 'Kinh doanh',
  accountant: 'Kế toán',
  supervisor: 'Giám sát',
};

export const LEAD_STAGE_LABELS: Record<string, string> = {
  new: 'Tiếp nhận mới',
  interested: 'Đang tư vấn',
  survey_scheduled: 'Đang chờ',
  potential: 'Đã chốt hồ sơ',
  signed_design: 'Deal đã thắng',
  lost: 'Đã mất',
  dormant: 'Tạm ngưng',
};

/** Tra nhãn Việt; key lạ trả nguyên văn (không crash, không hiện undefined). */
export function labelOf(map: Record<string, string>, key?: string | null): string {
  if (!key) return '—';
  return map[key] || key;
}

/** "2026-07" hoặc Date → "Tháng 7/2026" (thay cho July 2026 của locale máy). */
export function monthLabelVN(input: string | Date): string {
  if (typeof input === 'string') {
    const m = input.match(/^(\d{4})-(\d{2})/);
    if (m) return `Tháng ${parseInt(m[2], 10)}/${m[1]}`;
    return input;
  }
  return `Tháng ${input.getMonth() + 1}/${input.getFullYear()}`;
}
