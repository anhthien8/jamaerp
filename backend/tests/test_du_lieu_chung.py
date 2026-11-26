"""Dữ liệu chung + Đối chiếu (20/11/2026) — spec «Dữ liệu chung v1» mục B8.

Mỗi test ghi rõ mục B8 nó phủ. Mốc thời gian chèn vào DB đều là UTC naive như prod.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.du_lieu_chung import CAU_HINH_MAC_DINH, CHU_L2_KHONG_XEM_LEAD, muc_theo_diem, tinh_diem
from app.cache import cache
from app.models.audit import AuditLog
from app.models.lead import Activity, Lead
from app.models.media import MediaFile
from app.models.notification import Notification, SystemSetting
from app.models.project import Project, Task, TaskActivity
from app.models.user import User
from app.services.attendance_service import vn_today
from tests.conftest import _uid, auth_header

URL = "/api/v1/dashboard/du-lieu-chung"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _truoc(ngay: float):
    return _now() - timedelta(days=ngay)


# ── Dựng dữ liệu ─────────────────────────────────────────────────────────────

async def _user(db, ten, role, dept, tg=None, **kw):
    u = User(id=_uid(), full_name=ten, email=f"{_uid()[:8]}@t.vn", password_hash="x",
             role=role, department=dept, is_active=True, telegram_user_id=tg, **kw)
    db.add(u)
    await db.flush()
    return u


_dem = {"n": 0}


async def _du_an(db, stage="design", status="active", **kw):
    _dem["n"] += 1
    kw.setdefault("code", f"PRJ-T-{_dem['n']:04d}-{_uid()[:4]}")
    kw.setdefault("name", f"Dự án {kw['code']}")
    kw.setdefault("client_name", "Anh Khách")
    p = Project(id=_uid(), stage=stage, status=status, **kw)
    db.add(p)
    await db.flush()
    return p


async def _viec(db, p, stage, title="Việc", order=1, status="not_started", dept=None, **kw):
    from app.models.project import task_department_for_stage
    t = Task(id=_uid(), project_id=p.id, title=title, stage=stage, order=order, status=status,
             department=dept or task_department_for_stage(stage), **kw)
    db.add(t)
    await db.flush()
    return t


async def _lead(db, ten, stage="new", tao=None, **kw):
    l = Lead(id=_uid(), name=ten, phone="0900000000", stage=stage, priority="medium", **kw)
    db.add(l)
    await db.flush()
    l.created_at = tao or _now()
    await db.flush()
    return l


async def _get(client, user):
    cache.clear_prefix("dashboard")
    r = await client.get(URL, headers=auth_header(user))
    assert r.status_code == 200, r.text
    return r.json()


def _phong(data, ma):
    return next(x for x in data["phong"] if x["ma"] == ma)


@pytest_asyncio.fixture
async def executive_user(db_session):
    u = await _user(db_session, "Giám đốc", "executive", "EXEC")
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def tp(db_session):
    """Trưởng 4 phòng — riêng Dự toán–Thu mua CHƯA có trưởng phòng."""
    ds = {
        "OPS": await _user(db_session, "TP Giám sát", "operation_leader", "OPS", tg=700001),
        "DESIGN": await _user(db_session, "TP Thiết kế", "leader", "DESIGN", tg=700002),
        "SALES": await _user(db_session, "TP Kinh doanh", "leader", "SALES", tg=700003),
    }
    await db_session.commit()
    return ds


@pytest.fixture
def tele(monkeypatch):
    """Telegram giả gắn vào automation._notify — ghi lại (chat_id, text, kwargs)."""
    gui: list[tuple] = []

    async def fake_send(chat_id, text, parse_mode="HTML", **kw):
        gui.append((chat_id, text, kw))
        return True

    monkeypatch.setattr("app.services.automation.send_telegram", fake_send)
    return gui


# ── 1. Quyền ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quyen_trang_chinh_bgd_va_truong_phong(client, db_session, admin_user, executive_user,
                                                    sales_user, accountant_user, designer_user, tp):
    """Vòng 4 (26/11/2026): trưởng 4 phòng được XEM trang chính; còn lại 403 như cũ.

    Trước vòng 4 test này chờ `leader` phòng Thiết kế bị 403 — nay đó là trưởng phòng.
    """
    tp_tm = await _user(db_session, "TP Thu mua", "dutoan_thumua_leader", "PURCHASING")
    bi_chan = [
        sales_user,                                                          # nhân viên KD
        accountant_user,                                                     # kế toán
        designer_user,                                                       # nhân viên phòng OPS
        await _user(db_session, "Trưởng nhóm KD", "sale_leader", "SALES"),
        await _user(db_session, "Chủ trì TK", "design_leader", "DESIGN"),
        await _user(db_session, "TP phòng PM cũ", "operation_leader", "PM"),  # PM không tính là OPS
        await _user(db_session, "Leader BGĐ", "leader", "EXEC"),
        await _user(db_session, "Leader phòng Giám sát", "leader", "OPS"),   # không phải vai TP của OPS
        await _user(db_session, "Leader Nhân sự", "leader", "HR"),
    ]
    await db_session.commit()
    for u in bi_chan:
        r = await client.get(URL, headers=auth_header(u))
        assert r.status_code == 403, (u.role, u.department, r.text)
    duoc_xem = [
        (admin_user, "bgd", None), (executive_user, "bgd", None),
        (tp["SALES"], "truong_phong", "SALES"), (tp["DESIGN"], "truong_phong", "DESIGN"),
        (tp_tm, "truong_phong", "PURCHASING"), (tp["OPS"], "truong_phong", "OPS"),
    ]
    for u, loai, phong in duoc_xem:
        r = await client.get(URL, headers=auth_header(u))
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("cap_nhat_luc", "chay_thu", "moc_bat_dau", "cau_hinh", "phan_anh", "hom_nay",
                  "dai_quy_trinh", "ngoai_dai", "phong", "lech", "can_xem", "cho_bgd", "du_lieu_cu",
                  "tin_hieu_30_ngay", "kenh_thong_bao", "nguoi_xem"):
            assert k in body, k
        bgd = loai == "bgd"
        assert body["nguoi_xem"] == {"loai": loai, "phong": phong, "xem_tien": bgd, "thao_tac": bgd}
    r = await client.post(f"{URL}/nhac", json={"phong": "OPS"}, headers=auth_header(sales_user))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_quyen_doi_chieu_truong_phong_chi_phong_minh(client, db_session, admin_user, tp):
    p = await _du_an(db_session, "construction", total_value=9e8)
    await _lead(db_session, "Lead chờ ký", "potential", assigned_to=tp["SALES"].id)
    await db_session.commit()
    h = auth_header(tp["OPS"])
    r = await client.get(f"{URL}/doi-chieu?phong=OPS", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phong"] == "OPS"
    assert [x["id"] for x in body["ho_so"]] == [p.id]
    assert all(x["loai"] == "du_an" for x in body["ho_so"])
    assert "gia_tri" not in body["ho_so"][0]           # trưởng phòng không thấy tiền
    assert (await client.get(f"{URL}/doi-chieu?phong=DESIGN", headers=h)).status_code == 403
    assert (await client.get(f"{URL}/doi-chieu?phong=SALES", headers=h)).status_code == 403
    r = await client.post(f"{URL}/doi-chieu", headers=h, json={"phong": "DESIGN", "muc": []})
    assert r.status_code == 403
    # Không truyền phòng → mặc định phòng mình
    r = await client.get(f"{URL}/doi-chieu", headers=h)
    assert r.json()["phong"] == "OPS"
    # Trưởng phòng Thiết kế cũng không bao giờ nhận dòng lead
    r = await client.get(f"{URL}/doi-chieu?phong=DESIGN", headers=auth_header(tp["DESIGN"]))
    assert all(x["loai"] == "du_an" for x in r.json()["ho_so"])
    # BGĐ thấy tiền
    r = await client.get(f"{URL}/doi-chieu?phong=OPS", headers=auth_header(admin_user))
    assert r.json()["ho_so"][0]["gia_tri"] == 9e8
    # TP KD thấy lead chờ ký
    r = await client.get(f"{URL}/doi-chieu?phong=SALES", headers=auth_header(tp["SALES"]))
    assert r.status_code == 200
    assert [x["loai"] for x in r.json()["ho_so"]] == ["lead"]


# ── 2. Dữ liệu cũ chưa xếp ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chua_xep_khong_vao_pham_vi_va_dai_cong_du(client, db_session, admin_user):
    await _du_an(db_session, "design")
    await _du_an(db_session, "design", status="paused", pause_reason="Khách đi nước ngoài")
    await _du_an(db_session, "construction")
    cu = await _du_an(db_session, "paused", status="active", total_value=5e8)
    await _du_an(db_session, "completed", status="completed")   # không đang chạy
    await db_session.commit()

    data = await _get(client, admin_user)
    assert data["ngoai_dai"]["chua_xep"]["so_luong"] == 1
    assert [x["id"] for x in data["du_lieu_cu"]] == [cu.id]
    assert data["ngoai_dai"]["tam_dung"] == {"so_luong": 1, "co_ly_do": 1}
    o = {x["ma"]: x for x in data["dai_quy_trinh"]}
    so_cot_du_an = sum(o[m]["so_luong"] for m in ("design", "quotation", "procurement", "construction", "acceptance"))
    assert so_cot_du_an + data["ngoai_dai"]["chua_xep"]["so_luong"] == data["phan_anh"]["tong"] == 4
    assert _phong(data, "DESIGN")["so_ho_so"] == 2
    assert _phong(data, "OPS")["so_ho_so"] == 1
    assert _phong(data, "PURCHASING")["so_ho_so"] == 0
    assert _phong(data, "PURCHASING")["muc"] == "khong_co_ho_so"
    assert all(r["id"] != cu.id for r in data["can_xem"])


# ── 3. updated_at không phải dấu vết ────────────────────────────────────────

@pytest.mark.asyncio
async def test_chi_updated_at_van_chua_ro(client, db_session, admin_user):
    p = await _du_an(db_session, "construction")
    p.updated_at = _now()
    await db_session.commit()
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["trang_thai"]["chua_ro"] == 1
    assert ops["trang_thai"]["co_dau_vet"] == 0
    assert ops["thanh_phan"]["tuoi"] == {"dat": 0, "tong": 1}


# ── 4. Gán dấu vết theo người làm ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_bao_cao_cua_giam_sat_tren_viec_thiet_ke_tinh_cho_ops(client, db_session, admin_user):
    gs = await _user(db_session, "Giám sát A", "giam_sat_thi_cong", "OPS")
    a = await _du_an(db_session, "construction")
    b = await _du_an(db_session, "design")
    for p in (a, b):
        t0 = await _viec(db_session, p, "design", "2D Concept", order=1)   # /baocao rơi về tasks[0]
        db_session.add(TaskActivity(task_id=t0.id, user_id=gs.id, content="Đổ bê tông xong",
                                    created_at=_truoc(1)))
    await db_session.commit()
    data = await _get(client, admin_user)
    assert _phong(data, "OPS")["thanh_phan"]["tuoi"] == {"dat": 1, "tong": 1}
    assert _phong(data, "DESIGN")["thanh_phan"]["tuoi"] == {"dat": 0, "tong": 1}
    assert _phong(data, "OPS")["dau_vet_gan_nhat"]["nguoi"] == "Giám sát A"


@pytest.mark.asyncio
async def test_bo_qua_dong_task_coordinator_tu_ghi(client, db_session, admin_user):
    gs = await _user(db_session, "Giám sát B", "giam_sat_thi_cong", "OPS")
    p = await _du_an(db_session, "construction")
    t = await _viec(db_session, p, "construction", "Thi công thô")
    db_session.add(TaskActivity(task_id=t.id, user_id=gs.id,
                                content="Task Thi công thô created by Task Coordinator for PRJ",
                                created_at=_truoc(1)))
    await db_session.commit()
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["tuoi"]["dat"] == 0
    assert ops["dau_vet_gan_nhat"] is None


# ── 5. Cửa sổ OPS ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cua_so_thi_cong_7_ban_giao_14(client, db_session, admin_user):
    for stage, ngay in (("construction", 6), ("construction", 8), ("acceptance", 13)):
        p = await _du_an(db_session, stage)
        await _viec(db_session, p, stage, "Việc hiện trường", status="in_progress", started_at=_truoc(ngay))
    await db_session.commit()
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["tuoi"] == {"dat": 2, "tong": 3}
    assert ops["trang_thai"]["co_dau_vet"] == 2


# ── 6. Lead ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_do_tuoi_lead_khong_dung_last_contacted(client, db_session, admin_user, sales_user):
    thu_hoi = await _lead(db_session, "Lead thu hồi", "new", tao=_truoc(10), last_contacted_at=_now())
    db_session.add(Activity(lead_id=thu_hoi.id, user_id=sales_user.id, type="assignment",
                            content="Thu hồi", created_at=_now()))
    hai_ngay = await _lead(db_session, "Lead note 2 ngày", "new", tao=_truoc(10))
    db_session.add(Activity(lead_id=hai_ngay.id, user_id=sales_user.id, type="note",
                            content="Đã gọi", created_at=_truoc(2)))
    bon_ngay = await _lead(db_session, "Lead note 4 ngày", "new", tao=_truoc(10))
    db_session.add(Activity(lead_id=bon_ngay.id, user_id=sales_user.id, type="note",
                            content="Đã gọi", created_at=_truoc(4)))
    await _lead(db_session, "Lead treo", "interested", tao=_truoc(61))
    await db_session.commit()
    data = await _get(client, admin_user)
    kd = _phong(data, "SALES")
    assert kd["thanh_phan"]["tuoi"] == {"dat": 1, "tong": 3}
    assert data["ngoai_dai"]["lead_treo"] == 1
    assert kd["so_ho_so"] == 4


# ── 7. sales_id = admin ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sales_id_admin_truot_k7_va_hoi_lai_gui_truong_phong(client, db_session, admin_user, tp, tele):
    p = await _du_an(db_session, "construction", sales_id=admin_user.id, address="12 Lê Lợi")
    await db_session.commit()
    kd = _phong(await _get(client, admin_user), "SALES")
    k7 = next(q for q in kd["quy_tac"] if q["ma"] == "K7")
    assert (k7["dat"], k7["tong"]) == (0, 1)

    r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user),
                          json={"phong": "SALES", "id": p.id, "loai": "du_an"})
    assert r.status_code == 200, r.text
    assert r.json()["da_gui"] == [{"phong": "SALES", "nguoi": "TP Kinh doanh", "telegram": True,
                                     "thong_bao_may": False}]
    nhan = (await db_session.execute(select(Notification.user_id).where(
        Notification.type == "du_lieu_chung"))).scalars().all()
    assert nhan == [tp["SALES"].id]
    assert [c for c, _t, _k in tele] == [700003]


# ── 8. Điểm ──────────────────────────────────────────────────────────────────

def _tp(du=(0, 0), tuoi=(0, 0), dc=(0, 0), ap_dung=False):
    return {"du": {"dat": du[0], "tong": du[1]}, "tuoi": {"dat": tuoi[0], "tong": tuoi[1]},
            "doi_chieu": {"dat": dc[0], "tong": dc[1], "ap_dung": ap_dung}}


def test_diem_ranh_gioi_va_thanh_phan_rong():
    assert tinh_diem(_tp(du=(80, 100)), 5) == (80, "sat")
    assert tinh_diem(_tp(du=(79, 100)), 5) == (79, "can_bo_sung")
    assert tinh_diem(_tp(du=(50, 100)), 5) == (50, "can_bo_sung")
    assert tinh_diem(_tp(du=(49, 100)), 5) == (49, "chua_phan_anh")
    assert muc_theo_diem(None) == "it_ho_so"
    # Phạm vi 2 hồ sơ → không chấm
    assert tinh_diem(_tp(du=(2, 2), tuoi=(2, 2)), 2) == (None, "it_ho_so")
    assert tinh_diem(_tp(), 0) == (None, "khong_co_ho_so")
    # Thành phần mẫu số 0 bị bỏ khỏi trung bình (không kéo về 0, không đẩy lên 100 giả)
    assert tinh_diem(_tp(du=(10, 10), tuoi=(0, 0)), 5) == (100, "sat")
    assert tinh_diem(_tp(du=(5, 10), tuoi=(0, 4)), 5) == (25, "chua_phan_anh")
    # Đối chiếu chưa áp dụng thì không vào điểm
    assert tinh_diem(_tp(du=(5, 10), dc=(0, 10), ap_dung=False), 5) == (50, "can_bo_sung")
    assert tinh_diem(_tp(du=(5, 10), dc=(0, 10), ap_dung=True), 5) == (25, "chua_phan_anh")


@pytest.mark.asyncio
async def test_doi_chieu_chi_vao_diem_khi_nhac_lan_dau_du_7_ngay(client, db_session, admin_user, tp):
    ds = [await _du_an(db_session, "construction") for _ in range(3)]
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={
        "phong": "OPS", "muc": [], "tat_ca_con_lai_dung": True, "ids_hien_thi": [p.id for p in ds]})
    assert r.status_code == 200, r.text
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["doi_chieu"] == {"dat": 3, "tong": 3, "ap_dung": False}
    diem_truoc = ops["diem"]

    # Nhắc lần đầu cách đây 8 ngày → bắt đầu tính
    db_session.add(Notification(user_id=tp["OPS"].id, type="du_lieu_chung", title="x",
                                ref_id="dlc:OPS:2026-01-01", created_at=_truoc(8)))
    await db_session.commit()
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["doi_chieu"]["ap_dung"] is True
    assert ops["diem"] != diem_truoc
    assert ops["lan_nhac_cuoi"]["da_xem"] is False


# ── 9. Lệch ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l1_anh_giam_sat_tren_du_an_bao_gia_khong_doi_diem(client, db_session, admin_user):
    gs = await _user(db_session, "Giám sát C", "giam_sat_thi_cong", "OPS")
    ds = [await _du_an(db_session, "quotation", total_value=1e9) for _ in range(3)]
    await db_session.commit()
    truoc = await _get(client, admin_user)
    assert truoc["lech"] == []

    db_session.add(MediaFile(sha256=_uid(), project_id=ds[0].id, uploaded_by=gs.id, created_at=_truoc(3)))
    await db_session.commit()
    sau = await _get(client, admin_user)
    l1 = [r for r in sau["lech"] if r["ma"] == "L1"]
    assert len(l1) == 1 and l1[0]["id"] == ds[0].id
    assert "Báo giá" in l1[0]["crm_ghi"] and "Thi công" in l1[0]["bang_chung"]
    assert set(l1[0]["phong_lien_quan"]) == {"PURCHASING", "OPS"}
    assert _phong(sau, "PURCHASING")["diem"] == _phong(truoc, "PURCHASING")["diem"]
    assert _phong(sau, "PURCHASING")["thanh_phan"] == _phong(truoc, "PURCHASING")["thanh_phan"]
    assert _phong(sau, "PURCHASING")["trang_thai"]["lech"] == 1


@pytest.mark.asyncio
async def test_l2_l4_l5_va_tre_han_theo_vn_today(client, db_session, admin_user):
    lead = await _lead(db_session, "Lead chưa thắng", "potential")
    l2 = await _du_an(db_session, "design", lead_id=lead.id)
    l4 = await _du_an(db_session, "construction", progress=100)
    l5a = await _du_an(db_session, "acceptance", handover_date=_truoc(1))
    l5b = await _du_an(db_session, "construction", start_date=_now() + timedelta(days=5))
    # Trễ: một hạn naive, một hạn tz-aware — không được văng lỗi so naive/aware
    tre = await _du_an(db_session, "construction", target_end_date=_truoc(2))
    tre2 = await _du_an(db_session, "acceptance",
                        target_end_date=datetime.now(timezone.utc) - timedelta(days=3))
    await _du_an(db_session, "construction", target_end_date=_now() + timedelta(days=3))
    ban_giao_hom_nay = await _du_an(db_session, "acceptance", handover_date=_now())
    await db_session.commit()
    data = await _get(client, admin_user)
    co = {(r["ma"], r["id"]) for r in data["lech"]}
    assert ("L5", ban_giao_hom_nay.id) not in co
    assert ("L2", l2.id) in co
    assert ("L4", l4.id) in co
    assert ("L5", l5a.id) in co
    assert ("L5", l5b.id) in co
    assert ("L5", tre.id) not in co and ("L5", tre2.id) not in co
    assert _phong(data, "OPS")["tre_han"] == 2
    # Vắng dấu vết không bao giờ là lệch
    assert all(r["bang_chung"] for r in data["lech"])


# ── 10. Nhắc ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nhac_commit_chan_trung_va_gioi_han_2_tin(client, db_session, db_engine, admin_user, tp, tele):
    a = await _du_an(db_session, "construction")
    b = await _du_an(db_session, "construction")
    await db_session.commit()
    h = auth_header(admin_user)
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    assert r.status_code == 200, r.text
    assert r.json() == {"da_gui": [{"phong": "OPS", "nguoi": "TP Giám sát", "telegram": True,
                                    "thong_bao_may": False}], "bo_qua": []}
    assert "/doi-chieu?phong=OPS" in tele[0][1] and "<a href=" in tele[0][1]

    # Đọc lại bằng session MỚI → đã commit
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s2:
        n = (await s2.execute(select(Notification).where(Notification.type == "du_lieu_chung"))).scalars().all()
        assert [x.ref_id for x in n] == [f"dlc:OPS:{vn_today().isoformat()}"]
        assert n[0].link == "/doi-chieu?phong=OPS"

    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    assert r.json() == {"da_gui": [], "bo_qua": [{"phong": "OPS", "ly_do": "da_nhac_hom_nay"}]}

    # Dự án chưa có giám sát → hỏi lại rơi về trưởng phòng (tin thứ 2 trong ngày)
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS", "id": a.id})
    assert [x["nguoi"] for x in r.json()["da_gui"]] == ["TP Giám sát"]
    # Tin thứ 3 cho cùng người trong ngày → bỏ qua
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS", "id": b.id})
    assert r.json() == {"da_gui": [], "bo_qua": [{"phong": "OPS", "ly_do": "vuot_2_tin"}]}

    # Phòng chưa có trưởng phòng
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "PURCHASING"})
    assert r.json() == {"da_gui": [], "bo_qua": [{"phong": "PURCHASING", "ly_do": "khong_co_truong_phong"}]}

    # Hôm nay: phòng đã nhắc không còn thẻ «nhắc», thẻ OPS lan_nhac_cuoi có giờ
    data = await _get(client, admin_user)
    assert all(t["phong"] != "OPS" for t in data["hom_nay"])
    assert _phong(data, "OPS")["lan_nhac_cuoi"]["luc"]


@pytest.mark.asyncio
async def test_hoi_lai_ops_co_giam_sat_gan_nut_baocao(client, db_session, admin_user, tp, tele):
    gs = await _user(db_session, "Giám sát D", "giam_sat_thi_cong", "OPS", tg=700099)
    p = await _du_an(db_session, "construction", pm_id=gs.id, code="PRJ-2026-7777")
    await db_session.commit()
    r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user),
                          json={"phong": "OPS", "id": p.id, "loai": "du_an"})
    assert r.json()["da_gui"] == [{"phong": "OPS", "nguoi": "Giám sát D", "telegram": True,
                                     "thong_bao_may": False}]
    chat, _text, kw = tele[0]
    assert chat == 700099
    nut = [b["callback_data"] for hang in kw["reply_markup"]["inline_keyboard"] for b in hang]
    assert "nx:baocao:PRJ-2026-7777" in nut and "nx:suco:PRJ-2026-7777" in nut
    ref = (await db_session.execute(select(Notification.ref_id))).scalar()
    assert ref == f"dlc:hs:{p.id}:{vn_today().isoformat()}"
    data = await _get(client, admin_user)
    dong = next(x for x in data["can_xem"] if x["id"] == p.id)
    assert dong["da_hoi_hom_nay"] is True


@pytest.mark.asyncio
async def test_nhac_chua_xep_gui_ba_truong_phong(client, db_session, admin_user, tp, tele):
    await _du_an(db_session, "paused")
    await db_session.commit()
    data = await _get(client, admin_user)
    assert data["hom_nay"][0]["nut"]["hanh_dong"] == "nhac_chua_xep"
    r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user), json={"phong": "chua_xep"})
    body = r.json()
    assert sorted(x["phong"] for x in body["da_gui"]) == ["DESIGN", "OPS"]
    assert body["bo_qua"] == [{"phong": "PURCHASING", "ly_do": "khong_co_truong_phong"}]
    link = (await db_session.execute(select(Notification.link).where(
        Notification.user_id == tp["DESIGN"].id))).scalar()
    assert link == "/doi-chieu?phong=DESIGN&tab=chua_xep"
    data = await _get(client, admin_user)
    assert data["hom_nay"][0]["da_nhac"]["da_xem"] is False


# ── 11. Đối chiếu ────────────────────────────────────────────────────────────

async def _audit(db, action=None, entity_id=None):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action == action)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    return (await db.execute(q)).scalars().all()


@pytest.mark.asyncio
async def test_doi_chieu_dung_ghi_audit_va_tang_thanh(client, db_session, admin_user, tp):
    p = await _du_an(db_session, "construction")
    await db_session.commit()
    assert _phong(await _get(client, admin_user), "OPS")["thanh_phan"]["doi_chieu"]["dat"] == 0
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={
        "phong": "OPS", "muc": [{"id": p.id, "loai": "du_an", "ket_qua": "dung"}]})
    assert r.json() == {"da_ghi": 1, "da_doi_giai_doan": 0, "loi": []}
    a = await _audit(db_session, "doi_chieu:OPS", p.id)
    assert len(a) == 1 and a[0].entity_type == "project" and json.loads(a[0].after_json) == {"ket_qua": "dung"}
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["doi_chieu"]["dat"] == 1
    # «Đúng» không phải dấu vết → chưa cập nhật, không phải «có dấu vết»
    assert ops["trang_thai"]["chua_cap_nhat"] == 1


@pytest.mark.asyncio
async def test_doi_chieu_sai_giai_doan_tam_dung_da_xong(client, db_session, admin_user, tp):
    a = await _du_an(db_session, "construction")
    b = await _du_an(db_session, "construction")
    c = await _du_an(db_session, "acceptance")
    await db_session.commit()
    h = auth_header(tp["OPS"])

    # tạm dừng thiếu lý do → 422, không ghi gì
    r = await client.post(f"{URL}/doi-chieu", headers=h, json={
        "phong": "OPS", "muc": [{"id": b.id, "ket_qua": "tam_dung"}]})
    assert r.status_code == 422
    assert await _audit(db_session) == []

    r = await client.post(f"{URL}/doi-chieu", headers=h, json={"phong": "OPS", "muc": [
        {"id": a.id, "loai": "du_an", "ket_qua": "sai_giai_doan", "giai_doan_moi": "acceptance"},
        {"id": b.id, "loai": "du_an", "ket_qua": "tam_dung", "ly_do": "Khách chưa chốt bản vẽ nội thất"},
        {"id": c.id, "loai": "du_an", "ket_qua": "da_xong"},
    ]})
    assert r.status_code == 200, r.text
    assert r.json() == {"da_ghi": 3, "da_doi_giai_doan": 1, "loi": []}
    await db_session.refresh(a)
    await db_session.refresh(b)
    await db_session.refresh(c)
    assert a.stage == "acceptance"
    dg = await _audit(db_session, "doi_giai_doan", a.id)
    assert len(dg) == 1 and json.loads(dg[0].after_json) == {"stage": "acceptance", "status": "active"}
    assert b.status == "paused" and b.pause_reason == "Khách chưa chốt bản vẽ nội thất"
    assert c.stage == "acceptance" and c.status == "active"

    data = await _get(client, admin_user)
    assert [x["id"] for x in data["cho_bgd"]] == [c.id]
    assert data["cho_bgd"][0]["boi"] == "TP Giám sát"
    assert _phong(data, "OPS")["trang_thai"]["dang_cho"] == 1


@pytest.mark.asyncio
async def test_doi_chieu_pic_ngoai_phong_vao_loi(client, db_session, tp):
    gs = await _user(db_session, "Giám sát E", "giam_sat_thi_cong", "OPS")
    tk = await _user(db_session, "Thiết kế F", "thiet_ke", "DESIGN")
    p = await _du_an(db_session, "construction")
    q = await _du_an(db_session, "construction")
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={"phong": "OPS", "muc": [
        {"id": p.id, "ket_qua": "dung", "pic_id": tk.id},
        {"id": q.id, "ket_qua": "dung", "pic_id": gs.id},
    ]})
    body = r.json()
    assert [x["id"] for x in body["loi"]] == [p.id]
    assert body["da_ghi"] == 1
    await db_session.refresh(p)
    await db_session.refresh(q)
    assert p.pm_id is None and q.pm_id == gs.id
    assert await _audit(db_session, "doi_chieu:OPS", p.id) == []


@pytest.mark.asyncio
async def test_tat_ca_con_lai_dung_chi_ghi_dong_chua_xu_ly(client, db_session, tp):
    ds = [await _du_an(db_session, "construction") for _ in range(3)]
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={
        "phong": "OPS",
        "muc": [{"id": ds[0].id, "ket_qua": "da_xong"}],
        "tat_ca_con_lai_dung": True,
        "ids_hien_thi": [p.id for p in ds],
    })
    assert r.json()["da_ghi"] == 3
    a0 = await _audit(db_session, "doi_chieu:OPS", ds[0].id)
    assert len(a0) == 1 and json.loads(a0[0].after_json)["ket_qua"] == "da_xong"
    for p in ds[1:]:
        a = await _audit(db_session, "doi_chieu:OPS", p.id)
        assert len(a) == 1 and json.loads(a[0].after_json)["ket_qua"] == "dung"


@pytest.mark.asyncio
async def test_nhan_du_an_cu_ve_phong(client, db_session, admin_user, tp):
    cu = await _du_an(db_session, "paused", status="active")
    await db_session.commit()
    r = await client.get(f"{URL}/doi-chieu?phong=OPS&tab=chua_xep", headers=auth_header(tp["OPS"]))
    assert [x["id"] for x in r.json()["chua_xep"]] == [cu.id]
    # Trưởng phòng chỉ nhận về giai đoạn của phòng mình
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={"phong": "OPS", "muc": [
        {"id": cu.id, "ket_qua": "sai_giai_doan", "giai_doan_moi": "design"}]})
    assert r.json()["loi"][0]["ly_do"] == "chi_nhan_ve_giai_doan_cua_phong"
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={"phong": "OPS", "muc": [
        {"id": cu.id, "ket_qua": "sai_giai_doan", "giai_doan_moi": "construction"}]})
    assert r.json() == {"da_ghi": 1, "da_doi_giai_doan": 1, "loi": []}
    data = await _get(client, admin_user)
    assert data["ngoai_dai"]["chua_xep"] == {"so_luong": 0, "da_xep_tu_moc": 1}
    assert _phong(data, "OPS")["so_ho_so"] == 1
    # Đổi giai đoạn của chính trưởng phòng là dấu vết của OPS
    assert _phong(data, "OPS")["thanh_phan"]["tuoi"]["dat"] == 1


@pytest.mark.asyncio
async def test_doi_chieu_lead_doi_giai_doan(client, db_session, tp):
    l = await _lead(db_session, "Lead đàm phán", "potential", assigned_to=tp["SALES"].id)
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["SALES"]), json={"phong": "SALES", "muc": [
        {"id": l.id, "loai": "lead", "ket_qua": "sai_giai_doan", "giai_doan_moi": "dormant"}]})
    assert r.json() == {"da_ghi": 1, "da_doi_giai_doan": 1, "loi": []}
    await db_session.refresh(l)
    assert l.stage == "dormant"
    act = (await db_session.execute(select(Activity.type).where(Activity.lead_id == l.id))).scalars().all()
    assert act == ["stage_change"]
    a = await _audit(db_session, "doi_chieu:SALES", l.id)
    assert a[0].entity_type == "lead"
    # Sang «Mất» phải đi đường /leads (cần lý do)
    l2 = await _lead(db_session, "Lead khác", "potential", assigned_to=tp["SALES"].id)
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["SALES"]), json={"phong": "SALES", "muc": [
        {"id": l2.id, "loai": "lead", "ket_qua": "sai_giai_doan", "giai_doan_moi": "lost"}]})
    assert r.json()["loi"] == [{"id": l2.id, "ly_do": "giai_doan_khong_hop_le"}]


# ── 12. Audit đổi giai đoạn ở PUT stage và PUT dự án ─────────────────────────

@pytest.mark.asyncio
async def test_put_stage_va_put_du_an_ghi_doi_giai_doan(client, db_session, admin_user):
    p = await _du_an(db_session, "design")
    await db_session.commit()
    h = auth_header(admin_user)
    r = await client.put(f"/api/v1/projects/{p.id}/stage", headers=h, json={"stage": "quotation"})
    assert r.status_code == 200, r.text
    a = await _audit(db_session, "doi_giai_doan", p.id)
    assert len(a) == 1
    assert json.loads(a[0].before_json) == {"stage": "design", "status": "active"}
    assert json.loads(a[0].after_json) == {"stage": "quotation", "status": "active"}

    r = await client.put(f"/api/v1/projects/{p.id}", headers=h, json={"stage": "procurement"})
    assert r.status_code == 200, r.text
    a = await _audit(db_session, "doi_giai_doan", p.id)
    assert len(a) == 2 and json.loads(a[-1].after_json)["stage"] == "procurement"

    # Sửa trường khác không ghi
    r = await client.put(f"/api/v1/projects/{p.id}", headers=h, json={"address": "1 Hai Bà Trưng"})
    assert r.status_code == 200
    assert len(await _audit(db_session, "doi_giai_doan", p.id)) == 2

    # 409 con_viec_mo vẫn giữ, không ghi audit
    await _viec(db_session, p, "acceptance", "Bàn giao")
    await db_session.commit()
    r = await client.put(f"/api/v1/projects/{p.id}/stage", headers=h, json={"stage": "completed"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "con_viec_mo"
    assert len(await _audit(db_session, "doi_giai_doan", p.id)) == 2


# ── 13. Đổi stage lead hàng loạt ghi Activity ────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_change_stage_ghi_activity(client, db_session, admin_user):
    l = await _lead(db_session, "Lead hàng loạt", "new")
    await db_session.commit()
    r = await client.post("/api/v1/leads/bulk/stage", headers=auth_header(admin_user),
                          json={"lead_ids": [l.id], "new_stage": "interested"})
    assert r.status_code == 200 and r.json()["updated"] == 1
    act = (await db_session.execute(select(Activity).where(Activity.lead_id == l.id))).scalars().all()
    assert [x.type for x in act] == ["stage_change"]
    assert "Đang tư vấn" in act[0].content


# ── 14. send_telegram không reply_markup → payload y cũ ──────────────────────

@pytest.mark.asyncio
async def test_send_telegram_payload_khong_doi(monkeypatch):
    import httpx
    from app.services import telegram_notify

    monkeypatch.setattr(telegram_notify.get_settings(), "TELEGRAM_BOT_TOKEN", "test-token", raising=False)
    da_gui: list[dict] = []

    class _Resp:
        status_code = 200
        text = "ok"

        def json(self):
            return {"ok": True}

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, json):
            da_gui.append(json)
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    assert await telegram_notify.send_telegram(-100123, "xin chào") is True
    assert da_gui[-1] == {"chat_id": -100123, "text": "xin chào", "parse_mode": "HTML"}
    nut = {"inline_keyboard": [[{"text": "A", "callback_data": "nx:baocao:X"}]]}
    assert await telegram_notify.send_telegram(-100123, "có nút", reply_markup=nut) is True
    assert da_gui[-1]["reply_markup"] == nut


# ── 15. GET chỉ đọc + cache ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_khong_ghi_va_cache(client, db_session, admin_user, tp, tele):
    p = await _du_an(db_session, "construction")
    await _lead(db_session, "Lead x", "new")
    await db_session.commit()

    async def _dem():
        kq = []
        for m in (AuditLog, Notification, SystemSetting, Activity, Project, TaskActivity):
            kq.append((await db_session.execute(select(func.count()).select_from(m))).scalar())
        return kq

    truoc = await _dem()
    cache.clear_prefix("dashboard")
    h = auth_header(admin_user)
    r1 = await client.get(URL, headers=h)
    r2 = await client.get(URL, headers=h)
    assert r1.status_code == r2.status_code == 200
    assert await _dem() == truoc
    assert r1.json()["cap_nhat_luc"] == r2.json()["cap_nhat_luc"]

    await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={
        "phong": "OPS", "muc": [{"id": p.id, "ket_qua": "dung"}]})
    r3 = await client.get(URL, headers=h)
    assert r3.json()["cap_nhat_luc"] != r1.json()["cap_nhat_luc"]
    r4 = await client.get(URL, headers=h)
    await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    r5 = await client.get(URL, headers=h)
    assert r5.json()["cap_nhat_luc"] != r4.json()["cap_nhat_luc"]


@pytest.mark.asyncio
async def test_cau_hinh_tu_system_setting(client, db_session, admin_user):
    db_session.add(SystemSetting(key="du_lieu_chung", value=json.dumps(
        {"cua_so": {"OPS": 3, "lead": {"new": 1}}, "moc_bat_dau": "2026-01-01"})))
    await db_session.commit()
    data = await _get(client, admin_user)
    cs = data["cau_hinh"]["cua_so"]
    assert cs["OPS"] == 3 and cs["DESIGN"] == CAU_HINH_MAC_DINH["cua_so"]["DESIGN"]
    assert cs["lead"]["new"] == 1 and cs["lead"]["potential"] == 14
    assert data["moc_bat_dau"] == "2026-01-01"
    assert data["chay_thu"] is False   # 01/01 + 60 ngày đã qua


# ── 16. Điểm không chảy vào thưởng/lương/KPI ─────────────────────────────────

def test_khong_module_thuong_luong_kpi_doc_du_lieu_chung():
    goc = Path(__file__).resolve().parents[1] / "app"
    tep = [f for f in goc.rglob("*.py")
           if any(k in f.name for k in ("kpi_engine", "che_do_thuong", "payroll"))]
    assert tep, "không tìm thấy module thưởng/lương/KPI để kiểm"
    for f in tep:
        assert "du_lieu_chung" not in f.read_text(encoding="utf-8"), f



# ── Vá sau review đối kháng 20/11 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l2_danh_dau_lead_kd_lech(client, db_session, admin_user, tp):
    """L2 gắn cả vào lead → thẻ KD đếm được «lệch» và can_xem có dòng lead lệch."""
    lead = await _lead(db_session, "Lead có dự án", "potential", assigned_to=tp["SALES"].id)
    await _du_an(db_session, "design", lead_id=lead.id)
    await db_session.commit()
    data = await _get(client, admin_user)
    kd = _phong(data, "SALES")
    assert kd["trang_thai"]["lech"] == 1
    dong = next(x for x in data["can_xem"] if x["id"] == lead.id)
    assert dong["loai"] == "lead" and dong["trang_thai"] == "lech"
    # L2 không lan sang các phòng khác
    assert _phong(data, "DESIGN")["trang_thai"]["lech"] == 0


@pytest.mark.asyncio
async def test_bgd_doi_chieu_khong_lam_ops_tuoi(client, db_session, admin_user, tp):
    """Đối chiếu có sửa gán dấu vết theo phòng NGƯỜI BẤM — BGĐ sửa hộ không làm OPS tươi."""
    gs = await _user(db_session, "Giám sát G", "giam_sat_thi_cong", "OPS")
    a = await _du_an(db_session, "construction")
    b = await _du_an(db_session, "construction")
    c = await _du_an(db_session, "construction")
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(admin_user), json={"phong": "OPS", "muc": [
        {"id": a.id, "ket_qua": "da_xong"},
        {"id": b.id, "ket_qua": "dung", "pic_id": gs.id},
    ]})
    assert r.json() == {"da_ghi": 2, "da_doi_giai_doan": 0, "loi": []}
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["tuoi"] == {"dat": 0, "tong": 3}
    assert ops["trang_thai"]["co_dau_vet"] == 0
    # Đối chứng: trưởng phòng OPS tự bấm thì là dấu vết của OPS
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(tp["OPS"]), json={"phong": "OPS", "muc": [
        {"id": c.id, "ket_qua": "da_xong"}]})
    assert r.json()["da_ghi"] == 1
    ops = _phong(await _get(client, admin_user), "OPS")
    assert ops["thanh_phan"]["tuoi"]["dat"] == 1


@pytest.mark.asyncio
async def test_nhac_lead_qua_phong_khac_kd_bi_400(client, db_session, admin_user, tp, tele):
    lead = await _lead(db_session, "Lead bí mật", "potential", assigned_to=tp["SALES"].id)
    await db_session.commit()
    for phong in ("DESIGN", "PURCHASING", "OPS"):
        r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user),
                              json={"phong": phong, "id": lead.id, "loai": "lead"})
        assert r.status_code == 400, (phong, r.text)
    assert (await db_session.execute(select(func.count(Notification.id)))).scalar() == 0
    assert tele == []


@pytest.mark.asyncio
async def test_pic_id_khong_hop_le_vao_loi_khong_500(client, db_session, admin_user, tp):
    """BGĐ cũng bị kiểm pic_id: không tồn tại / nghỉ việc / sai phòng / phòng PM cũ → loi."""
    gs = await _user(db_session, "Giám sát H", "giam_sat_thi_cong", "OPS")
    nghi = await _user(db_session, "Giám sát nghỉ", "giam_sat_thi_cong", "OPS")
    nghi.is_active = False
    tk = await _user(db_session, "Thiết kế I", "thiet_ke", "DESIGN")
    pm_cu = await _user(db_session, "PM cũ", "giam_sat_thi_cong", "PM")
    ds = [await _du_an(db_session, "construction") for _ in range(5)]
    await db_session.commit()
    r = await client.post(f"{URL}/doi-chieu", headers=auth_header(admin_user), json={"phong": "OPS", "muc": [
        {"id": ds[0].id, "ket_qua": "dung", "pic_id": "khong-ton-tai"},
        {"id": ds[1].id, "ket_qua": "dung", "pic_id": nghi.id},
        {"id": ds[2].id, "ket_qua": "dung", "pic_id": tk.id},
        {"id": ds[3].id, "ket_qua": "dung", "pic_id": pm_cu.id},
        {"id": ds[4].id, "ket_qua": "dung", "pic_id": gs.id},
    ]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["loi"] == [{"id": p.id, "ly_do": "pic_khong_hop_le"} for p in ds[:4]]
    assert body["da_ghi"] == 1
    for p in ds:
        await db_session.refresh(p)
    assert [p.pm_id for p in ds] == [None, None, None, None, gs.id]


@pytest.mark.asyncio
async def test_truong_phong_kd_chi_thay_va_ghi_lead_trong_pham_vi(client, db_session, admin_user, tp, sales_user):
    gs = await _user(db_session, "Giám sát J", "giam_sat_thi_cong", "OPS")
    minh = await _lead(db_session, "Lead của TP", "potential", assigned_to=tp["SALES"].id)
    cung_phong = await _lead(db_session, "Lead sale cùng phòng", "survey_scheduled", assigned_to=sales_user.id)
    chua_giao = await _lead(db_session, "Lead chưa giao", "potential")
    ngoai = await _lead(db_session, "Lead người phòng khác", "potential", assigned_to=gs.id)
    moi = await _lead(db_session, "Lead mới", "new", assigned_to=tp["SALES"].id)
    await db_session.commit()
    h = auth_header(tp["SALES"])

    r = await client.get(f"{URL}/doi-chieu?phong=SALES", headers=h)
    assert {x["id"] for x in r.json()["ho_so"]} == {minh.id, cung_phong.id}
    r = await client.get(f"{URL}/doi-chieu?phong=SALES", headers=auth_header(admin_user))
    assert {x["id"] for x in r.json()["ho_so"]} == {minh.id, cung_phong.id, chua_giao.id, ngoai.id}

    r = await client.post(f"{URL}/doi-chieu", headers=h, json={
        "phong": "SALES",
        "muc": [
            {"id": ngoai.id, "loai": "lead", "ket_qua": "dung"},
            {"id": moi.id, "loai": "lead", "ket_qua": "dung"},             # không phải deal chờ ký
            {"id": chua_giao.id, "loai": "lead", "ket_qua": "sai_giai_doan", "giai_doan_moi": "dormant"},
        ],
        "tat_ca_con_lai_dung": True,
        "ids_hien_thi": [minh.id, cung_phong.id, ngoai.id, chua_giao.id],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["da_ghi"] == 2 and body["da_doi_giai_doan"] == 0
    assert {x["id"] for x in body["loi"]} == {ngoai.id, moi.id, chua_giao.id}
    assert all(x["ly_do"] == "khong_phai_ho_so_cua_phong" for x in body["loi"])
    ghi = {a.entity_id for a in await _audit(db_session, "doi_chieu:SALES")}
    assert ghi == {minh.id, cung_phong.id}
    await db_session.refresh(chua_giao)
    assert chua_giao.stage == "potential"


@pytest.mark.asyncio
async def test_tieu_de_telegram_escape_ten_khach(client, db_session, admin_user, tp, tele):
    lead = await _lead(db_session, 'Anh A & chị <a href="x">B</a>', "potential", assigned_to=tp["SALES"].id)
    await db_session.commit()
    r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user),
                          json={"phong": "SALES", "id": lead.id, "loai": "lead"})
    assert r.status_code == 200, r.text
    _chat, text, _kw = tele[0]
    tieu_de = text.split("\n", 1)[0]
    assert tieu_de == '<b>Hỏi lại lead Anh A &amp; chị &lt;a href="x"&gt;B&lt;/a&gt;</b>'
    assert '<a href="x">' not in text
    # Trong app tiêu đề hiện nguyên văn → lưu chữ thường, không lưu bản đã escape.
    tb = (await db_session.execute(
        select(Notification).where(Notification.type == "du_lieu_chung", Notification.ref_id.like("dlc:hs:%"))
    )).scalars().all()
    assert [n.title for n in tb] == ['Hỏi lại lead Anh A & chị <a href="x">B</a>']


@pytest.mark.asyncio
async def test_web_push_bo_the_va_giai_ma_thuc_the(db_session, admin_user):
    from app.services.web_push import KHOA_HANG_DOI
    db_session.add(Notification(user_id=admin_user.id, type="du_lieu_chung", title="Hỏi lại lead A &amp; B",
                                body='Lead A &amp; B\n<a href="https://x">Mở danh sách</a>'))
    await db_session.flush()
    muc = db_session.sync_session.info[KHOA_HANG_DOI][-1]
    assert muc["title"] == "Hỏi lại lead A & B"
    assert muc["body"] == "Lead A & B\nMở danh sách"
    await db_session.rollback()


@pytest.mark.asyncio
async def test_gioi_han_do_dai_doi_chieu_422(client, db_session, tp):
    h = auth_header(tp["OPS"])
    muc = {"id": _uid(), "ket_qua": "dung"}
    for body in (
        {"phong": "OPS", "muc": [muc] * 501},
        {"phong": "OPS", "ids_hien_thi": [_uid()] * 1001, "tat_ca_con_lai_dung": True},
        {"phong": "OPS", "ids_hien_thi": ["x" * 65]},
        {"phong": "OPS", "muc": [{**muc, "ket_qua": "tam_dung", "ly_do": "x" * 501}]},
        {"phong": "OPS", "muc": [{**muc, "pic_id": "x" * 37}]},
        {"phong": "OPS", "muc": [{**muc, "id": "x" * 65}]},
    ):
        r = await client.post(f"{URL}/doi-chieu", headers=h, json=body)
        assert r.status_code == 422, r.text[:200]
    assert await _audit(db_session) == []


@pytest.mark.asyncio
async def test_phong_pm_cu_khong_duoc_moi_thao_tac_backend_tu_choi(client, db_session, admin_user, tp, tele):
    """Phòng 'PM' cũ: vẫn tính dấu vết cho OPS, nhưng không vào danh sách chọn PIC,
    không được /doi-chieu, không nhận tin nhắc trưởng phòng OPS."""
    gs_pm = await _user(db_session, "Giám sát PM", "giam_sat_thi_cong", "PM")
    tp_pm = await _user(db_session, "TP phòng PM", "operation_leader", "PM", tg=700777)
    gs = await _user(db_session, "Giám sát K", "giam_sat_thi_cong", "OPS")
    p = await _du_an(db_session, "construction")
    t = await _viec(db_session, p, "construction", "Thi công")
    db_session.add(TaskActivity(task_id=t.id, user_id=gs_pm.id, content="Báo cáo", created_at=_truoc(1)))
    await db_session.commit()

    r = await client.get(f"{URL}/doi-chieu?phong=OPS", headers=auth_header(admin_user))
    ids = {x["id"] for x in r.json()["nguoi_trong_phong"]}
    assert gs.id in ids and gs_pm.id not in ids and tp_pm.id not in ids
    assert (await client.get(f"{URL}/doi-chieu", headers=auth_header(tp_pm))).status_code == 403

    data = await _get(client, admin_user)
    ops = _phong(data, "OPS")
    assert [x["id"] for x in ops["truong_phong"]] == [tp["OPS"].id]
    assert ops["thanh_phan"]["tuoi"]["dat"] == 1      # dấu vết của người phòng PM vẫn tính cho OPS

    r = await client.post(f"{URL}/nhac", headers=auth_header(admin_user), json={"phong": "OPS"})
    assert [x["nguoi"] for x in r.json()["da_gui"]] == ["TP Giám sát"]
    assert 700777 not in [c for c, _t, _k in tele]


@pytest.mark.asyncio
async def test_phong_dau_viec_chu_hoa_van_gan_dau_vet(client, db_session, admin_user):
    p = await _du_an(db_session, "design")
    await _viec(db_session, p, "design", "Bản vẽ", dept="DESIGN", status="in_progress", started_at=_truoc(1))
    q = await _du_an(db_session, "design")
    await _viec(db_session, q, "design", "Bản vẽ", dept="phong-la", status="in_progress", started_at=_truoc(1))
    await db_session.commit()
    tk = _phong(await _get(client, admin_user), "DESIGN")
    assert tk["thanh_phan"]["tuoi"] == {"dat": 2, "tong": 2}


@pytest.mark.asyncio
async def test_l1_vat_tu_da_dat_cu_hon_30_ngay_khong_lech(client, db_session, admin_user):
    from app.models.vat_tu import DongPhieuVatTu
    cu = await _du_an(db_session, "quotation")
    moi = await _du_an(db_session, "quotation")
    db_session.add(DongPhieuVatTu(id=_uid(), project_id=cu.id, ma_tu_do="G1", trang_thai="da_dat",
                                  dat_luc=_truoc(40), created_at=_truoc(45), updated_at=_truoc(40)))
    db_session.add(DongPhieuVatTu(id=_uid(), project_id=moi.id, ma_tu_do="G2", trang_thai="da_dat",
                                  dat_luc=_truoc(2), created_at=_truoc(5), updated_at=_truoc(2)))
    await db_session.commit()
    data = await _get(client, admin_user)
    l1 = {r["id"] for r in data["lech"] if r["ma"] == "L1"}
    assert l1 == {moi.id}


# ── Vòng 2 (21/11/2026): kênh nhận thông báo + nhắc cài app ─────────────────

URL_CAI_APP = f"{URL}/nhac-cai-app"


async def _push(db, u):
    """Một máy đã bật «thông báo trên máy» cho user u."""
    from app.models.push_subscription import PushSubscription
    from app.services.web_push import bam_endpoint
    ep = f"https://push.example/{_uid()}"
    db.add(PushSubscription(user_id=u.id, endpoint=ep, endpoint_hash=bam_endpoint(ep), p256dh="k", auth="a"))
    await db.flush()


def _hang_doi_push(db_session) -> list[dict]:
    from app.services.web_push import KHOA_HANG_DOI
    return db_session.sync_session.info.get(KHOA_HANG_DOI, [])


def _xoa_hang_doi_push(db_session) -> None:
    from app.services.web_push import KHOA_HANG_DOI
    db_session.sync_session.info.pop(KHOA_HANG_DOI, None)


@pytest_asyncio.fixture
async def nhom_kenh(db_session, admin_user, executive_user, tp):
    """Đủ kiểu người cho khối «Kênh nhận thông báo».

    - TP Giám sát (OPS): Telegram, chưa bật máy
    - TP Thiết kế (DESIGN): Telegram + đã bật máy
    - TP Kinh doanh (SALES): Telegram, chưa bật máy
    - Giám sát PM (phòng 'PM' cũ → OPS): đã bật máy, không Telegram
    - Giám sát L (OPS): không gì cả → chỉ chuông
    - Kế toán M (ACCT → KHAC): không gì cả
    - Giám đốc (EXEC → KHAC): không gì cả
    - admin (có Telegram) và người đã nghỉ: KHÔNG tính
    """
    gs_pm = await _user(db_session, "Giám sát PM", "giam_sat_thi_cong", "PM")
    gs = await _user(db_session, "Giám sát L", "giam_sat_thi_cong", "OPS")
    kt = await _user(db_session, "Kế toán M", "accountant", "ACCT")
    nghi = await _user(db_session, "Người đã nghỉ", "giam_sat_thi_cong", "OPS")
    nghi.is_active = False
    await _push(db_session, tp["DESIGN"])
    await _push(db_session, gs_pm)
    await db_session.commit()
    return {"gs_pm": gs_pm, "gs": gs, "kt": kt, "nghi": nghi, "exec": executive_user, **tp}


@pytest.mark.asyncio
async def test_truong_phong_co_thong_bao_may_va_co_telegram(client, db_session, admin_user, tp):
    tp_ops_2 = await _user(db_session, "TP Thi công 2", "operation_leader", "OPS")   # không Telegram, không máy
    await _push(db_session, tp["DESIGN"])
    await _push(db_session, tp["DESIGN"])       # 2 máy vẫn là 1 người đã bật
    await db_session.commit()
    data = await _get(client, admin_user)
    ops = {x["id"]: x for x in _phong(data, "OPS")["truong_phong"]}
    assert ops[tp["OPS"].id] == {"id": tp["OPS"].id, "ten": "TP Giám sát", "co_telegram": True,
                                 "co_thong_bao_may": False}
    assert ops[tp_ops_2.id] == {"id": tp_ops_2.id, "ten": "TP Thi công 2", "co_telegram": False,
                                "co_thong_bao_may": False}
    tk = _phong(data, "DESIGN")["truong_phong"]
    assert tk == [{"id": tp["DESIGN"].id, "ten": "TP Thiết kế", "co_telegram": True, "co_thong_bao_may": True}]
    assert _phong(data, "PURCHASING")["truong_phong"] == []


@pytest.mark.asyncio
async def test_kenh_thong_bao_dem_dung(client, db_session, admin_user, nhom_kenh):
    k = (await _get(client, admin_user))["kenh_thong_bao"]
    assert set(k) == {"tong", "co_thong_bao_may", "co_telegram", "chi_chuong", "theo_phong", "chua_bat",
                      "lan_nhac_cai_app_cuoi"}
    # admin + người đã nghỉ không tính
    assert (k["tong"], k["co_thong_bao_may"], k["co_telegram"], k["chi_chuong"]) == (7, 2, 3, 3)
    theo = {x["phong"]: x for x in k["theo_phong"]}
    assert [x["phong"] for x in k["theo_phong"]] == ["SALES", "DESIGN", "PURCHASING", "OPS", "KHAC"]
    assert theo["SALES"] == {"phong": "SALES", "ten": "Kinh doanh", "tong": 1, "co_thong_bao_may": 0,
                             "co_telegram": 1, "chi_chuong": 0}
    assert theo["DESIGN"] == {"phong": "DESIGN", "ten": "Thiết kế", "tong": 1, "co_thong_bao_may": 1,
                              "co_telegram": 1, "chi_chuong": 0}
    assert theo["PURCHASING"]["tong"] == 0
    # Phòng 'PM' cũ tính vào OPS
    assert (theo["OPS"]["tong"], theo["OPS"]["co_thong_bao_may"], theo["OPS"]["co_telegram"],
            theo["OPS"]["chi_chuong"]) == (3, 1, 1, 1)
    assert (theo["KHAC"]["tong"], theo["KHAC"]["chi_chuong"]) == (2, 2)
    assert theo["KHAC"]["ten"] == "Bộ phận khác"
    # Chưa bật máy: sắp theo phòng rồi tên; không có người đã bật, admin, người nghỉ
    n = nhom_kenh
    assert k["chua_bat"] == [
        {"id": n["SALES"].id, "ten": "TP Kinh doanh", "phong": "SALES", "co_telegram": True},
        {"id": n["gs"].id, "ten": "Giám sát L", "phong": "OPS", "co_telegram": False},
        {"id": n["OPS"].id, "ten": "TP Giám sát", "phong": "OPS", "co_telegram": True},
        {"id": n["exec"].id, "ten": "Giám đốc", "phong": "KHAC", "co_telegram": False},
        {"id": n["kt"].id, "ten": "Kế toán M", "phong": "KHAC", "co_telegram": False},
    ]
    assert k["lan_nhac_cai_app_cuoi"] is None


@pytest.mark.asyncio
async def test_nhac_them_dong_cai_app_khi_chua_bat_may(client, db_session, admin_user, tp, tele):
    await _push(db_session, tp["DESIGN"])
    await _du_an(db_session, "construction")
    await _du_an(db_session, "design")
    await db_session.commit()
    _xoa_hang_doi_push(db_session)
    h = auth_header(admin_user)

    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    assert r.json()["da_gui"] == [{"phong": "OPS", "nguoi": "TP Giám sát", "telegram": True,
                                   "thong_bao_may": False}]
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "DESIGN"})
    assert r.json()["da_gui"] == [{"phong": "DESIGN", "nguoi": "TP Thiết kế", "telegram": True,
                                   "thong_bao_may": True}]

    than = dict((await db_session.execute(select(Notification.user_id, Notification.body).where(
        Notification.type == "du_lieu_chung"))).all())
    # Chưa bật máy → dòng cuối mời cài app, link tuyệt đối tới /cai-app
    dong_cuoi = than[tp["OPS"].id].split("\n")[-1]
    assert dong_cuoi.startswith('Cài JAMA HOME lên điện thoại và bật thông báo để nhận nhắc ngay: <a href="http')
    assert '/cai-app">Hướng dẫn 1 phút</a>' in dong_cuoi
    assert "Mở danh sách đối chiếu" in than[tp["OPS"].id]
    # Đã bật máy → không thêm
    assert "cai-app" not in than[tp["DESIGN"].id]
    assert than[tp["DESIGN"].id].split("\n")[-1].endswith("Mở danh sách đối chiếu (~2 phút)</a>")
    # Telegram nhận đúng thân tin
    assert "/cai-app" in tele[0][1] and "/cai-app" not in tele[1][1]
    # Notification vừa tạo được đưa vào hàng đợi Web Push (đẩy sau commit)
    hang = _hang_doi_push(db_session)
    assert {(x["user_id"], x["url"]) for x in hang} == {
        (tp["OPS"].id, "/doi-chieu?phong=OPS"), (tp["DESIGN"].id, "/doi-chieu?phong=DESIGN")}
    assert all("<a" not in x["body"] for x in hang)
    _xoa_hang_doi_push(db_session)


@pytest.mark.asyncio
async def test_nhac_cai_app_chi_nguoi_chua_bat_loc_phong_ids_1_tin_ngay(
        client, db_session, db_engine, admin_user, nhom_kenh, tele):
    n = nhom_kenh
    h = auth_header(admin_user)
    _xoa_hang_doi_push(db_session)

    # Lọc phòng OPS: TP Giám sát + Giám sát L; Giám sát PM đã bật máy → bỏ
    r = await client.post(URL_CAI_APP, headers=h, json={"phong": "OPS"})
    assert r.status_code == 200, r.text
    assert r.json() == {"da_gui": 2, "qua_telegram": 1, "bo_qua_da_nhac": 0}
    assert [c for c, _t, _k in tele] == [700001]
    assert "/cai-app" in tele[0][1] and tele[0][1].startswith("<b>Cài JAMA HOME lên điện thoại</b>")

    # Đã commit — đọc lại bằng session MỚI
    hom_nay = vn_today().isoformat()
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s2:
        ds = (await s2.execute(select(Notification).where(Notification.type == "nhac_cai_app"))).scalars().all()
        assert {x.user_id for x in ds} == {n["OPS"].id, n["gs"].id}
        for x in ds:
            assert x.link == "/cai-app"
            assert x.ref_id == f"cai_app:{hom_nay}"
            assert x.title == "Cài JAMA HOME lên điện thoại"
            assert 2 <= len(x.body.split("\n")) <= 3
            assert '<a href="http' in x.body and '/cai-app">' in x.body

    # Được đưa vào hàng đợi Web Push
    hang = _hang_doi_push(db_session)
    assert sorted(x["user_id"] for x in hang) == sorted([n["OPS"].id, n["gs"].id])
    assert all(x["url"] == "/cai-app" and x["tag"] == f"cai_app:{hom_nay}" for x in hang)
    _xoa_hang_doi_push(db_session)

    # Lần 2 trong ngày → bỏ qua, kể cả khi người nhận ĐÃ ĐỌC tin (chặn theo created_at)
    await db_session.execute(Notification.__table__.update().where(
        Notification.user_id == n["OPS"].id).values(read=True))
    await db_session.commit()
    r = await client.post(URL_CAI_APP, headers=h, json={"phong": "OPS"})
    assert r.json() == {"da_gui": 0, "qua_telegram": 0, "bo_qua_da_nhac": 2}

    # Lọc ids: người đã bật máy (TP Thiết kế), admin, người nghỉ, id lạ → không gửi
    r = await client.post(URL_CAI_APP, headers=h, json={
        "ids": [n["kt"].id, n["DESIGN"].id, admin_user.id, n["nghi"].id, "khong-ton-tai"]})
    assert r.json() == {"da_gui": 1, "qua_telegram": 0, "bo_qua_da_nhac": 0}

    # ids rỗng → không ai (không hiểu thành «gửi tất cả»)
    r = await client.post(URL_CAI_APP, headers=h, json={"ids": []})
    assert r.json() == {"da_gui": 0, "qua_telegram": 0, "bo_qua_da_nhac": 0}

    # Không lọc → mọi người chưa bật còn lại: TP Kinh doanh + Giám đốc
    r = await client.post(URL_CAI_APP, headers=h, json={})
    assert r.json() == {"da_gui": 2, "qua_telegram": 1, "bo_qua_da_nhac": 3}
    nhan = (await db_session.execute(select(Notification.user_id).where(
        Notification.type == "nhac_cai_app"))).scalars().all()
    assert sorted(nhan) == sorted([n["OPS"].id, n["gs"].id, n["kt"].id, n["SALES"].id, n["exec"].id])

    # Không tính vào giới hạn 2 tin «Dữ liệu chung»/người/ngày
    await _du_an(db_session, "construction")
    a = await _du_an(db_session, "construction")
    await db_session.commit()
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    assert [x["nguoi"] for x in r.json()["da_gui"]] == ["TP Giám sát"]
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS", "id": a.id})
    assert [x["nguoi"] for x in r.json()["da_gui"]] == ["TP Giám sát"]


@pytest.mark.asyncio
async def test_nhac_cai_app_chi_bgd_va_gioi_han_body(client, db_session, executive_user, sales_user,
                                                     accountant_user, tp, tele):
    for u in (sales_user, accountant_user, tp["OPS"], tp["DESIGN"]):
        r = await client.post(URL_CAI_APP, headers=auth_header(u), json={"phong": "OPS"})
        assert r.status_code == 403, (u.role, r.text)
    for body in ({"ids": [_uid()] * 201}, {"ids": ["x" * 65]}, {"phong": "KHAC"}, {"phong": "chua_xep"}):
        r = await client.post(URL_CAI_APP, headers=auth_header(executive_user), json=body)
        assert r.status_code == 422, (body, r.text[:200])
    assert (await db_session.execute(select(func.count(Notification.id)))).scalar() == 0
    assert tele == []
    # Executive (BGĐ) được nhắc
    r = await client.post(URL_CAI_APP, headers=auth_header(executive_user), json={"phong": "DESIGN"})
    assert r.status_code == 200, r.text
    assert r.json() == {"da_gui": 1, "qua_telegram": 1, "bo_qua_da_nhac": 0}


@pytest.mark.asyncio
async def test_lan_nhac_cai_app_cuoi(client, db_session, admin_user, nhom_kenh, tele):
    n = nhom_kenh
    # Lần nhắc cũ 3 ngày trước — không tính vào số người của lần mới nhất
    db_session.add(Notification(user_id=n["kt"].id, type="nhac_cai_app", title="x",
                                ref_id="cai_app:cu", created_at=_truoc(3)))
    await db_session.commit()
    h = auth_header(admin_user)
    cache.clear_prefix("dashboard")
    cu = (await client.get(URL, headers=h)).json()["kenh_thong_bao"]["lan_nhac_cai_app_cuoi"]
    assert cu["so_nguoi"] == 1
    assert datetime.fromisoformat(cu["luc"]) < datetime.now(timezone.utc) - timedelta(days=2)

    r = await client.post(URL_CAI_APP, headers=h, json={"phong": "OPS"})
    assert r.json()["da_gui"] == 2
    # POST xoá cache → GET kế tiếp (không tự xoá cache) thấy ngay lần nhắc mới
    moi = (await client.get(URL, headers=h)).json()["kenh_thong_bao"]["lan_nhac_cai_app_cuoi"]
    assert moi["so_nguoi"] == 2
    assert datetime.fromisoformat(moi["luc"]) > datetime.now(timezone.utc) - timedelta(minutes=5)
    # Nhắc thêm người trong cùng ngày → số người cộng dồn trong ngày
    await client.post(URL_CAI_APP, headers=h, json={"ids": [n["kt"].id]})
    moi = (await client.get(URL, headers=h)).json()["kenh_thong_bao"]["lan_nhac_cai_app_cuoi"]
    assert moi["so_nguoi"] == 3
    # Nhắc cài app không làm thay đổi «Nhắc trưởng phòng» của thẻ phòng
    data = await _get(client, admin_user)
    assert _phong(data, "OPS")["lan_nhac_cuoi"] is None


# ── Xếp hàng lượt gửi nhắc (chống gửi trùng khi 2 request chồng nhau) ────────

class _BindGia:
    def __init__(self, ten):
        self.dialect = type("D", (), {"name": ten})()


class _DbGia:
    def __init__(self, ten):
        self._bind = _BindGia(ten)
        self.cau: list[tuple[str, dict]] = []

    def get_bind(self):
        return self._bind

    async def execute(self, cau, tham_so=None):
        self.cau.append((str(cau), tham_so or {}))


@pytest.mark.asyncio
async def test_xep_hang_gui_khoa_advisory_tren_postgres_bo_qua_sqlite():
    from app.api.du_lieu_chung import _xep_hang_gui

    pg = _DbGia("postgresql")
    await _xep_hang_gui(pg, "du_lieu_chung:nhac_cai_app")
    assert pg.cau == [("SELECT pg_advisory_xact_lock(hashtext(:k))", {"k": "du_lieu_chung:nhac_cai_app"})]

    lite = _DbGia("sqlite")
    await _xep_hang_gui(lite, "du_lieu_chung:nhac_cai_app")
    assert lite.cau == []


@pytest.mark.asyncio
async def test_nhac_va_nhac_cai_app_xep_hang_truoc_khi_doc_da_nhac(
        client, db_session, admin_user, nhom_kenh, tele, monkeypatch):
    """Khoá phải lấy TRƯỚC khi đọc «đã nhắc hôm nay» — lấy sau thì vẫn đua."""
    import app.api.du_lieu_chung as m

    thu_tu: list[str] = []

    async def khoa_gia(db, khoa):
        thu_tu.append(f"khoa:{khoa}")

    goc_push, goc_nap = m._nguoi_co_push, m._nap

    async def push_ghi(db):
        thu_tu.append("doc_push")
        return await goc_push(db)

    async def nap_ghi(db):
        thu_tu.append("nap")
        return await goc_nap(db)

    monkeypatch.setattr(m, "_xep_hang_gui", khoa_gia)
    monkeypatch.setattr(m, "_nguoi_co_push", push_ghi)
    monkeypatch.setattr(m, "_nap", nap_ghi)
    h = auth_header(admin_user)

    r = await client.post(URL_CAI_APP, headers=h, json={"phong": "OPS"})
    assert r.status_code == 200, r.text
    assert thu_tu[0] == "khoa:du_lieu_chung:nhac_cai_app" and "doc_push" in thu_tu[1:]

    thu_tu.clear()
    r = await client.post(f"{URL}/nhac", headers=h, json={"phong": "OPS"})
    assert r.status_code == 200, r.text
    assert thu_tu[0] == "khoa:du_lieu_chung:nhac" and "nap" in thu_tu[1:]

    # Người không phải BGĐ bị chặn trước, không giữ khoá
    thu_tu.clear()
    r = await client.post(URL_CAI_APP, headers=auth_header(nhom_kenh["OPS"]), json={})
    assert r.status_code == 403
    assert thu_tu == []


# ── Vòng 4 (26/11/2026): trưởng phòng XEM cùng trang chính ──────────────────
# Luật: số tổng hợp giống hệt BGĐ, tiền → null, dòng chi tiết chỉ còn hồ sơ người
# đó vốn đã thấy ở trang Dự án / Lead, «Hôm nay» chỉ có thẻ mở, POST nhắc vẫn 403.

LEAD_V4 = ("Lead Hoa Sen", "Lead Mai Vàng", "Lead Lan Tím", "Lead Cúc Trắng")


def _moi_gia_tri(obj, khoa):
    """Mọi giá trị của khoá `khoa` ở mọi tầng JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == khoa:
                yield v
            yield from _moi_gia_tri(v, khoa)
    elif isinstance(obj, list):
        for v in obj:
            yield from _moi_gia_tri(v, khoa)


