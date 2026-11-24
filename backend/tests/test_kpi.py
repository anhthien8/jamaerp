"""KPI engine + API tests — spec 04.

Tests compute_kpi, snapshot_all, leaderboard, coaching notes, reviews, burnout signals.
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.attendance import AttendanceRecord
from app.models.project import Project
from app.models.performance import KpiSnapshot, CoachingNote, ReviewCycle
from app.services.kpi_engine import (
    compute_kpi, snapshot_all, parse_period, detect_burnout, get_leaderboard,
    gio_lam_viec, tinh_kpi_ky,
)
from app.services.attendance_service import VN_TZ

from tests.conftest import auth_header, _uid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _create_sales_team(db: AsyncSession) -> dict:
    """Create 2 sales users in same team for testing."""
    team_id = _uid()
    team = Team(id=team_id, name="Sales Alpha", code="SA", department="SALES")
    db.add(team)

    leader = User(
        id=_uid(), full_name="Leader KPI", email="leader-kpi@test.com",
        password_hash=hash_password("pass123"), role="leader",
        department="SALES", is_active=True, team_id=team_id,
        telegram_user_id=10_000_001,
    )
    sale = User(
        id=_uid(), full_name="Sale KPI", email="sale-kpi@test.com",
        password_hash=hash_password("pass123"), role="data_entry",
        department="SALES", is_active=True, team_id=team_id,
        telegram_user_id=10_000_002,
    )
    db.add(leader)
    db.add(sale)
    await db.flush()
    return {"leader": leader, "sale": sale, "team_id": team_id}


async def _seed_kpi_data(db: AsyncSession, user: User, period: str = "2026-07"):
    """Seed realistic KPI data for a user in a given period."""
    start, end = parse_period(period)

    # 20 working days attendance
    for day_offset in range(20):
        d = (start + timedelta(days=day_offset)).date()
        if d.weekday() >= 5:  # skip weekends
            continue
        att = AttendanceRecord(
            id=_uid(), user_id=user.id, work_date=d,
            check_in=datetime(d.year, d.month, d.day, 8, 0, tzinfo=timezone.utc),
            check_out=datetime(d.year, d.month, d.day, 17, 0, tzinfo=timezone.utc),
            work_hours=8, ot_hours=0, source="web",
        )
        db.add(att)

    # 20 leads with various stages
    stages = ["new"] * 8 + ["interested"] * 5 + ["survey_scheduled"] * 3 + ["potential"] * 2 + ["signed_design"] * 2
    for i, stage in enumerate(stages):
        lead = Lead(
            id=_uid(), name=f"Lead KPI {i}", phone=f"090{i:07d}",
            assigned_to=user.id, stage=stage,
            deal_value=500_000_000 if stage in ("potential", "signed_design") else 200_000_000,
            created_at=start + timedelta(days=i),
            # PHẢI set tường minh trong kỳ test: mặc định = now() → khi lịch thật sang
            # tháng mới, signed_count query (updated_at trong kỳ) trả 0 — test nổ hẹn giờ
            # (fail lần đầu 06/08/2026 dù code không đổi)
            updated_at=start + timedelta(days=i),
            last_contacted_at=start + timedelta(days=i, hours=12),
        )
        db.add(lead)

    await db.flush()
    # Doanh số = dự án sinh khi lead Thắng (cùng nguồn hũ thưởng & Bảng KD)
    thang = (await db.execute(
        select(Lead.id).where(Lead.assigned_to == user.id, Lead.stage == "signed_design")
    )).scalars().all()
    for i, lid in enumerate(thang):
        db.add(Project(
            id=_uid(), code=f"KPI-{_uid()[:8]}", name=f"Dự án KPI {i}", client_name="Khách KPI",
            lead_id=lid, sales_id=user.id, total_value=500_000_000,
            created_at=start + timedelta(days=10 + i),
        ))

    # 15 activities across leads
    lead_ids = [lid for lid, in (await db.execute(
        select(Lead.id).where(Lead.assigned_to == user.id)
    )).all()]
    for i in range(15):
        act = Activity(
            id=_uid(),
            lead_id=lead_ids[i % len(lead_ids)],
            user_id=user.id,
            type="call", content=f"Call {i}",
            created_at=start + timedelta(days=i % 20, hours=10),
        )
        db.add(act)

    await db.flush()


# ---------------------------------------------------------------------------
# Engine unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_period():
    start, end = parse_period("2026-07")
    assert start.year == 2026 and start.month == 7
    assert end.year == 2026 and end.month == 8


@pytest.mark.asyncio
async def test_compute_kpi_basic(db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    result = await compute_kpi(db_session, sale.id, "2026-07")

    assert 0 <= result["score"] <= 100
    metrics = result["metrics"]
    assert "activity_rate" in metrics
    assert "sla_compliance" in metrics
    assert "signed_count" in metrics
    assert metrics["signed_count"] == 2
    assert metrics["activity_rate"] > 0


@pytest.mark.asyncio
async def test_snapshot_all_idempotent(db_session):
    users = await _create_sales_team(db_session)
    await _seed_kpi_data(db_session, users["sale"])

    count1 = await snapshot_all(db_session, "2026-07")
    count2 = await snapshot_all(db_session, "2026-07")

    assert count1 == 2
    assert count2 == 2

    # Should not duplicate — still 2 rows
    from sqlalchemy import select, func
    total = (await db_session.execute(
        select(func.count(KpiSnapshot.id)).where(KpiSnapshot.period == "2026-07")
    )).scalar()
    assert total == 2


@pytest.mark.asyncio
async def test_leaderboard_anonymized(db_session):
    users = await _create_sales_team(db_session)
    await _seed_kpi_data(db_session, users["sale"])
    await snapshot_all(db_session, "2026-07")

    result = await get_leaderboard(db_session, "2026-07", users["sale"].id)
    assert "leaderboard" in result
    assert len(result["leaderboard"]) > 0


@pytest.mark.asyncio
async def test_gio_lam_viec_bo_qua_dem_va_chu_nhat():
    # Thứ Sáu 03/07/2026 22:00 → Thứ Bảy 08:15 = 15 phút làm việc
    a = datetime(2026, 7, 3, 22, 0, tzinfo=VN_TZ)
    assert gio_lam_viec(a, datetime(2026, 7, 4, 8, 15, tzinfo=VN_TZ)) == pytest.approx(0.25)
    # Thứ Bảy 17:00 → Thứ Hai 09:00: bỏ trọn Chủ nhật = 1h + 1h
    assert gio_lam_viec(datetime(2026, 7, 4, 17, 0, tzinfo=VN_TZ),
                        datetime(2026, 7, 6, 9, 0, tzinfo=VN_TZ)) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_kpi_v2_doanh_so_tu_du_an_khong_dem_lai_khi_sua_lead(db_session):
    """Bản 1 đếm deal theo Lead.updated_at → sửa lead đã thắng là đếm lại. Bản 2 không."""
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)
    # Lead thắng từ tháng 7 bị sửa trong tháng 8
    for lead in (await db_session.execute(
        select(Lead).where(Lead.assigned_to == sale.id, Lead.stage == "signed_design")
    )).scalars().all():
        lead.updated_at = datetime(2026, 8, 5, tzinfo=timezone.utc)
    await db_session.flush()

    thang_7 = await compute_kpi(db_session, sale.id, "2026-07")
    thang_8 = await compute_kpi(db_session, sale.id, "2026-08")
    assert thang_7["metrics"]["deal_thang"] == 2
    assert thang_7["metrics"]["doanh_so"] == 1_000_000_000
    assert thang_8["metrics"]["deal_thang"] == 0


@pytest.mark.asyncio
async def test_kpi_v2_thanh_phan_va_trong_so(db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    m = (await compute_kpi(db_session, sale.id, "2026-07"))["metrics"]
    assert m["phien_ban"] == 2
    assert sum(tp["trong_so"] for tp in m["thanh_phan"]) == 100
    assert m["lead_nhan"] == 20
    # 12/20 lead tiến tới «Đang tư vấn» trở lên → 60% ≥ mốc 30% → 100 điểm
    tien_buoc = next(tp for tp in m["thanh_phan"] if tp["ma"] == "tien_buoc")
    assert tien_buoc["gia_tri"] == 60.0 and tien_buoc["diem"] == 100.0
    assert not m["chua_du_lieu"]


@pytest.mark.asyncio
async def test_kpi_v2_khong_co_gi_de_cham_thi_danh_dau_trong(db_session):
    """Người không lead, không deal: 0 điểm là «trống», phải có cờ để không xếp chung với «kém»."""
    users = await _create_sales_team(db_session)
    kq = await compute_kpi(db_session, users["sale"].id, "2026-07")
    assert kq["score"] == 0
    assert kq["metrics"]["chua_du_lieu"] is True


@pytest.mark.asyncio
async def test_kpi_v2_it_lead_thi_khong_cham_ty_le(db_session):
    """2 lead mà mất 1 = «50% mất khách» là kết luận từ mẫu quá nhỏ → không chấm."""
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    start, _ = parse_period("2026-07")
    for i, stage in enumerate(["lost", "new"]):
        db_session.add(Lead(id=_uid(), name=f"Ít {i}", phone=f"091{i:07d}", assigned_to=sale.id,
                            stage=stage, created_at=start + timedelta(days=2)))
    await db_session.flush()

    m = (await compute_kpi(db_session, sale.id, "2026-07"))["metrics"]
    mat = next(tp for tp in m["thanh_phan"] if tp["ma"] == "mat_khach")
    assert mat["diem"] is None and mat["ly_do"]
    assert m["do_phu"] < 100


@pytest.mark.asyncio
async def test_kpi_v2_co_hen_phia_truoc_khong_tinh_tre(db_session):
    """Lead lâu chưa liên hệ nhưng đã có lịch khảo sát phía trước = đang chăm."""
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    nay = datetime.now(timezone.utc)
    ky = nay.astimezone(VN_TZ).strftime("%Y-%m")
    cu = nay - timedelta(days=40)
    db_session.add(Lead(id=_uid(), name="Có hẹn", phone="0920000001", assigned_to=sale.id,
                        stage="interested", created_at=cu, last_contacted_at=cu,
                        survey_date=nay + timedelta(days=2)))
    db_session.add(Lead(id=_uid(), name="Bỏ quên", phone="0920000002", assigned_to=sale.id,
                        stage="interested", created_at=cu, last_contacted_at=cu))
    await db_session.flush()

    m = (await compute_kpi(db_session, sale.id, ky))["metrics"]
    assert m["lead_dang_giu"] == 2
    assert m["lead_tre_cham"] == 1


@pytest.mark.asyncio
async def test_kpi_v2_phan_hoi_dem_tu_luc_duoc_giao(db_session):
    """Lead nằm chờ ở khâu chia data 5 ngày rồi mới giao: sale gọi sau 30 phút = 0,5 giờ."""
    users = await _create_sales_team(db_session)
    sale, leader = users["sale"], users["leader"]
    for i in range(3):
        tao = datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc)          # 09:00 VN 01/07
        giao = datetime(2026, 7, 6, 2, 0, tzinfo=timezone.utc)         # 09:00 VN thứ Hai 06/07
        lead = Lead(id=_uid(), name=f"Chờ chia {i}", phone=f"093{i:07d}", assigned_to=sale.id,
                    stage="interested", created_at=tao)
        db_session.add(lead)
        db_session.add(Activity(id=_uid(), lead_id=lead.id, user_id=leader.id, type="assignment",
                                content="Giao lead", created_at=giao))
        db_session.add(Activity(id=_uid(), lead_id=lead.id, user_id=sale.id, type="call",
                                content="Gọi chào", created_at=giao + timedelta(minutes=30)))
    await db_session.flush()

    m = (await compute_kpi(db_session, sale.id, "2026-07"))["metrics"]
    assert m["gio_phan_hoi"] == 0.5


@pytest.mark.asyncio
async def test_kpi_v2_dieu_phoi_kd_khong_ganh_chi_tieu(db_session):
    users = await _create_sales_team(db_session)
    db_session.add(User(
        id=_uid(), full_name="Admin CSKH", email="cskh-kpi@test.com",
        password_hash=hash_password("pass123"), role="admin_cskh",
        department="SALES", is_active=True, telegram_user_id=10_000_009,
    ))
    await db_session.flush()
    kq = await tinh_kpi_ky(db_session, "2026-07")
    assert set(kq) == {users["sale"].id, users["leader"].id}


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_kpi(client, db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    resp = await client.get("/api/v1/kpi/me?period=2026-07", headers=auth_header(sale))
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score"] <= 100
    assert "metrics" in data


def _ky_nay() -> str:
    return datetime.now(timezone.utc).astimezone(VN_TZ).strftime("%Y-%m")


@pytest.mark.asyncio
async def test_viec_tiep_chi_ra_dung_lead_can_lam(client, db_session):
    """«Của tôi» phải nói được việc tiếp theo, gắn với lead cụ thể — và hạn chăm
    theo từng bước (đàm phán 14 ngày, tư vấn 7 ngày), khớp nhãn «Quá hạn» ở bảng lead."""
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    nay = datetime.now(timezone.utc)
    cu = nay - timedelta(days=40)

    def lead(ten, stage, lien_he_truoc=None, tao=cu, **kw):
        l = Lead(id=_uid(), name=ten, phone=f"094{abs(hash(ten)) % 10**7:07d}", assigned_to=sale.id,
                 stage=stage, created_at=tao,
                 last_contacted_at=nay - timedelta(days=lien_he_truoc) if lien_he_truoc is not None else None,
                 **kw)
        db_session.add(l)
        return l

    lead("Mới tinh", "new", tao=nay - timedelta(hours=2))
    lead("Đàm phán bỏ quên", "potential", 20, deal_value=900_000_000)
    lead("Đàm phán vừa gọi", "potential", 5, deal_value=300_000_000)
    lead("Tư vấn 5 ngày", "interested", 5)
    lead("Tư vấn bỏ quên", "interested", 9)
    await db_session.flush()

    resp = await client.get(f"/api/v1/kpi/me?period={_ky_nay()}", headers=auth_header(sale))
    assert resp.status_code == 200
    data = resp.json()
    assert data["thuoc_doi"] is True and data["tien_do"]["dang_chay"] is True
    assert data["cong_thuc"]["han_cham"]["potential"] == 14
    assert data["metrics"]["lead_tre_cham"] == 2

    viec = {v["ma"]: v for v in data["viec_tiep"]}
    assert [l["ten"] for l in viec["goi_lead_moi"]["lead"]] == ["Mới tinh"]
    # Lead gần chốt xếp trước; lead còn trong hạn của bước mình thì KHÔNG bị liệt kê
    assert [l["ten"] for l in viec["lien_he_lai"]["lead"]] == ["Đàm phán bỏ quên", "Tư vấn bỏ quên"]
    assert viec["lien_he_lai"]["diem_them"] > 0
    assert viec["lien_he_lai"]["lead"][0]["sdt"]
    # Hụt mục tiêu → chỉ đúng lead gần chốt, lead giá trị cao đứng đầu
    assert [l["ten"] for l in viec["chot_deal"]["lead"]] == ["Đàm phán bỏ quên", "Đàm phán vừa gọi"]
    # Thứ tự = độ gấp: lead mới trước, rồi quá hạn, rồi chốt deal
    ma = [v["ma"] for v in data["viec_tiep"]]
    assert ma.index("goi_lead_moi") < ma.index("lien_he_lai") < ma.index("chot_deal")


@pytest.mark.asyncio
async def test_viec_tiep_ky_da_khep_va_nguoi_chua_co_lead(client, db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    cu = (await client.get("/api/v1/kpi/me?period=2026-07", headers=auth_header(sale))).json()
    assert cu["viec_tiep"] == [] and cu["tien_do"]["dang_chay"] is False

    # Kỳ này: toàn bộ lead seed đã cũ, không lead mới nhận, không deal → vẫn có việc quá hạn
    # của lead đang mở; người KHÔNG có gì (leader) thì được chỉ đường đi xin lead.
    trong = (await client.get(f"/api/v1/kpi/me?period={_ky_nay()}",
                              headers=auth_header(users["leader"]))).json()
    assert [v["ma"] for v in trong["viec_tiep"]] == ["chua_co_lead"]


@pytest.mark.asyncio
async def test_viec_tiep_nguoi_ngoai_doi_kd_khong_bi_gan_viec(client, db_session):
    """Giám sát công trình mở tab «Của tôi»: không gánh chỉ tiêu → không có việc KD nào."""
    gs = User(id=_uid(), full_name="Giám sát KPI", email="gs-kpi@test.com",
              password_hash=hash_password("pass123"), role="supervisor",
              department="CONSTRUCTION", is_active=True, telegram_user_id=10_000_021)
    db_session.add(gs)
    await db_session.flush()
    data = (await client.get(f"/api/v1/kpi/me?period={_ky_nay()}", headers=auth_header(gs))).json()
    assert data["thuoc_doi"] is False
    assert data["viec_tiep"] == []


@pytest.mark.asyncio
async def test_team_kpi_leader(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    await _seed_kpi_data(db_session, users["sale"])
    await snapshot_all(db_session, "2026-07")

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(leader))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) >= 1


@pytest.mark.asyncio
async def test_team_kpi_forbidden_for_sale(client, db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(sale))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_leaderboard(client, db_session):
    users = await _create_sales_team(db_session)
    await snapshot_all(db_session, "2026-07")

    resp = await client.get("/api/v1/kpi/leaderboard?period=2026-07",
                            headers=auth_header(users["sale"]))
    assert resp.status_code == 200
    assert "leaderboard" in resp.json()


@pytest.mark.asyncio
async def test_snapshot_trigger_admin_only(client, db_session):
    users = await _create_sales_team(db_session)

    # Sale can't trigger
    resp = await client.post("/api/v1/kpi/snapshot?period=2026-07",
                             headers=auth_header(users["sale"]))
    assert resp.status_code == 403


async def _tao_bgd(db: AsyncSession, role: str = "executive") -> User:
    u = User(id=_uid(), full_name="Giám đốc KPI", email=f"bgd-{_uid()[:6]}@test.com",
             password_hash=hash_password("pass123"), role=role, is_active=True,
             telegram_user_id=int(uuid.uuid4().int % 10**9))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_tong_quan_chi_bgd(client, db_session):
    users = await _create_sales_team(db_session)
    for nguoi in (users["sale"], users["leader"]):
        resp = await client.get("/api/v1/kpi/tong-quan?period=2026-07", headers=auth_header(nguoi))
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tong_quan_bgd_du_so_lieu(client, db_session):
    users = await _create_sales_team(db_session)
    await _seed_kpi_data(db_session, users["sale"])
    bgd = await _tao_bgd(db_session)

    resp = await client.get("/api/v1/kpi/tong-quan?period=2026-07", headers=auth_header(bgd))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tong"]["doanh_so"] == 1_000_000_000
    assert data["tong"]["deal"] == 2
    assert data["tong"]["so_nguoi"] == 2
    # Trưởng nhóm không lead, không deal → «chưa có dữ liệu», nằm cuối bảng
    assert data["tong"]["phan_bo"]["chua_du_lieu"] == 1
    assert [h["name"] for h in data["nhan_vien"]] == ["Sale KPI", "Leader KPI"]
    assert data["nhom"][0]["ten"] == "Sales Alpha"
    assert data["nhom"][0]["truong_nhom"] == "Leader KPI"
    assert sum(tp["trong_so"] for tp in data["cong_thuc"]["thanh_phan"]) == 100
    assert data["can_chu_y"]


@pytest.mark.asyncio
async def test_leaderboard_bgd_thay_du_ten(client, db_session):
    """Nhân viên bị ẩn tên từ hạng 6; BGĐ phải thấy đủ — không ai ra quyết định với «Nhân viên #6»."""
    team_id = _uid()
    db_session.add(Team(id=team_id, name="Sales Đông", code="SD", department="SALES"))
    nguoi = []
    for i in range(7):
        u = User(id=_uid(), full_name=f"Sale {i}", email=f"sale-lb-{i}@test.com",
                 password_hash=hash_password("pass123"), role="data_entry", department="SALES",
                 is_active=True, team_id=team_id, telegram_user_id=10_100_000 + i)
        db_session.add(u)
        nguoi.append(u)
    bgd = await _tao_bgd(db_session, "admin")
    await db_session.flush()

    cua_sale = (await client.get("/api/v1/kpi/leaderboard?period=2026-07",
                                 headers=auth_header(nguoi[0]))).json()["leaderboard"]
    cua_bgd = (await client.get("/api/v1/kpi/leaderboard?period=2026-07",
                                headers=auth_header(bgd))).json()["leaderboard"]
    assert len(cua_bgd) == 7
    assert all(e["name"] for e in cua_bgd)
    assert any(e["name"] is None for e in cua_sale)


