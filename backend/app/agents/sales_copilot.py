"""Sales Co-Pilot Agent — suggest next actions for leads."""

import json
from uuid import UUID

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.lead import Lead, Activity, LeadStage

settings = get_settings()

SYSTEM_PROMPT = """Bạn là Sales Co-Pilot AI của JAMA HOME (nội thất cao cấp).
Dựa trên thông tin lead và lịch sử tương tác, đề xuất hành động tiếp theo.

Pipeline 7 giai đoạn:
1. Mới tiếp nhận → Cần liên hệ trong ngày
2. Có nhu cầu → Hẹn khảo sát
3. Đã hẹn khảo sát → Thực hiện khảo sát
4. KH tiềm năng → Gửi báo giá, thuyết phục ký
5. Ký thiết kế → Auto tạo Project

Trả về JSON:
{
  "action": "hành động cụ thể",
  "reason": "lý do ngắn gọn",
  "priority": "high/medium/low",
  "message_template": "mẫu tin nhắn gợi ý (nếu có)"
}
"""


async def suggest_action(lead_id: str, user_id: str, db: AsyncSession) -> dict:
    """Generate AI suggestion for a lead."""
    # Fetch lead + activities
    result = await db.execute(select(Lead).where(Lead.id == UUID(lead_id)))
    lead = result.scalar_one_or_none()

    if not lead:
        return {"action": "Lead không tồn tại", "reason": "N/A", "priority": "low"}

    # Fetch recent activities
    act_result = await db.execute(
        select(Activity)
        .where(Activity.lead_id == UUID(lead_id))
        .order_by(Activity.created_at.desc())
        .limit(5)
    )
    activities = act_result.scalars().all()

    # Build context
    context = f"""Lead: {lead.name}
Giai đoạn: {lead.stage}
Nguồn: {lead.source or 'N/A'}
Ngân sách: {lead.estimated_budget or 'N/A'} VND
Diện tích: {lead.area_sqm or 'N/A'} m²
Nhu cầu: {lead.needs or 'N/A'}
Liên hệ gần nhất: {lead.last_contacted_at or 'Chưa liên hệ'}
Số lần tương tác: {len(activities)}
Hoạt động gần nhất: {activities[0].content if activities else 'Chưa có'}"""

    try:
        response = await acompletion(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    except Exception:
        # Fallback rule-based suggestions
        return _rule_based_suggestion(lead, activities)


def _rule_based_suggestion(lead: Lead, activities: list[Activity]) -> dict:
    """Fallback when LLM unavailable."""
    stage = lead.stage

    if stage == LeadStage.NEW:
        return {
            "action": "Gọi điện giới thiệu dịch vụ JAMA HOME",
            "reason": "Lead mới, cần liên hệ trong ngày (Quy tắc vàng #1)",
            "priority": "high",
            "message_template": f"Xin chào {lead.contact_person or lead.name}, em là [Tên] từ JAMA HOME. Em được biết anh/chị đang quan tâm đến thiết kế nội thất..."
        }
    elif stage == LeadStage.INTERESTED:
        return {
            "action": "Hẹn lịch khảo sát thực tế",
            "reason": "KH đã có nhu cầu, cần khảo sát để lên phương án",
            "priority": "high",
            "message_template": f"Anh/Chị {lead.contact_person or lead.name}, JAMA HOME xin hẹn khảo sát thực tế nhà anh/chị vào [ngày]. Thời gian khoảng 30-45 phút ạ."
        }
    elif stage == LeadStage.SURVEY_SCHEDULED:
        return {
            "action": "Xác nhận lịch khảo sát và chuẩn bị hồ sơ",
            "reason": "Đã hẹn khảo sát, cần xác nhận lại để tránh bị hủy",
            "priority": "medium",
        }
    elif stage == LeadStage.POTENTIAL:
        return {
            "action": "Gửi phương án thiết kế sơ bộ + báo giá",
            "reason": "KH tiềm năng, cần push để ký hợp đồng thiết kế",
            "priority": "high",
        }
    else:
        return {
            "action": "Theo dõi tiến độ dự án",
            "reason": "Đã ký hợp đồng",
            "priority": "low",
        }