def _ids(data, loai: str) -> dict[str, set]:
    """id dòng loại `loai` (du_an | lead) trong 4 danh sách chi tiết."""
    du_an = loai == "du_an"
    return {
        "lech": {r["id"] for r in data["lech"] if r["loai"] == loai},
        "can_xem": {r["id"] for r in data["can_xem"] if r["loai"] == loai},
        "cho_bgd": {r["id"] for r in data["cho_bgd"]} if du_an else set(),
        "du_lieu_cu": {r["id"] for r in data["du_lieu_cu"]} if du_an else set(),
    }


def _l2(data) -> dict[str, str]:
    return {r["id"]: r["crm_ghi"] for r in data["lech"] if r["ma"] == "L2"}


@pytest_asyncio.fixture
async def tp4(db_session, tp):
    """Đủ trưởng 4 phòng — fixture `tp` cố ý thiếu Dự toán–Thu mua."""
    tm = await _user(db_session, "TP Thu mua", "dutoan_thumua_leader", "PURCHASING")
    await db_session.commit()
    return {**tp, "PURCHASING": tm}


async def _du_lieu_v4(db, tp4, sales_user) -> dict:
    """4 phòng có hồ sơ + tiền; lead trong/ngoài phạm vi TP KD; L2, L3, L4; dữ liệu cũ; chờ BGĐ.

    Phạm vi lead của TP KD (luật /leads tầng phòng ban): lead giao người phòng KD hoặc
    chính mình — lead chưa giao ai / giao người phòng khác là NGOÀI phạm vi.
    """
    gs = await _user(db, "Giám sát V4", "giam_sat_thi_cong", "OPS")
    lead_trong = await _lead(db, "Lead Hoa Sen", "potential", assigned_to=sales_user.id, deal_value=7e8)
    lead_ngoai = await _lead(db, "Lead Mai Vàng", "potential", deal_value=3e8)           # chưa giao ai
    l3_trong = await _lead(db, "Lead Lan Tím", "signed_design", assigned_to=sales_user.id)
    l3_ngoai = await _lead(db, "Lead Cúc Trắng", "signed_design", assigned_to=gs.id)    # giao người OPS
    tk = await _du_an(db, "design", total_value=9e8, lead_id=lead_trong.id)    # L2 — lead trong phạm vi KD
    tk2 = await _du_an(db, "design", total_value=1e8, lead_id=lead_ngoai.id)   # L2 — lead ngoài phạm vi KD
    bg = await _du_an(db, "quotation", total_value=5e8)
    tc = await _du_an(db, "construction", total_value=2e9, progress=100)       # L4
    cu = await _du_an(db, "paused", total_value=4e8)                           # dữ liệu cũ chưa xếp
    db.add(AuditLog(entity_type="project", entity_id=tc.id, action="doi_chieu:OPS",   # → chờ BGĐ
                    actor_id=tp4["OPS"].id, actor_name="TP Giám sát",
                    after_json=json.dumps({"ket_qua": "da_xong"}), created_at=_truoc(1)))
    await db.commit()
    return {"gs": gs, "lead_trong": lead_trong, "lead_ngoai": lead_ngoai, "l3_trong": l3_trong,
            "l3_ngoai": l3_ngoai, "tk": tk, "tk2": tk2, "bg": bg, "tc": tc, "cu": cu}


