"""RBAC helpers — role-based access control."""

from fastapi import HTTPException
from app.models.user import User
from app.models.lead import Lead

# 6 vai trò hệ thống — mọi role khác là vai trò tùy chỉnh (system_settings.custom_roles)
SYSTEM_ROLES = {"admin", "leader", "data_entry", "accountant", "executive", "supervisor"}

# Vai trò tùy chỉnh "Trưởng nhóm Kinh doanh" — seed idempotent trong seed.py nên
# role_key này là hằng số code-owned. Cùng bộ phận SALES nhưng KHÁC điều phối:
# trưởng nhóm bị giới hạn trong nhóm mình.
SALE_LEADER_ROLE = "sale_leader"


def is_team_lead(user: User) -> bool:
    """Trưởng nhóm KD — vai trò hệ thống `leader` hoặc vai trò tùy chỉnh `sale_leader`.

    Luồng data (14/08/2026): Admin CSKH chia data cho trưởng nhóm → trưởng nhóm
    chia cho sale trong nhóm. Trưởng nhóm CHỈ thấy & giao data trong nhóm mình.
    """
    return user.role in ("leader", SALE_LEADER_ROLE)


def is_sales_coordinator(user: User) -> bool:
    """Vai trò tùy chỉnh thuộc bộ phận Kinh doanh (vd: Admin CSKH) — TRỪ sale_leader.

    Đây là nhóm nhập lead từ marketing rồi phân chia cho trưởng nhóm/nhân viên KD,
    nên được đối xử như điều phối viên: thấy toàn bộ lead, đủ SĐT, được gắn/đổi
    người phụ trách bất kỳ (feedback team KD 12/08/2026). `sale_leader` cũng là
    vai trò tùy chỉnh + SALES nhưng là TRƯỞNG NHÓM — phạm vi nhóm, không phải điều phối.
    """
    return (
        user.role not in SYSTEM_ROLES
        and user.role != SALE_LEADER_ROLE
        and (user.department or "").upper() == "SALES"
    )


def can_assign_leads(user: User) -> bool:
    """Ai được phân chia data lead: admin, trưởng nhóm, hoặc điều phối KD (CSKH)."""
    return user.role == "admin" or is_team_lead(user) or is_sales_coordinator(user)


# ── Ai được TIẾP CẬN lead (chốt 22/09/2026) ──────────────────────────────────
# Nguyên tắc chủ dự án: «trừ bộ phận kinh doanh và nhân sự thuộc ban giám đốc,
# không ai được quyền thấy lead». Đây là chặn CỨNG theo bộ phận, đứng TRÊN ma
# trận 23 ô chức năng — trước đây vai `operation_leader` (Trưởng phòng Giám sát)
# bị bật sẵn «Xem Leads» trong system_settings, tích một ô là lọt cả module.
BO_PHAN_XEM_LEAD: set[str] = {"SALES", "EXEC"}


def duoc_xem_lead(user: User) -> bool:
    """Bộ phận này có được tiếp cận module Lead không (chặn cứng, không qua ma trận)."""
    if user.role in ("admin", "executive"):
        return True
    return (user.department or "").upper() in BO_PHAN_XEM_LEAD


# ── Phạm vi xem DỰ ÁN theo bộ phận (05/09/2026) ─────────────────────────────
# Trước đây list_projects KHÔNG lọc gì: mọi tài khoản đăng nhập thấy toàn bộ
# 113 dự án. Nay soi gương luồng lead của Kinh doanh: nhân viên thấy dự án mình
# phụ trách, trưởng phòng thấy toàn bộ dự án của bộ phận mình.

# Cột PIC trên bảng projects ứng với từng bộ phận.
PIC_THEO_PHONG_BAN: dict[str, str] = {
    "OPS": "pm_id",              # Giám sát / PM
    "DESIGN": "designer_id",     # Thiết kế
    "SALES": "sales_id",         # Kinh doanh
    "PURCHASING": "purchasing_id",  # Dự toán – Thu mua
}

# Vai trò TRƯỞNG PHÒNG thật sự — chốt với chủ dự án 05/09 sau khi đối chiếu cơ
# cấu thật trên prod. Cố ý KHÔNG gồm `design_leader` (5 người) và `2d_leader`:
# theo sơ đồ trong JD Thiết kế họ là CHỦ TRÌ, không phải trưởng phòng.
#
# 22/09: bỏ `sale_leader` khỏi SALES. Chốt lại 3 tầng — trưởng phòng xem cả bộ
# phận, trưởng nhóm xem nhóm mình, nhân viên xem của mình. `sale_leader` là
# TRƯỞNG NHÓM nên tụt xuống tầng giữa (trước đây bị xếp ngang trưởng phòng).
VAI_TRO_TRUONG_PHONG: dict[str, set[str]] = {
    "DESIGN": {"leader"},
    "OPS": {"operation_leader"},
    "PURCHASING": {"dutoan_thumua_leader"},
    "SALES": {"leader"},
}

