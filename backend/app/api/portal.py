"""Customer Portal — public access for customers (read + xác nhận nghiệm thu)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.customer import Customer
from app.models.media import MediaFile
from app.models.project import Project, Task, TaskActivity
from app.models.user import User
from app.services.media_gateway import url_media

router = APIRouter(prefix="/portal", tags=["portal"])

ACCEPTABLE_STAGES = ["design", "quotation", "procurement", "construction", "acceptance", "completed"]


class StageAcceptRequest(BaseModel):
    stage: str
    note: str = Field(default="", max_length=500)


async def _get_customer_by_token(token: str, db: AsyncSession) -> Customer:
    """Look up customer by portal token."""
    result = await db.execute(
        select(Customer).where(Customer.portal_token == token, Customer.portal_enabled == True)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    return customer


def _customer_owns_project(project: Project, customer: Customer) -> bool:
    """customer.lead_id có thể NULL — so sánh khi đó sẽ nhận nhầm mọi dự án
    chưa gắn lead của khách khác, nên chỉ đối chiếu lead_id khi khách có lead."""
    if project.customer_id == customer.id:
        return True
    return customer.lead_id is not None and project.lead_id == customer.lead_id


@router.get("/{token}")
async def portal_profile(token: str, db: AsyncSession = Depends(get_db)):
    """Customer profile + list of projects."""
    customer = await _get_customer_by_token(token, db)

    # Get all projects for this customer
    # (lead_id NULL thì Project.lead_id == None dịch thành IS NULL → lộ dự án khách khác)
    dieu_kien = [Project.customer_id == customer.id]
    if customer.lead_id is not None:
        dieu_kien.append(Project.lead_id == customer.lead_id)
    result = await db.execute(
        select(Project).where(or_(*dieu_kien)).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return {
        "customer": {
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "type": customer.type,
            "company_name": customer.company_name,
        },
        "projects": [
            {
                "id": p.id, "code": p.code, "name": p.name,
                "status": p.status, "stage": p.stage,
                "progress": p.progress, "total_value": p.total_value,
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ],
        "project_count": len(projects),
    }


@router.get("/{token}/projects/{project_id}")
async def portal_project_detail(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    """Project detail with tasks."""
    customer = await _get_customer_by_token(token, db)

    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # Verify customer owns this project
    if not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền xem dự án này")

    # Get tasks
    tasks_result = await db.execute(
        select(Task).where(Task.project_id == project.id).order_by(Task.order)
    )
    # Audit 27/10: sự cố/bảo hành là việc nội bộ — khách không thấy
    tasks = [t for t in tasks_result.scalars().all()
             if not (t.title or "").startswith(("[Sự cố", "[Bảo hành"))]

    task_status = {"done": 0, "in_progress": 0, "not_started": 0}
    for t in tasks:
        st = "done" if t.status == "completed" else t.status
        if st in task_status:
            task_status[st] += 1

    STAGE_LABELS = {
        "design": "Thiết kế", "quotation": "Báo giá", "procurement": "Thu mua",
        "construction": "Thi công", "acceptance": "Nghiệm thu", "completed": "Hoàn thành",
    }

    return {
        "project": {
            "id": project.id, "code": project.code, "name": project.name,
            "status": project.status, "stage": project.stage,
            "stage_label": STAGE_LABELS.get(project.stage, project.stage),
            "progress": project.progress,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "target_end_date": project.target_end_date.isoformat() if project.target_end_date else None,
            "stage_acceptances": project.stage_acceptances or {},
            "handover_date": project.handover_date.isoformat() if project.handover_date else None,
            "warranty_months": project.warranty_months,
        },
        "tasks": [
            {"id": t.id, "title": t.title, "status": "done" if t.status == "completed" else t.status, "stage": t.stage}
            for t in tasks
        ],
        "task_summary": task_status,
        "total_tasks": len(tasks),
    }


@router.post("/{token}/projects/{project_id}/accept-stage")
async def portal_accept_stage(
    token: str,
    project_id: str,
    data: StageAcceptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Khách xác nhận nghiệm thu 1 giai đoạn — lưu timestamp làm bằng chứng.

    Idempotent: giai đoạn đã xác nhận rồi thì trả về bản ghi cũ (không ghi đè).
    """
    customer = await _get_customer_by_token(token, db)

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")
    if data.stage not in ACCEPTABLE_STAGES:
        raise HTTPException(status_code=400, detail="Giai đoạn không hợp lệ")
    # Audit 27/10: chỉ nghiệm thu giai đoạn đang làm hoặc đã qua
    hien_tai = project.stage if project.stage in ACCEPTABLE_STAGES else None
    if hien_tai is None or ACCEPTABLE_STAGES.index(data.stage) > ACCEPTABLE_STAGES.index(hien_tai):
        raise HTTPException(status_code=400, detail="Giai đoạn này chưa tới — chưa nghiệm thu được")

    acceptances = dict(project.stage_acceptances or {})
    if data.stage in acceptances:
        return {"status": "already_accepted", "acceptance": acceptances[data.stage]}

    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "note": data.note.strip(),
        "by": customer.name,
    }
    acceptances[data.stage] = record
    project.stage_acceptances = acceptances
    flag_modified(project, "stage_acceptances")
    await db.flush()

    # Báo sales/PM qua Telegram (best-effort, không chặn response)
    try:
        from app.services.telegram_notify import send_telegram
        STAGE_LABELS = {
            "design": "Thiết kế", "quotation": "Báo giá", "procurement": "Thu mua",
            "construction": "Thi công", "acceptance": "Nghiệm thu", "completed": "Hoàn thành",
        }
        msg = (
            f"✅ Khách <b>{customer.name}</b> vừa xác nhận nghiệm thu giai đoạn "
            f"<b>{STAGE_LABELS.get(data.stage, data.stage)}</b> — dự án {project.code} {project.name}."
        )
        for uid in {project.sales_id, project.pm_id}:
            if not uid:
                continue
            u = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
            if u and u.telegram_user_id:
                await send_telegram(u.telegram_user_id, msg)
    except Exception:
        pass

    return {"status": "accepted", "acceptance": record}