@pytest.mark.asyncio
async def test_truong_phong_khong_thay_tien_va_chi_co_the_mo(client, db_session, admin_user, tp4, sales_user):
    """Tiền → null nhưng giữ khoá; nguoi_xem đúng; «Hôm nay» chỉ thẻ mở đối chiếu phòng mình."""
    v = await _du_lieu_v4(db_session, tp4, sales_user)
    bgd = await _get(client, admin_user)
    o = {x["ma"]: x for x in bgd["dai_quy_trinh"]}
    assert (o["lead_mo"]["tong_tien"], o["design"]["tong_tien"], o["construction"]["tong_tien"]) == (1e9, 1e9, 2e9)
    assert [r["gia_tri"] for r in bgd["du_lieu_cu"]] == [4e8]
    assert {t["nut"]["hanh_dong"] for t in bgd["hom_nay"]} == {"nhac_chua_xep", "nhac"}
    assert bgd["nguoi_xem"] == {"loai": "bgd", "phong": None, "xem_tien": True, "thao_tac": True}

    the_mong = {
        "SALES": [("phong_SALES", 2, "/doi-chieu?phong=SALES")],      # KD không nhận dự án cũ
        "DESIGN": [("phong_DESIGN", 2, "/doi-chieu?phong=DESIGN"),
                   ("chua_xep", 1, "/doi-chieu?phong=DESIGN&tab=chua_xep")],
        "PURCHASING": [("phong_PURCHASING", 1, "/doi-chieu?phong=PURCHASING"),
                       ("chua_xep", 1, "/doi-chieu?phong=PURCHASING&tab=chua_xep")],
        "OPS": [("phong_OPS", 1, "/doi-chieu?phong=OPS"),
                ("chua_xep", 1, "/doi-chieu?phong=OPS&tab=chua_xep")],
    }
    for phong, u in tp4.items():
        data = await _get(client, u)
        assert data["nguoi_xem"] == {"loai": "truong_phong", "phong": phong, "xem_tien": False,
                                     "thao_tac": False}
        tien = [*_moi_gia_tri(data, "tong_tien"), *_moi_gia_tri(data, "gia_tri")]
        assert tien and all(x is None for x in tien), phong
        # Khoá tiền vẫn còn — giao diện nhận `number | null`
        assert len(data["dai_quy_trinh"]) == len(bgd["dai_quy_trinh"])
        assert all("tong_tien" in x for x in data["dai_quy_trinh"])
        assert data["can_xem"] and all("gia_tri" in x for x in data["can_xem"])
        assert [r["id"] for r in data["du_lieu_cu"]] == [v["cu"].id]
        assert all("gia_tri" in x for x in data["du_lieu_cu"])
        assert [(t["ma"], t["so_luong"], t["nut"]["link"]) for t in data["hom_nay"]] == the_mong[phong]
        assert all(t["nut"]["hanh_dong"] == "mo" and t["da_nhac"] is None for t in data["hom_nay"])
        assert [r["id"] for r in data["cho_bgd"]] == [v["tc"].id]


