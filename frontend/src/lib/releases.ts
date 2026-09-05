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
    date: '05/09/2026',
    title: 'Data khách: đổi tên 2 cột pipeline, lọc theo nhân viên phụ trách, thanh kéo ngang đặt lên trên',
    tag: 'RELEASE',
    news: [
      'ĐỔI TÊN 2 CỘT — anh em để ý kẻo tìm nhầm: «Đang chờ» nay là «📤 Đã gửi báo giá», «Đã chốt hồ sơ» nay là «🤝 Đang đàm phán». Bốn cột còn lại giữ nguyên tên. Không có data nào bị mất hay chuyển cột — chỉ đổi chữ hiển thị.',
      'Tên cột nay đồng nhất ở mọi nơi: bảng data khách, lịch sử hoạt động trong thẻ khách, và bot Telegram. Trước đây cùng một cột mà ba chỗ gọi ba tên khác nhau («Đang chờ» / «Khảo sát» / «Đã hẹn khảo sát») rất dễ hiểu lầm.',
      'Thêm bộ lọc «Tất cả nhân viên KD» trên thanh lọc: chọn một người để xem riêng data của người đó, hoặc chọn «— Chưa phân công —» để soi data còn tồn chưa giao ai. Danh sách chỉ hiện những người thực sự đang giữ data trong phạm vi bạn xem được.',
      'Thanh kéo ngang nay nằm NGAY TRÊN bảng và dính ở đầu trang: kéo qua các cột mà không phải cuộn xuống tận đáy để tìm thanh kéo. Kéo thanh trên hay kéo thẳng bảng đều được, hai bên tự chạy theo nhau.',
      'Form «Tạo Lead mới»: ô «Phân khúc» (vốn trùng y hệt «Loại BĐS», không thêm thông tin gì) đổi thành «Nhu cầu» với 3 lựa chọn Thi công nội thất / Cải tạo / Xây mới.',
      'Nguồn lead có thêm «Hotline» và «Khách đến văn phòng».',
    ],
    fixes: [
      'Lead nhập TRƯỚC hôm nay vẫn hiện ô «Nhu cầu» theo giá trị cũ (Nhà phố, Biệt thự…) chứ không hiện mã khó đọc. Muốn chuẩn hoá thì mở thẻ khách chọn lại nhu cầu đúng.',
    ],
    test: [
      'Sale/CSKH: mở Data khách → kiểm 2 cột đã đổi tên đúng, và số thẻ từng cột không đổi so với hôm qua.',
      'CSKH/Trưởng nhóm: chọn bộ lọc «Tất cả nhân viên KD» → chọn một sale → xác nhận chỉ còn data của người đó; thử «— Chưa phân công —» xem còn tồn bao nhiêu.',
      'Kéo thanh ngang màu vàng ở trên đầu bảng → xác nhận bảng chạy theo, không cần cuộn xuống đáy.',
      'Bấm «+ Thêm Lead» → ô «Nhu cầu» có đúng 3 lựa chọn, ô «Nguồn lead» có Hotline và Khách đến văn phòng.',
    ],
  },
  {
    date: '05/09/2026',
    title: 'Bảng data khách gọn lại: hết cuộn mỏi tay ở cột «Tiếp nhận mới» + P&L có ngày thật',
    tag: 'RELEASE',
    news: [
      'Cột nào trên bảng data khách cũng chỉ hiện 25 thẻ đầu, muốn xem tiếp bấm «Hiện thêm 25 thẻ (còn X)» ở đáy cột — cột «Tiếp nhận mới» 137 thẻ từng kéo trang dài gần 30 màn hình, giờ gọn trong một tầm mắt. Số trên đầu cột vẫn là TỔNG thật, không mất thẻ nào.',
      'Đã xem thêm rồi muốn gọn lại: bấm «Thu gọn» về 25 thẻ đầu. Đổi bộ lọc, tìm kiếm hay sắp xếp thì các cột tự gọn về như cũ.',
      'Báo cáo P&L chế độ Làm việc nay có NGÀY BẮT ĐẦU thật của từng dự án: bộ chọn kỳ theo tháng/quý/năm hoạt động với số liệu thật (trước đây toàn «—» vì máy chủ chưa trả ngày), huy hiệu trạng thái dự án cũng là trạng thái thật.',
    ],
    fixes: [
      'Kéo thẻ vào cột đang đông: thẻ vừa chuyển luôn hiện ra ngay (không còn cảnh thẻ «biến mất» dưới nếp gấp làm tưởng chuyển hụt — thực ra data vẫn nguyên).',
      'Ngày trên P&L hiển thị đúng ở mọi múi giờ — kể cả khi sếp mở báo cáo lúc đi công tác nước ngoài.',
    ],
    test: [
      'Sale/CSKH: mở Data khách → cột «Tiếp nhận mới» chỉ 25 thẻ + nút «Hiện thêm» ở đáy; kéo một thẻ sang cột khác → thẻ hiện ngay ở cột đích.',
      'Kế toán/Giám đốc: mở P&L (chế độ Làm việc) → cột ngày có dd/mm thay «—» với dự án đã nhập ngày bắt đầu; bấm lọc theo tháng → đúng dự án của tháng đó.',
      'Dự án chưa nhập ngày bắt đầu vẫn hiện «—» và luôn có mặt trong mọi kỳ — muốn lọc theo kỳ thì vào Dự án nhập ngày bắt đầu.',
    ],
  },
  {
    date: '29/08/2026',
    title: 'Siết quyền Duyệt báo giá & Xác nhận thu tiền — tách quyền soạn với quyền duyệt',
    tag: 'RELEASE',
    news: [
      'ĐỔI QUYỀN — anh em đọc kỹ: nút «Duyệt báo giá» nay chỉ Giám đốc, Trưởng nhóm/phòng và Giám sát mới thấy. Sale vẫn soạn, sửa, gửi báo giá bình thường như cũ — chỉ là không tự duyệt bản của chính mình nữa.',
      'Nút «Xác nhận TT» (đánh dấu đã thu tiền đợt thanh toán hợp đồng) nay chỉ Kế toán, Giám đốc và Trưởng nhóm/phòng mới thấy. Sale vẫn xem được đầy đủ trạng thái thanh toán của hợp đồng, chỉ không tự tích «đã thu».',
      'Sale nào đang quen tự duyệt báo giá hoặc tự tích đã thu tiền thì từ nay báo cấp trên / kế toán làm giúp. Nếu cách này vướng thực tế công việc, báo lại để chỉnh.',
    ],
    fixes: [
      'Kế toán không còn tạo/sửa được báo giá — đúng như bảng phân quyền và tài liệu công ty vẫn ghi (Kế toán = chỉ Đọc báo giá). Trước đây bảng ghi một đằng, hệ thống cho làm một nẻo.',
      'Ba nút trên trước đây KHÔNG hề kiểm quyền ở máy chủ: dù giao diện có ẩn nút thì người biết cách vẫn gọi thẳng được. Nay máy chủ tự chặn, không phụ thuộc nút bị ẩn.',
    ],
    test: [
      'Sale: mở một báo giá nháp → xác nhận KHÔNG còn nút «Duyệt báo giá», nhưng vẫn sửa và lưu được bình thường.',
      'Sale: mở hợp đồng → xác nhận vẫn xem được các đợt thanh toán và trạng thái, nhưng không còn nút «Xác nhận TT».',
      'Trưởng nhóm/Kế toán: xác nhận vẫn duyệt báo giá / tích đã thu tiền được như thường.',
    ],
  },
  {
    date: '27/08/2026',
    title: 'Tổng QC hệ thống: vá 4 form «lưu giả» (Dự án, Hợp đồng, Báo giá, Thu chi) + 3 lỗi nhỏ',
    tag: 'RELEASE',
    news: [
      'Đợt tổng rà soát chất lượng toàn hệ thống sau 4 bản cập nhật ngày 27/08: chạy đủ 533 test tự động, bộ QC 146 điểm theo từng vai trò, 10 luồng thao tác thật trên trình duyệt, và đi chụp màn hình từng trang của 5 vai trò trên bản chạy thật.',
    ],
    fixes: [
      'NHÓM LỖI «LƯU GIẢ» (cùng họ với lỗi Mất lead đã vá sáng nay — báo thành công nhưng không lưu): SỬA DỰ ÁN đổi tên khách / SĐT / địa chỉ / loại công trình / giá trị / ngày bắt đầu / ngày dự kiến xong — trước đây toast xanh nhưng KHÔNG lưu gì. Nay lưu thật cả 7 trường.',
      'SỬA HỢP ĐỒNG đổi ô «Dự án» — trước đây bị bỏ qua im lặng. Nay lưu thật.',
      'SỬA BÁO GIÁ đổi «Loại» hoặc «Dự án» — trước đây bị bỏ qua im lặng. Nay lưu thật.',
      'SỬA GIAO DỊCH THU CHI đổi ngày hoặc người liên quan — trước đây CHƯA BAO GIỜ lưu được (kể cả từ trước các bản cập nhật gần đây). Kế toán lưu ý: giao dịch nào từng sửa ngày đều đang mang ngày TẠO chứ không phải ngày đã chọn — cần rà lại.',
      'Trưởng phòng chưa được xếp vào đội nào mở trang Chấm công không còn bị toast lỗi đỏ «Không tải được bảng công» — nay chỉ ẩn bảng công team, phần chấm công cá nhân hiện bình thường.',
      'Trang Góp ý khi chưa có góp ý nào nay hiện hướng dẫn «gửi qua bot Telegram lệnh /feedback» thay vì bảng trống trơn.',
      'Form «Thêm Lead»: ô «Trưởng nhóm phụ trách» chỉ còn liệt kê các đội KINH DOANH — không còn lẫn Ban Giám Đốc / Phòng Thiết Kế / Phòng Thu mua.',
    ],
    test: [
      'Trưởng nhóm/PM: mở một Dự án → Sửa → đổi SĐT khách hoặc ngày dự kiến xong → Lưu → TẢI LẠI TRANG và xác nhận thay đổi còn đó (đây là điểm trước đây lưu giả).',
      'Kế toán: sửa một giao dịch thu chi đổi ngày → tải lại → xác nhận ngày đã đổi thật. Và rà các giao dịch cũ từng sửa ngày.',
      'Sale: tạo báo giá rồi Sửa đổi loại Thiết kế ↔ Thi công → tải lại → xác nhận loại đã đổi.',
    ],
  },
  {
    date: '27/08/2026',
    title: 'Sửa lỗi: bấm «Chuyển sang Mất lead» báo thành công nhưng lead vẫn nằm ở cột cũ',
    tag: 'HOTFIX',
    fixes: [
      'LỖI CHÍNH: chọn lý do rồi bấm «Xác nhận mất lead», hệ thống hiện thông báo xanh «đã chuyển» nhưng lead vẫn nằm nguyên cột cũ, tải lại trang cũng vậy. Nay chuyển đúng sang cột «❌ Mất» thật.',
      'Lý do mất lead trước đây KHÔNG được lưu lại chút nào — hệ thống chưa hề có chỗ chứa nó, dù màn hình vẫn cho chọn. Nay lý do được lưu, hiện trong thẻ khách và ghi vào lịch sử hoạt động («Chuyển stage: … → Mất — Lý do: …»), nên sau này rà lại biết vì sao mất khách.',
      'Vì lý do cũ chưa từng được lưu nên các lead đã chuyển sang Mất TRƯỚC bản này sẽ hiện trống phần lý do — không khôi phục được. Từ bản này trở đi mới có.',
      'Kéo một lead từ cột «Mất» quay lại pipeline thì lý do mất cũ được xoá, không còn treo dòng «Mất: …» trên khách đang chăm lại.',
      'Chuyển sang «Mất» mà chưa chọn lý do nay bị chặn rõ ràng (kể cả khi chuyển hàng loạt), thay vì âm thầm không làm gì.',
    ],
    test: [
      'Sale/Trưởng nhóm: mở một lead thử → «🚫 Chuyển sang Mất lead» → chọn lý do → Xác nhận → kiểm tra lead ĐÃ nhảy sang cột «❌ Mất».',
      'Mở lại lead vừa chuyển → xác nhận khối «Lý do mất lead» hiện đúng lý do đã chọn, và lịch sử hoạt động có dòng ghi lý do.',
      'Kéo lead đó từ cột «Mất» về «Đang tư vấn» → xác nhận phần lý do mất đã được xoá.',
    ],
  },
  {
    date: '27/08/2026',
    title: 'Giao data theo đội: chọn Trưởng nhóm trước rồi mới chọn nhân viên — và Trưởng nhóm xem được data cả nhóm',
    tag: 'RELEASE',
    news: [
      'Form «Thêm Lead» đổi ô «Gắn nhân viên KD phụ trách» thành 2 bước: chọn «Trưởng nhóm phụ trách» trước, rồi ô «Nhân viên kinh doanh» chỉ hiện đúng người trong nhóm của trưởng nhóm đó. Hết cảnh một danh sách dài trộn lẫn mọi đội, giao nhầm sang quân của trưởng nhóm khác.',
      'Chọn trưởng nhóm mà chưa chọn nhân viên cụ thể thì data về thẳng trưởng nhóm để họ tự chia tiếp trong nhóm — đúng luồng CSKH → Trưởng nhóm → Sale. Ngay dưới ô có dòng nhắc data sẽ vào tay ai.',
      'Đổi trưởng nhóm thì ô nhân viên tự xóa lựa chọn cũ, không giao nhầm chéo đội.',
    ],
    fixes: [
      'LỖI QUAN TRỌNG: tài khoản Trưởng nhóm trước đây chỉ xem được data gắn cho chính mình, không thấy data của nhân viên trong nhóm mình phụ trách. Nay xem và quản lý được data của cả nhóm.',
      'Nguyên nhân thứ hai đã xử lý: nhân viên nhận data TRƯỚC khi được xếp vào đội thì số data đó không mang nhãn đội, nên trưởng nhóm không bao giờ thấy dù sau đó đã xếp người vào đội. Nay xếp người vào đội / chuyển đội / đổi trưởng nhóm đều tự gắn lại nhãn đội cho toàn bộ data của người đó, và hệ thống đã rà soát gắn lại một lượt cho data cũ.',
      'Nhân viên chuyển sang đội khác thì data cũ đi theo sang đội mới — trưởng nhóm đội cũ không còn thấy data của người đã rời đi. Data chưa giao cho ai vẫn nằm ở kho chung, không bị vơ vào đội nào.',
    ],
    test: [
      'Admin CSKH: thêm một lead mới → chọn «Trưởng nhóm phụ trách» → xác nhận ô «Nhân viên kinh doanh» chỉ liệt kê người của nhóm đó.',
      'Admin CSKH: chọn trưởng nhóm rồi bấm Tạo luôn (không chọn nhân viên) → xác nhận data vào tay trưởng nhóm.',
      'Trưởng nhóm: mở trang Quy trình → xác nhận thấy data của TẤT CẢ nhân viên trong nhóm mình, không chỉ data của mình. Đây là phần cần anh em kiểm kỹ nhất.',
      'Trưởng nhóm: đếm thử số lead trong nhóm xem có khớp với số nhân viên đang giữ data không — thiếu ai thì báo lại ngay.',
    ],
  },
  {
    date: '27/08/2026',
    title: 'Ô ghi chú CSKH trong thẻ khách: chấm chất lượng chăm sóc của team kinh doanh',
    tag: 'RELEASE',
    news: [
      'Mở thẻ khách ở trang Quy trình có thêm khối «🎧 CSKH — Đánh giá chất lượng chăm sóc». Admin CSKH gọi lại khách hỏi thăm rồi ghi nhận xét vào đây: khách khen ai, phàn nàn gì, sale có gọi lại đúng hẹn không.',
      'Đây là LOGNOTE nhiều mục, không phải một ô ghi đè: mỗi lần ghi là thêm một mục mới, mục cũ giữ nguyên. Hệ thống tự đóng dấu ngày giờ đầy đủ + tên người nhập, mới nhất nằm trên cùng, và có dòng «Cập nhật gần nhất» ngay cạnh tiêu đề.',
      'Nhân viên kinh doanh ĐỌC được đầy đủ đánh giá về mình để biết chỗ nào khách chưa hài lòng mà sửa — nhưng không sửa/xóa được nội dung.',
      'Ghi chú CSKH nằm ở khối riêng, không trộn vào «Lịch sử hoạt động» nên không bị trôi mất giữa hàng chục cuộc gọi và ghi chú hằng ngày.',
    ],
    fixes: [
      'Ghi đánh giá CSKH KHÔNG làm mất cờ «⚠️ Quá hạn» của khách: cuộc gọi của CSKH là gọi kiểm tra chất lượng, không tính là team kinh doanh đã chăm khách. Trước giờ mọi ghi nhận đều làm mới mốc «liên hệ lần cuối» — nếu tính cả CSKH thì số liệu chăm sóc sẽ đẹp giả.',
    ],
    test: [
      'Admin CSKH: mở một thẻ khách → gõ nhận xét vào ô CSKH → «Lưu đánh giá» → kiểm tra mục vừa ghi hiện đúng ngày giờ và tên bạn.',
      'Admin CSKH: ghi thêm mục thứ hai cho cùng khách đó → xác nhận mục cũ vẫn còn, không bị đè.',
      'Sale: mở thẻ khách của mình → xác nhận ĐỌC được đánh giá CSKH nhưng không có ô nhập (chỉ hiện dòng giải thích).',
      'Sale/Trưởng nhóm: kiểm tra khách đang có cờ «⚠️ Quá hạn» — sau khi CSKH ghi đánh giá, cờ đó phải vẫn còn.',
    ],
  },
  {
    date: '27/08/2026',
    title: 'Trang Quy trình: thêm kiểu xem Danh sách, bộ lọc theo ngày và cột «Mất»',
    tag: 'RELEASE',
    news: [
      'Trang Quy trình có thêm kiểu xem «📊 Danh sách» bên cạnh Kanban và Lịch: toàn bộ lead nằm trên một bảng ngang — tên, giai đoạn, ưu tiên, loại nhà, ngân sách, giá trị hợp đồng, điểm AI, nguồn, người phụ trách, ngày thêm, ngày cập nhật. Bấm vào tiêu đề cột để sắp xếp, bấm vào dòng để mở thẻ khách như cũ.',
      'Bộ lọc theo ngày: chọn mốc (Ngày cập nhật / Ngày thêm mới / Ngày liên hệ cuối) rồi chọn khoảng (Hôm nay, Hôm qua, 7 ngày qua, 30 ngày qua, Tháng này, hoặc tự chọn từ ngày – đến ngày). Dùng để soát lại data mình vừa nhập trong ngày đã đủ thông tin chưa.',
      'Bảng kanban có thêm cột «❌ Mất» ở cuối: các lead đã đánh mất nay nhìn thấy và kiểm soát được ngay trên bảng, trước đây phải đi vòng từ trang Tổng quan mới thấy.',
      'Kéo một thẻ khách thả vào cột «Mất» sẽ tự mở thẻ khách và bật sẵn ô chọn lý do mất — không còn báo lỗi đỏ bắt tự đi tìm. Chọn «Mất» ở ô trạng thái nhỏ trên thẻ cũng vậy.',
      'Thêm kiểu sắp xếp «Cập nhật gần nhất» — ghép với bộ lọc ngày là ra đúng danh sách data vừa đụng tới.',
    ],
    fixes: [
      'Số lead ghi ở đầu trang Quy trình nay khớp đúng số thẻ đang hiện; trước đây có đếm cả lead không nằm trong cột nào nên nhìn cứ thấy thiếu.',
      'Ô trạng thái nhỏ trên thẻ khách không còn bị trống với lead ở giai đoạn «Mất» hoặc «Ngủ đông».',
      'Bấm vào một giai đoạn từ trang Tổng quan nay chỉ mở đúng cột đó thay vì bày thêm 4 cột rỗng.',
    ],
    test: [
      'Sale/CSKH: mở Quy trình → bấm «📊 Danh sách» → kiểm tra bảng kéo ngang xem được hết cột, bấm tiêu đề «Giá trị HĐ» xem có sắp xếp không.',
      'Cuối ngày: chọn Ngày «Ngày thêm mới» + «Hôm nay» → rà lại các lead vừa nhập xem đã đủ SĐT, khu vực, ngân sách, người phụ trách chưa.',
      'Trưởng nhóm: kéo thử một thẻ khách vào cột «❌ Mất» → xác nhận thẻ khách tự mở và ô chọn lý do đã bật sẵn.',
    ],
  },
  {
    date: '18/08/2026',
    title: 'Giao việc dự án chéo phòng ban hoạt động lại cho mọi vai trò',
    tag: 'FIX',
    fixes: [
      'Trưởng nhóm Kinh doanh mở form «Thêm công việc» trong Dự án: ô «Người phụ trách» cho việc Thiết kế / Thi công / Thu mua trước đây bị TRỐNG (hệ quả phụ của đợt siết phạm vi nhân sự 14/08) — nay hiện đủ người đúng phòng ban để giao việc chéo phòng như quy trình.',
      'Tên người phụ trách công việc khác phòng ban nay hiện đúng thay vì để trống trên thẻ công việc.',
      'Các vai trò tự tạo như Quản lý dự án / Thiết kế / Giám sát thi công vào trang Dự án nay cũng giao việc và thấy tên người phụ trách bình thường — trước đây danh sách người giao việc bị chặn vì các vai trò này không có quyền «Xem Nhân sự».',
      'Danh sách giao việc này chỉ có tên + vai trò + phòng ban — SĐT, email, bậc lương của đồng nghiệp vẫn kín như cũ; trang Nhân sự vẫn giữ nguyên phạm vi (trưởng nhóm chỉ thấy nhóm mình).',
    ],
    test: [
      'Trưởng nhóm KD: mở một Dự án → «Thêm công việc» → chọn phòng ban Thiết kế → xác nhận ô «Người phụ trách» có danh sách nhân sự Thiết kế (không còn trống).',
      'Quản lý dự án / Giám sát thi công: mở Dự án → giao một việc bằng nút «👤 Đảm nhận» trên thẻ công việc → xác nhận giao được và tên người nhận hiện đúng.',
    ],
  },
  {
    date: '18/08/2026',
    title: 'Mạng chập chờn không còn bị đá oan khỏi trang Nhân sự / Tài khoản',
    tag: 'HOTFIX',
    fixes: [
      'Trưởng nhóm Kinh doanh (và các vai trò tùy chỉnh khác) mở trang Nhân sự hay Tài khoản đúng lúc máy chủ chậm / mạng chập chờn trước đây có thể bị đẩy ngược về Tổng quan dù có quyền — nay hệ thống tự thử lại vài lần, vẫn không được thì hiện thanh vàng «Không tải được quyền — Thử lại» và giữ bạn ở nguyên trang.',
      'Ngược lại, khi máy chủ treo lâu, trang không còn đứng hình khung trống vô hạn — sau ít giây sẽ hiện thanh vàng để bạn bấm «Thử lại» thay vì phải F5 mò mẫm.',
    ],
    test: [
      'Trưởng nhóm KD: mở trang Nhân sự lúc mạng yếu (hoặc vừa mở app buổi sáng khi máy chủ còn "ngái ngủ") → nếu thấy thanh vàng thì bấm «Thử lại» — không bị đá về Tổng quan như trước.',
    ],
  },
  {
    date: '15/08/2026',
    title: 'Tổng rà soát chất lượng: vá 18 lỗi khắp hệ thống + làm mới hướng dẫn sử dụng theo vai trò',
    tag: 'RELEASE',
    news: [
      'Hướng dẫn từng bước theo vai trò được rà lại toàn bộ cho khớp hệ thống hiện tại: nhân viên mới bấm «Hướng dẫn» là đi đúng màn hình, đúng nút — thêm các bước còn thiếu như liên kết Telegram lần đầu, copy báo giá gửi Zalo, chế độ NGOÀI TRỜI cho anh em công trường.',
      'Checklist tuần đầu cho người mới có thêm 2 việc chung mọi vai trò (liên kết Telegram, đọc «Có gì mới») + 4 mẹo sống còn: quên mật khẩu lấy lại qua Telegram, phân biệt lỗi tải với số 0, chuông thông báo, cài app ra màn hình chính.',
      'Cảnh báo rõ trong hướng dẫn CSKH: «Deal đã thắng» tạo NGAY Khách hàng + Dự án + Hợp đồng và không lùi được — chỉ chọn khi khách đã ký thật.',
    ],
    fixes: [
      'Báo giá: xóa hết hạng mục rồi bấm Lưu nay lưu được bình thường (trước đây báo lỗi hệ thống); hai người cùng tạo báo giá một lúc không còn nguy cơ trùng mã; tự nhập mã đã tồn tại thì báo rõ «Mã đã tồn tại — chọn mã khác» thay vì lỗi khó hiểu.',
      'Xếp đội: mở thẻ đội khi danh sách nhân sự chưa tải xong sẽ được nhắc chờ vài giây — chặn hẳn tình huống hiếm bấm Lưu lúc đó làm trôi sạch thành viên của đội.',
      'Báo cáo P&L chế độ Làm việc: hết cảnh nút kỳ hiện «Năm NaN» hay bảng in «Invalid Date» — dự án chưa có ngày bắt đầu hiển thị «—» gọn gàng.',
      'Bảng điều khiển cá nhân: thẻ số liệu nào bạn không có quyền mở trang chi tiết thì không còn giả vờ bấm được (mất chữ «Xem chi tiết», chuột không đổi hình).',
      'Nhà cung cấp: trang có đủ menu trái như mọi trang khác, danh sách báo giá NCC hiện đúng thay vì trống trơn.',
      'Kho: danh sách vật tư hiện đủ tới 200 mục thay vì đứng ở 50; tải lỗi sẽ báo thật thay vì lặng lẽ hiện danh sách demo.',
      'Thu chi: mở trang mặc định vào đúng tháng hiện tại thay vì tháng cũ.',
      'Nhân sự: ngày nghỉ việc lưu và hiển thị đúng; xử lý nghỉ việc tự bàn giao lead như hướng dẫn.',
      'Cổng khách hàng: khách chỉ xem được đúng công trình của mình.',
      'Trang «Có gì mới»: hai bản phát hành cùng ngày không còn dính lỗi hiển thị trùng.',
    ],
    test: [
      'Nhân viên mới: đăng nhập → làm theo checklist tuần đầu (có 2 mục chung mới) → bấm «Bắt đầu hướng dẫn từng bước» → xác nhận các bước khớp màn hình thật.',
      'Kế toán/Sale: tạo báo giá bỏ trống mã → hệ thống tự sinh mã BG-2026-xxxx; sửa báo giá xóa hết hạng mục → Lưu vẫn chạy.',
      'Anh em công trường: menu dưới cùng → bật «☀️ NGOÀI TRỜI» khi nắng chói khó đọc màn hình.',
    ],
  },
  {
    date: '14/08/2026',
    title: 'Chia đội kinh doanh ngay trên hệ thống: tạo đội, chọn trưởng nhóm, xếp thành viên',
    tag: 'RELEASE',
    news: [
      'Trang «Quản lý tài khoản» có khối Đội nhóm: quản trị viên tạo/sửa đội, chọn trưởng nhóm và tick danh sách thành viên trong một màn hình — hết cảnh không chia đội được vì thiếu chỗ phân nhóm.',
      'Trang Nhân sự thêm chế độ xem «Đội nhóm»: nhìn một phát biết đội nào — trưởng nhóm nào — quân số bao nhiêu, ai chưa được xếp đội.',
      'Giải tán đội làm được ngay trên UI (có xác nhận): thành viên về «chưa xếp đội», data khách chỉ mất nhãn đội — người phụ trách và toàn bộ lịch sử chăm sóc GIỮ NGUYÊN.',
    ],
    fixes: [
      'Trưởng nhóm nghỉ việc không khóa cứng đội: vẫn đổi tên đội, xếp lại thành viên bình thường; người nghỉ giữ nguyên nhãn đội, quay lại làm là đội nguyên vẹn như cũ.',
      'Chặn kéo trưởng nhóm đang lãnh đội này sang đội khác — kể cả qua sửa hồ sơ nhân sự; muốn chuyển phải đổi trưởng nhóm đội cũ trước, tránh đội «mồ côi» không ai quản.',
      'Người được cấp quyền «Quản lý Users» (không phải admin/kế toán) không thể tự thêm mình vào đội khác hay tự bổ nhiệm mình làm trưởng nhóm — chặn cả 3 đường: sửa đội, xếp thành viên, tạo đội mới.',
      'Tạo đội bị lỗi giữa chừng (ví dụ mạng chập chờn ở bước xếp thành viên) không còn dính «Mã đội đã tồn tại» khi bấm Lưu lại.',
      'Danh sách nhân sự trong màn hình xếp đội tự làm mới sau khi tạo/sửa/khóa tài khoản; lỗi tải sẽ báo rõ thay vì treo «Đang tải...» mãi. Trần danh sách nâng 200 → 500 người.',
    ],
    test: [
      'Quản trị viên: Quản lý tài khoản → khối «Đội nhóm» → «Tạo đội» → đặt tên/mã đội, chọn trưởng nhóm, tick thành viên → Lưu → thấy thẻ đội kèm sĩ số.',
      'Mọi người: menu Nhân sự → nút «Đội nhóm» → xem sơ đồ đội của công ty.',
      'Trưởng nhóm: sau khi được xếp đội, mở Data khách — chỉ thấy và chia được data trong nhóm mình.',
    ],
  },
  {
    date: '14/08/2026',
    title: 'Luồng chia data theo nhóm kinh doanh: CSKH → Trưởng nhóm → Sale',
    tag: 'RELEASE',
    news: [
      'Chia data đúng luồng công ty: Admin CSKH nhập data lên hệ thống → chia cho Trưởng nhóm Kinh doanh (hoặc chia thẳng cho sale) → Trưởng nhóm chia tiếp cho sale trong nhóm mình → Sale liên hệ, tư vấn và cập nhật tình trạng chăm sóc.',
      'Trưởng nhóm Kinh doanh từ nay CHỈ thấy data và nhân sự thuộc nhóm mình — data nhóm khác không hiện, kể cả khi tìm kiếm, xem pipeline hay xuất file.',
      'Admin CSKH chia data thay trưởng nhóm được ngay: ô «Giao cho» hiện đủ nhân viên kinh doanh + trưởng nhóm toàn công ty mà KHÔNG cần được cấp quyền «Xem Nhân sự» (danh sách chỉ có tên + đội, không lộ SĐT hay lương của ai).',
      'Quản trị viên quản lý Đội ngay trên hệ thống: tạo/sửa đội, chọn trưởng nhóm — chọn ai làm trưởng nhóm là người đó tự động được kéo về đội đó.',
    ],
    fixes: [
      'Tick «Xem Nhân sự» cho vai trò tự tạo (vd Admin CSKH) nay CÓ hiệu lực thật với danh sách nhân sự — trước đây chỉ tài khoản quản trị mới mở được trang này dù đã tick quyền (đúng phản ánh của bộ phận CSKH).',
      'Giao data hàng loạt trước nay bấm là báo «Lead không tồn tại» — đã sửa tận gốc, giờ giao được thật và báo rõ bao nhiêu lead được giao / bị bỏ qua vì ngoài phạm vi.',
      'Trưởng nhóm chưa được xếp đội vẫn mở, sửa và thấy đủ SĐT lead của CHÍNH mình (trước bản này thấy trong danh sách nhưng bấm vào là báo không có quyền).',
      'Tự đổi Đội hoặc Bộ phận trong hồ sơ cá nhân đã bị chặn — chuyển nhóm/bộ phận là việc của quản trị viên hoặc kế toán, tránh tự mở rộng phạm vi xem data khách.',
      'Xuất file CSV data khách nay theo đúng phạm vi từng người: trưởng nhóm chỉ xuất được nhóm mình, sale chỉ xuất lead của mình; các vai trò ngoài kinh doanh (kế toán, điều hành, giám sát) không tải được danh bạ khách nữa.',
      '«Ký HĐ Thiết kế» phải chuyển từng lead một (hệ thống tự tạo Khách hàng + Dự án + Hợp đồng kèm theo) — chặn đổi hàng loạt để không sót dự án nào.',
    ],
    test: [
      'Admin CSKH: mở Data khách → chọn một lead → ô «Giao cho» có đủ danh sách sale + trưởng nhóm để chia, không cần nhờ admin.',
      'Trưởng nhóm (đã có đội): mở Data khách — chỉ thấy lead nhóm mình; trang Nhân sự chỉ thấy người trong nhóm; ô «Giao cho» chỉ có người nhóm mình.',
      'Sale: vẫn chỉ thấy lead của mình như trước; nhận lead mới là thấy ngay trong danh sách và cập nhật tình trạng bình thường.',
    ],
  },
  {
    date: '14/08/2026',
    title: 'Trợ lý AI hoạt động thật + khóa AI cá nhân cho ai muốn dùng riêng',
    tag: 'RELEASE',
    news: [
      'Các tính năng AI (chấm điểm lead, gợi ý Sales Co-Pilot, phân tích – nhận định) nay chạy THẬT trên máy chủ: công ty đã gắn khóa AI chung, không cần ai cài gì thêm.',
      'Ai muốn dùng khóa AI riêng: vào Cài đặt → thẻ «Khóa AI cá nhân» (mọi vai trò đều có), dán khóa Groq của bạn (tạo miễn phí tại console.groq.com) — từ đó AI ưu tiên chạy bằng khóa của bạn, không tốn hạn mức chung của công ty. Không bắt buộc: bỏ trống thì dùng khóa chung như bình thường.',
      'Khóa cá nhân lỡ sai hoặc hết hạn mức thì hệ thống tự quay về khóa chung — công việc không bị gián đoạn. Có nút «Kiểm tra» để thử khóa ngay sau khi lưu.',
    ],
    fixes: [
      'Khóa của bạn được giữ kín: mọi màn hình và API chỉ hiện dạng che (gsk_****xxxx), không bao giờ hiện đầy đủ; hệ thống chỉ nhận đúng khóa Groq và không bao giờ gửi khóa của bạn sang dịch vụ AI khác.',
      'Nút «Kiểm tra kết nối AI» của quản trị viên nay test đúng khóa CHUNG của hệ thống — trước bản này, nếu quản trị viên có khóa riêng thì nút test chạy bằng khóa riêng đó, khóa chung hỏng cũng không phát hiện ra.',
    ],
    test: [
      'Bất kỳ ai: mở một Lead → xác nhận phần chấm điểm / gợi ý Co-Pilot có nội dung AI (không còn im lặng như trước).',
      'Ai muốn dùng khóa riêng: Cài đặt → «Khóa AI cá nhân» → dán khóa gsk_… → «Lưu khóa» → bấm «Kiểm tra» thấy AI trả lời là xong.',
      'Quản trị viên: Cài đặt → «Kiểm tra kết nối AI» → xác nhận trả lời "ok" (đây là khóa chung, không phải khóa riêng của bạn).',
    ],
  },
  {
    date: '13/08/2026',
    title: 'Dọn sạch dữ liệu mẫu — CRM từ nay 100% là số thật',
    tag: 'RELEASE',
    news: [
      'Đã xóa toàn bộ dữ liệu MẪU dùng để dựng hệ thống (các dự án "Chị Mai", "Anh Tuấn"…, khách hàng, báo giá, hợp đồng, sổ giao dịch TX-001→012, kho vật tư VT-001→010 và 4 chi phí cố định tháng 6). Từ giờ mọi con số trong CRM đều là dữ liệu thật của công ty — thấy gì tin nấy.',
      'Ghi chú công việc trong Dự án nay đính kèm được NHIỀU ảnh một lúc: chọn bao nhiêu ảnh thì lưu đủ bấy nhiêu (trước đây chọn 3 ảnh chỉ lưu được 1 mà không báo gì).',
      'Hai thẻ cảnh báo "Lead quá hạn liên hệ" và "Việc quá hạn" ở Tổng quan nay đếm số THẬT từ máy chủ theo đúng phạm vi của bạn — trước đây một thẻ hiện số 4 cố định, một thẻ luôn hiện 0.',
    ],
    fixes: [
      'Trang Tài chính và trang Kho: khi máy chủ trục trặc, trước đây màn hình âm thầm hiện bảng lương/chi phí/tồn kho MẪU trông y như thật — nay hiện thông báo lỗi rõ ràng và để trống bảng, không bao giờ đưa số giả.',
      'Menu "Tài chính" nay chỉ hiện với người có quyền Xem Lợi nhuận (P&L) — trước đây Trưởng nhóm/Sale thấy menu nhưng vào chỉ gặp lỗi.',
      'Ô "Upload file thiết kế / tài liệu" trong công việc: trước đây chọn file PDF/DWG/SKP trông như đã đính kèm nhưng thực tế KHÔNG lưu — nay ô này nhận ảnh (lưu thật vào ghi chú), còn tài liệu nặng thì hướng dẫn gửi vào nhóm Telegram dự án rồi dán link vào ô «Lưu File», đúng quy trình công ty.',
    ],
    test: [
      'Bất kỳ ai: mở Dự án / Khách hàng / Kế toán — xác nhận KHÔNG còn thấy "Chị Mai", "Anh Tuấn", TX-001… Danh sách trống là ĐÚNG (chưa nhập dự án thật), không phải lỗi.',
      'Thợ/PM: vào một công việc, đính 3 ảnh + ghi chú, bấm «Đăng cập nhật» → xác nhận đủ 3 ảnh xuất hiện trong dòng hoạt động.',
      'Kế toán: vào trang Kho — kho hiện đang TRỐNG là đúng (vật tư mẫu đã xóa); nhập vật tư thật để bắt đầu theo dõi tồn kho.',
    ],
  },
  {
    date: '13/08/2026',
    title: 'Phân quyền có hiệu lực thật + 4 vai trò theo phòng ban + phiên tự gia hạn',
    tag: 'RELEASE',
    news: [
      'Trang Phân quyền nay có hiệu lực THẬT: tắt một ô quyền là máy chủ chặn luôn, không chỉ ẩn nút trên màn hình. Ai bị chặn sẽ thấy thông báo rõ ràng "Bạn chưa được cấp quyền «…»" kèm hướng dẫn nhờ quản trị viên mở.',
      'Thêm 4 vai trò dựng sẵn cho các phòng: Quản lý dự án, Thiết kế, Giám sát thi công, Thu mua — gán cho nhân sự mới là vào đúng việc của phòng mình, không thấy số liệu tài chính. Quản trị viên vẫn chỉnh được từng ô quyền trên trang Phân quyền như vai trò tự tạo.',
      'Đang làm việc thì phiên tự gia hạn: dùng app liên tục sẽ không bao giờ bị văng giữa chừng nữa. Chỉ khi bỏ máy quá 12 tiếng liền mới phải đăng nhập lại.',
    ],
    fixes: [
      'Trước đây ai đăng nhập cũng gọi được số liệu tài chính (sổ giao dịch, chi phí, cơ cấu hoa hồng, danh bạ nhà cung cấp kèm giá mua) nếu biết đường dẫn — nay máy chủ chặn đúng theo bảng Phân quyền.',
      'Danh sách hoa hồng: trước đây máy chủ gửi hoa hồng của TẤT CẢ mọi người về máy rồi mới ẩn trên màn hình; nay ai chưa được cấp quyền "Xem hoa hồng người khác" thì máy chủ chỉ trả về đúng phần của người đó.',
      'LƯU Ý cho Trưởng nhóm và Nhân viên Sale: hai vai trò này không còn thấy tab "Tổng quan" và "Sổ giao dịch" trong trang Kế toán (vào thẳng tab Hoa hồng), và Trưởng nhóm chỉ thấy hoa hồng của chính mình. Nếu công việc cần xem, nhờ quản trị viên mở quyền "Xem Lợi nhuận (P&L)" / "Xem hoa hồng người khác" trên trang Phân quyền.',
      'Vai trò "Giám đốc" không dùng từ lâu đã được gỡ khỏi các danh sách chọn cho gọn (tài khoản cũ nếu có vẫn hoạt động bình thường).',
    ],
    test: [
      'Quản trị viên: vào Phân quyền, thấy 4 cột vai trò mới (Quản lý dự án, Thiết kế, Giám sát thi công, Thu mua) bên cạnh các vai trò cũ.',
      'Trưởng nhóm: mở trang Kế toán → xác nhận vào thẳng tab Hoa hồng và danh sách chỉ có tên mình.',
      'Bất kỳ ai: làm việc liên tục qua giờ thứ 7-8 trong ngày → xác nhận KHÔNG bị văng ra trang đăng nhập giữa chừng.',
    ],
  },
  {
    date: '13/08/2026',
    title: 'Hết cảnh "Không thể tải dữ liệu" — nay báo đúng là phiên đã hết hạn',
    tag: 'RELEASE',
    news: [
      'Phiên đăng nhập kéo dài 12 tiếng thay vì 8 tiếng — đủ trọn một ngày làm việc, không còn bị văng giữa buổi chiều.',
      'Khi phiên hết hạn, hệ thống tự đưa về trang đăng nhập kèm dòng "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục." — biết ngay phải làm gì.',
    ],
    fixes: [
      'Lỗi nhiều bạn báo: mở trang Quy trình (và cả Dự án, Khách hàng, Kho, Kế toán, Nhân sự, KPI) thì hiện "Không thể tải dữ liệu. Vui lòng thử lại.", bấm "Thử lại" bao nhiêu lần cũng vậy. Nguyên nhân KHÔNG phải hỏng dữ liệu: phiên đăng nhập đã hết hạn nhưng màn hình vẫn hiện tên và menu như đang đăng nhập, nên không ai biết chỉ cần đăng nhập lại là xong.',
      'Nay chỉ cần thoát ra đăng nhập lại một lần là hết — không phải chờ ai sửa.',
    ],
    test: [
      'Bạn nào đang gặp lỗi: bấm Đăng xuất rồi đăng nhập lại, mở trang Quy trình xem đã lên danh sách khách chưa.',
      'Sáng hôm sau mở máy: nếu bị đưa về trang đăng nhập kèm dòng chữ vàng "Phiên đăng nhập đã hết hạn" thì là đúng, cứ đăng nhập lại bình thường.',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Trợ lý AI biết nhớ — gợi ý việc cần làm với từng khách',
    tag: 'RELEASE',
    news: [
      'Thẻ khách hàng (Lead) có thêm ô "Gợi ý AI": bấm "Xin gợi ý" là hệ thống đề xuất việc nên làm tiếp với khách này, kèm lý do và mẫu tin nhắn để gửi luôn.',
      'Mỗi gợi ý có 2 nút "Đã làm" / "Bỏ qua". Bấm xong, lần sau hệ thống sẽ đề xuất việc KHÁC chứ không nhắc lại đúng câu vừa rồi.',
      'Ngay dưới ô gợi ý là danh sách các gợi ý đã đưa trước đó cùng phản hồi của mình — mở thẻ khách ra là biết đã làm tới đâu.',
      'Mỗi gợi ý ghi rõ do "AI viết" hay "theo bộ luật", để không ai nhầm câu máy tự suy ra là câu AI phân tích.',
    ],
    fixes: [
      'Trước đây mọi phần AI (chấm điểm khách, nhận định kinh doanh, gợi ý hành động) đều chạy lại từ con số 0 mỗi lần — không nhớ gì cả. Nay kết quả được lưu lại, hỏi lại đúng câu cũ trong ngày thì lấy bản đã có, không tốn thêm lượt gọi AI.',
      'Điểm AI của khách hàng và nhận định trong báo cáo BOD nay có lịch sử, xem lại được thay vì bị ghi đè mất.',
    ],
    test: [
      'Một bạn Sale: mở 1 thẻ khách bất kỳ → bấm "Xin gợi ý" → đọc gợi ý → bấm "Đã làm".',
      'Cũng bạn đó: bấm "Xin gợi ý" lần nữa, xác nhận gợi ý mới KHÁC gợi ý vừa bấm "Đã làm".',
      'Đóng thẻ khách rồi mở lại: xác nhận phần "Đã gợi ý trước đó" còn ghi lại việc đã làm.',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Nhân viên Sale xem được KPI của mình',
    tag: 'RELEASE',
    news: [
      'Nhân viên Sale mở được trang KPI: thẻ "Cá nhân" xem điểm, chỉ số và cảnh báo rủi ro của chính mình; thẻ "Bảng xếp hạng" xem mình đang đứng thứ mấy trong tháng.',
      'Bảng xếp hạng hiện tên 5 người dẫn đầu và dòng của chính người đang xem; những dòng còn lại chỉ ghi "Nhân viên #thứ tự" — không ai thấy tên kèm điểm của người ngoài top 5.',
    ],
    fixes: [
      'Mục "KPI" vốn đã được ghim sẵn trên thanh bên của Nhân viên Sale nhưng bấm vào là bị đá về Tổng quan — link chết từ đầu. Nay bấm vào mở đúng trang.',
      'Ngược lại, Kế toán không được xem KPI mà vẫn thấy mục "KPI" trong menu; nay mục này ẩn đi thay vì để bấm rồi bị đá ra.',
      'Bảng ở trang Phân quyền trước đây ghi Kế toán KHÔNG xem được Báo giá, trong khi thực tế xem được. Nay bảng ghi đúng thực tế.',
    ],
    test: [
      'Một bạn Sale: vào KPI → xác nhận thẻ "Cá nhân" có điểm, và thẻ "Bảng xếp hạng" có dòng của mình.',
      'Cũng bạn đó: xác nhận KHÔNG có thẻ "Đội nhóm" (thẻ đó dành cho trưởng phòng và điều phối KD).',
      'Kế toán: xem thanh bên, xác nhận mục "KPI" đã biến mất.',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Điều phối KD xem được KPI đội và Góp ý',
    tag: 'RELEASE',
    news: [
      'Điều phối KD (Admin CSKH) mở được thẻ "Đội nhóm" trong trang KPI — thấy điểm và chỉ số của cả đội Kinh doanh, để biết ai đang tải nặng và ai đang hụt số trước khi chia data tiếp.',
      'Điều phối KD vào được trang Góp ý: đọc phản ánh của nhân viên, đổi trạng thái và trả lời ngay (câu trả lời vẫn tự bắn về Telegram của người gửi như cũ).',
    ],
    fixes: [
      'Hai trang trên trước đây hiện ra rồi báo "chưa được cấp quyền" — giao diện đã mở nhưng máy chủ vẫn chặn. Nay hai bên khớp nhau.',
      'Mục "Góp ý" trên thanh bên trước đây hiện với Trưởng phòng, Nhân viên Sale, Kế toán và Giám sát, nhưng bấm vào là bị đá về Tổng quan. Nay chỉ hiện với người thật sự được xem.',
    ],
    test: [
      'Chị Ngọc Hạnh / Mỹ Liên / Ngọc Bích: vào KPI → chọn thẻ "Đội nhóm", xác nhận có danh sách nhân viên và điểm.',
      'Cũng 3 chị: vào Góp ý, mở 1 phản ánh, đổi trạng thái sang "Đang xem xét" và gửi thử một câu trả lời.',
      'Trưởng phòng / Sale / Kế toán: xem thanh bên, xác nhận mục "Góp ý" đã biến mất (đúng quyền).',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Soát toàn bộ CRM trước khi mở rộng — danh sách hiện đủ, báo lỗi nói thật',
    tag: 'RELEASE',
    news: [
      'Danh sách Lead, Dự án, Khách hàng giờ nạp ĐỦ mọi bản ghi. Trước đây hệ thống chỉ lấy 50 dòng đầu rồi mới lọc/sắp xếp, nên khi công ty vượt 50 lead thì phần dư biến mất không một lời báo — bộ lọc và con số thống kê đều tính thiếu mà nhìn vẫn bình thường.',
      'Ô tìm kiếm nhanh (Ctrl+K) cũng tìm trên toàn bộ lead và dự án thay vì 100 cái đầu.',
      'Trang Nhà cung cấp dùng được đầy đủ: nút "So sánh giá" chạy thật (trước đây bấm không ra gì), thẻ báo giá hiện đúng ngày báo giá, bảng so sánh có lại dấu tiếng Việt.',
      'Các nút Lưu / Thêm / So sánh bị khoá trong lúc đang gửi — bấm đúp không còn tạo bản ghi trùng.',
    ],
    fixes: [
      'Trang Kế toán không còn trắng cả trang với Trưởng nhóm và Nhập liệu. Nguyên nhân: hệ thống gọi luôn bảng lương (mục chỉ Giám đốc + Kế toán được xem) rồi lấy lỗi đó chặn cả trang.',
      'Trang Báo cáo hết cảnh hiện "Không có dữ liệu" khi thực chất máy chủ đang lỗi — nguy hiểm vì nhìn như công ty không có số. Nay báo rõ phần nào chưa tải được và có nút Tải lại.',
      'Thông báo lỗi phân biệt rõ "tài khoản chưa được cấp quyền" với "hệ thống đang lỗi" — hết cảnh báo nhầm sự cố khi thật ra chỉ là thiếu quyền.',
      'Thêm nhà cung cấp mới không còn mất tên người liên hệ sau khi lưu.',
      'Gỡ hẳn nút gạt "Tập luyện ↔ Làm việc" trên thanh bên — nút vẫn hiện dù chế độ đã nghỉ, bấm nhầm là rơi sang dữ liệu MẪU.',
      'Dịch nốt chữ tiếng Anh còn sót: Deal Value → Giá trị hợp đồng, Budget → Ngân sách, AI Score → Điểm AI, Export CSV → Xuất bảng tính, Office → Văn phòng, Upload → Tải lên, Tasks → Công việc.',
    ],
    test: [
      'Cả nhà: mở Lead / Dự án / Khách hàng, kiểm tra số ở góc danh sách khớp với thực tế (không dừng ở 50).',
      'Trưởng nhóm + Nhập liệu: mở trang Kế toán, xác nhận trang lên bình thường (mục Bảng lương trống là đúng — không được cấp quyền).',
      'Mua hàng/admin: vào Nhà cung cấp → chọn 1 vật tư → bấm "So sánh giá", xác nhận ra bảng so sánh.',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Sửa nút "+" tạo vai trò bị che & trang Dự án báo lỗi',
    tag: 'HOTFIX',
    fixes: [
      'Nút "+" (tạo vai trò mới) cạnh ô Vai trò trong form Tạo tài khoản đã hiện lại — từ hôm tạo vai trò tùy chỉnh đầu tiên, ô Vai trò bị giãn quá khổ và đẩy nút "+" nấp sau ô Bộ phận nên nhìn như mất hẳn (cảm ơn Nghĩa planning đã báo).',
      'Trang Dự án báo "Không thể tải dữ liệu — vui lòng thử lại" đã hết. Nguyên nhân: cơ sở dữ liệu trên máy chủ thật thiếu vài cột được thêm hồi cuối tháng 7 nên máy chủ lỗi mỗi lần đọc dự án. Kéo theo trang này cũng hoạt động lại: chi tiết dự án, dự án theo phòng ban ở Trang chủ, dự án liên kết trong chi tiết khách hàng, và Lãi lỗ theo dự án.',
      'Máy nào còn lưu phiên "Chế độ Tập luyện" cũ sẽ tự đăng xuất về màn hình đăng nhập thật — tránh cảnh nhìn thấy dữ liệu MẪU mà tưởng dữ liệu công ty.',
    ],
    test: [
      'Nghĩa/admin: vào Tài khoản → "+ Tạo tài khoản" → kiểm tra nút "+" nhỏ màu vàng nằm ngay cạnh ô Vai trò, bấm vào mở được bảng tạo vai trò mới.',
      'Cả nhà: mở trang Dự án, xác nhận danh sách/bảng kanban lên bình thường, không còn thẻ báo lỗi.',
    ],
  },
  {
    date: '12/08/2026',
    title: 'Chia data lead cho team Kinh doanh — gắn sale ngay khi tạo lead',
    tag: 'RELEASE',
    news: [
      'Form "Tạo Lead mới" có ô "Gắn nhân viên KD phụ trách" — nhập lead từ marketing là giao thẳng cho sale, không cần vào chi tiết lead đổi lại (theo phản hồi team KD). Bỏ trống thì người tạo tự phụ trách như cũ.',
      'Team CSKH (vai trò tùy chỉnh thuộc bộ phận Kinh doanh) chính thức là điều phối data: thấy toàn bộ lead, đủ số điện thoại, được gắn/đổi người phụ trách — không còn cảnh chỉ admin mới giao được lead.',
      'Ai được giao lead sẽ nhận thông báo trong app (chuông 🔔) kèm link mở thẳng lead đó.',
      'Chia data đúng người: tài khoản nhân viên KD chỉ thấy lead được giao cho mình — cả bảng kanban, danh sách lẫn số liệu pipeline.',
    ],
    fixes: [
      'Vai trò tùy chỉnh KHÔNG thuộc bộ phận Kinh doanh (nếu sau này tạo) chỉ còn thấy lead của chính mình thay vì thấy tất cả — vá lỗ hổng phân quyền dữ liệu.',
    ],
    test: [
      'CSKH: tạo lead mới → chọn tên sale ở ô "Gắn nhân viên KD phụ trách" → hỏi bạn sale đó xem có nhận được thông báo + thấy lead trong bảng của mình không.',
      'Sale: đăng nhập và xác nhận chỉ thấy lead của mình, không thấy lead của người khác.',
    ],
  },
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
