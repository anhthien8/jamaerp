# Spec 09 — Zalo Listener Bot (trợ lý lắng nghe hội thoại → Telegram)

> **Ngày:** 16/07/2026 · **Người quyết:** Chủ dự án (Dương Anh Thiện) — đã có đồng thuận nội bộ, mục tiêu nâng hiệu suất & thu nhập toàn công ty.
> **Bản chất:** dùng **1 tài khoản Zalo cá nhân chuyên dụng** làm listener, add vào các nhóm nội bộ + nhóm khách của nhân viên, nghe hội thoại → phân tích AI → đẩy tín hiệu về Telegram bot đã có.

---

## 0. SỰ THẬT RỦI RO PHẢI ĐỌC TRƯỚC (không né tránh)

1. **Không có API chính thức.** Zalo chỉ có OA (chat 1-1 với khách) + Mini App. Nghe nhóm bằng tài khoản cá nhân = automation Zalo Web qua thư viện không chính thống (`zca-js` Node / `zlapi` Python). **Vi phạm điều khoản Zalo.**
2. **Tài khoản chạy bot SẼ bị khóa — sớm hay muộn.** Yếu tố kích hoạt: tài khoản mới + join nhiều nhóm dồn dập + hoạt động 24/7 + gửi tin. Thiết kế này giảm xác suất + giảm thiệt hại, KHÔNG loại bỏ được.
3. **Hệ quả nếu khóa nhằm tài khoản trong nhóm KHÁCH:** khách thấy một thành viên rời nhóm (ít ảnh hưởng nếu là account phụ vô danh) — nhưng nếu dùng nhầm account thật của nhân viên/OA công ty thì mất cả quan hệ khách. → **Bắt buộc dùng account chuyên dụng, vô danh, không phải người thật.**
4. **Pháp lý (Nghị định 13/2023 về bảo vệ dữ liệu cá nhân):** đồng thuận nhân viên là cần nhưng CHƯA đủ — trong nhóm còn dữ liệu cá nhân của KHÁCH. Giảm rủi ro bằng: mục đích rõ ràng (cải thiện dịch vụ/CSKH), tối thiểu hóa lưu trữ, không dùng cho mục đích ngoài đã nêu, không dùng để kỷ luật nhân viên.

**Kết luận thiết kế:** account chuyên dụng + **listen-only (không gửi gì vào Zalo)** + lưu TÍN HIỆU không lưu transcript thô lâu dài + có kế hoạch dự phòng khi bị khóa.

---

## 1. Nguyên tắc thiết kế (mỗi cái đều để giảm 1 rủi ro cụ thể)

| Nguyên tắc | Giảm rủi ro gì |
|---|---|
| **Account chuyên dụng, vô danh** (không phải người thật, không phải OA) | Bị khóa không mất quan hệ khách / account nhân viên |
| **LISTEN-ONLY** — bot KHÔNG bao giờ gửi tin vào nhóm Zalo, mọi output ra Telegram/web | Spam-detection chủ yếu bắt hành vi GỬI → không gửi thì bề mặt bị khóa nhỏ đi nhiều, đồng thời khách không thấy bot |
| **Account có tuổi + join nhóm từ từ** (không add 50 nhóm/ngày) | Tránh cờ "tài khoản mới hoạt động bất thường" |
| **1 thiết bị/IP cố định tại VN** (VPS VN hoặc máy tại văn phòng) | Tránh cờ đăng nhập lạ |
| **Lưu TÍN HIỆU, không lưu transcript** (raw giữ ≤7 ngày rồi xóa) | Giảm phơi nhiễm pháp lý + dung lượng |
| **Kế hoạch dự phòng account #2 + giám sát phiên** | Khóa không làm gián đoạn dài |

---

## 2. Kiến trúc

