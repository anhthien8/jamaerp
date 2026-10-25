/**
 * Nội dung Sổ tay sử dụng (/huong-dan) — NGUỒN SỰ THẬT duy nhất của hướng dẫn.
 * File docs/HUONG_DAN_SU_DUNG_CRM.md cũ đã ngừng cập nhật (repo public, không
 * muốn lộ quy trình nội bộ) — mọi chỉnh sửa hướng dẫn làm TẠI ĐÂY.
 *
 * Sinh lần đầu 09/09/2026 từ workflow 7 agent đọc mã nguồn hiện tại (không chép
 * guide cũ). Quy ước: viết cho nhân viên không rành máy tính, thuần Việt, câu
 * ngắn hướng hành động; trong text hỗ trợ **đậm** và `code` (page tự render).
 * Nhãn nút/menu/quyền PHẢI khớp mã nguồn — đổi tính năng thì sửa mục tương ứng
 * ở đây trong cùng một commit.
 */

export interface GuideBlock {
  type: 'p' | 'h3' | 'list' | 'steps' | 'table' | 'tip' | 'warn';
  text?: string;
  items?: string[];
  header?: string[];
  rows?: string[][];
}

export interface GuideSection {
  id: string;
  icon: string; // tên LineIcon hợp lệ
  title: string;
  roles?: string[]; // badge vai trò liên quan; bỏ trống = mọi người
  blocks: GuideBlock[];
}

export const GUIDE_UPDATED = '25/10/2026';

