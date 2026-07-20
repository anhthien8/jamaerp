'use client';

import { useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';

/**
 * Trang "Có gì mới" — ghi chú thay đổi giữa các bản cập nhật, viết cho NHÂN VIÊN
 * (không phải dev): mỗi bản gồm Tính năng mới / Đã sửa / Anh em test giúp.
 * Cập nhật mảng RELEASES mỗi lần deploy tính năng đáng chú ý.
 */

interface Release {
  date: string;
  title: string;
  tag?: string;
  news?: string[];
  fixes?: string[];
  test?: string[];
}

const RELEASES: Release[] = [
  {
    date: '21/07/2026',
    title: 'Chế độ Tập luyện "thật" hơn + thuần Việt toàn bộ',
    tag: 'BETA',
    news: [
      'Chế độ Tập luyện giờ PHẢN HỒI THẬT: tạo lead là thấy thẻ mới trong bảng, kéo thẻ đổi cột được, bấm Duyệt là đơn biến mất, Vào ca là trạng thái đổi, chốt sổ lương chạy từng bước — thao tác nào cũng thấy kết quả ngay (dữ liệu mẫu, xả vai thoải mái).',
      'Dữ liệu mẫu mới theo quy mô công ty: doanh thu ~98 tỷ/tháng, hoa hồng sales trong demo lên tới 864 triệu/công trình — anh em xem thử để hình dung thu nhập khi chốt deal lớn.',
      'Form Báo giá mới: nhập từng hạng mục (tên, đơn vị, số lượng, đơn giá nghìn đồng) — hệ thống tự tính thành tiền và tổng, không còn ô mã JSON khó hiểu.',
      'Toàn bộ nhãn tiếng Anh còn sót đã chuyển tiếng Việt: danh mục thu chi, loại vật tư, phòng ban, vai trò, các thẻ báo cáo.',
    ],
    fixes: [
      'Số liệu các trang đã khớp nhau (trang chủ, Kế toán, P&L, Báo cáo cùng một câu chuyện số).',
      'Điện thoại: nút "+ Dự án mới" hết che thanh điều hướng; trang Tài khoản dùng được đầy đủ trên điện thoại; chuông thông báo về đúng chỗ.',
      'Nhấn phím Esc để đóng cửa sổ; số tiền âm hiển thị gọn (-400 triệu); ngày giờ theo kiểu Việt Nam.',
    ],
    test: [
      'Vào Chế độ Tập luyện: tạo thử 1 lead, kéo thẻ qua cột khác, duyệt 1 đơn, bấm Vào ca — mọi thứ phải "ăn" ngay trên màn hình.',
      'Tạo thử 1 báo giá bằng form hạng mục mới.',
      'Ai hay dùng điện thoại: mở trang Dự án + Tài khoản xem có gì bất tiện báo lại nhé.',
    ],
  },
  {
    date: '20/07/2026',
    title: 'Sẵn sàng beta toàn công ty',
    tag: 'BETA',
    news: [
      'Link Portal khách hàng hoạt động đầy đủ: Khách hàng → mở hồ sơ → "Tạo link portal" → copy gửi khách. Khách xem tiến độ nhà mình + bấm xác nhận nghiệm thu online.',
      'Chế độ Tập luyện có portal mẫu: bấm tạo link trong Tập luyện sẽ ra trang /portal/demo — dùng để demo cho khách hoặc đào tạo nhau.',
      'Ô nhập tiền đổi sang NGHÌN ĐỒNG: gõ 2500000 = 2,5 tỷ, bên dưới hiện dòng "= 2.500.000.000 đ (2,5 tỷ)" để tự soát. Áp dụng cho dự án, hợp đồng, lead.',
    ],
    fixes: [
      'Báo giá tức thì trong Chế độ Tập luyện không còn báo lỗi khi bấm "Tạo báo giá".',
      'Trang Khách hàng (chế độ Làm việc) hết lỗi tải danh sách.',
      'Trên điện thoại: bảng Dự án & Quy trình không còn kéo trôi cả trang sang ngang — chỉ vùng thẻ cuộn.',
      'Portal khách hàng: nếu bấm "Xác nhận nghiệm thu" mà mạng lỗi sẽ hiện thông báo đỏ rõ ràng (trước đây im lặng).',
      'Trang "Góp ý" thuần Việt (trước ghi "Feedback"), ngày hiển thị gọn dạng ngày/tháng.',
    ],
    test: [
      'Đăng nhập đúng vai trò của bạn, đi hết các trang mình hay dùng.',
      'Tạo thử 1 lead + 1 báo giá tức thì trong Chế độ Tập luyện.',
      'Admin/Leader: tạo link portal cho 1 khách thật và mở link đó trên điện thoại.',
    ],
  },
  {
    date: '18–19/07/2026',
    title: 'Gói tính năng lớn: tài khoản, tài chính, sau bàn giao, mobile',
    news: [
      'Tự đổi mật khẩu trong Cài đặt — không cần nhờ Admin.',
      'Quên mật khẩu ngay ở trang đăng nhập: mã 6 số gửi qua Telegram đã liên kết.',
      'Ngân sách dự án: nhập ngân sách khi tạo/sửa dự án → hệ thống cảnh báo khi chi tiêu chạm 80% hoặc vượt.',
      'Phải thu theo hợp đồng (trang P&L): các đợt thanh toán chưa thu, bấm xem chi tiết từng đợt.',
      'Nhắc bảo hành tự động: trước khi công trình hết bảo hành 30 và 7 ngày, hệ thống nhắc sales/PM gọi chăm khách.',
      'Thanh điều hướng dưới màn hình cho điện thoại — thao tác nhanh bằng ngón cái.',
      'Trang Cài đặt sắp xếp lại thành 3 nhóm: Cá nhân · Tích hợp · Hệ thống.',
      'Dữ liệu production chuyển sang PostgreSQL — bền vững, không mất khi cập nhật phiên bản.',
    ],
    fixes: [
      'Dashboard các vai trò Kinh doanh / Giám sát / Trưởng nhóm / Kế toán hết trống số liệu.',
      'Bấm ô ngày là mở lịch ngay (trước đây icon lịch bị chìm, khó bấm).',
      'Danh sách chọn (dropdown) hết bị chữ tối trên nền tối.',
    ],
    test: [
      'Đổi mật khẩu của chính bạn trong Cài đặt.',
      'Liên kết Telegram (Cài đặt → Telegram Bot) để nhận nhắc việc + dùng được Quên mật khẩu.',
      'Mở app trên điện thoại, dùng thử thanh điều hướng dưới.',
    ],
  },
  {
    date: '17/07/2026',
    title: 'Đăng nhập dễ hơn + sửa loạt lỗi giao diện',
    news: [
      'Đăng nhập bằng tên ngắn: gõ "admin" thay vì "admin@jamahome.vn".',
      'Logo mới + khẩu hiệu "Thiết kế cho cuộc sống mới".',
    ],
    fixes: [
      'Hết lỗi "Có lỗi xảy ra" khi bấm vào chi tiết lead ở chế độ Làm việc.',
      'Trang Cài đặt mở được với mọi vai trò (trước bị đẩy về Tổng quan).',
      'Sidebar hiển thị đủ 10 mục trên máy tính rồi mới gom "Xem thêm".',
    ],
  },
];

const SECTION_META = {
  news: { icon: 'star', label: 'Tính năng mới', color: '#C9A96E' },
  fixes: { icon: 'check', label: 'Đã sửa', color: '#34D399' },
  test: { icon: 'eye', label: 'Anh em test giúp', color: '#60A5FA' },
} as const;

export default function ChangelogPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-6 animate-in max-w-3xl">
        <h1 className="text-2xl font-bold mb-1 flex items-center gap-2.5"><LineIcon name="bell" size={22} />Có gì mới</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Ghi chú thay đổi giữa các bản cập nhật — đọc mục <span style={{ color: '#60A5FA' }}>&quot;Anh em test giúp&quot;</span> rồi vọc thử nhé.
          Gặp lỗi: chụp màn hình (khung lỗi tự hiện chi tiết) gửi nhóm kỹ thuật hoặc bot Telegram <code className="px-1 rounded bg-white/10">/feedback</code>.
        </p>

        <div className="space-y-6">
          {RELEASES.map(rel => (
            <div key={rel.date} className="glass-card p-6">
              <div className="flex items-center gap-3 flex-wrap mb-4">
                <span className="text-sm font-mono px-2.5 py-1 rounded-lg" style={{ background: 'rgba(201,169,110,0.12)', color: '#C9A96E' }}>{rel.date}</span>
                <h2 className="text-lg font-semibold">{rel.title}</h2>
                {rel.tag && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: 'rgba(52,211,153,0.15)', color: '#34D399' }}>{rel.tag}</span>
                )}
              </div>
              {(['news', 'fixes', 'test'] as const).map(key => {
                const items = rel[key];
                if (!items?.length) return null;
                const meta = SECTION_META[key];
                return (
                  <div key={key} className="mb-4 last:mb-0">
                    <div className="flex items-center gap-2 mb-2">
                      <LineIcon name={meta.icon} size={15} color={meta.color} />
                      <span className="text-xs font-bold uppercase tracking-wide" style={{ color: meta.color }}>{meta.label}</span>
                    </div>
                    <ul className="space-y-1.5">
                      {items.map((it, i) => (
                        <li key={i} className="flex gap-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                          <span className="flex-shrink-0 mt-0.5" style={{ color: meta.color }}>•</span>
                          <span>{it}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <p className="text-xs text-center mt-8" style={{ color: 'var(--text-muted)' }}>
          JAMA HOME · Thiết kế cho cuộc sống mới
        </p>
      </div>
    </Sidebar>
  );
}
