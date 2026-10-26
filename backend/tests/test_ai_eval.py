"""Đo hiệu quả AI — dữ liệu mẫu biết trước đáp số, và chỉ admin được xem."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import (
    AGENT_SALES_COPILOT,
    OUTCOME_DONE,
    OUTCOME_SKIPPED,
    SCOPE_LEAD,
    SOURCE_LLM,
    SOURCE_RULE,
    AiRun,
)
from app.models.lead import Activity, Lead
from app.models.user import User
from app.services import ai_eval
from tests.conftest import auth_header


def _uid() -> str:
    return str(uuid.uuid4())


def _luc(ngay_truoc: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=ngay_truoc)


def _lead(sale: User, diem: float, stage: str) -> Lead:
    return Lead(
        id=_uid(), name=f"Lead {diem}", phone="0909000000", source="facebook",
        stage=stage, ai_score=diem, assigned_to=sale.id, created_at=_luc(10),
    )


def _goi_y(lead: Lead, outcome: str | None, source: str = SOURCE_RULE) -> AiRun:
    return AiRun(
        agent=AGENT_SALES_COPILOT, scope_type=SCOPE_LEAD, scope_id=lead.id,
        input_hash=_uid().replace("-", ""), source=source, outcome=outcome,
        created_at=_luc(5),
    )


@pytest_asyncio.fixture
async def du_lieu(db_session: AsyncSession, sales_user: User):
    # 2 lead điểm cao: 1 thắng, 1 mất (mất = chấm sai); 2 lead điểm thấp: cả 2 mất
    cao_thang = _lead(sales_user, 85, "signed_design")
    cao_mat = _lead(sales_user, 75, "lost")
    thap_1 = _lead(sales_user, 20, "lost")
    thap_2 = _lead(sales_user, 30, "lost")
    db_session.add_all([cao_thang, cao_mat, thap_1, thap_2])

    # 3 gợi ý: 2 đã làm (1 LLM), 1 bỏ qua, 1 chưa phản hồi
    db_session.add_all([
        _goi_y(cao_thang, OUTCOME_DONE, SOURCE_LLM),
        _goi_y(thap_1, OUTCOME_DONE),
        _goi_y(cao_mat, OUTCOME_SKIPPED),
        _goi_y(thap_2, None),
    ])

    # cao_thang tiến lên sau gợi ý (tính); thap_1 sang Mất (lùi, không tính);
    # cao_mat đổi stage TRƯỚC gợi ý (không tính)
    db_session.add_all([
        Activity(lead_id=cao_thang.id, user_id=sales_user.id, type="stage_change",
                 content="Chuyển stage: Đang tư vấn → Đã gửi báo giá", created_at=_luc(3)),
        Activity(lead_id=thap_1.id, user_id=sales_user.id, type="stage_change",
                 content="Chuyển stage: Đang tư vấn → Mất — Lý do: hết ngân sách", created_at=_luc(3)),
        Activity(lead_id=cao_mat.id, user_id=sales_user.id, type="stage_change",
                 content="Chuyển stage: Tiếp nhận mới → Đang tư vấn", created_at=_luc(8)),
    ])
    await db_session.commit()
    return cao_mat


class TestTinhHieuQua:
    @pytest.mark.asyncio
    async def test_bon_chi_so_dung_dap_so(self, db_session: AsyncSession, du_lieu: Lead):
        kq = await ai_eval.tinh_hieu_qua(db_session, so_ngay=30)

        assert kq["goi_y"] == {
            "tong": 4, "da_lam": 2, "bo_qua": 1, "chua_phan_hoi": 1, "ti_le_lam": 66.7,
        }
        assert kq["diem_lead"]["cao"] == {"da_chot": 2, "thang": 1, "ti_le_thang": 50.0}
        assert kq["diem_lead"]["thap"] == {"da_chot": 2, "thang": 0, "ti_le_thang": 0.0}
        assert [l["id"] for l in kq["diem_lead"]["cham_sai"]] == [du_lieu.id]
        # Đã làm: 1/2 đi tiếp (lead kia sang Mất là lùi); Bỏ qua: đổi stage trước gợi ý, không tính
        assert kq["di_tiep_7_ngay"] == {"sau_da_lam": 50.0, "sau_bo_qua": 0.0}
        assert kq["nguon"] == {"llm": 1, "luat": 3, "ti_le_llm": 25.0}

    @pytest.mark.asyncio
    async def test_khong_co_du_lieu_thi_khong_chia_cho_0(self, db_session: AsyncSession):
        kq = await ai_eval.tinh_hieu_qua(db_session, so_ngay=30)
        assert kq["goi_y"]["ti_le_lam"] is None
        assert kq["diem_lead"]["cao"]["ti_le_thang"] is None
        assert kq["nguon"]["ti_le_llm"] is None


class TestApiHieuQua:
    @pytest.mark.asyncio
    async def test_admin_xem_duoc(self, client, admin_user: User):
        r = await client.get("/api/v1/ai/hieu-qua", headers=auth_header(admin_user))
        assert r.status_code == 200
        assert r.json()["so_ngay"] == 30

    @pytest.mark.asyncio
    async def test_sale_bi_chan(self, client, sales_user: User):
        r = await client.get("/api/v1/ai/hieu-qua", headers=auth_header(sales_user))
        assert r.status_code == 403
