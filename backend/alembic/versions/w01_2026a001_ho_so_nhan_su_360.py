"""Hồ sơ nhân sự 360°: employee_profiles + employee_documents + handover_records
+ cột đối chiếu văn phòng và vết duyệt OT trên attendance_records.

Yêu cầu 09/09/2026: quản lý profile/HĐLĐ/CCCD, click nhân viên thấy toàn bộ
giao dịch (kể cả sau bàn giao nghỉ việc), check-in đối chiếu GPS + IP văn phòng,
trưởng nhóm KD duyệt OT (hiển thị ai duyệt/lúc nào).

Phòng thủ kiểu o01→t01: kiểm tra tồn tại trước khi tạo/thêm — chạy lại an toàn
trên cả dev SQLite (create_all tạo sẵn) lẫn prod Postgres.

Revision ID: w01_2026a001
Revises: v01_2026a001
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'w01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'v01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "employee_profiles" not in tables:
        op.create_table(
            "employee_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("national_id", sa.String(20), nullable=True),
            sa.Column("national_id_issued_date", sa.Date(), nullable=True),
            sa.Column("national_id_issued_place", sa.String(100), nullable=True),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("address", sa.String(255), nullable=True),
            sa.Column("emergency_contact", sa.String(200), nullable=True),
            sa.Column("bank_account", sa.String(30), nullable=True),
            sa.Column("bank_name", sa.String(100), nullable=True),
            sa.Column("social_insurance_no", sa.String(20), nullable=True),
            sa.Column("hire_date", sa.Date(), nullable=True),
            sa.Column("contract_type", sa.String(20), nullable=True),
            sa.Column("contract_signed_date", sa.Date(), nullable=True),
            sa.Column("contract_end_date", sa.Date(), nullable=True),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if "employee_documents" not in tables:
        op.create_table(
            "employee_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("doc_type", sa.String(30), nullable=False),
            sa.Column("filename", sa.String(200), nullable=False),
            sa.Column("mime", sa.String(50), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("uploaded_by", sa.String(36), nullable=True),
            sa.Column("uploaded_by_name", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_employee_documents_user", "employee_documents", ["user_id"])

    if "handover_records" not in tables:
        op.create_table(
            "handover_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("from_user_id", sa.String(36), nullable=False),
            sa.Column("from_user_name", sa.String(100), nullable=False),
            sa.Column("to_user_id", sa.String(36), nullable=False),
            sa.Column("to_user_name", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(20), nullable=False),
            sa.Column("entity_id", sa.String(36), nullable=False),
            sa.Column("entity_name", sa.String(255), nullable=False),
            sa.Column("reason", sa.String(20), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("actor_name", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_handover_from_user", "handover_records", ["from_user_id"])
        op.create_index("ix_handover_to_user", "handover_records", ["to_user_id"])

    if "attendance_records" in tables:
        cols = {c["name"] for c in insp.get_columns("attendance_records")}
        new_cols = [
            ("check_in_ip", sa.Column("check_in_ip", sa.String(45), nullable=True)),
            ("ip_ok", sa.Column("ip_ok", sa.Boolean(), nullable=True)),
            ("gps_ok", sa.Column("gps_ok", sa.Boolean(), nullable=True)),
            ("ot_decided_by", sa.Column("ot_decided_by", sa.String(36), nullable=True)),
            ("ot_decided_by_name", sa.Column("ot_decided_by_name", sa.String(100), nullable=True)),
            ("ot_decided_at", sa.Column("ot_decided_at", sa.DateTime(), nullable=True)),
        ]
        for name, col in new_cols:
            if name not in cols:
                op.add_column("attendance_records", col)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for t in ("handover_records", "employee_documents", "employee_profiles"):
        if t in tables:
            op.drop_table(t)
    if "attendance_records" in tables:
        cols = {c["name"] for c in insp.get_columns("attendance_records")}
        for name in ("ot_decided_at", "ot_decided_by_name", "ot_decided_by", "gps_ok", "ip_ok", "check_in_ip"):
            if name in cols:
                op.drop_column("attendance_records", name)
