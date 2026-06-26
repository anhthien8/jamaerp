/** Utility helpers */

export const STAGE_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  new: { label: 'Mới tiếp nhận', color: '#3B82F6', emoji: '🆕' },
  interested: { label: 'Có nhu cầu', color: '#8B5CF6', emoji: '💡' },
  survey_scheduled: { label: 'Đã hẹn khảo sát', color: '#F59E0B', emoji: '📅' },
  potential: { label: 'KH tiềm năng', color: '#10B981', emoji: '⭐' },
  signed_design: { label: 'Ký thiết kế', color: '#C9A96E', emoji: '✍️' },
  lost: { label: 'Mất', color: '#EF4444', emoji: '❌' },
  dormant: { label: 'Ngủ đông', color: '#6B7280', emoji: '😴' },
};

export const SOURCE_LABELS: Record<string, string> = {
  facebook: 'Facebook',
  zalo: 'Zalo',
  website: 'Website',
  referral: 'Giới thiệu',
  tiktok: 'TikTok',
  other: 'Khác',
};

export const PROPERTY_LABELS: Record<string, string> = {
  townhouse: 'Nhà phố',
  apartment: 'Căn hộ',
  villa: 'Biệt thự',
  office: 'Văn phòng',
  shophouse: 'Shophouse',
  other: 'Khác',
};

export const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: 'Thấp', color: '#6B7280' },
  medium: { label: 'Trung bình', color: '#3B82F6' },
  high: { label: 'Cao', color: '#F59E0B' },
  urgent: { label: 'Khẩn cấp', color: '#EF4444' },
};

export function formatCurrency(value?: number | null): string {
  if (!value) return '—';
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} tỷ`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(0)} triệu`;
  return `${value.toLocaleString('vi-VN')} ₫`;
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function timeAgo(dateStr?: string | null): string {
  if (!dateStr) return 'Chưa liên hệ';
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return 'Hôm nay';
  if (days === 1) return 'Hôm qua';
  return `${days} ngày trước`;
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ');
}
