/**
 * Nhãn + quy tắc phía giao diện cho «Dữ liệu chung» (/du-lieu-chung, BGĐ) và
 * «Đối chiếu» (/doi-chieu, trưởng phòng) — 20/11/2026.
 *
 * Quyền ở đây PHẢI khớp backend (backend/app/api/du_lieu_chung.py):
 *  • /du-lieu-chung: VAI_TRO_BGD = admin + executive.
 *  • /doi-chieu: BGĐ mọi phòng; trưởng phòng (VAI_TRO_TRUONG_PHONG) chỉ phòng mình.
 * Màu chỉ qua biến theme, KHÔNG dùng --danger: trang này đo, không phạt.
 */

import type {
  MucDuLieu, NhacCaiAppKetQua, NhacDuLieuChungKetQua, PhongDuLieu, TrangThaiHoSo,
} from '@/lib/api';
import { laTruongPhong } from '@/lib/roles';
import { STAGE_CONFIG } from '@/lib/utils';
import { STAGE_LABELS } from '@/components/projects/shared';

type NguoiDung = { role?: string | null; department?: string | null } | null | undefined;

export const VAI_TRO_DU_LIEU_CHUNG = ['admin', 'executive'];

export const PHONG_DU_LIEU: PhongDuLieu[] = ['SALES', 'DESIGN', 'PURCHASING', 'OPS'];

export const TEN_PHONG: Record<PhongDuLieu, string> = {
  SALES: 'Kinh doanh',
  DESIGN: 'Thiết kế',
  PURCHASING: 'Dự toán – Thu mua',
  OPS: 'Thi công / Giám sát',
};

export function laBGD(u: NguoiDung): boolean {
  return u?.role === 'admin' || u?.role === 'executive';
}

/** Phòng của người dùng theo mã dữ liệu chung — 'PM' cũ coi là OPS. */
export function phongCuaNguoi(u: NguoiDung): PhongDuLieu | null {
  const d = (u?.department || '').toUpperCase();
  const p = d === 'PM' ? 'OPS' : d;
  return (PHONG_DU_LIEU as string[]).includes(p) ? (p as PhongDuLieu) : null;
}

/** Ai mở được /doi-chieu: BGĐ, hoặc trưởng phòng của 1 trong 4 phòng.
 *  Dùng bộ phận GỐC (laTruongPhong): bộ phận 'PM' cũ KHÔNG được coi là trưởng phòng OPS —
 *  khớp backend (_phong_doi_chieu / duoc_doi_giai_doan / phân công PIC đều đọc bộ phận gốc),
 *  để trang không bao giờ mời bấm việc backend sẽ từ chối. */
export function duocDoiChieu(u: NguoiDung): boolean {
  if (laBGD(u)) return true;
  return laTruongPhong(u) && phongCuaNguoi(u) !== null;
}

/** Executive chưa được đổi giai đoạn dự án (backend duoc_doi_giai_doan) —
 *  ẩn «Sai giai đoạn» / «Tạm dừng» của dự án và nút nhận dự án cũ về phòng. */
export function duocDoiGiaiDoanDuAn(u: NguoiDung): boolean {
  return u?.role !== 'executive';
}

/** Mã lỗi từng dòng của POST /doi-chieu → câu tiếng Việt. Lỗi khác (HTTPException
 *  của luồng đổi giai đoạn / phân công PIC) backend đã trả sẵn câu tiếng Việt. */
const NHAN_LOI_DOI_CHIEU: Record<string, string> = {
  khong_phai_ho_so_cua_phong: 'không thuộc hồ sơ phòng này',
  khong_ton_tai: 'hồ sơ không còn tồn tại',
  khong_ap_dung_cho_lead: 'lead không áp dụng kết quả này',
  giai_doan_khong_hop_le: 'giai đoạn không hợp lệ',
  chua_xep_chi_nhan_giai_doan: 'dự án chưa xếp chỉ nhận về một giai đoạn',
  chi_nhan_ve_giai_doan_cua_phong: 'chỉ nhận về giai đoạn của phòng mình',
  khong_co_quyen_doi_giai_doan: 'bạn chưa có quyền đổi giai đoạn dự án',
  pic_khong_hop_le: 'người phụ trách không thuộc phòng hoặc đã nghỉ',
};

export function nhanLoiDoiChieu(ma: string): string {
  if (NHAN_LOI_DOI_CHIEU[ma]) return NHAN_LOI_DOI_CHIEU[ma];
  // Mã lạ dạng snake_case (chưa có nhãn) thì không in thô ra màn hình.
  return /^[a-z0-9_]+$/.test(ma) ? 'không lưu được dòng này' : ma;
}