```
[Tài khoản Zalo chuyên dụng] — zca-js listener trên VPS VN (giữ session QR)
      │  nhận message các nhóm (nội bộ + khách)  — CHỈ ĐỌC
      ▼
[Zalo Ingest Service]  (process Node/Python riêng, KHÔNG chung process backend chính
                        để nếu Zalo lib crash không kéo sập ERP)
      │  chuẩn hóa {group_id, group_name, sender, text, ts, media_ref}
      │  POST /zalo/ingest  (header bí mật chia sẻ, giống pattern TELEGRAM_AUTH_SECRET)
      ▼
[Backend JAMA — module zalo]
      │  1. lưu ZaloMessage (retention ngắn) HOẶC bỏ qua lưu, chỉ phân tích
      │  2. Analysis pipeline (tái dùng services/llm_config — Groq/Gemini + fallback rule-based):
      │       • lead detection (SĐT + ý định)      • commitment/deadline
      │       • quote-request                        • unanswered-customer
      │       • deal-risk sentiment
      │  3. lưu ZaloSignal (có cấu trúc)
      ▼
[Telegram bot đã có]  → đẩy tín hiệu cho sale/leader phụ trách (chat riêng)
[Web dashboard]       → khối văn phòng xem tổng hợp (designer/thu mua/kế toán/GĐ)
```

**Vì sao tách Ingest Service khỏi backend chính:** thư viện Zalo lậu hay vỡ/khởi động lại — cô lập để không ảnh hưởng ERP đang phục vụ 100+ người.

---

## 3. Data model (module `zalo`)

```python
# models/zalo.py
class ZaloGroup(Base):            # nhóm được theo dõi
    id, zalo_group_id (unique), name
    kind: str   # internal | customer
    assigned_team_id / assigned_user_id   # ai phụ trách nhóm này
    monitoring: bool = True
    consent_ref: str | None       # link/ghi chú đồng thuận

class ZaloMessage(Base):          # raw — RETENTION NGẮN (job xóa >7 ngày)
    id, group_id (FK), sender_zalo_id, sender_name
    text: Text, media_ref: str | None
    created_at
    # KHÔNG index full-text, KHÔNG giữ vĩnh viễn — chỉ đệm để phân tích + truy vết ngắn hạn

class ZaloSignal(Base):           # OUTPUT có giá trị — giữ lâu
    id, group_id (FK), source_msg_id | None
    type: str   # lead_candidate | commitment | quote_request | unanswered | deal_risk | faq
    summary: str(500)
    payload_json: Text            # {phone, intent, deadline, ...}
    status: str   # new | actioned | dismissed
    assigned_user_id | None
    created_at, resolved_at
```

Nguyên tắc dữ liệu: **ZaloSignal là tài sản, ZaloMessage là rác tạm.** Ưu tiên trích tín hiệu rồi xóa thô.

---

## 4. Tính năng tạo giá trị (cái này mới là lý do làm)

| # | Tính năng | Mô tả | Đẩy đi đâu |
|---|---|---|---|
| 1 | **Ra-đa Lead** | Phát hiện SĐT + ý định mua trong bất kỳ nhóm nào → tạo lead nháp (chống trùng với lead đã có) | Telegram cho sale phụ trách nhóm → duyệt 1 chạm |
| 2 | **Theo dõi cam kết** | "gửi báo giá thứ 5", "hẹn khảo sát 20/7" → tạo nhắc việc + SLA | Telegram + trang việc cá nhân |
| 3 | **Cảnh báo khách chờ** | Khách hỏi mà không ai trả lời trong X giờ → nhắc sale, quá lâu → escalate leader | Telegram (quan trọng nhất cho chốt deal) |
| 4 | **Bắt yêu cầu báo giá** | Khách hỏi giá → gợi ý sale dùng /quote-tool + link | Telegram |
| 5 | **Cảnh báo deal rủi ro** | Khách tỏ ý không hài lòng / im lặng dài → báo leader | Telegram cho leader |
| 6 | **Tổng hợp nhóm cuối ngày** | Digest mỗi nhóm: có gì mới, việc cần theo dõi | Web (khối văn phòng) + Telegram |
| 7 | **Gợi ý FAQ** | Câu hỏi khách lặp lại nhiều → đề xuất mẫu trả lời chuẩn | Web (marketing/CSKH) |

