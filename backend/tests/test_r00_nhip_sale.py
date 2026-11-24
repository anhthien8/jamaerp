"""R00 mục 9-10 (21/11/2026): hỏi kết quả buổi hẹn + bản tin sáng «Hôm nay của bạn»."""
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.auth import hash_password
from app.models.contract import Contract
from app.models.lead import Activity, Lead
from app.models.notification import Notification
from app.models.project import Project
from app.models.user import User
from app.services import automation, nhip_sale, telegram_notify
from app.services.automation import gio_vn_naive
from tests.conftest import auth_header

VN = timezone(timedelta(hours=7))
HOM_NAY = gio_vn_naive().date()


def _luc(ngay: date, gio: int, phut: int = 0) -> datetime:
    return datetime.combine(ngay, time(gio, phut))


def _uid() -> str:
    return str(uuid.uuid4())


def _utc(vn: datetime) -> datetime:
    return vn.replace(tzinfo=VN).astimezone(timezone.utc)


@pytest.fixture
def gui(monkeypatch) -> list[tuple]:
    """Telegram giả (cả _notify lẫn bản tin gửi thẳng) — ghi (chat, text, reply_markup)."""
    ds: list[tuple] = []

    async def fake_send(chat, text, parse_mode="HTML", reply_markup=None):
        ds.append((chat, text, reply_markup))
        return True

    monkeypatch.setattr(automation, "send_telegram", fake_send)
    monkeypatch.setattr(nhip_sale, "send_telegram", fake_send)
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "https://crm.jamahome.vn", raising=False)
    return ds


@pytest_asyncio.fixture
async def sale(db_session, sales_user) -> User:
    sales_user.telegram_user_id = 777001
    await db_session.commit()
    return sales_user


@pytest_asyncio.fixture
async def sale_khac(db_session) -> User:
    u = User(id=_uid(), full_name="Sale Khác", email="sale.khac.nhip@test.com",
             password_hash=hash_password("x12345678"), role="data_entry", department="SALES",
             is_active=True, telegram_user_id=777002)
    db_session.add(u)
    await db_session.commit()
    return u


async def _lead(db_session, owner: User, ten="Anh Nam – Vinhomes", sdt="0909000111", lien_he_ngay=1, **kw) -> Lead:
    lead = Lead(id=_uid(), name=ten, phone=sdt, stage="interested", assigned_to=owner.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=20),
                last_contacted_at=datetime.now(timezone.utc) - timedelta(days=lien_he_ngay), **kw)
    db_session.add(lead)
    await db_session.commit()
    return lead


async def _thong_bao(db_session, loai: str) -> list[Notification]:
    return list((await db_session.execute(select(Notification).where(Notification.type == loai))).scalars().all())


def _nut(mk: dict) -> list[tuple[str, str]]:
    return [(b["text"], b.get("callback_data") or b.get("url")) for h in mk["inline_keyboard"] for b in h]


# ── Mục 9: hỏi kết quả buổi hẹn ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hoi_ket_qua_2_tieng_sau_hen_mot_lan(db_session, sale, gui):
    hen = _luc(HOM_NAY, 9)
    lead = await _lead(db_session, sale, hen_tiep_luc=hen, plan_type="offline")

    kq = await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 11, 30))
    assert kq["hoi"] == 1
    chat, text, mk = gui[0]
    assert chat == 777001
    assert text.startswith("<b>Buổi hẹn với Anh Nam – Vinhomes thế nào?</b>")
    assert "Hẹn lúc 09:00 hôm nay" in text and "0909000111" in text
    nut = _nut(mk)
    assert nut[0] == ("Chốt được", f"https://crm.jamahome.vn/leads?id={lead.id}&chot=1")
    assert ("Cần theo tiếp", f"ld:tt:{lead.id}") in nut
    assert ("Khách hoãn", f"ld:ho:{lead.id}") in nut and ("Mất", f"ld:mk:{lead.id}") in nut
    assert nut[-1] == ("Mở ERP", f"https://crm.jamahome.vn/leads?id={lead.id}")
    assert all(len(d.encode()) <= 64 for t, d in nut if d.startswith("ld:"))
    tb = await _thong_bao(db_session, "hoi_ket_qua_hen")
    assert [t.ref_id for t in tb] == [f"hen:{lead.id}:{hen:%Y%m%d%H%M}"]

    # Không hỏi lần 2 cho cùng buổi hẹn
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 15)))["hoi"] == 0
    assert len(gui) == 1


