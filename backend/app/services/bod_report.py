"""BOD Report — báo cáo tự động cho ban lãnh đạo qua Telegram + in-app.

Theo Brief JAMA HOME: "Báo cáo gửi tự động cho BOD hàng ngày/tuần/tháng".
Gửi cho users role admin/executive (có telegram_user_id thì push Telegram).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.project import Project
from app.models.payroll import Transaction
from app.models.user import User
from app.models.notification import Notification
from app.agents.insight_agent import format_vnd, generate_insights
from app.services.telegram_notify import send_telegram

logger = logging.getLogger(__name__)

PERIOD_LABELS = {"daily": "ngày", "weekly": "tuần", "monthly": "tháng"}
PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}

BOD_ROLES = ("admin", "executive")


async def build_bod_report(db: AsyncSession, period: str = "daily") -> dict:
    """Gather metrics and build a Vietnamese report text for the given period."""
    days = PERIOD_DAYS.get(period, 1)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    # --- Leads ---
    new_leads = (await db.execute(
        select(func.count(Lead.id)).where(Lead.created_at >= start)
    )).scalar() or 0
    new_leads_prev = (await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.created_at >= prev_start, Lead.created_at < start)
        )
    )).scalar() or 0
    signed = (await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.stage == "signed_design", Lead.updated_at >= start)
        )
    )).scalar() or 0
    lost = (await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.stage == "lost", Lead.updated_at >= start)
        )
    )).scalar() or 0
    pipeline_value = (await db.execute(
        select(func.coalesce(func.sum(Lead.estimated_budget), 0)).where(
            Lead.stage.notin_(["lost", "dormant", "signed_design"])
        )
    )).scalar() or 0

    # --- Revenue / Expense (completed transactions in period) ---
    revenue = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.type == "income",
                Transaction.status == "completed",
                Transaction.date >= start,
            )
        )
    )).scalar() or 0
    expense = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.type == "expense",
                Transaction.status == "completed",
                Transaction.date >= start,
            )
        )
    )).scalar() or 0

    # --- Projects ---
    active_projects = (await db.execute(
        select(func.count(Project.id)).where(Project.status.notin_(["completed", "cancelled"]))
    )).scalar() or 0

    # --- Sales performance (leads signed per user in period) ---
    top_sales_rows = (await db.execute(
        select(User.full_name, func.count(Lead.id).label("cnt"))
        .join(Lead, Lead.assigned_to == User.id)
        .where(and_(Lead.stage == "signed_design", Lead.updated_at >= start))
        .group_by(User.id)
        .order_by(func.count(Lead.id).desc())
        .limit(3)
    )).all()

    trend = "📈" if new_leads >= new_leads_prev else "📉"
    label = PERIOD_LABELS.get(period, "ngày")
    date_str = now.strftime("%d/%m/%Y")

    lines = [
        f"📊 <b>BÁO CÁO {label.upper()} — {date_str}</b>",
        "",
        f"🎯 <b>Kinh doanh</b>",
        f"{trend} Lead mới: <b>{new_leads}</b> (kỳ trước: {new_leads_prev})",
        f"✅ Ký thiết kế: <b>{signed}</b>  |  ❌ Mất lead: {lost}",
        f"💼 Giá trị pipeline: <b>{format_vnd(pipeline_value)}</b>",
        "",
        f"💰 <b>Tài chính ({label})</b>",
        f"↗️ Thu: <b>{format_vnd(revenue)}</b>",
        f"↘️ Chi: <b>{format_vnd(expense)}</b>",
        f"💵 Chênh lệch: <b>{format_vnd(revenue - expense)}</b>",
        "",
        f"🏗️ Dự án đang chạy: <b>{active_projects}</b>",
    ]

    if top_sales_rows:
        lines += ["", "🏆 <b>Top sales (ký TK)</b>"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, cnt) in enumerate(top_sales_rows):
            lines.append(f"{medals[i]} {name}: {cnt} hợp đồng")

    # Weekly/monthly: enrich with AI insight summary
    if period in ("weekly", "monthly"):
        try:
            insights = await generate_insights(db, period_days=days)
            summary = insights.get("summary", "")
            if summary:
                lines += ["", f"🤖 <b>AI Insight</b>", summary]
            alerts = insights.get("alerts") or []
            if alerts:
                lines += [""] + [f"⚠️ {a}" for a in alerts[:3]]
        except Exception:
            logger.warning("Insight enrichment failed for BOD report", exc_info=True)

    text = "\n".join(lines)
    return {
        "period": period,
        "text": text,
        "metrics": {
            "new_leads": new_leads,
            "signed": signed,
            "lost": lost,
            "pipeline_value": pipeline_value,
            "revenue": revenue,
            "expense": expense,
            "active_projects": active_projects,
        },
    }


async def send_bod_report(db: AsyncSession, period: str = "daily") -> dict:
    """Build report and deliver to all BOD users (in-app + Telegram)."""
    report = await build_bod_report(db, period)

    result = await db.execute(
        select(User).where(
            User.role.in_(BOD_ROLES),
            User.is_active == True,  # noqa: E712
        )
    )
    bod_users = result.scalars().all()

    label = PERIOD_LABELS.get(period, "ngày")
    sent_inapp = 0
    sent_telegram = 0
    for user in bod_users:
        db.add(
            Notification(
                user_id=user.id,
                type="bod_report",
                title=f"📊 Báo cáo {label} {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
                body=report["text"].replace("<b>", "").replace("</b>", ""),
                link="/reports",
            )
        )
        sent_inapp += 1
        if user.telegram_user_id:
            ok = await send_telegram(user.telegram_user_id, report["text"])
            if ok:
                sent_telegram += 1

    await db.commit()
    logger.info(
        "BOD %s report delivered: %d in-app, %d telegram", period, sent_inapp, sent_telegram
    )
    return {
        "status": "completed",
        "period": period,
        "recipients": sent_inapp,
        "telegram_sent": sent_telegram,
    }


# ---------------------------------------------------------------------------
# Group briefing — gửi vào nhóm Telegram công ty (KHÔNG kèm số liệu tài chính)
# ---------------------------------------------------------------------------

async def build_group_briefing(db: AsyncSession) -> str:
    """Daily team briefing for the company group: leads, projects, tasks.

    Deliberately excludes revenue/expense/P&L — the group includes all staff.
    """
    from app.models.project import Task

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)

    new_leads = (await db.execute(
        select(func.count(Lead.id)).where(Lead.created_at >= start)
    )).scalar() or 0
    signed = (await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.stage == "signed_design", Lead.updated_at >= start)
        )
    )).scalar() or 0
    active_projects = (await db.execute(
        select(func.count(Project.id)).where(Project.status.notin_(["completed", "cancelled"]))
    )).scalar() or 0
    open_tasks = (await db.execute(
        select(func.count(Task.id)).where(Task.status.notin_(["done", "cancelled"]))
    )).scalar() or 0
    overdue_leads = (await db.execute(
        select(func.count(Lead.id)).where(
            Lead.stage.in_(("new", "interested", "survey_scheduled", "potential")),
            Lead.last_contacted_at < now - timedelta(days=3),
        )
    )).scalar() or 0

    date_str = now.strftime("%d/%m/%Y")
    lines = [
        f"🌅 <b>BRIEFING NGÀY {date_str} — JAMA HOME</b>",
        "",
        f"📥 Lead mới hôm qua: <b>{new_leads}</b>",
        f"✍️ Ký thiết kế: <b>{signed}</b>",
        f"🏗️ Dự án đang chạy: <b>{active_projects}</b>",
        f"📋 Công việc đang mở: <b>{open_tasks}</b>",
    ]
    if overdue_leads:
        lines.append(f"⚠️ Lead quá hạn chăm sóc (3+ ngày): <b>{overdue_leads}</b> — sales lưu ý!")
    lines += [
        "",
        "💡 Lệnh bot: /duan [Mã] · /baocao · /vatlieu · /suco · /checkin · /pipeline",
        "Chúc cả team một ngày làm việc hiệu quả! 💪",
    ]
    return "\n".join(lines)


async def send_group_briefing(db: AsyncSession) -> dict:
    """Send daily briefing to the configured company Telegram group."""
    from app.services.automation import get_automation_settings

    settings_map = await get_automation_settings(db)
    if settings_map.get("group_briefing_enabled", "true") != "true":
        return {"status": "skipped", "reason": "disabled"}

    chat_id_str = settings_map.get("telegram_group_chat_id", "").strip()
    if not chat_id_str or not chat_id_str.lstrip("-").isdigit():
        return {"status": "skipped", "reason": "no group chat id configured"}

    text = await build_group_briefing(db)
    ok = await send_telegram(int(chat_id_str), text)
    logger.info("Group briefing sent to %s: %s", chat_id_str, ok)
    return {"status": "completed" if ok else "failed", "chat_id": chat_id_str}
