"""«Việc cần Ban Giám đốc quyết» (24/11/2026) — khối đầu trang «Việc của tôi» của BGĐ.

Giám đốc không được giao đầu việc dự án nên trang «Việc của tôi» của họ trống trơn.
Việc của Giám đốc là gỡ chỗ kẹt và ra quyết định, nên mỗi mục ở đây là MỘT quyết định
hoặc một cuộc hỏi cụ thể: có số, có lý do, có tên người/dự án, có đường bấm tới nơi xử lý.

Nguyên tắc chọn mục:
- Chỉ nêu việc đã vượt tầm người phụ trách trực tiếp (kẹt lâu, quá tải, lệch mục tiêu).
  Việc còn trong hạn là của trưởng nhóm/trưởng phòng, không đẩy lên đây.
- Số lấy từ cùng nguồn với trang gốc (KPI, Phê duyệt, Dự án, Vật tư), không tính lại kiểu khác.
- Không có gì vượt mốc thì trả danh sách rỗng: màn hình nói thẳng «không có việc cần quyết».
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.lead import ACTIVE_LEAD_STAGES, XAC_SUAT_STAGE, Lead
from app.models.performance import KpiSnapshot
from app.models.project import Project, Task
from app.models.user import Team, User
from app.models.vat_tu import DongPhieuVatTu, MauVatTu
from app.services.attendance_service import VN_TZ
from app.services.kpi_engine import (
    LEAD_QUA_TAI, NGUONG_CAN_KEM, STAGE_GAN_CHOT, _tien_gon, dam_bao_snapshot, ky_truoc, tien_do_ky,
)

logger = logging.getLogger(__name__)

# ── Mốc «đã vượt tầm người phụ trách» — đổi ở đây, nhớ sửa mục «viec-cua-toi» trong Sổ tay ──
DON_KET_NGAY = 2            # đơn chờ duyệt quá 2 ngày
LEAD_CHUA_GIAO_GIO = 24     # lead chưa có sale phụ trách quá 24 giờ
LEAD_TRE_TOI_THIEU = 5      # cả đội từ 5 lead quá hạn chăm mới nêu
DOANH_SO_BAO_DONG = 70.0    # doanh số dưới 70% mốc tiến độ hôm nay
MUC_TIEU_LECH = 2.0         # mục tiêu tháng từ gấp đôi doanh số kỳ trước trở lên
VIEC_TRE_NGAY = 3           # đầu việc dự án quá hạn hơn 3 ngày (trong 3 ngày là việc của trưởng phòng)
TAM_DUNG_NGAY = 14          # dự án tạm dừng quá 14 ngày
SO_DONG = 5                 # mỗi mục kèm tối đa chừng này dòng; số tổng nằm ở `tong`


def _naive(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo is not None else dt


def _so_ngay(tu: datetime | None, moc: datetime) -> int:
    return max(0, (moc - _naive(tu)).days) if tu else 0


def _so(x: float) -> str:
    """Số gọn kiểu Việt: 12.5 → «12,5», 21.0 → «21»."""
    return f"{x:g}".replace(".", ",")


def _gia_tri(l: Lead) -> float:
    return float(l.design_contract_value or l.deal_value or l.estimated_budget or 0)


def _muc(ma: str, muc: str, tieu_de: str, ly_do: str, nut: str, href: str,
         dong: list[dict], tong: int | None = None) -> dict:
    return {"ma": ma, "muc": muc, "tieu_de": tieu_de, "ly_do": ly_do, "nut": nut, "href": href,
            "tong": len(dong) if tong is None else tong, "dong": dong[:SO_DONG]}


async def _don_ket_duyet(db: AsyncSession, moc: datetime, user: User) -> dict | None:
    rows = (await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.status == "pending",
               ApprovalRequest.created_at < moc - timedelta(days=DON_KET_NGAY))
        .order_by(ApprovalRequest.created_at)
    )).scalars().all()
    if not rows:
        return None
    ids = {r.requester_id for r in rows} | {r.current_approver_id for r in rows if r.current_approver_id}
    ten = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())
    cua_toi = sum(1 for r in rows if r.current_approver_id == user.id)
    dong = [{
        "ten": r.title,
        "phu": f"{ten.get(r.requester_id, '—')} gửi · chờ "
               f"{'bạn' if r.current_approver_id == user.id else ten.get(r.current_approver_id, 'chưa rõ ai')} duyệt"
               f" · {_so_ngay(r.created_at, moc)} ngày",
        "href": "/approvals",
    } for r in rows]
    return _muc(
        "don_ket_duyet", "do" if cua_toi else "vang",
        f"{len(rows)} đơn chờ duyệt đã kẹt quá {DON_KET_NGAY} ngày",
        (f"Trong đó {cua_toi} đơn đang chờ chính bạn. " if cua_toi else "")
        + "Người gửi đang phải đứng chờ. Duyệt đơn của mình, và nhắc người đang giữ các đơn còn lại.",
        "Mở Phê duyệt", "/approvals", dong)


async def _lead_chua_giao(db: AsyncSession, moc: datetime) -> dict | None:
    rows = (await db.execute(
        select(Lead)
        .where(Lead.assigned_to.is_(None), Lead.stage.in_(ACTIVE_LEAD_STAGES),
               Lead.created_at < moc - timedelta(hours=LEAD_CHUA_GIAO_GIO))
        .order_by(Lead.created_at)
    )).scalars().all()
    if not rows:
        return None
    from app.api.leads import STAGE_LABELS  # nạp trễ: api ↔ services không vòng nhau lúc import
    dong = [{
        "ten": l.name or "Khách chưa có tên",
        "phu": f"{STAGE_LABELS.get(l.stage, l.stage)} · chờ {_so_ngay(l.created_at, moc)} ngày chưa ai nhận",
        "href": f"/leads?id={l.id}",
    } for l in rows]
    return _muc(
        "lead_chua_giao", "do",
        f"{len(rows)} lead chưa có sale phụ trách quá {LEAD_CHUA_GIAO_GIO} giờ",
        "Lead chưa giao thì không ai gọi, khách nguội dần. Yêu cầu Điều phối Kinh doanh hoặc trưởng nhóm chia ngay hôm nay.",
        "Mở trang Lead", "/leads", dong)


async def _hang_kpi(db: AsyncSession, period: str) -> list[dict]:
    rows = (await db.execute(
        select(KpiSnapshot, User.full_name, Team.name)
        .join(User, KpiSnapshot.user_id == User.id)
        .outerjoin(Team, User.team_id == Team.id)
        .where(KpiSnapshot.period == period)
    )).all()
    return [{"user_id": s.user_id, "ten": ten, "nhom": nhom or "Chưa xếp nhóm", "score": s.score,
             "m": json.loads(s.metrics_json)} for s, ten, nhom in rows]


async def _tu_kpi(db: AsyncSession, moc: datetime) -> list[dict]:
    """Bốn mục đọc từ bảng chấm KPI kỳ này: lead quá hạn, quá tải, doanh số, người cần kèm."""
    period = moc.replace(tzinfo=timezone.utc).astimezone(VN_TZ).strftime("%Y-%m")
    truoc = ky_truoc(period)
    await dam_bao_snapshot(db, period)
    await dam_bao_snapshot(db, truoc)
    hang = await _hang_kpi(db, period)
    hang_truoc = await _hang_kpi(db, truoc)
    co_so = [h for h in hang if not h["m"].get("chua_du_lieu")]
    ra: list[dict] = []

    # ── Lead quá hạn chăm dồn ở ai ──────────────────────────────────────────
    tre = sorted((h for h in co_so if h["m"].get("lead_tre_cham")), key=lambda h: -h["m"]["lead_tre_cham"])
    tong_tre = sum(h["m"]["lead_tre_cham"] for h in tre)
    if tong_tre >= LEAD_TRE_TOI_THIEU:
        ra.append(_muc(
            "lead_qua_han", "do" if tong_tre >= 20 else "vang",
            f"{tong_tre:g} lead đang mở đã quá hạn chăm, dồn ở {len(tre)} người",
            "Khách quá hạn chưa ai liên hệ là khách dễ mất nhất. Giao trưởng nhóm của những người dưới đây "
            "xử lý trong hôm nay; ai quá nhiều thì chuyển bớt cho người khác.",
            "Xem lead quá hạn", "/leads?filter=overdue",
            [{"ten": h["ten"], "phu": f"{h['nhom']} · {h['m']['lead_tre_cham']:g} lead quá hạn"
                                      f" / đang giữ {h['m'].get('lead_dang_giu', 0):g}",
              "href": "/kpi?tab=team"} for h in tre]))

    # ── Quá tải: nêu luôn ai đang nhẹ để chuyển sang ────────────────────────
    nang = sorted((h for h in co_so if h["m"].get("lead_dang_giu", 0) > LEAD_QUA_TAI),
                  key=lambda h: -h["m"]["lead_dang_giu"])
    if nang:
        nhe = sorted((h for h in hang if h["m"].get("lead_dang_giu", 0) <= LEAD_QUA_TAI // 2),
                     key=lambda h: h["m"].get("lead_dang_giu", 0))[:3]
        goi_y = ("Người đang nhẹ có thể nhận thêm: "
                 + ", ".join(f"{h['ten']} ({h['m'].get('lead_dang_giu', 0):g} lead)" for h in nhe) + "."
                 ) if nhe else "Cả đội đều đang nặng: cân nhắc giảm lượng lead đổ về hoặc thêm người."
        ra.append(_muc(
            "qua_tai", "do",
            f"{len(nang)} người đang giữ quá {LEAD_QUA_TAI} lead",
            f"Giữ quá {LEAD_QUA_TAI} lead thì không chăm kịp, lead mới đổ thêm sẽ bị bỏ. {goi_y}",
            "Mở trang Lead", "/leads",
            [{"ten": h["ten"], "phu": f"{h['nhom']} · đang giữ {h['m']['lead_dang_giu']:g} lead",
              "href": "/kpi?tab=team"} for h in nang]))

    # ── Doanh số so mốc hôm nay + các lead lớn gần chốt để Giám đốc hỗ trợ ───
    doanh_so = sum(h["m"].get("doanh_so") or 0 for h in hang)
    mt_thang = sum(h["m"].get("muc_tieu_doanh_so") or 0 for h in hang)
    mt_td = sum(h["m"].get("muc_tieu_tien_do") or 0 for h in hang)
    da_qua, so_ngay = tien_do_ky(period)
    if mt_td > 0 and doanh_so / mt_td * 100 < DOANH_SO_BAO_DONG:
        gan_chot = (await db.execute(
            select(Lead, User.full_name)
            .join(User, Lead.assigned_to == User.id)
            .where(Lead.stage.in_(STAGE_GAN_CHOT))
        )).all()
        gan_chot.sort(key=lambda r: -XAC_SUAT_STAGE.get(r[0].stage, 0) * _gia_tri(r[0]))
        from app.api.leads import STAGE_LABELS
        ra.append(_muc(
            "doanh_so", "do",
            f"Doanh số mới đạt {doanh_so / mt_td * 100:.0f}% mốc hôm nay, còn thiếu {_tien_gon(mt_td - doanh_so)}",
            f"Ngày {da_qua}/{so_ngay} của kỳ: "
            + (f"đã có {_tien_gon(doanh_so)}" if doanh_so else "chưa có deal nào")
            + f" trên mục tiêu tháng {_tien_gon(mt_thang)}. "
            + ("Dưới đây là các lead gần chốt có giá trị lớn nhất. Hỏi sale phụ trách đang vướng gì, "
               "có cần Giám đốc gặp khách hay duyệt ưu đãi để chốt không."
               if gan_chot else "Hiện chưa có lead nào ở bước khảo sát trở lên: nghẽn nằm ở đầu phễu, cần thêm lead chất lượng."),
            "Mở Bảng điều khiển Kinh doanh", "/sale-dashboard",
            [{"ten": l.name or "Khách chưa có tên",
              "phu": f"{ten_sale} · {STAGE_LABELS.get(l.stage, l.stage)}"
                     + (f" · {_tien_gon(_gia_tri(l))}" if _gia_tri(l) else " · chưa ghi giá trị"),
              "href": f"/leads?id={l.id}"} for l, ten_sale in gan_chot],
            tong=len(gan_chot)))

    # ── Mục tiêu lệch xa thực tế: điểm «Kết quả» của cả đội mất nghĩa ───────
    ds_truoc = sum(h["m"].get("doanh_so") or 0 for h in hang_truoc)
    if ds_truoc > 0 and mt_thang >= ds_truoc * MUC_TIEU_LECH:
        gap = f"{mt_thang / ds_truoc:.1f}".replace(".", ",")
        ra.append(_muc(
            "muc_tieu_lech", "vang",
            f"Mục tiêu tháng {_tien_gon(mt_thang)} gấp {gap} lần doanh số tháng trước ({_tien_gon(ds_truoc)})",
            "Mục tiêu quá xa thực tế thì gần như ai cũng thiếu điểm Kết quả, KPI không còn phân biệt được người làm tốt "
            "với người làm kém. Xem lại mục tiêu cho sát sức đội, hoặc giữ nguyên nếu đây là chủ ý.",
            "Chỉnh mục tiêu", "/sale-dashboard", []))

    # ── Dưới ngưỡng hai kỳ liền ──────────────────────────────────────────────
    diem_truoc = {h["user_id"]: h["score"] for h in hang_truoc if not h["m"].get("chua_du_lieu")}
    kem = sorted((h for h in co_so if h["score"] < NGUONG_CAN_KEM
                  and diem_truoc.get(h["user_id"], NGUONG_CAN_KEM) < NGUONG_CAN_KEM),
                 key=lambda h: h["score"])
    if kem:
        ra.append(_muc(
            "can_kem", "vang",
            f"{len(kem)} người dưới {NGUONG_CAN_KEM:.0f} điểm KPI hai tháng liền",
            ("Hơn nửa đội dưới ngưỡng hai kỳ liền thì vấn đề không nằm ở từng người: xem lại mục tiêu và lượng "
             "lead có vừa sức đội không trước khi kèm riêng ai."
             if len(kem) * 2 > len(co_so) else
             "Hai kỳ liền dưới ngưỡng thì không còn là một tháng xui. Trao đổi với trưởng nhóm về kế hoạch kèm "
             "từng người, có hạn rõ ràng."),
            "Xem KPI đội nhóm", "/kpi?tab=team",
            [{"ten": h["ten"], "phu": f"{h['nhom']} · {_so(h['score'])} điểm, tháng trước {_so(diem_truoc[h['user_id']])}",
              "href": "/kpi?tab=team"} for h in kem]))
    return ra


async def _du_an(db: AsyncSession, moc: datetime) -> list[dict]:
    ra: list[dict] = []

    # ── Đầu việc quá hạn lâu, gom theo dự án ────────────────────────────────
    han = func.coalesce(Task.due_date, Task.sla_due_at)
    rows = (await db.execute(
        select(Project.id, Project.code, Project.name, func.count(Task.id), func.min(han))
        .join(Project, Project.id == Task.project_id)
        .where(Project.status == "active",
               Task.status.notin_(("done", "completed", "cancelled")),
               han < moc - timedelta(days=VIEC_TRE_NGAY))
        .group_by(Project.id, Project.code, Project.name)
    )).all()
    if rows:
        rows.sort(key=lambda r: -r[3])
        tong_viec = sum(r[3] for r in rows)
        ra.append(_muc(
            "viec_tre", "do" if tong_viec >= 10 else "vang",
            f"{tong_viec} đầu việc quá hạn hơn {VIEC_TRE_NGAY} ngày ở {len(rows)} dự án",
            "Trễ vài ngày là việc của trưởng phòng, trễ lâu là dấu hiệu dự án đang kẹt. Hỏi người phụ trách "
            "từng dự án lý do và hạn mới.",
            "Mở Dự án", "/projects",
            [{"ten": f"{code} · {ten}", "phu": f"{n} việc quá hạn · trễ lâu nhất {_so_ngay(som_nhat, moc)} ngày",
              "href": f"/projects?id={pid}"} for pid, code, ten, n, som_nhat in rows],
            tong=len(rows)))

    # ── Dự án đã qua ngày bàn giao dự kiến ──────────────────────────────────
    tre = (await db.execute(
        select(Project).where(Project.status == "active", Project.target_end_date < moc)
        .order_by(Project.target_end_date)
    )).scalars().all()
    if tre:
        ra.append(_muc(
            "du_an_tre", "do",
            f"{len(tre)} dự án đã qua ngày bàn giao dự kiến",
            "Trễ bàn giao ảnh hưởng thẳng tới đợt thu tiền và uy tín với khách. Chốt lại ngày bàn giao mới "
            "với người phụ trách và báo khách.",
            "Mở Dự án", "/projects",
            [{"ten": f"{p.code} · {p.name}",
              "phu": f"trễ {_so_ngay(p.target_end_date, moc)} ngày · tiến độ {p.progress}%",
              "href": f"/projects?id={p.id}"} for p in tre]))

    # ── Dự án tạm dừng lâu: tiếp tục hay đóng ───────────────────────────────
    dung = (await db.execute(
        select(Project).where(Project.status == "paused",
                              Project.paused_at < moc - timedelta(days=TAM_DUNG_NGAY))
        .order_by(Project.paused_at)
    )).scalars().all()
    if dung:
        ra.append(_muc(
            "du_an_tam_dung", "vang",
            f"{len(dung)} dự án tạm dừng quá {TAM_DUNG_NGAY} ngày",
            "Dự án treo lâu vẫn giữ người và vật tư. Quyết định chạy tiếp hay đóng lại.",
            "Mở Dự án", "/projects",
            [{"ten": f"{p.code} · {p.name}",
              "phu": f"dừng {_so_ngay(p.paused_at, moc)} ngày" + (f" · {p.pause_reason}" if p.pause_reason else ""),
              "href": f"/projects?id={p.id}"} for p in dung]))
    return ra


async def _gia_chuan(db: AsyncSession) -> dict | None:
    """Mẫu vật tư đang nằm trong phiếu của dự án đang chạy mà Giám đốc chưa ấn định giá chuẩn."""
    rows = (await db.execute(
        select(MauVatTu.id, MauVatTu.ma, MauVatTu.ten, func.count(DongPhieuVatTu.id))
        .join(DongPhieuVatTu, DongPhieuVatTu.mau_id == MauVatTu.id)
        .join(Project, Project.id == DongPhieuVatTu.project_id)
        .where(Project.status == "active", DongPhieuVatTu.trang_thai != "huy",
               func.coalesce(MauVatTu.gia_ban_co_dinh, 0) <= 0)
        .group_by(MauVatTu.id, MauVatTu.ma, MauVatTu.ten)
    )).all()
    if not rows:
        return None
    rows.sort(key=lambda r: -r[3])
    return _muc(
        "gia_chuan", "xam",
        f"{len(rows)} mẫu vật tư đang dùng trong dự án chưa có giá chuẩn",
        "Mẫu chưa có giá chuẩn thì giá bán đang tính theo giá vốn cộng phần trăm, chưa phải đơn giá Giám đốc ấn định.",
        "Mở Bảng giá chuẩn", "/vat-tu?tab=gia-chuan&loc=chua_co",
        [{"ten": " ".join(f"{ma} · {ten}".split()) if ten else " ".join(ma.split()),
          "phu": f"đang nằm trong {n} dòng phiếu",
          "href": "/vat-tu?tab=gia-chuan&loc=chua_co"} for _, ma, ten, n in rows])


async def _bai_hoc_ai(db: AsyncSession) -> dict | None:
    from app.services.ai_tien_hoa import bang_theo_doi
    so = (await bang_theo_doi(db)).get("so_cho_duyet") or 0
    if not so:
        return None
    return _muc(
        "bai_hoc_ai", "xam",
        f"{so} bài học của trợ lý AI đang chờ bạn duyệt",
        "Bài học chỉ có hiệu lực khi quản trị duyệt; để lâu thì trợ lý vẫn gợi ý theo cách cũ.",
        "Mở AI Tiến Hoá", "/ai-tien-hoa", [], tong=so)


async def viec_can_bgd_quyet(db: AsyncSession, user: User) -> list[dict]:
    """Danh sách việc cần BGĐ quyết, xếp theo độ gấp. Một nguồn lỗi không làm trắng cả khối."""
    moc = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC naive, khớp kiểu cột
    ra: list[dict] = []

    async def thu(ten: str, viec) -> None:
        try:
            kq = await viec
            ra.extend(kq if isinstance(kq, list) else [kq] if kq else [])
        except Exception:
            logger.warning("Việc BGĐ: nguồn %s lỗi, bỏ qua mục này", ten, exc_info=True)
            await db.rollback()

    await thu("don_ket_duyet", _don_ket_duyet(db, moc, user))
    await thu("lead_chua_giao", _lead_chua_giao(db, moc))
    await thu("kpi", _tu_kpi(db, moc))
    await thu("du_an", _du_an(db, moc))
    if user.role == "admin":  # chỉ admin đặt giá chuẩn và duyệt bài học AI
        await thu("gia_chuan", _gia_chuan(db))
        await thu("bai_hoc_ai", _bai_hoc_ai(db))

    thu_tu = {"do": 0, "vang": 1, "xam": 2}
    ra.sort(key=lambda v: thu_tu.get(v["muc"], 3))  # sort ổn định: cùng mức giữ thứ tự nguồn
    return ra