export const NHAN_MUC: Record<MucDuLieu, string> = {
  sat: 'Sát',
  can_bo_sung: 'Cần bổ sung',
  chua_phan_anh: 'Chưa phản ánh',
  it_ho_so: 'Ít hồ sơ',
  khong_co_ho_so: 'Không có hồ sơ',
};

export function mauMuc(muc: MucDuLieu | null | undefined): string {
  switch (muc) {
    case 'sat': return 'var(--success)';
    case 'can_bo_sung': return 'var(--gold-500)';
    case 'chua_phan_anh': return 'var(--warning)';
    default: return 'var(--text-disabled)';
  }
}

export const NHAN_TRANG_THAI: Record<TrangThaiHoSo, string> = {
  co_dau_vet: 'Có dấu vết',
  chua_cap_nhat: 'Chưa cập nhật',
  chua_ro: 'Chưa rõ',
  dang_cho: 'Đang chờ',
  lech: 'Lệch',
};

export const THU_TU_TRANG_THAI: TrangThaiHoSo[] = ['co_dau_vet', 'chua_cap_nhat', 'chua_ro', 'dang_cho', 'lech'];

export function mauTrangThai(t: TrangThaiHoSo): string {
  switch (t) {
    case 'co_dau_vet': return 'var(--success)';
    case 'chua_cap_nhat': return 'var(--info)';
    case 'dang_cho': return 'var(--text-muted)';
    case 'lech': return 'var(--warning)';
    default: return 'var(--text-tertiary)';
  }
}

export const NHAN_LECH: Record<string, string> = {
  L1: 'CRM chậm hơn thực tế',
  L2: 'Dự án trỏ tới lead chưa thắng',
  L3: 'Deal đã thắng chưa có dự án',
  L4: 'Tiến độ 100% nhưng chưa hoàn thành',
  L5: 'Ngày tháng mâu thuẫn với giai đoạn',
};

export const NHAN_KET_QUA: Record<string, string> = {
  dung: 'Đúng',
  sai_giai_doan: 'Sai giai đoạn',
  tam_dung: 'Tạm dừng',
  da_xong: 'Đã xong',
};

const NHAN_DAU_VET: Record<string, string> = {
  task_activity: 'báo cáo việc',
  bao_cao: 'báo cáo việc',
  viec_bat_dau: 'nhận việc',
  viec_xong: 'xong việc',
  file: 'tệp bản vẽ',
  tep: 'tệp bản vẽ',
  tai_lieu: 'tài liệu',
  anh: 'ảnh công trình',
  vat_tu: 'vật tư',
  bao_gia: 'báo giá',
  doi_chieu: 'đối chiếu',
  doi_giai_doan: 'đổi giai đoạn',
  activity: 'hoạt động',
  note: 'ghi chú',
  call: 'cuộc gọi',
  meeting: 'gặp khách',
  survey: 'khảo sát',
  email: 'email',
  stage_change: 'đổi giai đoạn',
  cskh: 'chăm sóc khách',
  tao_moi: 'tạo mới',
};

export function nhanDauVet(loai?: string | null): string {
  if (!loai) return '';
  return NHAN_DAU_VET[loai] || loai.replace(/_/g, ' ');
}

/** Nhãn giai đoạn cho cả dự án lẫn lead (key thô → tiếng Việt). */
export function nhanGiaiDoan(key?: string | null): string {
  if (!key) return '—';
  if (key === 'paused') return 'Chưa xếp giai đoạn';
  return STAGE_LABELS[key] || STAGE_CONFIG[key]?.label || key;
}

/** Giai đoạn dự án thuộc phòng — dùng cho «Nhận dự án cũ về phòng». */
export const GIAI_DOAN_THEO_PHONG: Record<Exclude<PhongDuLieu, 'SALES'>, string[]> = {
  DESIGN: ['design'],
  PURCHASING: ['quotation', 'procurement'],
  OPS: ['construction', 'acceptance'],
};

/** Đổi giai đoạn dự án trên /doi-chieu (không có «Hoàn thành»: đã xong thì dồn về BGĐ). */
export const GIAI_DOAN_DU_AN = ['design', 'quotation', 'procurement', 'construction', 'acceptance'];

/** Lead: chỉ đổi trong nhóm đang mở hoặc Ngủ đông; Mất/Thắng phải sang /leads. */
export const GIAI_DOAN_LEAD = ['new', 'interested', 'surveyed', 'survey_scheduled', 'potential', 'dormant'];

/** Chip 1 chạm phân loại dữ liệu cũ (admin). */
export const GIAI_DOAN_PHAN_LOAI = ['design', 'quotation', 'procurement', 'construction', 'acceptance', 'completed', 'paused'];

