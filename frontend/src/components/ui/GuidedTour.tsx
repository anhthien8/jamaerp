'use client';

/**
 * GuidedTour — hướng dẫn TỪNG BƯỚC theo đúng workflow của mỗi vai trò.
 *
 * Khác OnboardingChecklist (modal giới thiệu): tour này DẪN người dùng đi qua
 * từng trang theo trình tự công việc thật (từ đầu ca đến cuối ca), mỗi bước
 * tự điều hướng đến trang tương ứng + thẻ hướng dẫn nêu rõ "làm gì ở đây".
 *
 * KISS: không thư viện ngoài, không highlight DOM (dễ vỡ khi UI đổi) —
 * thẻ coach cố định góc phải dưới + tự chuyển trang là đủ để hiểu luồng.
 *
 * Kích hoạt: window.dispatchEvent(new CustomEvent('jama:start-tour'))
 * (OnboardingChecklist bước cuối + nút "Xem lại hướng dẫn" ở Cài đặt).
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export const START_TOUR_EVENT = 'jama:start-tour';

export function startGuidedTour() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(START_TOUR_EVENT));
  }
}

interface TourStep {
  href: string;
  icon: string;
  title: string;
  /** Việc cần làm tại trang này — nói như đang kèm việc thật */
  points: string[];
}

