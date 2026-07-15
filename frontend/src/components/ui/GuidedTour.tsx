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
    { href: '/attendance', icon: '⏱️', title: 'Vào ca', points: [
      'Bấm "✅ Vào ca" — công của bạn được tính tự động vào bảng lương',
      'Đi công trường? Dùng Telegram: /checkin [Mã dự án] kèm GPS',
    ]},
    { href: '/leads', icon: '🔄', title: 'Quy trình CRM — nơi bạn sống cả ngày', points: [
      'Khách mới → bấm "+ Thêm Lead" (hoặc paste tin Zalo vào bot Telegram: /lead)',
      'Sau MỖI cuộc gọi/gặp: mở thẻ khách → ghi chú lại nội dung',
      'Khách đồng ý bước tiếp → đổi giai đoạn ngay trên thẻ',
      'Lưu ý: khách bỏ bê 7 ngày sẽ bị hệ thống thu hồi giao người khác',
    ]},
    { href: '/quote-tool', icon: '💰', title: 'Khách hỏi giá? Trả lời trong 30 giây', points: [
      'Nhập diện tích + loại nhà → 3 phương án giá ngay',
      'Bấm "Sao chép" → dán thẳng vào Zalo cho khách',
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
    { href: '/attendance', icon: '⏱️', title: 'Bảng công + OT của team', points: [
      'Bảng công team ở cuối trang; ca có ⚠️ là quên tan ca — cần bạn xác nhận',
      'Duyệt/từ chối tăng ca ngay tại khối "OT chờ duyệt"',
    ]},
    { href: '/kpi', icon: '📈', title: 'KPI & kèm cặp', points: [
      'Tab Team: điểm từng người theo kỳ — thấy ai tụt thì hẹn 1-1',
      'Cuối tuần xem Báo cáo để chuẩn bị họp team',
    ]},
  ],
  designer: [
    { href: '/', icon: '🌅', title: 'Tổng quan của bạn', points: [
      'Khối "🏗️ Dự án đang đến phòng bạn" — việc thiết kế xếp sẵn theo độ gấp',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Vào ca mỗi sáng', points: [
      'Bấm "✅ Vào ca" — công tính tự động; nghỉ phép/phiếu lương cũng ở trang này',
    ]},
    { href: '/projects', icon: '📐', title: 'Nhận việc thiết kế', points: [
      'Mở dự án → chuyển "Theo phòng ban" → khối Thiết kế là việc của bạn',
      'Làm xong việc nào đổi trạng thái việc đó — thanh tiến độ tự chạy',
      'Upload file thiết kế/3D vào từng đầu việc (ghi chú + đính kèm)',
    ]},
    { href: '/quotations', icon: '📋', title: 'Báo giá thiết kế', points: [
      'Bóc tách vật tư xong → tạo báo giá tại đây, đính kèm file',
    ]},
  ],
  pm: [
    { href: '/', icon: '🌅', title: 'Tổng quan điều phối', points: [
      'Khối "🏗️ Dự án đang đến phòng bạn": ưu tiên quá hạn → cận hạn → HĐ lớn',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Điều phối dự án — trang chính của bạn', points: [
      'Thẻ dự án có thanh 5 khối = đang ở giai đoạn nào; badge 🔴/🟠 = độ gấp',
      'Mở dự án → phân công đầu việc cho designer/thu mua',
      'Thiếu vật tư → nút "📦 Yêu cầu vật tư" → Thu mua nhận thông báo duyệt',
    ]},
    { href: '/approvals', icon: '✅', title: 'Duyệt & được duyệt', points: [
      'OT đội thi công chờ bạn duyệt tại đây',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công của bạn + hiện trường', points: [
      'Tại công trường: Telegram /checkin [Mã] kèm GPS; /baocao gửi ảnh tiến độ',
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
      'Tạo tài khoản nhân viên mới / xử lý nghỉ việc (hệ thống tự bàn giao lead)',
      'Quy trình lương: Sinh bảng lương → Trình sếp duyệt (khóa kỳ) → Chi → phiếu lương tự gửi Telegram riêng từng người',
    ]},
    { href: '/pl', icon: '📈', title: 'Lãi/Lỗ', points: [
      'P&L theo dự án/tháng — chỉ bạn và Ban Giám đốc thấy trang này',
    ]},
  ],
  purchasing: [
    { href: '/', icon: '🌅', title: 'Tổng quan thu mua', points: [
      'Khối "🏗️ Dự án đang đến phòng bạn": dự án sắp/đang ở giai đoạn Thu mua',
    ]},
    { href: '/inventory', icon: '📦', title: 'Kho vật tư — trang chính của bạn', points: [
      'Cảnh báo 🔴 = tồn thấp, nhập thêm ngay',
      'Yêu cầu vật tư từ PM chờ duyệt tại đây (hoặc bấm nút ngay trên Telegram)',
      'Nhập/xuất kho xong cập nhật liền để số liệu đúng',
    ]},
    { href: '/projects', icon: '🏗️', title: 'Theo vật tư từng dự án', points: [
      'Mở dự án → "Theo phòng ban" → khối Thu mua là phần việc của bạn',
    ]},
    { href: '/attendance', icon: '⏱️', title: 'Công & quyền lợi', points: [
      'Vào ca/Tan ca tại đây; nghỉ phép, phiếu lương cùng trang',
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
    ]},
    { href: '/settings', icon: '⚙️', title: 'Cài đặt hệ thống', points: [
      'Nhóm Telegram công ty, AI model, sao lưu, tự động hóa CSKH — tất cả ở đây',
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

function tourStorageKey(role: string) {
  return `jama_tour_step_${role}`;
}

export default function GuidedTour() {
  const { user } = useAuth();
  const router = useRouter();
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);

  const role = user?.role || 'data_entry';
  const steps = ROLE_TOURS[role] || ROLE_TOURS.data_entry;

  const goTo = useCallback((index: number) => {
    const target = steps[index];
    if (!target) return;
    setStep(index);
    localStorage.setItem(tourStorageKey(role), String(index));
    router.push(target.href);
  }, [steps, role, router]);

  // Lắng nghe sự kiện bắt đầu tour (từ OnboardingChecklist / Cài đặt)
  useEffect(() => {
    const handler = () => {
      const saved = parseInt(localStorage.getItem(tourStorageKey(role)) || '0', 10);
      const startAt = Number.isFinite(saved) && saved > 0 && saved < steps.length ? saved : 0;
      setActive(true);
      goTo(startAt);
    };
    window.addEventListener(START_TOUR_EVENT, handler);
    return () => window.removeEventListener(START_TOUR_EVENT, handler);
  }, [role, steps.length, goTo]);

  const finish = () => {
    setActive(false);
    localStorage.removeItem(tourStorageKey(role));
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