@pytest.mark.asyncio
async def test_chua_du_2_tieng_hoac_ngoai_gio_khong_hoi(db_session, sale, gui):
    await _lead(db_session, sale, survey_date=_luc(HOM_NAY, 9))
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 10, 30)))["hoi"] == 0
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 21, 5)))["status"] == "skipped"
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 7, 59)))["status"] == "skipped"
    assert gui == []
    # Khảo sát: nhãn «Khảo sát»
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 11)))["hoi"] == 1
    assert "Khảo sát lúc 09:00 hôm nay" in gui[0][1]


@pytest.mark.asyncio
async def test_da_ghi_ket_qua_sau_hen_thi_khong_hoi(db_session, sale, gui):
    hen = _luc(HOM_NAY, 9)
    lead = await _lead(db_session, sale, hen_tiep_luc=hen)
    # Đánh giá CSKH không phải kết quả của sale → vẫn hỏi; cuộc gọi sau hẹn → thôi hỏi
    db_session.add(Activity(lead_id=lead.id, user_id=sale.id, type="cskh", content="kiểm tra",
                            created_at=_utc(hen + timedelta(minutes=30))))
    await db_session.commit()
    assert await nhip_sale.da_co_ket_qua(db_session, lead.id, hen) is False
    db_session.add(Activity(lead_id=lead.id, user_id=sale.id, type="call", content="Đã gọi cho khách",
                            created_at=_utc(hen + timedelta(hours=1))))
    await db_session.commit()
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 12)))["hoi"] == 0
    assert gui == []


@pytest.mark.asyncio
async def test_hen_hom_qua_khong_hoi_ma_vao_ban_tin(db_session, sale, gui):
    hom_qua = HOM_NAY - timedelta(days=1)
    lead = await _lead(db_session, sale, hen_tiep_luc=_luc(hom_qua, 20), plan_type="online")
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 11)))["hoi"] == 0
    bt = await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY, 7))
    assert "<b>Hẹn hôm qua chưa có kết quả (1)</b>" in bt["text"]
    assert "20:00 hôm qua · <b>Anh Nam – Vinhomes</b> · Hẹn · 0909000111" in bt["text"]
    assert ("1. Anh Nam – Vinhomes", f"ld:bq:{lead.id}") in _nut(bt["reply_markup"])


@pytest.mark.asyncio
async def test_lead_mat_hoac_da_thang_khong_hoi(db_session, sale, gui):
    lead = await _lead(db_session, sale, hen_tiep_luc=_luc(HOM_NAY, 9))
    lead.stage = "lost"
    await db_session.commit()
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 12)))["hoi"] == 0


# ── Mục 10: bản tin sáng ─────────────────────────────────────────────────────


async def _du_an_co_dot_thu(db_session, owner: User, han: date, status="signed") -> Contract:
    da = Project(id=_uid(), code=f"JMH-{uuid.uuid4().hex[:6]}", name="Dự án Anh Nam", client_name="Anh Nam",
                 sales_id=owner.id)
    db_session.add(da)
    await db_session.flush()
    hd = Contract(id=_uid(), code=f"HD-{uuid.uuid4().hex[:6]}", project_id=da.id, title="HĐ thiết kế",
                  status=status, total_value=400_000_000, signed_date=HOM_NAY - timedelta(days=30),
                  payment_terms={"installments": [
                      {"name": "Đợt 1", "percentage": 50, "status": "paid", "due_date": (HOM_NAY - timedelta(days=20)).isoformat()},
                      {"name": "Đợt 2", "percentage": 30, "status": "pending", "due_date": han.isoformat()},
                      {"name": "Đợt 3", "percentage": 20, "status": "pending", "due_date": (HOM_NAY + timedelta(days=40)).isoformat()},
                  ]})
    db_session.add(hd)
    await db_session.commit()
    return hd


