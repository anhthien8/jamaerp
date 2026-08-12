"""AI API — parse lead, gợi ý hành động (Sales Co-Pilot), chấm điểm."""

import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sales_copilot import (
    SO_GOI_Y_NHO_LAI,
    suggest_action as copilot_suggest_action,
    tom_luoc_ban_ghi,
)
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import can_modify_lead, can_view_lead
from app.models.ai_memory import (
    AGENT_SALES_COPILOT,
    OUTCOMES,
    SCOPE_LEAD,
    AiRun,
)
from app.models.user import User
from app.models.lead import Lead
from app.services import ai_memory

router = APIRouter(prefix="/ai", tags=["ai"])

# Phone patterns
PHONE_PATTERN = re.compile(r"(?:0|\+84)\d{9,10}")
# Budget patterns (Vietnamese currency)
BUDGET_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:tỷ|ty|triệu|trieu|tr|t)", re.IGNORECASE)
# Area patterns
AREA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:m2|m²|mét vuông)", re.IGNORECASE)

SOURCE_KEYWORDS = {
    "facebook": ["fb", "facebook", "face"],
    "zalo": ["zalo", "zl"],
    "tiktok": ["tiktok", "tt"],
    "website": ["web", "website", "site"],
    "referral": ["giới thiệu", "recommend", "ref"],
}

PROPERTY_KEYWORDS = {
    "townhouse": ["nhà phố", "nha pho", "townhouse"],
    "apartment": ["căn hộ", "can ho", "apartment", "chung cư"],
    "villa": ["biệt thự", "biet thu", "villa"],
    "office": ["văn phòng", "van phong", "office"],
    "shophouse": ["shophouse", "shop house"],
}


def parse_budget(text: str) -> float | None:
    """Extract budget from Vietnamese text."""
    matches = BUDGET_PATTERN.findall(text)
    if not matches:
        return None
    value = float(matches[0])
    text_lower = text.lower()
    if "tỷ" in text_lower or "ty" in text_lower:
        return value * 1_000_000_000
    return value * 1_000_000


def detect_source(text: str) -> str | None:
    text_lower = text.lower()
    for source, keywords in SOURCE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return source
    return None


def detect_property_type(text: str) -> str | None:
    text_lower = text.lower()
    for ptype, keywords in PROPERTY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return ptype
    return None


@router.post("/parse-lead")
async def parse_lead(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Parse unstructured text into lead fields. Rule-based, no LLM required."""
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Cần nhập text để parse")

    # Extract phone
    phones = PHONE_PATTERN.findall(text)
    phone = phones[0] if phones else None

    # Extract budget
    budget = parse_budget(text)

    # Extract area
    areas = AREA_PATTERN.findall(text)
    area = float(areas[0]) if areas else None

    # Detect source & property type
    source = detect_source(text)
    property_type = detect_property_type(text)

    # Try to extract name (first line or text before phone)
    lines = text.strip().split("\n")
    name = lines[0].strip() if lines else None
    if name and phone and phone in name:
        name = name.replace(phone, "").strip(" :-,")

    # Confidence scoring
    confidence = 0.3
    if phone:
        confidence += 0.25
    if budget:
        confidence += 0.2
    if property_type:
        confidence += 0.15
    if area:
        confidence += 0.1

    return {
        "name": name,
        "phone": phone,
        "contact_person": None,
        "address": None,
        "needs": text[:200] if len(text) > 10 else None,
        "source": source,
        "property_type": property_type,
        "area_sqm": area,
        "estimated_budget": budget,
        "confidence": round(confidence, 2),
        "raw_text": text,
    }


async def _lay_lead_xem_duoc(lead_id: str, db: AsyncSession, current_user: User) -> Lead:
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")
    if not can_view_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Bạn không xem được lead này")
    return lead


@router.post("/suggest-action")
async def suggest_action(
    lead_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gợi ý việc nên làm tiếp với lead này.

    Đi qua Sales Co-Pilot: có LLM thì dùng LLM, không thì bộ luật. Cả hai đường
    đều được ghi vào bộ nhớ (`ai_runs`) và đều bỏ qua những gợi ý sale đã phản hồi.
    """
    await _lay_lead_xem_duoc(lead_id, db, current_user)
    return await copilot_suggest_action(lead_id, current_user.id, db)


@router.get("/suggestions/{lead_id}")
async def lich_su_goi_y(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(SO_GOI_Y_NHO_LAI, ge=1, le=50),
):
    """Các gợi ý Co-Pilot đã đưa cho lead này, mới nhất trước."""
    await _lay_lead_xem_duoc(lead_id, db, current_user)
    lich_su = await ai_memory.nho_lai(
        db,
        agent=AGENT_SALES_COPILOT,
        scope_type=SCOPE_LEAD,
        scope_id=str(lead_id),
        limit=limit,
    )
    return {"items": [tom_luoc_ban_ghi(b) for b in lich_su], "total": len(lich_su)}


@router.post("/suggestions/{run_id}/outcome")
async def ghi_nhan_ket_qua(
    run_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sale bấm "Đã làm" / "Bỏ qua" trên một gợi ý.

    Đây là mấu chốt của bộ nhớ: có phản hồi thì vòng sau Co-Pilot mới biết đường
    đề xuất việc khác thay vì nhắc lại đúng câu cũ.
    """
    outcome = (data.get("outcome") or "").strip().lower()
    if outcome not in OUTCOMES:
        raise HTTPException(
            status_code=400, detail=f"Kết quả phải là một trong: {', '.join(OUTCOMES)}"
        )

    ban = await db.get(AiRun, run_id)
    if ban is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gợi ý này")

    # Gợi ý gắn với lead nào thì phải có quyền sửa lead đó mới được ghi nhận
    if ban.scope_type == SCOPE_LEAD and ban.scope_id:
        lead = (await db.execute(select(Lead).where(Lead.id == ban.scope_id))).scalar_one_or_none()
        if lead is not None and not can_modify_lead(current_user, lead):
            raise HTTPException(status_code=403, detail="Bạn không sửa được lead này")

    note = data.get("note")
    ban = await ai_memory.danh_dau_ket_qua(
        db, run_id=run_id, outcome=outcome, user_id=current_user.id,
        note=note.strip() if isinstance(note, str) and note.strip() else None,
    )
    return tom_luoc_ban_ghi(ban)


@router.post("/score-lead")
async def score_lead(
    lead_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a lead 0-100 based on rules."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    score = 30  # Base score

    # Budget weight
    if lead.estimated_budget:
        if lead.estimated_budget >= 2_000_000_000:
            score += 30
        elif lead.estimated_budget >= 1_000_000_000:
            score += 25
        elif lead.estimated_budget >= 500_000_000:
            score += 20
        elif lead.estimated_budget >= 200_000_000:
            score += 10

    # Source weight
    source_scores = {"referral": 20, "website": 15, "zalo": 12, "facebook": 10, "tiktok": 8}
    if lead.source and lead.source in source_scores:
        score += source_scores[lead.source]

    # Property type weight
    if lead.property_type in ("villa", "shophouse"):
        score += 10
    elif lead.property_type == "townhouse":
        score += 8

    # Contact recency
    if lead.last_contacted_at:
        from datetime import datetime, timezone, timedelta
        days_since = (datetime.now(timezone.utc) - lead.last_contacted_at.replace(tzinfo=timezone.utc)).days
        if days_since <= 1:
            score += 10
        elif days_since <= 3:
            score += 5

    score = min(100, max(0, score))

    # Update lead score
    lead.ai_score = score
    await db.flush()

    return {"lead_id": lead.id, "score": score, "name": lead.name}
