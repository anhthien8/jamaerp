"""CSKH Automation — follow-up reminders, lead recall, payment reminders.

Theo Brief JAMA HOME:
- Nhắc cập nhật thông tin chăm sóc KH mỗi 3-5 ngày
- Quá hạn CSKH → thu hồi lead & giao cho sale khác
- Nhắc hẹn thanh toán hóa đơn (đợt thanh toán pending)
"""

import html
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import ACTIVE_LEAD_STAGES, Lead, Activity
from app.models.contract import Contract
from app.models.project import Project
from app.models.user import User
from app.models.notification import Notification, SystemSetting, DEFAULT_AUTOMATION_SETTINGS
from app.services.telegram_notify import ban_phim, nut_lead, send_telegram

logger = logging.getLogger(__name__)

# Stages đang chăm sóc — cần nhắc follow-up


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
# Notification helper (chống trùng theo khung giờ cùng loại + ref)
# ---------------------------------------------------------------------------

# Job hằng ngày chạy ~07:00; redeploy trong ngày chạy lại job → 20 giờ đủ chặn tin trùng
# trong ngày mà sáng hôm sau vẫn nhắc tiếp.
NHAC_LAI_SAU_GIO = 20.0


async def _notify(
    db: AsyncSession,
    user: User | None,
    type_: str,
    title: str,
    body: str,
    link: str | None = None,
    ref_id: str | None = None,
    telegram: bool = True,
    nut: list[list[dict]] | None = None,
    nhac_lai_sau_gio: float = NHAC_LAI_SAU_GIO,
) -> bool:
    """Thông báo trong app + đẩy Telegram (kèm nút).

    Chống trùng (R00, 14/11/2026): cùng người + loại + ref đã gửi trong `nhac_lai_sau_gio`
    giờ thì bỏ qua — KHÔNG còn xét «đã đọc chưa». Trước đây người không mở app chỉ được
    nhắc đúng một lần, người chăm đọc lại bị nhắc mỗi sáng; giờ ai cũng theo một nhịp.
    Tin Telegram có các hàng nút `nut` + nút «Mở ERP» trỏ thẳng `link`.
    """
    if user is None:
        return False

    # Cột title là String(255): Postgres báo lỗi khi dài hơn (SQLite thì không),
    # kéo cả thao tác giao việc đổ theo. Cắt cho vừa.
    if len(title) > 255:
        title = title[:254] + "…"

    if ref_id:
        moc = datetime.now(timezone.utc) - timedelta(hours=nhac_lai_sau_gio)
        existing = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.type == type_,
                Notification.ref_id == ref_id,
                Notification.created_at >= moc,
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
        # Tiêu đề/nội dung là chữ thường (cũng hiện trong app) — thoát HTML khi đẩy Telegram,
        # kẻo tên khách có «&» hay «<» làm Telegram từ chối cả tin.
        await send_telegram(
            user.telegram_user_id,
            f"<b>{html.escape(title, quote=False)}</b>\n{html.escape(body, quote=False)}",
            reply_markup=ban_phim(nut, link),
        )
    return True


def _last_touch(lead: Lead) -> datetime:
    """Latest contact timestamp for a lead (fallback: created_at)."""
    dt = lead.last_contacted_at or lead.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


VN = timezone(timedelta(hours=7))


def gio_vn_naive(now: datetime | None = None) -> datetime:
    """Giờ VN dạng naive — cùng hệ với cột `survey_date` / `hen_tiep_luc`."""
    return (now or datetime.now(timezone.utc)).astimezone(VN).replace(tzinfo=None)


def co_hen_toi(lead: Lead, now_vn: datetime | None = None) -> bool:
    """Lead còn hẹn tiếp / ngày khảo sát ở tương lai = đang được chăm (luật R00 số 3)."""
    now_vn = now_vn or gio_vn_naive()
    return any(m is not None and m > now_vn for m in (lead.hen_tiep_luc, lead.survey_date))


