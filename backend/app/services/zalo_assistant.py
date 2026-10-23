"""Trợ lý Zalo cho trưởng phòng + BGĐ (spec 09, hoàn thiện 23/10/2026).

Ba việc chạy trên dữ liệu listener đã đẩy về:
- Báo gấp Telegram: tín hiệu quan trọng → người phụ trách nhóm + trưởng phòng
  của nhóm; khách phàn nàn/khách chờ → thêm BGĐ.
- Khách chờ: nhóm KHÁCH có tin cuối của khách mà quá N giờ chưa nhân viên nào
  nhắn lại → tín hiệu `unanswered` (mỗi tin chỉ báo 1 lần).
- Tóm tắt cuối ngày: mỗi nhóm có tin trong ngày → 1 `ZaloDigest` (AI tóm tắt,
  thiếu AI thì đếm + liệt kê tín hiệu); gửi trưởng phòng bản phòng mình, BGĐ
  bản toàn công ty.

Phạm vi xem: admin/executive thấy hết; trưởng phòng (và kế toán) thấy nhóm
gắn phòng mình; còn lại chỉ thấy tín hiệu giao cho chính mình.
"""

import base64
import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from html import escape

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.middleware.rbac import VAI_TRO_TRUONG_PHONG, la_truong_phong
from app.models.user import User
from app.models.zalo import ZaloDigest, ZaloGroup, ZaloMessage, ZaloSignal, ZaloStaff

logger = logging.getLogger(__name__)

VN_TZ = timezone(timedelta(hours=7))
BOD_ROLES = ("admin", "executive")

# Tín hiệu báo gấp cho người phụ trách + trưởng phòng; nhóm sau báo thêm BGĐ
LOAI_BAO_GAP = {"lead_candidate", "quote_request", "deal_risk", "unanswered"}
LOAI_BAO_BGD = {"deal_risk", "unanswered"}

TEN_LOAI = {
    "lead_candidate": "Lead mới",
    "quote_request": "Hỏi giá",
    "commitment": "Cam kết",
    "deal_risk": "Khách không hài lòng",
    "unanswered": "Khách chờ",
    "faq": "Câu hỏi lặp lại",
}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Mã hóa phiên Zalo (cookie + imei) — khóa suy từ JWT_SECRET_KEY
# ---------------------------------------------------------------------------

def _fernet() -> Fernet:
    secret = get_settings().JWT_SECRET_KEY or "jama-dev-secret"
    key = base64.urlsafe_b64encode(hashlib.sha256(f"zalo-session:{secret}".encode()).digest())
    return Fernet(key)


