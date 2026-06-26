"""AI API — rule-based lead parsing, action suggestions, scoring."""

import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.lead import Lead

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


@router.post("/suggest-action")
async def suggest_action(
    lead_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest next action for a lead based on rules."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    # Rule-based suggestions
    suggestions = []

    # Not assigned
    if not lead.assigned_to:
        suggestions.append({
            "action": "assign",
            "reason": "Lead chưa được phân công cho nhân viên nào",
            "priority": "high",
            "message_template": None,
        })

    # No contact yet
    if not lead.last_contacted_at:
        suggestions.append({
            "action": "call",
            "reason": "Chưa liên hệ khách hàng lần nào",
            "priority": "high",
            "message_template": f"Chào anh/chị {lead.name}, em là nhân viên tư vấn JAMA HOME. Em gọi để trao đổi về nhu cầu thiết kế nội thất ạ.",
        })

    # High budget
    if lead.estimated_budget and lead.estimated_budget >= 1_000_000_000:
        suggestions.append({
            "action": "escalate",
            "reason": f"Ngân sách cao ({lead.estimated_budget/1_000_000:.0f} triệu), cần ưu tiên chăm sóc",
            "priority": "urgent",
            "message_template": None,
        })

    # Stage-based
    stage_actions = {
        "new": {"action": "call", "reason": "Lead mới, cần gọi tư vấn ngay"},
        "interested": {"action": "survey", "reason": "KH quan tâm, hẹn khảo sát hiện trạng"},
        "survey_scheduled": {"action": "meeting", "reason": "Chuẩn bị hồ sơ khảo sát & thiết kế"},
        "potential": {"action": "proposal", "reason": "Gửi báo giá & phương án thiết kế"},
    }
    if lead.stage in stage_actions:
        sa = stage_actions[lead.stage]
        suggestions.append({
            "action": sa["action"],
            "reason": sa["reason"],
            "priority": "medium",
            "message_template": None,
        })

    if not suggestions:
        suggestions.append({
            "action": "note",
            "reason": "Cập nhật tình trạng lead",
            "priority": "low",
            "message_template": None,
        })

    return suggestions[0]  # Return top suggestion


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
        from datetime import timezone, timedelta
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
