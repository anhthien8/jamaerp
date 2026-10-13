"""Giao việc cho NHIỀU người + thông báo cho từng người (13/10/2026).

Yêu cầu chủ dự án: «khu vực Người Đảm Nhận công việc có thể thêm nhiều người»,
«đảm bảo thông báo công việc được gửi đi cho từng nhân sự/tài khoản khi gắn tag,
PIC công việc». Chốt thêm: tất cả người đảm nhận NGANG VAI, không chính/phụ.

Trước bản này có 4 đường đổi người làm và chỉ 1 đường gửi thông báo:
  `assign_task` (gửi) · `create_task` · `update_task` · `bulk_assign_tasks` (im).
Nên mọi đường đều phải đi qua `dat_nguoi_lam()` — thêm đường thứ 5 mà quên gọi
hàm này thì lại tái diễn chuyện giao việc không ai hay.

CỐ Ý không kiểm tra phòng ban của người được gắn ở đây: frontend đã lọc dropdown
theo phòng (`canTakeTask`), còn backend thì `bulk_assign_tasks` và agent AI vẫn
gắn chéo phòng trong dữ liệu cũ. Siết ở tầng này sẽ làm vỡ các đường đang chạy
mà không giải quyết yêu cầu nào của chủ dự án.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Task, TaskAssignee
from app.models.user import User
from app.services.task_sla import lay_cau_hinh_sla, tinh_han_sla

logger = logging.getLogger(__name__)


def _ids_sach(user_ids) -> list[str]:
    """Bỏ rỗng, bỏ trùng, GIỮ thứ tự — thứ tự quyết định ai được soi vào cột
    `assigned_to` (bản sao cho truy vấn cũ)."""
    sach: list[str] = []
    for uid in user_ids or []:
        if uid and uid not in sach:
            sach.append(str(uid))
    return sach


async def dat_nguoi_lam(
    db: AsyncSession,
    task: Task,
    user_ids,
    actor: User | None = None,
    *,
    thong_bao: bool = True,
) -> dict:
    """Đặt lại TOÀN BỘ nhóm đảm nhận của một đầu việc.

    Trả về {"them": [User], "bo": [user_id], "nguoi_lam": [User]} để endpoint
    biết có gì đổi mà ghi log / trả về.

    Người được thêm sẽ nhận thông báo trong app + Telegram. Người tự gắn mình thì
    không tự nhắc mình (actor).
    """
    ids = _ids_sach(user_ids)

    nguoi_theo_id: dict[str, User] = {}
    if ids:
        rows = await db.execute(select(User).where(User.id.in_(ids)))
        nguoi_theo_id = {u.id: u for u in rows.scalars().all()}
        thieu = [uid for uid in ids if uid not in nguoi_theo_id]
        if thieu:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhân sự được giao việc")

    # Đầu việc vừa tạo chưa có id (id sinh lúc INSERT) ⇒ phải flush để có id
    # trước khi gắn người vào.
    if task.id is None:
        await db.flush()

    # Đọc nhóm hiện tại bằng TRUY VẤN CÓ AWAIT, không đọc `task.assignees`: đầu
    # việc vừa flush là object persistent mà quan hệ chưa nạp, chạm vào nó sẽ
    # kích lazy-load đồng bộ giữa async ⇒ MissingGreenlet (bắt được 13/10/2026
    # ở create_task).
    rows = await db.execute(select(TaskAssignee).where(TaskAssignee.task_id == task.id))
    dang_co = {a.user_id: a for a in rows.scalars().all()}
    them = [uid for uid in ids if uid not in dang_co]
    bo = [uid for uid in dang_co if uid not in ids]

    # Chỉ chặn người MỚI đã nghỉ việc. Chặn cả nhóm sẽ làm bàn giao khi nghỉ việc
    # bất khả thi: nhóm cũ còn tên người vừa nghỉ thì mọi lần đổi người đều 400.
    nghi = [nguoi_theo_id[uid].full_name for uid in them if not nguoi_theo_id[uid].is_active]
    if nghi:
        raise HTTPException(
            status_code=400,
            detail=f"{', '.join(nghi)} đã nghỉ việc — không giao việc được",
        )

    for uid in bo:
        await db.delete(dang_co[uid])
    for uid in them:
        db.add(TaskAssignee(task_id=task.id, user_id=uid))

    # Bản sao cho các truy vấn cũ (phạm vi xem dự án, hồ sơ nhân sự, Tổng quan).
    # Người đầu nhóm làm đại diện — mọi chỗ ĐẾM đã chuyển sang `task_assignees`.
    task.assigned_to = ids[0] if ids else None

    # Có người nhận = việc bắt đầu chạy ⇒ mở đồng hồ SLA. Không ghi đè mốc cũ:
    # thay người giữa đường không được làm SLA đếm lại từ đầu.
    if ids and task.started_at is None:
        task.started_at = datetime.now(timezone.utc)
    if task.started_at is not None and task.sla_due_at is None:
        task.sla_due_at = tinh_han_sla(task, await lay_cau_hinh_sla(db))

    await db.flush()

    # Thêm/xoá hàng trực tiếp nên quan hệ đã nạp trước đó vẫn giữ nhóm CŨ trong
    # bộ nhớ — nạp lại để response (`assignee_ids`) trả đúng nhóm vừa đặt. Nạp
    # cả khi không đổi gì: việc vừa tạo chưa nạp quan hệ, Pydantic đọc tới là
    # lazy-load giữa async rồi vỡ (MissingGreenlet).
    await db.refresh(task, ["assignees"])

    if thong_bao and them:
        await _thong_bao_giao_viec(db, task, [nguoi_theo_id[uid] for uid in them], actor)

    return {
        "them": [nguoi_theo_id[uid] for uid in them],
        "bo": bo,
        "nguoi_lam": [nguoi_theo_id[uid] for uid in ids],
    }


async def _thong_bao_giao_viec(
    db: AsyncSession, task: Task, nguoi_moi: list[User], actor: User | None
) -> int:
    """(1) Gắn tag / PIC công việc → thông báo trong app + Telegram cho TỪNG người."""
    # Import muộn để tránh vòng import automation ↔ task_assign.
    from app.services.automation import _notify

    # KHÔNG đọc `task.project`: route chỉ nạp task nên quan hệ này còn rỗng, chạm
    # vào là lazy-load đồng bộ giữa async ⇒ MissingGreenlet (bắt được 13/10/2026
    # khi gọi thật endpoint /assign). `db.get` lấy từ identity map nếu đã nạp sẵn
    # nên không phát sinh truy vấn thừa.
    du_an = None
    if task.project_id:
        from app.models.project import Project
        du_an = await db.get(Project, task.project_id)

    ten_du_an = f"{du_an.code} — {du_an.name}" if du_an else "dự án"
    nguoi_giao = actor.full_name if actor else "Hệ thống"
    han = task.due_date or task.sla_due_at
    dong_han = f"\nHạn: {han.strftime('%d/%m/%Y')}" if han else ""

    dem = 0
    for nguoi in nguoi_moi:
        if actor is not None and nguoi.id == actor.id:
            continue  # tự nhận việc thì khỏi tự thông báo cho mình
        if await _notify(
            db, nguoi, "task_assigned",
            f"Bạn được giao việc: {task.title}",
            f"{ten_du_an}\nNgười giao: {nguoi_giao}{dong_han}",
            link=f"/projects?id={task.project_id}",
            ref_id=task.id,
        ):
            dem += 1
    return dem


async def bat_dau_dong_ho_sla(db: AsyncSession, task: Task) -> None:
    """Việc chuyển sang «Đang làm» → mở đồng hồ SLA nếu chưa mở.

    Gọi từ endpoint đổi trạng thái. Việc có người nhận trước khi đổi trạng thái
    thì `dat_nguoi_lam` đã mở đồng hồ rồi; hàm này lo trường hợp người ta bắt tay
    vào làm mà chưa gắn tên ai.
    """
    if task.started_at is None:
        task.started_at = datetime.now(timezone.utc)
    if task.sla_due_at is None:
        task.sla_due_at = tinh_han_sla(task, await lay_cau_hinh_sla(db))
