"""Chuẩn hoá Unicode NFC cho chữ đã lưu (21/11/2026).

Đo prod 21/11 (Postgres 18.6, UTF8): leads.address 66/1229, leads.needs 63,
notifications.body 56/4162, activities.content 28/5538, leads.name 28,
notifications.title 17, users.full_name 12/70, audit_logs.after_json 2/199,
task_activities.content 2/5, project_documents.filename 1/8 đang ở dạng tổ hợp (NFD —
bộ gõ «Unicode tổ hợp») → tìm «Trịnh» không ra người tên «Trịnh». Cột JSON: 0.
Từ nay listener `before_flush` (app/chuan_hoa_unicode.py) chuẩn hoá chữ mới khi ghi;
migration này dọn phần đã lưu.

- Phản chiếu (inspector) MỌI bảng / cột kiểu chữ (varchar/text/char, trừ enum), bỏ
  `alembic_version`. Cột JSON/JSONB không phải kiểu chữ → không đụng.
- Postgres: mỗi cột 1 câu `UPDATE … SET c = normalize(c, NFC) WHERE c IS NOT NULL AND
  NOT (c IS NFC NORMALIZED) AND (NOT (c IS JSON) OR normalize(c, NFC) IS JSON)` trong
  SAVEPOINT riêng — lỗi ở một cột (vd trùng khoá unique) → ghi log rồi đi tiếp, không
  chặn khởi động. Vế `IS JSON`: cột chữ đựng JSON mà bản NFC làm hỏng JSON thì để nguyên.
- SQLite (máy dev/test): duyệt bằng Python theo khoá chính (không có thì rowid).
- SQL thô → KHÔNG kích `onupdate` của ORM: updated_at giữ nguyên (kpi_engine đếm lead
  «được cập nhật trong kỳ» theo leads.updated_at).
- Chạy lại = không đổi gì (chỉ đụng giá trị còn chưa NFC). Log số dòng sửa theo từng cột.
- Cột tên tệp (project_documents / contract_files / contract_templates /
  employee_documents .filename) chỉ để hiển thị + tên khi tải về: tệp tra theo id /
  mã Telegram, link /media/docs/{id}/{chữ ký}/{tên} không kiểm đoạn tên → chuẩn hoá an
  toàn. contract_templates.file_key là chữ đã bỏ dấu (ASCII) → không đổi.
- Khoảng giao thời (bản cũ chưa có listener còn phục vụ trong lúc migration + khởi động)
  được dọn nốt bởi `quet_lai_sau_deploy` — chạy lại đúng hàm này MỘT lần, nền, sau deploy.
- downgrade = no-op (không có bản «tổ hợp» nào cần khôi phục).

MÃ REVISION: a28_2026b007, KHÔNG phải a27_2026b006 — mã đó đã thuộc migration «hẹn tiếp
lead» (R00, leads.hen_tiep_luc) ở nhánh claude/hopeful-mcnulty-6d1860. Hai tệp cùng mã thì
Alembic chỉ cảnh báo rồi lặng lẽ giữ một → một trong hai không bao giờ chạy
(tests/test_alembic_revision.py chặn việc này). Nhánh nào vào main SAU thì sửa
down_revision của mình trỏ vào revision của nhánh kia để chuỗi vẫn một đường thẳng
(vd R00 vào sau: hen_tiep_lead.down_revision = 'a28_2026b007').
Trước khi deploy: `SELECT version_num FROM alembic_version` trên prod phải là a26_2026b005.

Revision ID: a28_2026b007
Revises: a26_2026b005
Create Date: 2026-11-21
"""
import logging
from typing import Sequence, Union

from alembic import op

# Hàm dọn dùng CHUNG với lần quét lại sau deploy (một nguồn duy nhất). alembic/env.py đã
# import app.database → gói `app` luôn import được ở đây; module này chỉ cần SQLAlchemy.
from app.chuan_hoa_unicode import chuan_hoa_csdl


revision: str = 'a28_2026b007'
down_revision: Union[str, Sequence[str], None] = 'a26_2026b005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Con của logger «alembic» (mức INFO trong alembic.ini) → hiện trong log deploy
logger = logging.getLogger("alembic.a28_chuan_hoa_nfc")


def upgrade() -> None:
    kq = chuan_hoa_csdl(op.get_bind(), logger)
    for cot, n in sorted(kq.items()):
        logger.info("[NFC] %s: chuẩn hoá %d dòng", cot, n)
    logger.info("[NFC] Xong — %d dòng-cột ở %d cột", sum(kq.values()), len(kq))


def downgrade() -> None:
    # Không có bản «tổ hợp» nào cần khôi phục — cố tình để trống.
    pass
