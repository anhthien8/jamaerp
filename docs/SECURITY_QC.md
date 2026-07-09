# 🔒 Báo cáo QC Bảo mật — JAMA HOME CRM

> Ngày rà soát: 08/07/2026 · Phạm vi: backend (FastAPI), telegram-bot, frontend (Next.js), cấu hình deploy.
> Trạng thái: các lỗ hổng Critical/High đã được vá trong lần rà soát này.

---

## Tóm tắt

| Mức độ | Phát hiện | Đã vá | Còn theo dõi |
|--------|-----------|-------|--------------|
| 🔴 Critical | 1 | 1 | 0 |
| 🟠 High | 3 | 3 | 0 |
| 🟡 Medium | 4 | 2 | 2 |
| 🟢 Đã tốt sẵn | 6 | — | — |

**Kết luận:** hệ thống có nền tảng bảo mật khá tốt (RBAC backend đầy đủ, không có SQL injection, bcrypt, rate-limit login). Lỗ hổng nghiêm trọng nhất là cơ chế đăng nhập qua Telegram — đã được vá bằng bí mật chia sẻ. Sau khi cấu hình `TELEGRAM_AUTH_SECRET` và đổi mật khẩu mặc định, hệ thống đủ an toàn để chạy production nội bộ.

---

## 🔴 CRITICAL

### C1 — `/auth/telegram` cấp JWT không cần xác thực bot  ✅ ĐÃ VÁ
**Rủi ro:** Endpoint chỉ nhận `telegram_user_id` rồi trả JWT đầy đủ quyền của nhân viên đó. Không có bằng chứng nào chứng minh người gọi thực sự là bot. Bất kỳ ai truy cập được backend (URL public trên Railway) và biết/đoán một `telegram_user_id` (số nguyên, dễ dò) đều có thể **mạo danh bất kỳ nhân viên nào**, kể cả admin — chiếm toàn quyền hệ thống.

**Cách vá:**
- Thêm biến `TELEGRAM_AUTH_SECRET` (bí mật chia sẻ bot ↔ backend).
- Backend yêu cầu header `X-Telegram-Bot-Secret` khớp (so sánh bằng `hmac.compare_digest` chống timing attack). Khi secret được cấu hình mà header sai → 401.
- Bot gửi header này trong mọi lần `authenticate`.
- Khi chưa đặt secret (deploy cũ): áp rate-limit 10 lần/phút theo `telegram_user_id` để hạn chế dò, kèm cảnh báo lúc khởi động.

**Việc cần làm khi deploy:** đặt `TELEGRAM_AUTH_SECRET` **giống nhau** ở cả backend và telegram-bot (dùng `python -c "import secrets; print(secrets.token_hex(32))"`).

---

## 🟠 HIGH

### H1 — JWT_SECRET_KEY chấp nhận giá trị placeholder yếu  ✅ ĐÃ VÁ
**Rủi ro:** Backend chỉ kiểm tra secret có tồn tại, không kiểm tra độ mạnh. Nếu ai đó deploy nguyên giá trị mẫu `change-me-to-a-random-64-char-string`, kẻ tấn công biết giá trị này (public trên GitHub) có thể **tự ký JWT giả** cho bất kỳ user/role nào.
**Cách vá:** backend từ chối khởi động nếu secret nằm trong danh sách placeholder yếu hoặc ngắn hơn 32 ký tự.

### H2 — Mật khẩu mặc định yếu, tạo user không kiểm soát  ✅ ĐÃ VÁ
**Rủi ro:** `create_user` có default password `jama2026`, không validate độ dài mật khẩu, không validate `role` (nhận `dict` thô, bỏ qua schema). Có thể tạo tài khoản mật khẩu rỗng/yếu hoặc role rác.
**Cách vá:** bắt buộc mật khẩu ≥ 8 ký tự, email hợp lệ, `role ∈ VALID_ROLES`; bỏ default password. `UserCreate` schema thêm `min_length` và `EmailStr`. `update_user` cũng validate role + độ dài mật khẩu.

