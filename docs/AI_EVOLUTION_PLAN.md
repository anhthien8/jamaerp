# Kế hoạch Module AI Tiến hoá — JAMA HOME

> Soạn ngày 25/10/2026. Mục tiêu: AI của JAMA **tự tốt lên theo thời gian** nhờ học từ chính dữ liệu và phản hồi của công ty (thiết kế – thi công nội thất), thay vì mỗi lần gọi LLM là một lần "quên sạch".

---

## 1. Hiện trạng (đã có trong code)

| Thành phần | File | Vai trò |
|---|---|---|
| 5 agent | `backend/app/agents/` (lead_intake, lead_scoring, sales_copilot, task_coordinator, insight_agent) | Hybrid: luật cứng + LLM qua `litellm` |
| Bộ nhớ AI | `models/ai_memory.py`, `services/ai_memory.py` | Bảng `ai_runs`: cache theo `input_hash`, lịch sử theo scope, `outcome` Đã làm/Bỏ qua |
| Cấu hình / key | `api/ai_settings.py`, `services/llm_user_key.py` | Key công ty + key riêng từng người |
| Trợ lý Zalo | `services/zalo_assistant.py` | Báo khách chờ, tóm tắt cuối ngày |

**Nền móng đã đúng hướng**: có ghi lại mọi lần chạy và có nút phản hồi. **Thiếu**: phản hồi mới chỉ được Co-Pilot đọc để "đừng gợi ý lặp"; chưa có vòng nào biến phản hồi + kết quả kinh doanh thật (thắng/mất deal, trễ tiến độ, vượt dự toán) thành tri thức để agent khác dùng, và chưa có cách đo agent đang giỏi lên hay tệ đi.

---

## 2. Thế nào là "tiến hoá" — vòng học 4 bước

```
  ① GHI NHẬN ─► ② CHẤM ĐIỂM ─► ③ CHƯNG CẤT ─► ④ ÁP DỤNG ─┐
  (ai_runs +     (so gợi ý với   (rút thành      (đưa vào   │
   ngữ cảnh)      kết quả thật)   "bài học")      prompt/luật)│
        ▲                                                    │
        └────────────────────────────────────────────────────┘
```

1. **Ghi nhận** — mọi gợi ý AI + hành động của người + kết quả nghiệp vụ sau đó.
2. **Chấm điểm** — gợi ý có dẫn tới kết quả tốt không (lead lên giai đoạn, deal thắng, task xong đúng hạn, dự toán sát thực tế).
3. **Chưng cất** — job định kỳ gom các trường hợp tốt/xấu, nhờ LLM viết thành *bài học* ngắn ("Khách căn hộ Vinhomes ngân sách < 300tr thường chốt khi gửi 3D trong 48h").
4. **Áp dụng** — bài học được duyệt sẽ chèn vào prompt (few-shot), hoặc chỉnh trọng số luật chấm điểm. Không fine-tune model — rẻ, minh bạch, đổi nhà cung cấp LLM vẫn giữ được tri thức.

Nguyên tắc: **con người duyệt trước khi AI "học"** (tránh học sai), **luôn có luật dự phòng** khi LLM lỗi/hết quota (giữ đúng triết lý hiện tại), **mọi bài học truy được nguồn** (từ lead/dự án nào).

---

## 3. Lộ trình theo giai đoạn

### Giai đoạn 1 — Đo được (2 tuần)
Chưa đo thì chưa thể nói là "tiến hoá".
- [ ] Bảng `ai_outcome_links`: nối `ai_runs.id` với sự kiện nghiệp vụ sau đó (lead đổi stage, deal won/lost, task done/overdue, chênh lệch dự toán – quyết toán). Ghi tự động từ các hook đã có trong `leads.py`, `projects.py`, `pl.py`.
- [ ] Mở rộng phản hồi: ngoài Đã làm/Bỏ qua thêm 👍/👎 + lý do nhanh ("không hợp khách", "sai dữ liệu", "đã biết rồi").
- [ ] Trang **/ai/hieu-qua** (admin): tỷ lệ chấp nhận gợi ý, độ chính xác lead score (điểm cao có thắng thật không), tỷ lệ LLM vs luật dự phòng, chi phí token theo tháng.
- **Đầu ra**: biết agent nào hữu ích, agent nào đang "nói cho có".

### Giai đoạn 2 — Kho tri thức công ty (3 tuần)
- [ ] Bảng `ai_lessons`: `agent`, `noi_dung`, `dieu_kien_ap_dung` (loại nhà, khu vực, ngân sách, nguồn lead), `bang_chung` (danh sách run/lead), `trang_thai` (đề xuất/đã duyệt/đã tắt), `diem_hieu_qua`.
- [ ] Job tuần `distill_lessons` (chạy trong `worker.py`): gom run có kết quả tốt/xấu → LLM đề xuất 3–5 bài học → gửi Telegram cho Trưởng phòng/BGĐ duyệt bằng nút bấm.
- [ ] Nhập tri thức sẵn có: quy trình 19 đầu việc, bảng giá, ma trận quyền, mẫu báo giá → dạng tài liệu để agent tra cứu (RAG đơn giản: pgvector trên Postgres hoặc tìm theo từ khoá trước).
- [ ] `services/ai_context.py`: hàm dùng chung chọn bài học phù hợp ngữ cảnh rồi chèn vào prompt cho mọi agent.