@pytest.mark.asyncio
async def test_truong_phong_so_tong_hop_giong_het_bgd(client, db_session, admin_user, tp4, sales_user):
    """Bản trưởng phòng là bản BGĐ đem lọc — số tổng hợp không lệch một đơn vị nào."""
    await _du_lieu_v4(db_session, tp4, sales_user)
    # Thêm hồ sơ để OPS và KD đủ ≥3 hồ sơ — có điểm thật để so, không so None với None
    for ngay in (1, 4, 12):
        p = await _du_an(db_session, "construction", total_value=ngay * 1e8)
        await _viec(db_session, p, "construction", "Thi công", status="in_progress", started_at=_truoc(ngay))
    await _lead(db_session, "Lead Đào", "new", assigned_to=sales_user.id)
    await _lead(db_session, "Lead Mận", "interested", tao=_truoc(20))
    await db_session.commit()
    bgd = await _get(client, admin_user)
    assert _phong(bgd, "OPS")["diem"] is not None and _phong(bgd, "SALES")["diem"] is not None

    def _bo_tien(dai):
        return [{k: x for k, x in o.items() if k != "tong_tien"} for o in dai]

    def _bo_chua_bat(kenh):
        return {k: x for k, x in kenh.items() if k != "chua_bat"}

    for phong, u in tp4.items():
        data = await _get(client, u)
        for k in ("phan_anh", "ngoai_dai", "phong", "tin_hieu_30_ngay", "cau_hinh",
                  "chay_thu", "chay_thu_den", "moc_bat_dau"):
            assert data[k] == bgd[k], (phong, k)
        assert [x["diem"] for x in data["phong"]] == [x["diem"] for x in bgd["phong"]]
        assert _bo_tien(data["dai_quy_trinh"]) == _bo_tien(bgd["dai_quy_trinh"]), phong
        assert _bo_chua_bat(data["kenh_thong_bao"]) == _bo_chua_bat(bgd["kenh_thong_bao"]), phong