# Vai trò TRƯỞNG NHÓM — tầng giữa. Chủ trì thiết kế là vai tương đương trưởng
# nhóm KD (chốt 22/09), nên xếp vào đây.
VAI_TRO_TRUONG_NHOM: dict[str, set[str]] = {
    "SALES": {SALE_LEADER_ROLE},
    "DESIGN": {"design_leader", "2d_leader"},
}

# Bộ phận mà `teams` thực sự là NHÓM CON, không phải cả phòng.
# Đo prod 22/09: ngoài KD, mỗi bộ phận chỉ có đúng 1 team trùng với cả phòng —
# «Phòng Thiết Kế» 16 người (gồm cả trưởng phòng + 5 chủ trì), «Giám sát» 8,
# «Phòng Báo Giá» 9. Lọc theo team_id ở các phòng đó = mở bằng cả phòng, tức là
# chủ trì được quyền như trưởng phòng. Nên với phòng KHÔNG có nhóm con thật,
# tầng trưởng nhóm tụt về «của mình» (chốt 22/09: chủ trì lọc theo dự án mình
# phụ trách). Khi Thiết kế chia nhóm con thật thì thêm "DESIGN" vào đây là xong.
PHONG_CO_NHOM_THAT: set[str] = {"SALES"}


def la_truong_phong(user: User) -> bool:
    """Trưởng phòng của CHÍNH bộ phận mình (vai trò `leader` ở phòng khác không tính)."""
    dept = (user.department or "").upper()
    return user.role in VAI_TRO_TRUONG_PHONG.get(dept, set())


def la_truong_nhom(user: User) -> bool:
    """Trưởng nhóm / chủ trì của CHÍNH bộ phận mình."""
    dept = (user.department or "").upper()
    return user.role in VAI_TRO_TRUONG_NHOM.get(dept, set())


def pham_vi_du_lieu(user: User) -> str:
    """'tat_ca' | 'phong_ban' | 'nhom' | 'ca_nhan' — một thước đo dùng cho cả
    lead và dự án, để hai module không trôi lệch nhau nữa.

    Kiêm nhiệm thì lấy tầng CAO NHẤT: vừa trưởng phòng vừa trưởng nhóm ⇒ xem
    cả bộ phận (yêu cầu chủ dự án 22/09).
    """
    # Kế toán giữ toàn quyền xem: cần đối chiếu công nợ/thanh toán/P&L mọi dự án
    # (chốt 05/09). Executive xem toàn bộ để nắm tình hình.
    if user.role in ("admin", "executive", "accountant"):
        return "tat_ca"
    if la_truong_phong(user):
        return "phong_ban"
    if la_truong_nhom(user):
        dept = (user.department or "").upper()
        # Nhóm chỉ có nghĩa khi phòng đó chia nhóm con thật (xem PHONG_CO_NHOM_THAT)
        if dept in PHONG_CO_NHOM_THAT and user.team_id is not None:
            return "nhom"
    return "ca_nhan"


def pham_vi_du_an(user: User) -> str:
    """Phạm vi xem DỰ ÁN. Giữ tên cũ cho các chỗ đang gọi."""
    return pham_vi_du_lieu(user)


def la_pic_du_an(user: User, project) -> bool:
    """Người này có phải PIC của dự án không (bất kể bộ phận nào)."""
    return user.id in {
        project.pm_id, project.designer_id, project.sales_id,
        getattr(project, "purchasing_id", None),
    }


def can_approve_quotation(user: User) -> bool:
    """Ai được DUYỆT báo giá — chốt với chủ dự án 29/08/2026: Giám đốc + Trưởng
    nhóm/phòng + Giám sát.

    Tách quyền SOẠN với quyền DUYỆT: sale vẫn tạo/sửa báo giá bình thường nhưng
    không tự duyệt bản của chính mình (trước QC 29/08 mọi tài khoản đăng nhập đều
    duyệt được — backend không kiểm, nút trên FE cũng không ẩn).
    """
    return user.role == "admin" or is_team_lead(user) or user.role == "supervisor"


def can_confirm_payment(user: User) -> bool:
    """Ai được đánh dấu ĐÃ THU TIỀN một đợt thanh toán hợp đồng — chốt 29/08/2026:
    Kế toán + Giám đốc + Trưởng nhóm/phòng.

    Ghi nhận tiền về là việc kế toán (tài liệu công ty: «Kế toán nhận thông báo HĐ
    mới → kiểm tra → tạo phiếu thu»); thêm trưởng nhóm để không tắc khi kế toán nghỉ.
    Sale vẫn XEM được trạng thái thanh toán, chỉ không tự tích.
    """
    return user.role in ("admin", "accountant") or is_team_lead(user)


