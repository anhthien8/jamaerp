# Spec — Chịu tải hệ thống: 200 nhân sự, 2 năm dữ liệu

> **Executor:** Bất kỳ phiên AI nào (dự kiến Opus 4.8). Spec tự chứa.
> **Ngày:** 15/07/2026. **Hiện trạng đã có:** Postgres + asyncpg + timestamp codec, Alembic + auto-migrate lúc boot, pool_size 20/max_overflow 10 + pool_pre_ping (`database.py`), 12 composite indexes, pagination 10 endpoints, in-memory cache TTL (`app/cache.py`), worker asyncio, backup SQLite→Drive (PG đang **skip**), security headers + rate-limit public quote 5/h/IP.

---

## §1. Dự phóng dung lượng 2 năm @ 200 nhân sự

| Bảng | Ước tính 2 năm | Cơ sở tính |
|---|---|---|
| attendance_records | ~125k | 200 người × 26 ngày × 24 tháng |
| activities (lead notes) | ~600k | 10k leads/năm × ~30 touch |
| audit_logs | ~500k–1M | mọi thao tác nhạy cảm + duyệt |
| notifications | ~1M | nhắc CSKH + duyệt + briefing/người |
| task_activities (**RỦI RO #1**) | ~200k rows nhưng **GB-scale** | ảnh công trình hiện nhận cả **base64 vào DB** (`telegram_workflow.py::SiteReportRequest.photos`) |
| leads / payrolls / approvals | 20k / 4.8k / 50k | nhỏ, không đáng ngại |

**Kết luận:** Postgres xử lý thoải mái về ROWS. Ba nguy cơ thật: (1) media base64 trong DB, (2) các endpoint N+1/không phân trang, (3) vận hành (backup PG chưa có, chưa observability, worker không có lock).

## §2. Track A — Ảnh công trình lưu trên NHÓM TELEGRAM (quyết định của chủ dự án 15/07/2026)

> **Thiết kế chốt:** ảnh hiện trường NẶNG → dùng nhóm Telegram công ty làm kho lưu trữ vĩnh viễn (Telegram tự backup, miễn phí). DB **chỉ lưu link message**. Web hiện nút "📷 Xem ảnh công trình" → mở thẳng link Telegram của tin nhắn trong nhóm.

### Luồng chuẩn

1. **Qua bot (`/baocao`, `/suco`, ghi chú task kèm ảnh):** nhân viên gửi ảnh cho bot như hiện tại → bot **đăng ảnh vào nhóm Telegram công ty** (`telegram_group_chat_id` đã có trong SystemSetting) với caption chuẩn: `📷 #<MÃ_DỰ_ÁN> · <tên đầu việc> · <người gửi> · <ngày>` → lấy `message_id` từ response → ghi vào DB link dạng `https://t.me/c/<internal_id>/<message_id>` (internal_id = chat_id bỏ tiền tố `-100`).
2. **Đăng thẳng vào nhóm:** nhân viên post ảnh vào nhóm kèm caption chứa `#JMH-xxx` → bot (đã là admin nhóm) bắt message có photo + hashtag mã dự án → tự tạo TaskActivity với link message đó + reply xác nhận "✅ Đã lưu vào dự án JMH-xxx".
3. **Web:** `TaskActivity.media_url` là link `t.me/c/...` → UI hiện nút "📷 Xem ảnh (Telegram)" mở tab mới. Chỉ thành viên nhóm mở được — đúng ý bảo mật nội bộ.
4. **File upload qua WEB — phân loại theo bản chất (feedback chủ dự án 15/07):**
   - Đa số là **sao kê, hợp đồng, bản vẽ** — dung lượng NHỎ và **nhạy cảm tài chính** → giữ luồng web hiện tại, lưu server (`backend/media/docs/`, serve qua endpoint có auth), **TUYỆT ĐỐI KHÔNG đăng lên nhóm Telegram** (nguyên tắc "tài chính không vào nhóm chung" áp dụng cho cả file).
   - Chỉ **ảnh hiện trường** (nặng, không nhạy cảm) mới đi luồng nhóm Telegram ở trên.
   - **CẤM base64 vào DB** áp dụng cho CẢ HAI luồng — validator reject payload photos/media_url là chuỗi base64 (>10KB không phải URL).
   - Backup: thư mục `backend/media/docs/` đưa vào backup service (nhỏ nên không đáng kể); ảnh Telegram theo chính sách export nhóm.

### Việc cần làm

- Bot: hàm `post_photos_to_group(project_code, photos, caption)` (sendPhoto/sendMediaGroup tới group chat id) + handler bắt photo+hashtag trong nhóm (lưu ý Privacy Mode đang Enabled — bot chỉ đọc lệnh `/`; hashtag caption không phải command → cần chuyển flow 2 (đăng thẳng) thành reply `/anh JMH-001` vào media message, HOẶC hạ Privacy Mode có chủ đích + ghi rõ vào [[Bảo mật]]. Executor chọn phương án reply-command để giữ Privacy Mode).
- Backend: `SiteReportRequest.photos` đổi ngữ nghĩa thành `photo_links` (link Telegram); validator chặn base64; TaskActivity.media_url giữ nguyên cột.
- Script `scripts/migrate_media.py` (một lần): quét base64 còn trong DB → đăng lên nhóm qua bot → thay bằng link (idempotent, batch, log dung lượng giải phóng).
- Fallback khi nhóm chưa cấu hình: từ chối kèm hướng dẫn admin bật nhóm (không âm thầm nhét base64 lại).

### Trade-off chấp nhận (ghi để đời sau khỏi cãi)

- Ảnh phụ thuộc Telegram (mất nhóm = mất ảnh) → backup nhóm là chính sách vận hành: nhóm KHÔNG được xóa; admin export chat định kỳ 6 tháng (Telegram Desktop → Export) — ghi vào checklist vận hành.
- Link `t.me/c/` chỉ mở được bởi thành viên nhóm — nhân viên nghỉ việc bị remove khỏi nhóm sẽ mất quyền xem (đúng mong muốn offboarding).

## §3. Track B — N+1 & pagination (đã xác định vị trí cụ thể)

| Vị trí | Vấn đề | Fix |
|---|---|---|
| `api/attendance.py::team_attendance` | loop `month_summary()` **mỗi user** = 200 queries | 1 aggregate: `SELECT user_id, SUM(...), COUNT(...) FROM attendance_records WHERE work_date BETWEEN ... GROUP BY user_id` + pagination `page_size=50` |
| `api/payroll.py::generate_period` → `build_payroll_row` | mỗi user 3-4 queries (summary/commission/advances) = ~800 queries/kỳ | prefetch 3 aggregate GROUP BY user_id trước vòng lặp, truyền dict vào build_row (giữ chữ ký hàm cho test) |
| `api/approvals.py::pending_for_me` | loop `db.get(User)` per delegator + per requester | join sẵn requester name; delegators bằng 1 query có điều kiện `delegate_until >= now` |
| `api/hr.py::resign_preview` | `db.get(Project)` per task | join Task→Project |
| `api/attendance.py::pending_ot` | `db.get(User)` per record + lọc team bằng Python | join User + filter team trong SQL |
| `services/approval_engine.py::escalate_overdue` | quét toàn bộ pending rồi lọc Python | thêm `WHERE due_at < :now` |
| Chuẩn chung | endpoint list mới phải có `page/page_size` (trần 200) | thêm test guard: mọi router mới trả `items` phải kèm `total/page` |

## §4. Track C — Cache Redis + invalidation

1. `docker-compose` đã có Redis; thêm `redis>=5` client, `REDIS_URL` (đã có trong config). `app/cache.py` giữ interface hiện tại, thêm driver Redis (fallback in-memory khi không có REDIS_URL — dev không cần Redis).
2. Cache TTL 60-120s cho read nặng: `/dashboard/*`, `/leads/pipeline/stats`, `/reports`, `/pl/summary`, `/kpi/leaderboard`. Key kèm role+scope (leader team X ≠ admin).
3. Invalidation: sự kiện ghi lead/transaction → `cache.delete_prefix('dashboard')` (đơn giản, đủ dùng — không làm event bus).
4. Notification poll 60s × 200 user = ~3.3 req/s — chấp nhận được, nhưng thêm endpoint `GET /notifications/unread-count` siêu nhẹ (1 COUNT, cache 30s) để sidebar poll thay vì full list.

## §5. Track D — Worker an toàn khi scale

1. **Postgres advisory lock** (`pg_advisory_lock(42)`) khi worker start job batch — chạy 2 replica không double-send briefing/payslip. SQLite: bỏ qua lock (dev 1 process).
2. Payslip/briefing gửi Telegram: thêm throttle 20 msg/s + retry 429 (Telegram limit 30/s) — 200 tin ~10s, an toàn.
3. Job nặng (kpi_snapshot, BOD) đo thời gian chạy, log warning nếu >60s.

## §6. Track E — Data lifecycle & backup PG

1. **Retention job** (worker, 2:00 Chủ nhật): notifications đã đọc >90 ngày → xóa; audit_logs >12 tháng → chuyển `audit_logs_archive` (cùng schema); deferred/resolved approvals >12 tháng giữ nguyên (nhỏ).
2. **Backup Postgres:** `backup_service.py` hiện skip PG — implement `pg_dump -Fc` (binary custom format) → zip → local + Google Drive (tái dùng OAuth flow có sẵn), retention như SQLite. Railway: chạy trong worker container (cần `postgresql-client` trong Dockerfile backend).
3. **Restore drill** ghi thành script `scripts/restore_check.py`: tải bản backup mới nhất → restore vào DB tạm → đếm bảng + smoke SELECT — chạy tay mỗi quý (ghi vào checklist vận hành).
4. RPO/RTO mục tiêu: RPO 24h (daily dump; nâng cấp sau bằng Railway PITR nếu có), RTO 1h (restore script + redeploy).

## §7. Track F — Observability

1. **Structured logging:** middleware log JSON 1 dòng/request (method, path, status, duration_ms, user_id) — bật khi `LOG_FORMAT=json`.
2. **Slow query:** Postgres `log_min_duration_statement=500ms` (Railway setting) + SQLAlchemy `echo_pool` off; thêm event ghi warning query >1s ở engine.
3. **Error tracking:** Sentry SDK (env `SENTRY_DSN`, no-op khi trống) cho backend + frontend + bot.
4. **Metrics tối thiểu:** endpoint `GET /metrics-lite` (admin): p95 latency 15 phút gần nhất (ring buffer in-memory), queue depth worker (đã có `get_health`), DB pool checked-out.
5. Uptime: dùng healthcheck Railway có sẵn + cron ping ngoài (UptimeRobot free) — ghi vào docs vận hành.

## §8. Track G — Load test (định nghĩa "đạt")

Kịch bản k6/locust (`backend/loadtest/`) chạy trên staging Postgres:

| Kịch bản | Mô phỏng | Ngưỡng đạt |
|---|---|---|
| **Sáng thứ Hai** | 200 user checkin trong 5 phút + 50 user mở dashboard | p95 < 500ms, 0 lỗi 5xx, 0 deadlock |
| **Giờ làm việc** | 60 phút: 40 sales CRUD leads/activities (2 req/s tổng), 10 leader reports, poll notifications nền 200 user | p95 < 700ms, RAM backend < 1GB |
| **Chốt lương** | generate payroll 200 user + 200 payslip | generate < 30s, gửi xong < 60s |
| **Soak** | kịch bản giờ làm × 4h | không rò rỉ RAM (chênh <10%), pool không cạn |

Chạy trước/sau Track B-C để chứng minh cải thiện — lưu kết quả vào `docs/loadtest-results.md`.

## §9. Track H — Bảo mật ở quy mô 200 (bổ sung, không trùng SECURITY_QC)

1. Rate-limit global bằng `slowapi`: `/auth/login` 10/phút/IP (chống brute-force khi 200 tài khoản là bề mặt lớn), API chung 120/phút/user.
2. Account lockout mềm: 5 lần sai → khóa 15 phút (bảng đếm trong cache/Redis).
3. TOTP 2FA cho role admin/accountant (pyotp, QR khi bật trong Settings) — **phase sau cùng**, chỉ khi các track trên xong.

## §10. Thứ tự thực thi + Definition of Done

```
A (media)  →  B (N+1/pagination)  →  E2 (backup PG)  →  C (Redis)  →  D (worker lock)
→ F (observability) → G (load test chứng minh) → E1 (retention) → H (security)
```

DoD toàn spec: 183+ tests xanh (thêm tests cho media/migration/N+1 aggregate đúng số với bản loop cũ), tsc clean, load test 4 kịch bản đạt ngưỡng trên staging Postgres, restore drill pass, QA per-role theo `docs/specs/06`.

## §11. Hướng dẫn thực thi (cho Opus 4.8)

1. Mỗi Track = 1 nhánh việc độc lập, làm tuần tự theo §10; sau MỖI track chạy full pytest + ghi Obsidian (memory `feedback_obsidian_notes`).
2. Track B: trước khi refactor, viết test khóa hành vi (kết quả aggregate == kết quả loop cũ trên fixture 5 user) rồi mới đổi — tránh lệch số liệu lương/công.
3. Track A script migration: BẮT BUỘC backup trước (`backup_service.run_backup`), chạy batch, in tổng dung lượng giải phóng.
4. Không đổi schema ngoài: `audit_logs_archive`, cột nếu cần cho media URL (đa số đã là Text). Mọi thay đổi schema qua Alembic revision mới trên head hiện tại.
5. Load test cần server staging: dùng docker-compose (đã có postgres+redis) — không bắn vào production Railway.