@pytest.mark.asyncio
async def test_truong_phong_dong_du_an_theo_dung_luat_trang_du_an(client, db_session, admin_user, tp4,
                                                                monkeypatch):
    """Dòng dự án ở lech / can_xem / cho_bgd / du_lieu_cu theo ĐÚNG `dieu_kien_pham_vi_du_an`."""
    p = {}
    for ten, stage, kw in (("trong_tc", "construction", {"progress": 100}),
                           ("ngoai_tc", "construction", {"progress": 100}),
                           ("trong_cu", "paused", {}), ("ngoai_cu", "paused", {})):
        p[ten] = await _du_an(db_session, stage, code=f"{ten[:5].upper()}-{_uid()[:8]}", **kw)
    for ten in ("trong_tc", "ngoai_tc"):
        db_session.add(AuditLog(entity_type="project", entity_id=p[ten].id, action="doi_chieu:OPS",
                                actor_id=tp4["OPS"].id, actor_name="TP Giám sát",
                                after_json=json.dumps({"ket_qua": "da_xong"}), created_at=_truoc(1)))
    await db_session.commit()
    bgd = await _get(client, admin_user)
    tc = {p["trong_tc"].id, p["ngoai_tc"].id}
    assert _ids(bgd, "du_an") == {"lech": tc, "can_xem": tc, "cho_bgd": tc,
                                  "du_lieu_cu": {p["trong_cu"].id, p["ngoai_cu"].id}}

    # 1) Luật thật: thấy đúng những dự án trang Dự án cho chính người đó thấy
    for phong in ("OPS", "DESIGN"):
        r = await client.get("/api/v1/projects?page_size=200", headers=auth_header(tp4[phong]))
        assert r.status_code == 200, r.text
        mo_duoc = {x["id"] for x in r.json()["items"]}
        data = await _get(client, tp4[phong])
        assert _ids(data, "du_an") == {k: ids & mo_duoc for k, ids in _ids(bgd, "du_an").items()}, phong

    # 2) Trang Dự án siết lại (giả lập) → trang này siết theo ở cả 4 danh sách
    monkeypatch.setattr("app.api.projects.dieu_kien_pham_vi_du_an",
                        lambda user, gom_chua_phan_cong=True: Project.code.like("TRONG-%"))
    for phong in ("OPS", "DESIGN"):
        data = await _get(client, tp4[phong])
        assert _ids(data, "du_an") == {"lech": {p["trong_tc"].id}, "can_xem": {p["trong_tc"].id},
                                       "cho_bgd": {p["trong_tc"].id}, "du_lieu_cu": {p["trong_cu"].id}}, phong
        for k in ("phan_anh", "ngoai_dai", "phong"):
            assert data[k] == bgd[k], (phong, k)          # số tổng hợp vẫn của cả công ty
    # BGĐ không đi qua bộ lọc
    assert _ids(await _get(client, admin_user), "du_an") == _ids(bgd, "du_an")


