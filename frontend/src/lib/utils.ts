/** Utility helpers */

// Màu stage qua CSS var để mỗi theme tự chọn bảng phù hợp:
// theme tối giữ bộ rực cũ; theme sáng (Ngoài trời) override sang bộ đất ấm luxury (globals.css).
export const STAGE_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  new: { label: 'Tiếp nhận mới', color: 'var(--stage-new)', emoji: '🆕' },
  interested: { label: 'Đang tư vấn', color: 'var(--stage-interested)', emoji: '💡' },
  // Đổi tên 05/09/2026 theo quy trình thật của team KD (key giữ nguyên — đổi key
  // là phải migrate toàn bộ lead + máy trạng thái, không đáng).
  survey_scheduled: { label: 'Đã gửi báo giá', color: 'var(--stage-survey)', emoji: '📤' },
  potential: { label: 'Đang đàm phán', color: 'var(--stage-potential)', emoji: '🤝' },
  signed_design: { label: 'Deal đã thắng', color: 'var(--stage-signed)', emoji: '🏆' },
  lost: { label: 'Mất', color: 'var(--stage-lost)', emoji: '❌' },
  dormant: { label: 'Ngủ đông', color: 'var(--stage-dormant)', emoji: '😴' },
};

export const SOURCE_LABELS: Record<string, string> = {
  facebook: 'Facebook',
  zalo: 'Zalo',
  website: 'Website',
  referral: 'Giới thiệu',
  tiktok: 'TikTok',
  hotline: 'Hotline',
  office_visit: 'Khách đến văn phòng',
  // Nguồn do Zalo listener / form marketing tự gắn — không có trong form Tạo Lead
  // nhưng đã có 3 lead prod mang giá trị này và đang hiện mã thô (QC 05/09).
  google_form: 'Google Form',
  other: 'Khác',
};

/**
 * Nhu cầu của khách (cột `segment` trong DB — giữ tên cột, đổi ý nghĩa 05/09/2026).
 * Trước đây ô này tên «Phân khúc» và lặp y hệt «Loại BĐS» (biệt thự/nhà phố/căn hộ…)
 * nên không mang thêm thông tin gì. Ba giá trị đầu là bộ mới; các key BĐS cũ giữ lại
 * để lead nhập trước ngày đổi vẫn hiện ra tiếng Việt thay vì mã trần trụi.
 */
export const NEEDS_LABELS: Record<string, string> = {
  thi_cong_noi_that: 'Thi công nội thất',
  cai_tao: 'Cải tạo',
  xay_moi: 'Xây mới',
  // ── giá trị cũ (chỉ để hiển thị, không còn cho chọn) ──
  villa: 'Biệt thự',
  townhouse: 'Nhà phố',
  apartment: 'Căn hộ',
  shophouse: 'Shophouse',
  office: 'Văn phòng',
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
  if (value == null) return '—';
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1)} tỷ`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(0)} triệu`;
  return `${value.toLocaleString('vi-VN')} đ`;
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
  if (value == null) return '—';
  return `${value.toLocaleString('vi-VN')} đ/m²`;
}

