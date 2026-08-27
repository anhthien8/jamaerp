"""Backfill leads.team_id theo đội hiện tại của người phụ trách.

Phạm vi lead của trưởng nhóm đọc `leads.team_id`, mà cột này chỉ được đặt lúc
GIAO lead (`assign_lead`: lead.team_id = target_user.team_id). Đổi đội của
người sau đó thì nhãn trôi và không ai gắn lại:

  - Sale nhận data lúc chưa được xếp đội → lead mang team_id NULL. Xếp vào đội
    sau này thì trưởng nhóm KHÔNG BAO GIỜ thấy số data đó (lỗi user báo 27/08:
    «Leader chỉ xem được Lead gắn cho mình»).
  - Sale chuyển sang đội khác → lead cũ vẫn đeo nhãn đội cũ.

Từ nay `users.py` gắn lại nhãn ngay khi đổi đội (xếp thành viên / sửa hồ sơ /
tạo–đổi trưởng nhóm). Migration này dọn phần tồn đọng trước đó.

Chỉ đụng lead CÓ người phụ trách — lead chưa giao ai giữ nguyên team_id NULL
(kho chung của điều phối KD), không được vơ vào đội nào.

Revision ID: s01_2026a001
Revises: r01_2026a001
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 's01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'r01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if not {"leads", "users"} <= tables:
        return
    lead_cols = {c["name"] for c in insp.get_columns("leads")}
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "team_id" not in lead_cols or "assigned_to" not in lead_cols or "team_id" not in user_cols:
        return

    # Correlated UPDATE — chạy được trên cả SQLite (dev) lẫn Postgres (prod).
    # Ghi đè thẳng mọi lead có người phụ trách thay vì dò xem dòng nào lệch:
    # idempotent, và tránh bẫy so sánh NULL khác nhau giữa 2 hệ CSDL.
    # KHÔNG đụng updated_at (raw SQL không kích onupdate của ORM) — nếu đụng thì
    # bộ lọc «Ngày cập nhật» sẽ thấy toàn bộ lead vừa sửa hôm nay.
    bind.execute(sa.text("""
        UPDATE leads
        SET team_id = (SELECT u.team_id FROM users u WHERE u.id = leads.assigned_to)
        WHERE leads.assigned_to IS NOT NULL
          AND EXISTS (SELECT 1 FROM users u WHERE u.id = leads.assigned_to)
    """))


def downgrade() -> None:
    # Không có bản gốc để khôi phục (nhãn cũ đã sai) — cố tình để trống.
    pass
