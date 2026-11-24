"""KPI API — performance metrics, leaderboard, coaching notes, reviews."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import VAI_TRO_BGD, is_sales_coordinator, is_team_lead
from app.models.user import User, Team
from app.models.performance import KpiSnapshot, CoachingNote, ReviewCycle
from app.services.attendance_service import VN_TZ
from app.services.kpi_engine import (
    LEAD_QUA_TAI, NGUONG_CAN_KEM, NGUONG_DAT, compute_kpi, cong_thuc, dam_bao_snapshot,
    detect_burnout, get_leaderboard, ky_truoc, nguoi_duoc_cham, parse_period, snapshot_all,
    tien_do_ky,
)
from app.services.audit import log_action

router = APIRouter(prefix="/kpi", tags=["kpi"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_period() -> str:
    # Giờ VN: trước 7h sáng mùng 1 theo UTC vẫn là tháng cũ, mở app ra thấy kỳ sai.
    return datetime.now(timezone.utc).astimezone(VN_TZ).strftime("%Y-%m")


def _period_hop_le(period: str | None) -> str:
    period = period or _current_period()
    try:
        nam, thang = period.split("-")
        if not (len(nam) == 4 and 1 <= int(thang) <= 12 and int(nam) >= 2000):
            raise ValueError
    except ValueError:
        raise HTTPException(400, f"Kỳ phải theo dạng YYYY-MM, nhận được: {period!r}")
    return f"{int(nam):04d}-{int(thang):02d}"


def _canh_bao(m: dict, score: float, score_truoc: float | None, qua_nua_ky: bool) -> list[dict]:
    """Cờ cần chú ý của MỘT người — đọc thẳng từ số đã chấm, không suy diễn thêm."""
    if m.get("chua_du_lieu"):
        return [{"ma": "chua_du_lieu", "muc": "xam", "noi_dung": "Chưa có lead hay deal trong kỳ"}]
    cb = []
    if m.get("lead_dang_giu", 0) > LEAD_QUA_TAI:
        cb.append({"ma": "qua_tai", "muc": "do",
                   "noi_dung": f"Đang giữ {m['lead_dang_giu']} lead — quá tải (mốc {LEAD_QUA_TAI})"})
    if m.get("lead_tre_cham", 0) >= 5:
        cb.append({"ma": "tre_cham", "muc": "do" if m["lead_tre_cham"] >= 10 else "vang",
                   "noi_dung": f"{m['lead_tre_cham']} lead quá hạn chăm"})
    if score_truoc is not None and score - score_truoc <= -15:
        cb.append({"ma": "tut_diem", "muc": "vang",
                   "noi_dung": f"Tụt {round(score_truoc - score, 1):g} điểm so với kỳ trước"})
    if score_truoc is not None and score < NGUONG_CAN_KEM and score_truoc < NGUONG_CAN_KEM:
        cb.append({"ma": "hai_ky_thap", "muc": "do",
                   "noi_dung": f"Dưới {NGUONG_CAN_KEM:.0f} điểm hai kỳ liền"})
    if qua_nua_ky and m.get("deal_thang", 0) == 0:
        cb.append({"ma": "chua_deal", "muc": "vang", "noi_dung": "Chưa có deal thắng trong kỳ"})
    return cb


async def _hang_nhan_vien(db: AsyncSession, period: str, q_loc=None) -> list[dict]:
    """Bảng chấm một kỳ, mỗi người một dòng kèm điểm kỳ trước + cờ cần chú ý.

    `q_loc`: hàm nhận truy vấn và thêm điều kiện phạm vi (nhóm mình / chỉ mình).
    """
    await dam_bao_snapshot(db, period)
    truoc = ky_truoc(period)
    await dam_bao_snapshot(db, truoc)

    q = (
        select(KpiSnapshot, User.full_name, User.team_id, User.role, Team.name)
        .join(User, KpiSnapshot.user_id == User.id)
        .outerjoin(Team, User.team_id == Team.id)
        .where(KpiSnapshot.period == period)
    )
    if q_loc is not None:
        q = q_loc(q)
    rows = (await db.execute(q.order_by(KpiSnapshot.score.desc()))).all()

    diem_truoc = dict((await db.execute(
        select(KpiSnapshot.user_id, KpiSnapshot.score).where(KpiSnapshot.period == truoc)
    )).all())
    da_qua, so_ngay = tien_do_ky(period)
    qua_nua_ky = da_qua * 2 >= so_ngay

    hang = []
    for snap, ten, team_id, role, ten_nhom in rows:
        m = json.loads(snap.metrics_json)
        score_truoc = diem_truoc.get(snap.user_id)
        hang.append({
            "user_id": snap.user_id,
            "name": ten,
            "team_id": team_id,
            "ten_nhom": ten_nhom,
            "la_truong_nhom": role in ("leader", "sale_leader"),
            "score": snap.score,
            "score_truoc": score_truoc,
            "delta": round(snap.score - score_truoc, 1) if score_truoc is not None else None,
            "metrics": m,
            "rank_in_team": snap.rank_in_team,
            "rank_overall": snap.rank_overall,
            "canh_bao": _canh_bao(m, snap.score, score_truoc, qua_nua_ky),
        })
    # Người chưa có dữ liệu xuống cuối: 0 điểm của họ là «trống», không xếp chung với «kém».
    hang.sort(key=lambda h: (bool(h["metrics"].get("chua_du_lieu")), -h["score"]))
    return hang


# ---------------------------------------------------------------------------
# GET /kpi/me — personal KPI
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_my_kpi(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = _period_hop_le(period)
    await dam_bao_snapshot(db, period)

    existing = (await db.execute(
        select(KpiSnapshot).where(
            KpiSnapshot.user_id == current_user.id,
            KpiSnapshot.period == period,
        )
    )).scalar_one_or_none()

    da_qua, so_ngay = tien_do_ky(period)
    dang_chay = 0 < da_qua and datetime.now(timezone.utc) < parse_period(period)[1]
    # Người gánh chỉ tiêu mới có điểm để chấm; vai khác (trưởng phòng Thiết kế, giám sát…)
    # mở tab này chỉ thấy lời giải thích, không bị gán «0 điểm».
    thuoc_doi = existing is not None or any(
        u.id == current_user.id for u in await nguoi_duoc_cham(db))
    chung = {
        "period": period,
        "thuoc_doi": thuoc_doi,
        "tien_do": {"ngay_da_qua": da_qua, "so_ngay": so_ngay, "dang_chay": dang_chay},
        "cong_thuc": cong_thuc(),
        "rank_in_team": existing.rank_in_team if existing else None,
        "rank_overall": existing.rank_overall if existing else None,
    }

    # Kỳ đã khép: đọc bản chụp đã đóng băng, không còn việc gì để «làm tiếp».
    if existing and not dang_chay:
        return {**chung, "score": existing.score,
                "metrics": json.loads(existing.metrics_json), "viec_tiep": []}

    # Kỳ đang chạy: tính tại chỗ cho riêng người này — vừa gọi xong một khách, tải lại
    # là điểm và danh sách việc đổi ngay, không chờ bản chụp 10 phút của cả đội.
    result = await compute_kpi(db, current_user.id, period, kem_viec=thuoc_doi)
    return {**chung, "score": result["score"], "metrics": result["metrics"],
            "viec_tiep": result.get("viec_tiep", [])}


# ---------------------------------------------------------------------------
# GET /kpi/team — team KPI (leader sees own team, admin/executive sees all)
# ---------------------------------------------------------------------------

@router.get("/team")
async def get_team_kpi(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = _period_hop_le(period)

    # Điều phối KD (Admin CSKH) được xem KPI toàn đội — chủ dự án chốt 12/08/2026:
    # họ chia data cho sale nên phải nhìn được ai đang tải nặng, ai đang hụt số.
    if (
        current_user.role not in VAI_TRO_BGD
        and not is_team_lead(current_user)
        and not is_sales_coordinator(current_user)
    ):
        raise HTTPException(403, "Chỉ admin/trưởng phòng/ban quản trị/điều phối KD xem KPI đội")

    def pham_vi(q):
        # Trưởng nhóm (leader/sale_leader): chỉ KPI nhóm mình; chưa có nhóm → chỉ mình
        if current_user.role != "admin" and is_team_lead(current_user):
            if current_user.team_id:
                return q.where(User.team_id == current_user.team_id)
            return q.where(User.id == current_user.id)
        return q

    return {
        "period": period,
        "members": await _hang_nhan_vien(db, period, pham_vi),
        "cong_thuc": cong_thuc(),
    }


# ---------------------------------------------------------------------------
# GET /kpi/tong-quan — góc nhìn Ban giám đốc: cả công ty trong một lần gọi
# ---------------------------------------------------------------------------

def _ten_gon(ds: list[dict], khoa=lambda h: "", toi_da: int = 4) -> str:
    phan = [f"{h['name']}{khoa(h)}" for h in ds[:toi_da]]
    return ", ".join(phan) + (f" và {len(ds) - toi_da} người nữa" if len(ds) > toi_da else "")


@router.get("/tong-quan")
async def kpi_tong_quan(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Một màn cho người ra quyết định: công ty đang ở đâu so với mục tiêu, nhóm
    nào kéo/ghì, ai cần kèm — kèm đủ tên và công thức đang áp dụng."""
    if current_user.role not in VAI_TRO_BGD:
        raise HTTPException(403, "Chỉ Ban giám đốc xem được tổng quan KPI toàn công ty")
    period = _period_hop_le(period)
    truoc = ky_truoc(period)

    hang = await _hang_nhan_vien(db, period)
    da_qua, so_ngay = tien_do_ky(period)

    truoc_rows = (await db.execute(
        select(KpiSnapshot.score, KpiSnapshot.metrics_json).where(KpiSnapshot.period == truoc)
    )).all()
    m_truoc = [(s, json.loads(raw)) for s, raw in truoc_rows]
    co_so_truoc = [s for s, m in m_truoc if not m.get("chua_du_lieu")]

    def tong(khoa: str, ds=None) -> float:
        return sum((h["metrics"].get(khoa) or 0) for h in (hang if ds is None else ds))

    def tom_tat(ds: list[dict]) -> dict:
        co_so = [h for h in ds if not h["metrics"].get("chua_du_lieu")]
        nhan, mt_td = tong("lead_nhan", ds), tong("muc_tieu_tien_do", ds)
        return {
            "so_nguoi": len(ds),
            "doanh_so": tong("doanh_so", ds),
            "muc_tieu_thang": tong("muc_tieu_doanh_so", ds),
            "muc_tieu_tien_do": mt_td,
            "dat_pct": round(tong("doanh_so", ds) / mt_td * 100, 1) if mt_td else None,
            "deal": tong("deal_thang", ds),
            "lead_nhan": nhan,
            "ty_le_tien_buoc": round(tong("lead_tien_buoc", ds) / nhan * 100, 1) if nhan else None,
            "ty_le_mat": round(tong("lead_mat", ds) / nhan * 100, 1) if nhan else None,
            "lead_dang_giu": tong("lead_dang_giu", ds),
            "lead_tre_cham": tong("lead_tre_cham", ds),
            "du_bao": tong("du_bao", ds),
            "diem_tb": round(sum(h["score"] for h in co_so) / len(co_so), 1) if co_so else None,
            "phan_bo": {
                "dat": sum(1 for h in co_so if h["score"] >= NGUONG_DAT),
                "trung_binh": sum(1 for h in co_so if NGUONG_CAN_KEM <= h["score"] < NGUONG_DAT),
                "can_kem": sum(1 for h in co_so if h["score"] < NGUONG_CAN_KEM),
                "chua_du_lieu": len(ds) - len(co_so),
            },
        }

    tong_ct = tom_tat(hang)
    tong_ct["doanh_so_truoc"] = sum((m.get("doanh_so") or 0) for _, m in m_truoc) if m_truoc else None
    tong_ct["deal_truoc"] = sum((m.get("deal_thang") or 0) for _, m in m_truoc) if m_truoc else None
    tong_ct["diem_tb_truoc"] = round(sum(co_so_truoc) / len(co_so_truoc), 1) if co_so_truoc else None

    # ── Theo nhóm ────────────────────────────────────────────────────────────
    theo_nhom: dict[str | None, list[dict]] = {}
    for h in hang:
        theo_nhom.setdefault(h["team_id"], []).append(h)
    nhom = []
    for tid, ds in theo_nhom.items():
        tt = tom_tat(ds)
        truong = next((h["name"] for h in ds if h["la_truong_nhom"]), None)
        nhom.append({"team_id": tid, "ten": ds[0]["ten_nhom"] or "Chưa xếp nhóm",
                     "truong_nhom": truong, **tt})
    nhom.sort(key=lambda n: -(n["doanh_so"] or 0))

    # ── Điều cần chú ý: mỗi dòng là một việc BGĐ có thể hỏi ngay hôm nay ─────
    co_so = [h for h in hang if not h["metrics"].get("chua_du_lieu")]
    chu_y: list[dict] = []

    def them(muc: str, tieu_de: str, chi_tiet: str = "") -> None:
        chu_y.append({"muc": muc, "tieu_de": tieu_de, "chi_tiet": chi_tiet})

    if tong_ct["dat_pct"] is not None:
        pct = tong_ct["dat_pct"]
        them("xanh" if pct >= 100 else "vang" if pct >= 70 else "do",
             f"Doanh số đạt {pct:g}% mục tiêu tính đến hôm nay" if da_qua < so_ngay
             else f"Doanh số kỳ đạt {pct:g}% mục tiêu",
             f"Ngày {da_qua}/{so_ngay} của kỳ." if da_qua < so_ngay else "")
    if tong_ct["doanh_so"] > 0 and len(co_so) >= 4:
        xep = sorted(co_so, key=lambda h: -(h["metrics"].get("doanh_so") or 0))
        hai_dau = sum((h["metrics"].get("doanh_so") or 0) for h in xep[:2])
        ty_trong = hai_dau / tong_ct["doanh_so"] * 100
        if ty_trong >= 60:
            them("vang", f"{ty_trong:.0f}% doanh số đến từ 2 người",
                 f"{_ten_gon(xep[:2])} — đội đang phụ thuộc vào ít người.")
    if da_qua * 2 >= so_ngay:
        chua_deal = [h for h in co_so if not h["metrics"].get("deal_thang")]
        if chua_deal:
            them("vang", f"{len(chua_deal)}/{len(co_so)} người chưa có deal thắng", _ten_gon(chua_deal))
    tre = sorted((h for h in co_so if h["metrics"].get("lead_tre_cham")),
                 key=lambda h: -h["metrics"]["lead_tre_cham"])
    if tong_ct["lead_tre_cham"] >= 5:
        them("do" if tong_ct["lead_tre_cham"] >= 20 else "vang",
             f"{tong_ct['lead_tre_cham']:g} lead đang mở quá hạn chăm",
             _ten_gon(tre, lambda h: f" ({h['metrics']['lead_tre_cham']})"))
    for ma, muc, tieu_de in (
        ("qua_tai", "do", "Đang quá tải lead"),
        ("hai_ky_thap", "do", f"Dưới {NGUONG_CAN_KEM:.0f} điểm hai kỳ liền"),
        ("tut_diem", "vang", "Tụt điểm mạnh so với kỳ trước"),
    ):
        ds = [h for h in co_so if any(c["ma"] == ma for c in h["canh_bao"])]
        if ds:
            duoi = {
                "qua_tai": lambda h: f" ({h['metrics']['lead_dang_giu']} lead)",
                "hai_ky_thap": lambda h: f" ({h['score']:g})",
                "tut_diem": lambda h: f" ({h['delta']:+g})",
            }[ma]
            them(muc, f"{tieu_de}: {len(ds)} người", _ten_gon(ds, duoi))
    if tong_ct["phan_bo"]["chua_du_lieu"]:
        trong = [h for h in hang if h["metrics"].get("chua_du_lieu")]
        them("xam", f"{len(trong)} người chưa có lead hay deal trong kỳ", _ten_gon(trong))

    return {
        "period": period,
        "ky_truoc": truoc,
        "tien_do": {"ngay_da_qua": da_qua, "so_ngay": so_ngay, "dang_chay": 0 < da_qua < so_ngay},
        "tinh_luc": max((h["metrics"].get("tinh_luc") or "" for h in hang), default=None) or None,
        "tong": tong_ct,
        "nhom": nhom,
        "nhan_vien": hang,
        "can_chu_y": chu_y,
        "cong_thuc": cong_thuc(),
    }