@pytest.mark.asyncio
async def test_truong_phong_ngoai_kd_khong_co_dong_lead_khong_lo_chu_lead(client, db_session, admin_user,
                                                                         tp4, sales_user):
    v = await _du_lieu_v4(db_session, tp4, sales_user)
    bgd = await _get(client, admin_user)
    assert _l2(bgd) == {v["tk"].id: "Lead đang ở «Đang đàm phán»", v["tk2"].id: "Lead đang ở «Đang đàm phán»"}
    chu_bgd = json.dumps(bgd, ensure_ascii=False)
    assert all(ten in chu_bgd for ten in LEAD_V4)
    for phong in ("DESIGN", "PURCHASING", "OPS"):
        data = await _get(client, tp4[phong])
        assert [r for r in data["lech"] + data["can_xem"] if r["loai"] == "lead"] == [], phong
        # Dòng DỰ ÁN L2 vẫn còn (dự án trong phạm vi) nhưng không lộ giai đoạn lead
        assert _l2(data) == {v["tk"].id: CHU_L2_KHONG_XEM_LEAD, v["tk2"].id: CHU_L2_KHONG_XEM_LEAD}, phong
        chu = json.dumps(data, ensure_ascii=False)
        for ten in (*LEAD_V4, "Đang đàm phán"):
            assert ten not in chu, (phong, ten)


