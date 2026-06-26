"""/pipeline handler — view pipeline kanban + stats in Telegram."""

from aiogram import Router, types
from aiogram.filters import Command

from bot.api_client import api

router = Router()

STAGE_EMOJIS = {
    "new": "🆕",
    "interested": "💡",
    "survey_scheduled": "📅",
    "potential": "⭐",
    "signed_design": "✍️",
    "lost": "❌",
    "dormant": "😴",
}

STAGE_LABELS = {
    "new": "Mới tiếp nhận",
    "interested": "Có nhu cầu",
    "survey_scheduled": "Đã hẹn khảo sát",
    "potential": "KH tiềm năng",
    "signed_design": "Ký thiết kế",
    "lost": "Mất",
    "dormant": "Ngủ đông",
}


@router.message(Command("pipeline"))
async def cmd_pipeline(message: types.Message):
    """Show pipeline overview."""
    stats = await api.get_pipeline_stats(message.from_user.id)

    if not stats:
        await message.answer("❌ Không thể tải pipeline. Hãy /start để đăng nhập lại.")
        return

    by_stage = stats.get("by_stage", {})
    total = stats.get("total_leads", 0)

    # Build visual pipeline
    lines = ["📊 <b>PIPELINE CRM</b>\n"]

    for stage_key in ["new", "interested", "survey_scheduled", "potential", "signed_design"]:
        count = by_stage.get(stage_key, 0)
        emoji = STAGE_EMOJIS.get(stage_key, "•")
        label = STAGE_LABELS.get(stage_key, stage_key)
        bar = "█" * min(count, 20)
        lines.append(f"{emoji} <b>{label}</b>: {count}\n{bar}")

    # Add stats
    lines.append(f"\n📈 <b>Tổng quan:</b>")
    lines.append(f"• Tổng leads: {total}")
    lines.append(f"• Tỷ lệ chuyển đổi: {stats.get('conversion_rate', 0):.1f}%")
    lines.append(f"• Giá trị pipeline: {_format_value(stats.get('pipeline_value', 0))}")
    lines.append(f"• Chưa phân công: {stats.get('unassigned_count', 0)}")

    lost = by_stage.get("lost", 0)
    dormant = by_stage.get("dormant", 0)
    if lost or dormant:
        lines.append(f"\n⚠️ Mất: {lost} | Ngủ đông: {dormant}")

    await message.answer("\n".join(lines))


def _format_value(value) -> str:
    if not value:
        return "0 ₫"
    v = float(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f} tỷ ₫"
    elif v >= 1_000_000:
        return f"{v / 1_000_000:.0f}tr ₫"
    return f"{v:,.0f} ₫"
