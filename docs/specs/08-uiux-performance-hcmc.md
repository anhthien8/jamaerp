# Đề xuất Performance + UI/UX theo hành vi nhân viên TP.HCM

> **Ngày:** 16/07/2026 · **Cơ sở:** rà một vòng codebase thực tế (19 trang frontend, sidebar 18 mục, poll 60s, GuidedTour/FAB/mobile-KISS vừa làm) + mô hình hành vi nhân viên HCM bên dưới.
> **Executor:** bất kỳ phiên AI nào. Mỗi mục có độ ưu tiên P0 (làm ngay) / P1 (quý này) / P2 (sau).

---

## 0. Mô hình hành vi nhân viên HCM (giả định làm việc — chủ dự án xác nhận/chỉnh)

| # | Hành vi | Hệ quả thiết kế |
|---|---|---|
| H1 | Ngoài văn phòng, **điện thoại Android tầm trung là thiết bị chính** (laptop chỉ ở bàn) | Mobile không phải "hỗ trợ" mà là **kênh chính** của sales/GS/PM |
| H2 | **4G chập chờn** khi chạy xe giữa các quận, hầm gửi xe, công trình bê tông | Thao tác ghi (checkin, ghi chú) phải chịu được mất mạng tạm |
| H3 | **Zalo là kênh khách hàng số 1** — chốt deal, gửi báo giá, nhận ảnh đều qua Zalo | Mọi luồng "từ Zalo vào hệ thống" và "từ hệ thống ra Zalo" phải ≤2 chạm |
| H4 | Cao điểm: **7h45–8h15 checkin đồng loạt**; nghỉ trưa 11h30–13h (ít thao tác); kế toán dồn **mùng 1–5** | Chịu tải burst sáng; job nặng tránh giờ sáng; UX kế toán tối ưu cho "mùa cao điểm" |
| H5 | Giám sát công trường: **ngoài nắng gắt, thao tác 1 tay**, tay bụi/ướt | Nút to đáy màn hình, chữ tương phản cao, tối thiểu gõ phím |
| H6 | Nhân viên **ít đọc hướng dẫn, thích được nhắc việc** qua thông báo | Đẩy việc đến người (notification/bot) thay vì chờ người mở trang |
| H7 | Sếp/BQT xem **điện thoại buổi tối**, muốn tóm tắt 30 giây | Briefing Telegram (đã có) là kênh chính của sếp — web là phụ |
| H8 | Gõ tiếng Việt có dấu chậm trên điện thoại | Ưu tiên chọn/bấm thay vì gõ; ghi chú nhanh có mẫu câu sẵn |

## 1. Đề xuất PERFORMANCE (nối tiếp spec 05, thêm góc "mạng HCM")

### P0
1. **Checkin chịu mất mạng (H2, H4)** — quan trọng nhất: nhân viên bấm "Vào ca" trong hầm xe/thang máy mà request rớt là mất công. Frontend: nếu POST /attendance/checkin lỗi mạng → lưu vào localStorage queue + toast "Sẽ tự gửi lại khi có mạng" → retry khi `online` event/mở lại app. Backend đã idempotent (1 record/ngày) nên retry an toàn. ~½ ngày.
2. **Tạm dừng poll khi tab ẩn** — `NotificationCenter` poll 60s kể cả khi tab nằm nền cả ngày (200 user × ngày dài = hàng trăm nghìn request vô ích + tốn pin 4G). Dùng `document.visibilitychange`: ẩn thì dừng, hiện lại thì fetch ngay. ~1 giờ. (Kèm endpoint `unread-count` nhẹ — đã có trong spec 05 §4.)
3. **Route chính theo role tải trước** — sau login, `router.prefetch()` trang chính của role (sales→/leads, GS/PM→/projects...) để cú bấm đầu tiên trên 4G không chờ. ~1 giờ.