@pytest.mark.asyncio
async def test_truong_phong_kd_chi_thay_lead_trong_pham_vi_trang_chinh(client, db_session, admin_user,
                                                                      tp4, sales_user):
    v = await _du_lieu_v4(db_session, tp4, sales_user)
    bgd = await _get(client, admin_user)
    assert _ids(bgd, "lead")["can_xem"] == {v["lead_trong"].id, v["lead_ngoai"].id}
    assert _ids(bgd, "lead")["lech"] == {v["l3_trong"].id, v["l3_ngoai"].id}

    data = await _get(client, tp4["SALES"])
    assert _ids(data, "lead")["can_xem"] == {v["lead_trong"].id}
    assert _ids(data, "lead")["lech"] == {v["l3_trong"].id}
    # Cùng phạm vi với trang Lead của chính người đó
    r = await client.get("/api/v1/leads?page_size=200", headers=auth_header(tp4["SALES"]))
    assert r.status_code == 200, r.text
    trang_lead = {x["id"] for x in r.json()["items"]}
    assert {v["lead_trong"].id, v["l3_trong"].id} <= trang_lead
    assert not {v["lead_ngoai"].id, v["l3_ngoai"].id} & trang_lead
    # L2: lead trong phạm vi giữ giai đoạn; lead ngoài phạm vi → chữ chung
    assert _l2(data) == {v["tk"].id: "Lead đang ở «Đang đàm phán»", v["tk2"].id: CHU_L2_KHONG_XEM_LEAD}
    chu = json.dumps(data, ensure_ascii=False)
    assert "Lead Hoa Sen" in chu and "Lead Lan Tím" in chu
    assert "Lead Mai Vàng" not in chu and "Lead Cúc Trắng" not in chu