@router.get("/{token}/projects/{project_id}/activities")
async def portal_activities(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    """Nhật ký tiến độ cho khách (20 dòng gần nhất).

    Chỉ `kind == "tien_do"` — trước 23/10 khách thấy cả sự cố, yêu cầu vật
    tư, check-in của thợ. Ảnh không đi theo dòng nhật ký (có thể là ảnh PIC
    chưa cho khách xem); ảnh lấy ở /media, nơi tôn trọng cờ chia sẻ."""
    customer = await _get_customer_by_token(token, db)

    # Verify ownership
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")

    # Get activities from all tasks in this project
    tasks_result = await db.execute(select(Task.id).where(Task.project_id == project.id))
    task_ids = [t[0] for t in tasks_result.all()]

    if not task_ids:
        return {"activities": []}

    act_result = await db.execute(
        select(TaskActivity, User.full_name.label("user_name"))
        .outerjoin(User, TaskActivity.user_id == User.id)
        .where(TaskActivity.task_id.in_(task_ids), TaskActivity.kind == "tien_do")
        .order_by(desc(TaskActivity.created_at))
        .limit(20)
    )

    activities = []
    for act, user_name in act_result.all():
        activities.append({
            "id": act.id, "content": act.content,
            "user_name": user_name or "Nhân viên JAMA",
            "created_at": act.created_at.isoformat(),
        })

    return {"activities": activities}


@router.get("/{token}/projects/{project_id}/media")
async def portal_media(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    """Ảnh công trình PIC đã bật «Khách thấy», gom theo ngày (giờ VN), mới
    nhất trước. Link ảnh đã ký HMAC nên `<img>` mở được không cần đăng nhập."""
    customer = await _get_customer_by_token(token, db)
    project = await db.get(Project, project_id)
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")

    rows = (await db.execute(
        select(MediaFile, User.full_name)
        .outerjoin(User, MediaFile.uploaded_by == User.id)
        .where(MediaFile.project_id == project.id, MediaFile.shared_with_customer == True)
        .order_by(desc(MediaFile.created_at))
        .limit(300)
    )).all()

    ngay: dict[str, list[dict]] = {}
    for m, ten in rows:
        gio_vn = (m.created_at or datetime.now(timezone.utc).replace(tzinfo=None)) + timedelta(hours=7)
        ngay.setdefault(gio_vn.date().isoformat(), []).append({
            "id": m.id,
            "url": url_media(m),
            "width": m.width,
            "height": m.height,
            "caption": m.caption,
            "user_name": ten or "Nhân viên JAMA",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"days": [{"date": d, "items": items} for d, items in ngay.items()], "total": len(rows)}


# ── Khách đánh giá (Chế độ thưởng, 23/10/2026) ──────────────────────────────

class DanhGiaIn(BaseModel):
    moc: str
    so_sao: int = Field(ge=1, le=5)
    nhan_xet: str = Field(default="", max_length=1000)
    khen_user_id: str | None = None


THU_TU_GIAI_DOAN = ["design", "quotation", "procurement", "construction", "acceptance", "completed"]


async def _moc_mo(db: AsyncSession, project: Project) -> dict[str, bool]:
    """Mốc nào khách đã chấm được: phải tới lúc thật mới mở, tránh chấm trước."""
    from app.models.contract import Contract
    co_hd = (await db.execute(
        select(Contract.id).where(Contract.project_id == project.id,
                                  Contract.status.in_(("signed", "completed"))).limit(1)
    )).scalar_one_or_none() is not None
    nghiem_thu = project.stage_acceptances or {}
    try:
        buoc = THU_TU_GIAI_DOAN.index(project.stage or "design")
    except ValueError:
        buoc = 0
    ban_giao = project.handover_date is not None or project.stage == "completed"
    bay_gio = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "ky_hd_tk": co_hd or buoc > 0,
        "chot_ban_ve": "design" in nghiem_thu or buoc > 0,
        "ban_giao": ban_giao,
        "sau_3_thang": project.handover_date is not None and bay_gio - project.handover_date >= timedelta(days=90),
    }


async def _doi_ngu(db: AsyncSession, project: Project) -> list[dict]:
    from app.services.che_do_thuong import doi_du_an
    ids = doi_du_an(project)
    if not ids:
        return []
    vai = {project.sales_id: "Tư vấn", project.designer_id: "Thiết kế",
           project.pm_id: "Quản lý dự án", project.purchasing_id: "Thu mua"}
    ten = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())
    return [{"id": i, "ten": ten.get(i, "Nhân viên JAMA"), "vai": vai.get(i, "")} for i in ids if i in ten]


@router.get("/{token}/projects/{project_id}/danh-gia")
async def portal_xem_danh_gia(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.danh_gia_khach import MOC_DANH_GIA, DanhGiaKhach
    from app.services.che_do_thuong import doc_cau_hinh
    customer = await _get_customer_by_token(token, db)
    project = await db.get(Project, project_id)
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")
    cfg, _ = await doc_cau_hinh(db)
    dg = cfg["chuong_trinh"]["danh_gia"]
    if not dg["bat"]:
        return {"bat": False, "moc": [], "doi_ngu": []}
    da = {r.moc: r for r in (await db.execute(
        select(DanhGiaKhach).where(DanhGiaKhach.project_id == project.id)
    )).scalars().all()}
    mo = await _moc_mo(db, project)
    return {
        "bat": True,
        "moc": [
            {
                "ma": m, "ten": MOC_DANH_GIA[m], "mo": mo.get(m, False),
                "da_cham": ({"so_sao": da[m].so_sao, "nhan_xet": da[m].nhan_xet,
                             "luc": da[m].created_at.isoformat() if da[m].created_at else None}
                            if m in da else None),
            }
            for m in dg["thoi_diem"] if m in MOC_DANH_GIA
        ],
        "doi_ngu": await _doi_ngu(db, project),
    }


@router.post("/{token}/projects/{project_id}/danh-gia")
async def portal_gui_danh_gia(token: str, project_id: str, data: DanhGiaIn, db: AsyncSession = Depends(get_db)):
    """Khách chấm sao 1 mốc. Mỗi mốc chấm 1 lần (không sửa — giữ số thật cho thưởng)."""
    from app.models.danh_gia_khach import MOC_DANH_GIA, DanhGiaKhach
    from app.services.che_do_thuong import doc_cau_hinh, doi_du_an
    customer = await _get_customer_by_token(token, db)
    project = await db.get(Project, project_id)
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")
    cfg, _ = await doc_cau_hinh(db)
    dg = cfg["chuong_trinh"]["danh_gia"]
    if not dg["bat"] or data.moc not in dg["thoi_diem"] or data.moc not in MOC_DANH_GIA:
        raise HTTPException(status_code=400, detail="Mốc đánh giá không hợp lệ")
    if not (await _moc_mo(db, project)).get(data.moc):
        raise HTTPException(status_code=400, detail="Mốc này chưa tới — anh/chị chấm sau nhé")
    cu = (await db.execute(
        select(DanhGiaKhach).where(DanhGiaKhach.project_id == project.id, DanhGiaKhach.moc == data.moc)
    )).scalar_one_or_none()
    if cu:
        raise HTTPException(status_code=409, detail="Mốc này anh/chị đã đánh giá rồi — cảm ơn anh/chị!")
    khen = data.khen_user_id if data.khen_user_id in doi_du_an(project) else None
    r = DanhGiaKhach(project_id=project.id, customer_id=customer.id, moc=data.moc,
                     so_sao=data.so_sao, nhan_xet=data.nhan_xet.strip() or None, khen_user_id=khen)
    db.add(r)
    await db.flush()

    if data.so_sao <= 2:
        # Khiếu nại: báo riêng quản lý (không đăng nhóm) để gọi lại khách trong ngày
        try:
            from app.models.user import Team
            from app.services.automation import _notify
            nhan = set((await db.execute(
                select(User.id).where(User.is_active == True, User.role.in_(("admin", "executive")))  # noqa: E712
            )).scalars().all())
            for uid in doi_du_an(project):
                u = await db.get(User, uid)
                if u and u.team_id:
                    t = await db.get(Team, u.team_id)
                    if t and t.leader_id:
                        nhan.add(t.leader_id)
            tieu_de = f"⚠️ Khách chấm {data.so_sao}★ — {project.code}"
            noi_dung = (f"Khách {customer.name} chấm {data.so_sao} sao mốc «{MOC_DANH_GIA[data.moc]}» dự án "
                        f"{project.code} {project.name}." + (f" Nhận xét: {data.nhan_xet.strip()[:300]}" if data.nhan_xet.strip() else "")
                        + " Thưởng đánh giá của dự án đang được giữ lại — gọi lại khách sớm.")
            for uid in nhan:
                await _notify(db, await db.get(User, uid), type_="danh_gia_khach", title=tieu_de,
                              body=noi_dung, link=f"/projects?id={project.id}", ref_id=r.id)
        except Exception:
            pass

    from app.cache import cache
    cache.clear_prefix("cdt:")
    return {"ok": True, "id": r.id}


# ── Vật tư: khách tự xem giá bán & đồng ý (27/10/2026, #13) ─────────────────

class KhachVatTuIn(BaseModel):
    ghi_chu: str | None = Field(default=None, max_length=500)


def _dong_cho_khach(d, ten_mau: dict) -> dict:
    """Không bao giờ trả giá vốn / NCC / % áp dụng cho khách."""
    cho_duyet = d.trang_thai in ("cho_khach_duyet_lai", "het_hang") or (
        d.gia_ban is not None and d.trang_thai == "da_chot_gia" and not (
            d.khach_dong_y_luc and (not d.chot_luc or d.khach_dong_y_luc >= d.chot_luc)))
    return {
        "id": d.id, "phong": d.phong, "hang_muc": d.hang_muc,
        "ten": ten_mau.get(d.mau_id) or d.ma_tu_do,
        "thay_the": ten_mau.get(d.mau_thay_the_id) or d.ma_thay_the, "ly_do_doi": d.ly_do_doi,
        "so_luong": d.so_luong, "don_vi": d.don_vi, "gia_ban": d.gia_ban,
        "thanh_tien": (d.gia_ban * d.so_luong) if d.gia_ban is not None else None,
        "trang_thai": d.trang_thai, "cho_khach_duyet": cho_duyet,
        "khach_dong_y_luc": d.khach_dong_y_luc.isoformat() if d.khach_dong_y_luc else None,
    }


async def _ten_mau(db: AsyncSession, ds) -> dict:
    from app.models.vat_tu import MauVatTu
    ids = {i for d in ds for i in (d.mau_id, d.mau_thay_the_id) if i}
    if not ids:
        return {}
    return {m.id: " · ".join(x for x in (m.ma, m.ten, m.hang) if x)
            for m in (await db.execute(select(MauVatTu).where(MauVatTu.id.in_(ids)))).scalars()}


@router.get("/{token}/projects/{project_id}/vat-tu")
async def portal_vat_tu(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.vat_tu import DongPhieuVatTu
    customer = await _get_customer_by_token(token, db)
    project = await db.get(Project, project_id)
    if not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == project.id, DongPhieuVatTu.trang_thai != "huy")
        .order_by(DongPhieuVatTu.phong, DongPhieuVatTu.thu_tu, DongPhieuVatTu.created_at)
    )).scalars().all()
    ten = await _ten_mau(db, ds)
    return [_dong_cho_khach(d, ten) for d in ds]


