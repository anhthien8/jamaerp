"""Một luật «quá hạn chăm» cho mọi màn hình (24/11/2026).

R00 chốt: có hẹn tiếp / ngày khảo sát ở phía trước = đang chăm; lúc nhận lead và buổi hẹn vừa
qua là một lần chăm; nhãn «Quá hạn» theo hạn từng giai đoạn. Bot, nhãn web và KPI đã theo, còn
Tổng quan, báo cáo nhóm, insight AI, workload, bảng Kinh doanh, Co-Pilot vẫn cứng 3/7 ngày theo
last_contacted_at → sale đang có hẹn vẫn hiện «quá hạn». Mỗi chỗ một test dưới đây.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.agents import insight_agent, sales_copilot
from app.cache import cache
from app.middleware.auth import hash_password
from app.models.lead import Activity, Lead
from app.models.user import Team, User
from app.services.automation import ds_lead_qua_han, gio_vn_naive, ngay_qua_han
from app.services.bod_report import build_group_briefing
from tests.conftest import auth_header
from tests.test_kpi import _create_sales_team, _ky_nay


def _uid() -> str:
    return str(uuid.uuid4())


def _truoc(ngay: float = 0, **kw) -> datetime:
    """UTC naive như các cột liên hệ / tạo / Activity."""
    return (datetime.now(timezone.utc) - timedelta(days=ngay, **kw)).replace(tzinfo=None)


def _vn(**delta) -> datetime:
    """Giờ VN naive như hen_tiep_luc / survey_date."""
    return gio_vn_naive() + timedelta(**delta)


# ── Hàm luật (thuần) ─────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc)
NV = gio_vn_naive(NOW)


def _l(stage="interested", lien_he=None, tao=30, hen=None, ks=None) -> SimpleNamespace:
    mot = lambda d: (NOW - timedelta(days=d)).replace(tzinfo=None)  # noqa: E731
    return SimpleNamespace(stage=stage, last_contacted_at=mot(lien_he) if lien_he is not None else None,
                           created_at=mot(tao), hen_tiep_luc=hen, survey_date=ks)


def test_han_theo_giai_doan_va_nhip_bot():
    assert ngay_qua_han(_l("interested", lien_he=5), None, NV) is None      # hạn tư vấn 7 ngày
    assert ngay_qua_han(_l("interested", lien_he=9), None, NV) == 9
    assert ngay_qua_han(_l("potential", lien_he=10), None, NV) is None      # đàm phán 14 ngày
    assert ngay_qua_han(_l("new", tao=4), None, NV) == 4                    # chưa liên hệ: từ lúc tạo
    for st in ("signed_design", "lost", "dormant"):
        assert ngay_qua_han(_l(st, lien_he=60), None, NV) is None
    # Nhắc / thu hồi của bot: hạn cố định theo cài đặt, không theo giai đoạn
    assert ngay_qua_han(_l("potential", lien_he=10), None, NV, so_ngay=3) == 10


def test_hen_va_luc_nhan_la_moc_cham():
    assert ngay_qua_han(_l(lien_he=20, hen=NV + timedelta(days=2)), None, NV) is None
    assert ngay_qua_han(_l(lien_he=20, ks=NV + timedelta(hours=3)), None, NV) is None
    assert ngay_qua_han(_l(lien_he=20, hen=NV - timedelta(days=2)), None, NV) is None
    assert ngay_qua_han(_l(lien_he=20, hen=NV - timedelta(days=9)), None, NV) == 9
    assert ngay_qua_han(_l(lien_he=20), NOW - timedelta(days=1), NV) is None  # vừa được giao


# ── Bộ lead dùng chung: 2 lead quá hạn thật + 5 lead luật cũ đếm oan ─────────

@pytest_asyncio.fixture
async def bo_lead(db_session, sales_user) -> dict[str, Lead]:
    def lead(ten, stage, lien_he=None, **kw) -> Lead:
        l = Lead(id=_uid(), name=ten, phone=f"09{abs(hash(ten)) % 10**8:08d}", stage=stage,
                 assigned_to=sales_user.id, created_at=_truoc(30),
                 last_contacted_at=_truoc(lien_he) if lien_he is not None else None, **kw)
        db_session.add(l)
        return l

    ds = {
        "qua_han": lead("Quá hạn thật", "new", 5),
        "chua_goi": lead("Chưa gọi lần nào", "new"),
        # Luật cũ đếm oan cả năm lead dưới:
        "hen_mai": lead("Có hẹn mai", "interested", 20, hen_tiep_luc=_vn(days=1)),
        "khao_sat": lead("Khảo sát tuần sau", "new", survey_date=_vn(days=5)),
        "vua_giao": lead("Vừa được giao", "interested", 20),
        "da_ky": lead("Đã ký", "signed_design", 30),
        "tu_van_5": lead("Tư vấn 5 ngày", "interested", 5),
    }
    await db_session.flush()
    db_session.add(Activity(lead_id=ds["vua_giao"].id, user_id=sales_user.id, type="assignment",
                            content="Phân công", created_at=_truoc(1)))
    await db_session.commit()
    return ds


@pytest.mark.asyncio
async def test_ds_lead_qua_han_dung_luat_chung(db_session, bo_lead):
    ten = sorted(l.name for l, _ in await ds_lead_qua_han(db_session))
    assert ten == ["Chưa gọi lần nào", "Quá hạn thật"]


@pytest.mark.asyncio
async def test_tong_quan_ca_nhan(client, sales_user, bo_lead):
    body = (await client.get("/api/v1/dashboard/personal", headers=auth_header(sales_user))).json()
    assert body["overdue_leads"] == 2
    assert [l["name"] for l in body["overdue_followup"]] == ["Chưa gọi lần nào", "Quá hạn thật"]
    viec = [p for p in body["priorities"] if p["type"] == "overdue_lead"]
    assert viec[1]["href"] == f"/leads?id={bo_lead['qua_han'].id}"  # mở thẳng thẻ khách
    assert "5 ngày chưa liên hệ" in viec[1]["subtitle"]


@pytest.mark.asyncio
async def test_tong_quan_ban_giam_doc(client, admin_user, bo_lead):
    cache.clear_prefix("dashboard")
    body = (await client.get("/api/v1/dashboard/executive", headers=auth_header(admin_user))).json()
    cache.clear_prefix("dashboard")
    assert body["overdue_leads"] == 2


@pytest.mark.asyncio
async def test_workload_dem_qua_han_theo_luat_chung(client, admin_user, sales_user, bo_lead):
    rows = (await client.get("/api/v1/leads/workload", headers=auth_header(admin_user))).json()
    dong = next(r for r in rows if r["user_id"] == sales_user.id)
    assert dong["overdue_count"] == 2


@pytest.mark.asyncio
async def test_ban_tin_nhom_dem_ca_lead_chua_goi_va_tru_lead_co_hen(db_session, bo_lead):
    # Luật cũ: 3 ngày theo last_contacted_at → bỏ sót «Chưa gọi lần nào», đếm oan 3 lead có
    # hẹn / mới giao / tư vấn 5 ngày.
    tin = await build_group_briefing(db_session)
    assert "Lead quá hạn chăm sóc (đã trừ khách có hẹn): <b>2</b>" in tin


@pytest.mark.asyncio
async def test_insight_ai_dem_theo_luat_chung(db_session, bo_lead):
    now = datetime.now(timezone.utc)
    m = await insight_agent._gather_metrics(db_session, now, now - timedelta(days=7), now - timedelta(days=14))
    assert m["overdue_leads"] == 2
    canh_bao = insight_agent._rule_based_insights(m, 7)["alerts"]
    assert any("2 lead quá hạn chăm sóc" in a["message"] for a in canh_bao)


@pytest.mark.asyncio
async def test_danh_sach_lead_tra_luc_nhan(client, admin_user, sales_user, bo_lead):
    """Nhãn «Quá hạn» trên web cần lúc nhận lead để khớp các bộ đếm (người vừa được giao có đủ hạn)."""
    r = await client.get("/api/v1/leads?page_size=200", headers=auth_header(sales_user))
    nhan = {l["name"]: l["nhan_luc"] for l in r.json()["items"]}
    assert nhan["Vừa được giao"] and nhan["Quá hạn thật"] is None

    r = await client.post(f"/api/v1/leads/{bo_lead['qua_han'].id}/assign",
                          headers=auth_header(admin_user), json={"user_id": sales_user.id})
    assert r.status_code == 200, r.text
    assert r.json()["nhan_luc"], "giao lại thì web tắt nhãn «Quá hạn» ngay, khỏi tải lại"


# ── Bảng điều khiển Kinh doanh ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bang_kinh_doanh_ngay_cho_va_bao_gia_treo(client, db_session, admin_user):
    nhom = Team(id=_uid(), name="Nhóm QH", code="QH", department="SALES")
    sale = User(id=_uid(), full_name="Sale QH", email="sale.qh@test.com", password_hash=hash_password("x"),
                role="data_entry", department="SALES", team_id=nhom.id, is_active=True)
    db_session.add_all([nhom, sale])
    await db_session.flush()

    def lead(ten, stage, lien_he=None, **kw):
        db_session.add(Lead(id=_uid(), name=ten, phone="0901234567", stage=stage, priority="medium",
                            assigned_to=sale.id, team_id=nhom.id, region="TP. Hồ Chí Minh",
                            created_at=_truoc(10),
                            last_contacted_at=_truoc(lien_he) if lien_he is not None else None, **kw))

    lead("Chưa gọi, có lịch khảo sát", "new", survey_date=_vn(days=2))
    lead("Chưa gọi thật", "new")
    lead("Hẹn mai", "interested", 9, hen_tiep_luc=_vn(days=1))
    lead("Đàm phán có hẹn", "potential", 10, hen_tiep_luc=_vn(days=2))
    lead("Đàm phán bỏ quên", "potential", 10)
    await db_session.commit()

    cache.clear_prefix("dashboard")
    tu = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
    den = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    d = (await client.get(f"/api/v1/dashboard/sales?tu={tu}&den={den}",
                          headers=auth_header(admin_user))).json()
    cache.clear_prefix("dashboard")

    o = next(x for x in d["top_nhan_vien"] if x["user_id"] == sale.id)
    assert o["ton_qua_han"] == 1           # luật cũ: 2 (lead có lịch khảo sát bị tính «chưa liên hệ»)
    assert o["ngay_cho_tb"] == 4.0         # (0 + 10 + 0 + 0 + 10) / 5 — có hẹn = 0 ngày chờ
    treo = next(c for c in d["canh_bao"] if c["ma"] == "bao_gia_treo")
    assert treo["so_luong"] == 1           # luật cũ: 2 (đàm phán có hẹn vẫn «chưa follow»)


# ── KPI «Việc nên làm tiếp» ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kpi_viec_tiep_dem_ngay_tu_buoi_hen_da_qua(client, db_session):
    sale = (await _create_sales_team(db_session))["sale"]
    db_session.add(Lead(id=_uid(), name="Tư vấn hẹn cũ", phone="0941112223", assigned_to=sale.id,
                        stage="interested", created_at=_truoc(40), last_contacted_at=_truoc(20),
                        hen_tiep_luc=_vn(days=-10)))
    await db_session.flush()

    data = (await client.get(f"/api/v1/kpi/me?period={_ky_nay()}", headers=auth_header(sale))).json()
    viec = {v["ma"]: v for v in data["viec_tiep"]}
    ghi_chu = viec["lien_he_lai"]["lead"][0]["ghi_chu"]
    assert ghi_chu.startswith("10 ngày chưa liên hệ"), ghi_chu  # buổi hẹn 10 ngày trước, không phải 20


# ── Co-Pilot ─────────────────────────────────────────────────────────────────

def _lead_copilot(**kw) -> Lead:
    return Lead(id=_uid(), name="Chị Lan", phone="0909888777", stage="interested",
                assigned_to=_uid(), created_at=_truoc(30), **kw)


def _ma_goi_y(lead: Lead) -> list[str]:
    return [u["code"] for u in sales_copilot._ung_vien_theo_luat(lead, [], sales_copilot._so_ngay_im_lang(lead))]


def test_copilot_co_hen_phia_truoc_khong_goi_y_ham_nong():
    assert "recontact" in _ma_goi_y(_lead_copilot(last_contacted_at=_truoc(10)))  # đối chứng
    assert "recontact" not in _ma_goi_y(_lead_copilot(last_contacted_at=_truoc(10), hen_tiep_luc=_vn(days=1)))


def test_copilot_co_lich_khao_sat_khong_phai_chua_lien_he():
    lead = _lead_copilot(survey_date=_vn(days=-2))
    ly_do = [u["reason"] for u in sales_copilot._ung_vien_theo_luat(lead, [], sales_copilot._so_ngay_im_lang(lead))]
    assert "Chưa liên hệ khách hàng lần nào" not in ly_do


def test_copilot_boi_canh_noi_ro_hen_sap_toi():
    boi_canh = sales_copilot._boi_canh(_lead_copilot(hen_tiep_luc=_vn(days=1)), [], "", "Sale A")
    assert "Hẹn tiếp:" in boi_canh and "(sắp tới)" in boi_canh
