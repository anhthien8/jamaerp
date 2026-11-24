"""«Việc cần Ban Giám đốc quyết» (24/11/2026) — GET /dashboard/viec-bgd.

Chủ dự án mở «Việc của tôi» bằng vai Giám đốc thấy trang trống: «chả thấy cần phải làm gì».
Test chốt: mỗi mục chỉ hiện khi đã vượt mốc, kèm tên cụ thể; không có gì vượt mốc thì rỗng.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.lead import Lead
from app.models.project import Project, Task
from app.models.user import User
from app.services.kpi_engine import LEAD_QUA_TAI
from app.services.viec_bgd import DON_KET_NGAY, VIEC_TRE_NGAY
from tests.conftest import _uid, auth_header

DUONG = "/api/v1/dashboard/viec-bgd"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _theo_ma(body: dict) -> dict[str, dict]:
    return {v["ma"]: v for v in body["viec"]}


@pytest.mark.asyncio
async def test_chi_bgd_duoc_xem(client: AsyncClient, admin_user: User, designer_user: User):
    assert (await client.get(DUONG, headers=auth_header(designer_user))).status_code == 403
    r = await client.get(DUONG, headers=auth_header(admin_user))
    assert r.status_code == 200
    # Không có gì vượt mốc → rỗng, không bịa việc cho có
    assert r.json() == {"viec": []}


@pytest.mark.asyncio
async def test_don_ket_va_lead_chua_giao_chi_hien_khi_qua_moc(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, sales_user: User
):
    now = _now()
    db_session.add_all([
        ApprovalRequest(id=_uid(), type="leave", ref_id=_uid(), title="Nghỉ phép kẹt lâu",
                        requester_id=sales_user.id, current_approver_id=admin_user.id,
                        status="pending", created_at=now - timedelta(days=DON_KET_NGAY + 3)),
        ApprovalRequest(id=_uid(), type="leave", ref_id=_uid(), title="Mới gửi sáng nay",
                        requester_id=sales_user.id, current_approver_id=admin_user.id,
                        status="pending", created_at=now - timedelta(hours=3)),
        ApprovalRequest(id=_uid(), type="leave", ref_id=_uid(), title="Đã duyệt từ lâu",
                        requester_id=sales_user.id, current_approver_id=admin_user.id,
                        status="approved", created_at=now - timedelta(days=30)),
        Lead(id=_uid(), name="Khách bị bỏ quên", phone="0930000001", stage="new",
             created_at=now - timedelta(days=4)),
        Lead(id=_uid(), name="Khách vừa vào", phone="0930000002", stage="new",
             created_at=now - timedelta(hours=2)),
        Lead(id=_uid(), name="Khách đã mất", phone="0930000003", stage="lost",
             created_at=now - timedelta(days=9)),
    ])
    await db_session.commit()

    viec = _theo_ma((await client.get(DUONG, headers=auth_header(admin_user))).json())

    don = viec["don_ket_duyet"]
    assert don["tong"] == 1 and don["muc"] == "do"       # đang chờ chính người xem → mức đỏ
    assert don["dong"][0]["ten"] == "Nghỉ phép kẹt lâu"
    assert "Sales Test gửi" in don["dong"][0]["phu"] and "chờ bạn duyệt" in don["dong"][0]["phu"]

    lead = viec["lead_chua_giao"]
    assert lead["tong"] == 1
    assert lead["dong"][0]["ten"] == "Khách bị bỏ quên"
    assert lead["dong"][0]["href"].startswith("/leads?id=")


@pytest.mark.asyncio
async def test_qua_tai_neu_ten_nguoi_nang_va_nguoi_nhe(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, sales_user: User
):
    now = _now()
    nhe = User(id=_uid(), full_name="Sale Đang Nhẹ", email="nhe@test.com", password_hash="x",
               role="data_entry", department="SALES", is_active=True)
    db_session.add(nhe)
    # Vừa nhận hôm nay, vừa liên hệ → quá tải nhưng KHÔNG quá hạn chăm
    for i in range(LEAD_QUA_TAI + 2):
        db_session.add(Lead(id=_uid(), name=f"Nặng {i}", phone=f"094{i:07d}", assigned_to=sales_user.id,
                            stage="interested", created_at=now, last_contacted_at=now))
    db_session.add(Lead(id=_uid(), name="Lead lớn sắp chốt", phone="0950000001", assigned_to=nhe.id,
                        stage="potential", deal_value=900_000_000, created_at=now, last_contacted_at=now))
    await db_session.commit()

    viec = _theo_ma((await client.get(DUONG, headers=auth_header(admin_user))).json())

    qt = viec["qua_tai"]
    assert qt["tong"] == 1 and qt["dong"][0]["ten"] == "Sales Test"
    assert "Sale Đang Nhẹ (1 lead)" in qt["ly_do"]
    assert "lead_qua_han" not in viec

    # Chưa có deal nào trong kỳ → hụt mốc doanh số; lead lớn gần chốt đứng đầu danh sách hỗ trợ
    ds = viec["doanh_so"]
    assert ds["dong"][0]["ten"] == "Lead lớn sắp chốt"
    assert "Sale Đang Nhẹ" in ds["dong"][0]["phu"] and "900tr" in ds["dong"][0]["phu"]


@pytest.mark.asyncio
async def test_du_an_tre_viec_tre_tam_dung(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, project: Project
):
    now = _now()
    project.target_end_date = now - timedelta(days=10)
    dung = Project(id=_uid(), code="JMH-DUNG", name="Dự án treo", client_name="Khách B", status="paused",
                   paused_at=now - timedelta(days=30), pause_reason="Khách chưa chốt mặt bằng")
    db_session.add_all([
        dung,
        Task(id=_uid(), project_id=project.id, title="Trễ lâu", status="in_progress",
             due_date=now - timedelta(days=VIEC_TRE_NGAY + 4)),
        Task(id=_uid(), project_id=project.id, title="Mới trễ hôm qua", status="in_progress",
             due_date=now - timedelta(days=1)),
        Task(id=_uid(), project_id=project.id, title="Trễ lâu nhưng đã xong", status="done",
             due_date=now - timedelta(days=20)),
    ])
    await db_session.commit()

    viec = _theo_ma((await client.get(DUONG, headers=auth_header(admin_user))).json())

    assert viec["viec_tre"]["tieu_de"].startswith("1 đầu việc quá hạn")
    assert viec["viec_tre"]["dong"][0]["href"] == f"/projects?id={project.id}"
    assert viec["du_an_tre"]["dong"][0]["phu"].startswith("trễ 10 ngày")
    assert viec["du_an_tam_dung"]["dong"][0]["ten"] == "JMH-DUNG · Dự án treo"
    assert "Khách chưa chốt mặt bằng" in viec["du_an_tam_dung"]["dong"][0]["phu"]

    # Xếp theo độ gấp: mọi mục đỏ đứng trước mục vàng
    muc = [v["muc"] for v in (await client.get(DUONG, headers=auth_header(admin_user))).json()["viec"]]
    assert muc == sorted(muc, key=["do", "vang", "xam"].index)
