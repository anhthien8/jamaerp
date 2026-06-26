"""Lead Intake Agent — NLP parsing of Zalo/raw text into structured lead data."""

import json
import re
from decimal import Decimal

from litellm import acompletion
from app.config import get_settings
from app.schemas.lead import LeadParseResponse

settings = get_settings()

SYSTEM_PROMPT = """Bạn là trợ lý AI của JAMA HOME (công ty nội thất cao cấp).
Nhiệm vụ: Trích xuất thông tin khách hàng tiềm năng từ tin nhắn Zalo hoặc ghi chú.

Trả về JSON với các trường:
- name: tên khách hàng (bắt buộc)
- phone: số điện thoại (bắt buộc, format 0xxx)
- contact_person: tên người liên hệ
- address: địa chỉ nhà/dự án
- needs: nhu cầu thiết kế/thi công
- source: nguồn (facebook, zalo, website, referral, tiktok, other)
- property_type: loại nhà (townhouse, apartment, villa, office, shophouse, other)
- area_sqm: diện tích (m2, chỉ số)
- estimated_budget: ngân sách ước tính (VND, chỉ số)
- confidence: độ chắc chắn 0-1

Quy tắc:
1. Nếu không tìm thấy trường nào → null
2. Budget format VND: 200 triệu → 200000000, 1.5 tỷ → 1500000000
3. Confidence = % các trường bắt buộc được tìm thấy
4. CHỈ trả JSON, không giải thích
"""


async def parse_lead_text(raw_text: str) -> LeadParseResponse:
    """Parse raw text using LLM → structured lead data."""
    try:
        response = await acompletion(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        return LeadParseResponse(
            name=data.get("name"),
            phone=data.get("phone"),
            contact_person=data.get("contact_person"),
            address=data.get("address"),
            needs=data.get("needs"),
            source=data.get("source"),
            property_type=data.get("property_type"),
            area_sqm=Decimal(str(data["area_sqm"])) if data.get("area_sqm") else None,
            estimated_budget=Decimal(str(data["estimated_budget"])) if data.get("estimated_budget") else None,
            confidence=data.get("confidence", 0.0),
            raw_text=raw_text,
        )

    except Exception as e:
        # Fallback: try regex extraction
        return _fallback_parse(raw_text)


def _fallback_parse(text: str) -> LeadParseResponse:
    """Regex fallback when LLM is unavailable."""
    # Try to extract phone
    phone_match = re.search(r'0\d{9,10}', text)
    phone = phone_match.group() if phone_match else None

    # Try to extract name (first line or "Anh/Chị X")
    name_match = re.search(r'(?:Anh|Chị|A\.|C\.)\s+([A-ZĐa-zđàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ\s]+)', text)
    name = name_match.group(1).strip() if name_match else None

    # Budget
    budget = None
    budget_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:tỷ|ty)', text, re.IGNORECASE)
    if budget_match:
        budget = Decimal(str(float(budget_match.group(1)) * 1_000_000_000))
    else:
        budget_match = re.search(r'(\d+)\s*(?:triệu|tr)', text, re.IGNORECASE)
        if budget_match:
            budget = Decimal(str(int(budget_match.group(1)) * 1_000_000))

    # Area
    area = None
    area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m2|m²)', text, re.IGNORECASE)
    if area_match:
        area = Decimal(area_match.group(1))

    confidence = 0.0
    if name:
        confidence += 0.3
    if phone:
        confidence += 0.4
    if budget:
        confidence += 0.15
    if area:
        confidence += 0.15

    return LeadParseResponse(
        name=name,
        phone=phone,
        estimated_budget=budget,
        area_sqm=area,
        confidence=round(confidence, 2),
        raw_text=text,
    )
