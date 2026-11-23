"""Hai nhịp mỗi ngày của sale trên Telegram (R00 mục 9-10, 21/11/2026).

Luật §B: sale nhận tối đa 2 nhịp/ngày — bản tin sáng + câu hỏi sau buổi hẹn — cộng sự
kiện nóng (lead mới…). Hệ hỏi, người trả lời bằng nút.

1. Bản tin sáng «Hôm nay của bạn» (từ 07:00): hẹn hôm nay, hẹn hôm qua chưa có kết quả,
   khách cần gọi, đợt thu cần nhắc. Mỗi dòng một nút: khách → bot gửi thẻ khách có nút
   (ld:bt / ld:bq), đợt thu → mở hợp đồng trên ERP. Thay cho các tin nhắc chăm khách lẻ
   lúc 07:00 (những tin đó giờ chỉ còn trong chuông). /briefing của bot dùng cùng bản tin.
2. Hỏi kết quả buổi hẹn: 2 tiếng sau giờ hẹn, trong 08:00-21:00, hỏi «Buổi hẹn với
   {khách} thế nào?» MỘT lần cho mỗi buổi hẹn trong ngày. Chưa trả lời (hoặc hẹn quá muộn
   để hỏi trong ngày) → vào mục «Hẹn hôm qua chưa có kết quả» của bản tin sáng hôm sau,
   không hỏi lần 3.

Không có giá vốn: đợt thu là tiền khách trả theo hợp đồng.
"""

from __future__ import annotations

import html
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.lead import ACTIVE_LEAD_STAGES, Activity, Lead
from app.models.project import Project
from app.models.user import User
from app.services.automation import VN, _notify, ds_lead_can_goi, gio_vn_naive
from app.services.lead_touch import NHAN_LOAI_HEN, THU_VN
from app.services.telegram_notify import erp_url, nut_ket_qua_hen, send_telegram

logger = logging.getLogger(__name__)

GIO_HOI_TU, GIO_HOI_DEN = 8, 21          # chỉ hỏi kết quả hẹn trong 08:00-21:00
HOI_SAU = timedelta(hours=2)             # hỏi 2 tiếng sau giờ hẹn
LOAI_HOI = "hoi_ket_qua_hen"             # ref hen:<lead_id>:<YYYYMMDDHHMM> (lead_touch đánh dấu đã đọc)
LOAI_BAN_TIN = "ban_tin_sang"
HOI_MOT_LAN_GIO = 24 * 30                # mỗi buổi hẹn chỉ hỏi một lần
# Activity KHÔNG phải kết quả buổi hẹn do người phụ trách ghi.
LOAI_KHONG_PHAI_KET_QUA = ("cskh", "assignment", "system")
TRANG_THAI_HD_THU = ("signed", "active", "in_progress")   # như run_payment_reminders
DOT_THU_TRUOC_NGAY = 3
TOI_DA = {"hen_nay": 8, "hen_qua": 6, "can_goi": 10, "dot_thu": 5}


# ── Hẹn ──────────────────────────────────────────────────────────────────────


def cac_hen(lead: Lead) -> list[tuple[datetime, str]]:
    """Các mốc hẹn của lead (naive giờ VN) kèm nhãn loại: hẹn tiếp và ngày khảo sát."""
    ra: list[tuple[datetime, str]] = []
    if lead.hen_tiep_luc:
        ra.append((lead.hen_tiep_luc, NHAN_LOAI_HEN.get(lead.plan_type or "", "Hẹn")))
    if lead.survey_date and lead.survey_date != lead.hen_tiep_luc:
        ra.append((lead.survey_date, "Khảo sát"))
    return ra


def ma_hen(lead_id: str, moc: datetime) -> str:
    return f"hen:{lead_id}:{moc:%Y%m%d%H%M}"


async def da_co_ket_qua(db: AsyncSession, lead_id: str, moc_vn: datetime) -> bool:
    """Sau giờ hẹn đã có ai ghi gì vào lead chưa (gọi, gặp, ghi chú, hẹn mới, đổi giai đoạn…)."""
    tu = moc_vn.replace(tzinfo=VN).astimezone(timezone.utc).replace(tzinfo=None)
    so = (await db.execute(
        select(func.count(Activity.id)).where(
            Activity.lead_id == lead_id,
            Activity.created_at > tu,
            Activity.type.notin_(LOAI_KHONG_PHAI_KET_QUA),
        )
    )).scalar() or 0
    return so > 0


