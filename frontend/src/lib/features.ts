/**
 * Cờ bật/tắt tính năng dùng chung cho toàn app.
 */

/**
 * Bảng điều khiển Kinh doanh (/sale-dashboard) — dựng 13/10/2026 theo dashboard
 * mẫu chủ dự án gửi, yêu cầu «làm demo trên tài khoản admin, không publish».
 *
 * Bật = CHỈ admin thấy mục menu và vào được trang. Backend cũng khóa cứng ở
 * admin (`VAI_TRO_XEM` trong app/api/sales_dashboard.py) nên tắt cờ này không
 * phải là lớp bảo mật duy nhất — nó chỉ để ẩn hẳn mục menu.
 *
 * Khi chốt mở cho Ban giám đốc / Trưởng phòng KD thì sửa HAI chỗ: `VAI_TRO_XEM`
 * ở backend và `VAI_TRO_SALE_DASHBOARD` ở Sidebar. Đừng chỉ sửa một bên — sửa
 * FE mà quên BE thì người ta thấy menu rồi bấm vào nhận 403.
 */
export const SHOW_SALES_DASHBOARD = true;
