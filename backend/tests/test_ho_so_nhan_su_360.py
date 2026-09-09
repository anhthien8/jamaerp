"""Tests Hồ sơ nhân viên 360° (09/09/2026) — profile/CCCD/HĐLĐ, giấy tờ JPG,
tab Tiền (chỉ admin+kế toán), chấm công theo người, bàn giao khi nghỉ việc,
sale_leader duyệt OT team + vết ai-duyệt-lúc-nào, webhook máy chấm công,
đối chiếu IP văn phòng.
"""

import base64
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.handover import HandoverRecord
from app.models.lead import Lead
from app.models.user import User, Team
from app.services.attendance_service import ip_in_networks

from tests.conftest import auth_header, _uid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def doi_kd(db_session: AsyncSession) -> Team:
    team = Team(id=_uid(), name="Đội KD 360", code=f"KD{_uid()[:4]}", department="SALES")
    db_session.add(team)
    await db_session.flush()
    return team


@pytest_asyncio.fixture
async def truong_nhom(db_session: AsyncSession, doi_kd: Team) -> User:
    user = User(
        id=_uid(), full_name="Trưởng Nhóm KD", email=f"tn-{_uid()}@test.com",
        password_hash="hashed", role="sale_leader", department="SALES",
        team_id=doi_kd.id, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sale_trong_nhom(db_session: AsyncSession, doi_kd: Team) -> User:
    user = User(
        id=_uid(), full_name="Sale Trong Nhóm", email=f"sale-{_uid()}@test.com",
        password_hash="hashed", role="data_entry", department="SALES",
        team_id=doi_kd.id, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def ot_cho_duyet(db_session: AsyncSession, sale_trong_nhom: User) -> AttendanceRecord:
    record = AttendanceRecord(
        id=_uid(), user_id=sale_trong_nhom.id, work_date=date(2026, 9, 8),
        check_in=datetime(2026, 9, 8, 1, 0), check_out=datetime(2026, 9, 8, 12, 0),
        source="web", work_hours=8, ot_hours=3, ot_status="pending",
    )
    db_session.add(record)
    await db_session.flush()
    return record


# ---------------------------------------------------------------------------
# Hồ sơ + giấy tờ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHoSoNhanSu:
    async def test_admin_luu_va_doc_ho_so(self, client, admin_user, sales_user):
        resp = await client.put(
            f"/api/v1/hr/employees/{sales_user.id}/profile",
            json={
                "national_id": "079012345678",
                "hire_date": "2025-03-01",
                "contract_type": "fixed_1y",
                "contract_signed_date": "2025-03-01",
                "contract_end_date": "2026-03-01",
                "bank_name": "VCB",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["profile"]["national_id"] == "079012345678"

        got = await client.get(
            f"/api/v1/hr/employees/{sales_user.id}/profile", headers=auth_header(admin_user)
        )
        assert got.status_code == 200
        body = got.json()
        assert body["profile"]["hire_date"] == "2025-03-01"
        assert body["profile"]["contract_type"] == "fixed_1y"
        assert body["can_edit"] is True

    async def test_chinh_chu_xem_duoc_khong_sua_duoc(self, client, admin_user, sales_user):
        await client.put(
            f"/api/v1/hr/employees/{sales_user.id}/profile",
            json={"national_id": "079099999999"},
            headers=auth_header(admin_user),
        )
        got = await client.get(
            f"/api/v1/hr/employees/{sales_user.id}/profile", headers=auth_header(sales_user)
        )
        assert got.status_code == 200
        assert got.json()["can_edit"] is False

        put = await client.put(
            f"/api/v1/hr/employees/{sales_user.id}/profile",
            json={"address": "tự sửa"},
            headers=auth_header(sales_user),
        )
        assert put.status_code == 403

    async def test_nguoi_khac_khong_xem_duoc(self, client, sales_user, designer_user):
        resp = await client.get(
            f"/api/v1/hr/employees/{designer_user.id}/profile", headers=auth_header(sales_user)
        )
        assert resp.status_code == 403

    async def test_contract_type_la_phai_hop_le(self, client, admin_user, sales_user):
        resp = await client.put(
            f"/api/v1/hr/employees/{sales_user.id}/profile",
            json={"contract_type": "vinh_vien"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422

    async def test_ngay_sai_dinh_dang_422(self, client, admin_user, sales_user):
        resp = await client.put(
            f"/api/v1/hr/employees/{sales_user.id}/profile",
            json={"hire_date": "01/03/2025"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGiayTo:
    async def test_upload_va_tai_lai_jpg(self, client, admin_user, sales_user):
        raw = b"\xff\xd8\xff" + b"x" * 100  # giả JPG nhỏ
        resp = await client.post(
            f"/api/v1/hr/employees/{sales_user.id}/documents",
            json={
                "doc_type": "cccd_front", "filename": "cccd-truoc.jpg",
                "mime": "image/jpeg", "data_base64": base64.b64encode(raw).decode(),
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        doc_id = resp.json()["id"]

        got = await client.get(
            f"/api/v1/hr/employees/{sales_user.id}/documents/{doc_id}",
            headers=auth_header(sales_user),  # chính chủ xem được giấy tờ của mình
        )
        assert got.status_code == 200
        assert base64.b64decode(got.json()["data_base64"]) == raw

    async def test_file_qua_lon_413(self, client, admin_user, sales_user):
        raw = b"x" * 800_000
        resp = await client.post(
            f"/api/v1/hr/employees/{sales_user.id}/documents",
            json={
                "doc_type": "contract", "filename": "hdld.jpg",
                "mime": "image/jpeg", "data_base64": base64.b64encode(raw).decode(),
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 413

    async def test_sale_khong_upload_duoc(self, client, sales_user):
        resp = await client.post(
            f"/api/v1/hr/employees/{sales_user.id}/documents",
            json={
                "doc_type": "other", "filename": "a.jpg",
                "mime": "image/jpeg", "data_base64": base64.b64encode(b"abc").decode(),
            },
            headers=auth_header(sales_user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tab Tiền — chỉ admin + kế toán (+ chính chủ)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTabTien:
    async def test_admin_va_ke_toan_xem_duoc(self, client, admin_user, accountant_user, sales_user):
        for viewer in (admin_user, accountant_user):
            resp = await client.get(
                f"/api/v1/hr/employees/{sales_user.id}/finance", headers=auth_header(viewer)
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert set(body.keys()) == {"payrolls", "commissions", "advances", "transactions", "totals"}

    async def test_chinh_chu_xem_duoc_cua_minh(self, client, sales_user):
        resp = await client.get(
            f"/api/v1/hr/employees/{sales_user.id}/finance", headers=auth_header(sales_user)
        )
        assert resp.status_code == 200

    async def test_truong_nhom_KHONG_xem_duoc_tien_cua_linh(
        self, client, truong_nhom, sale_trong_nhom
    ):
        # Chốt 09/09: tab Tiền chỉ Admin + Kế toán — trưởng nhóm cùng team vẫn 403
        resp = await client.get(
            f"/api/v1/hr/employees/{sale_trong_nhom.id}/finance", headers=auth_header(truong_nhom)
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Chấm công theo người + OT sale_leader
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestChamCongTheoNguoi:
    async def test_truong_nhom_xem_cong_linh_cung_team(self, client, truong_nhom, sale_trong_nhom):
        resp = await client.get(
            f"/api/v1/hr/employees/{sale_trong_nhom.id}/attendance?period=2026-09",
            headers=auth_header(truong_nhom),
        )
        assert resp.status_code == 200, resp.text

    async def test_truong_nhom_khong_xem_cong_nguoi_ngoai_team(self, client, truong_nhom, designer_user):
        resp = await client.get(
            f"/api/v1/hr/employees/{designer_user.id}/attendance", headers=auth_header(truong_nhom)
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestSaleLeaderDuyetOT:
    async def test_sale_leader_thay_va_duyet_ot_team(
        self, client, truong_nhom, sale_trong_nhom, ot_cho_duyet
    ):
        pending = await client.get("/api/v1/attendance/ot/pending", headers=auth_header(truong_nhom))
        assert pending.status_code == 200, pending.text
        assert any(i["id"] == ot_cho_duyet.id for i in pending.json()["items"])

        resp = await client.post(
            f"/api/v1/attendance/{ot_cho_duyet.id}/ot-approve", headers=auth_header(truong_nhom)
        )
        assert resp.status_code == 200, resp.text
        record = resp.json()["record"]
        # Vết duyệt hiển thị được ngay: ai duyệt + lúc nào
        assert record["ot_status"] == "approved"
        assert record["ot_decided_by_name"] == truong_nhom.full_name
        assert record["ot_decided_at"] is not None

    async def test_sale_leader_khong_duyet_ot_ngoai_team(
        self, client, db_session, truong_nhom, designer_user
    ):
        record = AttendanceRecord(
            id=_uid(), user_id=designer_user.id, work_date=date(2026, 9, 8),
            source="web", work_hours=8, ot_hours=2, ot_status="pending",
        )
        db_session.add(record)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/attendance/{record.id}/ot-approve", headers=auth_header(truong_nhom)
        )
        assert resp.status_code == 403

    async def test_sale_thuong_khong_vao_duoc_ot_pending(self, client, sales_user):
        resp = await client.get("/api/v1/attendance/ot/pending", headers=auth_header(sales_user))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Bàn giao khi nghỉ việc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestBanGiao:
    async def test_resign_ghi_vet_ban_giao_va_doc_duoc(
        self, client, db_session, admin_user, truong_nhom, sale_trong_nhom
    ):
        lead = Lead(
            id=_uid(), name="Khách Bàn Giao", phone=f"09{_uid()[:8]}",
            stage="new", assigned_to=sale_trong_nhom.id,
        )
        db_session.add(lead)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/hr/resign",
            json={"user_id": sale_trong_nhom.id, "transfer_leads_to": truong_nhom.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text

        handovers = await client.get(
            f"/api/v1/hr/employees/{sale_trong_nhom.id}/handovers", headers=auth_header(admin_user)
        )
        assert handovers.status_code == 200
        given = handovers.json()["given"]
        assert any(
            h["entity_type"] == "lead" and h["entity_name"] == "Khách Bàn Giao"
            and h["to_user_name"] == truong_nhom.full_name and h["reason"] == "resign"
            for h in given
        ), given

    async def test_sale_khong_xem_duoc_ban_giao(self, client, sales_user):
        resp = await client.get(
            f"/api/v1/hr/employees/{sales_user.id}/handovers", headers=auth_header(sales_user)
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Đối chiếu văn phòng + webhook máy chấm công
# ---------------------------------------------------------------------------

class TestIpNetworks:
    def test_ip_khop_chinh_xac_va_cidr(self):
        assert ip_in_networks("113.161.72.10", ["113.161.72.10"]) is True
        assert ip_in_networks("192.168.1.77", ["192.168.1.0/24"]) is True
        assert ip_in_networks("14.241.0.9", ["113.161.72.10", "192.168.1.0/24"]) is False

    def test_thieu_du_lieu_tra_none(self):
        assert ip_in_networks(None, ["1.2.3.4"]) is None
        assert ip_in_networks("1.2.3.4", []) is None
        assert ip_in_networks("khong-phai-ip", ["1.2.3.4"]) is None

    def test_dong_cau_hinh_hong_khong_lam_chet_check(self):
        assert ip_in_networks("1.2.3.4", ["not-an-ip", "1.2.3.4"]) is True


@pytest.mark.asyncio
class TestVanPhongVaMayChamCong:
    async def test_admin_cau_hinh_van_phong_va_checkin_gan_nhan_ip(
        self, client, admin_user, sales_user
    ):
        cfg = await client.put(
            "/api/v1/attendance/office-config",
            json={"networks": ["10.77.0.0/16"], "radius_m": 200},
            headers=auth_header(admin_user),
        )
        assert cfg.status_code == 200, cfg.text

        resp = await client.post(
            "/api/v1/attendance/checkin",
            json={},
            headers={**auth_header(sales_user), "X-Forwarded-For": "10.77.3.9"},
        )
        assert resp.status_code == 200, resp.text
        record = resp.json()["record"]
        assert record["ip_ok"] is True
        assert "văn phòng" in resp.json()["message"]

    async def test_non_admin_khong_cau_hinh_duoc(self, client, accountant_user):
        resp = await client.put(
            "/api/v1/attendance/office-config",
            json={"networks": []},
            headers=auth_header(accountant_user),
        )
        assert resp.status_code == 403

    async def test_webhook_sai_khoa_401_dung_khoa_tao_va_gop_ca(
        self, client, admin_user, sales_user
    ):
        from app.services.attendance_service import vn_today

        hom_nay = vn_today().isoformat()
        # Chưa bật thiết bị → 401
        deny = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T08:00:00"},
            headers={"X-Device-Key": "sai-khoa"},
        )
        assert deny.status_code == 401

        rotate = await client.post(
            "/api/v1/attendance/device-key/rotate", headers=auth_header(admin_user)
        )
        assert rotate.status_code == 200
        key = rotate.json()["api_key"]

        first = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T08:00:00"},
            headers={"X-Device-Key": key},
        )
        assert first.status_code == 200, first.text
        assert first.json()["applied"] == "check_in"
        assert first.json()["record"]["source"] == "device"
        # 08:00 giờ VN = 01:00 UTC (quy ước cột lưu UTC naive)
        assert first.json()["record"]["check_in"].startswith(f"{hom_nay} 01:00")

        second = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T18:30:00", "direction": "out"},
            headers={"X-Device-Key": key},
        )
        assert second.status_code == 200, second.text
        assert second.json()["applied"] == "check_out"
        record = second.json()["record"]
        assert record["work_hours"] == 8  # 10.5h → 8h công + OT chờ duyệt
        assert record["ot_hours"] == 2.5
        assert record["ot_status"] == "pending"

    async def test_webhook_email_la_404(self, client, admin_user):
        from app.services.attendance_service import vn_today

        rotate = await client.post(
            "/api/v1/attendance/device-key/rotate", headers=auth_header(admin_user)
        )
        resp = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": "khong-ton-tai@test.com", "event_time": f"{vn_today().isoformat()}T08:00:00"},
            headers={"X-Device-Key": rotate.json()["api_key"]},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestWebhookGopCaVaChongPha:
    """Fix từ vòng phản biện: gộp lộn thứ tự, chặn ngày xa, không phá công phép,
    tính lại giờ + xóa vết duyệt khi backfill."""

    async def _key(self, client, admin_user) -> str:
        rotate = await client.post(
            "/api/v1/attendance/device-key/rotate", headers=auth_header(admin_user)
        )
        return rotate.json()["api_key"]

    async def test_event_lon_thu_tu_khong_mat_luot_quet(self, client, admin_user, sales_user):
        from app.services.attendance_service import vn_today

        hom_nay = vn_today().isoformat()
        key = await self._key(client, admin_user)
        # Máy offline đẩy bù: OUT 17:00 đến TRƯỚC, IN 08:00 đến SAU
        out_first = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T17:00:00", "direction": "out"},
            headers={"X-Device-Key": key},
        )
        assert out_first.status_code == 200
        in_later = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T08:00:00", "direction": "in"},
            headers={"X-Device-Key": key},
        )
        assert in_later.status_code == 200, in_later.text
        record = in_later.json()["record"]
        # Sớm nhất = vào, muộn nhất = ra — KHÔNG mất lượt 17:00
        assert record["check_in"].startswith(f"{hom_nay} 01:00")
        assert record["check_out"].startswith(f"{hom_nay} 10:00")
        assert record["work_hours"] == 8  # 9h elapsed
        assert record["ot_hours"] == 1.0

    async def test_backfill_check_in_som_hon_tinh_lai_gio_va_xoa_vet_duyet(
        self, client, admin_user, sales_user
    ):
        from app.services.attendance_service import vn_today

        hom_nay = vn_today().isoformat()
        key = await self._key(client, admin_user)
        for t, d in ((f"{hom_nay}T09:00:00", "in"), (f"{hom_nay}T18:00:00", "out")):
            await client.post(
                "/api/v1/attendance/device-webhook",
                json={"email": sales_user.email, "event_time": t, "direction": d},
                headers={"X-Device-Key": key},
            )
        # Admin duyệt OT (9h elapsed → 1h OT pending)
        me = await client.get(
            "/api/v1/attendance/ot/pending", headers=auth_header(admin_user)
        )
        rid = next(i["id"] for i in me.json()["items"] if i["user_id"] == sales_user.id)
        approved = await client.post(
            f"/api/v1/attendance/{rid}/ot-approve", headers=auth_header(admin_user)
        )
        assert approved.json()["record"]["ot_status"] == "approved"

        # Máy đẩy bù lượt quẹt 07:30 → giờ công PHẢI tính lại + vết duyệt cũ PHẢI xóa
        backfill = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{hom_nay}T07:30:00"},
            headers={"X-Device-Key": key},
        )
        record = backfill.json()["record"]
        assert record["check_in"].startswith(f"{hom_nay} 00:30")
        assert record["ot_hours"] == 2.5  # 10.5h elapsed
        assert record["ot_status"] == "pending"  # số giờ MỚI — phải duyệt lại
        assert record["ot_decided_by_name"] is None  # vết duyệt cũ không còn ứng

    async def test_ngay_ngoai_cua_so_bi_chan_422(self, client, admin_user, sales_user):
        from datetime import timedelta

        from app.services.attendance_service import vn_today

        key = await self._key(client, admin_user)
        for delta in (-30, 10):
            ngay = (vn_today() + timedelta(days=delta)).isoformat()
            resp = await client.post(
                "/api/v1/attendance/device-webhook",
                json={"email": sales_user.email, "event_time": f"{ngay}T08:00:00"},
                headers={"X-Device-Key": key},
            )
            assert resp.status_code == 422, f"delta={delta}: {resp.text}"

    async def test_khong_ghi_de_ngay_nghi_phep(self, client, db_session, admin_user, sales_user):
        from app.services.attendance_service import vn_today

        record = AttendanceRecord(
            id=_uid(), user_id=sales_user.id, work_date=vn_today(),
            source="leave", work_hours=8, ot_hours=0, ot_status="none",
            note="Phép năm",
        )
        db_session.add(record)
        await db_session.flush()

        key = await self._key(client, admin_user)
        resp = await client.post(
            "/api/v1/attendance/device-webhook",
            json={"email": sales_user.email, "event_time": f"{vn_today().isoformat()}T08:00:00"},
            headers={"X-Device-Key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["applied"] == "ignored_leave"
        assert resp.json()["record"]["work_hours"] == 8  # giờ phép giữ nguyên
        assert resp.json()["record"]["source"] == "leave"
