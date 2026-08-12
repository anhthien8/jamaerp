/**
 * Cờ bật/tắt tính năng dùng chung cho toàn app.
 */

/**
 * Chế độ Tập luyện (dữ liệu mẫu). Tắt từ 07/08/2026 — toàn công ty vào thẳng dữ liệu thật.
 *
 * NGHỈ HẲN từ 12/08/2026: chủ dự án chốt "đang là bản beta rồi nên không còn dùng chế độ
 * tập luyện nữa". Mã nguồn demo (lib/demo-data.ts + lớp resolveDemo trong lib/api.ts +
 * các nhánh isDemo ở trang) được GIỮ NGUYÊN ở trạng thái ngủ theo yêu cầu — đừng gỡ,
 * cũng đừng bật lại cờ này nếu chưa hỏi lại chủ dự án.
 *
 * Khi tắt: ẩn ô chọn chế độ ở màn đăng nhập, ẩn nút "← Demo" trên banner, và
 * AuthProvider xoá phiên demo còn lưu trên máy (xem lib/auth.tsx).
 */
export const SHOW_DEMO_MODE = false;