@pytest.mark.asyncio
async def test_cache_moi_truong_phong_mot_ban_bgd_khong_nhan_ban_loc(client, db_session, admin_user,
                                                                    tp4, sales_user):
    v = await _du_lieu_v4(db_session, tp4, sales_user)
    cache.clear_prefix("dashboard")

    async def _xem(u):
        r = await client.get(URL, headers=auth_header(u))
        assert r.status_code == 200, r.text
        return r.json()

    # TP Thiết kế và TP Kinh doanh CÙNG vai `leader` — khoá chỉ theo vai sẽ trả nhầm bản của nhau
    tk = await _xem(tp4["DESIGN"])
    kd = await _xem(tp4["SALES"])
    assert (tk["nguoi_xem"]["phong"], kd["nguoi_xem"]["phong"]) == ("DESIGN", "SALES")
    assert _ids(tk, "lead")["can_xem"] == set()
    assert _ids(kd, "lead")["can_xem"] == {v["lead_trong"].id}
    # BGĐ gọi SAU trưởng phòng vẫn nhận bản đủ, không nhận bản đã lọc
    bgd = await _xem(admin_user)
    assert bgd["nguoi_xem"]["loai"] == "bgd"
    assert _ids(bgd, "lead")["can_xem"] == {v["lead_trong"].id, v["lead_ngoai"].id}
    assert any(x["tong_tien"] for x in bgd["dai_quy_trinh"])
    # Gọi lại trong hạn cache: ai cũng trúng đúng bản của mình
    for u, cu in ((tp4["DESIGN"], tk), (tp4["SALES"], kd), (admin_user, bgd)):
        lai = await _xem(u)
        assert (lai["cap_nhat_luc"], lai["nguoi_xem"]) == (cu["cap_nhat_luc"], cu["nguoi_xem"])
    khoa = [k for k in cache._store if ":du_lieu_chung:" in k]
    assert len(khoa) == 3
    assert any(tp4["DESIGN"].id in k for k in khoa) and any(tp4["SALES"].id in k for k in khoa)

    # Thứ tự ngược: BGĐ trước → trưởng phòng sau vẫn nhận bản lọc, BGĐ vẫn bản đủ
    cache.clear_prefix("dashboard")
    bgd2 = await _xem(admin_user)
    ops = await _xem(tp4["OPS"])
    assert bgd2["nguoi_xem"]["loai"] == "bgd" and ops["nguoi_xem"]["phong"] == "OPS"
    assert all(x["tong_tien"] is None for x in ops["dai_quy_trinh"])
    lai = await _xem(admin_user)
    assert lai["cap_nhat_luc"] == bgd2["cap_nhat_luc"] and any(x["tong_tien"] for x in lai["dai_quy_trinh"])


@pytest.mark.asyncio
async def test_truong_phong_xem_duoc_nhung_khong_gui_nhac(client, db_session, tp4, tele):
    """CHỈ XEM: mọi POST nhắc vẫn 403 cho trưởng phòng, không tin nào được tạo."""
    p = await _du_an(db_session, "construction")
    await db_session.commit()
    for phong, u in tp4.items():
        h = auth_header(u)
        assert (await client.get(URL, headers=h)).status_code == 200
        for body in ({"phong": phong}, {"phong": "chua_xep"}, {"phong": phong, "id": p.id, "loai": "du_an"}):
            r = await client.post(f"{URL}/nhac", headers=h, json=body)
            assert r.status_code == 403, (phong, body, r.text)
        for body in ({}, {"phong": phong}, {"ids": [u.id]}):
            r = await client.post(URL_CAI_APP, headers=h, json=body)
            assert r.status_code == 403, (phong, body, r.text)
    assert (await db_session.execute(select(func.count(Notification.id)))).scalar() == 0
    assert tele == []


@pytest.mark.asyncio
async def test_truong_phong_chua_bat_chi_nguoi_cung_phong(client, db_session, admin_user, nhom_kenh):
    """Danh sách người chưa bật thông báo chỉ còn người cùng phòng; số đếm giữ nguyên."""
    n = nhom_kenh
    pm2 = await _user(db_session, "Giám sát PM 2", "giam_sat_thi_cong", "PM")   # phòng PM cũ → kênh OPS
    tm = await _user(db_session, "TP Thu mua", "dutoan_thumua_leader", "PURCHASING")
    await db_session.commit()
    bgd = (await _get(client, admin_user))["kenh_thong_bao"]
    mong = [
        (n["OPS"], [n["gs"].id, pm2.id, n["OPS"].id]),   # Giám sát PM đã bật máy → không có
        (n["SALES"], [n["SALES"].id]),
        (n["DESIGN"], []),                               # TP Thiết kế đã bật máy
        (tm, [tm.id]),
    ]
    for u, ids in mong:
        k = (await _get(client, u))["kenh_thong_bao"]
        assert [x["id"] for x in k["chua_bat"]] == ids, u.full_name
        assert ({kk: x for kk, x in k.items() if kk != "chua_bat"}
                == {kk: x for kk, x in bgd.items() if kk != "chua_bat"}), u.full_name


@pytest.mark.asyncio
async def test_truong_phong_kd_loc_pham_vi_truoc_roi_moi_cat_50_dong(client, db_session, admin_user,
                                                                    tp4, sales_user):
    """Cắt 50 dòng/phòng SAU khi lọc phạm vi. Lấy 50 dòng đầu của BGĐ rồi mới lọc thì lead
    ngoài phạm vi (chưa giao ai, «chưa rõ» — xếp trước) chiếm hết suất Kinh doanh: TP KD
    thấy danh sách trống dù còn hồ sơ của phòng mình cần bổ sung."""
    for i in range(60):   # chưa giao ai → ngoài phạm vi TP KD; 10 ngày không dấu vết → «chưa rõ»
        await _lead(db_session, f"Lead ngoài {i:02d}", "new", tao=_truoc(10), deal_value=9e8 + i)
    trong = {(await _lead(db_session, f"Lead trong {i}", "new", assigned_to=sales_user.id,
                          deal_value=1e6)).id for i in range(5)}   # vừa tạo → còn tươi, chỉ thiếu khu vực/nguồn
    await db_session.commit()

    bgd = await _get(client, admin_user)
    lead_bgd = {r["id"] for r in bgd["can_xem"] if r["loai"] == "lead"}
    assert len(lead_bgd) == 50 and not lead_bgd & trong      # bản BGĐ giữ nguyên như cũ
    data = await _get(client, tp4["SALES"])
    assert {r["id"] for r in data["can_xem"] if r["loai"] == "lead"} == trong
    assert _phong(data, "SALES") == _phong(bgd, "SALES")      # số trên thẻ vẫn của cả công ty


@pytest.mark.asyncio
async def test_truong_phong_thu_tu_va_viec_chon_dong_khong_theo_tien(client, db_session, admin_user, tp4):
    """Tiền ẩn mà danh sách vẫn xếp/chọn theo tiền là lộ tiền (dòng đầu = hồ sơ giá trị
    nhất). Bản trưởng phòng: nhóm lệch → chưa rõ → thiếu, thiếu nhiều trước, rồi mã hồ sơ;
    50 dòng/phòng cũng chọn theo đúng thứ tự đó. Dữ liệu cũ xếp theo mã."""
    ma_tk = [f"TKV4-{i:02d}" for i in range(55)]
    for i, ma in enumerate(ma_tk):   # mã càng lớn giá trị càng cao; «chưa rõ», thiếu T1 (+ K6/K7 phía KD)
        await _du_an(db_session, "design", code=ma, total_value=(i + 1) * 1e7)
    ma_cu = ["CUV4-A", "CUV4-B", "CUV4-C"]
    for ma, gt in zip(ma_cu, (1e8, 9e8, 5e8)):
        await _du_an(db_session, "paused", code=ma, total_value=gt)
    await db_session.commit()

    bgd = await _get(client, admin_user)
    # BGĐ giữ nguyên: giá trị cao trước, chọn 50 dòng giá trị cao nhất
    assert [r["ma"] for r in bgd["can_xem"] if r["phong_giu"] == "DESIGN"] == ma_tk[::-1][:50]
    assert [r["ma"] for r in bgd["du_lieu_cu"]] == ["CUV4-B", "CUV4-C", "CUV4-A"]

    for phong in ("DESIGN", "OPS"):
        data = await _get(client, tp4[phong])
        assert [(r["phong_giu"], r["ma"]) for r in data["can_xem"]] == (
            [("DESIGN", m) for m in ma_tk[:50]] + [("SALES", m) for m in ma_tk[:50]]), phong
        assert [r["ma"] for r in data["du_lieu_cu"]] == ma_cu, phong
        assert all(r["gia_tri"] is None for r in data["can_xem"] + data["du_lieu_cu"]), phong


@pytest.mark.asyncio
async def test_truong_phong_chua_bat_loc_phong_truoc_roi_moi_cat_200(client, db_session, admin_user, tp):
    """Danh sách tên cắt 200 SAU khi lọc phòng: công ty đông người chưa bật thông báo máy
    thì trưởng phòng xếp sau (Giám sát) vẫn thấy đủ người phòng mình, khớp số trên thanh."""
    for i in range(205):
        db_session.add(User(id=_uid(), full_name=f"Sale {i:03d}", email=f"{_uid()[:12]}@t.vn",
                            password_hash="x", role="data_entry", department="SALES", is_active=True))
    gs = [await _user(db_session, f"Giám sát {i}", "giam_sat_thi_cong", "OPS") for i in range(3)]
    await db_session.commit()

    bgd = (await _get(client, admin_user))["kenh_thong_bao"]
    assert len(bgd["chua_bat"]) == 200 and {x["phong"] for x in bgd["chua_bat"]} == {"SALES"}
    for u, ids in ((tp["OPS"], [*(x.id for x in gs), tp["OPS"].id]), (tp["DESIGN"], [tp["DESIGN"].id])):
        k = (await _get(client, u))["kenh_thong_bao"]
        assert [x["id"] for x in k["chua_bat"]] == ids, u.full_name
        dem = next(x for x in k["theo_phong"] if x["phong"] == phong_cua_tp(u))
        assert dem["tong"] - dem["co_thong_bao_may"] == len(ids), u.full_name
        assert ({kk: x for kk, x in k.items() if kk != "chua_bat"}
                == {kk: x for kk, x in bgd.items() if kk != "chua_bat"}), u.full_name
    # TP Kinh doanh: đủ người phòng mình (206) thì vẫn cắt ở 200
    kd = (await _get(client, tp["SALES"]))["kenh_thong_bao"]["chua_bat"]
    assert len(kd) == 200 and {x["phong"] for x in kd} == {"SALES"}


def phong_cua_tp(u) -> str:
    return (u.department or "").upper()


@pytest.mark.asyncio
async def test_loc_cho_truong_phong_khong_dung_ban_bgd(db_session, tp4, sales_user):
    """Dòng ứng viên «Hồ sơ cần xem» dùng chung đối tượng với bản BGĐ — lọc cho trưởng phòng
    (ẩn tiền, xếp lại, cắt lại) không được sửa lây sang bản BGĐ trong cùng lượt tính."""
    import copy

    from app.api.du_lieu_chung import _loc_cho_truong_phong, _nap, _pham_vi_xem, _tinh

    await _du_lieu_v4(db_session, tp4, sales_user)
    d = await _nap(db_session)
    kq = _tinh(d)
    truoc = copy.deepcopy(kq)
    for phong, u in tp4.items():
        du_an, lead = await _pham_vi_xem(db_session, u)
        out = _loc_cho_truong_phong(kq, d, phong, du_an, lead)
        assert out["can_xem"] and all(r["gia_tri"] is None for r in out["can_xem"]), phong
    assert kq == truoc
    assert any(r["gia_tri"] for r in kq["can_xem"])
