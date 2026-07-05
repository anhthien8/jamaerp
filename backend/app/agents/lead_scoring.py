"""Lead Scoring Agent — AI-powered lead quality scoring with rule-based fallback."""

import json
import logging
from datetime import datetime, timezone

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.lead import Activity, Lead

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """Bạn là trợ lý AI đánh giá chất lượng khách hàng tiềm năng của JAMA HOME (công ty nội thất cao cấp).

NHIỆM VỤ: Phân tích dữ liệu khách hàng và đánh giá điểm chất lượng từ 0-100.

Dữ liệu đầu vào bao gồm:
- Budget: ngân sách ước tính (VND)
- Source: nguồn khách (facebook, zalo, website, referral, tiktok, other)
- Property_type: loại bất động sản (townhouse, apartment, villa, office, shophouse, other)
- Area_sqm: diện tích (m2)
- Total_activities: số lần liên hệ/tương tác
- Activity_types: các loại hoạt động đã có
- Days_since_created: số ngày kể từ khi tạo lead
- Days_since_last_contact: số ngày kể từ lần liên hệ cuối
- Stage: giai đoạn hiện tại

Trả về JSON với cấu trúc:
{
  "score": <int 0-100>,
  "factors": [
    {"name": "budget", "weight": <float>, "value": "<mô tả>"},
    {"name": "source", "weight": <float>, "value": "<mô tả>"},
    {"name": "property_type", "weight": <float>, "value": "<mô tả>"},
    {"name": "area", "weight": <float>, "value": "<mô tả>"},
    {"name": "engagement", "weight": <float>, "value": "<mô tả>"},
    {"name": "recency", "weight": <float>, "value": "<mô tả>"}
  ],
  "recommendations": ["<khuyến nghị 1>", "<khuyến nghị 2>"]
}

QUY TẮC ĐÁNH GIÁ:
1. Budget: >= 2 tỷ = cao (25đ), >= 1 tỷ = trung bình cao (18đ), >= 500 triệu = trung bình (12đ), < 500 triệu = thấp (5đ)
2. Source: referral = cao (20đ), website = trung bình cao (15đ), facebook/zalo = trung bình (10đ), tiktok = thấp (5đ), other = rất thấp (2đ)
3. Property_type: villa = cao (20đ), townhouse = trung bình cao (16đ), shophouse/office = trung bình (12đ), apartment = thấp (8đ)
4. Area: >= 200m2 = cao (15đ), >= 100m2 = trung bình (10đ), < 100m2 = thấp (5đ)
5. Engagement: >= 5 hoạt động = cao (15đ), >= 2 = trung bình (8đ), 0-1 = thấp (3đ)
6. Recency: < 3 ngày = cao (5đ), < 7 ngày = trung bình (3đ), >= 7 ngày = thấp (1đ)

ĐIỀU CHỈNH:
- Nếu stage = "potential" hoặc "signed_design" → +10 bonus
- Nếu days_since_last_contact > 14 → -10 penalty
- Nếu referral + villa/và budget lớn → bonus thêm 5

CHỈ trả JSON, không giải thích."""


def _build_lead_context(lead: Lead, activities: list[Activity]) -> str:
    """Build a text summary of the lead for LLM context."""
    total_activities = len(activities)
    activity_types = list({a.type for a in activities}) if activities else []
    days_since_created = (datetime.now(timezone.utc) - lead.created_at.replace(tzinfo=timezone.utc)).days if lead.created_at else 0
    days_since_last_contact = (
        (datetime.now(timezone.utc) - lead.last_contacted_at.replace(tzinfo=timezone.utc)).days
        if lead.last_contacted_at
        else days_since_created
    )

    return (
        f"Budget: {lead.estimated_budget or 'không rõ'} VND\n"
        f"Source: {lead.source or 'không rõ'}\n"
        f"Property_type: {lead.property_type or 'không rõ'}\n"
        f"Area_sqm: {lead.area_sqm or 'không rõ'}\n"
        f"Total_activities: {total_activities}\n"
        f"Activity_types: {', '.join(activity_types) if activity_types else 'chưa có'}\n"
        f"Days_since_created: {days_since_created}\n"
        f"Days_since_last_contact: {days_since_last_contact}\n"
        f"Stage: {lead.stage}\n"
        f"Priority: {lead.priority}"
    )


