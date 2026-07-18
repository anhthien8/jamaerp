"""CSKH Automation — follow-up reminders, lead recall, payment reminders.

Theo Brief JAMA HOME:
- Nhắc cập nhật thông tin chăm sóc KH mỗi 3-5 ngày
- Quá hạn CSKH → thu hồi lead & giao cho sale khác
- Nhắc hẹn thanh toán hóa đơn (đợt thanh toán pending)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, Activity
from app.models.contract import Contract
from app.models.project import Project
from app.models.user import User
from app.models.notification import Notification, SystemSetting, DEFAULT_AUTOMATION_SETTINGS
from app.services.telegram_notify import send_telegram

logger = logging.getLogger(__name__)

# Stages đang chăm sóc — cần nhắc follow-up
ACTIVE_LEAD_STAGES = ("new", "interested", "survey_scheduled", "potential")


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

async def get_automation_settings(db: AsyncSession) -> dict[str, str]:
    """Load settings from DB, falling back to defaults for missing keys."""
    result = await db.execute(select(SystemSetting))
    stored = {s.key: s.value for s in result.scalars().all()}
    return {**DEFAULT_AUTOMATION_SETTINGS, **stored}


async def set_automation_setting(db: AsyncSession, key: str, value: str) -> None:
    setting = await db.get(SystemSetting, key)
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    await db.flush()


def _int_setting(settings: dict[str, str], key: str, default: int) -> int:
    try:
        return max(1, int(settings.get(key, default)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Notification helper (with dedupe on unread same type+ref)
# ---------------------------------------------------------------------------

async def _notify(
    db: AsyncSession,
    user: User | None,
    type_: str,
    title: str,
    body: str,
    link: str | None = None,
    ref_id: str | None = None,
    telegram: bool = True,
) -> bool:
    """Create in-app notification (dedupe unread) + optional Telegram push."""
    if user is None:
        return False

    # Dedupe: skip if an unread notification of same type+ref exists
    if ref_id:
        existing = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.type == type_,
                Notification.ref_id == ref_id,
                Notification.read == False,  # noqa: E712
            )
        )
        if (existing.scalar() or 0) > 0:
            return False

    db.add(
        Notification(
            user_id=user.id, type=type_, title=title, body=body, link=link, ref_id=ref_id
        )
    )
    await db.flush()

    if telegram and user.telegram_user_id:
        await send_telegram(user.telegram_user_id, f"<b>{title}</b>\n{body}")
    return True


def _last_touch(lead: Lead) -> datetime:
    """Latest contact timestamp for a lead (fallback: created_at)."""
    dt = lead.last_contacted_at or lead.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# 1. Follow-up reminders — nhắc CSKH mỗi 3-5 ngày
# ---------------------------------------------------------------------------

async def run_followup_reminders(db: AsyncSession) -> dict:
    """Notify assigned sales about leads not contacted for N days."""
    settings = await get_automation_settings(db)
    days = _int_setting(settings, "followup_reminder_days", 3)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Lead).where(
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
            Lead.assigned_to.is_not(None),
        )
    )
    leads = result.scalars().all()

    reminded = 0
    for lead in leads:
        if _last_touch(lead) > cutoff:
            continue
        user = await db.get(User, lead.assigned_to)
        overdue_days = (datetime.now(timezone.utc) - _last_touch(lead)).days
        sent = await _notify(
            db,
            user,
            "followup_reminder",
            f"⏰ Nhắc chăm sóc KH: {lead.name}",
            f"Lead \"{lead.name}\" ({lead.phone}) đã {overdue_days} ngày chưa được liên hệ. "
            f"Vui lòng cập nhật tình trạng chăm sóc.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
        )
        if sent:
            reminded += 1

    logger.info("Follow-up reminders: %d leads reminded (threshold=%dd)", reminded, days)
    return {"status": "completed", "reminded": reminded, "threshold_days": days}


# ---------------------------------------------------------------------------
# 2. Lead recall — thu hồi lead quá hạn & giao sale khác
# ---------------------------------------------------------------------------

async def _pick_new_sales(db: AsyncSession, lead: Lead) -> User | None:
    """Least-loaded active SALES user (same team preferred), excluding current."""
    candidates_q = select(User).where(
        User.department == "SALES",
        User.is_active == True,  # noqa: E712
        User.id != lead.assigned_to,
    )
    result = await db.execute(candidates_q)
    candidates = result.scalars().all()
    if not candidates:
        return None

    # Prefer same team
    same_team = [u for u in candidates if lead.team_id and u.team_id == lead.team_id]
    pool = same_team or candidates

    # Least-loaded: count active leads per candidate
    counts: dict[str, int] = {}
    for user in pool:
        c = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.assigned_to == user.id,
                Lead.stage.in_(ACTIVE_LEAD_STAGES),
            )
        )
        counts[user.id] = c.scalar() or 0

    return min(pool, key=lambda u: counts[u.id])


async def run_lead_recall(db: AsyncSession) -> dict:
    """Recall leads not contacted for N days and reassign to another sales."""
    settings = await get_automation_settings(db)
    if settings.get("lead_recall_enabled", "true") != "true":
        return {"status": "skipped", "reason": "disabled"}

    days = _int_setting(settings, "lead_recall_days", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Lead).where(
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
            Lead.assigned_to.is_not(None),
        )
    )
    leads = result.scalars().all()

    recalled = 0
    for lead in leads:
        if _last_touch(lead) > cutoff:
            continue

        old_user = await db.get(User, lead.assigned_to)
        new_user = await _pick_new_sales(db, lead)
        if new_user is None:
            continue  # no one to reassign to

        lead.assigned_to = new_user.id
        if new_user.team_id:
            lead.team_id = new_user.team_id
        # Reset clock so the new sales gets a fresh follow-up window
        lead.last_contacted_at = datetime.now(timezone.utc)

        db.add(
            Activity(
                lead_id=lead.id,
                user_id=new_user.id,
                type="assignment",
                content=(
                    f"🔄 Tự động thu hồi: lead quá hạn chăm sóc {days} ngày. "
                    f"Chuyển từ {old_user.full_name if old_user else 'N/A'} → {new_user.full_name}."
                ),
            )
        )

        await _notify(
            db,
            old_user,
            "lead_recalled",
            f"⚠️ Lead bị thu hồi: {lead.name}",
            f"Lead \"{lead.name}\" quá hạn chăm sóc {days} ngày, đã chuyển cho {new_user.full_name}.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
        )
        await _notify(
            db,
            new_user,
            "lead_assigned",
            f"📥 Lead mới được giao: {lead.name}",
            f"Bạn được giao lead \"{lead.name}\" ({lead.phone}). Vui lòng liên hệ sớm.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
        )
        recalled += 1

    logger.info("Lead recall: %d leads reassigned (threshold=%dd)", recalled, days)
    return {"status": "completed", "recalled": recalled, "threshold_days": days}


# ---------------------------------------------------------------------------
# 3. Payment reminders — nhắc hẹn thanh toán các đợt pending
# ---------------------------------------------------------------------------

async def run_payment_reminders(db: AsyncSession) -> dict:
    """Remind accountants about pending installments on signed contracts."""
    settings = await get_automation_settings(db)
    days = _int_setting(settings, "payment_reminder_days", 3)
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(Contract).where(
            Contract.status.in_(("signed", "active", "in_progress")),
            Contract.signed_date.is_not(None),
        )
    )
    contracts = result.scalars().all()

    # Accountants to notify
    acct_result = await db.execute(
        select(User).where(
            User.role.in_(("accountant", "admin")),
            User.is_active == True,  # noqa: E712
        )
    )
    accountants = acct_result.scalars().all()

    reminded = 0
    for contract in contracts:
        terms = contract.payment_terms or {}
        installments = terms.get("installments", [])
        pending = [i for i in installments if i.get("status") == "pending"]
        if not pending:
            continue
        if (today - contract.signed_date).days < days:
            continue

        total = contract.total_value or 0
        lines = [
            f"• {i.get('name', 'Đợt ?')} — {i.get('percentage', 0)}% "
            f"(~{total * i.get('percentage', 0) / 100:,.0f}đ)"
            for i in pending
        ]
        body = (
            f"Hợp đồng {contract.code} ({contract.title}) còn {len(pending)} đợt chưa thanh toán:\n"
            + "\n".join(lines)
        )

        for acct in accountants:
            sent = await _notify(
                db,
                acct,
                "payment_reminder",
                f"💰 Nhắc thanh toán: HĐ {contract.code}",
                body,
                link=f"/contracts?id={contract.id}",
                ref_id=contract.id,
            )
            if sent:
                reminded += 1

    logger.info("Payment reminders: %d notifications sent", reminded)
    return {"status": "completed", "reminded": reminded, "threshold_days": days}


# ---------------------------------------------------------------------------
# Run-all entry point (used by worker + manual trigger API)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4. Warranty reminders — nhắc trước khi hết bảo hành (30 & 7 ngày)
# ---------------------------------------------------------------------------

async def run_warranty_reminders(db: AsyncSession) -> dict:
    """Nhắc sales/PM chăm sóc khách trước khi hết hạn bảo hành.

    warranty_end = handover_date + warranty_months. Nhắc ở mốc còn 30 ngày và
    7 ngày (dedupe qua _notify unread cùng type+ref). Cơ hội bán gói bảo trì.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Project).where(
            Project.handover_date.isnot(None),
            Project.status.in_(["active", "completed"]),
        )
    )
    projects = result.scalars().all()

    notified = 0
    for p in projects:
        handover = p.handover_date
        if handover.tzinfo is None:
            handover = handover.replace(tzinfo=timezone.utc)
        warranty_end = handover + timedelta(days=30 * (p.warranty_months or 12))
        days_left = (warranty_end - now).days
        if days_left < 0 or days_left > 30:
            continue
        milestone = "7d" if days_left <= 7 else "30d"
        title = f"🛡️ Dự án {p.code} còn {days_left} ngày bảo hành"
        body = (
            f"{p.name} — khách {p.client_name}. Hết bảo hành {warranty_end.strftime('%d/%m/%Y')}. "
            f"Nên gọi hỏi thăm + đề xuất gói bảo trì định kỳ."
        )
        for uid in {p.sales_id, p.pm_id}:
            if not uid:
                continue
            u = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
            if await _notify(
                db, u, "warranty_reminder", title, body,
                link=f"/projects?id={p.id}", ref_id=f"{p.id}:{milestone}",
            ):
                notified += 1

    return {"checked": len(projects), "notified": notified}


async def run_all_automation(db: AsyncSession) -> dict:
    followups = await run_followup_reminders(db)
    recalls = await run_lead_recall(db)
    payments = await run_payment_reminders(db)
    warranties = await run_warranty_reminders(db)
    await db.commit()
    return {"followups": followups, "recalls": recalls, "payments": payments, "warranties": warranties}
