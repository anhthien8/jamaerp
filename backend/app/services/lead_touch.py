"""Ghi một lần chăm khách: lõi DÙNG CHUNG cho web và nút Telegram (R00 mục 3, 14/11/2026).

Web (`POST /leads/{id}/activities`) và nút trên tin bot (`POST /telegram/lead/{id}/touch`)
cùng gọi vào đây, để một lần bấm trên Telegram ghi y hệt một lần bấm trên web:

- Ghi Activity, kèm id tin Telegram khi bấm từ bot (đo được bao nhiêu % hoạt động đến từ
  Telegram).
- Chạm khách thật (gọi, gặp, Zoom, khách lên văn phòng, ghi chú) dời mốc «liên hệ lần
  cuối». Hẹn lịch, đánh giá CSKH và các dòng hệ thống thì không: đó không phải chạm khách.
- Người vừa xử lý lead thì các thông báo về lead đó của chính họ coi như đã đọc.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import CSKH_ACTIVITY_TYPE, Activity, Lead
from app.models.notification import Notification
from app.models.user import User
from app.services.automation import gio_vn_naive

# Loại Activity KHÔNG phải một lần chạm khách → không dời mốc «liên hệ lần cuối».
# cskh: cuộc gọi KIỂM TRA chất lượng của Admin CSKH (tính vào sẽ xoá oan nhãn «Quá hạn»).
# hen: mới là kế hoạch; chính mốc hẹn lo việc «không nhắc» (automation.co_hen_toi).
LOAI_KHONG_TINH_LIEN_HE = frozenset(
    {CSKH_ACTIVITY_TYPE, "hen", "stage_change", "assignment", "system"}
)

# Việc bấm được trên tin Telegram → (loại Activity, nội dung mặc định).
VIEC_TIEP_XUC: dict[str, tuple[str, str]] = {
    "goi": ("call", "Đã gọi cho khách"),
    "gap": ("meeting", "Đã gặp khách trực tiếp"),
    "zoom": ("zoom", "Đã tư vấn khách qua Zoom/online"),
    "vp": ("office_visit", "Khách lên văn phòng"),
    "ghi_chu": ("note", ""),
}

# Nhãn loại buổi hẹn — khớp PLAN_TYPE_LABELS của frontend (lib/utils.ts).
NHAN_LOAI_HEN: dict[str, str] = {
    "online": "Tư vấn Online",
    "offline": "Tư vấn Offline",
    "survey": "Khảo sát",
}

# Bấm lặp (mạng chậm, bấm hai lần) trong khoảng này → trả lại bản ghi cũ, không ghi đôi.
CHONG_BAM_LAP_GIAY = 120

# «Mai / 3 ngày / 1 tuần» = 09:00 giờ VN của ngày đó.
GIO_HEN_MAC_DINH = 9

# Hẹn xa hơn coi như nhầm: một ngày hẹn quá xa sẽ miễn nhắc/thu hồi lead rất lâu.
HEN_XA_NHAT_NGAY = 180


def nhan_gio_hen(moc: datetime) -> str:
    """09:00 15/11/2026 — mốc naive giờ VN."""
    return moc.strftime("%H:%M %d/%m/%Y")


THU_VN = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật")

# Nhãn ngắn của việc vừa ghi — server trả sẵn cho bot (`nhan` ở /touch, `tom_tat` ở /doan).
NHAN_VIEC: dict[str, str] = {
    "goi": "Đã gọi",
    "gap": "Đã gặp trực tiếp",
    "zoom": "Đã Zoom/online",
    "vp": "Khách lên văn phòng",
    "ghi_chu": "Ghi chú",
}


def nhan_hen_ngan(moc: datetime, now_vn: datetime | None = None) -> str:
    """«09:00 thứ Hai 16/11» — kèm thứ để sale soát nhanh bot hiểu đúng ngày."""
    nam = "" if moc.year == (now_vn or gio_vn_naive()).year else f"/{moc.year}"
    return f"{moc:%H:%M} {THU_VN[moc.weekday()]} {moc:%d/%m}{nam}"


def nhan_viec(
    viec: str | None, hen_luc: datetime | None = None, plan_type: str | None = None,
    now_vn: datetime | None = None,
) -> str:
    """«Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 17/11», «Hẹn tư vấn offline 14:00 thứ Bảy 21/11»."""
    phan = [NHAN_VIEC[viec]] if viec in NHAN_VIEC else []
    if hen_luc is not None:
        loai = NHAN_LOAI_HEN.get(plan_type or "")
        phan.append(f"hẹn {loai.lower() if loai else 'lại'} {nhan_hen_ngan(hen_luc, now_vn)}")
    s = " · ".join(phan)
    return s[:1].upper() + s[1:]


def moc_hen_sau(so_ngay: int, now_vn: datetime | None = None) -> datetime:
    """Mốc hẹn «sau N ngày»: 09:00 giờ VN của ngày đó (naive, như cột hen_tiep_luc)."""
    ngay = (now_vn or gio_vn_naive()).date() + timedelta(days=so_ngay)
    return datetime(ngay.year, ngay.month, ngay.day, GIO_HEN_MAC_DINH, 0)


async def danh_dau_da_doc_thong_bao_lead(
    db: AsyncSession, user_id: str, lead_id: str
) -> int:
    """Thông báo về lead này của người vừa xử lý → đã đọc.

    Gồm thông báo trỏ thẳng lead (`ref_id = lead_id`: nhắc chăm sóc, được giao lead) và
    câu hỏi kết quả buổi hẹn (`ref_id = hen:<lead_id>:<giờ hẹn>`).
    """
    res = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read.is_(False),
            or_(
                Notification.ref_id == lead_id,
                Notification.ref_id.like(f"hen:{lead_id}:%"),
            ),
        )
        .values(read=True)
        .execution_options(synchronize_session=False)
    )
    return res.rowcount or 0


async def ghi_hoat_dong(
    db: AsyncSession,
    lead: Lead,
    user: User,
    loai: str,
    noi_dung: str,
    *,
    tg_message_id: int | None = None,
    tg_chat_id: int | None = None,
    chong_bam_lap: bool = False,
) -> tuple[Activity, bool]:
    """Ghi một Activity cho lead. Trả `(activity, moi_ghi)`.

    `chong_bam_lap`: cùng người + lead + loại + nội dung trong `CHONG_BAM_LAP_GIAY` giây
    thì trả bản cũ, `moi_ghi=False` (nút Telegram bấm hai lần không ghi đôi).
    """
    now = datetime.now(timezone.utc)
    if chong_bam_lap:
        cu = (
            await db.execute(
                select(Activity)
                .where(
                    Activity.lead_id == lead.id,
                    Activity.user_id == user.id,
                    Activity.type == loai,
                    Activity.content == noi_dung,
                    Activity.created_at >= now - timedelta(seconds=CHONG_BAM_LAP_GIAY),
                )
                .order_by(Activity.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if cu is not None:
            return cu, False

    act = Activity(
        lead_id=lead.id, user_id=user.id, type=loai, content=noi_dung,
        telegram_message_id=tg_message_id, telegram_chat_id=tg_chat_id,
    )
    db.add(act)
    if loai not in LOAI_KHONG_TINH_LIEN_HE:
        lead.last_contacted_at = now
    lead.updated_at = now
    await danh_dau_da_doc_thong_bao_lead(db, user.id, lead.id)
    await db.flush()
    return act, True


async def dat_hen_tiep(
    db: AsyncSession,
    lead: Lead,
    user: User,
    hen_luc: datetime,
    *,
    plan_type: str | None = None,
    ghi_them: str | None = None,
    tg_message_id: int | None = None,
    tg_chat_id: int | None = None,
) -> tuple[Activity, bool]:
    """Đặt hẹn tiếp (`hen_luc` naive giờ VN) + ghi dòng «Hẹn …» vào lịch sử.

    Không dời mốc «liên hệ lần cuối»: hẹn còn ở phía trước đã đủ để bot thôi nhắc và hệ
    thống thôi thu hồi; qua giờ hẹn thì đồng hồ đếm lại từ lúc hẹn.
    """
    if plan_type in NHAN_LOAI_HEN:
        lead.plan_type = plan_type
    lead.hen_tiep_luc = hen_luc
    loai_hen = NHAN_LOAI_HEN.get(plan_type or "")
    noi_dung = f"Hẹn {loai_hen.lower() if loai_hen else 'lại'}: {nhan_gio_hen(hen_luc)}"
    if ghi_them:
        noi_dung = f"{ghi_them.strip()} — {noi_dung}"
    return await ghi_hoat_dong(
        db, lead, user, "hen", noi_dung,
        tg_message_id=tg_message_id, tg_chat_id=tg_chat_id, chong_bam_lap=True,
    )
