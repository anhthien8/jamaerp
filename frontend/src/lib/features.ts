/**
 * Cờ bật/tắt tính năng dùng chung cho toàn app.
 */

/**
 * Chế độ Tập luyện (dữ liệu mẫu). Tắt từ 07/08/2026 — toàn công ty vào thẳng dữ liệu thật.
 * Bật lại khi cần đào tạo nhân sự mới: đổi thành true, KHÔNG cần sửa chỗ nào khác.
 * Khi tắt: ẩn ô chọn chế độ ở màn đăng nhập, ẩn nút "← Demo" trên banner, và
 * AuthProvider xoá phiên demo còn lưu trên máy (xem lib/auth.tsx).
 */
export const SHOW_DEMO_MODE = false;