@router.post("/{token}/vat-tu/{dong_id}/dong-y")
async def portal_vat_tu_dong_y(token: str, dong_id: str, data: KhachVatTuIn, db: AsyncSession = Depends(get_db)):
    from app.models.vat_tu import DongPhieuVatTu
    customer = await _get_customer_by_token(token, db)
    d = await db.get(DongPhieuVatTu, dong_id)
    project = await db.get(Project, d.project_id) if d else None
    if not d or not project or not _customer_owns_project(project, customer):
        raise HTTPException(status_code=403, detail="Không có quyền")
    d.khach_dong_y_luc = datetime.now(timezone.utc).replace(tzinfo=None)
    d.khach_ghi_chu = ((data.ghi_chu or "").strip() or None) and f"[Khách tự bấm] {data.ghi_chu.strip()}"
    if d.trang_thai in ("cho_khach_duyet_lai", "het_hang") and (d.mau_thay_the_id or d.ma_thay_the):
        d.mau_id, d.ma_tu_do = d.mau_thay_the_id, (None if d.mau_thay_the_id else d.ma_thay_the)
        d.mau_thay_the_id = d.ma_thay_the = None
        d.trang_thai = "hoi_ncc"
    await db.commit()
    await db.refresh(d)
    return _dong_cho_khach(d, await _ten_mau(db, [d]))