/** Workflow đầu-đến-cuối theo NGHIỆP VỤ từng vai trò (không phải danh sách trang) */
const ROLE_TOURS: Record<string, TourStep[]> = {
  data_entry: [
    { href: '/', icon: '🌅', title: 'Bắt đầu ngày: xem Tổng quan', points: [
      'Khối "Việc cần làm hôm nay" liệt kê khách quá hạn cần gọi lại ngay',
      'Mục tiêu mỗi sáng: không còn khách nào quá hạn 3 ngày chưa liên hệ',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Vào ca — nhanh nhất là Telegram', points: [
      'Cách chính: nhắn /checkin cho bot Telegram (công trường: /checkin [Mã dự án] kèm GPS)',
      'Lần đầu phải liên kết Telegram: Cài đặt → nhắn /id cho bot → dán số vào → Lưu → /start',
      'Nút "✅ Vào ca" trên web dùng khi đang ngồi máy tính',
      'Công của bạn tự tính vào bảng lương — quên tan ca hệ thống tự đóng 8h',
    ]},
    { href: '/leads', icon: '🔄', title: 'Quy trình CRM — nơi bạn sống cả ngày', points: [
      'Khách mới → bấm "+ Thêm Lead" (hoặc paste tin Zalo vào bot Telegram: /lead)',
      'Data do CSKH/trưởng nhóm giao cho bạn TỰ xuất hiện ở đây — không cần ai nhắn tay',
      'Sau MỖI cuộc gọi/gặp: mở thẻ khách → ghi chú lại nội dung',
      'Khách đồng ý bước tiếp → đổi giai đoạn ngay trên thẻ',
      '⚠️ "Deal đã thắng" tạo NGAY Khách hàng + Dự án + Hợp đồng và KHÔNG lùi được — chỉ chọn khi khách đã ký thật',
      'Lưu ý: khách bỏ bê 7 ngày sẽ bị hệ thống thu hồi giao người khác',
    ]},
    { href: '/quote-tool', icon: '💰', title: 'Khách hỏi giá? Trả lời trong 30 giây', points: [
      'Nhập diện tích + loại nhà → 3 phương án giá ngay',
      'Bấm "📋 Copy text gửi Zalo" → dán thẳng vào Zalo cho khách',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Khách ký xong — theo dõi dự án', points: [
      'Khách ký HĐ thiết kế → hệ thống TỰ tạo dự án + 19 đầu việc, bạn không nhập lại gì',
      'Thanh 5 khối trên thẻ dự án = dự án đang ở phòng nào',
    ]},
    { href: '/attendance', icon: '🏖️', title: 'Cuối ngày & quyền lợi của bạn', points: [
      'Bấm "🏁 Tan ca" trước khi về — quá 8h tự tính tăng ca chờ duyệt',
      'Tab "Nghỉ phép": xin nghỉ tại đây, leader duyệt trong 24h',
      'Tab "Phiếu lương": xem lương của chính bạn các kỳ đã chi',
    ]},
  ],
  leader: [
    { href: '/', icon: '🌅', title: 'Sáng: nắm team trong 2 phút', points: [
      'Tổng quan team: leads quá hạn, hiệu suất từng nhân viên',
    ]},
    { href: '/approvals', icon: '✅', title: 'Duyệt đơn — việc quan trọng nhất của leader', points: [
      'Đơn nghỉ phép, tăng ca của team chờ bạn tại đây (quá 24h sẽ bị nhắc + chuyển sếp)',
      'Đang di chuyển? Duyệt ngay trên Telegram: /choduyet',
    ]},
    { href: '/leads', icon: '🔄', title: 'Phân lead & giữ nhịp team', points: [
      'Lead mới chưa ai nhận → mở thẻ → chọn "Nhân viên phụ trách"',
      'Soi thẻ có nhãn "Quá hạn" — nhắc nhân viên trước khi hệ thống thu hồi',
    ]},
    { href: '/hr', icon: '👥', title: 'Đội của bạn', points: [
      'Nút "Đội nhóm" trên trang Nhân sự = sơ đồ đội: trưởng nhóm → thành viên từng đội',
      'Danh sách chỉ hiện người trong phạm vi của bạn',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Bảng công + OT của team', points: [
      'Bảng công team ở cuối trang; ca có ⚠️ là quên tan ca — cần bạn xác nhận',
      'Duyệt/từ chối tăng ca ngay tại khối "OT chờ duyệt"',
    ]},
    { href: '/kpi', icon: '📈', title: 'KPI & kèm cặp', points: [
      'Tab "Đội nhóm": điểm từng người theo kỳ — thấy ai tụt thì hẹn 1-1',
      'Cuối tuần xem Báo cáo để chuẩn bị họp team',
    ]},
  ],
  supervisor: [
    { href: '/', icon: '🌅', title: 'Tổng quan Giám sát', points: [
      'Khối "🏗️ Dự án đang đến phòng bạn": ưu tiên quá hạn → cận hạn → HĐ lớn',
      'Vai trò Giám sát bao gồm cả Thiết kế, Thu mua và Dự án',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Điều phối & thi công dự án — trang chính', points: [
      'Thẻ dự án có thanh 5 khối = đang ở giai đoạn nào; badge 🔴/🟠 = độ gấp',
      'Mở dự án → chuyển "Theo phòng ban" để thấy việc từng khối (Thiết kế/Thu mua/Thi công)',
      'Làm xong việc nào đổi trạng thái việc đó — thanh tiến độ tự chạy',
      'Upload bản vẽ/3D/ảnh vào từng đầu việc (ghi chú + đính kèm)',
    ]},
    { href: '/inventory', icon: '📦', title: 'Kho vật tư', points: [
      'Cảnh báo 🔴 = tồn thấp; duyệt yêu cầu vật tư (hoặc ngay trên Telegram)',
    ]},
    { href: '/quotations', icon: '📋', title: 'Báo giá', points: [
      'Bóc tách vật tư xong → tạo báo giá tại đây, đính kèm file',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & hiện trường', points: [
      'Tại công trường: Telegram /checkin [Mã] kèm GPS; /baocao gửi ảnh tiến độ',
      'Vào ca/Tan ca, nghỉ phép, phiếu lương đều ở trang này',
      'Nắng chói khó đọc? Bật "☀️ NGOÀI TRỜI" ở đáy menu — giao diện sáng cho công trường',
    ]},
  ],
  accountant: [
    { href: '/', icon: '🌅', title: 'Tổng quan tài chính', points: [
      'Công nợ phải thu + hợp đồng đến hạn thanh toán hiện ngay đầu trang',
    ]},
    { href: '/accounting', icon: '💰', title: 'Sổ thu chi hằng ngày', points: [
      'Ghi phiếu thu/chi: "+ Giao dịch mới", gắn vào dự án để P&L đúng',
      'Tab Công nợ: soi nhóm đỏ >90 ngày trước',
    ]},
    { href: '/approvals', icon: '✅', title: 'Duyệt tạm ứng & vật tư', points: [
      'Tạm ứng lương nhân viên chờ bạn duyệt ở đây (>5 triệu cần thêm sếp)',
    ]},
    { href: '/attendance', icon: '🧾', title: 'Chốt công cuối tháng', points: [
      'Mùng 1 hệ thống nhắc: rà ca ⚠️ quên tan ca trước khi tính lương',
    ]},
    { href: '/hr', icon: '👥', title: 'Nhân sự & bảng lương', points: [
      'Xử lý nghỉ việc (hệ thống tự bàn giao lead) — TẠO tài khoản mới là việc của admin',
      'Chia đội: sang "Quản lý tài khoản" → khối "Đội nhóm" — chỉ admin/kế toán được chuyển người giữa các đội',
      'Quy trình lương: Sinh bảng lương → Trình sếp duyệt (khóa kỳ) → Chi → phiếu lương tự gửi Telegram riêng từng người',
    ]},
    { href: '/pl', icon: '📈', title: 'Lãi/Lỗ', points: [
      'P&L theo dự án/tháng — chỉ bạn và Ban Giám đốc thấy trang này',
    ]},
  ],
  admin: [
    { href: '/', icon: '🌅', title: 'Tổng quan điều hành', points: [
      'KPI toàn công ty; mỗi sáng bot cũng gửi báo cáo vào Telegram cho bạn',
    ]},
    { href: '/approvals', icon: '✅', title: 'Trung tâm phê duyệt', points: [
      'Nghỉ phép dài, tạm ứng lớn, BẢNG LƯƠNG chờ bạn duyệt tại đây',
      'Duyệt lương xong = khóa kỳ — không ai sửa được công/hoa hồng kỳ đó',
    ]},
    { href: '/leads', icon: '🔄', title: 'Toàn cảnh kinh doanh', points: [
      'Xem mọi lead của 5 team; thẻ "Quá hạn" nhiều = team đó cần chấn chỉnh',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Toàn cảnh dự án', points: [
      'Sắp theo ưu tiên: quá hạn → cận hạn → HĐ lớn — nhìn là biết dồn lực đâu',
    ]},
    { href: '/hr', icon: '👥', title: 'Nhân sự', points: [
      'Tạo tài khoản, nghỉ việc (tự bàn giao lead), xem audit log thao tác nhạy cảm',
      'Nút "Đội nhóm" = sơ đồ đội toàn công ty (trưởng nhóm → thành viên)',
    ]},
    { href: '/users', icon: '🧩', title: 'Quản lý tài khoản & chia đội', points: [
      'Khối "Đội nhóm": Tạo đội (tên + mã) → chọn Trưởng nhóm → tick thành viên → Lưu',
      'Đổi trưởng nhóm/giải tán đội cũng tại đây — giải tán vẫn giữ người và lịch sử',
      'Phân quyền chi tiết từng vai trò: trang Phân quyền (menu Quản trị)',
    ]},
    { href: '/settings', icon: '⚙️', title: 'Cài đặt hệ thống', points: [
      'Nhóm Telegram công ty, AI model, sao lưu, tự động hóa CSKH — tất cả ở đây',
      'Thẻ "Khóa AI cá nhân": ai muốn AI chạy bằng key Groq riêng thì dán vào (không bắt buộc)',
    ]},
  ],
  // ── Vai trò tùy chỉnh (khớp role_key trong system_settings.custom_roles) ──
  // Thiếu key ở đây = rơi về tour data_entry SAI nghiệp vụ (QA 15/08/2026).
  sale_leader: [
    { href: '/', icon: '🌅', title: 'Sáng: nắm nhóm trong 2 phút', points: [
      'Tổng quan nhóm bạn: leads quá hạn, hiệu suất từng sale trong nhóm',
    ]},
    { href: '/leads', icon: '🔄', title: 'Nhận data & chia cho sale — việc chính của bạn', points: [
      'CSKH giao data về nhóm bạn → thẻ tự xuất hiện trong pipeline',
      'Mở thẻ → "Nhân viên phụ trách" → chọn sale (danh sách chỉ hiện người trong nhóm bạn)',
      'Soi thẻ "Quá hạn" — nhắc sale trước khi hệ thống thu hồi giao người khác',
    ]},
    { href: '/hr', icon: '👥', title: 'Sơ đồ đội của bạn', points: [
      'Nút "Đội nhóm" = sơ đồ đội: bạn là trưởng nhóm, dưới là thành viên',
      'Muốn thêm/bớt người trong đội → báo admin hoặc kế toán (chỉ họ được chuyển đội)',
    ]},
    { href: '/approvals', icon: '✅', title: 'Duyệt đơn của nhóm', points: [
      'Nghỉ phép, tăng ca của sale nhóm bạn chờ tại đây (quá 24h sẽ bị nhắc + chuyển sếp)',
      'Đang di chuyển? Duyệt ngay trên Telegram: /choduyet',
    ]},
    { href: '/kpi', icon: '📈', title: 'KPI nhóm & kèm cặp', points: [
      'Tab "Đội nhóm": điểm từng sale theo kỳ — thấy ai tụt thì hẹn 1-1',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi của bạn', points: [
      'Vào ca/Tan ca, xin nghỉ phép, xem phiếu lương của chính bạn tại đây',
    ]},
  ],
  admin_cskh: [
    { href: '/', icon: '🌅', title: 'Bắt đầu ngày', points: [
      'Khối "Việc cần làm hôm nay": data mới chưa giao, khách quá hạn liên hệ',
    ]},
    { href: '/leads', icon: '📥', title: 'Nhập data từ marketing', points: [
      'Khách mới → "+ Thêm Lead" (hoặc paste tin Zalo vào bot Telegram: /lead)',
      'Điền đủ SĐT + nguồn — hệ thống tự chấm điểm AI cho từng lead',
    ]},
    { href: '/leads', icon: '🤝', title: 'Giao data cho các nhóm', points: [
      'Mở thẻ → "Nhân viên phụ trách" → chọn trưởng nhóm (họ tự chia tiếp trong nhóm)',
      'SĐT khách tự che với người ngoài phạm vi — cứ giao, không lo lộ data',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi của bạn', points: [
      'Vào ca/Tan ca, xin nghỉ phép, xem phiếu lương tại đây',
    ]},
  ],
  quan_ly_du_an: [
    { href: '/', icon: '🌅', title: 'Tổng quan dự án', points: [
      'Khối "🏗️ Dự án đang đến phòng bạn": ưu tiên quá hạn → cận hạn → HĐ lớn',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Điều phối dự án — trang chính của bạn', points: [
      'Thẻ dự án có thanh 5 khối = đang ở giai đoạn nào; badge 🔴/🟠 = độ gấp',
      'Mở dự án → "Theo phòng ban" để thấy việc từng khối (Thiết kế/Thu mua/Thi công)',
      'Giao việc, đổi trạng thái, upload tài liệu ngay trên từng đầu việc',
    ]},
    { href: '/inventory', icon: '📦', title: 'Kho vật tư', points: [
      'Cảnh báo 🔴 = tồn thấp; duyệt yêu cầu vật tư của công trường',
    ]},
    { href: '/quotations', icon: '📋', title: 'Báo giá thi công', points: [
      'Bóc tách vật tư xong → tạo báo giá, đính kèm file',
    ]},
    { href: '/approvals', icon: '✅', title: 'Phê duyệt', points: [
      'Đơn nghỉ phép/đề xuất của anh em công trường chờ bạn tại đây',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi', points: [
      'Vào ca/Tan ca, nghỉ phép, phiếu lương — công trường dùng Telegram /checkin [Mã] kèm GPS',
      'Nắng chói khó đọc? Bật "☀️ NGOÀI TRỜI" ở đáy menu — giao diện sáng cho công trường',
    ]},
  ],
  thiet_ke: [
    { href: '/', icon: '🌅', title: 'Việc của bạn hôm nay', points: [
      'Đầu việc thiết kế đang chờ bạn hiện ngay trang đầu',
    ]},
    { href: '/projects', icon: '🎨', title: 'Việc thiết kế trong dự án', points: [
      'Mở dự án → lọc việc phòng Thiết kế — chỉ sửa được việc giao cho bạn',
      'Upload bản vẽ/3D/moodboard vào từng đầu việc (ghi chú + đính kèm)',
      'Làm xong đổi trạng thái — phòng tiếp theo tự nhận việc, không cần nhắn tay',
    ]},
    { href: '/quotations', icon: '📋', title: 'Xem phạm vi đã bán', points: [
      'Xem báo giá để biết khách đã chốt hạng mục gì — thiết kế đúng phạm vi, không vẽ lố',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi', points: [
      'Vào ca/Tan ca, xin nghỉ phép, xem phiếu lương tại đây',
    ]},
  ],
  giam_sat_thi_cong: [
    { href: '/', icon: '🌅', title: 'Việc hiện trường hôm nay', points: [
      'Đầu việc thi công đang chờ bạn hiện ngay trang đầu',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Cập nhật tiến độ thi công', points: [
      'Làm xong hạng mục nào đổi trạng thái hạng mục đó — thanh tiến độ tự chạy',
      'Ảnh hiện trường: gửi vào nhóm Telegram bằng /baocao (ảnh lưu link, không nặng hệ thống)',
    ]},
    { href: '/inventory', icon: '📦', title: 'Vật tư công trường', points: [
      'Thiếu vật tư → tạo yêu cầu tại đây, thu mua/PM duyệt là có hàng',
    ]},
    { href: '/attendance', icon: '📍', title: 'Chấm công hiện trường', points: [
      'Tại công trường: Telegram /checkin [Mã dự án] kèm GPS — không cần mở web',
      'Nghỉ phép, phiếu lương cũng xem tại trang này',
      'Nắng chói khó đọc? Bật "☀️ NGOÀI TRỜI" ở đáy menu — giao diện sáng cho công trường',
    ]},
  ],
  thu_mua: [
    { href: '/', icon: '🌅', title: 'Bắt đầu ngày', points: [
      'Việc thu mua đang chờ + cảnh báo tồn kho hiện ngay trang đầu',
    ]},
    { href: '/inventory', icon: '📦', title: 'Kho vật tư — trang chính của bạn', points: [
      'Cảnh báo 🔴 = tồn thấp cần nhập; nhập kho ghi tại đây để tồn đúng',
      'Duyệt yêu cầu vật tư từ công trường',
    ]},
    { href: '/suppliers', icon: '🏬', title: 'Nhà cung cấp & so giá', points: [
      'So giá cùng mặt hàng giữa các NCC + lịch sử giá — chọn chỗ rẻ có căn cứ',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Việc thu mua trong dự án', points: [
      'Dự án đến khối Thu mua → cập nhật trạng thái đặt hàng/giao hàng trên đầu việc',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi', points: [
      'Vào ca/Tan ca, xin nghỉ phép, xem phiếu lương tại đây',
    ]},
  ],
  executive: [
    { href: '/', icon: '🌅', title: 'Tổng quan điều hành', points: [
      'Doanh thu, leads mới, tỷ lệ chuyển đổi — cập nhật realtime',
    ]},
    { href: '/pl', icon: '📈', title: 'Lãi/Lỗ', points: [
      'P&L theo dự án và theo tháng — trang chỉ dành cho cấp điều hành',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Dự án theo ưu tiên', points: [
      'Quá hạn nổi đầu danh sách — câu hỏi cho giao ban: vì sao trễ?',
    ]},
    { href: '/reports', icon: '📊', title: 'Báo cáo', points: [
      'Hiệu suất theo team/nhân viên; thứ Hai bot gửi báo cáo tuần vào Telegram',
    ]},
  ],
};

