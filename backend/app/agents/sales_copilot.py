"""Sales Co-Pilot — gợi ý hành động tiếp theo cho một lead, có nhớ đã gợi ý gì.

Trước 12/08/2026 file này là **mã chết**: không nơi nào import, còn `/ai/suggest-action`
lại là một bộ luật riêng viết lại từ đầu trong `app/api/ai.py`. Bản này gộp cả hai và
nối vào `ai_runs`, nên Co-Pilot có ba thứ nó thiếu:

  * **Nhớ đã nói gì** — đọc lại N gợi ý gần nhất của chính lead đó.
  * **Biết sale có làm không** — mỗi gợi ý có ô "Đã làm" / "Bỏ qua".
  * **Không nói lại** — gợi ý nào sale đã phản hồi thì bộ luật bỏ qua, còn LLM
    nhận nguyên lịch sử đó trong prompt kèm lệnh cấm lặp.

Bộ luật vẫn là đường lui: LLM tắt, hết quota hay trả rác thì sale vẫn có gợi ý dùng được.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import (
    AGENT_SALES_COPILOT,
    SCOPE_LEAD,
    SOURCE_LLM,
    SOURCE_RULE,
    AiRun,
)
from app.models.lead import Activity, Lead
from app.services import ai_memory
from app.services.llm_config import llm_available, llm_complete

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là Sales Co-Pilot AI của JAMA HOME (nội thất cao cấp).
Dựa trên thông tin lead, lịch sử tương tác và các gợi ý đã đưa trước đó, đề xuất
MỘT hành động tiếp theo.

Pipeline 7 giai đoạn:
1. Mới tiếp nhận → Cần liên hệ trong ngày
2. Có nhu cầu → Hẹn khảo sát
3. Đã hẹn khảo sát → Thực hiện khảo sát
4. KH tiềm năng → Gửi báo giá, thuyết phục ký
5. Ký thiết kế → Auto tạo Project

QUY TẮC BẮT BUỘC:
- Không lặp lại gợi ý mà sale đã ghi "đã làm" hoặc "bỏ qua" — hãy đề xuất bước kế tiếp.
- Mọi câu chữ bằng tiếng Việt, xưng "em", gọi khách là "anh/chị".
- CHỈ trả JSON, không giải thích, không rào đầu.

Trả về JSON:
{
  "action": "hành động cụ thể",
  "reason": "lý do ngắn gọn",
  "priority": "urgent/high/medium/low",
  "message_template": "mẫu tin nhắn gợi ý (null nếu không cần)"
}
"""

# Số gợi ý cũ đọc lại — đủ để không lặp, không đủ để phình prompt
SO_GOI_Y_NHO_LAI = 5

_NHAN_KET_QUA = {
    "done": "sale đã làm",
    "skipped": "sale bỏ qua",
}


# ---------------------------------------------------------------------------
# Bộ luật — đường lui khi không có LLM
# ---------------------------------------------------------------------------