### Giai đoạn 3 — Agent mới phục vụ đúng nghiệp vụ nội thất (4–6 tuần)
Ưu tiên theo giá trị cho công ty:
1. **Trợ lý Báo giá / Dự toán** — từ diện tích, loại nhà, phong cách → dự toán sơ bộ; học từ chênh lệch dự toán vs quyết toán các dự án cũ để tự hiệu chỉnh đơn giá theo hạng mục. (Nối `estimations`, `quotations`, `instant_quote`, `pl`.)
2. **Giám sát tiến độ thi công** — đọc ảnh công trình gửi qua Telegram (đã có kho ảnh) + nhật ký task → cảnh báo nguy cơ trễ; học từ các dự án từng trễ để nhận diện dấu hiệu sớm.
3. **Trợ lý chăm sóc khách sau bàn giao** — dựa trên đánh giá sao trên portal, nhắc bảo hành, gợi ý bán thêm.
4. **Huấn luyện Sale** — tổng hợp cách sale giỏi chốt deal (từ ghi chú lead) thành gợi ý cho sale mới; gắn với Điểm JAMA.

### Giai đoạn 4 — Tự tối ưu (liên tục)
- [ ] **A/B prompt**: mỗi agent có 2 phiên bản prompt chạy song song, tự giữ bản có tỷ lệ chấp nhận cao hơn sau N lượt.
- [ ] **Tự chỉnh trọng số lead scoring** theo dữ liệu thắng/mất hằng tháng (hồi quy logistic đơn giản), BGĐ xem chênh lệch trước khi bật.
- [ ] **Định tuyến model theo chi phí**: việc dễ dùng model rẻ, việc khó (báo giá, phân tích) dùng model mạnh; theo dõi chất lượng từng tuyến.
- [ ] Bài học có `diem_hieu_qua` thấp liên tục thì tự đề xuất tắt.

---

## 4. Thiết kế kỹ thuật tóm tắt

**Bảng mới**
- `ai_outcome_links(id, run_id, event_type, event_ref, value, created_at)`
- `ai_lessons(id, agent, content, conditions_json, evidence_json, status, approved_by, score, created_at)`
- `ai_prompt_versions(id, agent, version, template, active, stats_json)`
- (GĐ2) `ai_documents(id, title, chunk, embedding, source)`

**Service**
- `ai_memory.py` (có sẵn) — thêm `link_outcome()`.
- `ai_context.py` (mới) — `build_context(agent, scope) → bài học + tài liệu liên quan`.
- `ai_eval.py` (mới) — tính chỉ số cho trang hiệu quả.

**Job trong `worker.py`**: `distill_lessons` (tuần), `recalibrate_scoring` (tháng), `eval_snapshot` (ngày).

**Giao diện**: `/ai/hieu-qua`, `/ai/bai-hoc` (duyệt/tắt bài học), nút 👍/👎 trên mọi thẻ gợi ý AI.

**Phân quyền**: admin/BGĐ duyệt bài học & bật trọng số mới; trưởng phòng duyệt bài học của khối mình; nhân viên chỉ phản hồi.

---

## 5. Chỉ số thành công

| Chỉ số | Mốc hiện tại | Mục tiêu sau 3 tháng |
|---|---|---|
| Tỷ lệ gợi ý Co-Pilot được "Đã làm" | đo ở GĐ1 | +20% |
| Lead điểm ≥ 70 thắng deal | đo ở GĐ1 | gấp đôi tỷ lệ lead < 40 |
| Sai lệch dự toán sơ bộ vs quyết toán | đo ở GĐ1 | < 15% |
| Dự án trễ được cảnh báo trước ≥ 7 ngày | 0 | ≥ 60% |
| Chi phí LLM / tháng | đo ở GĐ1 | không tăng quá 30% dù thêm agent |

---

## 6. Rủi ro & cách chặn

- **Học sai** (bài học dựa trên vài ca lẻ) → bắt buộc tối thiểu N bằng chứng + người duyệt.
- **Lộ dữ liệu khách** khi gửi lên LLM → ẩn SĐT/tên trước khi gửi, chỉ gửi trường cần thiết.
- **Phụ thuộc nhà cung cấp** → tri thức nằm ở DB (bài học, prompt), không nằm trong model.
- **Chi phí** → cache `input_hash` sẵn có + định tuyến model + giới hạn token theo ngày.

---

## 7. Việc làm ngay (sprint đầu)

1. Migration `ai_outcome_links` + hook ghi khi lead đổi stage / deal thắng-mất.
2. Thêm 👍/👎 + lý do vào thẻ gợi ý Co-Pilot.
3. Trang `/ai/hieu-qua` bản đầu: 4 chỉ số ở mục 5.
4. Chốt với BGĐ: thứ tự agent ở Giai đoạn 3.
