"""Zalo message analysis — trích TÍN HIỆU công việc từ hội thoại nhóm (spec 09 §4).

Rule-based làm nền (chạy luôn, không cần LLM) + LLM enrichment tùy chọn.
Nguyên tắc: chỉ trích tín hiệu công việc, bỏ qua chuyện phiếm cá nhân.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zalo import ZaloGroup, ZaloMessage, ZaloSignal
from app.models.lead import Lead

logger = logging.getLogger(__name__)

# SĐT VN: 0xxxxxxxxx (10 số) hoặc +84xxxxxxxxx
_PHONE_RE = re.compile(r"(?:(?:\+?84)|0)(?:\d[\s.]?){9}")

_QUOTE_KEYWORDS = ("báo giá", "bao gia", "bao nhiêu", "giá bao nhiêu", "chi phí", "dự toán", "du toan", "báo giá giúp")
_COMMIT_KEYWORDS = ("gửi", "gui", "hẹn", "hen", "sẽ", "se ", "chốt", "chot", "xong trước", "deadline", "trước ngày")
_RISK_KEYWORDS = ("không hài lòng", "thất vọng", "chậm quá", "cham qua", "hủy", "huy ", "phàn nàn", "chờ lâu", "cho lau", "đắt quá", "dat qua")
_DATE_HINT_RE = re.compile(r"(thứ\s*[2-7]|thứ\s*hai|thứ\s*ba|thứ\s*tư|thứ\s*năm|thứ\s*sáu|thứ\s*bảy|chủ\s*nhật|ngày\s*\d{1,2}|\d{1,2}[/-]\d{1,2}|cuối tuần|hôm nay|ngày mai|mai\b|mốt\b)", re.IGNORECASE)


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^\d]", "", raw)
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits


async def _phone_is_new(db: AsyncSession, phone: str) -> bool:
    """Chống trùng: SĐT đã là lead thì không tạo lead_candidate nữa."""
    result = await db.execute(select(Lead.id).where(Lead.phone == phone).limit(1))
    return result.first() is None


def _rule_based_signals(text: str) -> list[dict]:
    """Trả list {type, summary, payload} từ 1 tin nhắn — không cần LLM."""
    signals: list[dict] = []
    low = text.lower()

    # 1. Lead candidate: có SĐT
    for m in _PHONE_RE.finditer(text):
        phone = _normalize_phone(m.group())
        if len(phone) == 10 and phone.startswith("0"):
            signals.append({
                "type": "lead_candidate",
                "summary": f"Phát hiện SĐT {phone} trong hội thoại",
                "payload": {"phone": phone, "excerpt": text[:200]},
            })
            break  # 1 SĐT/tin là đủ

    # 2. Quote request
    if any(k in low for k in _QUOTE_KEYWORDS):
        signals.append({
            "type": "quote_request",
            "summary": "Khách hỏi giá/báo giá — gợi ý dùng /quote-tool",
            "payload": {"excerpt": text[:200]},
        })

    # 3. Commitment: động từ cam kết + gợi ý thời gian
    if any(k in low for k in _COMMIT_KEYWORDS) and _DATE_HINT_RE.search(text):
        deadline = _DATE_HINT_RE.search(text)
        signals.append({
            "type": "commitment",
            "summary": f"Cam kết có mốc thời gian: \"{text[:120]}\"",
            "payload": {"excerpt": text[:200], "deadline_hint": deadline.group() if deadline else None},
        })

    # 4. Deal risk: khách tỏ ý không hài lòng
    if any(k in low for k in _RISK_KEYWORDS):
        signals.append({
            "type": "deal_risk",
            "summary": f"Dấu hiệu khách không hài lòng: \"{text[:120]}\"",
            "payload": {"excerpt": text[:200]},
        })

    return signals


async def _llm_enrich(text: str) -> list[dict]:
    """LLM tinh chỉnh (tùy chọn) — bắt tín hiệu tinh vi rule-based bỏ lỡ."""
    from app.services.llm_config import llm_available, llm_complete
    if not await llm_available():
        return []
    try:
        prompt = (
            "Bạn phân tích 1 tin nhắn trong nhóm chat công việc của công ty nội thất. "
            "Trả JSON {\"signals\": [{\"type\": \"lead_candidate|quote_request|commitment|deal_risk|unanswered\", "
            "\"summary\": \"...\"}]}. Chỉ trích tín hiệu CÔNG VIỆC (khách hàng, deal, cam kết, rủi ro). "
            "Bỏ qua chuyện phiếm. Nếu không có tín hiệu, trả {\"signals\": []}.\n\n"
            f"Tin nhắn: {text[:500]}"
        )
        raw = await llm_complete(
            [{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=300,
            response_format={"type": "json_object"},
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        out = []
        for s in (data.get("signals") or [])[:3]:
            if s.get("type") and s.get("summary"):
                out.append({"type": s["type"], "summary": s["summary"][:500], "payload": {"excerpt": text[:200], "by": "llm"}})
        return out
    except Exception as exc:
        logger.debug("Zalo LLM enrich skipped: %s", exc)
        return []


async def analyze_and_store(db: AsyncSession, message: ZaloMessage, group: ZaloGroup, use_llm: bool = False) -> list[ZaloSignal]:
    """Phân tích 1 tin → tạo ZaloSignal (chống trùng lead). Trả list signal đã tạo."""
    text = (message.text or "").strip()
    if not text:
        return []

    raw_signals = _rule_based_signals(text)
    if use_llm:
        # Chỉ gọi LLM khi rule-based không bắt được gì (tiết kiệm quota)
        if not raw_signals:
            raw_signals = await _llm_enrich(text)

    created: list[ZaloSignal] = []
    for sig in raw_signals:
        # Chống trùng lead: SĐT đã có trong hệ thống → bỏ
        if sig["type"] == "lead_candidate":
            phone = sig.get("payload", {}).get("phone")
            if phone and not await _phone_is_new(db, phone):
                continue

        signal = ZaloSignal(
            id=str(uuid.uuid4()),
            group_id=group.id,
            source_msg_id=message.id,
            type=sig["type"],
            summary=sig["summary"],
            payload_json=json.dumps(sig.get("payload", {}), ensure_ascii=False),
            status="new",
            assigned_user_id=group.assigned_user_id,
        )
        db.add(signal)
        created.append(signal)

    if created:
        await db.flush()
    return created


async def purge_old_messages(db: AsyncSession, days: int = 7) -> int:
    """Job đêm: xóa ZaloMessage thô >N ngày (giữ ZaloSignal). Trả số dòng xóa."""
    from datetime import timedelta
    from sqlalchemy import delete
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        delete(ZaloMessage).where(ZaloMessage.created_at < cutoff)
    )
    await db.flush()
    return result.rowcount or 0