def ma_hoa_phien(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def giai_ma_phien(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, ValueError):
        logger.warning("Phiên Zalo lưu trữ không giải mã được (đổi JWT_SECRET_KEY?) — cần quét QR lại")
        return None


# ---------------------------------------------------------------------------
# Phạm vi xem
# ---------------------------------------------------------------------------

def pham_vi_zalo(user: User) -> tuple[str, str | None]:
    """('tat_ca', None) | ('phong', DEPT) | ('ca_nhan', None)."""
    if user.role in BOD_ROLES:
        return "tat_ca", None
    if la_truong_phong(user) or user.role == "accountant":
        return "phong", (user.department or "").upper()
    return "ca_nhan", None


def duoc_xem_trang(user: User) -> bool:
    return pham_vi_zalo(user)[0] != "ca_nhan"


def loc_tin_hieu(q, user: User):
    """Áp phạm vi lên câu select đã join ZaloGroup."""
    pv, dept = pham_vi_zalo(user)
    if pv == "tat_ca":
        return q
    if pv == "phong":
        return q.where(or_(ZaloGroup.department == dept, ZaloSignal.assigned_user_id == user.id))
    return q.where(ZaloSignal.assigned_user_id == user.id)


# ---------------------------------------------------------------------------
# Người nhận
# ---------------------------------------------------------------------------

async def truong_phong_cua(db: AsyncSession, dept: str | None) -> list[User]:
    if not dept:
        return []
    dept = dept.upper()
    roles = VAI_TRO_TRUONG_PHONG.get(dept, set())
    if dept == "ACCT":
        roles = roles | {"accountant"}
    if not roles:
        return []
    rows = await db.execute(
        select(User).where(User.department == dept, User.role.in_(roles), User.is_active.is_(True))
    )
    return list(rows.scalars().all())


async def ban_giam_doc(db: AsyncSession) -> list[User]:
    rows = await db.execute(
        select(User).where(User.role.in_(BOD_ROLES), User.is_active.is_(True), User.telegram_user_id.is_not(None))
    )
    return list(rows.scalars().all())


async def bao_gap(db: AsyncSession, group: ZaloGroup, signals: list[ZaloSignal]) -> int:
    """Đẩy tín hiệu quan trọng về Telegram. Trả số tin đã gửi."""
    from app.services.telegram_notify import send_telegram

    quan_trong = [s for s in signals if s.type in LOAI_BAO_GAP]
    if not quan_trong:
        return 0

    nguoi: dict[str, User] = {}
    if group.assigned_user_id:
        u = await db.get(User, group.assigned_user_id)
        if u:
            nguoi[u.id] = u
    for u in await truong_phong_cua(db, group.department):
        nguoi[u.id] = u
    bgd = {u.id: u for u in await ban_giam_doc(db)} if any(s.type in LOAI_BAO_BGD for s in quan_trong) else {}

    da_gui = 0
    for sig in quan_trong:
        nhan = dict(nguoi)
        if sig.type in LOAI_BAO_BGD:
            nhan.update(bgd)
        text = (
            f"🔔 <b>Zalo · {escape(group.name)}</b> — {TEN_LOAI.get(sig.type, sig.type)}\n"
            f"{escape(sig.summary)}"
        )
        for u in nhan.values():
            if u.telegram_user_id and await send_telegram(u.telegram_user_id, text):
                da_gui += 1
    return da_gui


# ---------------------------------------------------------------------------
# Nhân viên Zalo + khách chờ
# ---------------------------------------------------------------------------

async def ghi_nhan_nhan_vien(db: AsyncSession, zalo_id: str | None, name: str | None) -> None:
    if not zalo_id:
        return
    row = await db.get(ZaloStaff, zalo_id)
    if row:
        row.last_seen = _now_naive()
        if name:
            row.name = name[:150]
    else:
        db.add(ZaloStaff(zalo_id=zalo_id, name=(name or "")[:150] or None, last_seen=_now_naive()))


async def la_nhan_vien(db: AsyncSession, zalo_id: str | None) -> bool:
    if not zalo_id:
        return False
    return (await db.get(ZaloStaff, zalo_id)) is not None


async def kiem_tra_khach_cho(db: AsyncSession, gio: float = 2) -> list[ZaloSignal]:
    """Nhóm khách: tin cuối là của khách, quá `gio` giờ chưa ai trả lời → tín hiệu.

    Chỉ xét tin trong 24 giờ gần nhất (tin cũ hơn coi như đã qua ngày, không
    báo dồn khi vừa bật nhóm). Mỗi tin khách chỉ sinh 1 tín hiệu.
    """
    now = _now_naive()
    moc = now - timedelta(hours=gio)
    groups = (await db.execute(
        select(ZaloGroup).where(ZaloGroup.kind == "customer", ZaloGroup.monitoring.is_(True))
    )).scalars().all()

    created: list[ZaloSignal] = []
    for g in groups:
        last = (await db.execute(
            select(ZaloMessage).where(ZaloMessage.group_id == g.id)
            .order_by(ZaloMessage.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if not last or last.is_staff:
            continue
        if not (now - timedelta(hours=24) <= last.created_at <= moc):
            continue
        da_bao = (await db.execute(
            select(ZaloSignal.id).where(ZaloSignal.source_msg_id == last.id, ZaloSignal.type == "unanswered")
        )).first()
        if da_bao:
            continue
        cho = int((now - last.created_at).total_seconds() // 3600)
        sig = ZaloSignal(
            group_id=g.id,
            source_msg_id=last.id,
            type="unanswered",
            summary=f"{last.sender_name or 'Khách'} chờ {cho} giờ chưa ai trả lời: \"{(last.text or '')[:120]}\"",
            payload_json=json.dumps({"excerpt": (last.text or "")[:200], "hours": cho}, ensure_ascii=False),
            status="new",
            assigned_user_id=g.assigned_user_id,
        )
        db.add(sig)
        await db.flush()
        await bao_gap(db, g, [sig])
        created.append(sig)
    return created


# ---------------------------------------------------------------------------
# Tóm tắt cuối ngày
# ---------------------------------------------------------------------------

def _khung_ngay(day: date) -> tuple[datetime, datetime]:
    """Ngày VN → khoảng UTC naive."""
    start = datetime(day.year, day.month, day.day, tzinfo=VN_TZ).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)


async def _tom_tat_llm(group: ZaloGroup, lines: list[str]) -> str | None:
    from app.services.llm_config import llm_available, llm_complete
    if not await llm_available():
        return None
    noi_dung = "\n".join(lines)[-6000:]
    prompt = (
        "Bạn là trợ lý của ban giám đốc công ty thiết kế - thi công nội thất JAMA HOME. "
        f"Dưới đây là tin nhắn trong ngày của nhóm Zalo «{group.name}» "
        f"({'nhóm khách hàng' if group.kind == 'customer' else 'nhóm nội bộ'}). "
        "Viết tóm tắt tiếng Việt cho trưởng phòng, tối đa 5 gạch đầu dòng ngắn, theo thứ tự: "
        "việc chính đã làm/đã chốt; vấn đề hoặc khách chưa hài lòng; cam kết có hạn (ai, việc gì, khi nào); "
        "việc cần lãnh đạo quyết. Bỏ qua chuyện phiếm, chào hỏi. Không bịa. "
        "Nếu không có gì đáng kể, trả đúng một dòng «Không có việc đáng chú ý».\n\n"
        f"{noi_dung}"
    )
    try:
        raw = await llm_complete([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=500)
        text = (raw.choices[0].message.content or "").strip()
        return text[:3000] or None
    except Exception as exc:  # AI lỗi → dùng bản đếm
        logger.info("Tóm tắt Zalo bằng AI lỗi, dùng bản đếm: %s", exc)
        return None


async def tao_tom_tat_ngay(db: AsyncSession, day: date) -> list[ZaloDigest]:
    """Tạo (hoặc làm lại) tóm tắt cho mọi nhóm có tin trong ngày `day` (giờ VN)."""
    start, end = _khung_ngay(day)
    rows = (await db.execute(
        select(ZaloMessage.group_id, func.count(ZaloMessage.id))
        .where(ZaloMessage.created_at >= start, ZaloMessage.created_at < end)
        .group_by(ZaloMessage.group_id)
    )).all()

    out: list[ZaloDigest] = []
    for group_id, n in rows:
        group = await db.get(ZaloGroup, group_id)
        if not group or not group.monitoring:
            continue
        msgs = (await db.execute(
            select(ZaloMessage).where(
                ZaloMessage.group_id == group_id,
                ZaloMessage.created_at >= start, ZaloMessage.created_at < end,
            ).order_by(ZaloMessage.created_at)
        )).scalars().all()
        lines = []
        for m in msgs:
            if not m.text:
                continue
            gio = (m.created_at + timedelta(hours=7)).strftime("%H:%M")
            lines.append(f"[{gio}] {m.sender_name or 'Ẩn danh'}: {m.text[:400]}")

        summary = await _tom_tat_llm(group, lines) if lines else None
        by_llm = summary is not None
        if not summary:
            sigs = (await db.execute(
                select(ZaloSignal).where(
                    ZaloSignal.group_id == group_id,
                    ZaloSignal.created_at >= start, ZaloSignal.created_at < end,
                )
            )).scalars().all()
            phan = [f"{n} tin nhắn"]
            phan += [f"• {TEN_LOAI.get(s.type, s.type)}: {s.summary}" for s in sigs[:6]]
            summary = "\n".join(phan)

        digest = (await db.execute(
            select(ZaloDigest).where(ZaloDigest.day == day, ZaloDigest.group_id == group_id)
        )).scalar_one_or_none()
        if digest:
            digest.summary, digest.msg_count, digest.by_llm = summary, int(n), by_llm
        else:
            digest = ZaloDigest(day=day, group_id=group_id, msg_count=int(n), summary=summary, by_llm=by_llm)
            db.add(digest)
        out.append(digest)
    await db.flush()
    return out


def _khoi_nhom(group: ZaloGroup, d: ZaloDigest) -> str:
    return f"<b>💬 {escape(group.name)}</b> · {d.msg_count} tin\n{escape(d.summary)}"


async def gui_tom_tat_ngay(db: AsyncSession, day: date) -> dict:
    """Gửi tóm tắt: trưởng phòng nhận nhóm phòng mình, BGĐ nhận cả công ty."""
    from app.services.telegram_notify import send_telegram

    digests = await tao_tom_tat_ngay(db, day)
    if not digests:
        return {"groups": 0, "sent": 0}

    theo_phong: dict[str, list[str]] = {}
    tat_ca: list[str] = []
    for d in digests:
        g = await db.get(ZaloGroup, d.group_id)
        khoi = _khoi_nhom(g, d)
        tat_ca.append(khoi)
        if g.department:
            theo_phong.setdefault(g.department.upper(), []).append(khoi)

    tieu_de = f"📋 <b>Tóm tắt Zalo {day.strftime('%d/%m')}</b>"
    sent = 0

    def _cat(khoi: list[str]) -> list[str]:
        """Telegram giới hạn 4096 ký tự/tin — chia nhiều tin nếu dài."""
        parts, cur = [], tieu_de
        for k in khoi:
            if len(cur) + len(k) + 2 > 3900:
                parts.append(cur)
                cur = tieu_de + " (tiếp)"
            cur += "\n\n" + k
        parts.append(cur)
        return parts

    da_nhan_ban_full: set[str] = set()
    for u in await ban_giam_doc(db):
        da_nhan_ban_full.add(u.id)
        for part in _cat(tat_ca):
            if await send_telegram(u.telegram_user_id, part):
                sent += 1

    for dept, khoi in theo_phong.items():
        for u in await truong_phong_cua(db, dept):
            if u.id in da_nhan_ban_full or not u.telegram_user_id:
                continue
            for part in _cat(khoi):
                if await send_telegram(u.telegram_user_id, part):
                    sent += 1
    return {"groups": len(digests), "sent": sent}
