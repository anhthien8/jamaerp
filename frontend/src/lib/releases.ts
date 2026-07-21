/**
 * Nhật ký phát hành — NGUỒN DUY NHẤT cho version hiển thị.
 * RELEASES[0] = bản mới nhất; dòng 'Phiên bản' ở Cài đặt tự lấy ngày từ đây
 * (hết cảnh hardcode 'Beta 20/07' rồi quên cập nhật).
 */

export interface Release {
  date: string;
  title: string;
  tag?: string;
  news?: string[];
  fixes?: string[];
  test?: string[];
}

export const RELEASES: Release[] = [
  {
    date: '22/07/2026',
    title: 'Lương & hoa hồng vận hành trọn vòng',
    tag: 'BETA',
    news: [
      'Gán bậc lương + số người phụ thuộc cho từng nhân viên ngay tại Tài khoản → Sửa — từ đó Chốt sổ sinh bảng lương ra SỐ THẬT (công, tăng ca, BHXH, thuế TNCN) thay vì 0đ.',
      'Tab Hoa hồng có nút "✓ Duyệt" và "💵 Đã chi trả" — hoa hồng không còn treo trạng thái "Chờ" vĩnh viễn; trạng thái tách rõ 3 nấc: Chờ duyệt / Đã duyệt / Đã trả.',
      'Giao dịch Lương/Hoa hồng gắn được với nhân viên cụ thể — chọn danh mục Lương là hiện ô "Liên kết nhân viên", tên hiện thành thẻ vàng cạnh mô tả.',
    ],
    fixes: [
      'Cửa sổ tạo/sửa (Hợp đồng, Báo giá...) hết bị lệch sang một bên với nền mờ phủ thiếu — giờ luôn căn giữa màn hình, nền mờ phủ kín.',
      'Nút "Tạo giao dịch" ở chế độ Làm việc đã hoạt động (trước đây luôn báo lỗi ngầm) và tôn trọng đúng NGÀY bạn chọn.',
      'Trang Tổng quan của Trưởng nhóm/Kinh doanh hết cảnh báo "Chưa kết nối API" khi có khách quá hạn.',
      'Trang P&L ở chế độ Làm việc hiển thị số thật từ hệ thống — nếu máy chủ lỗi sẽ báo rõ thay vì hiện số mẫu.',
      'Kế toán (kiêm nhân sự) bấm Sửa tài khoản nhân viên không còn bị từ chối quyền.',
    ],
    test: [
      'Kế toán: gán bậc lương cho từng nhân viên (Tài khoản → Sửa), rồi chạy thử Chốt sổ → Sinh bảng lương xem số có ra thật không.',
      'Kế toán: tạo 1 giao dịch thu/chi ở chế độ Làm việc, chọn ngày trong quá khứ, reload xem còn không.',
      'Duyệt thử 1 khoản hoa hồng rồi đánh dấu Đã chi trả.',
    ],
  },
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
