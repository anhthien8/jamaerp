"""Bộ nhớ cho AI Agents — băm đầu vào, dùng lại bản cũ, và không gợi ý lặp.

Ba nhóm:
  * `TestBamDauVao` — băm phải ổn định, nếu không thì cache không bao giờ trúng.
  * `TestDungLaiBanCu` — trúng trong hạn, trượt ngoài hạn, và KHÔNG dùng lại bản luật.
  * `TestCoPilotKhongLap` / `TestApiGoiY` — thứ anh Thiện đặt hàng: sale bấm "Đã làm"
    hay "Bỏ qua" thì lượt sau Co-Pilot phải đề xuất việc khác.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import sales_copilot
from app.models.ai_memory import (
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
from app.services import ai_memory
from tests.conftest import auth_header


def _uid() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def lead_cua_sale(db_session: AsyncSession, sales_user: User) -> Lead:
    lead = Lead(
        id=_uid(),
        name="Chị Lan — Thảo Điền",
        phone="0909111222",
        source="referral",
        property_type="villa",
        area_sqm=280.0,
        estimated_budget=2_500_000_000,
        stage="new",
        priority="high",
        assigned_to=sales_user.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add(lead)
    await db_session.commit()
    return lead


@pytest.fixture(autouse=True)
def _tat_llm(monkeypatch):
    """Test chạy đường bộ luật cho tất định — không phụ thuộc key LLM của máy chạy."""
    async def _khong_co():
        return False

    monkeypatch.setattr("app.agents.sales_copilot.llm_available", _khong_co)


# ---------------------------------------------------------------------------


class TestBamDauVao:
    def test_cung_chuoi_thi_cung_bam(self):
        assert ai_memory.bam_dau_vao("xin chào") == ai_memory.bam_dau_vao("xin chào")

    def test_khac_chuoi_thi_khac_bam(self):
        assert ai_memory.bam_dau_vao("a") != ai_memory.bam_dau_vao("b")

    def test_dict_khong_phu_thuoc_thu_tu_khoa(self):
        # Nếu thứ tự khoá đổi băm thì cache gần như không bao giờ trúng
        assert ai_memory.bam_dau_vao({"a": 1, "b": 2}) == ai_memory.bam_dau_vao({"b": 2, "a": 1})

    def test_giu_duoc_tieng_viet_co_dau(self):
        bam = ai_memory.bam_dau_vao({"ghi_chu": "Đã gửi báo giá"})
        assert len(bam) == 64


class TestDungLaiBanCu:
    @pytest.mark.asyncio
    async def test_ghi_roi_tra_lai_duoc(self, db_session: AsyncSession):
        bam = ai_memory.bam_dau_vao("lead-1")
        await ai_memory.ghi_lai(
            db_session, agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD,
            scope_id="lead-1", input_hash=bam, output={"score": 88},
            source=SOURCE_LLM, model_used="groq/llama-3.3-70b-versatile", commit=True,
        )
        ban = await ai_memory.tim_ban_cu(db_session, AGENT_LEAD_SCORING, bam)
        assert ban is not None
        assert ai_memory.doc_output(ban)["score"] == 88
        assert ban.model_used == "groq/llama-3.3-70b-versatile"

    @pytest.mark.asyncio
    async def test_khac_agent_thi_khong_dung_nham(self, db_session: AsyncSession):
        bam = ai_memory.bam_dau_vao("chung-mot-cau-hoi")
        await ai_memory.ghi_lai(
            db_session, agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD,
            input_hash=bam, output={"score": 50}, source=SOURCE_LLM, commit=True,
        )
        assert await ai_memory.tim_ban_cu(db_session, AGENT_SALES_COPILOT, bam) is None

    @pytest.mark.asyncio
    async def test_qua_han_thi_khong_dung_lai(self, db_session: AsyncSession):
        bam = ai_memory.bam_dau_vao("lead-cu")
        ban = AiRun(
            id=_uid(), agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD,
            scope_id="lead-cu", input_hash=bam, output_json='{"score": 70}',
            source=SOURCE_LLM,
            created_at=datetime.now(timezone.utc) - timedelta(hours=30),
        )
        db_session.add(ban)
        await db_session.commit()

        assert await ai_memory.tim_ban_cu(db_session, AGENT_LEAD_SCORING, bam) is None
        # còn trong hạn rộng hơn thì vẫn dùng được
        assert await ai_memory.tim_ban_cu(db_session, AGENT_LEAD_SCORING, bam, ttl_gio=48) is not None

    @pytest.mark.asyncio
    async def test_ban_theo_luat_khong_duoc_dung_lai(self, db_session: AsyncSession):
        """Bản luật tính lại còn nhanh hơn tra bảng, và dùng lại thì lỡ dịp gọi LLM."""
        bam = ai_memory.bam_dau_vao("lead-luat")
        await ai_memory.ghi_lai(
            db_session, agent=AGENT_LEAD_SCORING, scope_type=SCOPE_LEAD,
            input_hash=bam, output={"score": 40}, source=SOURCE_RULE, commit=True,
        )
        assert await ai_memory.tim_ban_cu(db_session, AGENT_LEAD_SCORING, bam) is None

    @pytest.mark.asyncio
    async def test_nho_lai_moi_nhat_truoc_va_dung_pham_vi(self, db_session: AsyncSession):
        goc = datetime.now(timezone.utc)
        for i in range(3):
            db_session.add(AiRun(
                id=_uid(), agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD,
                scope_id="lead-A", input_hash=f"h{i}",
                output_json=f'{{"action": "viec {i}"}}', source=SOURCE_RULE,
                created_at=goc - timedelta(minutes=10 - i),
            ))
        db_session.add(AiRun(
            id=_uid(), agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD,
            scope_id="lead-B", input_hash="hB", output_json='{"action": "cua lead khac"}',
            source=SOURCE_RULE, created_at=goc,
        ))
        await db_session.commit()

        lich_su = await ai_memory.nho_lai(
            db_session, agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD, scope_id="lead-A"
        )
        assert len(lich_su) == 3
        assert ai_memory.doc_output(lich_su[0])["action"] == "viec 2"

    @pytest.mark.asyncio
    async def test_danh_dau_ket_qua(self, db_session: AsyncSession, sales_user: User):
        ban = await ai_memory.ghi_lai(
            db_session, agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD,
            scope_id="lead-C", input_hash="h", output={"action": "Gọi khách"},
            source=SOURCE_RULE, commit=True,
        )
        sau = await ai_memory.danh_dau_ket_qua(
            db_session, run_id=ban.id, outcome=OUTCOME_DONE, user_id=sales_user.id,
            note="Gọi lúc 9h sáng",
        )
        assert sau.outcome == OUTCOME_DONE
        assert sau.outcome_by == sales_user.id
        assert sau.outcome_note == "Gọi lúc 9h sáng"

    @pytest.mark.asyncio
    async def test_outcome_la_rac_thi_bao_loi(self, db_session: AsyncSession, sales_user: User):
        ban = await ai_memory.ghi_lai(
            db_session, agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD,
            input_hash="h", output={}, source=SOURCE_RULE, commit=True,
        )
        with pytest.raises(ValueError):
            await ai_memory.danh_dau_ket_qua(
                db_session, run_id=ban.id, outcome="xong-roi-nhe", user_id=sales_user.id
            )

    @pytest.mark.asyncio
    async def test_khong_co_ban_ghi_thi_tra_none(self, db_session: AsyncSession, sales_user: User):
        ket = await ai_memory.danh_dau_ket_qua(
            db_session, run_id=_uid(), outcome=OUTCOME_DONE, user_id=sales_user.id
        )
        assert ket is None


class TestCoPilotKhongLap:
    @pytest.mark.asyncio
    async def test_lan_dau_co_goi_y_va_co_run_id(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User
    ):
        goi_y = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert goi_y["action"]
        assert goi_y["run_id"]
        assert goi_y["source"] == SOURCE_RULE
        assert goi_y["lich_su"] == []

    @pytest.mark.asyncio
    async def test_da_phan_hoi_thi_lan_sau_goi_y_viec_khac(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User
    ):
        dau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        await ai_memory.danh_dau_ket_qua(
            db_session, run_id=dau["run_id"], outcome=OUTCOME_DONE, user_id=sales_user.id
        )
        await db_session.commit()

        sau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert sau["action"] != dau["action"]
        assert len(sau["lich_su"]) == 1
        assert sau["lich_su"][0]["outcome"] == OUTCOME_DONE

    @pytest.mark.asyncio
    async def test_bo_qua_cung_duoc_tinh_la_da_phan_hoi(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User
    ):
        dau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        await ai_memory.danh_dau_ket_qua(
            db_session, run_id=dau["run_id"], outcome=OUTCOME_SKIPPED, user_id=sales_user.id
        )
        await db_session.commit()

        sau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert sau["action"] != dau["action"]

    @pytest.mark.asyncio
    async def test_chua_phan_hoi_thi_van_nhac_lai_viec_cu(
        self, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User
    ):
        """Chưa bấm gì = chưa làm. Nhắc lại đúng việc đó mới đúng, không phải lỗi."""
        dau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        sau = await sales_copilot.suggest_action(lead_cua_sale.id, sales_user.id, db_session)
        assert sau["action"] == dau["action"]

    @pytest.mark.asyncio
    async def test_lead_khong_ton_tai(self, db_session: AsyncSession, sales_user: User):
        with pytest.raises(ValueError):
            await sales_copilot.suggest_action(_uid(), sales_user.id, db_session)


class TestApiGoiY:
    @pytest.mark.asyncio
    async def test_sale_xin_duoc_goi_y(self, client, lead_cua_sale: Lead, sales_user: User):
        r = await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": lead_cua_sale.id},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] and data["run_id"]
        assert data["source"] in (SOURCE_LLM, SOURCE_RULE)

    @pytest.mark.asyncio
    async def test_ghi_nhan_da_lam_roi_doc_lai_lich_su(
        self, client, lead_cua_sale: Lead, sales_user: User
    ):
        goi_y = (await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": lead_cua_sale.id},
            headers=auth_header(sales_user),
        )).json()

        r = await client.post(
            f"/api/v1/ai/suggestions/{goi_y['run_id']}/outcome",
            json={"outcome": "done"},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "done"

        ls = await client.get(
            f"/api/v1/ai/suggestions/{lead_cua_sale.id}", headers=auth_header(sales_user)
        )
        assert ls.status_code == 200
        items = ls.json()["items"]
        assert len(items) == 1
        assert items[0]["outcome"] == "done"

    @pytest.mark.asyncio
    async def test_outcome_sai_thi_400(self, client, lead_cua_sale: Lead, sales_user: User):
        goi_y = (await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": lead_cua_sale.id},
            headers=auth_header(sales_user),
        )).json()
        r = await client.post(
            f"/api/v1/ai/suggestions/{goi_y['run_id']}/outcome",
            json={"outcome": "xong"},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_khong_co_run_id_thi_404(self, client, sales_user: User):
        r = await client.post(
            f"/api/v1/ai/suggestions/{_uid()}/outcome",
            json={"outcome": "done"},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_sale_khac_khong_xem_duoc_lead_nay(
        self, client, db_session: AsyncSession, lead_cua_sale: Lead
    ):
        nguoi_la = User(
            id=_uid(), full_name="Sale Khác", email="salekhac@test.com",
            password_hash="x", role="data_entry", department="SALES", is_active=True,
        )
        db_session.add(nguoi_la)
        await db_session.commit()

        r = await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": lead_cua_sale.id},
            headers=auth_header(nguoi_la),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_sale_khac_khong_ghi_nhan_ho_duoc(
        self, client, db_session: AsyncSession, lead_cua_sale: Lead, sales_user: User
    ):
        goi_y = (await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": lead_cua_sale.id},
            headers=auth_header(sales_user),
        )).json()

        nguoi_la = User(
            id=_uid(), full_name="Sale Khác 2", email="salekhac2@test.com",
            password_hash="x", role="data_entry", department="SALES", is_active=True,
        )
        db_session.add(nguoi_la)
        await db_session.commit()

        r = await client.post(
            f"/api/v1/ai/suggestions/{goi_y['run_id']}/outcome",
            json={"outcome": "done"},
            headers=auth_header(nguoi_la),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_lead_khong_ton_tai_thi_404(self, client, sales_user: User):
        r = await client.post(
            "/api/v1/ai/suggest-action",
            params={"lead_id": _uid()},
            headers=auth_header(sales_user),
        )
        assert r.status_code == 404
