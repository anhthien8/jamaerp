/** Utility helpers */

export const STAGE_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  new: { label: 'Tiếp nhận mới', color: '#3B82F6', emoji: '🆕' },
  interested: { label: 'Đang tư vấn', color: '#8B5CF6', emoji: '💡' },
  survey_scheduled: { label: 'Đang chờ', color: '#F59E0B', emoji: '⏳' },
  potential: { label: 'Đã chốt hồ sơ', color: '#10B981', emoji: '⭐' },
  signed_design: { label: 'Deal đã thắng', color: '#C9A96E', emoji: '🏆' },
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

export function formatPricePerSqm(value?: number | null): string {
  if (!value) return '—';
  return `${value.toLocaleString('vi-VN')} ₫/m²`;
}

export function formatDealValue(value?: number | null): string {
  if (!value) return '—';
  if (value >= 1_000_000_000) {
    const v = value / 1_000_000_000;
    const s = v % 1 === 0 ? String(Math.round(v)) : String(v);
    return `${s} tỷ`;
  }
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(0)} triệu`;
  return `${value.toLocaleString('vi-VN')} ₫`;
}

export const PROPERTY_CLASS_LABELS: Record<string, { label: string; color: string }> = {
  luxury: { label: 'Hạng sang', color: '#C9A96E' },
  mid_range: { label: 'Trung bình', color: '#3B82F6' },
  budget: { label: 'Bình dân', color: '#6B7280' },
};

export const SEGMENT_LABELS: Record<string, string> = {
  villa: 'Biệt thự', townhouse: 'Nhà phố', apartment: 'Căn hộ',
  shophouse: 'Shophouse', office: 'Office',
};

export const PLAN_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  online: { label: 'Tư vấn Online', color: '#3B82F6' },
  offline: { label: 'Tư vấn Offline', color: '#10B981' },
  survey: { label: 'Khảo sát', color: '#F59E0B' },
  none: { label: 'Chưa có', color: '#6B7280' },
};

export const REGION_OPTIONS = [
  'Long An', 'Q7', 'Bình Chánh', 'Q1', 'Q2', 'Q9', 'Gò Vấp', 'Phú Nhuận', 'Thủ Đức', 'Quận khác',
];

export const TAG_COLORS: Record<string, string> = {
  'Deal': '#10B981',
  'Ưu tiên': '#F59E0B',
  'VIP': '#C9A96E',
  'Mới': '#3B82F6',
  'Cần follow-up': '#EF4444',
};

export const ALL_TAGS = ['Deal', 'Ưu tiên', 'VIP', 'Mới', 'Cần follow-up'];