# ---------------------------------------------------------------------------
# GET /kpi/leaderboard — nhân viên: ẩn tên từ hạng 6; BGĐ: đủ tên
# ---------------------------------------------------------------------------

@router.get("/leaderboard")
async def get_kpi_leaderboard(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = _period_hop_le(period)
    await dam_bao_snapshot(db, period)
    return await get_leaderboard(db, period, current_user.id,
                                 hien_het_ten=current_user.role in VAI_TRO_BGD)


# ---------------------------------------------------------------------------
# POST /kpi/snapshot — trigger manual snapshot (admin only)
# ---------------------------------------------------------------------------

@router.post("/snapshot")
async def trigger_snapshot(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Chỉ admin chạy snapshot")

    period = period or _current_period()
    count = await snapshot_all(db, period)
    await log_action(db, actor=current_user, action="kpi_snapshot", entity_type="kpi", note=f"Snapshot KPI kỳ {period}: {count} users")
    return {"period": period, "users_snapshot": count}


# ---------------------------------------------------------------------------
# GET /kpi/burnout — personal burnout status
# ---------------------------------------------------------------------------

@router.get("/burnout")
async def get_my_burnout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await detect_burnout(db, current_user.id)
    return result


# ---------------------------------------------------------------------------
# Coaching notes
# ---------------------------------------------------------------------------

class CoachingNoteCreate(BaseModel):
    user_id: str
    note: str
    kind: str = "one_on_one"


@router.post("/coaching-notes")
async def create_coaching_note(
    body: CoachingNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and not is_team_lead(current_user):
        raise HTTPException(403, "Chỉ trưởng nhóm/admin tạo coaching note")

    # Trưởng nhóm chỉ note cho người trong nhóm mình
    if current_user.role != "admin":
        target = await db.get(User, body.user_id)
        if not target or current_user.team_id is None or target.team_id != current_user.team_id:
            raise HTTPException(403, "Nhân viên không thuộc team của bạn")

    note = CoachingNote(
        user_id=body.user_id,
        coach_id=current_user.id,
        note=body.note,
        kind=body.kind,
    )
    db.add(note)
    await db.commit()
    await log_action(db, actor=current_user, action="coaching_note", entity_type="coaching", note=f"Note cho {body.user_id}: {body.kind}")
    return {"id": note.id, "created_at": str(note.created_at)}


@router.get("/coaching-notes")
async def list_coaching_notes(
    user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(CoachingNote).order_by(CoachingNote.created_at.desc())

    if user_id:
        # Users can only see notes about themselves; leaders see team; admin sees all
        if current_user.role == "admin":
            q = q.where(CoachingNote.user_id == user_id)
        elif is_team_lead(current_user) and user_id != current_user.id:
            target = await db.get(User, user_id)
            if target and current_user.team_id is not None and target.team_id == current_user.team_id:
                q = q.where(CoachingNote.user_id == user_id)
            else:
                raise HTTPException(403, "Không có quyền xem note của nhân viên này")
        else:
            if user_id != current_user.id:
                raise HTTPException(403, "Chỉ xem note của chính mình")
            q = q.where(CoachingNote.user_id == user_id)
    else:
        # Default: leader sees own team, admin sees all
        if current_user.role == "admin":
            pass
        elif is_team_lead(current_user) and current_user.team_id is not None:
            team_users = (await db.execute(
                select(User.id).where(User.team_id == current_user.team_id)
            )).scalars().all()
            q = q.where(CoachingNote.user_id.in_(team_users))
        else:
            q = q.where(CoachingNote.user_id == current_user.id)

    notes = (await db.execute(q.limit(50))).scalars().all()
    return {
        "items": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "coach_id": n.coach_id,
                "note": n.note,
                "kind": n.kind,
                "created_at": str(n.created_at),
            }
            for n in notes
        ]
    }


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class ReviewSelfSubmit(BaseModel):
    self_json: str  # JSON string with self-assessment answers


class ReviewLeaderSubmit(BaseModel):
    leader_json: str  # JSON string with leader assessment
    goals_json: str | None = None
    suggested_grade_change: str | None = None


@router.get("/reviews/me")
async def get_my_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reviews = (await db.execute(
        select(ReviewCycle).where(ReviewCycle.user_id == current_user.id)
        .order_by(ReviewCycle.created_at.desc()).limit(4)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "period": r.period,
                "status": r.status,
                "self_json": r.self_json,
                "leader_json": r.leader_json,
                "goals_json": r.goals_json,
                "suggested_grade_change": r.suggested_grade_change,
            }
            for r in reviews
        ]
    }


@router.put("/reviews/me/{review_id}")
async def submit_self_review(
    review_id: str,
    body: ReviewSelfSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = await db.get(ReviewCycle, review_id)
    if not review or review.user_id != current_user.id:
        raise HTTPException(404, "Không tìm thấy review")
    if review.status != "pending_self":
        raise HTTPException(409, "Review không ở trạng thái chờ self-assessment")

    review.self_json = body.self_json
    review.status = "pending_leader"
    await db.commit()
    await log_action(db, actor=current_user, action="review_self", entity_type="review", note=f"Submit self review kỳ {review.period}")
    return {"status": review.status}


@router.put("/reviews/{review_id}/leader")
async def submit_leader_review(
    review_id: str,
    body: ReviewLeaderSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and not is_team_lead(current_user):
        raise HTTPException(403, "Chỉ trưởng nhóm/admin chấm review")

    review = await db.get(ReviewCycle, review_id)
    if not review:
        raise HTTPException(404, "Không tìm thấy review")
    if review.status != "pending_leader":
        raise HTTPException(409, "Review không ở trạng thái chờ leader")

    # Trưởng nhóm chỉ chấm người trong nhóm mình
    if current_user.role != "admin":
        target = await db.get(User, review.user_id)
        if not target or current_user.team_id is None or target.team_id != current_user.team_id:
            raise HTTPException(403, "Nhân viên không thuộc team của bạn")

    review.leader_json = body.leader_json
    review.goals_json = body.goals_json
    review.suggested_grade_change = body.suggested_grade_change
    review.status = "done"
    await db.commit()
    await log_action(db, actor=current_user, action="review_leader", entity_type="review", note=f"Submit leader review kỳ {review.period}")
    return {"status": review.status}