### P1
4. **PWA tối thiểu** — manifest + icon để "Thêm vào màn hình chính": nhân viên HCM quen mở app từ homescreen như Zalo, không gõ URL. KHÔNG làm service-worker cache phức tạp (KISS) — chỉ manifest + splash. ~½ ngày.
5. **Đo bundle trang /leads và /projects** (2 trang nặng nhất, mỗi trang >1.400 dòng) — `next build` xem First Load JS; nếu >250KB: tách modal chi tiết thành `dynamic import` (chỉ tải khi click thẻ). Trên 4G yếu khác biệt rõ.
6. **Ảnh khảo sát/công trình nén phía client trước khi gửi** (H2): canvas resize về ≤1600px/JPEG 0.8 trước khi upload/gửi bot — 4G yếu gửi ảnh 12MP gốc rất hay đứt giữa chừng. (Khớp Track A spec 05 — ảnh đi nhóm Telegram thì Telegram tự nén, luồng web docs mới cần.)
7. **Job nặng né giờ cao điểm sáng** (H4): `kpi_snapshot`, retention... đặt 5h-6h sáng hoặc 22h — KHÔNG đặt 8h (đụng burst checkin). Rà `worker.py` khi thêm job mới.

### P2
8. Light-touch APM: log JSON + p95 (spec 05 Track F) trước, đừng mua APM sớm.
9. HTTP caching tĩnh: font/icon local + `Cache-Control` dài cho asset (Vercel tự lo phần lớn — chỉ kiểm không dùng font CDN nước ngoài chậm ở VN).

## 2. Đề xuất UI/UX THEO TỪNG ROLE

### 2.1 Sales (`data_entry`) — sống trên yên xe, khách trên Zalo (H1,H2,H3,H8)
- **P0 — Nút gọi = tel: link thật**: thẻ lead có icon 📞 — đảm bảo là `<a href="tel:...">` (bấm là gọi luôn, không phải copy số). Kiểm + sửa ở `leads/page.tsx` card & modal.
- **P0 — "Ghi chú nhanh 1 chạm" sau cuộc gọi (H8)**: trong modal lead, thêm 4 chip bấm sẵn: `Không nghe máy` / `Hẹn gọi lại` / `Đã gửi báo giá` / `Hẹn khảo sát` → tạo activity không cần gõ. Giảm 80% lý do sales lười ghi chú → SLA thật lên.
- **P1 — Paste Zalo ở web**: ô "＋ Thêm Lead" thêm tab "Dán tin nhắn Zalo" gọi `/ai/parse-lead` (bot đã có, web chưa) — sales ngồi VP không phải chuyển qua Telegram.
- **P1 — Deep-link từ briefing bot**: dòng "⚠️ Chị Lan — 3 ngày chưa liên hệ" kèm link mở thẳng lead trên web/app.

### 2.2 Giám sát/PM công trường (H5,H2)
- **P0 — Chế độ tương phản cao ngoài trời**: theme hiện tại nền tối chữ vàng nhạt — ngoài nắng HCM gần như không đọc được. Thêm toggle "☀️ Ngoài trời" (Cài đặt + nút nhanh ở /projects): nền trắng, chữ đen đậm, nút to hơn 20%. CSS variables đã sẵn — chỉ thêm 1 bộ biến `[data-theme=outdoor]`.
- **P0 — Hàng nút to đáy màn hình ở chi tiết dự án (mobile)**: 3 hành động GS dùng 90% thời gian: `📷 Báo cáo` / `📦 Vật tư` / `✅ Xong việc` — thanh cố định đáy (1 tay với tới), thay vì tìm nút rải rác.
- **P1 — Nhắc tan ca thông minh (H6)**: 17h45 nếu đã vào ca mà chưa tan ca → bot nhắn "Bấm /checkout trước khi về nhé" — giảm hẳn ca auto-close ⚠️ mà kế toán phải rà.