def _moc_cham(lead: Lead, giao_luc: datetime | None, now_vn: datetime) -> datetime:
    """Mốc «được chăm» gần nhất (UTC có múi): liên hệ thật, lúc được giao lead,
    buổi hẹn / khảo sát vừa qua. Lúc giao là để người mới nhận có đủ hạn chăm
    — thay cho lối cũ ghi đè `last_contacted_at` (mốc đó chỉ dành cho liên hệ thật)."""
    moc = [_last_touch(lead)]
    if giao_luc is not None:
        moc.append(giao_luc if giao_luc.tzinfo else giao_luc.replace(tzinfo=timezone.utc))
    for h in (lead.hen_tiep_luc, lead.survey_date):
        if h is not None and h <= now_vn:
            moc.append(h.replace(tzinfo=VN).astimezone(timezone.utc))
    return max(moc)


async def _lan_giao_cuoi(db: AsyncSession) -> dict[str, datetime]:
    """{lead_id: lúc được giao gần nhất} cho lead đang chăm — từ Activity «assignment»
    (giao tay, giao hàng loạt, tự thu hồi đều ghi)."""
    dang_cham = select(Lead.id).where(
        Lead.stage.in_(ACTIVE_LEAD_STAGES), Lead.assigned_to.is_not(None),
    )
    rows = await db.execute(
        select(Activity.lead_id, func.max(Activity.created_at))
        .where(Activity.type == "assignment", Activity.lead_id.in_(dang_cham))
        .group_by(Activity.lead_id)
    )
    return {lead_id: luc for lead_id, luc in rows.all() if luc is not None}


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
    now_vn = gio_vn_naive()
    giao = await _lan_giao_cuoi(db)

    reminded = 0
    for lead in leads:
        if co_hen_toi(lead, now_vn):
            continue  # có hẹn tương lai = đang chăm, không nhắc
        moc = _moc_cham(lead, giao.get(lead.id), now_vn)
        if moc > cutoff:
            continue
        user = await db.get(User, lead.assigned_to)
        overdue_days = (datetime.now(timezone.utc) - moc).days
        sent = await _notify(
            db,
            user,
            "followup_reminder",
            f"Nhắc chăm sóc KH: {lead.name}",
            f"Lead \"{lead.name}\" — SĐT {lead.phone} — đã {overdue_days} ngày chưa được liên hệ. "
            f"Liên hệ xong bấm nút bên dưới để ghi, khỏi mở web.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
            nut=nut_lead(lead.id),
        )
        if sent:
            reminded += 1

    logger.info("Follow-up reminders: %d leads reminded (threshold=%dd)", reminded, days)
    return {"status": "completed", "reminded": reminded, "threshold_days": days}


# ---------------------------------------------------------------------------
# 2. Lead recall — thu hồi lead quá hạn & giao sale khác
# ---------------------------------------------------------------------------