Tất cả bám đúng chiến lược **Telegram-first**: Zalo là nơi NGHE, Telegram là nơi HÀNH ĐỘNG.

---

## 5. Đồng thuận & Quyền riêng tư (dựng đúng dù đã có đồng thuận)

1. **Sổ đồng thuận:** nhân viên ký xác nhận; nhóm khách có thông báo ghim + cơ sở "mục đích kinh doanh, cải thiện dịch vụ".
2. **Tối thiểu hóa:** lưu ZaloSignal, KHÔNG lưu transcript thô quá 7 ngày (job đêm xóa).
3. **Giới hạn mục đích:** dữ liệu CHỈ dùng nâng hiệu suất/CSKH — **không dùng để kỷ luật/giám sát nhân viên** (giữ đúng tinh thần chính sách chống burnout: dữ liệu để hỗ trợ, không để phạt). Ghi rõ trong chính sách.
4. **Phân quyền tín hiệu:** signal của nhóm nào chỉ sale/leader phụ trách + admin thấy — không phải cả công ty.
5. **Loại trừ nội dung riêng tư:** pipeline bỏ qua chuyện phiếm cá nhân, chỉ trích tín hiệu công việc.

---

## 6. Lộ trình triển khai (de-risk từng bước — KHÔNG làm ồ ạt)

| Phase | Làm gì | Điều kiện qua phase sau |
|---|---|---|
| **P0 — Chứng minh sống sót** | 1 account chuyên dụng, **1 nhóm nội bộ duy nhất**, listen-only, 2 tuần | Account không bị khóa, session ổn định |
| **P1 — Nội bộ** | Mở tất cả nhóm NỘI BỘ (rủi ro thấp, không đụng khách) | Tính năng 1-3 chạy đúng, ít nhiễu |
| **P2 — Nhóm khách** | Mở dần nhóm khách (**rủi ro cao nhất**), có account #2 dự phòng | — |
| **KHÔNG BAO GIỜ** | Bot gửi tin vào nhóm khách | Giữ bot vô hình với khách |

**Giám sát + dự phòng:** theo dõi sức khỏe phiên Zalo → mất phiên báo Telegram admin ngay; sẵn account #2 để thay; nếu bị khóa giữa chừng, phía JAMA **không mất dữ liệu** (signal đã lưu ở backend).

---

## 7. Ước lượng & phụ thuộc

- **Ingest Service** (zca-js Node hoặc zlapi Python): ~2-3 ngày dựng + giữ session QR ổn định (phần khó nhất là session sống lâu).
- **Backend module zalo** (models + ingest endpoint + analysis worker tái dùng llm_config): ~3-4 ngày.
- **Surfacing Telegram + web dashboard**: ~2-3 ngày.
- **VPS VN** (IP Việt Nam, chạy 24/7 cho listener) — chi phí vận hành.
- Rủi ro lịch: thư viện Zalo có thể vỡ bất kỳ lúc nào Zalo cập nhật → cần người trực bảo trì.

## 8. Khuyến nghị thẳng của kỹ thuật (chủ dự án quyết)

- **Nên làm:** P0 + P1 (nhóm nội bộ, listen-only) — giá trị cao (ra-đa lead, cam kết, cảnh báo khách chờ), rủi ro thấp vì không đụng khách, account phụ khóa cũng không sao.
- **Cân nhắc kỹ:** P2 (nhóm khách) — giá trị lớn nhất nhưng rủi ro cao nhất; chỉ mở sau khi account chứng minh sống ≥1 tháng + có dự phòng.
- **Song song (an toàn tuyệt đối, nên làm bất kể):** mở **Zalo OA chính thức** cho luồng khách nhắn trực tiếp công ty → webhook hợp lệ → auto-lead + ZNS nhắc hẹn. Cái này KHÔNG rủi ro khóa và bổ trợ cho listener bot.