def _ung_vien_theo_luat(lead: Lead, activities: list[Activity], so_ngay_im_lang: int | None) -> list[dict]:
    """Toàn bộ gợi ý bộ luật nghĩ ra được, xếp theo thứ tự nên làm trước.

    Trả về cả danh sách (không phải mỗi cái đầu) để tầng gọi còn bước xuống cái
    tiếp theo khi cái đầu đã bị sale bỏ qua.
    """
    ten_khach = lead.contact_person or lead.name
    ung_vien: list[dict] = []

    if not lead.assigned_to:
        ung_vien.append({
            "code": "assign",
            "action": "Phân công lead cho một bạn Sale",
            "reason": "Lead chưa được phân công cho nhân viên nào",
            "priority": "high",
            "message_template": None,
        })

    if not lead.last_contacted_at:
        ung_vien.append({
            "code": "call",
            "action": "Gọi điện giới thiệu dịch vụ JAMA HOME",
            "reason": "Chưa liên hệ khách hàng lần nào",
            "priority": "high",
            "message_template": (
                f"Chào anh/chị {ten_khach}, em là nhân viên tư vấn JAMA HOME. "
                "Em gọi để trao đổi về nhu cầu thiết kế nội thất của anh/chị ạ."
            ),
        })
    elif so_ngay_im_lang is not None and so_ngay_im_lang > 7:
        ung_vien.append({
            "code": "recontact",
            "action": "Liên hệ lại để hâm nóng khách",
            "reason": f"Đã {so_ngay_im_lang} ngày không liên hệ, khách dễ nguội",
            "priority": "high",
            "message_template": (
                f"Anh/chị {ten_khach} ơi, JAMA HOME hỏi thăm xem kế hoạch nội thất "
                "của anh/chị tới đâu rồi ạ. Em hỗ trợ tiếp được không ạ?"
            ),
        })

    if lead.estimated_budget and lead.estimated_budget >= 1_000_000_000:
        ung_vien.append({
            "code": "escalate",
            "action": "Báo trưởng nhóm cùng chăm khách này",
            "reason": (
                f"Ngân sách cao ({lead.estimated_budget / 1_000_000:.0f} triệu), cần ưu tiên chăm sóc"
            ),
            "priority": "urgent",
            "message_template": None,
        })

    theo_giai_doan = {
        "new": {
            "code": "call",
            "action": "Gọi tư vấn ngay trong ngày",
            "reason": "Lead mới, cần gọi tư vấn ngay",
            "message_template": None,
        },
        "interested": {
            "code": "survey",
            "action": "Hẹn lịch khảo sát thực tế",
            "reason": "KH quan tâm, hẹn khảo sát hiện trạng",
            "message_template": (
                f"Anh/chị {ten_khach}, JAMA HOME xin hẹn khảo sát thực tế nhà anh/chị "
                "vào [ngày]. Thời gian khoảng 30-45 phút ạ."
            ),
        },
        "survey_scheduled": {
            "code": "meeting",
            "action": "Xác nhận lịch khảo sát và chuẩn bị hồ sơ",
            "reason": "Đã hẹn khảo sát, cần xác nhận lại để tránh bị huỷ",
            "message_template": None,
        },
        "potential": {
            "code": "proposal",
            "action": "Gửi phương án thiết kế sơ bộ + báo giá",
            "reason": "KH tiềm năng, cần push để ký hợp đồng thiết kế",
            "message_template": None,
        },
    }
    if lead.stage in theo_giai_doan:
        gd = dict(theo_giai_doan[lead.stage])
        gd["priority"] = "medium"
        ung_vien.append(gd)

    ung_vien.append({
        "code": "note",
        "action": "Cập nhật tình trạng lead",
        "reason": "Chưa có việc gấp — ghi lại tình trạng để lần sau còn nhớ",
        "priority": "low",
        "message_template": None,
    })

    # Cùng một code có thể sinh ra từ hai nhánh (ví dụ "call"): giữ cái đầu tiên
    da_co: set[str] = set()
    gon: list[dict] = []
    for uv in ung_vien:
        if uv["code"] in da_co:
            continue
        da_co.add(uv["code"])
        gon.append(uv)
    return gon


def _rule_based_suggestion(lead: Lead, activities: list[Activity]) -> dict:
    """Giữ tên cũ cho tương thích: gợi ý đầu tiên của bộ luật, không xét lịch sử."""
    return _ung_vien_theo_luat(lead, activities, _so_ngay_im_lang(lead))[0]


# ---------------------------------------------------------------------------
# Bối cảnh
# ---------------------------------------------------------------------------

def _so_ngay_im_lang(lead: Lead) -> int | None:
    if not lead.last_contacted_at:
        return None
    from datetime import datetime, timezone

    moc = lead.last_contacted_at
    if moc.tzinfo is None:
        moc = moc.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moc).days


def _tom_tat_lich_su(lich_su: list[AiRun]) -> str:
    """Các gợi ý cũ, viết thành văn để nhét vào prompt."""
    if not lich_su:
        return "Chưa từng gợi ý gì cho lead này."

    dong = []
    for ban in lich_su:
        noi_dung = ai_memory.doc_output(ban)
        ket = _NHAN_KET_QUA.get(ban.outcome or "", "sale chưa phản hồi")
        dong.append(f"- \"{noi_dung.get('action', '(trống)')}\" → {ket}")
    return "Đã gợi ý trước đó:\n" + "\n".join(dong)


def _boi_canh(lead: Lead, activities: list[Activity], tom_tat_lich_su: str) -> str:
    return (
        f"Lead: {lead.name}\n"
        f"Giai đoạn: {lead.stage}\n"
        f"Nguồn: {lead.source or 'N/A'}\n"
        f"Ngân sách: {lead.estimated_budget or 'N/A'} VND\n"
        f"Diện tích: {lead.area_sqm or 'N/A'} m²\n"
        f"Nhu cầu: {lead.needs or 'N/A'}\n"
        f"Liên hệ gần nhất: {lead.last_contacted_at or 'Chưa liên hệ'}\n"
        f"Số lần tương tác: {len(activities)}\n"
        f"Hoạt động gần nhất: {activities[0].content if activities else 'Chưa có'}\n\n"
        f"{tom_tat_lich_su}"
    )


def _chuan_hoa(data: dict) -> dict | None:
    """Nhận đầu ra LLM, trả về dict đúng khuôn hoặc None nếu không dùng được."""
    if not isinstance(data, dict):
        return None
    action = (data.get("action") or "").strip()
    if not action:
        return None
    uu_tien = str(data.get("priority") or "medium").lower()
    if uu_tien not in ("urgent", "high", "medium", "low"):
        uu_tien = "medium"
    mau = data.get("message_template")
    return {
        "code": "llm",
        "action": action,
        "reason": (data.get("reason") or "").strip() or "Co-Pilot đề xuất",
        "priority": uu_tien,
        "message_template": mau if isinstance(mau, str) and mau.strip() else None,
    }


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------