@pytest.mark.asyncio
async def test_ban_tin_du_bon_muc_moi_dong_mot_nut(db_session, sale, sale_khac, gui):
    hom_qua = HOM_NAY - timedelta(days=1)
    a = await _lead(db_session, sale, ten="Chị Mai – Ecopark", sdt="0912345678", hen_tiep_luc=_luc(HOM_NAY, 14))
    b = await _lead(db_session, sale, ten="Anh Tâm – Gamuda", sdt="0977000333", survey_date=_luc(hom_qua, 16))
    c = await _lead(db_session, sale, ten="Cô Lan – Hồ Tây", sdt="0988000222", lien_he_ngay=6)
    await _lead(db_session, sale_khac, ten="Khách của người khác", sdt="0900000000", lien_he_ngay=9)
    hd = await _du_an_co_dot_thu(db_session, sale, HOM_NAY + timedelta(days=2))

    bt = await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY, 7))
    text = bt["text"]
    assert text.startswith("<b>Hôm nay của bạn</b> · ")
    for muc in ("Hẹn hôm nay (1)", "Hẹn hôm qua chưa có kết quả (1)", "Cần gọi (1)", "Đợt thu cần nhắc (1)"):
        assert f"<b>{muc}</b>" in text, muc
    assert "14:00 · <b>Chị Mai – Ecopark</b> · Hẹn · 0912345678" in text
    assert "<b>Cô Lan – Hồ Tây</b> · 6 ngày chưa liên hệ · 0988000222" in text
    assert f"HĐ {hd.code} · Đợt 2 · 120.000.000đ · hạn" in text
    assert "Khách của người khác" not in text
    nut = _nut(bt["reply_markup"])
    assert ("1. Chị Mai – Ecopark", f"ld:bt:{a.id}") in nut
    assert ("2. Anh Tâm – Gamuda", f"ld:bq:{b.id}") in nut
    assert ("3. Cô Lan – Hồ Tây", f"ld:bt:{c.id}") in nut
    assert (f"4. HĐ {hd.code}", f"https://crm.jamahome.vn/contracts?hd={hd.id}") in nut
    assert nut[-1] == ("Mở ERP", "https://crm.jamahome.vn/leads")
    assert bt["tom_tat"] == "1 hẹn hôm nay · 1 hẹn hôm qua chưa có kết quả · 1 khách cần gọi · 1 đợt thu cần nhắc"


@pytest.mark.asyncio
async def test_dot_thu_hd_nhap_hoac_xa_han_khong_vao(db_session, sale, gui):
    await _du_an_co_dot_thu(db_session, sale, HOM_NAY + timedelta(days=10))
    await _du_an_co_dot_thu(db_session, sale, HOM_NAY, status="draft")
    assert await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY, 7)) is None


@pytest.mark.asyncio
async def test_run_ban_tin_moi_nguoi_moi_ngay_mot_ban(db_session, sale, sale_khac, gui):
    await _lead(db_session, sale, lien_he_ngay=8)
    await _lead(db_session, sale_khac, ten="Khách mới liên hệ", lien_he_ngay=0)  # không có việc → không gửi
    kq = await nhip_sale.run_ban_tin_sang(db_session, now_vn=_luc(HOM_NAY, 7))
    assert kq == {"status": "completed", "gui": 1, "telegram": 1}
    assert [c for c, _, _ in gui] == [777001]
    tb = await _thong_bao(db_session, "ban_tin_sang")
    assert len(tb) == 1 and tb[0].user_id == sale.id and tb[0].body == "1 khách cần gọi"
    # Khởi động lại sau 07:00 → không gửi đôi
    assert (await nhip_sale.run_ban_tin_sang(db_session, now_vn=_luc(HOM_NAY, 9)))["gui"] == 0
    assert len(gui) == 1


@pytest.mark.asyncio
async def test_ban_tin_khong_gui_ngoai_buoi_sang(db_session, sale, gui):
    """Khởi động lại server lúc tối: không bắn «Hôm nay của bạn» lúc đêm."""
    await _lead(db_session, sale, lien_he_ngay=8)
    for gio in (6, 10, 22):
        kq = await nhip_sale.run_ban_tin_sang(db_session, now_vn=_luc(HOM_NAY, gio))
        assert kq["status"] == "skipped", gio
    assert gui == []


@pytest.mark.asyncio
async def test_khao_sat_chi_co_ngay_hoi_buoi_toi(db_session, sale, gui):
    """Ô «Ngày khảo sát» trên web chỉ có ngày (00:00): không hỏi lúc 08:00, hỏi từ 19:00."""
    lead = await _lead(db_session, sale, survey_date=_luc(HOM_NAY, 0))
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 8, 5)))["hoi"] == 0
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 18, 30)))["hoi"] == 0
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 19, 5)))["hoi"] == 1
    assert "Khảo sát hôm nay · SĐT 0909000111" in gui[0][1] and "00:00" not in gui[0][1]
    bt = await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY, 7))
    assert f"Trong ngày · <b>{lead.name}</b> · Khảo sát" in bt["text"]
    hom_sau = await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY + timedelta(days=1), 7))
    assert f"Hôm qua · <b>{lead.name}</b> · Khảo sát" in hom_sau["text"]