export const GUIDE_SECTIONS: GuideSection[] = [
  {
    "id": "dang-nhap",
    "icon": "lock",
    "title": "Đăng nhập vào hệ thống",
    "blocks": [
      {
        "type": "p",
        "text": "Mở trình duyệt (Chrome, Safari...), vào địa chỉ **crm.jamahome.vn**. Trên điện thoại hay máy tính đều dùng được."
      },
      {
        "type": "steps",
        "items": [
          "Ô **Email hoặc tên đăng nhập**: gõ tên ngắn công ty cấp (vd `thao.sale`) hoặc email đầy đủ — cách nào cũng được.",
          "Ô **Mật khẩu**: gõ mật khẩu của bạn.",
          "Bấm nút vàng **Đăng nhập**. Vào thẳng trang Tổng quan là xong."
        ]
      },
      {
        "type": "h3",
        "text": "Quên mật khẩu thì làm sao?"
      },
      {
        "type": "steps",
        "items": [
          "Ở trang đăng nhập, bấm dòng chữ nhỏ **Quên mật khẩu?** (dưới nút Đăng nhập).",
          "Gõ email hoặc tên đăng nhập → bấm **Gửi mã qua Telegram**.",
          "Mở Telegram, chép **mã 6 số** bot vừa gửi.",
          "Quay lại, dán mã + gõ mật khẩu mới (ít nhất 6 ký tự) → bấm **Đặt lại mật khẩu** → đăng nhập bằng mật khẩu mới."
        ]
      },
      {
        "type": "warn",
        "text": "Cách này chỉ chạy khi bạn **đã liên kết Telegram** trong mục Cài đặt (xem phần Cài đặt bên dưới). Chưa liên kết? Nhắn Admin đặt lại mật khẩu hộ."
      },
      {
        "type": "tip",
        "text": "Đang dùng app liên tục thì phiên đăng nhập **tự gia hạn** — không lo bị văng giữa chừng. Chỉ khi bỏ máy quá lâu (khoảng nửa ngày) mới phải đăng nhập lại; lúc đó màn hình đăng nhập sẽ báo «Phiên đăng nhập đã hết hạn» — cứ đăng nhập lại bình thường."
      }
    ]
  },
  {
    "id": "giao-dien-chung",
    "icon": "compass",
    "title": "Làm quen giao diện",
    "blocks": [
      {
        "type": "p",
        "text": "Trên **máy tính**: menu nằm cột trái, chia **2 tầng**: dưới **Tổng quan** là các khối **Việc hằng ngày** (Phê duyệt, Chấm công, Dự án, KPI), **Kinh doanh** (Quy trình, Khách hàng, Báo giá, Hợp đồng…), **Kho hàng**, **Tài chính**, **Nhân sự**, **Trợ giúp** (Sổ tay, Có gì mới, Góp ý, Cài đặt). Bấm tên khối để mở/đóng; con số xám cạnh khối là số mục bên trong. Khối chứa trang bạn đang xem tự mở sẵn, và app nhớ khối nào bạn đã mở/đóng. Bạn chỉ thấy mục mình có quyền dùng. Trên cùng cột trái có ô **Tìm kiếm...** — bấm vào (hoặc nhấn Ctrl+K) để tìm nhanh khách, dự án."
      },
      {
        "type": "p",
        "text": "**Bấm vào ảnh đại diện + tên của bạn ở góc dưới cột menu** để mở menu tài khoản: **Hồ sơ 360° của tôi** (thông tin cá nhân, giấy tờ, hợp đồng, chấm công, lương, nghỉ phép của chính bạn), **Đổi ảnh đại diện**, **Cài đặt tài khoản** (mật khẩu, Telegram, thông báo), **Sổ tay hướng dẫn** và **Đăng xuất**."
      },
      {
        "type": "p",
        "text": "Trên **điện thoại**: menu đầy đủ mở bằng nút **☰** góc trên trái. Ngoài ra có **thanh nút dưới đáy màn hình** (tối đa 5 nút: Tổng quan, Quy trình, Dự án, Chấm công, Phê duyệt — tùy quyền của bạn) để bấm nhanh bằng ngón cái."
      },
      {
        "type": "p",
        "text": "Từ 23/10/2026 giao diện dùng **nền đen, thẻ phẳng, nút vàng bo tròn**: nút vàng đặc luôn là việc chính của màn hình (Tạo, Lưu, Gửi), nút viền mảnh là việc phụ. Đứng ngoài nắng khó nhìn thì bấm nút **🌙 TRONG NHÀ** ở cột menu để chuyển sang **Ngoài trời** (nền sáng)."
      },
      {
        "type": "h3",
        "text": "Chuông thông báo 🔔"
      },
      {
        "type": "p",
        "text": "Nút chuông ở **góc trên phải**. Có việc mới thì hiện chấm đỏ kèm con số. Bấm vào sẽ mở bảng thông báo chia 2 nhóm: **Cần xử lý** (việc đang chờ bạn) và **Gần đây** (tin tức chung). Bấm 1 dòng để nhảy thẳng tới việc đó (lead hoặc dự án tự mở ra, cả trên điện thoại); bấm **Đánh dấu đã đọc** để xóa chấm đỏ."
      },
      {
        "type": "h3",
        "text": "Banner xanh đầu trang"
      },
      {
        "type": "p",
        "text": "Dải chữ **CHẾ ĐỘ LÀM VIỆC — Dữ liệu thật từ hệ thống** ở đầu mỗi trang nhắc bạn: mọi số liệu đang là **dữ liệu thật** của công ty. Sửa gì là sửa thật, nên cẩn thận nhé."
      },
      {
        "type": "h3",
        "text": "Nút ☀️ NGOÀI TRỜI — dành cho anh em công trình"
      },
      {
        "type": "p",
        "text": "Cuối menu trái có nút **TRONG NHÀ 🌙 / NGOÀI TRỜI ☀️**. Đứng ngoài nắng nhìn màn hình không rõ? Bấm nút này để chuyển sang nền sáng, chữ đậm, dễ đọc dưới nắng. Bấm lại để về như cũ. Máy sẽ nhớ lựa chọn của bạn."
      },
      {
        "type": "tip",
        "text": "**Cài app ra màn hình chính:** mở web bằng điện thoại, ngay trang đăng nhập sẽ có thanh dưới «Cài JAMA HOME lên điện thoại». Android/Samsung: bấm **Cài đặt** là xong. iPhone/iPad: bấm **Thêm** để xem 3 bước — nút **Chia sẻ ⬆️** của Safari → **Thêm vào MH chính** → **Thêm**. Lỡ bấm ✕ thì 7 ngày sau thanh nhắc lại, hoặc đăng xuất ra trang đăng nhập là thấy. Sau đó mở app 1 chạm như Zalo, khỏi gõ địa chỉ."
      }
    ]
  },
  {
    "id": "trang-tong-quan",
    "icon": "home",
    "title": "Trang «Tổng quan» — mỗi người thấy một kiểu",
    "blocks": [
      {
        "type": "p",
        "text": "Đăng nhập xong là vào trang **Tổng quan**. Hệ thống tự chọn số liệu hợp với công việc của bạn — nên màn hình của bạn có thể khác đồng nghiệp, đó là bình thường."
      },
      {
        "type": "table",
        "header": [
          "Bạn là ai",
          "Bạn thấy gì"
        ],
        "rows": [
          [
            "Sale / CSKH",
            "4 thẻ của riêng bạn: **Lead Của Tôi**, Giá trị pipeline, Hợp đồng, **Hoa Hồng** đã duyệt kỳ gần nhất."
          ],
          [
            "Trưởng phòng",
            "Số liệu chung (lead, pipeline, dự án, hợp đồng) + khối **⚡ Cần xử lý ngay**: khách quá hạn, đơn chờ duyệt, tăng ca chờ — bấm vào là tới nơi."
          ],
          [
            "Giám sát",
            "Số liệu chung + khối **🏗️ Dự án đang đến phòng bạn** — dự án sắp/đang cần phòng bạn xử lý, kèm cảnh báo 🔴 quá hạn, 🟠 cận hạn."
          ],
          [
            "Kế toán",
            "**Tổng Thu / Tổng Chi** lấy từ sổ kế toán thật, kèm lãi ròng, dự án và hợp đồng."
          ],
          [
            "Ban giám đốc / Admin",
            "Bức tranh toàn công ty: giá trị pipeline, tổng lead, dự án đang chạy, tổng giá trị hợp đồng."
          ]
        ]
      },
      {
        "type": "tip",
        "text": "Hầu hết các thẻ số đều **bấm được** — bấm thẻ Hợp đồng là nhảy sang trang Hợp đồng, khỏi tìm menu."
      },
      {
        "type": "warn",
        "text": "Thấy dấu **«—»** thay vì con số nghĩa là mục đó chưa có/chưa tải được dữ liệu, **không phải bằng 0**. Nếu đầu trang hiện khung đỏ «Chưa tải được số liệu», bấm nút **Tải lại** trong khung đó."
      }
    ]
  },
  {
    "id": "cai-dat",
    "icon": "settings",
    "title": "Trang «Cài đặt» — việc cá nhân của bạn",
    "blocks": [
      {
        "type": "p",
        "text": "Mở menu → **Cài đặt** (ai cũng vào được). Nhóm **Cá nhân** ở đầu trang là chỗ bạn cần quan tâm nhất."
      },
      {
        "type": "list",
        "items": [
          "**Thông tin cá nhân** — xem tên, email, vai trò, phòng ban của bạn. Sai thì báo Nhân sự/Admin sửa.",
          "**Ảnh đại diện** — bấm nút **máy ảnh vàng** trên vòng tròn tên → chọn ảnh (tự cắt vuông). Ảnh hiện ở thanh bên, danh sách Nhân sự và Hồ sơ 360°. Bấm **Gỡ ảnh** để quay về chữ cái đầu. Admin/Kế toán đổi hộ được ở Hồ sơ 360° của nhân viên.",
          "**Đổi mật khẩu** — gõ mật khẩu hiện tại + mật khẩu mới (ít nhất 6 ký tự) 2 lần → bấm **Đổi mật khẩu**.",
          "**Telegram Bot** — quan trọng! Liên kết xong bạn mới nhận nhắc việc qua Telegram và tự lấy lại mật khẩu khi quên.",
          "**Khóa AI cá nhân** — không bắt buộc, ai không rành cứ bỏ qua; hệ thống đã có AI chung dùng ổn."
        ]
      },
      {
        "type": "h3",
        "text": "Liên kết Telegram (làm 1 lần, mất 1 phút)"
      },
      {
        "type": "steps",
        "items": [
          "Mở Telegram, tìm **bot công ty** (chưa biết tên bot thì hỏi Admin).",
          "Nhắn cho bot chữ `/id` — bot trả về một **dãy số** (User ID của bạn).",
          "Quay lại trang Cài đặt, dán dãy số đó vào ô ở mục **Telegram Bot** → bấm **Lưu**.",
          "Nhắn `/start` cho bot để kiểm tra — thấy trạng thái ✅ Đã liên kết là xong."
        ]
      },
      {
        "type": "tip",
        "text": "Quên thao tác trên hệ thống? Kéo xuống thẻ **Thông tin hệ thống**, bấm nút **«Xem lại hướng dẫn từng bước theo vai trò»** — app sẽ dắt tay bạn đi lại từng bước đúng theo công việc của bạn."
      },
      {
        "type": "p",
        "text": "**Ai thấy thêm gì:** Admin thấy thêm nhóm «Tích hợp» (Cấu hình AI, Zalo, **Chấm công văn phòng** — khai IP mạng công ty + tọa độ VP để bảng công gắn nhãn ✓VP, và nối máy chấm công qua API) và «Sao lưu dữ liệu»; Admin + Ban giám đốc thấy thêm «Tự động hóa CSKH & Báo cáo» (trong đó có ô **«Nhóm Telegram Kho ảnh»** — chat ID nhóm «JAMA Công trình», kèm tình trạng kho và nút «🧪 Thử gửi 1 ảnh») và **«Chuẩn SLA đầu việc»**. Nhân viên bình thường không thấy các mục này — không phải máy bạn lỗi đâu."
      },
      {
        "type": "p",
        "text": "**Chuẩn SLA đầu việc** (Admin + Ban giám đốc): khai số ngày tiêu chuẩn cho từng đầu việc trong 19 đầu việc mẫu, số ngày chuẩn theo phòng (dùng cho việc tự thêm, không nằm trong 19 việc mẫu), và **số ngày trễ thì nhắc lên cấp trên**. Có công tắc tắt/bật toàn bộ việc nhắc, và nút **«▶️ Quét & nhắc ngay»** để chạy thử xem hệ thống đang thấy bao nhiêu việc quá hạn, bao nhiêu việc vượt SLA."
      }
    ]
  },
  {
    "id": "quy-trinh-lead",
    "icon": "kanban",
    "title": "Theo dõi khách tiềm năng trong «Quy trình»",
    "roles": [
      "Sale",
      "Trưởng nhóm KD",
      "CSKH"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Ai thấy mục này: **chỉ bộ phận Kinh doanh và Ban Giám Đốc** (siết từ 22/09). Thiết kế, Giám sát, Báo giá–Thu mua, Kế toán KHÔNG thấy menu «Quy trình» — và kể cả khi được tích thêm ô «Xem Leads» thì vẫn không xem được, vì hệ thống chặn theo bộ phận. Muốn ai xem lead thì phải chuyển bộ phận của họ sang Kinh doanh trong mục Tài khoản."
      },
      {
        "type": "p",
        "text": "Đây là bảng theo dõi khách tiềm năng (lead). Mỗi khách là một thẻ, mỗi cột là một giai đoạn. Khách đi từ trái sang phải cho tới khi chốt được deal."
      },
      {
        "type": "table",
        "header": [
          "Cột",
          "Nghĩa là gì"
        ],
        "rows": [
          [
            "🆕 Tiếp nhận mới",
            "Khách vừa vào, chưa ai tư vấn"
          ],
          [
            "💡 Đang tư vấn",
            "Đã liên hệ, đang trao đổi nhu cầu"
          ],
          [
            "📤 Đã gửi báo giá",
            "Đã gửi báo giá cho khách"
          ],
          [
            "🤝 Đang đàm phán",
            "Khách quan tâm, đang thương lượng"
          ],
          [
            "🏆 Deal đã thắng",
            "Khách đã chốt — xem mục «Deal đã thắng» bên dưới"
          ],
          [
            "❌ Mất",
            "Khách không làm nữa — bắt buộc chọn lý do"
          ]
        ]
      },
      {
        "type": "warn",
        "text": "Tên các cột vừa đổi ngày 05/09/2026 (ví dụ «Đã gửi báo giá», «Đang đàm phán»). Tài liệu cũ ghi tên khác là đã lỗi thời — cứ nhìn theo bảng trên."
      },
      {
        "type": "steps",
        "items": [
          "Muốn đổi giai đoạn: **kéo thẻ** sang cột khác và thả. Hoặc bấm vào thẻ, cuộn xuống phần «Chuyển giai đoạn» rồi bấm nút giai đoạn mới.",
          "Kéo thẻ vào cột **«Mất»**: thẻ chi tiết tự mở kèm ô chọn lý do (Ngân sách không phù hợp / Đã chọn đối thủ / Không phản hồi / Thay đổi kế hoạch / Lý do khác). Chọn xong bấm **«Xác nhận mất lead»** — không chọn lý do thì không chuyển được.",
          "Thêm khách mới: bấm nút **«+ Thêm Lead»** màu vàng ở góc phải trên.",
          "Cột đông khách chỉ hiện 25 thẻ đầu (số trên đầu cột vẫn là tổng thật). Cuộn xuống cuối cột, bấm **«Hiện thêm … thẻ»** để xem tiếp, bấm **«Thu gọn»** để gọn lại."
        ]
      },
      {
        "type": "p",
        "text": "Góc phải trên có 3 kiểu xem: **📋 Kanban** (bảng thẻ), **📊 Danh sách** (bảng dòng, bấm tiêu đề cột để sắp xếp) và **📅 Lịch**."
      },
      {
        "type": "p",
        "text": "Thanh «Lọc» phía trên giúp tìm nhanh: ô tìm tên/SĐT, nguồn, ưu tiên, khu vực, phân loại, **nhân viên KD phụ trách** (có mục «— Chưa phân công —»), và lọc theo **ngày** (Ngày cập nhật / Ngày thêm mới / Ngày liên hệ cuối — chọn Hôm nay, 7 ngày qua, Tháng này… hoặc Tùy chọn). Bấm **«✕ Xóa bộ lọc»** để về mặc định."
      },
      {
        "type": "tip",
        "text": "Thẻ có nhãn đỏ «⚠️ Quá hạn» nghĩa là hơn 3 ngày chưa ai đụng tới khách này — ưu tiên gọi lại ngay."
      }
    ]
  },
  {
    "id": "chia-data",
    "icon": "send",
    "title": "Chia data khách: CSKH → Trưởng nhóm → Sale",
    "roles": [
      "CSKH",
      "Trưởng nhóm KD"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Ai được giao/đổi người phụ trách: Quản trị viên, Trưởng nhóm KD và Điều phối KD (Admin CSKH). Sale thường không giao được — chỉ nhận."
      },
      {
        "type": "p",
        "text": "Luồng chuẩn: bạn CSKH nhập lead từ marketing → giao cho **trưởng nhóm** → trưởng nhóm chia tiếp cho **sale** trong nhóm mình. Ai được giao data nào thì chăm data đó."
      },
      {
        "type": "steps",
        "items": [
          "Khi **tạo lead mới**, kéo xuống sẽ thấy 2 ô: **«Trưởng nhóm phụ trách»** và **«Nhân viên kinh doanh»**. Chọn trưởng nhóm trước, rồi mới chọn được nhân viên trong nhóm đó.",
          "Chỉ chọn trưởng nhóm, bỏ trống ô nhân viên → data giao cho trưởng nhóm **chia tiếp trong nhóm**.",
          "Chọn cả nhân viên → data vào **thẳng** nhân viên đó.",
          "Bỏ trống cả hai ô → **bạn tự phụ trách** lead này."
        ]
      },
      {
        "type": "steps",
        "items": [
          "Muốn đổi người phụ trách lead đã có: bấm vào thẻ lead, nhìn dòng **«Phụ trách»** trong phần Thông tin liên hệ.",
          "Bấm nút **«✏️ Đổi»**, chọn tên trong danh sách — hệ thống lưu ngay và báo «Đã giao lead cho …»."
        ]
      },
      {
        "type": "p",
        "text": "Phạm vi nhìn thấy (3 tầng, từ 22/09): **Trưởng phòng Kinh doanh** thấy lead của **mọi nhân sự trong phòng**, kể cả các đội khác. **Trưởng nhóm** thấy lead **của nhóm mình** (kèm lead giao cho chính mình). **Sale** chỉ thấy lead **được giao cho mình**. CSKH thấy **tất cả** để phân chia. Ai kiêm cả trưởng phòng lẫn trưởng nhóm thì lấy quyền cao nhất là trưởng phòng. Không thấy lead của người khác là đúng thiết kế, không phải lỗi."
      },
      {
        "type": "tip",
        "text": "Nếu chọn đội mà báo «Đội này chưa có thành viên nào» — nhờ Quản trị viên xếp người vào đội ở trang «Tài khoản» trước rồi mới chia data được."
      }
    ]
  },
  {
    "id": "deal-thang",
    "icon": "zap",
    "title": "Cột «Deal đã thắng» — bước một chiều, cân nhắc kỹ",
    "roles": [
      "Sale",
      "Trưởng nhóm KD"
    ],
    "blocks": [
      {
        "type": "warn",
        "text": "Chuyển lead vào cột «🏆 Deal đã thắng» là bước KHÔNG LÙI ĐƯỢC. Chỉ chuyển khi khách đã chốt chắc chắn."
      },
      {
        "type": "p",
        "text": "Ngay khi thẻ vào cột này, hệ thống **tự động tạo** một loạt thứ cho bạn:"
      },
      {
        "type": "list",
        "items": [
          "**Khách hàng** mới trong menu «Khách hàng» (lấy đúng tên, SĐT, địa chỉ từ lead).",
          "**Dự án** mới trong menu «Dự án» (mã dạng PRJ-2026-xxxx) kèm sẵn **19 đầu việc mẫu**: từ 2D Concept, 3D Render… đến thi công, bàn giao, bảo hành.",
          "**Hợp đồng** trong menu «Hợp đồng» (mã dạng HD-PRJ-…) để theo dõi thu tiền."
        ]
      },
      {
        "type": "p",
        "text": "Vì đã sinh ra chừng đó dữ liệu nên thẻ ở cột này **không kéo đi đâu được nữa** — di chuột lên thẻ sẽ thấy dòng nhắc «Deal đã thắng — đã tạo Khách hàng + Dự án, không kéo lùi được»."
      },
      {
        "type": "tip",
        "text": "Lỡ chuyển nhầm? Đừng cố sửa tay — báo ngay Quản trị viên để xử lý dữ liệu đã sinh ra."
      }
    ]
  },
  {
    "id": "bao-gia-tuc-thi",
    "icon": "zap",
    "title": "«Báo giá tức thì» — báo giá sơ bộ trong 30 giây",
    "roles": [
      "Sale",
      "Trưởng nhóm KD",
      "CSKH"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Ai thấy mục này: **mọi nhân viên** (mở từ 22/10) — ai đang nói chuyện với khách cũng tra giá nhanh được."
      },
      {
        "type": "p",
        "text": "Trang này giúp bạn báo giá sơ bộ cho khách ngay khi khách còn «nóng», để chốt lịch khảo sát. Đây là giá ước lượng, không phải báo giá chính thức."
      },
      {
        "type": "steps",
        "items": [
          "Chọn kiểu công trình: **«🏗️ Xây mới»** hoặc **«🔨 Cải tạo»**.",
          "Xây mới có 2 cách nhập: **«📐 Nhập số liệu»** (điền Diện tích m² — bắt buộc, Loại nhà, Phòng ngủ, Ngân sách) hoặc **«🤖 Paste tin Zalo (AI)»** — dán nguyên tin nhắn khách nhắn, AI tự đọc ra số liệu.",
          "Cải tạo thì điền: Diện tích mỗi tầng, Số tầng, Ngân sách khách.",
          "Bấm **«⚡ Tạo báo giá»** và chờ vài giây."
        ]
      },
      {
        "type": "p",
        "text": "Kết quả xây mới ra **3 mức giá**: Cơ bản — Tiêu chuẩn — Cao cấp, mức hợp ngân sách khách nhất có nhãn vàng **«GỢI Ý»**. Bấm vào từng mức để xem bảng chi tiết hạng mục. Kết quả cải tạo ra tổng dự kiến kèm các nhóm hạng mục (Tháo dỡ, Kết cấu, Cửa…)."
      },
      {
        "type": "tip",
        "text": "Bấm nút **«📋 Copy text gửi Zalo»** — hệ thống đã soạn sẵn tin nhắn báo giá, bạn chỉ việc dán vào Zalo gửi khách."
      },
      {
        "type": "p",
        "text": "Nút **«📒 Xem bảng đơn giá»** ở góc phải trên mở bảng giá chuẩn để tra cứu. **Chỉ Giám đốc (tài khoản quản trị) sửa được đơn giá** (chốt 22/10) — mọi người khác chỉ xem. Trưởng phòng Báo giá thấy giá nào cần đổi thì báo quản trị."
      }
    ]
  },
  {
    "id": "ghi-hoat-dong",
    "icon": "message",
    "title": "Ghi lại mọi lần chăm khách + đánh giá CSKH",
    "roles": [
      "Sale",
      "CSKH"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Mọi cuộc gọi, ghi chú với khách đều nằm trong thẻ lead, phần **«Lịch sử hoạt động»**. Ghi đều tay thì ai xem thẻ cũng biết khách đang tới đâu — và bạn không bị nhãn «Quá hạn»."
      },
      {
        "type": "steps",
        "items": [
          "Bấm vào thẻ lead, cuộn xuống «Lịch sử hoạt động».",
          "Vội thì bấm **chip 1 chạm**: «📵 Không nghe máy», «🔁 Hẹn gọi lại», «📤 Đã gửi báo giá», «📅 Hẹn khảo sát» — một cái bấm là ghi xong.",
          "Muốn ghi kỹ hơn: gõ vào ô **«Thêm ghi chú...»** rồi bấm **«Gửi»** (hoặc phím Enter). Có ảnh (ảnh nhà khách, ảnh chụp tin nhắn...) thì bấm **📷** cạnh ô ghi chú hoặc dán ảnh thẳng vào ô, tối đa 6 ảnh mỗi ghi chú; ảnh hiện ngay trong lịch sử, bấm để phóng to. Ảnh lead chỉ người xem được lead mới thấy.",
          "Gọi khách ngay trên bảng: bấm **biểu tượng điện thoại** trên thẻ — máy gọi thật và hệ thống tự ghi nhận cuộc gọi kèm giờ."
        ]
      },
      {
        "type": "p",
        "text": "Trong thẻ còn có khối **«🤖 Gợi ý AI»**: bấm «Xin gợi ý» để hệ thống đề xuất việc nên làm tiếp với khách (kèm mẫu tin nhắn). Làm xong bấm **«✅ Đã làm»**, không hợp thì **«⏭️ Bỏ qua»** — AI sẽ nhớ và không nhắc lại."
      },
      {
        "type": "h3",
        "text": "🎧 Đánh giá chất lượng chăm sóc (CSKH)"
      },
      {
        "type": "p",
        "text": "Khối **«🎧 CSKH — Đánh giá chất lượng chăm sóc»** trong thẻ lead là nơi Admin CSKH gọi lại khách để chấm chất lượng tư vấn của team KD (ví dụ: khách khen tư vấn nhiệt tình, hay phàn nàn 3 ngày chưa nhận báo giá)."
      },
      {
        "type": "warn",
        "text": "Chỉ Admin CSKH và Quản trị viên ghi được đánh giá — sale và trưởng nhóm chỉ đọc (vì đây là đánh giá VỀ mình). Mục đã lưu không sửa/xóa được, hệ thống tự đóng dấu ngày giờ và tên người ghi."
      }
    ]
  },
  {
    "id": "du-an",
    "icon": "kanban",
    "title": "Dự án «Dự án» — theo dõi công trình từ Thiết kế đến Bàn giao",
    "blocks": [
      {
        "type": "p",
        "text": "Mọi vai trò chuẩn đều thấy mục **Dự án** trong menu. Khi tạo dự án mới, hệ thống **tự sinh mã** và **gửi thông báo cho trưởng phòng** các bộ phận chưa có người phụ trách để họ vào gắn PIC — mỗi trưởng phòng chỉ thấy ô PIC của **bộ phận mình** (Ban Giám Đốc thấy cả 4 ô). Ở **cả 2 chế độ Danh sách và Kanban** (Kanban siết từ 22/10), bạn chỉ thấy các dự án **liên quan đến mình**: dự án bạn được phân công phụ trách (PIC) hoặc được giao ít nhất 1 đầu việc. Trưởng phòng thấy thêm mọi dự án có người phòng mình phụ trách. Giám đốc, Ban Quản Trị và Kế toán thấy toàn bộ. Riêng dự án **chưa phân công ai** thì mọi người đều thấy. **Sửa một đầu việc** (đổi trạng thái, giao người, sửa nội dung) chỉ dành cho người được giao, PIC dự án, trưởng phòng hoặc vai có quyền «Sửa công việc»; người được giao đổi được trạng thái nhưng không tự dời hạn chốt."
      },
      {
        "type": "h3",
        "text": "2 chế độ xem — chuyển bằng 2 nút to ngay đầu trang"
      },
      {
        "type": "list",
        "items": [
          "**📊 Kanban** (mặc định): dự án xếp thành cột theo giai đoạn — Thiết kế → Báo giá → Thu mua → Thi công → Nghiệm thu, cuộn tiếp còn 2 cột Tạm dừng và Hoàn thành. Thẻ nào **quá hạn hay sát hạn tự nổi lên đầu cột**, kèm nhãn 🔴 «Quá hạn X ngày» hoặc 🟠 «Còn X ngày».",
          "**📋 Danh sách**: xem dạng thẻ lưới, có nút lọc theo trạng thái (Đang thực hiện / Tạm dừng / Hoàn thành / Hủy) và theo **Quý** (Q1–Q4).",
          "Cả 2 chế độ đều có ô **«Tìm dự án...»** và ô tick **«Công việc của tôi»** — tick vào để chỉ hiện dự án bạn phụ trách.",
          "Trên mỗi thẻ có **thanh khối màu theo giai đoạn** (6 khối, khối cuối là Tạm dừng): xanh lá = giai đoạn xong, vàng = đang làm, xám = chưa tới. Nhìn 1 giây biết dự án đang ở đâu."
        ]
      },
      {
        "type": "h3",
        "text": "Mở chi tiết dự án và đổi giai đoạn"
      },
      {
        "type": "steps",
        "items": [
          "Bấm vào thẻ dự án → hiện cửa sổ chi tiết: tiến độ, tổng giá trị, đã chi, **Phân công bộ phận** (PM/Giám sát – Thiết kế – Báo giá/Thu mua – Kinh doanh), thông tin khách, ngân sách và cảnh báo khi chi vượt.",
          "Đổi giai đoạn bằng ô **«Giai đoạn:»** ở góc trên cửa sổ. Chọn **«Tạm dừng»** thì hệ thống hỏi lý do (VD: đang xin phép, khách đi du lịch...) — nhập rồi bấm **«Xác nhận tạm dừng»**.",
          "Kéo xuống mục **«Đầu việc»** — có thể xem gộp **«Theo giai đoạn»** hoặc **«Theo phòng ban»** (mỗi phòng thấy ngay phần việc của mình; phòng chưa tới lượt hiện mờ kèm chữ «Chờ giai đoạn trước»)."
        ]
      },
      {
        "type": "h3",
        "text": "Làm việc với đầu việc"
      },
      {
        "type": "list",
        "items": [
          "**Đổi trạng thái** ngay trên dòng đầu việc bằng ô nhỏ bên phải: Chưa bắt đầu → Đang làm → Xong.",
          "Ô xanh **«👤 Đảm nhận»** để chọn người làm — bấm vào và chọn tên. Danh sách **chỉ hiện người đúng phòng ban** của việc đó (việc thiết kế chỉ hiện người phòng Thiết kế...). Không thấy tên mình? Báo quản trị kiểm tra lại phòng ban trong mục Tài khoản.",
          "**Một đầu việc giao được nhiều người**, tất cả ngang vai (không có chính/phụ): gắn người thứ nhất xong, ô đó đổi thành **«👤 Thêm»** để chọn tiếp người thứ hai, thứ ba. Mỗi người được gắn đều nhận thông báo riêng và đều thấy đầu việc này trong việc của mình.",
          "Muốn **gỡ người** ra khỏi việc: bấm tên đầu việc để mở chi tiết → khối **«👤 Người đảm nhận»** → bấm dấu ✕ cạnh tên.",
          "Nút **«+ Thêm công việc»**: chọn tiêu đề, giai đoạn, phòng ban và người phụ trách.",
          "Nút **«📦 Yêu cầu vật tư»**: chọn vật tư trong kho, số lượng, ghi chú rồi bấm «Gửi yêu cầu»."
        ]
      },
      {
        "type": "h3",
        "text": "Hạn chốt, chuẩn SLA và chuyện bị nhắc"
      },
      {
        "type": "list",
        "items": [
          "**Hạn chốt** là hạn đã thống nhất với nhau cho đầu việc đó — sửa trong chi tiết việc, ô **«Hạn chốt»**. Quá ngày này là việc **quá hạn**.",
          "**Chuẩn SLA** là số ngày tiêu chuẩn của công ty cho từng loại đầu việc (ví dụ 2D Concept 3 ngày, 3D Render 5 ngày). Đồng hồ SLA **chỉ bắt đầu chạy** khi việc có người nhận hoặc được chuyển sang «Đang làm» — không tính từ lúc mở dự án.",
          "Trên dòng đầu việc có nhãn cho biết tình trạng: **🟠 Còn N ngày** (sắp tới hạn), **🔴 Quá hạn**, **⚠ Vượt SLA**.",
          "Việc quá hạn hoặc vượt SLA: hệ thống **nhắc từng người đang làm việc đó** (trong app và Telegram nếu bạn đã liên kết). Trễ lâu quá — mặc định quá 2 ngày — thì nhắc tiếp lên **trưởng phòng** phụ trách và **chủ nhiệm dự án**.",
          "Một việc trễ chỉ nhận **một** lời nhắc: đã báo quá hạn chốt thì không báo thêm vượt SLA nữa."
        ]
      },
      {
        "type": "tip",
        "text": "Hạn chốt lùi lại là chuyện bình thường khi khách đổi ý — nhưng **sửa ô «Hạn chốt» cho đúng thực tế** thì hệ thống mới thôi nhắc. Để nguyên hạn cũ rồi mặc nhắc thì trưởng phòng và chủ nhiệm dự án sẽ nhận cảnh báo oan."
      },
      {
        "type": "h3",
        "text": "Ghi chú và gửi ảnh công trình"
      },
      {
        "type": "steps",
        "items": [
          "Bấm vào tên đầu việc → mở cửa sổ chi tiết việc.",
          "Gõ nội dung vào ô **«Thêm cập nhật ghi chú & hình ảnh»**.",
          "Bấm **«📷 Đính kèm ảnh»** để chọn ảnh (chọn được nhiều ảnh). App tự nén ảnh cho gọn nên ảnh chụp điện thoại cỡ nào cũng gửi được. Ảnh hiện trước ở dạng thu nhỏ, bấm dấu × để bỏ ảnh chọn nhầm.",
          "Bấm **«Đăng cập nhật»** — ảnh được lưu vào **Kho ảnh công trình**, ghi chú và ảnh vào mục «Lịch sử cập nhật công việc», cả đội cùng thấy. Nếu mạng yếu chỉ gửi được một phần, cứ bấm «Đăng cập nhật» lần nữa để gửi nốt ảnh còn lại."
        ]
      },
      {
        "type": "h3",
        "text": "Khối «📷 Ảnh dự án» — kho ảnh của từng công trình"
      },
      {
        "type": "list",
        "items": [
          "Trong chi tiết dự án có khối **«📷 Ảnh dự án»**: toàn bộ ảnh của dự án, gửi từ web hay từ Telegram đều về đây. Bấm ảnh để phóng to, bấm **«＋ Thêm ảnh»** để đăng thêm.",
          "Mỗi ảnh có công tắc **«👁 Khách thấy / 🙈 Nội bộ»**. Ảnh tiến độ mặc định **khách thấy** trên trang tiến độ của khách; ảnh sự cố, vật tư mặc định **nội bộ**.",
          "Ảnh chưa đẹp, lộ đồ đạc riêng của chủ nhà, hay chụp lỗi thi công → bấm chuyển sang **«🙈 Nội bộ»** trước khi khách mở link."
        ]
      },
      {
        "type": "tip",
        "text": "Tài liệu (PDF, bản vẽ DWG, file SKP, Excel...) tải thẳng lên: mở đầu việc → **«📤 Tải file lên»** trong khối **«📁 File kết quả giai đoạn»** (tối đa 50MB). File thành file kết quả của đầu việc, bot tự gửi một bản vào topic dự án ở nhóm Telegram. File lớn hơn 50MB thì dán link Drive vào ô bên dưới rồi bấm **«Lưu link»**. **Không tải hợp đồng, chứng từ tài chính** ở đây vì cả nhóm công trình xem được."
      },
      {
        "type": "p",
        "text": "**Tạo / sửa dự án**: bấm nút vàng **«+ Dự án mới»** góc phải (trên điện thoại là nút tròn nổi góc dưới phải), hoặc nút **«Chỉnh sửa»** trong chi tiết dự án. Nhớ điền đủ 4 ô **«Phân công phụ trách (PIC)»** — PM/Giám sát, Thiết kế, Báo giá–Thu mua, Kinh doanh — để hệ thống giới hạn đúng phạm vi xem và báo đúng người (riêng ô tick «Công việc của tôi» hiện mới lọc theo PIC PM/Giám sát, Thiết kế và Kinh doanh — PIC Báo giá–Thu mua chưa được tính). Bắt buộc: tên dự án và tên khách hàng. Nên điền thêm **Ngày dự kiến hoàn thành** (để hệ thống nhắc hạn) và **Ngân sách kế hoạch** (để cảnh báo khi chi vượt)."
      }
    ]
  },
  {
    "id": "khach-hang",
    "icon": "user",
    "title": "Khách hàng «Khách hàng» — sổ danh bạ khách đã ký",
    "blocks": [
      {
        "type": "p",
        "text": "Trang này là **hồ sơ khách hàng chính thức** — khách tự động xuất hiện ở đây khi lead ký hợp đồng (khách đang tư vấn thì nằm bên mục «Quy trình»). Ai cũng xem được; còn **thêm/sửa** hồ sơ thì chỉ một số vai trò có nút."
      },
      {
        "type": "list",
        "items": [
          "Ô tìm kiếm: gõ **tên, SĐT hoặc email** là ra ngay.",
          "Ô lọc bên cạnh: **Tất cả loại KH / Cá nhân / Doanh nghiệp**.",
          "Bảng danh sách hiện: Tên, Loại, SĐT, Email, Địa chỉ. Trên điện thoại hiển thị dạng thẻ gọn.",
          "Bấm vào 1 khách → cửa sổ chi tiết: SĐT, email, địa chỉ, mã số thuế, ghi chú nội bộ, và **danh sách dự án** của khách kèm % tiến độ từng dự án."
        ]
      },
      {
        "type": "h3",
        "text": "Thêm khách hàng mới"
      },
      {
        "type": "steps",
        "items": [
          "Bấm nút vàng **«+ Thêm khách hàng»** góc phải.",
          "Điền **Tên khách hàng** và **SĐT** (2 ô bắt buộc). Khách công ty thì chọn loại «Doanh nghiệp» và điền thêm tên công ty, mã số thuế.",
          "Bấm **«Tạo khách hàng»**. Muốn sửa sau này: bấm nút **«Sửa»** ở cuối dòng."
        ]
      },
      {
        "type": "tip",
        "text": "Ô **«Ghi chú nội bộ»** chỉ người trong công ty thấy — ghi thói quen, sở thích, lưu ý khi làm việc với khách vào đây để đồng nghiệp tiếp quản không bị bỡ ngỡ."
      },
      {
        "type": "p",
        "text": "Trong cửa sổ chi tiết khách còn có phần **link portal** (cổng tra cứu cho khách tự xem tiến độ) — xem hướng dẫn ở mục «Cổng tra cứu cho khách» ngay dưới."
      }
    ]
  },
  {
    "id": "cong-khach",
    "icon": "send",
    "title": "Cổng tra cứu cho khách — khách tự xem tiến độ, khỏi hỏi đi hỏi lại",
    "blocks": [
      {
        "type": "p",
        "text": "Mỗi khách hàng có thể được cấp **1 đường link riêng** dạng `crm.jamahome.vn/portal/...`. Khách mở link trên điện thoại là xem được tiến độ dự án của mình — **không cần tài khoản, không cần mật khẩu**. Ai tạo được link: chỉ **Giám đốc** và **Trưởng phòng** (người khác bấm sẽ báo lỗi không đủ quyền)."
      },
      {
        "type": "h3",
        "text": "Tạo và gửi link cho khách"
      },
      {
        "type": "steps",
        "items": [
          "Vào menu **«Khách hàng»** → bấm vào tên khách → cửa sổ chi tiết mở ra.",
          "Ở phần **«📋 Dự án»**, bấm nút **«Tạo link portal»** (nếu đã tạo trước đó thì link hiện sẵn).",
          "Bấm **«Copy»** rồi gửi link cho khách qua Zalo/Telegram/tin nhắn."
        ]
      },
      {
        "type": "h3",
        "text": "Khách xem được những gì?"
      },
      {
        "type": "list",
        "items": [
          "Danh sách **dự án của chính khách đó** (không thấy dự án của khách khác), kèm % tiến độ và giai đoạn hiện tại.",
          "Bấm vào từng dự án: danh sách **đầu việc** với dấu ✅ xong / 🔄 đang làm / ⏳ chưa bắt đầu.",
          "**«📸 Nhật ký công trình»**: ảnh công trình xếp theo ngày, kèm tên người cập nhật. Khách chỉ thấy ảnh đang bật **«👁 Khách thấy»** (xem khối «📷 Ảnh dự án» trong chi tiết dự án).",
          "**«📝 Tiến độ gần đây»**: các cập nhật tiến độ mới nhất đội thi công đăng trong đầu việc — nên viết ghi chú tử tế, khách đọc được đấy! Sự cố, yêu cầu vật tư và check-in của đội **không** hiện cho khách.",
          "**«✍️ Nghiệm thu giai đoạn»**: khách bấm nút **«Xác nhận nghiệm thu»** khi hài lòng với giai đoạn hiện tại, ghi chú thêm nếu muốn."
        ]
      },
      {
        "type": "p",
        "text": "Khi khách bấm xác nhận nghiệm thu, hệ thống **lưu mốc thời gian làm bằng chứng** (mỗi giai đoạn chỉ xác nhận 1 lần, không ghi đè được) và **báo ngay qua Telegram** cho Sale phụ trách và PM của dự án. Trên link cũng có sẵn số hotline JAMA HOME 070.56.23456 để khách gọi khi cần."
      },
      {
        "type": "warn",
        "text": "Đường link chính là «chìa khóa» — **ai cầm link đều xem được** thông tin dự án của khách đó. Chỉ gửi cho đúng chủ nhà, đừng đăng link lên nhóm chung hay mạng xã hội."
      },
      {
        "type": "tip",
        "text": "Muốn tập dượt hoặc demo cho khách xem trước? Mở `crm.jamahome.vn/portal/demo` — đây là trang mẫu với dữ liệu giả «Chị Mai», bấm thoải mái không ảnh hưởng gì."
      }
    ]
  },
  {
    "id": "tro-ly-zalo",
    "icon": "message",
    "title": "«Trợ lý Zalo» — nắm việc trong các nhóm Zalo mà không phải đọc hết",
    "roles": [
      "Ban giám đốc",
      "Trưởng phòng"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Một tài khoản Zalo riêng của công ty được thêm vào các nhóm Zalo. Trợ lý **chỉ đọc, không bao giờ gửi tin vào Zalo**. Nó lọc ra việc cần xử lý và báo cho đúng người. Menu **«Trợ lý Zalo»** chỉ hiện với **Ban giám đốc, Kế toán và Trưởng phòng**."
      },
      {
        "type": "table",
        "header": ["Ai", "Thấy gì"],
        "rows": [
          ["Ban giám đốc / Admin", "Toàn bộ nhóm đang nghe, lọc được theo phòng"],
          ["Trưởng phòng", "Chỉ các nhóm đã gán cho phòng mình"]
        ]
      },
      {
        "type": "list",
        "items": [
          "**Báo gấp qua Telegram:** khách nhắn trong nhóm mà quá **2 giờ** (đổi được ở Cài đặt) chưa ai trong công ty trả lời → bot nhắn riêng Trưởng phòng của nhóm đó và Ban giám đốc. Mỗi lần khách chờ chỉ báo một lần.",
          "**Tóm tắt cuối ngày (~17h):** mỗi nhóm có tin trong ngày được tóm tắt vài dòng. Trưởng phòng nhận phần của phòng mình, Ban giám đốc nhận cả công ty, qua Telegram chat riêng.",
          "**Trang «Trợ lý Zalo»:** 4 ô đếm (Khách chờ trả lời, Có nguy cơ mất khách, Khách hỏi giá, Khách mới tiềm năng), bấm ô để lọc. Xử lý xong bấm **«✓ Đã xử lý»**, không cần thì **«Bỏ qua»**. Tab **«Tóm tắt cuối ngày»** xem lại tóm tắt các ngày trước."
        ]
      },
      {
        "type": "steps",
        "items": [
          "Admin vào **Cài đặt → Zalo — Trợ lý lắng nghe**, bấm đăng nhập rồi quét mã QR bằng **tài khoản Zalo riêng của công ty** (không dùng Zalo cá nhân).",
          "Danh sách nhóm hiện ra, nhóm mới luôn ở trạng thái **TẮT**. Bật những nhóm muốn nghe, chọn loại nhóm (nội bộ / khách) và **chọn phòng** cho từng nhóm để báo đúng Trưởng phòng.",
          "Chỉnh giờ gửi tóm tắt và số giờ coi là «khách chờ» ở **Cài đặt → Tự động hóa**."
        ]
      },
      {
        "type": "warn",
        "text": "Sau khi quét QR, **đừng mở Zalo Web/Zalo PC bằng tài khoản trợ lý**: Zalo chỉ cho một phiên web, mở chỗ khác là trợ lý bị đăng xuất. Tin nhắn gốc tự xoá sau **7 ngày**, chỉ giữ tín hiệu và tóm tắt. Trợ lý dùng để chăm khách tốt hơn, **không dùng để chấm điểm hay kỷ luật nhân viên**."
      }
    ]
  },
  {
    "id": "hop-dong",
    "icon": "wallet",
    "title": "Hợp đồng «Hợp đồng»",
    "blocks": [
      {
        "type": "p",
        "text": "Mọi vai trò đều xem được trang này. Vào menu **Hợp đồng**, bạn thấy 4 ô tổng: Tổng HĐ, Đã ký, Tổng giá trị, Nháp — bên dưới là bảng danh sách hợp đồng. Mỗi hợp đồng có trạng thái riêng: **Nháp**, **Duyệt**, **Đã gửi**, **Ký HĐ**, **Hoàn thành**, **Hủy**."
      },
      {
        "type": "h3",
        "text": "Tạo và sửa hợp đồng"
      },
      {
        "type": "steps",
        "items": [
          "Bấm nút **+ Tạo hợp đồng mới** ở góc phải trên. Chỉ người có quyền **«Tạo hợp đồng»** mới tạo/sửa được (từ 22/10 vai trò tùy chỉnh phải được quản trị tick ô này trong Phân quyền).",
          "Nhập **Tiêu đề hợp đồng** (bắt buộc), chọn Dự án nếu có.",
          "Điền Giá trị hợp đồng, Số ngày thi công, Ngày bắt đầu, Ngày ký, Ghi chú.",
          "Bấm **Tạo hợp đồng** để lưu. Muốn sửa lại, bấm nút **Sửa** màu xanh ở cuối dòng hợp đồng đó."
        ]
      },
      {
        "type": "tip",
        "text": "Ô tiền nhập theo **nghìn đồng**: gõ `500000` nghĩa là 500 triệu. Ngay dưới ô có chữ nhắc để bạn kiểm tra lại."
      },
      {
        "type": "h3",
        "text": "Mẫu hợp đồng, phụ lục, biên bản (tab «Mẫu & biên bản»)"
      },
      {
        "type": "steps",
        "items": [
          "Trong trang Hợp đồng bấm tab **«Mẫu & biên bản»**. Mẫu chia nhóm: **Hợp đồng**, **Phụ lục**, **Biên bản**, **Thanh toán**; nhãn **Thiết kế / Thi công** giúp chọn đúng loại.",
          "Bấm **Tải về** để lấy bản mới nhất rồi điền thông tin khách. Luôn tải ở đây, đừng dùng bản cũ lưu trong máy hay Zalo.",
          "**BGĐ và Kế toán**: bấm **Tải mẫu lên**, chọn nhiều tệp Word/Excel/PDF một lúc (tối đa 20 tệp, mỗi tệp 40 MB). App tự xếp nhóm theo tên tệp; sai nhóm thì bấm **Sửa tên/nhóm**.",
          "Sửa mẫu xong, tải lên lại **đúng tên tệp cũ** → thay bản cũ và tăng số «bản». Mẫu không dùng nữa bấm **Ẩn** (bấm «Hiện mẫu đã ẩn» để xem lại)."
        ]
      },
      {
        "type": "tip",
        "text": "Mẫu chỉ người có quyền xem Hợp đồng mới thấy và tải được — không gửi ra ngoài công ty."
      },
      {
        "type": "h3",
        "text": "Theo dõi đợt thanh toán và xác nhận đã thu tiền"
      },
      {
        "type": "steps",
        "items": [
          "Bấm vào một dòng hợp đồng để mở chi tiết: có thanh **Tiến độ thi công** (còn bao nhiêu ngày) và danh sách **Tiến độ thanh toán** theo từng đợt.",
          "Bấm vào một đợt để xem chi tiết: tỷ lệ %, số tiền, trạng thái, ngày thanh toán, ảnh sao kê (nếu có).",
          "Khi khách đã chuyển tiền một đợt: bấm nút **Xác nhận TT** màu xanh lá ở đợt đó.",
          "Tải ảnh sao kê ngân hàng lên (PNG/JPG tối đa 5MB) hoặc dán link ảnh — bước này không bắt buộc nhưng nên làm.",
          "Tích ô **«Tôi xác nhận đợt thanh toán này đã được thanh toán»** rồi bấm **Xác nhận đã thanh toán**."
        ]
      },
      {
        "type": "warn",
        "text": "Nút **Xác nhận TT** chỉ hiện với **Kế toán (Trưởng phòng Tài chính) và Giám đốc** (chốt 22/10 — Trưởng nhóm Kinh doanh không còn bấm được). Vai trò khác không thấy nút này — hệ thống cũng chặn ở máy chủ, có cố cũng không được. Xác nhận rồi thì đợt đó chuyển sang «Đã thanh toán», hãy chắc chắn tiền đã về tài khoản trước khi bấm."
      }
    ]
  },
  {
    "id": "bao-gia",
    "icon": "send",
    "title": "Báo giá «Báo giá»",
    "roles": [
      "Sale",
      "Trưởng phòng",
      "Giám sát",
      "Kế toán",
      "Giám đốc"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "**Ai thấy mục này:** mọi vai trò trừ Ban Quản Trị (Kế toán chỉ xem, không tạo). Trang **Báo giá** liệt kê báo giá dạng thẻ, có 3 tab lọc phía trên: **Tất cả / Thiết kế / Thi công**. Mỗi thẻ hiện mã báo giá, trạng thái (Nháp, Duyệt, Đã gửi, Từ chối, Hết hạn), tổng tiền và hạn hiệu lực."
      },
      {
        "type": "h3",
        "text": "Tạo báo giá mới"
      },
      {
        "type": "steps",
        "items": [
          "Bấm **+ Tạo báo giá mới** ở góc phải trên.",
          "Nhập **Tiêu đề** (bắt buộc), chọn Loại báo giá (Thiết kế / Thi công) và Dự án nếu có.",
          "Ở phần **Mục báo giá**, bấm **+ Thêm hạng mục** cho từng dòng: tên hạng mục, đơn vị (gói / m2 / bộ), số lượng, đơn giá. Thành tiền tự tính.",
          "Điền Thuế, Hiệu lực đến, Ghi chú nếu cần, rồi bấm **Tạo mới**."
        ]
      },
      {
        "type": "tip",
        "text": "**Mã báo giá không cần nhập** — hệ thống tự sinh dạng `BG-năm-số` (ví dụ BG-2026-1234). Ô **Tổng tiền** tự cộng từ các hạng mục, nhưng bạn vẫn gõ đè tay được. Xóa hết hạng mục thì báo giá vẫn lưu bình thường."
      },
      {
        "type": "h3",
        "text": "Duyệt báo giá"
      },
      {
        "type": "p",
        "text": "Bấm vào thẻ báo giá đang ở trạng thái **Nháp** để mở chi tiết. Nếu bạn có quyền duyệt, sẽ thấy nút vàng **Duyệt báo giá** — bấm là báo giá chuyển sang «Duyệt». Muốn sửa nội dung trước khi duyệt, bấm **Chỉnh sửa**."
      },
      {
        "type": "warn",
        "text": "Nút **Duyệt báo giá** chỉ dành cho **Giám đốc và Trưởng phòng Báo giá** (chốt 22/10). Sale soạn và sửa được báo giá nhưng **không tự duyệt bản của mình** — máy chủ sẽ từ chối."
      }
    ]
  },
  {
    "id": "du-toan",
    "icon": "zap",
    "title": "Trang «Báo giá nội thất trong 30 giây» — dành cho khách",
    "blocks": [
      {
        "type": "p",
        "text": "Đây là trang **công khai cho khách hàng**, không cần đăng nhập, không nằm trong menu: `crm.jamahome.vn/bao-gia`. Đừng nhầm với mục «Báo giá tức thì» trong menu (công cụ nội bộ) hay mục «Báo giá» ở trên."
      },
      {
        "type": "p",
        "text": "Khách tự nhập: Họ tên, Số điện thoại, Diện tích (m²), loại nhà (Căn hộ / Nhà phố / Biệt thự / Văn phòng / Shophouse), số phòng ngủ, ngân sách dự kiến — rồi bấm **⚡ Nhận báo giá ngay**. Màn hình hiện ngay **khoảng giá 3 phương án** (kèm nhãn «Phù hợp với bạn»), chỉ hiện khoảng giá chứ không lộ đơn giá chi tiết của công ty."
      },
      {
        "type": "tip",
        "text": "**Cách dùng cho nhân viên Sale:** gửi link `crm.jamahome.vn/bao-gia` cho khách qua Zalo/Facebook. Khách điền xong, hệ thống **tự tạo khách hàng tiềm năng nóng** kèm số điện thoại — bạn vào mục «Quy trình» để nhận và gọi tư vấn trong 24h."
      }
    ]
  },
  {
    "id": "vat-tu",
    "icon": "package",
    "title": "Vật tư — khách chọn mẫu, Thu mua hỏi giá, chốt giá bán «Vật tư»",
    "roles": ["Thiết kế", "Kinh doanh", "Thu mua", "Giám đốc"],
    "blocks": [
      { "type": "p", "text": "Menu **Kho hàng → Vật tư** (từ 25/10/2026). JAMA không có bảng giá vật tư chuẩn: khách chọn mẫu → Thu mua hỏi 2–3 nhà cung cấp → chốt giá. App gói đúng luồng đó thành **phiếu vật tư theo dự án**, từng phòng một." },
      { "type": "h3", "text": "Quy tắc giá — ai thấy gì" },
      { "type": "list", "items": [
        "**Giá bán cho khách = giá vốn + % lãi theo nhóm** (gạch 30x30, 60x60… mỗi nhóm một %; Giám đốc cài ở tab «% lãi theo nhóm»). Mẫu nào có **giá bán cố định** thì áp giá nào **cao hơn**.",
        "**Chỉ Thu mua chốt giá.** Không ai gõ giá bán tay — tránh mỗi dự án một kiểu.",
        "**Giá vốn, tên NCC, lãi** chỉ Giám đốc, Thu mua và Trưởng phòng thấy. Kinh doanh, Thiết kế chỉ thấy **giá bán** — máy chủ không gửi cột giá vốn xuống, không phải chỉ ẩn trên màn hình.",
        "Khách không bao giờ thấy giá vốn hay NCC (portal cho khách duyệt mẫu làm ở đợt sau)."
      ] },
      { "type": "h3", "text": "Thiết kế / Kinh doanh — ngồi cùng khách" },
      { "type": "steps", "items": [
        "Mở dự án → bấm **«Phiếu vật tư của dự án»** (hoặc menu Vật tư → tab Phiếu dự án → gõ mã/tên dự án vào ô tìm; dự án có hoạt động 7 ngày gần nhất nằm sẵn ở mục **Gần đây**).",
        "Bấm **«Khách chọn mẫu»**: chọn phòng (Phòng khách, Bếp, WC…), hạng mục (sàn, tường…), gõ mã hoặc hãng để chọn trong danh mục có ảnh; nhập số lượng. Mã chưa có trong danh mục thì gõ tự do.",
        "Dòng mới ở trạng thái **Khách chọn** — Thu mua tự thấy ở bảng «Cần hỏi giá», không cần nhắn.",
        "Khi khách gật đầu (ở quán, qua Zalo…), bấm **«Khách đã đồng ý»** và ghi chú khách nói gì, qua kênh nào.",
        "Nếu Thu mua báo **Hết hàng / đề xuất thay**, dòng hiện đỏ kèm mã thay thế: hỏi lại khách, bấm «Khách đã đồng ý» → mã thay thành mã chính, Thu mua hỏi giá tiếp."
      ] },
      { "type": "h3", "text": "Thu mua — thêm / sửa mẫu trong Danh mục" },
      { "type": "steps", "items": [
        "Tab **Danh mục** → **«Thêm mẫu»** (hoặc «Sửa» trên thẻ mẫu). Chọn **Nhóm** trong danh sách (kích thước 30x30, 60x60…) hoặc «+ Nhóm mới…».",
        "**Ảnh mẫu**: dán link ảnh là thấy ngay; hoặc bấm **«Tải ảnh lên»** chụp/chọn từ máy — app nén và lưu trong ERP, không cần link ngoài.",
        "Chưa có ảnh hay muốn xem giá thị trường: bấm **«Tìm trên Shopee»** — mở sẵn Shopee tìm theo hãng + mã. Thấy đúng sản phẩm thì chép link ảnh và dán **Link Shopee sản phẩm** vào form để lần sau so giá bằng nút «Mở Shopee». ERP không tự lấy dữ liệu từ Shopee (Shopee chặn máy đọc tự động).",
        "Bấm **Lưu**. Giá tham khảo (vốn) và NCC quen chỉ Thu mua / Giám đốc / Trưởng phòng thấy."
      ] },
      { "type": "h3", "text": "Thu mua — bảng «Cần hỏi giá»" },
      { "type": "steps", "items": [
        "Tab **Cần hỏi giá** gom mọi dòng chờ của tất cả dự án. Bấm một dòng để mở.",
        "Nhập từng báo giá NCC: tên NCC, giá vốn, còn hàng không, ngày giao. Báo giá **rẻ nhất tự lên đầu**.",
        "Bấm **«Chốt giá này»** → app tính giá bán theo % lãi nhóm (hoặc giá cố định nếu cao hơn), ghi «giá gần nhất» về mẫu để lần sau tham khảo, và báo cho Thiết kế / Kinh doanh / PM của dự án.",
        "Hết hàng: bấm **«Hết hàng / đề xuất thay»**, chọn mã thay và lý do → dòng chuyển sang chờ khách duyệt lại.",
        "Sau chốt: bấm **Đã đặt** → **Đã giao** theo tiến độ."
      ] },
      { "type": "h3", "text": "Danh mục mẫu" },
      { "type": "list", "items": [
        "Thu mua bấm **«Nhập Google Sheet»** dán link bảng mẫu của JAMA (mỗi tab = một nhóm kích thước): app đọc cột MÃ, THƯƠNG HIỆU, HÌNH ẢNH, TÍNH CHẤT, TÌNH TRẠNG, ĐƠN GIÁ, NCC. Nhập lại chỉ thêm mẫu mới, tick «Ghi đè» mới cập nhật mẫu cũ.",
        "Có thể thêm/sửa từng mẫu tay: mã, hãng, nhóm, ảnh, giá tham khảo, giá bán cố định, tắt «Đang dùng» khi ngừng bán."
      ] },
      { "type": "tip", "text": "Dòng đã chốt giá chỉ Giám đốc xoá được. Thu mua không cần được gắn vào dự án vẫn xem và chốt mọi phiếu." }
    ]
  },
  {
    "id": "kho-ncc",
    "icon": "building",
    "title": "Kho vật tư & Nhà cung cấp «Kho vật tư» «Nhà cung cấp»",
    "roles": [
      "Giám đốc",
      "Kế toán",
      "Giám sát"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "**Ai thấy 2 mục này:** Giám đốc, Kế toán và Giám sát (phụ trách mua hàng). Các vai trò khác không thấy trong menu."
      },
      {
        "type": "h3",
        "text": "Kho vật tư — xem tồn và nhập hàng loạt"
      },
      {
        "type": "p",
        "text": "Trang **Kho vật tư** có 4 ô tổng (Tổng mặt hàng, Giá trị tồn kho, Cảnh báo hết hàng, Danh mục) và bảng vật tư: mã, tên, danh mục, tồn kho, đơn giá, giá trị, nhà cung cấp. Vật tư nào **tồn kho xuống bằng hoặc dưới mức tối thiểu** sẽ đỏ lên kèm khung cảnh báo «Vật tư sắp hết» ở đầu trang. Dùng ô **Tìm vật tư...** và các nút lọc theo Danh mục / NCC để tìm nhanh."
      },
      {
        "type": "steps",
        "items": [
          "Bấm nút **📥 Nhập từ file** ở góc phải trên để đưa cả bảng giá vật tư vào một lần.",
          "Chuẩn bị file CSV: trong Excel chọn **Lưu dưới dạng → CSV UTF-8**. Chưa rõ định dạng thì bấm **Tải file mẫu** ngay trong cửa sổ.",
          "Cột bắt buộc duy nhất là **Tên vật tư**; các cột Mã, Danh mục, Đơn vị, Đơn giá, NCC, Tồn kho, Tồn tối thiểu là tùy chọn.",
          "Chọn file, kiểm tra bảng **xem trước** — dòng lỗi sẽ được báo đỏ — rồi bấm **Nhập N dòng**."
        ]
      },
      {
        "type": "tip",
        "text": "Khi nhập file: vật tư **trùng Mã hoặc Tên** với hàng đã có sẽ được **cập nhật giá và NCC** (coi như báo giá mới); chưa có thì tạo mới. Không sợ nhập trùng thành 2 dòng."
      },
      {
        "type": "h3",
        "text": "Nhà cung cấp — tra giá và so sánh giá"
      },
      {
        "type": "steps",
        "items": [
          "Vào menu **Nhà cung cấp**: danh sách NCC nằm bên trái, bấm vào một NCC để xem thông tin liên hệ và **Bảng giá** của họ bên phải.",
          "Muốn biết vật tư nào mua ở đâu rẻ nhất: gõ tên vật tư vào ô **So sánh giá** (ví dụ: Gỗ sồi) rồi bấm nút **So sánh giá** — bảng so sánh giá giữa các NCC hiện ra.",
          "Thêm NCC mới: bấm **+ Thêm nhà cung cấp**, điền Tên NCC (bắt buộc), người liên hệ, điện thoại, loại hàng rồi bấm **Thêm**.",
          "Ghi báo giá NCC vừa gửi: chọn NCC đó, bấm **+ Thêm báo giá**, điền tên vật tư, đơn giá, số lượng tối thiểu, số ngày giao hàng."
        ]
      },
      {
        "type": "warn",
        "text": "Nút **+ Thêm nhà cung cấp** và **+ Thêm báo giá** chỉ hiện với **Giám đốc và Giám sát**. Kế toán vào được trang để tra giá, so sánh giá nhưng không thêm/sửa được."
      }
    ]
  },
  {
    "id": "ke-toan",
    "icon": "wallet",
    "title": "Kế toán — thu chi, hoa hồng, bảng lương «Kế toán»",
    "roles": [
      "Giám đốc",
      "Trưởng phòng",
      "Sale",
      "Kế toán"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "**Ai thấy mục này:** Giám đốc, Trưởng phòng, Nhân viên Sale, Kế toán. (Ban Quản Trị và Giám sát không thấy menu này.) Bấm **Kế toán** ở menu trái để mở. Trang có tối đa 4 tab ngang phía trên: **Tổng quan**, **Giao dịch**, **Hoa hồng**, **Bảng lương** — bạn thấy tab nào là tùy quyền của mình."
      },
      {
        "type": "table",
        "header": [
          "Tab",
          "Ai thấy",
          "Dùng để làm gì"
        ],
        "rows": [
          [
            "Tổng quan",
            "Giám đốc, Kế toán",
            "Xem 3 thẻ Tổng thu / Tổng chi / Lợi nhuận, lọc theo Tất cả – Tháng này – Quý này – Năm nay"
          ],
          [
            "Giao dịch",
            "Giám đốc, Kế toán",
            "Sổ thu chi chi tiết: tìm kiếm, lọc Thu/Chi, lọc danh mục, lọc theo ngày"
          ],
          [
            "Hoa hồng",
            "Cả 4 vai trò trên",
            "Xem hoa hồng theo từng mốc dự án; duyệt và đánh dấu chi trả"
          ],
          [
            "Bảng lương",
            "Giám đốc, Kế toán",
            "Xem lương cơ bản, hoa hồng, thưởng, khấu trừ, thực lĩnh từng người"
          ]
        ]
      },
      {
        "type": "p",
        "text": "**Về hoa hồng:** nếu bạn là Sale hoặc Trưởng phòng, tab Hoa hồng chỉ hiện hoa hồng **của chính bạn** — chỉ Giám đốc và Kế toán xem được hoa hồng của người khác. Mỗi khoản có 3 trạng thái: **Chờ duyệt** (vàng) → **Đã duyệt** (xanh dương) → **Đã trả** (xanh lá)."
      },
      {
        "type": "p",
        "text": "**Hoa hồng tự tính theo JD (mới 24/10):** mỗi lần kế toán xác nhận khách trả một đợt, hệ thống tự sinh hoa hồng: Sale 1% số tiền đợt đó (dự án tích «Khách riêng của sale» thì 2%), TP Kinh doanh 0,2%; Thiết kế 0,5% nếu chủ trì / 0,3% nếu hỗ trợ, TP Thiết kế 0,2% — chỉ tính trên HĐ **thi công**. Thu mua 0,1% và TP Báo giá 0,2% giá trị HĐ, chia nửa lúc ký, nửa lúc nghiệm thu. Giám sát 0,5% và TP Giám sát 0,2% khi nghiệm thu. Dòng **Chờ mốc** (xám) là hoa hồng thiết kế chờ khách trả đợt 2 (hoặc chờ nghiệm thu với các đợt sau) — chưa duyệt được. Mỗi dòng ghi **Kỳ** = tháng lương sẽ trả."
      },
      {
        "type": "steps",
        "items": [
          "**Duyệt hoa hồng** (chỉ Giám đốc, Kế toán): ở dòng đang «Chờ duyệt», bấm nút **✓ Duyệt** bên phải.",
          "Khi đã chi tiền thật, bấm tiếp **💵 Đã chi trả** — trạng thái chuyển sang «Đã trả»."
        ]
      },
      {
        "type": "steps",
        "items": [
          "**Ghi một khoản thu/chi** (chỉ Giám đốc, Kế toán): vào tab **Giao dịch**, bấm nút xanh **+ Giao dịch mới**.",
          "Chọn **Thu nhập** hoặc **Chi phí**, chọn danh mục (HĐ Thiết kế, HĐ Thi công, Vật tư, Nhân công, Lương, Hoa hồng, Tiền mặt bằng, Điện nước, Khác).",
          "Nhập mô tả, số tiền (máy tự thêm dấu chấm ngăn cách), ngày. Có thể gắn thêm dự án hoặc nhân viên liên quan.",
          "Bấm **Tạo giao dịch**. Muốn sửa sau này, bấm nút **Sửa** ở cuối dòng; chỉ Giám đốc mới có nút **Xóa**."
        ]
      },
      {
        "type": "tip",
        "text": "Cần đưa sổ thu chi ra Excel? Ở tab Giao dịch, bấm **📥 Xuất bảng tính** — máy tải về file CSV theo đúng bộ lọc bạn đang chọn."
      },
      {
        "type": "warn",
        "text": "Lương chi tiết từng người (công, tăng ca, BHXH, thuế) KHÔNG nhập ở đây — hệ thống tự sinh từ **Chấm công → Chốt sổ**. Ô «Liên kết nhân viên» trong giao dịch chỉ dùng khi ghi một khoản chi lẻ cho một người cụ thể."
      }
    ]
  },
  {
    "id": "tai-chinh-pl",
    "icon": "building",
    "title": "Tài chính & P&L — chi phí công ty và lợi nhuận dự án",
    "roles": [
      "Giám đốc",
      "Kế toán",
      "Ban Quản Trị"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "**Ai thấy 2 mục này:** Giám đốc, Kế toán, Ban Quản Trị. Đây là hai trang «số liệu lớn» của công ty: **Tài chính** quản chi phí và cơ cấu lương thưởng, **P&L** cho biết từng dự án lãi hay lỗ."
      },
      {
        "type": "h3",
        "text": "Trang «Tài chính» — Lương & Hoa hồng"
      },
      {
        "type": "list",
        "items": [
          "**Bậc lương** — bảng lương gross và các mức BHXH/BHYT/BHTN theo bậc. Tab này **chỉ Giám đốc và Kế toán thấy**; Ban Quản Trị mở trang sẽ vào thẳng tab Chi phí cố định.",
          "**Chi phí cố định** — mặt bằng, điện nước… theo từng tháng. Đổi tháng bằng ô chọn tháng ở góc phải bảng.",
          "**Chi phí biến phí** — chi phí phát sinh theo tháng, có cột ghi rõ thuộc dự án nào.",
          "**Cơ cấu hoa hồng** — tỷ lệ % hoa hồng của từng phòng ban và ngày bắt đầu áp dụng."
        ]
      },
      {
        "type": "p",
        "text": "Ba thẻ trên đầu trang cộng sẵn cho bạn: Chi phí cố định, Chi phí biến phí và Tổng chi phí của tháng đang chọn."
      },
      {
        "type": "h3",
        "text": "Trang «P&L» — Tổng quan Lợi nhuận"
      },
      {
        "type": "list",
        "items": [
          "4 thẻ tổng: **Tổng Doanh thu**, **Tổng Chi phí**, **Lợi nhuận ròng**, **Biên lợi nhuận** — tự tính lại theo bộ lọc bạn chọn.",
          "Thanh **📅 Lọc theo**: Tất cả / Tháng / Quý / Năm / Tùy chọn (7–90 ngày qua hoặc tự chọn từ ngày → đến ngày). Bộ lọc tính theo **ngày bắt đầu** của dự án.",
          "Khung **Phải thu theo hợp đồng**: tổng tiền các đợt thanh toán khách chưa trả — bấm «Chi tiết ▼» để xem từng hợp đồng, từng đợt.",
          "Bảng dự án: bấm tiêu đề cột **Doanh thu / Lợi nhuận / Biên LN** để sắp xếp; **bấm vào một dòng** để mở bảng chi tiết (vật tư, nhân công, hoa hồng) và nút «Mở dự án đầy đủ →»."
        ]
      },
      {
        "type": "warn",
        "text": "Dự án chưa nhập ngày bắt đầu sẽ hiện **«—»** ở cột Ngày BĐ và luôn xuất hiện trong mọi kỳ lọc (hệ thống không tự bịa ngày). Muốn dự án lọc đúng tháng/quý/năm, hãy vào trang **Dự án** nhập ngày bắt đầu cho nó."
      },
      {
        "type": "tip",
        "text": "Màu ở cột Biên LN: xanh lá = biên từ 50% trở lên, vàng = 20–50%, đỏ = dưới 20% (dự án đang lãi mà biên mỏng vẫn đỏ). Liếc màu là biết dự án nào cần để mắt."
      }
    ]
  },
  {
    "id": "bao-cao-kpi",
    "icon": "kanban",
    "title": "Báo cáo & KPI — xem sức khỏe công ty và điểm của bạn",
    "blocks": [
      {
        "type": "h3",
        "text": "Trang «Báo cáo» — bức tranh chung"
      },
      {
        "type": "p",
        "text": "**Ai thấy mục Báo cáo:** hầu hết vai trò (riêng Thiết kế, Giám sát thi công và Thu mua không có mục này). Trang gồm 4 khối: **Doanh thu** (kèm biểu đồ theo danh mục thu), **Phễu quy trình** (tỷ lệ chuyển đổi từ khách quan tâm thành hợp đồng), **Hiệu suất đội nhóm** (mỗi đội bao nhiêu leads, ký bao nhiêu HĐ), và **KPI tổng hợp** (8 ô số nhanh: tổng leads, dự án đang chạy, giá trị pipeline, tuân thủ SLA…)."
      },
      {
        "type": "p",
        "text": "Khối Doanh thu chỉ hiện số với người có quyền xem P&L (Giám đốc, Kế toán, Ban Quản Trị). Nếu bạn thấy dòng «Bạn chưa được cấp quyền xem số liệu thu chi» thì đó là chủ ý phân quyền, không phải lỗi. Còn khi có lỗi tải thật, đầu trang sẽ có băng đỏ kèm nút **Tải lại**."
      },
      {
        "type": "h3",
        "text": "Trang «KPI» — điểm hiệu suất hằng tháng"
      },
      {
        "type": "p",
        "text": "**Ai thấy mục KPI:** mọi vai trò trừ Kế toán / Nhân sự. Chọn kỳ bằng ô chọn tháng ở góc phải. Trang có 3 tab: **Của tôi**, **Đội nhóm**, **Bảng xếp hạng** — tab Đội nhóm chỉ hiện với Giám đốc, Trưởng phòng, Trưởng nhóm KD, Ban Quản Trị và Điều phối kinh doanh."
      },
      {
        "type": "list",
        "items": [
          "**Của tôi** — vòng tròn điểm KPI (xanh lá từ 80, vàng từ 60, đỏ dưới 60) kèm hạng của bạn trong đội và toàn công ty. Điểm gồm 3 nhóm: **Nỗ lực 30%** (hoạt động, SLA, tốc độ phản hồi), **Kết quả 50%** (số HĐ ký, giá trị, chuyển đổi), **Chất lượng 20%** (tỷ lệ bị thu hồi, mất khách).",
          "**Đội nhóm** — bảng điểm từng thành viên: điểm, SLA, HĐ ký, hoạt động/ngày. Dành cho trưởng nhóm theo dõi cả đội.",
          "**Bảng xếp hạng** — top 3 có huy chương 🥇🥈🥉; top 5 hiện tên, từ hạng 6 trở xuống ẩn danh («Nhân viên #n»). Dòng của bạn được viền vàng kèm nhãn «Bạn»."
        ]
      },
      {
        "type": "tip",
        "text": "Chưa thấy điểm? KPI chỉ hiện khi kỳ đó bạn có lead hoặc công trình được gán. Thử lùi về tháng trước bằng ô chọn tháng."
      },
      {
        "type": "p",
        "text": "Lưu ý chính sách ghi ngay chân trang KPI: dữ liệu quá tải chỉ dùng để hỗ trợ, **không dùng để phạt hay xếp loại**."
      }
    ]
  },
  {
    "id": "cham-cong",
    "icon": "clock",
    "title": "Chấm công hằng ngày «Chấm công»",
    "blocks": [
      {
        "type": "p",
        "text": "Vào menu **Chấm công**, trang «Chấm công & Nghỉ phép» có 3 thẻ: **Chấm công**, **Nghỉ phép**, **Phiếu lương**. Hầu hết mọi người đều dùng được trang này (riêng vai trò Ban Quản Trị không dùng)."
      },
      {
        "type": "h3",
        "text": "Lần đầu tiên: liên kết Telegram (làm 1 lần, mất 1 phút)"
      },
      {
        "type": "steps",
        "items": [
          "Mở app **Telegram** trên điện thoại, tìm bot của công ty (chưa biết tên bot thì hỏi Admin).",
          "Nhắn cho bot chữ `/id` — bot trả về một dãy số (đó là ID của bạn).",
          "Quay lại ERP, vào menu **Cài đặt**, tìm mục **Telegram Bot**.",
          "Dán dãy số vào ô «Dán Telegram ID của bạn» rồi bấm **Lưu**.",
          "Quay lại Telegram, nhắn `/start` cho bot để kiểm tra. Xong!"
        ]
      },
      {
        "type": "h3",
        "text": "Chấm công mỗi ngày"
      },
      {
        "type": "list",
        "items": [
          "**Cách nhanh nhất — qua Telegram:** nhắn `/checkin` cho bot khi bắt đầu làm, `/checkout` khi về. Vào ca văn phòng mà bot đòi vị trí thì bấm nút **«📍 Gửi vị trí hiện tại»** bot hiện ra. Đang ở công trường thì nhắn `/checkin` kèm mã dự án, bot sẽ ghi kèm vị trí GPS.",
          "**Trên web:** vào trang Chấm công, bấm nút **Vào ca** (màu vàng) khi bắt đầu, bấm **Tan ca** khi về. Cách này dùng khi đang ngồi máy tính.",
          "**Mất mạng giữa chừng?** Cứ yên tâm — hệ thống tự gửi lại lần chấm công đó ngay khi có sóng."
        ]
      },
      {
        "type": "p",
        "text": "**Xem bảng công của bạn:** ngay dưới nút chấm công có ô chọn tháng. Bảng liệt kê từng ngày: giờ vào, giờ ra, giờ công, tăng ca (OT). Phía trên có tổng: Công, Giờ, OT đã duyệt. Ngày nào có dấu ⚠️ nghĩa là bạn quên bấm tan ca — báo trưởng phòng hoặc kế toán để xác nhận lại."
      },
      {
        "type": "tip",
        "text": "Trưởng phòng, Trưởng nhóm KD (team mình), Kế toán và Giám đốc còn thấy thêm: khối «OT chờ duyệt» và bảng công team / toàn công ty ở cuối trang."
      },
      {
        "type": "h3",
        "text": "Nhãn «✓VP» và duyệt OT (mới 09/09)"
      },
      {
        "type": "list",
        "items": [
          "**Từ 22/10 vào ca văn phòng phải bật vị trí (GPS) và đứng trong bán kính 20 m** quanh văn phòng. Ngoài bán kính, màn hình báo bạn đang cách văn phòng bao nhiêu mét và không cho vào ca. Đang dùng wifi văn phòng thì không cần GPS. Nhân viên hiện trường (Giám sát, Quản lý dự án) và check-in tại công trình không bị giới hạn này. Vào ca hợp lệ thì bảng công gắn nhãn **✓VP**.",
          "Thẻ hôm nay có đồng hồ **«Đang làm: 3h12»** tự chạy và dòng **«Ngày công tháng này: X / 22 (không gồm OT)»**. Đủ 8 tiếng/ngày là 1 công; làm quá thì phần dư tính OT riêng, chờ duyệt.",
          "Tăng ca (OT) sau khi được duyệt sẽ hiện rõ **ai duyệt, lúc mấy giờ** ngay trong bảng công của bạn.",
          "**Trưởng nhóm Kinh doanh** từ nay duyệt được OT của người trong nhóm mình (trước chỉ Trưởng phòng/Admin/Kế toán).",
          "Công ty có máy chấm công thì Admin nối máy vào hệ thống ở **Cài đặt → Chấm công văn phòng** — lượt quẹt máy tự đổ về bảng công (nguồn hiện «Máy chấm công»)."
        ]
      }
    ]
  },
  {
    "id": "nghi-phep-ot",
    "icon": "send",
    "title": "Xin nghỉ phép, tăng ca & trang «Phê duyệt»",
    "blocks": [
      {
        "type": "h3",
        "text": "Xin nghỉ phép"
      },
      {
        "type": "steps",
        "items": [
          "Vào menu **Chấm công**, bấm thẻ **Nghỉ phép** ở góc phải trên.",
          "Xem số phép còn lại ở 4 ô trên cùng (Phép năm còn lại, Đã dùng, Nghỉ ốm, Không lương).",
          "Bấm nút vàng **+ Xin nghỉ phép**.",
          "Chọn loại phép (Phép năm có lương / Nghỉ ốm / Không lương), chọn **Từ ngày** – **Đến ngày**. Nghỉ nửa buổi thì tick ô **Nửa ngày**.",
          "Gõ lý do (ít nhất vài chữ) rồi bấm **Gửi đơn**."
        ]
      },
      {
        "type": "p",
        "text": "**Ai duyệt đơn của bạn?** Nghỉ từ 3 ngày trở xuống: trưởng nhóm của bạn duyệt. Nghỉ trên 3 ngày, hoặc bạn chưa có trưởng nhóm, hoặc bạn là trưởng phòng: đơn sẽ lên **Giám đốc** (có thể qua 2 cấp duyệt). Người duyệt nhận thông báo trên web và Telegram."
      },
      {
        "type": "p",
        "text": "**Theo dõi đơn ở đâu?** Bảng dưới thẻ Nghỉ phép hiện trạng thái từng đơn: Chờ duyệt (vàng), Đã duyệt (xanh), Từ chối (đỏ). Hoặc vào menu **Phê duyệt** → thẻ **Đơn của tôi**. Đơn còn chờ duyệt thì bấm **Hủy đơn** được."
      },
      {
        "type": "h3",
        "text": "Tăng ca (OT)"
      },
      {
        "type": "p",
        "text": "Giờ tăng ca hiện ngay trong bảng công của bạn kèm trạng thái: «OT chờ duyệt», «OT đã duyệt» hoặc «OT từ chối». Trưởng phòng / Trưởng nhóm KD (team mình) / Kế toán / Giám đốc duyệt OT trong khối **OT chờ duyệt** ở trang Chấm công — bấm **Duyệt** hoặc **Từ chối** từng ca."
      },
      {
        "type": "h3",
        "text": "Trang «Phê duyệt» — chỗ duyệt mọi loại đơn"
      },
      {
        "type": "p",
        "text": "Menu **Phê duyệt** gom tất cả đơn từ: nghỉ phép 🏖️, tạm ứng 💸, chi phí 🚗, tăng ca ⏰, bảng lương 🧾. Có 3 thẻ: **Chờ tôi** (đơn đang chờ bạn duyệt — có số đỏ báo ngay trên tiêu đề), **Đơn của tôi**, **Đã xử lý**. Duyệt thì bấm **Duyệt**; từ chối thì bấm **Từ chối** và bắt buộc gõ lý do. Đơn để lâu quá hạn sẽ hiện chữ đỏ «QUÁ HẠN», hệ thống nhắc người duyệt rồi tự chuyển lên Giám đốc nếu vẫn không ai xử lý."
      }
    ]
  },
  {
    "id": "nhan-su-doi",
    "icon": "user",
    "title": "Trang «Nhân sự» — hồ sơ, đội nhóm, nghỉ việc",
    "roles": [
      "Giám đốc",
      "Trưởng phòng",
      "Kế toán"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "**Ai thấy mục này:** Giám đốc, Trưởng phòng, Kế toán / Nhân sự và Trưởng nhóm Kinh doanh (chỉ thấy sale nhóm mình)."
      },
      {
        "type": "p",
        "text": "Trang **Nhân sự** có 4 nút chuyển cách xem ở góc phải trên: **Danh sách** (bảng đầy đủ tên, vai trò, phòng ban, email, SĐT, trạng thái), **Sơ đồ** (cây mạng lưới công ty), **Phòng ban** (gom theo Kinh doanh / Giám sát-Vận hành / Kế toán / Ban Giám đốc) và **Đội nhóm**. Ở mọi cách xem, **bấm vào thẻ một người là mở Hồ sơ 360°** của người đó để xem/sửa. Dòng của chính bạn luôn nằm đầu danh sách, tô vàng kèm nhãn «Bạn»."
      },
      {
        "type": "h3",
        "text": "Chế độ xem «Sơ đồ» — mạng lưới công ty"
      },
      {
        "type": "p",
        "text": "Mặc định là dạng **«Mạng lưới»**: cây tổ chức vẽ từ trên xuống **JAMA HOME → Ban Giám đốc → từng phòng ban → Trưởng phòng → nhóm/Trưởng nhóm → Nhân viên**. Kéo để di chuyển, cuộn chuột hoặc chụm 2 ngón để phóng to/thu nhỏ, bấm nút tròn dưới thẻ để mở/gập nhánh, bấm thẻ người để mở Hồ sơ 360°. **Thẻ của bạn tô vàng, có nhãn «Bạn»** và được đưa vào giữa màn hình khi mở. Thanh nút: «Tìm tôi», «Vừa màn hình», «Mở hết», «Thu gọn»; gõ tên vào ô tìm thì người khớp đầu tiên được tô sáng cả đường lên gốc. Muốn xem kiểu cũ thì bấm **«Dạng thẻ»**. Chỉ hiện người đang làm."
      },
      {
        "type": "h3",
        "text": "Chế độ xem «Đội nhóm»"
      },
      {
        "type": "p",
        "text": "Mỗi đội hiện thành một khối: **trưởng nhóm nằm trên cùng** (khung viền vàng), các thành viên xếp bên dưới. Ai chưa được xếp vào đội nào sẽ nằm ở khối «Chưa xếp đội» cuối trang. Muốn tạo đội mới hoặc đổi trưởng nhóm: làm trong trang **Tài khoản** (khối Đội nhóm) — việc của Admin. Trong khung sửa đội có ô **Tìm tên hoặc email** (gõ không dấu cũng được) để tick thành viên nhanh. Đội thuộc bộ phận **Ban Giám đốc** chọn trưởng nhóm là Giám đốc / Ban điều hành; các đội khác chọn Trưởng phòng / Trưởng nhóm KD."
      },
      {
        "type": "h3",
        "text": "Cho nhân viên nghỉ việc (Kế toán / Giám đốc làm)"
      },
      {
        "type": "steps",
        "items": [
          "Ở chế độ xem Danh sách, bấm nút đỏ **Cho nghỉ việc** ở dòng nhân viên đó.",
          "Hệ thống hiện trước danh sách **khách hàng (leads) và công việc** người này đang giữ.",
          "Để tick **Tự động phân bổ đều** thì hệ thống tự chia cho người còn lại; hoặc bỏ tick và tự chọn người nhận bàn giao.",
          "Bấm **Xác nhận nghỉ việc**. Lỡ tay? Trong vòng **7 ngày** vẫn bấm **Hoàn tác** được; qua 7 ngày thì chỉ Giám đốc bấm **Kích hoạt** lại được."
        ]
      },
      {
        "type": "warn",
        "text": "TẠO tài khoản đăng nhập mới là việc của Admin: dùng nút **+ Thêm nhân viên** ở trang Nhân sự (chỉ Giám đốc thấy nút này) hoặc trang **Tài khoản**. Nhân viên thường không tự tạo tài khoản. Form Thêm nhân viên ở trang Nhân sự cho nhập luôn **ảnh đại diện, số CCCD + ảnh 2 mặt, loại/ngày hợp đồng lao động + ảnh scan HĐLĐ** — đều không bắt buộc, thiếu thì bổ sung sau ở Hồ sơ 360°. Vai trò phòng ban (VD: Giám sát thi công) chọn được ngay trong ô Vai trò."
      },
      {
        "type": "h3",
        "text": "Hồ sơ nhân viên chi tiết (mới 09/09)"
      },
      {
        "type": "p",
        "text": "Bấm vào **một nhân viên bất kỳ** trong danh sách để mở trang hồ sơ chi tiết: thông tin cá nhân + hợp đồng lao động, chấm công, nghỉ phép — và với Admin/Kế toán có thêm tab **Tiền** (lương, thưởng, hoa hồng, tạm ứng) + tab **Bàn giao** (ai nghỉ việc, khách/việc đã sang tay ai)."
      },
      {
        "type": "p",
        "text": "**Lương & BHXH từng người (mới 24/10):** trong Hồ sơ 360° có thẻ «Lương & BHXH» — lương ký HĐLĐ, mức lương đóng BHXH, phụ cấp hàng tháng, ngày bắt đầu đóng BHXH. Chỉ Giám đốc và Kế toán sửa được. Muốn điền hàng loạt: ở trang Nhân sự bấm **Nhập Excel** → chọn file danh sách nhân sự của HCNS (có cột «HỌ VÀ TÊN») → **Xem trước** để thấy ai khớp, ô nào sẽ đổi, ai chưa có tài khoản → bấm **Áp dụng**. Ô trống trong file không xóa dữ liệu cũ; người chưa khớp tên thì sửa họ tên tài khoản cho giống file rồi nhập lại."
      }
    ]
  },
  {
    "id": "ho-so-nhan-vien",
    "icon": "user",
    "title": "Hồ sơ nhân viên 360° — CCCD, HĐLĐ, tiền, bàn giao",
    "roles": [
      "Admin",
      "Kế toán"
    ],
    "blocks": [
      {
        "type": "p",
        "text": "Mở menu **Nhân sự** → bấm vào một nhân viên. Trang hồ sơ có các tab; nhân viên thường cũng mở được hồ sơ CỦA CHÍNH MÌNH để xem (không sửa được)."
      },
      {
        "type": "p",
        "text": "**Đổi họ tên:** Ban Giám đốc và Kế toán / Nhân sự thấy **nút bút chì** cạnh tên ở đầu hồ sơ → bấm, sửa tên, bấm **Lưu** (hoặc Enter; Esc để hủy). Tên mới hiện ngay ở mọi nơi. Nhân viên khác không tự đổi tên được — nhờ Kế toán / Nhân sự sửa giúp."
      },
      {
        "type": "table",
        "header": [
          "Tab",
          "Có gì",
          "Ai xem được"
        ],
        "rows": [
          [
            "Hồ sơ & HĐLĐ",
            "CCCD, ngày sinh, địa chỉ, TK ngân hàng, BHXH, ngày vào làm, loại HĐ + ngày hết hạn, ảnh giấy tờ",
            "Admin, Kế toán (sửa) · chính chủ (xem)"
          ],
          [
            "Tiền",
            "Lương từng kỳ, thưởng, hoa hồng, tạm ứng, giao dịch sổ kế toán gắn người",
            "CHỈ Admin + Kế toán · chính chủ"
          ],
          [
            "Chấm công / Nghỉ phép",
            "Bảng công từng ngày theo kỳ, số phép đã dùng",
            "Thêm Trưởng nhóm/phòng (người trong nhóm mình)"
          ],
          [
            "Bàn giao",
            "Nghỉ việc thì khách/đầu việc nào đã sang tay ai, lúc nào",
            "Admin, Kế toán"
          ],
          [
            "Nhật ký",
            "Ai đổi lương/quyền/cho nghỉ việc người này",
            "Chỉ Admin"
          ]
        ]
      },
      {
        "type": "steps",
        "items": [
          "Điền hồ sơ: mở tab **Hồ sơ & HĐLĐ** → bấm **Sửa** → điền → **Lưu**.",
          "Tải ảnh CCCD/HĐLĐ: kéo xuống khối **Giấy tờ** → bấm **+ CCCD mặt trước** (hoặc loại khác) → chọn ảnh — app tự nén JPG cho nhẹ, không cần chỉnh gì. Ảnh tải lên hiện ngay thành hình thu nhỏ, bấm vào ảnh để xem lớn.",
          "Nhập **Ngày hết hạn** hợp đồng để hệ thống nhắc gia hạn (HĐ không thời hạn thì để trống)."
        ]
      },
      {
        "type": "warn",
        "text": "Giấy tờ tùy thân là dữ liệu nhạy cảm — hệ thống KHÔNG đăng lên nhóm Telegram (khác ảnh công trình) và chỉ Admin/Kế toán/chính chủ mở được. Đừng chụp CCCD gửi qua Zalo/nhóm chat cho nhau."
      },
      {
        "type": "tip",
        "text": "Nhân viên đã nghỉ việc vẫn mở được hồ sơ (có nhãn «Đã nghỉ việc») — mọi lịch sử lương, hoa hồng, bàn giao giữ nguyên để tra cứu."
      }
    ]
  },
  {
    "id": "luong",
    "icon": "wallet",
    "title": "Xem lương & phiếu lương",
    "blocks": [
      {
        "type": "h3",
        "text": "Nhân viên: xem phiếu lương của mình"
      },
      {
        "type": "p",
        "text": "Vào menu **Chấm công** → bấm thẻ **Phiếu lương**. Mỗi kỳ lương là một tấm thẻ ghi rõ: lương cơ bản, số công, tiền OT, hoa hồng, thưởng, phụ cấp, trừ BHXH, thuế TNCN, tạm ứng… và số **thực lĩnh** in đậm màu vàng."
      },
      {
        "type": "list",
        "items": [
          "🔒 Bạn **chỉ xem được phiếu của chính mình**, và chỉ các kỳ **đã chi lương** mới hiện ra.",
          "Phiếu lương chi tiết còn được bot gửi vào **Telegram chat riêng** của từng người — không ai khác đọc được.",
          "Chưa thấy phiếu? Kỳ lương đó có thể chưa chi, hoặc bạn chưa liên kết Telegram (xem mục Chấm công ở trên)."
        ]
      },
      {
        "type": "h3",
        "text": "Kế toán / Giám đốc: chạy lương cuối tháng"
      },
      {
        "type": "p",
        "text": "Ở thẻ **Chấm công**, Kế toán và Giám đốc thấy khối **«Chốt sổ»** — đi từ trên xuống đúng 5 bước: (1) rà các ca quên tan ca, (2) duyệt hết OT tồn, (3) bấm **Sinh bảng lương**, (4) bấm **Trình duyệt** để Giám đốc duyệt (quá 72 giờ chưa duyệt sẽ có nhắc qua Telegram), (5) sau khi duyệt xong bấm **Xác nhận đã chi** — hệ thống tự gửi phiếu lương riêng cho từng người."
      },
      {
        "type": "tip",
        "text": "Bảng lương lấy **lương ký HĐLĐ** trong Hồ sơ 360° của từng người (trừ BHXH theo mức lương đóng BHXH, cộng phụ cấp). Ai chưa điền lương HĐ thì mới lấy theo bậc lương. Báo có nhân viên lương 0đ thì điền lương ở Hồ sơ 360° (hoặc gán bậc ở trang **Tài khoản**), rồi sinh lại."
      }
    ]
  },
  {
    "id": "telegram-bot",
    "icon": "send",
    "title": "Trợ lý Telegram — làm việc ngay trên điện thoại",
    "blocks": [
      {
        "type": "p",
        "text": "Công ty có bot Telegram riêng: chấm công GPS ở công trình, xem khách của mình, xin nghỉ phép, xem phiếu lương, báo lỗi… đều nhắn tin là xong, không cần mở web. Nhưng trước tiên bạn phải **liên kết tài khoản 1 lần** (chỉ mất 1 phút)."
      },
      {
        "type": "steps",
        "items": [
          "Mở Telegram, tìm bot của công ty (chưa biết tên bot thì hỏi Admin).",
          "Nhắn `/id` cho bot — bot trả về một dãy số, đó là **Telegram ID của bạn**.",
          "Vào ERP trên web → menu **Cài đặt** → mục **Telegram Bot** → dán dãy số vào ô → bấm **Lưu**.",
          "Quay lại bot, nhắn `/start`. Bot chào đúng tên bạn là xong. Nếu bot báo «Chưa liên kết tài khoản ERP» thì kiểm tra lại dãy số hoặc nhờ Admin."
        ]
      },
      {
        "type": "tip",
        "text": "**Ngại dán số?** Chỉ cần nhắn `/start` cho bot hoặc nhắn một câu trong nhóm công ty có bot. Bot tự ghi nhận bạn, Admin vào **Tài khoản** → thẻ **«Telegram chưa gán»** chọn đúng tên bạn (hệ thống gợi ý sẵn theo tên) rồi bấm **Gán** là xong."
      },
      {
        "type": "h3",
        "text": "Gõ /help để bot tự hướng dẫn"
      },
      {
        "type": "list",
        "items": [
          "Gõ `/help` trong chat với bot: bot gửi sổ tay ngắn **theo đúng vai của bạn** (ai cũng thấy chấm công, báo cáo công trình, nghỉ phép; Kinh doanh thêm /lead, /pipeline; Thu mua thêm phần nhập báo giá; Trưởng phòng/BGĐ thêm phần duyệt). Người chưa được gán tài khoản cũng gõ được.",
          "Đang làm dở việc gì, gõ `/cancel` là thoát."
        ]
      },
      {
        "type": "h3",
        "text": "Thu mua: gửi tệp báo giá NCC cho bot (/baogia)"
      },
      {
        "type": "list",
        "items": [
          "Gõ `/baogia` → bấm chọn dự án → gửi **tệp báo giá của nhà cung cấp**: Excel (.xlsx), CSV, PDF hoặc ảnh chụp bảng giá. Bot đọc tệp, tìm mã sản phẩm và giá, rồi **khớp mã với phiếu vật tư của dự án**.",
          "Bot hiện **bản xem trước**: phòng · mã · giá · còn hàng; mã nào không có trong phiếu thì báo bỏ qua. **Chưa ghi gì** cho tới khi bạn bấm **«✅ Ghi N báo giá»**. Tệp không ghi tên NCC thì gõ tên NCC trước khi bấm Ghi.",
          "Ghi xong, báo giá nằm trong từng dòng phiếu ở web (Vật tư → Cần hỏi giá), ghi chú «Nhập từ tệp … bởi … (bot)». Chốt giá vẫn làm trên web như cũ.",
          "Chỉ Thu mua (và Giám đốc) dùng được; Kinh doanh/Thiết kế gọi sẽ bị từ chối. Không nhập từ Word (hợp đồng, biên bản) hay bảng giá không có mã — bot sẽ báo rõ lý do.",
          "`/nhapmau <link Google Sheet>`: thêm mẫu mới vào Danh mục ngay từ Telegram (chỉ thêm, không ghi đè mẫu đã có). Sheet phải ở chế độ «Bất kỳ ai có liên kết đều xem được»."
        ]
      },
      {
        "type": "h3",
        "text": "Bấm chọn dự án, không cần nhớ mã"
      },
      {
        "type": "list",
        "items": [
          "Gõ `/baocao`, `/suco`, `/vatlieu`, `/duan`, `/checkin` hoặc `/checkout` **không kèm gì**: bot hiện danh sách dự án bạn đang phụ trách, bấm một nút là vào việc. Chấm công có thêm nút **«🏢 Văn phòng»**.",
          "Đang gửi ảnh báo cáo/sự cố: bấm **«✅ Gửi»** khi xong, **«❌ Hủy»** để bỏ. Gõ `/done`, `/cancel` vẫn được.",
          "Quen gõ mã rồi thì cứ gõ như cũ, ví dụ `/baocao JMH-0601 Đã đổ bê tông sàn 2`.",
          "Gõ `/` trong khung chat để xem danh sách lệnh kèm giải thích tiếng Việt."
        ]
      },
      {
        "type": "h3",
        "text": "Gửi bản vẽ, PDF trong báo cáo"
      },
      {
        "type": "list",
        "items": [
          "Trong `/baocao`, gửi bản vẽ (.skp, .dwg), PDF, video như gửi tệp bình thường — nặng mấy cũng được.",
          "Bot tự **chép tệp vào topic của dự án** trong nhóm «JAMA Công trình» và ghi vào **Tài liệu dự án** trên ERP; nhật ký cập nhật dự án có link mở đúng tệp đó.",
          "Bấm **«✅ Gửi»** xong, người phụ trách dự án và người đảm nhận đầu việc nhận thông báo ngay (chuông trên ERP, và điện thoại/máy tính nếu đã bật).",
          "Bot báo «Chưa chép được vào topic dự án» thì báo cáo vẫn lưu kèm link tin gốc — báo Admin kiểm tra nhóm Kho."
        ]
      },
      {
        "type": "tip",
        "text": "**Nhận thông báo trên điện thoại/máy tính:** vào **Cài đặt → Thông báo trên máy này → Bật**, bấm **«Gửi thử»** để kiểm. Mỗi máy bật một lần. iPhone/iPad (iOS 16.4+): mở ERP bằng Safari → nút Chia sẻ → **«Thêm vào MH chính»**, rồi mở JAMA từ màn hình chính mới bật được."
      },
      {
        "type": "h3",
        "text": "Các lệnh dùng hằng ngày"
      },
      {
        "type": "table",
        "header": [
          "Lệnh",
          "Dùng để làm gì"
        ],
        "rows": [
          [
            "`/start`",
            "Mở menu nút bấm — quên lệnh thì cứ gõ /start"
          ],
          [
            "`/checkin [mã DA]` · `/checkout [mã DA]`",
            "Chấm công vào/ra tại công trình, bot ghi nhận vị trí GPS. Gõ `/checkin` không kèm mã = vào ca văn phòng; bot đòi vị trí thì bấm nút «📍 Gửi vị trí hiện tại» (phải trong 20 m)"
          ],
          [
            "`/pipeline` · `/briefing`",
            "Xem khách mình đang chăm theo từng giai đoạn · tóm tắt việc hôm nay"
          ],
          [
            "`/lead`",
            "Nhập khách mới: dán/chuyển tiếp tin nhắn Zalo của khách, bot tự đọc thông tin"
          ],
          [
            "`/duan [mã DA]`",
            "Tra cứu nhanh một dự án. Gõ `/duan` không mã thì bấm chọn từ danh sách"
          ],
          [
            "`/baocao [mã DA] [nội dung]`",
            "Báo cáo tiến độ công trình, gửi kèm ảnh được, bấm «✅ Gửi» (hoặc gõ `/done`) khi xong"
          ],
          [
            "`/vatlieu [mã DA] [tên] - [SL] [đơn vị]`",
            "Yêu cầu vật tư cho công trình"
          ],
          [
            "`/suco [mã DA] [mô tả]`",
            "Báo sự cố tại công trình (kèm ảnh)"
          ],
          [
            "`/dutoan`",
            "Dự toán cải tạo bằng AI: nhập số liệu, mô tả hoặc gửi hình"
          ],
          [
            "`/nghiphep [từ] [đến] [lý do]`",
            "Xin nghỉ phép, ví dụ `/nghiphep 20/07 21/07 việc gia đình`"
          ],
          [
            "`/tamung [số tiền] [lý do]`",
            "Xin tạm ứng lương (tối đa 30% lương cơ bản, trừ kỳ lương sau)"
          ],
          [
            "`/congcuatoi` · `/phieuluong`",
            "Bảng công tháng này · phiếu lương gần nhất"
          ],
          [
            "`/choduyet`",
            "Sếp xem đơn chờ mình duyệt, bấm ✅ Duyệt / ❌ Từ chối ngay trong chat"
          ],
          [
            "`/feedback` · `/myfeedback`",
            "Báo lỗi, góp ý về hệ thống · xem lại góp ý đã gửi"
          ],
          [
            "`/cancel`",
            "Đang nhập dở mà muốn hủy thì gõ lệnh này (hoặc bấm nút «❌ Hủy»)"
          ]
        ]
      },
      {
        "type": "p",
        "text": "Bot cũng **tự nhắn cho bạn** không cần gọi: báo kết quả khi đơn nghỉ phép/tạm ứng được duyệt hay từ chối, nhắc khách lâu chưa liên hệ lại, nhắc đợt thanh toán trễ hạn, và gửi tóm tắt công việc mỗi sáng vào nhóm chung của công ty."
      },
      {
        "type": "h3",
        "text": "Gửi ảnh công trình — vào Kho ảnh"
      },
      {
        "type": "list",
        "items": [
          "Tải **nhiều ảnh một lúc** trên web (ghi chú đầu việc hoặc khối «Ảnh dự án»): nhóm Kho ảnh nhận **một album** (tối đa 10 ảnh/album) thay vì mỗi ảnh một tin — đỡ trôi tin nhóm.",
          "Ảnh gửi trong `/baocao` và `/suco` được lưu ngay vào **Kho ảnh công trình** (bot báo «✅ Đã lưu ảnh»), hiện trên web ở khối «📷 Ảnh dự án».",
          "Nhanh nhất: vào nhóm **«JAMA Công trình»**, mở **đúng topic của dự án** (mỗi dự án một topic, tên dạng «MÃ · Tên dự án») rồi **thả ảnh vào, không cần gõ lệnh**. Bot thả 👍 là đã ghi nhận. Ghi chú thì gõ luôn vào chú thích ảnh.",
          "Bot không thả 👍? Kiểm tra bạn đã liên kết Telegram với ERP (phần trên) và đang gửi đúng topic dự án, không phải mục «General»."
        ]
      },
      {
        "type": "h3",
        "text": "Gửi bản vẽ, video, tệp nặng trong /baocao"
      },
      {
        "type": "list",
        "items": [
          "Trong `/baocao` gửi được cả **bản vẽ (SKP, DWG, PDF…), video, ghi âm** — trước hay sau khi gõ nội dung đều được. Gửi tệp kèm **chú thích** thì chú thích được lấy làm nội dung báo cáo.",
          "Xong bấm **✅ Gửi**, hoặc gõ **xong** / **done** / `/done`. Bot trả lời **«✅ Báo cáo đã được lưu vào ERP!»** kèm đường dẫn mở thẳng dự án trên web.",
          "Xem trên web: **Dự án → mở dự án → bấm đầu việc → Lịch sử cập nhật**. Mỗi tệp hiện tên + dung lượng + nút **«Mở trong Telegram»** để mở đúng tin gốc trong nhóm.",
          "Tệp nặng (trên 20 MB) vẫn nằm trong nhóm Telegram, ERP chỉ giữ link — nên gửi báo cáo **trong nhóm dự án**; gửi trong chat riêng với bot thì không có link mở lại."
        ]
      },
      {
        "type": "warn",
        "text": "`/phieuluong` chỉ xem được trong **chat riêng** với bot — gõ trong nhóm bot sẽ từ chối để lộ lương không ai thấy."
      },
      {
        "type": "tip",
        "text": "Chưa liên kết Telegram thì chấm công qua bot, nhắc việc tự động và cả nút «Quên mật khẩu?» đều không dùng được — nên làm ngay trong tuần đầu."
      }
    ]
  },
  {
    "id": "phan-quyen-tong-quan",
    "icon": "shield",
    "title": "Phân quyền — vì sao menu của tôi khác người bên cạnh?",
    "blocks": [
      {
        "type": "p",
        "text": "Mỗi vai trò chỉ thấy những menu mình cần dùng. **Không thấy một mục nào đó không phải là lỗi** — là bạn chưa được cấp quyền. Nếu bấm vào đâu đó bị chặn, hệ thống sẽ báo rõ tên quyền còn thiếu (ví dụ «Xem Kế toán») — chụp màn hình gửi Admin để được mở đúng ô đó."
      },
      {
        "type": "p",
        "text": "**Ai thấy mục này:** hai menu «Phân quyền» và «Tài khoản» chỉ hiện với người có quyền Quản lý Users — mặc định là **Giám đốc** và **Kế toán / Nhân sự**."
      },
      {
        "type": "table",
        "header": [
          "Vai trò",
          "Mảng việc chính trên hệ thống"
        ],
        "rows": [
          [
            "Giám đốc (admin)",
            "Toàn quyền — thấy và sửa được mọi thứ, kể cả phân quyền"
          ],
          [
            "Ban Quản Trị",
            "Xem P&L, Tài chính, Dự án, Báo cáo, KPI — nắm số liệu, không thao tác vận hành"
          ],
          [
            "Trưởng phòng",
            "Khách của cả nhóm, duyệt đơn, tạo dự án/hợp đồng, KPI, chấm công"
          ],
          [
            "Trưởng nhóm Kinh doanh",
            "Nhận data từ CSKH, chia khách cho sale trong nhóm, báo giá, KPI đội nhóm, duyệt OT + xem bảng công team"
          ],
          [
            "Nhân viên Sale",
            "Khách của riêng mình, báo giá, Báo giá tức thì, chấm công, KPI"
          ],
          [
            "Kế toán / Nhân sự",
            "Thu chi, lương, xác nhận đã thu tiền hợp đồng, tài khoản nhân viên, P&L"
          ],
          [
            "Quản lý dự án",
            "Điều phối dự án và đầu việc, kho, báo giá thi công, phê duyệt"
          ],
          [
            "Thiết kế",
            "Đầu việc thiết kế trong dự án, xem báo giá để nắm phạm vi đã bán"
          ],
          [
            "Giám sát thi công",
            "Đầu việc thi công, yêu cầu vật tư, chấm công GPS tại công trình. Vai «Giám sát» cũ đã gộp vào Trưởng phòng Giám sát (22/10)"
          ],
          [
            "Thu mua",
            "Kho vật tư, nhà cung cấp, so giá, đầu việc thu mua trong dự án"
          ]
        ]
      },
      {
        "type": "tip",
        "text": "Bảng trên là quyền **mặc định**. Giám đốc có thể bật/tắt từng quyền cho từng vai trò trên trang «Phân quyền», hoặc cho từng người ngay khi sửa tài khoản trong trang «Tài khoản», nên thực tế của bạn có thể khác chút — cứ lấy màn hình của mình làm chuẩn."
      },
      {
        "type": "p",
        "text": "**Đọc bảng Phân quyền:** các cột chia 2 nhóm — **Vai trò có sẵn** (Giám đốc, Trưởng phòng, Nhân viên Sale, Kế toán / Nhân sự) và **Vai trò tự tạo** (thêm ở trang Tài khoản, ví dụ Thiết kế, Thu mua). Bấm ô tròn để bật/tắt, xong bấm **Lưu tất cả thay đổi**. Nút mũi tên vòng nhỏ dưới tên vai trò có sẵn = khôi phục quyền mặc định của vai trò đó."
      }
    ]
  },
  {
    "id": "meo-xu-ly-loi",
    "icon": "info",
    "title": "Gặp trục trặc? Đọc mục này trước khi hoảng",
    "blocks": [
      {
        "type": "h3",
        "text": "Băng đỏ «Chưa tải được số liệu»"
      },
      {
        "type": "p",
        "text": "Đây là **lỗi tải trang, không phải số liệu bằng 0**. Đừng vội báo mất dữ liệu — bấm nút **Tải lại** trên băng đỏ (hoặc tải lại trang). Mạng yếu ở công trình rất hay gặp cảnh này."
      },
      {
        "type": "h3",
        "text": "Quên mật khẩu"
      },
      {
        "type": "p",
        "text": "Ở trang đăng nhập, bấm **«Quên mật khẩu?»** — hệ thống gửi mã 6 số qua Telegram đã liên kết, nhập mã là đặt lại được. Chưa liên kết Telegram thì nút này không giúp được — nhờ Admin đặt lại giùm, rồi nhớ liên kết Telegram luôn."
      },
      {
        "type": "h3",
        "text": "Báo lỗi, góp ý cải tiến"
      },
      {
        "type": "p",
        "text": "Nhắn `/feedback` cho bot Telegram → chọn loại (Bug / Lỗi · Tính năng mới · Cải thiện workflow · Khác) → gõ nội dung. Xem lại phản hồi bằng `/myfeedback`. Trang «Góp ý» trên web là nơi Giám đốc và Ban Quản Trị đọc và trả lời các góp ý này."
      },
      {
        "type": "list",
        "items": [
          "**Sau mỗi bản cập nhật**, mở menu **«Có gì mới»** đọc 1 phút — nút đổi chỗ, tính năng mới đều ghi ở đó.",
          "**Không thấy menu nào đó** = chưa có quyền, xem mục Phân quyền ở trên.",
          "**Chuông ở góc trên phải**: tab «Cần xử lý» / «Gần đây», số đỏ là thông báo chưa đọc.",
          "**Cài app ra màn hình chính điện thoại**: Android bấm «Cài đặt» trên banner; iPhone bấm nút Chia sẻ → «Thêm vào MH chính»."
        ]
      }
    ]
  },
  {
    "id": "quy-trinh-tong-the",
    "icon": "compass",
    "title": "Bức tranh lớn — một đơn hàng chạy qua hệ thống thế nào",
    "blocks": [
      {
        "type": "p",
        "text": "Đọc mục này để hiểu việc của bạn nằm ở đâu trong chuỗi. Mỗi người chỉ cần làm đúng ô của mình — hệ thống tự nối các khâu lại với nhau."
      },
      {
        "type": "steps",
        "items": [
          "**Data khách về** — CSKH nhập khách mới vào menu **«Quy trình»** (hoặc dán tin nhắn Zalo cho bot bằng lệnh `/lead`).",
          "**Chia khách** — CSKH chia data về Trưởng nhóm Kinh doanh, trưởng nhóm chia tiếp cho từng Sale trong nhóm mình.",
          "**Sale tư vấn** — kéo thẻ khách qua các cột: **Tiếp nhận mới → Đang tư vấn → Đã gửi báo giá → Đang đàm phán**. Cần ra giá nhanh cho khách thì dùng menu **«Báo giá tức thì»**.",
          "**Deal thắng** — kéo thẻ vào cột **«Deal đã thắng»**: hệ thống TỰ tạo Khách hàng + Dự án (kèm 19 đầu việc chuẩn) + Hợp đồng. Thẻ đã thắng không kéo lùi lại được, nên chắc chắn rồi hãy kéo.",
          "**Dự án chạy** — 19 đầu việc chia sẵn theo phòng ban: Thiết kế → Báo giá → Thu mua → Thi công → Nghiệm thu, bàn giao. Mỗi bộ phận có người phụ trách (PIC) được gán ngay trong dự án; ai xong việc nấy thì đổi trạng thái đầu việc.",
          "**Thu tiền từng đợt** — hợp đồng mặc định 4 đợt: Đặt cọc → Nghiệm thu thô → Nghiệm thu nội thất → Bàn giao. Tiền về tài khoản rồi thì bấm **«Xác nhận TT»** trong trang Hợp đồng — chỉ Kế toán, Giám đốc, Trưởng nhóm bấm được nút này.",
          "**Chốt sổ** — số thu/chi tự chảy vào trang **Kế toán** và **P&L**: sếp nhìn thấy lãi/lỗ của từng dự án mà không ai phải cộng tay."
        ]
      },
      {
        "type": "tip",
        "text": "Khách ký hợp đồng rồi mà chưa thấy dự án? Kiểm tra thẻ khách đã được kéo vào đúng cột «Deal đã thắng» chưa — hệ thống chỉ tự tạo dự án ở bước đó."
      }
    ]
  },
  {
    "id": "che-do-thuong",
    "icon": "wallet",
    "title": "Chế độ thưởng & Điểm JAMA — làm tốt thì nhận gì",
    "blocks": [
      {
        "type": "p",
        "text": "Công ty có **5 chương trình thưởng**, Admin bật/tắt và chỉnh số ở menu **«Chế độ thưởng»** (hoặc Cài đặt → Nhân sự). Mỗi chương trình chạy theo **Tháng** hoặc **Quý**. Đổi luật thì **áp từ kỳ sau**, có lưu lịch sử."
      },
      {
        "type": "table",
        "header": [
          "Chương trình",
          "Cách tính (số mẫu)"
        ],
        "rows": [
          [
            "Hũ doanh số",
            "Doanh số công ty (= giá trị dự án khi thắng deal, tính theo ngày thắng) vượt mốc 8 / 12 / 14,4 / 18 tỷ → quỹ mở 20 / 50 / 100 / 200 triệu, chia theo % doanh số mỗi người"
          ],
          [
            "Chuyên cần",
            "100 điểm: đi trễ quá 5 phút −3, quên chấm ra −2, nghỉ không phép −15. Đủ chuẩn → +500k"
          ],
          [
            "Phản hồi khách",
            "Gọi khách mới trong 2 giờ (≥ 90%), trả lời Zalo trong 15 phút (≥ 85%); mỗi lead bỏ quá 24 giờ −2. Đạt → +1 triệu"
          ],
          [
            "Khách hàng đánh giá",
            "Khách chấm sao trên trang tiến độ ở 4 mốc. Trung bình ≥ 4,5 sao → 3 triệu/dự án; mỗi lời khen đích danh +300k; ≤ 2 sao → báo Trưởng phòng và giữ thưởng dự án đó"
          ],
          [
            "Ngôi sao quý",
            "Top 3 điểm JAMA của quý: 5 / 3 / 2 triệu (mặc định tắt)"
          ]
        ]
      },
      {
        "type": "h3",
        "text": "Điểm JAMA và hệ số thưởng"
      },
      {
        "type": "p",
        "text": "Điểm JAMA (0–100) gộp 4 phần **Doanh số · Chuyên cần · Phản hồi · Đánh giá**, trọng số theo phòng (Kinh doanh 40/20/25/15). Điểm ≥ 90 nhân **×1,2**; 70–89 **×1,0**; 50–69 **×0,5**; dưới 50 **không có thưởng**. Thử việc nhận 50%, đang bị kỷ luật thì không nhận."
      },
      {
        "type": "steps",
        "items": [
          "**Xem điểm của mình**: Hồ sơ nhân viên → tab **Tiền** → khối «Điểm JAMA» (hiện khi Admin bật «Nhân viên tự xem điểm»).",
          "**Hũ trên Tổng quan**: hũ vàng đầy dần theo doanh số công ty — mỗi lead chuyển «Thắng» thì giá trị dự án vừa tạo cộng ngay vào hũ (dự án hủy hoặc tạo tay không tính; dự án chưa nhập giá trị thì chưa cộng), kèm số còn thiếu tới mốc tiếp. Bảng «Ai đang đẩy hũ» chỉ ghi doanh số, không ghi tiền thưởng từng người.",
          "**Cuối kỳ**: Kế toán mở tab **Bảng thưởng** → kiểm tra → **«Chốt kỳ → gửi duyệt»**. Phiếu «Bảng thưởng» vào trang Phê duyệt; duyệt xong mới vào lương."
        ]
      },
      {
        "type": "tip",
        "text": "Số trong khối Điểm JAMA là **dự kiến**, cập nhật theo ngày. Số chính thức là bảng đã chốt và được duyệt."
      }
    ]
  }
];