def can_write_cskh_note(user: User) -> bool:
    """Ai được ghi lognote CSKH (đánh giá chất lượng chăm sóc của team KD).

    CHỈ điều phối KD (Admin CSKH) + admin — chốt 27/08/2026. Cố tình KHÔNG cho
    trưởng nhóm và sale: đây là đánh giá VỀ họ, tự viết được thì mất ý nghĩa
    kiểm soát. Ai xem được lead vẫn ĐỌC được ghi chú (minh bạch để sale tự sửa).
    """
    return user.role == "admin" or is_sales_coordinator(user)


def can_assign_lead_to(user: User, target: User) -> bool:
    """Được giao lead cho `target` không?

    Admin/điều phối KD: bất kỳ ai đang làm việc. Trưởng phòng KD: bất kỳ ai
    CÙNG BỘ PHẬN (22/09 — trước đây trưởng phòng bị bó trong nhóm mình y như
    trưởng nhóm). Trưởng nhóm: chính mình hoặc người CÙNG NHÓM — chưa được xếp
    nhóm thì chỉ giao được cho chính mình.
    """
    if not target.is_active:
        return False
    if user.role == "admin" or is_sales_coordinator(user):
        return True
    if la_truong_phong(user):
        return _cung_bo_phan(user, target)
    if is_team_lead(user):
        return target.id == user.id or (
            user.team_id is not None and target.team_id == user.team_id
        )
    return False


def _cung_bo_phan(a: User, b: User) -> bool:
    """Hai người cùng một bộ phận. Bộ phận trống KHÔNG khớp với bộ phận trống —
    nếu không, hai tài khoản chưa gán phòng sẽ thấy dữ liệu của nhau."""
    dept = (a.department or "").upper()
    return dept != "" and dept == (b.department or "").upper()


async def _phu_trach_cung_bo_phan(db, user: User, uid: str | None) -> bool:
    """Người phụ trách lead/dự án này có cùng bộ phận với `user` không."""
    if uid is None:
        return False
    nguoi = await db.get(User, uid)
    return nguoi is not None and _cung_bo_phan(user, nguoi)


# Ba hàm dưới đây là ASYNC vì tầng «phòng ban» phải tra bộ phận của người phụ
# trách. Cố ý KHÔNG để bản sync song song: bài học 05/09 — guard chi tiết lệch
# với bộ lọc danh sách thì sinh ra lead/dự án «hiện trong danh sách mà mở ra 403».


async def duoc_xem_lead_nay(db, user: User, lead: Lead) -> bool:
    """Xem được lead này không — 4 tầng, khớp đúng với bộ lọc danh sách."""
    if not duoc_xem_lead(user):
        return False
    if is_sales_coordinator(user):
        return True
    # Lead giao cho chính mình thì luôn xem được — vế này bắt buộc cho trưởng
    # nhóm/trưởng phòng chưa được xếp đội (prod từng có 2 sale_leader teamless:
    # thấy trong danh sách nhưng mở ra 403 — review đối kháng 14/08).
    if lead.assigned_to == user.id:
        return True
    pham_vi = pham_vi_du_lieu(user)
    if pham_vi == "tat_ca":
        return True
    if pham_vi == "phong_ban":
        return await _phu_trach_cung_bo_phan(db, user, lead.assigned_to)
    if pham_vi == "nhom":
        return user.team_id is not None and lead.team_id == user.team_id
    return False


async def duoc_sua_lead_nay(db, user: User, lead: Lead) -> bool:
    """Sửa được lead này không — cùng phạm vi với quyền xem."""
    return await duoc_xem_lead_nay(db, user, lead)


async def duoc_doi_phan_cong_lead(db, user: User, lead: Lead) -> bool:
    """Được đổi người phụ trách của lead này không?

    Admin/điều phối KD: mọi lead. Trưởng phòng: mọi lead của bộ phận mình.
    Trưởng nhóm: chỉ lead đã thuộc nhóm mình (CSKH giao về nhóm trước, trưởng
    nhóm chia tiếp trong nhóm).
    """
    if user.role == "admin" or is_sales_coordinator(user):
        return True
    if la_truong_phong(user):
        return (
            lead.assigned_to == user.id
            or await _phu_trach_cung_bo_phan(db, user, lead.assigned_to)
        )
    if is_team_lead(user):
        return user.team_id is not None and lead.team_id == user.team_id
    return False


def require_roles(*roles):
    """Factory for role checking."""
    def check(user: User):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Cần quyền {', '.join(roles)} để thực hiện thao tác này",
            )
        return True
    return check