def _fallback_score(lead: Lead, activities: list[Activity]) -> dict:
    """Rule-based scoring fallback when LLM is unavailable."""
    score = 0
    factors = []

    # Budget scoring (0-25)
    budget = lead.estimated_budget
    if budget and budget >= 2_000_000_000:
        budget_score = 25
        budget_val = "Cao (>= 2 ty VND)"
    elif budget and budget >= 1_000_000_000:
        budget_score = 18
        budget_val = "Trung binh cao (>= 1 ty VND)"
    elif budget and budget >= 500_000_000:
        budget_score = 12
        budget_val = "Trung binh (>= 500 trieu VND)"
    elif budget:
        budget_score = 5
        budget_val = "Thap (< 500 trieu VND)"
    else:
        budget_score = 3
        budget_val = "Khong ro"
    score += budget_score
    factors.append({"name": "budget", "weight": 0.25, "value": budget_val})

    # Source scoring (0-20)
    source_scores = {
        "referral": (20, "Referral - khach gioi thieu"),
        "website": (15, "Website - khach tu tim"),
        "facebook": (10, "Facebook"),
        "zalo": (10, "Zalo"),
        "tiktok": (5, "TikTok"),
    }
    source = lead.source
    source_score, source_val = source_scores.get(source, (2, f"Khac: {source or 'khong ro'}"))
    score += source_score
    factors.append({"name": "source", "weight": 0.20, "value": source_val})

    # Property type scoring (0-20)
    prop_scores = {
        "villa": (20, "Villa"),
        "townhouse": (16, "Nha pho"),
        "shophouse": (12, "Shophouse"),
        "office": (12, "Van phong"),
        "apartment": (8, "Can ho"),
    }
    prop = lead.property_type
    prop_score, prop_val = prop_scores.get(prop, (5, f"Khac: {prop or 'khong ro'}"))
    score += prop_score
    factors.append({"name": "property_type", "weight": 0.20, "value": prop_val})

    # Area scoring (0-15)
    area = lead.area_sqm
    if area and area >= 200:
        area_score = 15
        area_val = f"Lon ({area}m2)"
    elif area and area >= 100:
        area_score = 10
        area_val = f"Trung binh ({area}m2)"
    elif area:
        area_score = 5
        area_val = f"Nho ({area}m2)"
    else:
        area_score = 3
        area_val = "Khong ro"
    score += area_score
    factors.append({"name": "area", "weight": 0.15, "value": area_val})

    # Engagement scoring (0-15)
    total_acts = len(activities)
    if total_acts >= 5:
        eng_score = 15
        eng_val = f"Cao ({total_acts} hoat dong)"
    elif total_acts >= 2:
        eng_score = 8
        eng_val = f"Trung binh ({total_acts} hoat dong)"
    else:
        eng_score = 3
        eng_val = f"Thap ({total_acts} hoat dong)"
    score += eng_score
    factors.append({"name": "engagement", "weight": 0.15, "value": eng_val})

    # Recency scoring (0-5)
    days_since_last = 0
    if lead.last_contacted_at:
        days_since_last = (datetime.now(timezone.utc) - lead.last_contacted_at.replace(tzinfo=timezone.utc)).days
    else:
        days_since_last = (datetime.now(timezone.utc) - lead.created_at.replace(tzinfo=timezone.utc)).days if lead.created_at else 0

    if days_since_last < 3:
        recency_score = 5
        recency_val = f"Moi ({days_since_last} ngay)"
    elif days_since_last < 7:
        recency_score = 3
        recency_val = f"Tam OK ({days_since_last} ngay)"
    else:
        recency_score = 1
        recency_val = f"Cu ({days_since_last} ngay)"
    score += recency_score
    factors.append({"name": "recency", "weight": 0.05, "value": recency_val})

    # Bonuses and penalties
    if lead.stage in ("potential", "signed_design"):
        score += 10
    if days_since_last > 14:
        score -= 10
    if source == "referral" and prop == "villa" and budget and budget >= 1_000_000_000:
        score += 5

    score = max(0, min(100, score))

    # Generate recommendations
    recommendations = _generate_rule_recommendations(lead, activities, score, days_since_last)

    return {"score": score, "factors": factors, "recommendations": recommendations}