### 2.3 Kế toán (H4, mùa cao điểm mùng 1–5)
- **P0 — "Chế độ chốt sổ"**: 1 màn hình gom đúng trình tự việc mùng 1: [rà ca ⚠️] → [duyệt OT tồn] → [sinh bảng lương] → [trình duyệt] — hiện đang phải nhảy 3 trang. Làm dạng stepper trên /attendance hoặc /hr, tái dùng API sẵn có, không backend mới.
- **P1 — Phím tắt nhập giao dịch**: kế toán quen Excel — form "+ Giao dịch mới" cho Enter để lưu-và-nhập-tiếp (không đóng modal), focus tự về ô số tiền.
- **P1 — Số tiền gõ tắt**: ô tiền hiểu `5tr` `1.2ty` `500k` → tự đổi số (một hàm parse nhỏ, dùng chung).

### 2.4 Leader (5 team sales)
- **P0 — Sáng thứ 2 một màn hình**: khối "Team tuần này" trên Tổng quan leader: 3 số (lead quá hạn của team / đơn chờ duyệt / OT chờ) + 1 nút đi thẳng từng mục. Leader HCM họp sáng thứ 2 — mở 1 trang là điều hành được cuộc họp.
- **P1 — Duyệt hàng loạt**: chọn nhiều đơn phép/OT cùng lúc ở /approvals (spec 02 §6 đã ghi — chưa làm).

### 2.5 Sếp/BQT (H7)
- **P0 — Không thêm gì trên web** — kênh của sếp là Telegram briefing (đã chạy). Chỉ bổ sung: cuối briefing thêm 1 dòng deep-link "Mở P&L đầy đủ →".
- **P2 — /kpi cho executive**: bảng xếp hạng team dạng đọc-nhanh-buổi-tối (chữ to, 5 dòng).

### 2.6 Designer & Thu mua
- **P1 (designer)** — khối "Dự án đang đến phòng bạn" (đã có) thêm badge số việc mới từ lần xem trước (localStorage last-seen) — designer mở app 2-3 lần/ngày, cần biết "có gì mới" ngay.
- **P1 (thu mua)** — /inventory mobile: ô tìm vật tư đặt trên cùng + quét gần đây; thao tác duyệt yêu cầu giữ trên Telegram (đúng thói quen hiện tại, đừng kéo về web).

### 2.7 Chung mọi role
- **P0 — Sidebar quá dài (18 mục)**: mobile "Xem thêm (9–11)" chôn mất trang quan trọng. Quy tắc: mỗi role tối đa **5 mục chính + Xem thêm**; rà lại `ROLE_ESSENTIALS` theo tần suất thật (sales không cần thấy Hợp đồng hằng ngày). ~1 giờ, tác động lớn.
- **P1 — Giờ hiển thị**: mọi giờ hiển thị phải là giờ VN (backend trả UTC — kiểm các chỗ `slice(11,16)` ở /attendance đang cắt chuỗi UTC → **sai giờ hiển thị vào/ra**, cần convert trước khi cắt). ⚠️ Đây là bug thật, ưu tiên kiểm đầu tiên.

## 3. Thứ tự thực thi đề xuất (executor)

| Đợt | Mục | Ước lượng |
|---|---|---|
| 1 (P0-bug) | 2.7 giờ VN ở /attendance (kiểm + fix) | ½ ngày |
| 2 (P0) | 1.1 checkin offline-queue · 1.2 poll visibility · 2.1 tel:+chip ghi chú nhanh · 2.7 sidebar 5 mục/role | 2 ngày |
| 3 (P0) | 2.2 theme ngoài trời + thanh nút đáy · 2.3 chế độ chốt sổ · 2.4 khối leader thứ 2 | 2-3 ngày |
| 4 (P1) | 1.3-1.7 + các P1 role | 1 tuần rải |

Mỗi đợt xong: pytest + tsc + QA per-role (spec 06) + Obsidian. Giả định hành vi H1–H8 sai ở đâu, chủ dự án sửa ở mục 0 — đề xuất bám theo đó tự điều chỉnh.
