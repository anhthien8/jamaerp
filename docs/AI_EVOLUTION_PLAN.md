# Kế hoạch Module AI Tiến hoá — JAMA HOME

> Bản thu gọn 26/10/2026 theo nguyên tắc "Đơn giản trước tiên" trong `CLAUDE.md`.
> Bản 25/10 có 4 giai đoạn, 4 bảng mới, A/B prompt, tự chỉnh trọng số… — quá nhiều thứ đoán trước khi có số liệu.
> Bản này chỉ làm **một việc: đo xem AI hiện tại có giúp được ai không.** Các bước sau chỉ mở khi số liệu đòi.

## 1. Vì sao bắt đầu bằng đo

AI chỉ "tiến hoá" được khi biết nó đang đúng hay sai. Hiện nay:
- `ai_runs` đã ghi mọi lần agent chạy (`models/ai_memory.py`), có `outcome` Đã làm/Bỏ qua.
- `activities` đã ghi mọi lần lead đổi giai đoạn (`type = "stage_change"`), và `leads.stage` có `won`/`lost`.

→ Đã đủ dữ liệu để đo, **không cần bảng mới, không cần sửa agent.** Chỉ thiếu một chỗ tính và hiển thị.

## 2. Việc cần làm (≈ 1 tuần)

| # | Việc | Kiểm bằng |
|---|---|---|
| 1 | `services/ai_eval.py`: hàm `tinh_hieu_qua(db, tu_ngay, den_ngay)` trả 4 chỉ số ở mục 3, tính thẳng từ `ai_runs` + `activities` + `leads` | `tests/test_ai_eval.py` với dữ liệu mẫu biết trước đáp số |
| 2 | `GET /ai/hieu-qua?ky=30` trong `api/ai.py`, chỉ admin | test 403 với role khác, 200 với admin |
| 3 | Trang `/ai/hieu-qua`: 4 thẻ số + bảng lead điểm cao mà mất / điểm thấp mà thắng | `npm run lint && npm run build`, mở thử trên máy |

Không làm trong đợt này: nút 👍/👎, bảng bài học, RAG, agent mới.

## 3. Bốn chỉ số

1. **Tỷ lệ gợi ý Co-Pilot được làm** = `done / (done + skipped)` — và bao nhiêu gợi ý không ai phản hồi.
2. **Lead score có phân biệt được không** = tỷ lệ thắng của lead điểm ≥ 70 so với lead < 40 (lấy điểm gần nhất trong `ai_runs` trước khi lead chốt).
3. **Gợi ý được làm có giúp lead đi tiếp không** = % lead có `stage_change` tiến lên trong 7 ngày sau gợi ý "Đã làm", so với "Bỏ qua".
4. **AI thật hay luật dự phòng** = tỷ lệ `source = llm` vs `rule` — nếu phần lớn là luật thì "AI" đang không chạy.

## 4. Đọc số rồi quyết bước tiếp (sau ~1 tháng có số)

| Nếu số liệu cho thấy | Thì bước tiếp mới đáng làm |
|---|---|
| Sale ít phản hồi (nhiều gợi ý không ai bấm) | Sửa chỗ hiển thị gợi ý / thêm 👍👎 nhanh — vấn đề là thói quen, chưa phải AI |
| Điểm lead không phân biệt thắng/thua | Chỉnh trọng số trong `agents/lead_scoring.py` theo dữ liệu thắng/mất |
| Gợi ý "Đã làm" giúp lead đi tiếp rõ rệt | Đầu tư thêm: rút bài học từ ca thành công đưa vào prompt Co-Pilot |
| Phần lớn là luật dự phòng | Sửa cấu hình/quota LLM trước mọi thứ khác |

Ý tưởng lớn hơn (Trợ lý báo giá học từ quyết toán, giám sát tiến độ qua ảnh, chăm sóc sau bàn giao) giữ trong danh sách chờ — chọn một khi BGĐ thấy nhu cầu và có số liệu nền.

## 5. Ràng buộc (theo `CLAUDE.md`)

- Endpoint kiểm quyền theo ma trận V3; không gửi tên/SĐT khách lên LLM (đợt này không gọi LLM).
- Không đụng tới agent đang chạy; chỉ đọc dữ liệu.