@pytest.mark.asyncio
async def test_ky_sai_dinh_dang_tra_400(client, db_session):
    users = await _create_sales_team(db_session)
    resp = await client.get("/api/v1/kpi/me?period=thang-7", headers=auth_header(users["sale"]))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Coaching notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coaching_note_crud(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    sale = users["sale"]

    # Create
    resp = await client.post("/api/v1/kpi/coaching-notes", json={
        "user_id": sale.id, "note": "Cần improve SLA", "kind": "concern",
    }, headers=auth_header(leader))
    assert resp.status_code == 200
    note_id = resp.json()["id"]

    # List
    resp = await client.get(f"/api/v1/kpi/coaching-notes?user_id={sale.id}",
                            headers=auth_header(leader))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_coaching_note_forbidden_cross_team(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]

    # Create user in different team
    other_user = User(
        id=_uid(), full_name="Other", email="other@test.com",
        password_hash=hash_password("pass123"), role="data_entry",
        department="SALES", is_active=True, telegram_user_id=10_000_003,
    )
    db_session.add(other_user)
    await db_session.flush()

    resp = await client.post("/api/v1/kpi/coaching-notes", json={
        "user_id": other_user.id, "note": "Test", "kind": "concern",
    }, headers=auth_header(leader))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_flow(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    sale = users["sale"]

    # Create review cycle
    review = ReviewCycle(
        id=_uid(), user_id=sale.id, period="2026-Q3", status="pending_self",
    )
    db_session.add(review)
    await db_session.flush()

    # Self submit
    resp = await client.put(f"/api/v1/kpi/reviews/me/{review.id}", json={
        "self_json": '{"goals": "improve SLA"}',
    }, headers=auth_header(sale))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_leader"

    # Leader submit
    resp = await client.put(f"/api/v1/kpi/reviews/{review.id}/leader", json={
        "leader_json": '{"score": 85}', "goals_json": '{"next": "close more"}',
    }, headers=auth_header(leader))
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


# ---------------------------------------------------------------------------
# Burnout detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_burnout_signals_lead_overload(db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]

    # Create 30 active leads (overload)
    for i in range(30):
        lead = Lead(
            id=_uid(), name=f"Overload {i}", phone=f"091{i:07d}",
            assigned_to=sale.id, stage="new",
        )
        db_session.add(lead)
    await db_session.flush()

    result = await detect_burnout(db_session, sale.id)
    assert "lead_overload" in result["signals"]
    assert result["risk_level"] in ("yellow", "red")
