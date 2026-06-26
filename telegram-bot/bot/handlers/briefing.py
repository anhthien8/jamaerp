"""/briefing handler — daily personal briefing."""

from aiogram import Router, types
from aiogram.filters import Command

from bot.api_client import api

router = Router()


@router.message(Command("briefing"))
async def cmd_briefing(message: types.Message):
    """Send personal daily briefing."""
    data = await api.get_personal_dashboard(message.from_user.id)

    if not data:
        await message.answer("❌ Không thể tải briefing. Hãy /start để đăng nhập lại.")
        return

    lines = [
        f"☀️ <b>Briefing — {data.get('user_name', 'N/A')}</b>\n",
        f"📊 <b>Tổng lead đang xử lý:</b> {data.get('total_active_leads', 0)}",
    ]

    # By stage breakdown
    by_stage = data.get("by_stage", {})
    if by_stage:
        lines.append("\n<b>Theo giai đoạn:</b>")
        stage_labels = {
            "new": "🆕 Mới",
            "interested": "💡 Có nhu cầu",
            "survey_scheduled": "📅 Hẹn khảo sát",
            "potential": "⭐ Tiềm năng",
        }
        for key, label in stage_labels.items():
            count = by_stage.get(key, 0)
            if count:
                lines.append(f"  {label}: {count}")

    # Pipeline value
    lines.append(f"\n💰 <b>Giá trị pipeline:</b> {_format_value(data.get('pipeline_value', 0))}")

    # Overdue follow-ups
    overdue = data.get("overdue_followup", [])
    if overdue:
        lines.append(f"\n🚨 <b>Cần liên hệ ngay ({len(overdue)}):</b>")
        for lead in overdue[:5]:
            lines.append(f"  ⚠️ {lead.get('name', '—')} — {lead.get('last_contact', 'Chưa LH')}")

    # AI suggestions
    suggestions = data.get("ai_suggestions", [])
    if suggestions:
        lines.append("\n🤖 <b>Gợi ý AI:</b>")
        for s in suggestions[:3]:
            lines.append(f"  💡 {s.get('action', '')}")

    lines.append(f"\n🔗 /pipeline để xem chi tiết")

    await message.answer("\n".join(lines))


@router.message(Command("suggest"))
async def cmd_suggest(message: types.Message):
    """Get AI suggestion — placeholder until lead selection UI."""
    await message.answer(
        "🤖 <b>AI Gợi ý</b>\n\n"
        "Sử dụng lệnh:\n"
        "<code>/suggest [ID lead]</code>\n\n"
        "Ví dụ: <code>/suggest abc12345</code>\n\n"
        "Bot sẽ phân tích và đề xuất hành động tiếp theo."
    )


def _format_value(value) -> str:
    if not value:
        return "0 ₫"
    v = float(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f} tỷ ₫"
    elif v >= 1_000_000:
        return f"{v / 1_000_000:.0f}tr ₫"
    return f"{v:,.0f} ₫"