async def suggest_action(lead_id: str, user_id: str, db: AsyncSession) -> dict:
    """Gợi ý hành động tiếp theo cho lead, có đọc lại các gợi ý đã đưa.

    Trả về dict gồm ``action / reason / priority / message_template`` như cũ, cộng
    thêm ``run_id`` (để giao diện gửi lại "Đã làm"/"Bỏ qua"), ``source`` (llm hay
    rule) và ``lich_su`` (các gợi ý trước cùng phản hồi).
    """
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    activities = list(
        (
            await db.execute(
                select(Activity)
                .where(Activity.lead_id == lead_id)
                .order_by(Activity.created_at.desc())
                .limit(5)
            )
        ).scalars().all()
    )

    lich_su = await ai_memory.nho_lai(
        db,
        agent=AGENT_SALES_COPILOT,
        scope_type=SCOPE_LEAD,
        scope_id=str(lead.id),
        limit=SO_GOI_Y_NHO_LAI,
    )
    tom_tat = _tom_tat_lich_su(lich_su)
    boi_canh = _boi_canh(lead, activities, tom_tat)

    # Băm gồm cả lịch sử: sale bấm "Đã làm" là băm đổi ⇒ gợi ý mới, không trả bản cũ.
    input_hash = ai_memory.bam_dau_vao(boi_canh)

    goi_y: dict | None = None
    nguon = SOURCE_RULE
    model_used: str | None = None

    if await llm_available():
        ban_cu = await ai_memory.tim_ban_cu(db, AGENT_SALES_COPILOT, input_hash)
        if ban_cu is not None:
            cu = ai_memory.doc_output(ban_cu)
            if cu.get("action"):
                logger.info("Co-Pilot dùng lại gợi ý %s cho lead %s", ban_cu.id, lead_id)
                return _tra_ve(ban_cu, cu, lich_su)

        try:
            response = await llm_complete(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": boi_canh},
                ],
                temperature=0.3,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            goi_y = _chuan_hoa(json.loads(response.choices[0].message.content))
            if goi_y is not None:
                nguon = SOURCE_LLM
                model_used = ai_memory.ten_model(response)
        except Exception as e:
            logger.warning("Co-Pilot LLM lỗi cho lead %s: %s — chuyển sang bộ luật", lead_id, e)

    if goi_y is None:
        goi_y = _chon_theo_luat(lead, activities, lich_su)

    ban = await ai_memory.ghi_lai(
        db,
        agent=AGENT_SALES_COPILOT,
        scope_type=SCOPE_LEAD,
        scope_id=str(lead.id),
        input_hash=input_hash,
        output=goi_y,
        source=nguon,
        model_used=model_used,
    )
    return _tra_ve(ban, goi_y, lich_su)


def _chon_theo_luat(lead: Lead, activities: list[Activity], lich_su: list[AiRun]) -> dict:
    """Gợi ý bộ luật đầu tiên mà sale CHƯA phản hồi. Hết thì lấy cái cuối."""
    da_phan_hoi = {
        ai_memory.doc_output(ban).get("code")
        for ban in lich_su
        if ban.outcome
    }
    ung_vien = _ung_vien_theo_luat(lead, activities, _so_ngay_im_lang(lead))
    for uv in ung_vien:
        if uv["code"] not in da_phan_hoi:
            return uv
    # Mọi việc trong sổ đều đã làm hoặc đã bỏ qua — không bịa thêm, nhắc cập nhật
    return ung_vien[-1]


def _tra_ve(ban: AiRun | None, goi_y: dict, lich_su: list[AiRun]) -> dict:
    return {
        **goi_y,
        "run_id": ban.id if ban is not None else None,
        "source": ban.source if ban is not None else SOURCE_RULE,
        "lich_su": [tom_luoc_ban_ghi(b) for b in lich_su],
    }


def tom_luoc_ban_ghi(ban: AiRun) -> dict:
    """Một dòng lịch sử cho giao diện."""
    noi_dung = ai_memory.doc_output(ban)
    return {
        "run_id": ban.id,
        "action": noi_dung.get("action"),
        "reason": noi_dung.get("reason"),
        "priority": noi_dung.get("priority"),
        "source": ban.source,
        "outcome": ban.outcome,
        "outcome_note": ban.outcome_note,
        "outcome_at": ban.outcome_at.isoformat() if ban.outcome_at else None,
        "created_at": ban.created_at.isoformat() if ban.created_at else None,
    }
