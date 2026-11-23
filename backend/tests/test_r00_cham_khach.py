"""R00 mục 3 (14/11/2026): nút trên tin Telegram ghi một lần chăm khách.

POST /api/v1/telegram/lead/{id}/touch — bot gọi bằng JWT riêng của người bấm.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.auth import hash_password
from app.models.lead import Activity, Lead
from app.models.notification import Notification
from app.models.user import User
from app.services.automation import gio_vn_naive
from tests.conftest import auth_header

URL = "/api/v1/telegram/lead/{}/touch"


def _uid() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def sale_khac(db_session) -> User:
    u = User(
        id=_uid(), full_name="Sale Khác", email="sale.khac@test.com",
        password_hash=hash_password("x12345678"), role="data_entry",
        department="SALES", is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


async def _lead(db_session, owner: User, **kw) -> Lead:
    lead = Lead(
        id=_uid(), name="Anh Nam – Vinhomes", phone="0909000111", stage="interested",
        assigned_to=owner.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
        last_contacted_at=datetime.now(timezone.utc) - timedelta(days=4),
        **kw,
    )
    db_session.add(lead)
    await db_session.commit()
    return lead


async def _hoat_dong(db_session, lead: Lead) -> list[Activity]:
    return list((await db_session.execute(
        select(Activity).where(Activity.lead_id == lead.id).order_by(Activity.created_at)
    )).scalars().all())


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_bam_vao_lead_nguoi_khac_bi_403(client, db_session, sales_user, sale_khac):
    lead = await _lead(db_session, sale_khac)
    r = await client.post(URL.format(lead.id), json={"viec": "goi"}, headers=auth_header(sales_user))
    assert r.status_code == 403
    assert await _hoat_dong(db_session, lead) == []


@pytest.mark.asyncio
async def test_lead_khong_ton_tai_404(client, sales_user):
    r = await client.post(URL.format(_uid()), json={"viec": "goi"}, headers=auth_header(sales_user))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ngoai_kinh_doanh_bi_chan_du_dang_giu_lead(client, db_session, designer_user):
    # Đổi phòng sang Giám sát mà lead cũ còn đứng tên — vẫn chặn theo bộ phận như web.
    lead = await _lead(db_session, designer_user)
    r = await client.post(URL.format(lead.id), json={"viec": "goi"}, headers=auth_header(designer_user))
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("viec,loai", [
    ("goi", "call"), ("gap", "meeting"), ("zoom", "zoom"), ("vp", "office_visit"),
])
async def test_moi_viec_ghi_dung_loai_va_doi_moc_lien_he(client, db_session, sales_user, viec, loai):
    lead = await _lead(db_session, sales_user)
    cu = _aware(lead.last_contacted_at)
    r = await client.post(
        URL.format(lead.id),
        json={"viec": viec, "telegram_message_id": 555, "telegram_chat_id": 900003},
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["moi_ghi"] is True and body["loai"] == loai
    assert body["lead"]["stage_label"] == "Đang tư vấn"
    acts = await _hoat_dong(db_session, lead)
    assert [(a.type, a.telegram_message_id, a.telegram_chat_id) for a in acts] == [(loai, 555, 900003)]
    await db_session.refresh(lead)
    assert _aware(lead.last_contacted_at) > cu


@pytest.mark.asyncio
async def test_hen_lai_dat_moc_nhung_khong_doi_moc_lien_he(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    cu = _aware(lead.last_contacted_at)
    r = await client.post(
        URL.format(lead.id), json={"viec": "hen", "hen_sau_ngay": 3, "plan_type": "offline"},
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(lead)
    mong_doi = datetime.combine(gio_vn_naive().date() + timedelta(days=3), datetime.min.time()).replace(hour=9)
    assert lead.hen_tiep_luc == mong_doi
    assert lead.plan_type == "offline"
    assert _aware(lead.last_contacted_at) == cu  # hẹn là kế hoạch, chưa phải chạm khách
    acts = await _hoat_dong(db_session, lead)
    assert [a.type for a in acts] == ["hen"]
    assert acts[0].content == f"Hẹn tư vấn offline: {mong_doi.strftime('%H:%M %d/%m/%Y')}"
    assert r.json()["lead"]["hen_tiep_luc"] == mong_doi.isoformat()


@pytest.mark.asyncio
async def test_hen_gio_cu_the_co_mui_gio_doi_ve_gio_vn(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    ngay = gio_vn_naive().date() + timedelta(days=2)
    r = await client.post(
        URL.format(lead.id),
        json={"viec": "hen", "hen_tiep_luc": f"{ngay.isoformat()}T07:30:00Z"},  # 14:30 giờ VN
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(lead)
    assert lead.hen_tiep_luc == datetime(ngay.year, ngay.month, ngay.day, 14, 30)


@pytest.mark.asyncio
async def test_goi_kem_hen_ghi_ca_hai(client, db_session, sales_user):
    # Bot xác nhận câu tự do «Đã gặp, hẹn lại 1 tuần» → một lần bấm [Đúng] ghi cả hai.
    lead = await _lead(db_session, sales_user)
    r = await client.post(
        URL.format(lead.id), json={"viec": "gap", "hen_sau_ngay": 7},
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    assert [a.type for a in await _hoat_dong(db_session, lead)] == ["meeting", "hen"]
    await db_session.refresh(lead)
    assert lead.hen_tiep_luc is not None


@pytest.mark.asyncio
async def test_hen_thieu_gio_hoac_gio_da_qua_bi_422(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    h = auth_header(sales_user)
    r = await client.post(URL.format(lead.id), json={"viec": "hen"}, headers=h)
    assert r.status_code == 422
    qua = (gio_vn_naive() - timedelta(hours=1)).isoformat()
    r = await client.post(URL.format(lead.id), json={"viec": "hen", "hen_tiep_luc": qua}, headers=h)
    assert r.status_code == 422
    r = await client.post(URL.format(lead.id), json={"viec": "ghi_chu", "noi_dung": "  "}, headers=h)
    assert r.status_code == 422
    assert await _hoat_dong(db_session, lead) == []


@pytest.mark.asyncio
async def test_bam_lap_khong_ghi_doi(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    h = auth_header(sales_user)
    r1 = await client.post(URL.format(lead.id), json={"viec": "goi"}, headers=h)
    r2 = await client.post(URL.format(lead.id), json={"viec": "goi"}, headers=h)
    assert r1.json()["moi_ghi"] is True
    assert r2.json()["moi_ghi"] is False
    assert r2.json()["activity_id"] == r1.json()["activity_id"]
    assert len(await _hoat_dong(db_session, lead)) == 1


@pytest.mark.asyncio
async def test_bam_nut_danh_dau_da_doc_thong_bao_cua_lead_do(client, db_session, sales_user, sale_khac):
    lead = await _lead(db_session, sales_user)
    lead_khac = await _lead(db_session, sales_user)
    n_nhac = Notification(user_id=sales_user.id, type="followup_reminder", title="Nhắc", body="",
                          ref_id=lead.id)
    n_hoi = Notification(user_id=sales_user.id, type="hoi_ket_qua_hen", title="Hỏi", body="",
                         ref_id=f"hen:{lead.id}:202611140900")
    n_lead_khac = Notification(user_id=sales_user.id, type="followup_reminder", title="Nhắc", body="",
                               ref_id=lead_khac.id)
    n_nguoi_khac = Notification(user_id=sale_khac.id, type="followup_reminder", title="Nhắc", body="",
                                ref_id=lead.id)
    db_session.add_all([n_nhac, n_hoi, n_lead_khac, n_nguoi_khac])
    await db_session.commit()

    r = await client.post(URL.format(lead.id), json={"viec": "zoom"}, headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    for n in (n_nhac, n_hoi, n_lead_khac, n_nguoi_khac):
        await db_session.refresh(n)
    assert (n_nhac.read, n_hoi.read) == (True, True)
    assert (n_lead_khac.read, n_nguoi_khac.read) == (False, False)


@pytest.mark.asyncio
async def test_chuyen_mat_tu_nut_bot_tat_thong_bao_khong_doi_moc_lien_he(client, db_session, sales_user):
    # Nút «Mất» trên tin bot gọi PUT /leads/{id}/stage — cũng qua lõi chung.
    lead = await _lead(db_session, sales_user)
    cu = _aware(lead.last_contacted_at)
    n = Notification(user_id=sales_user.id, type="hoi_ket_qua_hen", title="Hỏi", body="",
                     ref_id=f"hen:{lead.id}:202611140900")
    db_session.add(n)
    await db_session.commit()
    r = await client.put(
        f"/api/v1/leads/{lead.id}/stage", json={"new_stage": "lost", "lost_reason": "Đã chọn đối thủ"},
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(lead)
    await db_session.refresh(n)
    assert lead.stage == "lost" and lead.lost_reason == "Đã chọn đối thủ"
    assert n.read is True
    assert _aware(lead.last_contacted_at) == cu
    assert [a.type for a in await _hoat_dong(db_session, lead)] == ["stage_change"]


@pytest.mark.asyncio
async def test_web_ghi_hoat_dong_qua_cung_loi(client, db_session, sales_user):
    # Web và bot ghi giống nhau: ghi chú web dời mốc liên hệ + tắt thông báo của lead đó.
    lead = await _lead(db_session, sales_user)
    cu = _aware(lead.last_contacted_at)
    n = Notification(user_id=sales_user.id, type="followup_reminder", title="Nhắc", body="", ref_id=lead.id)
    db_session.add(n)
    await db_session.commit()
    r = await client.post(
        f"/api/v1/leads/{lead.id}/activities", json={"type": "meeting", "content": "Gặp tại công trình"},
        headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(lead)
    await db_session.refresh(n)
    assert _aware(lead.last_contacted_at) > cu
    assert n.read is True


# ── Web: POST /leads/{id}/hen (chip «Hẹn…», R00 §E) ─────────────────────────


@pytest.mark.asyncio
async def test_web_hen_sau_3_ngay_ghi_hen_tiep_va_lich_su(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    lien_he_cu = _aware(lead.last_contacted_at)
    r = await client.post(f"/api/v1/leads/{lead.id}/hen", json={"hen_sau_ngay": 3, "plan_type": "survey"},
                          headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    moc = (gio_vn_naive() + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
    assert r.json()["hen_tiep_luc"].startswith(moc.isoformat()[:16])
    assert r.json()["plan_type"] == "survey"
    await db_session.refresh(lead)
    assert lead.hen_tiep_luc == moc
    acts = await _hoat_dong(db_session, lead)
    assert [a.type for a in acts] == ["hen"]
    assert acts[0].content == f"Hẹn khảo sát: {moc:%H:%M %d/%m/%Y}"
    # Hẹn chưa phải chạm khách → «liên hệ lần cuối» giữ nguyên
    assert _aware(lead.last_contacted_at) == lien_he_cu


@pytest.mark.asyncio
async def test_web_hen_chon_ngay_qua_khu_hoac_thieu_gio_bi_tu_choi(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    qua = (gio_vn_naive() - timedelta(hours=1)).replace(microsecond=0).isoformat()
    r = await client.post(f"/api/v1/leads/{lead.id}/hen", json={"hen_tiep_luc": qua}, headers=auth_header(sales_user))
    assert r.status_code == 422 and r.json()["detail"] == "Giờ hẹn phải ở phía trước"
    r = await client.post(f"/api/v1/leads/{lead.id}/hen", json={}, headers=auth_header(sales_user))
    assert r.status_code == 422 and r.json()["detail"] == "Thiếu giờ hẹn"
    toi = (gio_vn_naive() + timedelta(days=2)).replace(hour=14, minute=30, second=0, microsecond=0)
    r = await client.post(f"/api/v1/leads/{lead.id}/hen", json={"hen_tiep_luc": toi.isoformat()},
                          headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    await db_session.refresh(lead)
    assert lead.hen_tiep_luc == toi


@pytest.mark.asyncio
async def test_web_hen_nguoi_ngoai_kinh_doanh_bi_chan(client, db_session, sales_user, designer_user):
    lead = await _lead(db_session, sales_user)
    r = await client.post(f"/api/v1/leads/{lead.id}/hen", json={"hen_sau_ngay": 1}, headers=auth_header(designer_user))
    assert r.status_code == 403
    await db_session.refresh(lead)
    assert lead.hen_tiep_luc is None


@pytest.mark.asyncio
async def test_web_chip_bam_hai_lan_khong_ghi_doi(client, db_session, sales_user):
    lead = await _lead(db_session, sales_user)
    body = {"type": "zoom", "content": "Đã tư vấn khách qua Zoom/online"}
    for _ in range(2):
        r = await client.post(f"/api/v1/leads/{lead.id}/activities", json=body, headers=auth_header(sales_user))
        assert r.status_code in (200, 201), r.text
    acts = await _hoat_dong(db_session, lead)
    assert [a.type for a in acts] == ["zoom"]