async def run_hoi_ket_qua_hen(db: AsyncSession, now_vn: datetime | None = None) -> dict:
    """Hỏi kết quả các buổi hẹn HÔM NAY đã qua ≥ 2 tiếng mà chưa có kết quả (mỗi buổi 1 lần)."""
    now = now_vn or gio_vn_naive()
    if not (GIO_HOI_TU <= now.hour < GIO_HOI_DEN):
        return {"status": "skipped", "ly_do": "ngoai_gio", "hoi": 0}
    dau_ngay = datetime.combine(now.date(), time())
    den = now - HOI_SAU
    leads = (await db.execute(
        select(Lead).where(
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
            Lead.assigned_to.is_not(None),
            or_(Lead.hen_tiep_luc.between(dau_ngay, den), Lead.survey_date.between(dau_ngay, den)),
        )
    )).scalars().all()

    hoi = 0
    for lead in leads:
        user = await db.get(User, lead.assigned_to)
        if user is None or not user.is_active:
            continue
        for moc, loai in cac_hen(lead):
            if not (dau_ngay <= moc <= den) or await da_co_ket_qua(db, lead.id, moc):
                continue
            gui = await _notify(
                db, user, LOAI_HOI,
                f"Buổi hẹn với {lead.name} thế nào?",
                f"{loai} lúc {moc:%H:%M} hôm nay · SĐT {lead.phone}\n"
                "Bấm một nút để ghi kết quả, khỏi mở web.",
                link=f"/leads?id={lead.id}", ref_id=ma_hen(lead.id, moc),
                nut=nut_ket_qua_hen(lead.id), nhac_lai_sau_gio=HOI_MOT_LAN_GIO,
            )
            hoi += int(gui)
    if hoi:
        logger.info("Hỏi kết quả buổi hẹn: %d câu", hoi)
    return {"status": "completed", "hoi": hoi}


# ── Bản tin sáng ─────────────────────────────────────────────────────────────