def _generate_rule_recommendations(
    lead: Lead, activities: list[Activity], score: int, days_since_last: int
) -> list[str]:
    """Generate actionable recommendations based on rule scoring."""
    recs: list[str] = []

    if score >= 75:
        recs.append("Khach hang cuc chat luong — uu tien tiep can ngay lap tuc.")
    elif score >= 50:
        recs.append("Khach hang co tiem nang — nen lien he trong vong 24h.")
    elif score >= 30:
        recs.append("Khach hang trung binh — theo doi va tu van khi co co hoi.")
    else:
        recs.append("Khach hang thap — chi nen dau tu khi co tin hieu tu van.")

    if days_since_last > 14:
        recs.append("Da qua lau tu lien he cuoi — can lien he lai ngay.")
    elif days_since_last > 7:
        recs.append("Nen lien he lai de duy tri su quan tam.")

    if not lead.estimated_budget:
        recs.append("Chua co ngan sach — can xac minh ngan sach khach.")
    if not lead.area_sqm:
        recs.append("Chua co dien tich — can hoi them chi tiet.")
    if len(activities) == 0:
        recs.append("Chua co hoat dong nao — bat dau tu van ngay.")
    if lead.source == "referral":
        recs.append("Khach tu gioi thieu — uu tien dao tao va cham soc dac biet.")
    if lead.property_type == "villa":
        recs.append("Biet thu/villa — kha nang gia tri don hang cao.")
    if lead.stage == "new":
        recs.append("Lead moi — can xu ly va phan loai ngay.")

    return recs[:5]


async def score_lead_agent(lead_id: str, db: AsyncSession) -> dict:
    """Score a lead 0-100 using LLM with rule-based fallback.

    Args:
        lead_id: UUID of the lead to score.
        db: Async SQLAlchemy session.

    Returns:
        dict with keys: score, factors, recommendations.
    """
    # Fetch lead
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    # Fetch activities
    act_result = await db.execute(
        select(Activity)
        .where(Activity.lead_id == lead_id)
        .order_by(Activity.created_at.desc())
    )
    activities = list(act_result.scalars().all())

    # Attempt LLM scoring
    if settings.LLM_API_KEY:
        try:
            lead_context = _build_lead_context(lead, activities)

            response = await acompletion(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": lead_context},
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            # Validate and normalize
            score = max(0, min(100, int(data.get("score", 0))))
            factors = data.get("factors", [])
            recommendations = data.get("recommendations", [])

            if not isinstance(factors, list) or not isinstance(recommendations, list):
                raise ValueError("Invalid LLM response structure")

            # Ensure all expected factor names are present
            expected = {"budget", "source", "property_type", "area", "engagement", "recency"}
            present = {f.get("name") for f in factors if isinstance(f, dict)}
            if not expected.issubset(present):
                # Fill missing factors from fallback
                fallback = _fallback_score(lead, activities)
                existing_map = {f["name"]: f for f in factors if isinstance(f, dict)}
                for fb in fallback["factors"]:
                    if fb["name"] not in existing_map:
                        factors.append(fb)
                if not recommendations:
                    recommendations = fallback["recommendations"]

            result_data = {"score": score, "factors": factors, "recommendations": recommendations}

            # Persist score to DB
            lead.ai_score = float(score)
            lead.ai_notes = json.dumps(result_data, ensure_ascii=False)
            await db.commit()

            logger.info("Lead %s scored %d via LLM", lead_id, score)
            return result_data

        except Exception as e:
            logger.warning("LLM scoring failed for lead %s: %s — using fallback", lead_id, e)

    # Rule-based fallback
    result_data = _fallback_score(lead, activities)

    # Persist score to DB
    lead.ai_score = float(result_data["score"])
    lead.ai_notes = json.dumps(result_data, ensure_ascii=False)
    await db.commit()

    logger.info("Lead %s scored %d via rule-based fallback", lead_id, result_data["score"])
    return result_data