### H3 — Thiếu security headers  ✅ ĐÃ VÁ
**Rủi ro:** không có `X-Frame-Options` (clickjacking), `X-Content-Type-Options` (MIME sniffing), HSTS...
**Cách vá:** thêm middleware gắn `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, và `Strict-Transport-Security` (khi HTTPS) cho mọi response.

---

## 🟡 MEDIUM

### M1 — `/auth/telegram` không có rate-limit riêng  ✅ ĐÃ VÁ
Đã thêm rate-limit theo `telegram_user_id` (fallback khi chưa đặt secret). Xem C1.

### M2 — Seed dữ liệu demo chạy cả trên production  🟡 THEO DÕI
**Rủi ro:** `seed_database` tạo 6 tài khoản mật khẩu công khai (`admin123`, `ceo123`...) mỗi lần khởi động. Trên production nếu chưa đổi, đây là cửa vào dễ nhất.
**Khuyến nghị:** đổi toàn bộ mật khẩu ngay sau deploy (đã ghi trong checklist IT). Cân nhắc: chỉ seed khi `APP_ENV != production`, hoặc buộc đổi mật khẩu lần đăng nhập đầu. *Chưa tự động hóa để tránh khóa tài khoản đang dùng.*

### M3 — `/auth/users` lộ email + telegram_user_id cho mọi user đăng nhập  🟡 THEO DÕI
**Rủi ro:** bất kỳ nhân viên nào cũng gọi được `/auth/users` và thấy email + `telegram_user_id` của toàn công ty. Sau khi vá C1, `telegram_user_id` không còn là credential nên rủi ro giảm mạnh, nhưng vẫn là rò rỉ thông tin nội bộ.
**Khuyến nghị:** trả về bản rút gọn (id + tên) cho endpoint dùng làm dropdown; giữ thông tin đầy đủ cho HR. *Chưa đổi để tránh vỡ các dropdown gán việc đang phụ thuộc field này.*

### M4 — Rate-limit login dùng IP client trực tiếp  🟡 THEO DÕI
**Rủi ro:** sau reverse proxy (Nginx/Railway), `request.client.host` là IP proxy → rate-limit thành toàn cục thay vì theo từng IP thật. Cũng là in-memory nên reset khi restart và không chia sẻ giữa nhiều instance.
**Khuyến nghị:** đọc `X-Forwarded-For` (thận trọng, chỉ tin proxy của mình) hoặc chuyển rate-limit sang Redis. *Chấp nhận được cho quy mô 100 nhân sự 1 instance.*

---

## 🟢 Những điểm đã làm tốt (giữ nguyên)

1. **RBAC backend đầy đủ** — mỗi endpoint kiểm quyền qua `get_current_user` + guard role; không tin frontend. P&L chặn non-C-level, inventory chặn non-purchasing, lead có `can_view_lead`/scope theo role.
2. **Không có SQL injection** — 100% dùng SQLAlchemy ORM tham số hóa, không có f-string/raw SQL.
3. **Không có eval/exec/pickle/os.system** — không có code thực thi động nguy hiểm.
4. **Mật khẩu bcrypt** — có salt ngẫu nhiên mỗi mật khẩu, `verify_password` đúng chuẩn.
5. **Chống privilege escalation ở update_user** — allow-list field, chỉ admin đổi `role`/`is_active`, user thường không tự nâng quyền.
6. **Google Drive OAuth an toàn** — state token 1 lần chống CSRF, secret không hiển thị lại (masked), refresh_token lưu server-side, callback không nhận lệnh từ nội dung ngoài.

---

## ✅ Checklist trước khi lên production

- [ ] Đặt `JWT_SECRET_KEY` = chuỗi ngẫu nhiên 64 ký tự (`token_hex(32)`)
- [ ] Đặt `TELEGRAM_AUTH_SECRET` **giống nhau** ở backend + telegram-bot
- [ ] Đổi toàn bộ 6 mật khẩu tài khoản seed (trang /hr)
- [ ] `CORS_ORIGINS` chỉ chứa domain thật của frontend (không dùng `*`)
- [ ] `APP_ENV=production`, `DEBUG=false`
- [ ] HTTPS bật (SSL) — setup.sh VPS đã tự cấu hình Let's Encrypt
- [ ] Không commit file `.env` (đã có trong `.gitignore`)
- [ ] Bật sao lưu tự động + kết nối Google Drive (backup ngoài server)