export function linkHoSo(loai: 'du_an' | 'lead', id: string): string {
  return loai === 'lead' ? `/leads?id=${encodeURIComponent(id)}` : `/projects?id=${encodeURIComponent(id)}`;
}

const NGAY_VN = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' });

/** Ngày theo giờ VN dạng YYYY-MM-DD (chuỗi ISO không có múi coi là UTC như backend). */
export function ngayVN(iso: string | Date): string {
  return NGAY_VN.format(typeof iso === 'string' ? docGio(iso) : iso);
}

/** Backend lưu giờ naive = UTC; thêm 'Z' nếu thiếu múi để trình duyệt không hiểu nhầm giờ máy. */
export function docGio(iso: string): Date {
  const coMui = /[zZ]|[+-]\d\d:?\d\d$/.test(iso);
  return new Date(coMui || iso.length <= 10 ? iso : `${iso}Z`);
}

export function laHomNay(iso?: string | null): boolean {
  if (!iso) return false;
  return ngayVN(iso) === ngayVN(new Date());
}

export function gioPhut(iso?: string | null): string {
  if (!iso) return '';
  return docGio(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });
}

export function ngayThang(iso?: string | null): string {
  if (!iso) return '—';
  return docGio(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh' });
}

/** «Hôm nay» / «Hôm qua» / «N ngày trước». */
export function baoLau(iso?: string | null): string {
  if (!iso) return '';
  const ngay = Math.floor((Date.now() - docGio(iso).getTime()) / 86_400_000);
  if (ngay <= 0) return 'hôm nay';
  if (ngay === 1) return 'hôm qua';
  return `${ngay} ngày trước`;
}

const LY_DO_BO_QUA: Record<string, string> = {
  da_nhac_hom_nay: 'đã nhắc hôm nay rồi',
  khong_co_truong_phong: 'phòng chưa có trưởng phòng',
  vuot_2_tin: 'người nhận đã đủ 2 tin hôm nay',
};

/** Kênh một tin nhắc đã đi: chuông luôn có; thêm Telegram / thông báo máy nếu người nhận đã bật. */
export function kenhDaGui(g: { telegram: boolean; thong_bao_may?: boolean }): string {
  const kenh = ['chuông'];
  if (g.telegram) kenh.push('Telegram');
  if (g.thong_bao_may) kenh.push('thông báo máy');
  return kenh.join(' + ');
}

/** Câu báo kết quả sau khi gửi nhắc + kiểu toast tương ứng — ghi rõ từng người nhận qua kênh nào (21/11/2026). */
export function tomTatNhac(kq: NhacDuLieuChungKetQua): { chu: string; kieu: 'success' | 'warning' } {
  const phan: string[] = [];
  if (kq.da_gui.length > 0) {
    const ten = kq.da_gui.map(g => {
      const chiChuong = !g.telegram && !g.thong_bao_may;
      return `${g.nguoi} (${kenhDaGui(g)}${chiChuong ? ' — chỉ thấy khi mở app' : ''})`;
    });
    phan.push(`Đã gửi cho ${ten.join(', ')}`);
  }
  for (const b of kq.bo_qua) {
    const tenPhong = TEN_PHONG[b.phong as PhongDuLieu] || (b.phong === 'chua_xep' ? 'Dự án cũ' : b.phong);
    phan.push(`${tenPhong}: bỏ qua vì ${LY_DO_BO_QUA[b.ly_do] || b.ly_do}`);
  }
  if (phan.length === 0) return { chu: 'Không có ai để nhắc', kieu: 'warning' };
  return { chu: phan.join(' · '), kieu: kq.da_gui.length > 0 ? 'success' : 'warning' };
}

/** Câu báo kết quả «Nhắc cài app & bật thông báo». */
export function tomTatNhacCaiApp(kq: NhacCaiAppKetQua): { chu: string; kieu: 'success' | 'warning' } {
  if (kq.da_gui === 0) {
    return {
      chu: kq.bo_qua_da_nhac > 0
        ? `Hôm nay đã nhắc ${kq.bo_qua_da_nhac} người này rồi — mai nhắc tiếp.`
        : 'Không còn ai cần nhắc cài app.',
      kieu: 'warning',
    };
  }
  const phan = [`Đã nhắc ${kq.da_gui} người cài app và bật thông báo (vào chuông${kq.qua_telegram > 0 ? `, ${kq.qua_telegram} người nhận thêm qua Telegram` : ''})`];
  if (kq.bo_qua_da_nhac > 0) phan.push(`bỏ qua ${kq.bo_qua_da_nhac} người đã nhắc hôm nay`);
  return { chu: phan.join(' · '), kieu: 'success' };
}