export function formatDealValue(value?: number | null): string {
  if (value == null) return '—';
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) {
    const v = abs / 1_000_000_000;
    // tỷ: tối đa 1 chữ số thập phân (7.071341221 → 7.1); tròn tỷ thì bỏ ".0".
    const s = v % 1 === 0 ? String(Math.round(v)) : v.toFixed(1);
    return `${sign}${s} tỷ`;
  }
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(0)} triệu`;
  return `${value.toLocaleString('vi-VN')} đ`;
}

export const PROPERTY_CLASS_LABELS: Record<string, { label: string; color: string }> = {
  luxury: { label: 'Hạng sang', color: '#C9A96E' },
  mid_range: { label: 'Trung bình', color: '#3B82F6' },
  budget: { label: 'Bình dân', color: '#6B7280' },
};

export const SEGMENT_LABELS: Record<string, string> = {
  villa: 'Biệt thự', townhouse: 'Nhà phố', apartment: 'Căn hộ',
  shophouse: 'Shophouse', office: 'Văn phòng',
};

export const PLAN_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  online: { label: 'Tư vấn Online', color: '#3B82F6' },
  offline: { label: 'Tư vấn Offline', color: '#10B981' },
  survey: { label: 'Khảo sát', color: '#F59E0B' },
  none: { label: 'Chưa có', color: '#6B7280' },
};

/** Ba mức ngân sách của lead — PHẢI khớp NGAN_SACH_KHOANG ở backend
 *  (app/models/lead.py). Chốt 22/09/2026. */
export const NGAN_SACH_OPTIONS = [
  { value: 'duoi_200', label: 'Dưới 200 triệu' },
  { value: 'tu_200_500', label: 'Từ 200–500 triệu' },
  { value: 'tren_500', label: 'Trên 500 triệu' },
];

export const NGAN_SACH_LABELS: Record<string, string> = Object.fromEntries(
  NGAN_SACH_OPTIONS.map(o => [o.value, o.label]),
);

/** 34 đơn vị hành chính cấp tỉnh SAU SÁP NHẬP — Nghị quyết 202/2025/QH15,
 *  hiệu lực 01/07/2025 (28 tỉnh + 6 thành phố trực thuộc trung ương).
 *
 *  Xếp thành phố trực thuộc TW lên trước, TP. Hồ Chí Minh đứng đầu vì gần như
 *  toàn bộ khách của JAMA ở đây (đo 22/09: 95/96 lead có khu vực là quận của
 *  TP.HCM hoặc tỉnh lân cận). 28 tỉnh còn lại xếp A→Z cho dễ tìm.
 *
 *  LƯU Ý dữ liệu cũ: 96 lead đang lưu tên QUẬN (Q1, Q7, Gò Vấp, «Quận khác»…)
 *  và tên tỉnh TRƯỚC sáp nhập (Long An → nay thuộc Tây Ninh; Khanh Hoa). Những
 *  giá trị đó KHÔNG có trong danh sách này — bộ lọc tự thêm chúng vào để vẫn
 *  lọc được (xem tuyChonKhuVuc), và cố ý KHÔNG tự ghi đè dữ liệu cũ. */
export const TINH_THANH_TRUC_THUOC_TW = [
  'TP. Hồ Chí Minh', 'Hà Nội', 'Hải Phòng', 'Đà Nẵng', 'Cần Thơ', 'Huế',
];

export const TINH_THANH_TINH = [
  'An Giang', 'Bắc Ninh', 'Cà Mau', 'Cao Bằng', 'Điện Biên', 'Đắk Lắk',
  'Đồng Nai', 'Đồng Tháp', 'Gia Lai', 'Hà Tĩnh', 'Hưng Yên', 'Khánh Hòa',
  'Lai Châu', 'Lâm Đồng', 'Lạng Sơn', 'Lào Cai', 'Nghệ An', 'Ninh Bình',
  'Phú Thọ', 'Quảng Ngãi', 'Quảng Ninh', 'Quảng Trị', 'Sơn La', 'Tây Ninh',
  'Thái Nguyên', 'Thanh Hóa', 'Tuyên Quang', 'Vĩnh Long',
];

export const REGION_OPTIONS = [...TINH_THANH_TRUC_THUOC_TW, ...TINH_THANH_TINH];

/** Danh sách cho ô lọc Khu vực: 34 tỉnh/thành + những giá trị CŨ đang thực sự
 *  có trong dữ liệu, để lead nhập trước 22/09 vẫn lọc ra được. */
export function tuyChonKhuVuc(dangCoTrongDuLieu: (string | null | undefined)[]): string[] {
  const chuan = new Set(REGION_OPTIONS);
  const cu = Array.from(new Set(dangCoTrongDuLieu.filter((x): x is string => !!x && !chuan.has(x)))).sort();
  return [...REGION_OPTIONS, ...cu];
}


export const TAG_COLORS: Record<string, string> = {
  'Deal': '#10B981',
  'Ưu tiên': '#F59E0B',
  'VIP': '#C9A96E',
  'Mới': '#3B82F6',
  'Cần follow-up': '#EF4444',
};

export const ALL_TAGS = ['Deal', 'Ưu tiên', 'VIP', 'Mới', 'Cần follow-up'];
