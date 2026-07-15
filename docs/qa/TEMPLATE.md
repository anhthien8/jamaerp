# QA Report — <version/ngày>

> Quy trình: `docs/specs/06-qa-per-role-process.md`. Copy file này thành `QA-<version>.md` cho mỗi version.

**Changelog kiểm:** <link entry Nhật ký phát triển>
**Người/agent chạy:** <tên phiên/model>
**Ngày chạy:** <ngày>

## L1 — Automated
- pytest: <n> passed / <n> failed
- `tsc --noEmit`: <clean/lỗi>
- RBAC matrix (`tests/test_rbac_matrix.py`): <n> case pass
- Load test (nếu version đụng hiệu năng — spec 05 §8): <kết quả/không áp dụng>

## L2 — Per-role walkthrough (10 surface)

| Surface | Pass | Fail | Ghi chú |
|---|---|---|---|
| admin | | | |
| executive | | | |
| leader | | | |
| data_entry (sales) | | | |
| designer | | | |
| pm | | | |
| accountant | | | |
| purchasing | | | |
| Telegram bot | | | |
| Mobile 390px | | | |

## L3 — Bất biến hệ thống (6/6 phải pass)

| # | Bất biến | Kết quả |
|---|---|---|
| 1 | Không số liệu tài chính/lương trong nhóm Telegram | |
| 2 | Kỳ lương khóa từ chối mọi sửa công/hoa hồng (409) | |
| 3 | User inactive không đăng nhập được | |
| 4 | Demo mode không gọi API thật | |
| 5 | Thao tác nhạy cảm sinh AuditLog | |
| 6 | Không nhãn UI tiếng Anh mới ngoài Bảng thuật ngữ (§20 HUONG_DAN) | |

## Findings

| # | Severity | Role/Surface | Mô tả | Bằng chứng | Trạng thái |
|---|---|---|---|---|---|
| 1 | | | | | |

## Verdict: **RELEASE / BLOCK** — <lý do>
