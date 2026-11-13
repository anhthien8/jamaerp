"""AI Tiến Hoá (13/11/2026) — bảng theo dõi + vòng tự học, chỉ quản trị.

  * `TestLoaiGoiY` — đoán loại từ câu chữ (gợi ý LLM cũ không mang loại).
  * `TestDeXuat` / `TestXepLai` — ngưỡng đề xuất bài học và cách xếp lại ứng viên bộ luật.
  * `TestCoPilotHoc` — bài học CHƯA duyệt thì không đổi gì; duyệt rồi mới đổi gợi ý.
  * `TestBangTheoDoi` — số liệu tuần, tỷ lệ dùng lại bộ nhớ, LLM/luật, loại hay bị bỏ qua.
  * `TestApi` — chỉ admin; duyệt / bỏ qua / gỡ; dữ liệu rác thì 400.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import sales_copilot
from app.models.ai_memory import (
    AGENT_INSIGHT,
    AGENT_LEAD_SCORING,
    AGENT_SALES_COPILOT,
    OUTCOME_DONE,
    OUTCOME_SKIPPED,
    SCOPE_LEAD,
    SOURCE_LLM,
    SOURCE_RULE,
    AiRun,
)
from app.models.lead import Lead
from app.models.user import User
from app.services import ai_memory, ai_tien_hoa
from tests.conftest import auth_header


def _uid() -> str:
    return str(uuid.uuid4())


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def lead_cua_sale(db_session: AsyncSession, sales_user: User) -> Lead:
    lead = Lead(
        id=_uid(),
        name="Anh Minh — Quận 7",
        phone="0909333444",
        source="facebook",
        property_type="villa",
        area_sqm=220.0,
        estimated_budget=2_500_000_000,
        stage="new",
        priority="high",
        assigned_to=sales_user.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(lead)
    await db_session.commit()
    return lead


@pytest.fixture(autouse=True)
def _tat_llm(monkeypatch):
    async def _khong_co():
        return False

    monkeypatch.setattr("app.agents.sales_copilot.llm_available", _khong_co)
    monkeypatch.setattr("app.services.llm_config.llm_available", _khong_co)


def _goi_y(code: str, outcome: str | None, luc: datetime, **them) -> AiRun:
    import json

    return AiRun(
        id=_uid(), agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD, scope_id=_uid(),
        input_hash=_uid(), output_json=json.dumps({"code": code, "action": f"việc {code}", **them}),
        source=SOURCE_RULE, outcome=outcome, created_at=_naive(luc),
    )


# ---------------------------------------------------------------------------


class TestLoaiGoiY:
    @pytest.mark.parametrize("cau, loai", [
        ("Xác nhận lịch khảo sát và chuẩn bị hồ sơ", "meeting"),
        ("Hẹn lịch khảo sát thực tế", "survey"),
        ("Gửi báo giá sau khảo sát", "proposal"),
        ("Chốt lịch khảo sát với khách", "survey"),
        ("Gửi phương án thiết kế sơ bộ", "proposal"),
        ("Liên hệ lại để hâm nóng khách", "recontact"),
        ("Gọi điện giới thiệu dịch vụ", "call"),
        ("Báo trưởng nhóm cùng chăm khách", "escalate"),
        ("Phân công lead cho một bạn Sale", "assign"),
        ("Cập nhật tình trạng lead", "note"),
        ("Đi uống cà phê", "khac"),
        ("", "khac"),
        (None, "khac"),
    ])
    def test_doan_loai(self, cau, loai):
        assert ai_tien_hoa.doan_loai(cau) == loai

    def test_loai_cua_uu_tien_code_da_biet(self):
        assert ai_tien_hoa.loai_cua({"code": "proposal", "action": "Gọi khách"}) == "proposal"

    def test_loai_cua_code_cu_llm_thi_doan(self):
        # trước 13/11 gợi ý LLM lưu code="llm"
        assert ai_tien_hoa.loai_cua({"code": "llm", "action": "Gọi khách chốt lịch"}) == "call"


class TestDeXuat:
    def test_it_mau_thi_chua_ket_luan(self):
        assert ai_tien_hoa.de_xuat_huong(0, 4) is None

    def test_bo_qua_nhieu_thi_ha(self):
        assert ai_tien_hoa.de_xuat_huong(2, 3) == ai_tien_hoa.HUONG_HA

    def test_lam_nhieu_thi_uu_tien(self):
        assert ai_tien_hoa.de_xuat_huong(7, 3) == ai_tien_hoa.HUONG_UU_TIEN

    def test_lung_chung_thi_khong_de_xuat(self):
        assert ai_tien_hoa.de_xuat_huong(5, 5) is None


class TestXepLai:
    UNG_VIEN = [
        {"code": "call"}, {"code": "escalate"}, {"code": "proposal"}, {"code": "note"},
    ]

    def test_khong_bai_hoc_giu_nguyen(self):
        assert ai_tien_hoa.xep_theo_bai_hoc(self.UNG_VIEN, {}) is self.UNG_VIEN

    def test_ha_xuong_va_uu_tien_len(self):
        xep = ai_tien_hoa.xep_theo_bai_hoc(self.UNG_VIEN, {"call": "ha", "proposal": "uu_tien"})
        assert [u["code"] for u in xep] == ["proposal", "escalate", "call", "note"]

    def test_note_luon_cuoi_du_duoc_uu_tien(self):
        xep = ai_tien_hoa.xep_theo_bai_hoc(self.UNG_VIEN, {"note": "uu_tien"})
        assert xep[-1]["code"] == "note"

    def test_loi_dan_prompt(self):
        assert ai_tien_hoa.loi_dan_bai_hoc({}) == ""
        van = ai_tien_hoa.loi_dan_bai_hoc({"call": "ha"})
        assert "BỎ QUA" in van and "Gọi tư vấn" in van


class TestCoPilotHoc:
    @pytest.mark.asyncio
    async def test_bai_hoc_chua_duyet_thi_khong_doi(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User, admin_user: User
    ):
        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "call", "ha", "tu_choi")
        await db_session.commit()

        goi_y = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert goi_y["code"] == "call"
        assert not goi_y.get("theo_bai_hoc")

    @pytest.mark.asyncio
    async def test_duyet_ha_call_thi_goi_y_viec_ke_tiep(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User, admin_user: User
    ):
        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "call", "ha", "duyet")
        await db_session.commit()

        goi_y = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert goi_y["code"] == "escalate"
        assert goi_y["theo_bai_hoc"] is True

    @pytest.mark.asyncio
    async def test_go_bai_hoc_thi_ve_nhu_cu(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User, admin_user: User
    ):
        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "call", "ha", "duyet")
        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "call", None, "go")
        await db_session.commit()

        assert await ai_tien_hoa.bai_hoc_dang_ap_dung(db_session) == {}
        goi_y = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert goi_y["code"] == "call"

    def test_llm_quen_tra_loai_thi_doan(self):
        ra = sales_copilot._chuan_hoa({"action": "Gửi báo giá phương án 2", "loai": "bậy"})
        assert ra["code"] == "proposal"
        ra = sales_copilot._chuan_hoa({"action": "Gọi khách", "loai": "survey"})
        assert ra["code"] == "survey"


class TestDungLai:
    @pytest.mark.asyncio
    async def test_dem_so_lan_dung_lai(self, db_session: AsyncSession):
        ban = await ai_memory.ghi_lai(
            db_session, agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD,
            input_hash="h-dung-lai", output={"score": 80}, source=SOURCE_LLM, commit=True,
        )
        await ai_memory.ghi_dung_lai(db_session, ban, commit=True)
        await ai_memory.ghi_dung_lai(db_session, ban, commit=True)
        await db_session.refresh(ban)
        assert ban.so_lan_dung_lai == 2


class TestBangTheoDoi:
    @pytest.mark.asyncio
    async def test_so_lieu(self, db_session: AsyncSession):
        bay_gio = datetime.now(timezone.utc)
        tuan_truoc = bay_gio - timedelta(days=7)

        # Tuần trước: 5 lần «Gọi» → 1 làm, 4 bỏ qua (đủ mẫu, 80% bỏ qua → đề xuất hạ)
        db_session.add(_goi_y("call", OUTCOME_DONE, tuan_truoc))
        for _ in range(4):
            db_session.add(_goi_y("call", OUTCOME_SKIPPED, tuan_truoc))
        # Tuần này: 3 «Báo giá» làm, 1 chưa phản hồi; 1 gợi ý LLM cũ code="llm" được làm
        for _ in range(3):
            db_session.add(_goi_y("proposal", OUTCOME_DONE, bay_gio))
        db_session.add(_goi_y("proposal", None, bay_gio, theo_bai_hoc=True))
        cu = _goi_y("llm", OUTCOME_DONE, bay_gio)
        cu.output_json = '{"code": "llm", "action": "Hẹn lịch khảo sát nhà"}'
        cu.source = SOURCE_LLM
        cu.model_used = "groq/qwen"
        cu.so_lan_dung_lai = 3
        db_session.add(cu)
        # Agent khác: chấm điểm bằng LLM, nhận định bằng luật
        db_session.add(AiRun(
            id=_uid(), agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD, input_hash=_uid(),
            output_json="{}", source=SOURCE_LLM, model_used="groq/qwen",
            so_lan_dung_lai=1, created_at=_naive(bay_gio),
        ))
        db_session.add(AiRun(
            id=_uid(), agent=AGENT_INSIGHT, scope_type="company", input_hash=_uid(),
            output_json="{}", source=SOURCE_RULE, created_at=_naive(bay_gio),
        ))
        # Quá cửa sổ 12 tuần → không tính
        db_session.add(_goi_y("call", OUTCOME_SKIPPED, bay_gio - timedelta(weeks=20)))
        await db_session.commit()

        bang = await ai_tien_hoa.bang_theo_doi(db_session, so_tuan=12, bay_gio=bay_gio)
        tong = bang["tong"]

        assert len(bang["theo_tuan"]) == 12
        assert tong["so_lan_chay"] == 12
        assert tong["so_goi_y"] == 10
        assert tong["lam"] == 5 and tong["bo_qua"] == 4
        assert tong["ty_le_lam_theo"] == round(5 / 9, 4)
        assert tong["ty_le_phan_hoi"] == round(9 / 10, 4)
        assert tong["llm"] == 2 and tong["rule"] == 10
        assert tong["dung_lai"] == 4
        assert tong["ty_le_dung_lai"] == round(4 / 16, 4)
        assert tong["ap_bai_hoc"]["so_goi_y"] == 1

        tuan_nay, tuan_kia = bang["theo_tuan"][-1], bang["theo_tuan"][-2]
        assert tuan_nay["ty_le_lam_theo"] == 1.0
        assert tuan_kia["ty_le_lam_theo"] == 0.2

        agent = {a["agent"]: a for a in bang["theo_agent"]}
        assert agent[AGENT_SALES_COPILOT]["chay"] == 10
        assert agent[AGENT_LEAD_SCORING]["llm"] == 1
        assert agent[AGENT_INSIGHT]["rule"] == 1
        assert bang["model"]["da_tra_loi"] == [{"model": "groq/qwen", "so_lan": 2}]

        loai = {x["code"]: x for x in bang["theo_loai"]}
        assert bang["theo_loai"][0]["code"] == "call"  # bị bỏ qua nhiều nhất đứng đầu
        assert loai["call"]["bo_qua"] == 4
        assert loai["proposal"]["chua_phan_hoi"] == 1
        assert loai["survey"]["lam"] == 1  # gợi ý LLM cũ được đoán loại

        bai = {b["code"]: b for b in bang["bai_hoc"]}
        assert bai["call"]["trang_thai"] == "cho_duyet"
        assert bai["call"]["huong"] == "ha"
        assert "proposal" not in bai  # 3 mẫu, chưa đủ
        assert bang["so_cho_duyet"] == 1

    @pytest.mark.asyncio
    async def test_trang_thai_bai_hoc(self, db_session: AsyncSession, admin_user: User):
        bay_gio = datetime.now(timezone.utc)
        for _ in range(5):
            db_session.add(_goi_y("call", OUTCOME_SKIPPED, bay_gio))
            db_session.add(_goi_y("proposal", OUTCOME_DONE, bay_gio))
        await db_session.commit()

        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "call", "ha", "tu_choi")
        # Duyệt «hạ» cho proposal trong khi số liệu nói «ưu tiên» → hiện đề xuất mới
        await ai_tien_hoa.quyet_dinh_bai_hoc(db_session, admin_user, "proposal", "ha", "duyet")
        await db_session.commit()

        bang = await ai_tien_hoa.bang_theo_doi(db_session, bay_gio=bay_gio)
        bai = {b["code"]: b for b in bang["bai_hoc"]}
        assert bai["call"]["trang_thai"] == "da_bo_qua"
        assert bai["proposal"]["trang_thai"] == "dang_ap_dung"
        assert bai["proposal"]["de_xuat_moi"] == "uu_tien"
        assert bai["proposal"]["quyet_boi"] == admin_user.full_name
        assert bang["bai_hoc"][0]["code"] == "proposal"  # đề xuất mới lên đầu
        assert bang["so_cho_duyet"] == 1

    @pytest.mark.asyncio
    async def test_trong_rong(self, db_session: AsyncSession):
        bang = await ai_tien_hoa.bang_theo_doi(db_session, so_tuan=4)
        assert bang["tong"]["so_lan_chay"] == 0
        assert bang["tong"]["ty_le_lam_theo"] is None
        assert bang["tong"]["chenh_lech"] is None
        assert bang["bai_hoc"] == []


class TestApi:
    @pytest.mark.asyncio
    async def test_admin_xem_duoc(self, client, admin_user: User):
        r = await client.get("/api/v1/ai/tien-hoa", headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json()["so_tuan"] == 12

    @pytest.mark.asyncio
    async def test_sale_bi_chan(self, client, sales_user: User):
        r = await client.get("/api/v1/ai/tien-hoa", headers=auth_header(sales_user))
        assert r.status_code == 403
        r = await client.post(
            "/api/v1/ai/tien-hoa/bai-hoc",
            json={"code": "call", "huong": "ha", "quyet_dinh": "duyet"},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_duyet_roi_go(self, client, db_session: AsyncSession, admin_user: User):
        r = await client.post(
            "/api/v1/ai/tien-hoa/bai-hoc",
            json={"code": "call", "huong": "ha", "quyet_dinh": "duyet"},
            headers=auth_header(admin_user),
        )
        assert r.status_code == 200, r.text
        assert r.json()["bai_hoc"]["trang_thai"] == "da_duyet"
        assert await ai_tien_hoa.bai_hoc_dang_ap_dung(db_session) == {"call": "ha"}

        r = await client.post(
            "/api/v1/ai/tien-hoa/bai-hoc",
            json={"code": "call", "quyet_dinh": "go"},
            headers=auth_header(admin_user),
        )
        assert r.status_code == 200
        assert r.json()["bai_hoc"] is None

    @pytest.mark.parametrize("body", [
        {"code": "bay", "huong": "ha", "quyet_dinh": "duyet"},
        {"code": "khac", "huong": "ha", "quyet_dinh": "duyet"},
        {"code": "call", "huong": "len", "quyet_dinh": "duyet"},
        {"code": "call", "huong": "ha", "quyet_dinh": "xoa"},
    ])
    @pytest.mark.asyncio
    async def test_du_lieu_rac_thi_400(self, client, admin_user: User, body):
        r = await client.post(
            "/api/v1/ai/tien-hoa/bai-hoc", json=body, headers=auth_header(admin_user)
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_so_tuan_ngoai_khoang_thi_422(self, client, admin_user: User):
        r = await client.get(
            "/api/v1/ai/tien-hoa", params={"so_tuan": 2}, headers=auth_header(admin_user)
        )
        assert r.status_code == 422