function tourStepKey(role: string) {
  return `jama_tour_step_${role}`;
}
function tourActiveKey(role: string) {
  return `jama_tour_active_${role}`;
}

export default function GuidedTour() {
  const { user } = useAuth();
  const router = useRouter();
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);

  const role = user?.role || 'data_entry';
  const steps = ROLE_TOURS[role] || ROLE_TOURS.data_entry;

  // goTo: lưu bước + cờ active vào localStorage TRƯỚC khi điều hướng, vì Sidebar
  // (chứa GuidedTour) được render trong TỪNG page → router.push sẽ unmount trang cũ
  // và mount GuidedTour mới. Nhờ localStorage, instance mới tự khôi phục card (fix bug
  // "bấm xem lại chỉ nhảy về Tổng quan, không thấy hướng dẫn").
  const goTo = useCallback((index: number) => {
    const target = steps[index];
    if (!target) return;
    setStep(index);
    setActive(true);
    localStorage.setItem(tourStepKey(role), String(index));
    localStorage.setItem(tourActiveKey(role), '1');
    router.push(target.href);
  }, [steps, role, router]);

  // Khôi phục tour khi component mount (sau khi điều hướng sang trang mới)
  useEffect(() => {
    if (localStorage.getItem(tourActiveKey(role)) === '1') {
      const saved = parseInt(localStorage.getItem(tourStepKey(role)) || '0', 10);
      setStep(Number.isFinite(saved) && saved >= 0 && saved < steps.length ? saved : 0);
      setActive(true);
    }
  }, [role, steps.length]);

  // Lắng nghe sự kiện bắt đầu tour (từ OnboardingChecklist / nút Cài đặt) — cùng trang
  useEffect(() => {
    const handler = () => goTo(0);
    window.addEventListener(START_TOUR_EVENT, handler);
    return () => window.removeEventListener(START_TOUR_EVENT, handler);
  }, [goTo]);

  const finish = () => {
    setActive(false);
    localStorage.removeItem(tourStepKey(role));
    localStorage.removeItem(tourActiveKey(role));
    localStorage.setItem(`jama_onboarded_${role}`, 'true');
  };

  if (!active || !user) return null;

  const current = steps[step];
  const isLast = step === steps.length - 1;

  return (
    <div
      className="fixed z-[95] bottom-4 right-4 left-4 sm:left-auto sm:w-[380px] rounded-2xl shadow-2xl animate-in"
      style={{ background: 'var(--surface-1)', border: '1px solid rgba(201,169,110,0.45)' }}
      role="dialog"
      aria-label="Hướng dẫn theo vai trò"
    >
      {/* Progress */}
      <div className="h-1 rounded-t-2xl overflow-hidden bg-white/5">
        <div
          className="h-full transition-all"
          style={{ width: `${((step + 1) / steps.length) * 100}%`, background: 'linear-gradient(90deg, var(--gold-500), var(--gold-700))' }}
        />
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xl flex-shrink-0">{current.icon}</span>
            <h3 className="text-sm font-bold text-white leading-snug">{current.title}</h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full flex-shrink-0" style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>
            Bước {step + 1}/{steps.length}
          </span>
        </div>

        <ul className="space-y-1.5 mb-3">
          {current.points.map((p, i) => (
            <li key={i} className="flex gap-2 text-xs text-[var(--text-secondary)] leading-relaxed">
              <span className="text-[#C9A96E] flex-shrink-0 mt-0.5">•</span>
              <span>{p}</span>
            </li>
          ))}
        </ul>

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={finish}
            className="px-3 py-2 rounded-xl text-xs font-medium min-h-[40px]"
            style={{ color: 'var(--text-muted)' }}
          >
            Thoát hướng dẫn
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button
                onClick={() => goTo(step - 1)}
                className="px-4 py-2 rounded-xl text-xs font-semibold min-h-[40px] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
              >
                ← Quay lại
              </button>
            )}
            <button
              onClick={() => (isLast ? finish() : goTo(step + 1))}
              className="px-4 py-2 rounded-xl text-xs font-bold text-white min-h-[40px]"
              style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)' }}
            >
              {isLast ? '✅ Hoàn thành' : 'Tiếp theo →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