@pytest.mark.asyncio
async def test_hen_khao_sat_va_ngay_khao_sat_cung_ngay_chi_mot_buoi(db_session, sale, gui):
    await _lead(db_session, sale, hen_tiep_luc=_luc(HOM_NAY, 9), plan_type="survey", survey_date=_luc(HOM_NAY, 0))
    bt = await nhip_sale.dung_ban_tin(db_session, sale, now_vn=_luc(HOM_NAY, 7))
    assert "<b>Hẹn hôm nay (1)</b>" in bt["text"]
    assert (await nhip_sale.run_hoi_ket_qua_hen(db_session, now_vn=_luc(HOM_NAY, 20)))["hoi"] == 1


@pytest.mark.asyncio
async def test_ngoai_kinh_doanh_khong_co_ban_tin(db_session, designer_user, gui):
    await _lead(db_session, designer_user, lien_he_ngay=8)
    assert await nhip_sale.dung_ban_tin(db_session, designer_user, now_vn=_luc(HOM_NAY, 7)) is None


# ── Endpoint cho bot ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_khach_chi_nguoi_phu_trach(client, db_session, sale, sale_khac):
    lead = await _lead(db_session, sale, hen_tiep_luc=_luc(HOM_NAY + timedelta(days=1), 9), plan_type="survey")
    r = await client.get(f"/api/v1/telegram/lead/{lead.id}/the", headers=auth_header(sale))
    assert r.status_code == 200, r.text
    the = r.json()["lead"]
    assert the["phone"] == "0909000111" and the["name"] == "Anh Nam – Vinhomes"
    assert the["hen"] == [{"luc": _luc(HOM_NAY + timedelta(days=1), 9).isoformat(), "loai": "Hẹn"}]
    assert the["mo_erp"].endswith(f"/leads?id={lead.id}")
    r = await client.get(f"/api/v1/telegram/lead/{lead.id}/the", headers=auth_header(sale_khac))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_endpoint_ban_tin_cho_briefing(client, db_session, sale, sale_khac):
    await _lead(db_session, sale, lien_he_ngay=8)
    r = await client.get("/api/v1/telegram/ban-tin", headers=auth_header(sale))
    assert r.status_code == 200
    assert "<b>Cần gọi (1)</b>" in r.json()["text"] and r.json()["reply_markup"]["inline_keyboard"]
    r = await client.get("/api/v1/telegram/ban-tin", headers=auth_header(sale_khac))
    assert r.json() == {"text": None, "reply_markup": None}


# ── KPI bản 2 (main) tính hẹn tiếp của R00 ───────────────────────────────────


@pytest.mark.asyncio
async def test_kpi_hen_tiep_phia_truoc_hoac_vua_qua_khong_tinh_tre(db_session, sale):
    """KPI «chăm đúng hạn» và «Việc nên làm tiếp»: có hẹn tiếp phía trước (hoặc vừa qua, còn
    trong hạn) = đang chăm — cùng luật nhắc của bot và nhãn «Quá hạn» trên web."""
    from app.services.attendance_service import VN_TZ
    from app.services.kpi_engine import compute_kpi

    nay = datetime.now(timezone.utc)
    ky = nay.astimezone(VN_TZ).strftime("%Y-%m")
    cu = nay - timedelta(days=40)
    gio_vn = gio_vn_naive()
    for ten, hen in (("Hẹn tới", gio_vn + timedelta(days=2)), ("Vừa hẹn hôm qua", gio_vn - timedelta(days=1)),
                     ("Hẹn từ tháng trước", gio_vn - timedelta(days=30)), ("Bỏ quên", None)):
        db_session.add(Lead(id=_uid(), name=ten, phone="0920000009", assigned_to=sale.id, stage="interested",
                            created_at=cu, last_contacted_at=cu, hen_tiep_luc=hen))
    await db_session.flush()

    m = (await compute_kpi(db_session, sale.id, ky))["metrics"]
    assert m["lead_dang_giu"] == 4
    assert m["lead_tre_cham"] == 2  # «Hẹn từ tháng trước» và «Bỏ quên»
