"""Đo hiệu quả AI — AI hiện tại có giúp được ai không.

Chỉ đọc dữ liệu sẵn có, không ghi gì, không gọi LLM:
  * `ai_runs`    — gợi ý Co-Pilot + phản hồi Đã làm/Bỏ qua, nguồn LLM hay luật.
  * `leads`      — `ai_score` hiện tại và giai đoạn cuối (thắng/mất).
  * `activities` — `stage_change` để biết lead có đi tiếp sau gợi ý không.

Kế hoạch và cách đọc số: `docs/AI_EVOLUTION_PLAN.md`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import (
    AGENT_SALES_COPILOT,
    OUTCOME_DONE,
    OUTCOME_SKIPPED,
    SCOPE_LEAD,
    SOURCE_LLM,
    AiRun,
)
from app.models.lead import Activity, Lead

DIEM_CAO = 70
DIEM_THAP = 40
SO_NGAY_DI_TIEP = 7
# Chuyển sang Mất / Ngủ đông là lùi, không tính là "đi tiếp" (nhãn khớp STAGE_LABELS ở api/leads.py)
_DUOI_LUI = ("→ Mất", "→ Ngủ đông")


def _ti_le(tu: int, mau: int) -> float | None:
    """Phần trăm làm tròn 1 chữ số; không có mẫu thì None để giao diện hiện "chưa có số"."""
    return round(tu * 100 / mau, 1) if mau else None


def _ty_le_thang(leads: list[Lead]) -> dict:
    da_chot = [l for l in leads if l.stage in ("signed_design", "lost")]
    thang = sum(1 for l in da_chot if l.stage == "signed_design")
    return {"da_chot": len(da_chot), "thang": thang, "ti_le_thang": _ti_le(thang, len(da_chot))}


async def tinh_hieu_qua(db: AsyncSession, so_ngay: int = 30) -> dict:
    tu_ngay = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=so_ngay)

    # 1 + 4: gợi ý Co-Pilot trong kỳ
    goi_y = list((await db.execute(
        select(AiRun).where(AiRun.agent == AGENT_SALES_COPILOT, AiRun.created_at >= tu_ngay)
    )).scalars())
    da_lam = [g for g in goi_y if g.outcome == OUTCOME_DONE]
    bo_qua = [g for g in goi_y if g.outcome == OUTCOME_SKIPPED]

    # 2: lead tạo trong kỳ, có điểm AI
    leads = list((await db.execute(
        select(Lead).where(Lead.created_at >= tu_ngay, Lead.ai_score.is_not(None))
    )).scalars())
    diem_cao = [l for l in leads if l.ai_score >= DIEM_CAO]
    diem_thap = [l for l in leads if l.ai_score < DIEM_THAP]

    # 3: sau gợi ý, lead có chuyển giai đoạn tiến lên trong 7 ngày không
    lead_ids = {g.scope_id for g in da_lam + bo_qua if g.scope_type == SCOPE_LEAD and g.scope_id}
    chuyen_stage = list((await db.execute(
        select(Activity).where(Activity.type == "stage_change", Activity.lead_id.in_(lead_ids))
    )).scalars()) if lead_ids else []

    def _di_tiep(g: AiRun) -> bool:
        han = g.created_at + timedelta(days=SO_NGAY_DI_TIEP)
        return any(
            a.lead_id == g.scope_id and g.created_at <= a.created_at <= han
            and not a.content.split(" — ")[0].endswith(_DUOI_LUI)
            for a in chuyen_stage
        )

    return {
        "so_ngay": so_ngay,
        "goi_y": {
            "tong": len(goi_y),
            "da_lam": len(da_lam),
            "bo_qua": len(bo_qua),
            "chua_phan_hoi": len(goi_y) - len(da_lam) - len(bo_qua),
            "ti_le_lam": _ti_le(len(da_lam), len(da_lam) + len(bo_qua)),
        },
        "diem_lead": {
            "cao": _ty_le_thang(diem_cao),
            "thap": _ty_le_thang(diem_thap),
            # Điểm cao mà mất / điểm thấp mà thắng — chỗ AI chấm sai, đáng xem tay
            "cham_sai": [
                {"id": l.id, "name": l.name, "ai_score": l.ai_score, "stage": l.stage}
                for l in leads
                if (l.ai_score >= DIEM_CAO and l.stage == "lost")
                or (l.ai_score < DIEM_THAP and l.stage == "signed_design")
            ][:20],
        },
        "di_tiep_7_ngay": {
            "sau_da_lam": _ti_le(sum(map(_di_tiep, da_lam)), len(da_lam)),
            "sau_bo_qua": _ti_le(sum(map(_di_tiep, bo_qua)), len(bo_qua)),
        },
        "nguon": {
            "llm": sum(1 for g in goi_y if g.source == SOURCE_LLM),
            "luat": sum(1 for g in goi_y if g.source != SOURCE_LLM),
            "ti_le_llm": _ti_le(sum(1 for g in goi_y if g.source == SOURCE_LLM), len(goi_y)),
        },
    }
