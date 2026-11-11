# AI trong JAMA HOME ERP

> Viết lại 11/11/2026 từ code hiện tại (bản cũ 1.565 dòng, nhiều chỗ sai, ở
> `docs/archive/ai-workflow-cu-2026-06.md`). Khi tài liệu và code lệch nhau, tin code.

## 1. Nguyên tắc chung
- **Luật trước, AI sau.** Mọi tính năng AI đều có bộ luật dự phòng chạy được khi chưa cấu hình AI,
  hết quota hay AI lỗi. AI chỉ làm kết quả tốt hơn, không bao giờ là điều kiện để hệ thống chạy.
- **Một cửa gọi AI:** `backend/app/services/llm_config.py` → `llm_complete()`. Hàm này thử lần lượt
  chuỗi model trong cấu hình (model chính → các model dự phòng), lỗi hết thì ném lỗi để nơi gọi
  chuyển sang bộ luật.
- **Cấu hình:** model mặc định `groq/openai/gpt-oss-120b` (`backend/app/config.py`), đọc ảnh dùng
  `LLM_VISION_MODEL`. Admin đổi model/khoá ở Cài đặt → Cấu hình AI (`/ai-settings`). Mỗi người có
  thể gắn khoá riêng (`/ai-settings/my-key`).
- **Bộ nhớ AI:** `backend/app/services/ai_memory.py` + bảng `ai_runs` — lưu kết quả kèm nguồn
  (AI hay luật), dùng lại kết quả cũ khi hỏi y hệt trong 24 giờ, đọc lại lịch sử gợi ý.
- **Gửi ít dữ liệu nhất có thể:** không gửi email/SĐT/tên khách khi không cần; chỉ gửi dữ liệu
  liên quan (vd. giao việc chỉ gửi mã nhân viên của phòng làm dự án).

## 2. Các tác vụ AI

| Tác vụ | File | Khi nào chạy | Dự phòng khi không có AI |
|---|---|---|---|
| Đọc lead từ chữ tự do (Zalo, ghi chú) | `agents/lead_intake.py` · `POST /ai/parse-lead` | Khi sale dán đoạn chữ | Regex SĐT, ngân sách, diện tích, nguồn |
| Chấm điểm lead 0–100 | `agents/lead_scoring.py` | Worker mỗi giờ, 20 lead chưa chấm | Bảng điểm theo ngân sách, nguồn, loại nhà, độ tươi |
| Gợi ý việc tiếp theo cho lead (Co-Pilot) | `agents/sales_copilot.py` · `POST /ai/suggest-action` | Khi sale mở lead | Bộ luật theo giai đoạn + lịch sử; nhớ gợi ý đã "Đã làm/Bỏ qua" |
| Gợi ý người làm + hạn cho đầu việc dự án | `agents/task_coordinator.py` | Worker, chỉ cho dự án **chưa có đầu việc nào** — thực tế hiếm khi chạy vì 19 việc mẫu đã sinh lúc thắng deal | Bản thiết kế 19 việc cố định, giao theo vai trò |
| Nhận định kinh doanh định kỳ | `agents/insight_agent.py` | Worker mỗi 24 giờ | Nhận định theo ngưỡng cố định |
| Trợ lý Zalo (khách chờ, tóm tắt cuối ngày) | `services/zalo_assistant.py`, `services/zalo_analysis.py` | Theo tin nhắn nhóm Zalo / cuối ngày | Phân loại tin bằng từ khoá |
| Đọc báo giá NCC (Excel/PDF/ảnh) | `services/vat_tu_bao_gia_tep.py` | Khi gửi tệp báo giá cho bot | Không có — báo lỗi để nhập tay |

## 3. Chi phí token — quy tắc khi sửa
- Đặt `max_tokens` vừa đủ cho đầu ra cần thiết; JSON gửi lên dùng `separators=(",", ":")`, không thụt lề.
- Danh sách dài (dự án, lead, nhân viên) phải lọc/cắt trước khi gửi.
- Kết quả có thể tái dùng thì cache (bộ nhớ `ai_runs` hoặc `app.cache` theo băm nội dung).
- Tác vụ chạy theo lịch chỉ lấy bản ghi **chưa xử lý** — không gửi lại mỗi lần chạy.

## 4. Kiểm tra
- Test chạy đường bộ luật (tắt AI) để tất định: xem `backend/tests/test_bo_nho_ai.py`.
- Thử kết nối model: Cài đặt → Cấu hình AI → "Test kết nối" (`POST /ai-settings/test`).
