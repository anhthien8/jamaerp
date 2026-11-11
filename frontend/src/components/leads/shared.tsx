import { TAG_COLORS } from '@/lib/utils';
import type { Lead } from '@/lib/api';

// Hằng số & helper hiển thị dùng chung giữa trang Lead và các khối tách ra.
export const PROPERTY_LABELS: Record<string, string> = {
  townhouse: 'Nhà phố', apartment: 'Căn hộ', villa: 'Biệt thự',
  office: 'Văn phòng', shophouse: 'Shophouse', other: 'Khác',
};
export const SOURCE_LABELS: Record<string, string> = {
  facebook: 'Facebook', zalo: 'Zalo', website: 'Website',
  referral: 'Giới thiệu', tiktok: 'TikTok',
  hotline: 'Hotline', office_visit: 'Khách đến văn phòng', google_form: 'Google Form', other: 'Khác',
};
export const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  urgent: { label: 'Khẩn cấp', color: 'var(--danger)' },
  high: { label: 'Cao', color: 'var(--warning)' },
  medium: { label: 'Trung bình', color: 'var(--info)' },
  low: { label: 'Thấp', color: '#6B7280' },
};
export const ACTIVITY_ICONS: Record<string, string> = {
  note: 'edit', call: 'phone', meeting: 'handshake', email: 'mail', sms: 'message',
  stage_change: 'refresh', assignment: 'user', system: 'robot', cskh: 'users',
};
export const STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design'];

/** Ngày giờ đầy đủ CÓ năm — lognote CSKH trải nhiều tháng, thiếu năm là đọc nhầm. */
export function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function TagBadge({ tag }: { tag: string }) {
  const color = TAG_COLORS[tag] || '#6B7280';
  return (
    <span
      className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-full font-medium"
      style={{ background: `${color}20`, color, border: `1px solid ${color}30` }}
    >
      {tag}
    </span>
  );
}

// Cột hiển thị trên bảng kanban. KHÁC STAGES vì "Mất" phải có mặt để kiểm soát lead rơi,
// nhưng không được nằm trong STAGES: chuyển sang "Mất" bắt buộc kèm lý do, mà các nút
// "Chuyển giai đoạn" trong thẻ chi tiết lại bắn thẳng handleStageChange không lý do.
export const BOARD_STAGES = [...STAGES, 'lost'];
export const ALL_STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design', 'lost', 'dormant'];
// Ngưỡng «Quá hạn» THEO GIAI ĐOẠN (tính từ last_contacted_at hoặc updated_at).
// Ngưỡng phẳng 3 ngày cũ gắn cờ cho ~73% lead — cờ mọc khắp nơi thì hết ý nghĩa cảnh báo.
// signed_design/lost/dormant không có trong map = không bao giờ gắn cờ.
export const OVERDUE_DAYS_BY_STAGE: Record<string, number> = {
  new: 3,
  interested: 7,
  survey_scheduled: 7,
  potential: 14,
};
// Kanban windowing: mỗi cột chỉ VẼ tối đa chừng này thẻ mỗi «trang» — cột «Tiếp nhận mới»
// 137 thẻ từng đẩy trang cao ~28.000px. Chỉ giới hạn render; đếm ở header cột vẫn là tổng thật.
export const KANBAN_PAGE_SIZE = 25;

export function isOverdueLead(lead: Lead) {
  const days = OVERDUE_DAYS_BY_STAGE[lead.stage];
  if (!days) return false;
  const timestamp = lead.last_contacted_at || lead.updated_at;
  if (!timestamp) return false;
  const ageMs = Date.now() - new Date(timestamp).getTime();
  return ageMs > days * 24 * 60 * 60 * 1000;
}