async def _pick_new_sales(db: AsyncSession, lead: Lead) -> User | None:
    """Pick best sales user: weighted by conversion rate (70%) + least load (30%), same team preferred."""
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

    # Count active leads per candidate (for load scoring)
    load_counts: dict[str, int] = {}
    for user in pool:
        c = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.assigned_to == user.id,
                Lead.stage.in_(ACTIVE_LEAD_STAGES),
            )
        )
        load_counts[user.id] = c.scalar() or 0

    # Calculate conversion rate per candidate
    conv_rates: dict[str, float] = {}
    for user in pool:
        total_q = await db.execute(
            select(func.count(Lead.id)).where(Lead.assigned_to == user.id)
        )
        total = total_q.scalar() or 0
        if total == 0:
            conv_rates[user.id] = 0.5  # Default for new users
            continue
        signed_q = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.assigned_to == user.id,
                Lead.stage == "signed_design",
            )
        )
        signed = signed_q.scalar() or 0
        conv_rates[user.id] = signed / total

    # Weighted score: conversion_rate (70%) + least_load (30%)
    max_load = max(load_counts.values()) if load_counts else 1
    scored = []
    for user in pool:
        cr = conv_rates.get(user.id, 0)
        load_score = 1 - (load_counts.get(user.id, 0) / max(max_load, 1))
        score = cr * 0.7 + load_score * 0.3
        scored.append((user, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


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
    now_vn = gio_vn_naive()
    giao = await _lan_giao_cuoi(db)

    recalled = 0
    for lead in leads:
        if co_hen_toi(lead, now_vn):
            continue  # có hẹn tương lai = đang chăm, không thu hồi
        if _moc_cham(lead, giao.get(lead.id), now_vn) > cutoff:
            continue

        old_user = await db.get(User, lead.assigned_to)
        new_user = await _pick_new_sales(db, lead)
        if new_user is None:
            continue  # no one to reassign to

        lead.assigned_to = new_user.id
        if new_user.team_id:
            lead.team_id = new_user.team_id
        # KHÔNG ghi đè last_contacted_at (14/11/2026): mốc đó chỉ dành cho liên hệ
        # thật. Người mới vẫn có đủ hạn chăm nhờ Activity «assignment» dưới đây
        # (_lan_giao_cuoi tính lúc giao là một mốc chăm).

        db.add(
            Activity(
                lead_id=lead.id,
                user_id=new_user.id,
                type="assignment",
                content=(
                    f"Tự động thu hồi: lead quá hạn chăm sóc {days} ngày. "
                    f"Chuyển từ {old_user.full_name if old_user else 'N/A'} → {new_user.full_name}."
                ),
            )
        )

        await _notify(
            db,
            old_user,
            "lead_recalled",
            f"Lead bị thu hồi: {lead.name}",
            f"Lead \"{lead.name}\" quá hạn chăm sóc {days} ngày, đã chuyển cho {new_user.full_name}.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
        )
        await _notify(
            db,
            new_user,
            "lead_assigned",
            f"Lead mới được giao: {lead.name}",
            f"Bạn được giao lead \"{lead.name}\" — SĐT {lead.phone}. Liên hệ xong bấm nút bên dưới để ghi.",
            link=f"/leads?id={lead.id}",
            ref_id=lead.id,
            nut=nut_lead(lead.id),  # người cũ (lead_recalled) không còn giữ lead → không nút
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
        pending = [i for i in installments if i.get("status") in ("pending", "partial")]
        if not pending:
            continue
        # Có hạn thu (27/10/2026): chỉ nhắc đợt sắp tới hạn trong `days` ngày hoặc quá hạn
        co_han = [i for i in pending if i.get("due_date")]
        if co_han:
            def _han(i):
                try:
                    return date.fromisoformat(str(i["due_date"])[:10])
                except ValueError:
                    return None
            pending = [i for i in co_han if _han(i) and (_han(i) - today).days <= days]
            if not pending:
                continue
        elif (today - contract.signed_date).days < days:
            continue

        total = contract.total_value or 0
        lines = [
            f"• {i.get('name', 'Đợt ?')} — {i.get('percentage', 0)}% "
            f"(~{total * i.get('percentage', 0) / 100:,.0f}đ)"
            + (f" — hạn {i['due_date']}" + (" (QUÁ HẠN)" if str(i['due_date']) < today.isoformat() else "")
               if i.get("due_date") else "")
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
    7 ngày (mỗi mốc 1 lần — ref có tên mốc). Cơ hội bán gói bảo trì.
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
                nhac_lai_sau_gio=24 * 31,  # mỗi mốc 30/7 ngày chỉ nhắc 1 lần
            ):
                notified += 1

    return {"checked": len(projects), "notified": notified}


async def run_all_automation(db: AsyncSession) -> dict:
    # Import muộn: task_sla gọi lại `_notify` của module này.
    from app.services.task_sla import run_task_overdue_alerts, run_task_sla_alerts

    followups = await run_followup_reminders(db)
    recalls = await run_lead_recall(db)
    payments = await run_payment_reminders(db)
    warranties = await run_warranty_reminders(db)
    # Nhắc hạn ĐẦU VIỆC dự án (13/10/2026) — đi cùng batch CSKH hằng ngày thay vì
    # thêm một job riêng, để chỉ có MỘT nơi quyết định tần suất nhắc.
    task_overdue = await run_task_overdue_alerts(db)
    task_sla = await run_task_sla_alerts(db)
    await db.commit()
    return {
        "followups": followups, "recalls": recalls, "payments": payments,
        "warranties": warranties,
        "task_overdue": task_overdue, "task_sla_breach": task_sla,
    }
