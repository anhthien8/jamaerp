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
    date: '07/08/2026',
    title: 'Sao lưu dữ liệu tự động hằng ngày + nhắc việc tự động chính thức hoạt động',
    tag: 'RELEASE',
    news: [
      'CRM có địa chỉ chính thức: https://crm.jamahome.vn — dễ nhớ, vào thẳng từ mọi thiết bị (địa chỉ cũ vẫn dùng được). Anh em lưu PWA ra màn hình chính nên cài lại từ địa chỉ mới.',
      'Toàn bộ dữ liệu CRM được sao lưu tự động 5h sáng mỗi ngày, file sao lưu gửi về nhóm Telegram riêng của ban quản trị — an tâm không mất dữ liệu.',
      'Bộ nhắc việc tự động chính thức chạy trên hệ thống thật: nhắc thanh toán hợp đồng, báo cáo BOD buổi sáng, tự chốt chấm công cuối ngày, chăm sóc khách hàng định kỳ.',
      'Cài đặt (admin) có mục Sao lưu mới: đặt giờ sao lưu, xem lần sao lưu gần nhất thành công hay lỗi, nút "Sao lưu ngay".',
      'Chế độ Tập luyện tạm ẩn khỏi trang đăng nhập — toàn công ty vào thẳng dữ liệu thật; sẽ mở lại khi tổ chức đào tạo nhân sự mới.',
      'Chi tiết lead có nút "Đổi" người phụ trách — admin/trưởng nhóm giao lead cho nhân viên kinh doanh ngay tại chỗ (theo phản hồi team KD). Lead chưa ai nhận hiện rõ "Chưa phân công".',
    ],
    fixes: [
      'Vai trò tùy chỉnh (tạo ở trang Tài khoản) giờ hiện đầy đủ trong trang Phân quyền để xem/sửa quyền — trước đây tạo xong là "biến mất". Nhân sự mang vai trò tùy chỉnh cũng nhận ĐÚNG bộ quyền đã cấu hình thay vì quyền mặc định.',
      'Nút "Sao lưu ngay" báo kết quả thật (thành công/lỗi kèm lý do) — trước đây trên hệ thống thật nó lặng lẽ bỏ qua.',
      'Gỡ hoàn toàn sao lưu Google Drive theo quyết định chuyển toàn bộ về Telegram.',
    ],
    test: [
      'Admin: vào Cài đặt → Sao lưu, dán Chat ID nhóm backup, bấm "Sao lưu ngay" và kiểm tra file về nhóm Telegram.',
    ],
  },
  {
    date: '06/08/2026',
    title: 'Tổng duyệt trước ra mắt chính thức — sạch lỗi toàn hệ thống',
    tag: 'RELEASE',
    news: [
      'Cài app lên điện thoại đẹp chuẩn thương hiệu: icon logo JM mới + banner hướng dẫn cài đặt (Android một chạm, iPhone có chỉ dẫn).',
      'Chế độ Tập luyện trung thực 100%: trang KPI hiện đủ số liệu mẫu cả 3 tab; thao tác nào chưa mô phỏng sẽ báo rõ thay vì "thành công giả".',
    ],
    fixes: [
      'HR "Cho nghỉ việc" trong Chế độ Tập luyện hết làm treo ứng dụng — xem trước bàn giao lead/việc hoạt động bình thường.',
      'Số tiền deal hết đuôi thập phân lê thê (7.071341221 tỷ → 7.1 tỷ) trên toàn hệ thống.',
      'Trang Kế toán: lợi nhuận/tỷ lệ chi-thu/danh mục cùng kỳ lọc — hết cảnh "Lợi nhuận: 2 đ" khó hiểu.',
      'Trang Phân quyền + Nhà cung cấp: toàn bộ chữ đã có dấu đầy đủ.',
      'Đổi giai đoạn lead có khóa chống bấm đúp — hết nguy cơ tạo trùng Khách hàng + Dự án.',
      'Chữ phụ trên nền tối đậm rõ hơn (đạt chuẩn dễ đọc); modal Từ chối hết "tàng hình" ở giao diện sáng.',
      'Điện thoại: banner cài đặt hết che thanh điều hướng; ô SĐT bật đúng bàn phím số; chuông thông báo hết đè nút Sửa.',
    ],
    test: [
      'Vào Chế độ Tập luyện đi hết một vòng: KPI, Nhân sự → Cho nghỉ việc (xem trước rồi Hủy), kéo thả lead, tạo giao dịch.',
      'Trên điện thoại: cài app từ banner, kiểm tra icon ngoài màn hình chính có đúng logo JM không.',
    ],
  },
  {
    date: '23/07/2026',
    title: 'Quản trị Dự toán Công trình, Thầu phụ & Báo cáo Chiến lược BOD',
    tag: 'RELEASE',
    news: [
      'Cảnh báo Vượt Dự toán Công trình: Hiển thị thanh tiến độ ngân sách thực chi vs tổng ngân sách (Cost Overrun), tự động cảnh báo màu Cam (>=85%) và màu Đỏ (>=100%) khi công trình chạm hạn mức.',
      'Quản lý Đội thầu phụ & Thi công: Thêm Tab "Thầu phụ & Thi công" trong Chi tiết Dự án, theo dõi thầu thạch cao, sơn, đồ gỗ, điện nước, đơn giá giao khoán và nghiệm thu 4 giai đoạn.',
      'Quản lý Phiên bản Báo giá (Versioning): Hỗ trợ nhân bản và lưu vết lịch sử Báo giá (v1.0, v2.0, v3.0), cho phép chọn lại phiên bản cũ và theo dõi ghi chú thay đổi.',
      'Báo cáo Chiến lược BOD (Tab mới trong Kế toán):',
      '  - Sub-tab 1: Biên Lợi nhuận theo Gói (Cơ bản, Tiêu chuẩn, Cao cấp) & Loại căn hộ (1PN, 2PN, Villa, Penthouse).',
      '  - Sub-tab 2: Dự báo Dòng tiền 30-60 ngày (Biểu đồ + Bảng dự tính Tiền vào từ Hợp đồng vs Tiền ra cho Thầu phụ, Vật tư & Lương).',
    ],
    fixes: [
      'Đồng bộ dữ liệu Demo offline cho Thầu phụ, Phiên bản Báo giá và Báo cáo Chiến lược.',
      'Khắc phục triệt để các lỗi thuộc tính TypeScript trên trang P&L và Báo giá.',
    ],
    test: [
      'BOD / Giám đốc: Mở Kế toán -> Tab Báo cáo Chiến lược BOD -> Kiểm tra Biểu đồ Dòng tiền 30-60 ngày & Biên lợi nhuận gói.',
      'Quản lý Dự án: Mở Dự án -> Chi tiết Dự án -> Tab Thầu phụ & Thi công -> Xem thanh Cảnh báo Vượt dự toán (amber/red).',
      'Kinh doanh / KTS: Mở Báo giá -> Thao tác "Tạo bản thảo mới (Version)" để lưu vết v2.0.',
    ],
  },
  {
    date: '22/07/2026',
    title: 'Lương & hoa hồng vận hành trọn vòng',
    tag: 'BETA',
    news: [
      'Cài JAMA HOME như app điện thoại: icon logo JM thương hiệu mới + banner hướng dẫn "Lưu ra màn hình chính" tự hiện khi mở bằng điện thoại (Android có nút Cài đặt một chạm, iPhone có chỉ dẫn từng bước).',
      'Kho vật tư có nút "📥 Nhập từ file": thu mua nhận báo giá NCC bằng Excel/CSV là nhập cả trăm dòng một lần — xem trước rồi mới xác nhận, trùng Mã/Tên thì tự cập nhật giá + NCC mới, có file mẫu tải về. (Excel: Lưu dưới dạng CSV UTF-8.)',
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