def _ngan(s: str, n: int = 22) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _tien(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") + "đ"


async def _dot_thu_can_nhac(db: AsyncSession, user_id: str, hom_nay: date) -> list[dict]:
    """Đợt thu chưa thu của hợp đồng thuộc dự án sale phụ trách, hạn trong 3 ngày tới hoặc đã quá."""
    rows = (await db.execute(
        select(Contract, Project)
        .join(Project, Project.id == Contract.project_id)
        .where(Project.sales_id == user_id, Contract.status.in_(TRANG_THAI_HD_THU))
    )).all()
    ra: list[dict] = []
    for hd, _ in rows:
        tong = hd.total_value or 0
        for i, dot in enumerate((hd.payment_terms or {}).get("installments") or []):
            if dot.get("status") not in ("pending", "partial") or not dot.get("due_date"):
                continue
            try:
                han = date.fromisoformat(str(dot["due_date"])[:10])
            except ValueError:
                continue
            if (han - hom_nay).days > DOT_THU_TRUOC_NGAY:
                continue
            ra.append({
                "hd": hd, "ten": dot.get("name") or f"Đợt {i + 1}", "han": han,
                "so_tien": tong * (dot.get("percentage") or 0) / 100,
                "mot_phan": dot.get("status") == "partial",
            })
    ra.sort(key=lambda d: d["han"])
    return ra


async def dung_ban_tin(db: AsyncSession, user: User, now_vn: datetime | None = None) -> dict | None:
    """Bản tin «Hôm nay của bạn» của một người: {text (HTML Telegram), reply_markup, tom_tat}.

    None khi không có việc gì. Chỉ lead người đó đang phụ trách và hợp đồng dự án của họ.
    """
    now = now_vn or gio_vn_naive()
    hom_nay = now.date()
    hom_qua = hom_nay - timedelta(days=1)
    tu = datetime.combine(hom_qua, time())
    leads = (await db.execute(
        select(Lead).where(
            Lead.assigned_to == user.id,
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
            or_(Lead.hen_tiep_luc >= tu, Lead.survey_date >= tu),
        )
    )).scalars().all()
    hen_nay, hen_qua = [], []
    for lead in leads:
        for moc, loai in cac_hen(lead):
            if moc.date() == hom_nay:
                hen_nay.append((moc, loai, lead))
            elif moc.date() == hom_qua and not await da_co_ket_qua(db, lead.id, moc):
                hen_qua.append((moc, loai, lead))
    hen_nay.sort(key=lambda x: x[0])
    hen_qua.sort(key=lambda x: x[0])
    co_hen = {lead.id for _, _, lead in hen_nay + hen_qua}
    can_goi = [(lead, n) for lead, n in await ds_lead_can_goi(db, user.id) if lead.id not in co_hen]
    dot_thu = await _dot_thu_can_nhac(db, user.id, hom_nay)
    if not (hen_nay or hen_qua or can_goi or dot_thu):
        return None

    e = lambda s: html.escape(s or "", quote=False)  # noqa: E731
    dong: list[str] = [f"<b>Hôm nay của bạn</b> · {THU_VN[hom_nay.weekday()]} {hom_nay:%d/%m}"]
    nut: list[dict] = []
    so = 0

    def muc(tieu_de: str, ds: list, cap: str, ve, nut_cua, du: str) -> None:
        nonlocal so
        if not ds:
            return
        dong.append(f"\n<b>{tieu_de} ({len(ds)})</b>")
        for x in ds[: TOI_DA[cap]]:
            so += 1
            dong.append(f"{so}. {ve(x)}")
            nut.append(nut_cua(x, so))
        if len(ds) > TOI_DA[cap]:
            dong.append(f"… và {len(ds) - TOI_DA[cap]} {du} khác — mở ERP để xem hết.")

    def nut_khach(ma: str, lay):
        """ld:bt = thẻ khách kèm nút chạm khách; ld:bq = thẻ kèm nút kết quả buổi hẹn."""
        return lambda x, n: {"text": f"{n}. {_ngan(lay(x).name)}", "callback_data": f"ld:{ma}:{lay(x).id}"}

    muc("Hẹn hôm nay", hen_nay, "hen_nay",
        lambda x: f"{x[0]:%H:%M} · <b>{e(x[2].name)}</b> · {e(x[1])} · {e(x[2].phone)}",
        nut_khach("bt", lambda x: x[2]), "hẹn")
    muc("Hẹn hôm qua chưa có kết quả", hen_qua, "hen_qua",
        lambda x: f"{x[0]:%H:%M} hôm qua · <b>{e(x[2].name)}</b> · {e(x[1])} · {e(x[2].phone)}",
        nut_khach("bq", lambda x: x[2]), "hẹn")
    muc("Cần gọi", can_goi, "can_goi",
        lambda x: f"<b>{e(x[0].name)}</b> · {x[1]} ngày chưa liên hệ · {e(x[0].phone)}",
        nut_khach("bt", lambda x: x[0]), "khách")

    def ve_dot(d: dict) -> str:
        han = "quá hạn" if d["han"] < hom_nay else "hôm nay" if d["han"] == hom_nay else f"hạn {d['han']:%d/%m}"
        them = " · đã thu một phần" if d["mot_phan"] else ""
        return f"HĐ {e(d['hd'].code)} · {e(d['ten'])} · {_tien(d['so_tien'])} · {han}{them}"

    def nut_dot(d: dict, n: int) -> dict:
        url = erp_url(f"/contracts?id={d['hd'].id}")
        return {"text": f"{n}. HĐ {_ngan(d['hd'].code, 18)}", "url": url} if url else {}

    muc("Đợt thu cần nhắc", dot_thu, "dot_thu", ve_dot, nut_dot, "đợt")
    dong.append("\nBấm số để làm việc với khách đó.")

    nut = [b for b in nut if b]
    hang = [nut[i: i + 2] for i in range(0, len(nut), 2)]
    url = erp_url("/leads")
    if url:
        hang.append([{"text": "Mở ERP", "url": url}])
    phan = [(len(hen_nay), "hẹn hôm nay"), (len(hen_qua), "hẹn hôm qua chưa có kết quả"),
            (len(can_goi), "khách cần gọi"), (len(dot_thu), "đợt thu cần nhắc")]
    return {
        "text": "\n".join(dong),
        "reply_markup": {"inline_keyboard": hang},
        "tom_tat": " · ".join(f"{n} {ten}" for n, ten in phan if n),
    }


async def run_ban_tin_sang(db: AsyncSession, now_vn: datetime | None = None) -> dict:
    """Gửi bản tin sáng cho mọi người đang phụ trách lead / dự án có đợt thu. Mỗi ngày 1 lần."""
    now = now_vn or gio_vn_naive()
    ids = set((await db.execute(
        select(Lead.assigned_to).where(Lead.assigned_to.is_not(None), Lead.stage.in_(ACTIVE_LEAD_STAGES)).distinct()
    )).scalars().all())
    ids |= set((await db.execute(
        select(Project.sales_id).join(Contract, Contract.project_id == Project.id)
        .where(Project.sales_id.is_not(None), Contract.status.in_(TRANG_THAI_HD_THU)).distinct()
    )).scalars().all())

    gui = qua_telegram = 0
    for uid in ids:
        user = await db.get(User, uid)
        if user is None or not user.is_active:
            continue
        bt = await dung_ban_tin(db, user, now)
        if bt is None:
            continue
        moi = await _notify(
            db, user, LOAI_BAN_TIN, "Hôm nay của bạn", bt["tom_tat"],
            link="/leads", ref_id=f"ban_tin:{now:%Y-%m-%d}", telegram=False,
        )
        if not moi:
            continue  # hôm nay đã gửi (khởi động lại sau 07:00)
        gui += 1
        if user.telegram_user_id and await send_telegram(
            user.telegram_user_id, bt["text"], reply_markup=bt["reply_markup"],
        ):
            qua_telegram += 1
    logger.info("Bản tin sáng: %d người (%d qua Telegram)", gui, qua_telegram)
    return {"status": "completed", "gui": gui, "telegram": qua_telegram}
