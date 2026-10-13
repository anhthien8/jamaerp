"""Tạo dữ liệu DEMO cho Bảng điều khiển Kinh doanh (/sale-dashboard).

VÌ SAO CÓ SCRIPT NÀY
--------------------
Màn /sale-dashboard dựng 13/10/2026 đọc TOÀN BỘ số từ dữ liệu thật — không có
nhánh dữ liệu mẫu nào trong mã nguồn. Máy dev chỉ có 43 lead, và các cột mà màn
này dựa vào (`contact_status`, `source`, `region`, `ngan_sach_khoang`,
`survey_date`, `lost_reason`) gần như NULL hết, nên mở ra là 20 khối trống —
không demo được cho ai xem. Script này nạp một tập dữ liệu đủ dày và đủ "lệch
nhau" để mọi khối trên màn hình có số liệu đọc được: phễu đủ 8 bước, 4 rổ chất
lượng data, 3 nhóm có hiệu suất khác nhau, người dẫn đầu và người cần hỗ trợ,
hợp đồng rải 6 tháng cho ô "chu kỳ 6 tháng".

AN TOÀN
-------
* CHỈ chạy được trên SQLite (máy dev). Gặp Postgres là thoát ngay — dữ liệu
  bịa đặt lọt vào prod thì phòng KD sẽ báo cáo theo số ảo.
* Mặc định CHẠY KHÔ: chỉ in ra sẽ tạo/xoá những gì. Muốn ghi thật thì thêm
  `--execute`.
* Mọi bản ghi đều có DẤU: lead có `[DEMO-BANG-KD]` đầu `notes`, team/dự án/báo
  giá/hợp đồng có mã bắt đầu `DEMO-KD-`, nhân viên demo có email kết thúc
  `@demo-bang-kd.local`. `--undo` xoá đúng những bản ghi mang dấu đó, không
  chạm gì khác.
* Chạy lại khi dữ liệu demo đang còn thì script dừng và nhắc `--undo` trước —
  không nhân đôi dữ liệu.

DÙNG
----
    python scripts/seed_sale_dashboard_demo.py             # xem trước
    python scripts/seed_sale_dashboard_demo.py --execute   # nạp
    python scripts/seed_sale_dashboard_demo.py --undo --execute   # dọn sạch

Nhân viên demo KHÔNG đăng nhập được: mật khẩu là chuỗi ngẫu nhiên không lưu lại.
Họ chỉ cần tồn tại để các bảng "Hiệu suất theo nhóm" / "Top nhân viên" có dòng.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# `app.models.__init__` không import quotation/contract/supplier nên nếu chỉ
# `import app.models` thì mapper của Lead không tìm được tên 'Quotation'.
import app.models  # noqa: F401
import app.models.contract  # noqa: F401
import app.models.quotation  # noqa: F401
import app.models.supplier  # noqa: F401

from sqlalchemy import select, delete

# Lấy đúng khóa cấu hình mà màn hình đọc, không gõ lại chuỗi "sales_targets" —
# đổi tên khóa ở API mà script còn ghi khóa cũ thì mục tiêu demo tự dưng mất.
from app.api.sales_dashboard import SALES_TARGETS_KEY
from app.config import get_settings
from app.database import async_session
from app.middleware.auth import hash_password
from app.models.contract import Contract
from app.models.lead import Lead
from app.models.notification import SystemSetting
from app.models.project import Project
from app.models.quotation import Quotation
from app.models.user import Team, User
from app.services.attendance_service import VN_TZ

# ── Dấu nhận biết ────────────────────────────────────────────────────────────
DAU_LEAD = "[DEMO-BANG-KD]"
DAU_MA = "DEMO-KD-"
DAU_EMAIL = "@demo-bang-kd.local"

# Số ngẫu nhiên có hạt giống cố định: chạy lần nào cũng ra đúng bộ dữ liệu đó,
# nên ảnh chụp màn hình hôm nay và hôm sau vẫn khớp nhau.
RNG = random.Random(20261013)

# ── Hình dáng dữ liệu muốn thấy trên màn hình ────────────────────────────────
# Mỗi nhóm một "tính cách" khác nhau để bảng hiệu suất có cái mà so sánh:
# nhóm A chạy tốt, nhóm B trung bình, nhóm C yếu — và người cần hỗ trợ sẽ rơi
# vào nhóm C.
NHOM_DEMO = [
    # (mã nhóm sẵn có để dùng lại, tên nhóm tạo mới nếu chưa có)
    {"code": "JMH-VT", "ten": "Đội Văn Toàn", "chat": 1.00},
    {"code": "JMH-TP", "ten": "Đội Thái Phượng", "chat": 0.72},
    {"code": DAU_MA + "C", "ten": "Đội Demo C", "chat": 0.45},
]

# Nhân viên demo: (tên, mã nhóm, vai trò, hệ số năng lực)
NHAN_VIEN_DEMO = [
    ("Vũ Hoàng Nam", "JMH-VT", "data_entry", 1.15),
    ("Đỗ Thị Mai Anh", "JMH-VT", "data_entry", 0.95),
    ("Bùi Quốc Khánh", "JMH-TP", "data_entry", 0.85),
    ("Lý Thanh Trúc", "JMH-TP", "data_entry", 0.70),
    ("Trịnh Văn Dũng", DAU_MA + "C", "sale_leader", 0.60),
    ("Ngô Thị Bảo Ngân", DAU_MA + "C", "data_entry", 0.35),
]

NGUON = ["facebook", "zalo", "website", "referral", "tiktok", "hotline", "office_visit"]
# Trọng số nguồn: Facebook vẫn là nguồn chính của phòng KD, giới thiệu ít mà chất.
TRONG_SO_NGUON = [38, 20, 14, 8, 10, 7, 3]

# `region` quyết định rổ "khách tỉnh": tên nằm trong danh sách 34 tỉnh/thành và
# khác khu vực trọng tâm (TP. Hồ Chí Minh) thì bị tính là khách tỉnh.
NOI_THANH = ["TP. Hồ Chí Minh"]
TINH_XA = ["Đồng Nai", "Tây Ninh", "Cần Thơ", "Lâm Đồng", "Khánh Hòa", "Hà Nội"]

LY_DO_MAT = [
    "Giá cao hơn đối thủ",
    "Khách hoãn kế hoạch",
    "Chọn nhà thầu quen",
    "Không liên hệ lại được",
    "Ngân sách không đủ",
]

LOAI_HINH = ["apartment", "house", "villa", "office", "shop"]


def _now_vn() -> datetime:
    return datetime.now(VN_TZ)


def _utc(dt: datetime) -> datetime:
    """Về UTC naive — toàn bộ cột DateTime trong DB đang lưu kiểu này."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _ma(prefix: str, i: int) -> str:
    return f"{DAU_MA}{prefix}-{i:03d}"


# ── Sinh lead ────────────────────────────────────────────────────────────────
# `do_sau_pheu` ở app/api/sales_dashboard.py suy ra bước xa nhất của lead từ
# stage + contact_status + last_contacted_at + survey_date. Bảng dưới đây là
# ảnh phản chiếu của hàm đó: mỗi dòng là một "kiểu lead" tạo ra đúng một độ sâu,
# nên phễu trên màn hình thu hẹp đều từ 100% xuống ~2% như phễu thật.
#
#   0 data thô · 1 đã gọi mà chưa kết nối · 2 kết nối được · 3 có nhu cầu
#   4 đã đặt lịch khảo sát · 5 đã khảo sát/báo giá · 6 đang đàm phán · 7 ký HĐ
KIEU_LEAD = [
    # (tỉ lệ, stage, contact_status, co_lien_he, co_khao_sat, do_sau_dich)
    (0.17, "new", None, False, False, 0),
    (0.12, "new", "unreachable", True, False, 1),
    (0.15, "new", "reachable", True, False, 2),
    (0.12, "interested", "reachable", True, False, 3),
    # Đã khảo sát nhưng CHƯA báo giá: `do_sau_pheu` cho bước "đã báo giá" cho
    # mọi lead từ stage survey_scheduled trở lên, nên thiếu kiểu này thì hai
    # bước «Đã khảo sát» và «Đã gửi báo giá» của phễu luôn bằng nhau đúng 100%.
    (0.05, "interested", "reachable", True, True, 4),
    (0.13, "survey_scheduled", "reachable", True, True, 5),
    (0.09, "potential", "reachable", True, True, 6),
    (0.09, "signed_design", "reachable", True, True, 7),
    (0.05, "lost", "no_need", True, False, 0),
    (0.03, "lost", "wrong_number", False, False, 0),
]


def chon_kieu() -> tuple:
    r = RNG.random()
    moc = 0.0
    for kieu in KIEU_LEAD:
        moc += kieu[0]
        if r <= moc:
            return kieu
    return KIEU_LEAD[0]


def sinh_lead(i: int, nguoi: dict, nhom_id: str, ngay_tao: datetime) -> Lead:
    """Một lead demo. `nguoi['chat']` kéo/đẩy chất lượng để các nhóm lệch nhau."""
    _, stage, contact, co_lien_he, co_khao_sat, _ = chon_kieu()
    chat = nguoi["chat"]

    # Người yếu thì nhiều lead tụt lại ở bước đầu — đây là chỗ tạo ra sự khác
    # biệt giữa "top nhân viên" và "cần hỗ trợ". Lead ĐÃ KÝ thì miễn: một hợp
    # đồng đã ký không thể bị "tụt" về bước tiếp nhận.
    if stage != "signed_design" and RNG.random() > chat and stage not in ("new", "lost"):
        stage, contact, co_khao_sat = "new", "reachable", False

    la_tinh = RNG.random() < (0.11 if chat >= 0.7 else 0.20)
    region = RNG.choice(TINH_XA) if la_tinh else RNG.choice(NOI_THANH)

    ngan_sach = RNG.choices(
        ["duoi_200", "tu_200_500", "tren_500", None],
        weights=[12 if chat >= 0.7 else 22, 46, 30, 12],
    )[0]

    # Lead đã ký buộc phải nằm trong rổ "data đạt tiêu chuẩn": `phan_loai_data`
    # xếp khách tỉnh / ngân sách dưới 200tr ra khỏi rổ đó, mà mọi khối hiệu suất
    # trên màn chỉ đếm data đạt chuẩn — để nguyên thì bước "Ký hợp đồng" của
    # phễu rỗng dù dữ liệu có lead ký.
    if stage == "signed_design":
        region, la_tinh = NOI_THANH[0], False
        if ngan_sach == "duoi_200":
            ngan_sach = "tu_200_500"

    # Data thô chưa ai gọi: với người làm tốt thì đó là data VỪA về (hôm nay,
    # hôm qua), với người yếu là data để quên. Khối «Nhân viên cần hỗ trợ» gắn
    # cờ "chưa liên hệ sau 3 ngày" cho bất kỳ ai có >0 lead như vậy, nên nếu
    # không phân biệt theo người thì cả 6/6 nhân viên đều bị gắn cờ và bảng mất
    # hẳn ý nghĩa phân loại.
    if not co_lien_he and stage == "new" and chat >= 0.9:
        ngay_tao = max(ngay_tao, _now_vn() - timedelta(days=2))

    lien_he_luc = None
    if co_lien_he and RNG.random() < min(0.97, chat + 0.25):
        # Người follow-up chậm để lại khoảng cách lớn giữa tạo và liên hệ —
        # chính là cái ô "Follow-up chậm" trong khối Nhân viên cần hỗ trợ đọc.
        tre = RNG.randint(0, 2) if chat >= 0.7 else RNG.randint(4, 12)
        lien_he_luc = ngay_tao + timedelta(days=tre, hours=RNG.randint(1, 8))
        if lien_he_luc > _now_vn():
            lien_he_luc = _now_vn() - timedelta(hours=RNG.randint(1, 20))

    khao_sat = None
    if co_khao_sat:
        khao_sat = (ngay_tao + timedelta(days=RNG.randint(3, 15))).date()

    gia_tri = {
        "duoi_200": RNG.randint(90, 195),
        "tu_200_500": RNG.randint(210, 490),
        "tren_500": RNG.randint(520, 1800),
        None: RNG.randint(150, 700),
    }[ngan_sach] * 1_000_000

    return Lead(
        id=str(uuid.uuid4()),
        name=f"KH Demo {i:03d}",
        phone=f"09{RNG.randint(10_000_000, 99_999_999)}",
        source=RNG.choices(NGUON, weights=TRONG_SO_NGUON)[0],
        property_type=RNG.choice(LOAI_HINH),
        area_sqm=RNG.randint(45, 320),
        estimated_budget=gia_tri,
        contact_status=contact,
        survey_date=khao_sat,
        region=region,
        ngan_sach_khoang=ngan_sach,
        stage=stage,
        priority=RNG.choice(["low", "normal", "high"]),
        lost_reason=RNG.choice(LY_DO_MAT) if stage == "lost" else None,
        assigned_to=nguoi["id"],
        team_id=nhom_id,
        notes=f"{DAU_LEAD} dữ liệu minh hoạ Bảng điều khiển Kinh doanh",
        deal_value=gia_tri if stage == "signed_design" else None,
        created_at=_utc(ngay_tao),
        updated_at=_utc(ngay_tao),
        last_contacted_at=_utc(lien_he_luc) if lien_he_luc else None,
    )


# ── Nạp ──────────────────────────────────────────────────────────────────────
async def dem_dau_vet(db) -> dict[str, int]:
    """Đếm bản ghi demo đang tồn tại — dùng cho cả kiểm tra lẫn --undo."""
    async def dem(stmt) -> int:
        return len((await db.execute(stmt)).scalars().all())

    return {
        "lead": await dem(select(Lead.id).where(Lead.notes.like(f"{DAU_LEAD}%"))),
        "contract": await dem(select(Contract.id).where(Contract.code.like(f"{DAU_MA}%"))),
        "quotation": await dem(select(Quotation.id).where(Quotation.code.like(f"{DAU_MA}%"))),
        "project": await dem(select(Project.id).where(Project.code.like(f"{DAU_MA}%"))),
        "user": await dem(select(User.id).where(User.email.like(f"%{DAU_EMAIL}"))),
        "team": await dem(select(Team.id).where(Team.code.like(f"{DAU_MA}%"))),
    }


async def go_demo(db, chay_that: bool) -> None:
    truoc = await dem_dau_vet(db)
    print("Dữ liệu demo đang có:", truoc)
    if not any(truoc.values()):
        print("→ Không có gì để gỡ.")
        return
    if not chay_that:
        print("→ CHẠY KHÔ: thêm --execute để xoá thật.")
        return

    # Thứ tự xoá đi từ bảng con lên bảng cha để không vướng khoá ngoại.
    nv_ids = (await db.execute(
        select(User.id).where(User.email.like(f"%{DAU_EMAIL}"))
    )).scalars().all()

    await db.execute(delete(Contract).where(Contract.code.like(f"{DAU_MA}%")))
    await db.execute(delete(Quotation).where(Quotation.code.like(f"{DAU_MA}%")))
    await db.execute(delete(Project).where(Project.code.like(f"{DAU_MA}%")))
    await db.execute(delete(Lead).where(Lead.notes.like(f"{DAU_LEAD}%")))
    if nv_ids:
        # Nhóm demo trỏ leader_id vào nhân viên demo — nhả ra trước khi xoá người.
        await db.execute(
            Team.__table__.update().where(Team.leader_id.in_(nv_ids)).values(leader_id=None)
        )
        await db.execute(delete(User).where(User.id.in_(nv_ids)))
    await db.execute(delete(Team).where(Team.code.like(f"{DAU_MA}%")))

    # Bản mục tiêu: CHỈ xoá nếu chính script này đặt (có cờ `_demo`). Nếu chủ
    # dự án đã tự sửa mục tiêu qua màn hình thì cờ mất và ta để nguyên — xoá
    # mục tiêu thật của người ta là mất dữ liệu, không phải dọn demo.
    mt = await db.get(SystemSetting, SALES_TARGETS_KEY)
    if mt and mt.value:
        try:
            la_demo = json.loads(mt.value).get("_demo") is True
        except (ValueError, TypeError):
            la_demo = False
        if la_demo:
            await db.delete(mt)
            print("  · đã xoá bản mục tiêu demo (system_settings.sales_targets)")
        else:
            print("  · GIỮ bản mục tiêu hiện tại — không mang dấu demo")

    await db.commit()
    print("Sau khi gỡ:", await dem_dau_vet(db))


async def nap_demo(db, chay_that: bool) -> None:
    dang_co = await dem_dau_vet(db)
    if any(dang_co.values()):
        print("DỪNG: dữ liệu demo đã tồn tại:", dang_co)
        print("→ Chạy `--undo --execute` trước rồi nạp lại.")
        return

    now = _now_vn()
    ke_hoach: list[str] = []

    # (1) Nhóm — dùng lại 2 nhóm KD sẵn có, chỉ tạo thêm nhóm C.
    nhom_id: dict[str, str] = {}
    them_nhom: list[Team] = []
    for n in NHOM_DEMO:
        co = (await db.execute(select(Team).where(Team.code == n["code"]))).scalar_one_or_none()
        if co:
            nhom_id[n["code"]] = co.id
            ke_hoach.append(f"dùng lại nhóm sẵn có: {co.name} ({co.code})")
        else:
            t = Team(id=str(uuid.uuid4()), name=n["ten"], code=n["code"],
                     department="SALES", created_at=_utc(now))
            nhom_id[n["code"]] = t.id
            them_nhom.append(t)
            ke_hoach.append(f"TẠO nhóm: {n['ten']} ({n['code']})")

    # (2) Nhân viên demo
    them_nguoi: list[User] = []
    nguoi_demo: list[dict] = []
    for idx, (ten, ma_nhom, vai, chat) in enumerate(NHAN_VIEN_DEMO, start=1):
        uid = str(uuid.uuid4())
        email = f"demo.kd{idx}{DAU_EMAIL}"
        them_nguoi.append(User(
            id=uid, full_name=ten, email=email,
            phone=f"09{RNG.randint(10_000_000, 99_999_999)}",
            # Mật khẩu ngẫu nhiên KHÔNG lưu lại ⇒ tài khoản demo không đăng
            # nhập được, dù vẫn is_active để lọt vào mẫu số chia mục tiêu.
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role=vai, department="SALES", team_id=nhom_id[ma_nhom],
            is_active=True, created_at=_utc(now), updated_at=_utc(now),
        ))
        nguoi_demo.append({"id": uid, "ten": ten, "nhom": ma_nhom, "chat": chat})
        ke_hoach.append(f"TẠO nhân viên KD: {ten} · {ma_nhom} · {vai}")

    # Nhóm C mới chưa có trưởng nhóm — gắn người sale_leader của chính nó.
    for t in them_nhom:
        ldr = next((n for n, (_, mn, v, _c) in zip(nguoi_demo, NHAN_VIEN_DEMO)
                    if mn == t.code and v == "sale_leader"), None)
        if ldr:
            t.leader_id = ldr["id"]

    # (3) Lead — rải 90 ngày gần nhất để bộ lọc kỳ (tháng này / tháng trước /
    # quý) đều có số, và tháng này dày hơn cho thẻ KPI nhìn ra "đang chạy".
    leads: list[Lead] = []
    i = 0
    for nguoi in nguoi_demo:
        so_lead = int(RNG.randint(26, 34) * (0.6 + nguoi["chat"] * 0.5))
        for _ in range(so_lead):
            i += 1
            # 55% lead trong tháng này, phần còn lại rải 2 tháng trước đó.
            if RNG.random() < 0.55:
                ngay = now.replace(day=1) + timedelta(
                    days=RNG.randint(0, max(now.day - 1, 0)),
                    hours=RNG.randint(8, 18),
                )
            else:
                ngay = now - timedelta(days=RNG.randint(now.day, 95),
                                       hours=RNG.randint(0, 10))
            leads.append(sinh_lead(i, nguoi, nhom_id[nguoi["nhom"]], ngay))
    ke_hoach.append(f"TẠO {len(leads)} lead (3 tháng gần nhất)")

    # Số hợp đồng mỗi tháng, tính từ tháng này lùi dần. Mức này cho doanh số
    # tháng xấp xỉ mục tiêu 14,4 tỷ nên biểu đồ cột chạm được đường mục tiêu —
    # chứ không phải mấy cột tí xíu dưới chân một đường kẻ đỏ.
    HD_MOI_THANG = [9, 10, 8, 9, 11, 8, 9, 7, 8, 6, 6, 5]
    lich_hd: list[tuple[datetime, int, int]] = []
    suc_chua: dict[tuple[int, int], int] = {}
    for lui_thang in range(12):
        moc = now.replace(day=15) - timedelta(days=30 * lui_thang)
        so_hd = HD_MOI_THANG[lui_thang]
        if lui_thang == 0:
            # Tháng này mới chạy được `now.day` ngày: nhồi đủ chỉ tiêu cả tháng
            # vào mấy ngày đầu thì thẻ KPI báo 194% mục tiêu — nhìn là biết số
            # bịa. Cắt theo phần tháng đã trôi qua.
            so_hd = max(1, round(so_hd * now.day / 30))
        lich_hd.append((moc, lui_thang, so_hd))
        suc_chua[(moc.year, moc.month)] = so_hd

    # Ai đã chốt được lead trong tháng nào — dùng để gắn hợp đồng cho đúng người.
    # Màn hình lấy cột «Ký HĐ» từ LEAD ở bước signed_design, còn cột «Doanh số»
    # từ HỢP ĐỒNG (qua Project.sales_id). Rải hai thứ độc lập là ra cảnh vô lý
    # «3 ký HĐ · 0 đ doanh số» ngay trên bảng hiệu suất nhóm.
    #
    # Mỗi lead đã ký phải có một hợp đồng đứng tên đúng người đó. Tháng nào sinh
    # nhiều lead ký hơn số hợp đồng của tháng thì hạ phần dư về bước "tiềm năng"
    # (vẫn có báo giá, chỉ chưa ký) — hạ lead rẻ hơn là đẻ thêm hợp đồng, vì mỗi
    # hợp đồng cộng cả tỷ vào thẻ KPI doanh thu và đẩy nó lên 160% tiến độ.
    chot_theo_thang: dict[tuple[int, int], list[str]] = {}
    for l in leads:
        if l.stage != "signed_design":
            continue
        moc_l = l.created_at.replace(tzinfo=timezone.utc).astimezone(VN_TZ)
        kho = chot_theo_thang.setdefault((moc_l.year, moc_l.month), [])
        if len(kho) >= suc_chua.get((moc_l.year, moc_l.month), 0):
            l.stage, l.deal_value = "potential", None
            continue
        kho.append(l.assigned_to)

    # (4) Dự án + báo giá + hợp đồng — nguồn duy nhất của doanh thu trên màn.
    # Rải 12 tháng, không phải 6: ô "Tổng doanh thu chu kỳ" so 6 tháng gần nhất
    # với 6 tháng TRƯỚC ĐÓ, thiếu nửa sau thì delta hiện "chưa có số".
    #
    # Ngày ký rải khắp tháng (1–28). Nếu chỉ rải nửa đầu tháng thì kỳ so sánh
    # của bộ lọc "tháng này" (13 ngày cuối tháng trước) không có hợp đồng nào,
    # và cả 3 thẻ KPI doanh thu đều mất phần "so với kỳ trước".
    du_an: list[Project] = []
    bao_gia: list[Quotation] = []
    hop_dong: list[Contract] = []
    stt = 0
    for moc, lui_thang, so_hd in lich_hd:
        for _ in range(so_hd):
            stt += 1
            # Ưu tiên gán hợp đồng cho người ĐÃ CÓ lead chốt trong tháng đó;
            # hết người thì mới bốc ngẫu nhiên (các tháng cũ không có lead).
            kho_chot = chot_theo_thang.get((moc.year, moc.month)) or []
            nguoi_id = kho_chot.pop() if kho_chot else None
            nguoi = (next(n for n in nguoi_demo if n["id"] == nguoi_id) if nguoi_id
                     else RNG.choices(nguoi_demo,
                                      weights=[n["chat"] for n in nguoi_demo])[0])
            la_thiet_ke = RNG.random() < 0.6
            gia_tri = (RNG.randint(420, 980) if la_thiet_ke
                       else RNG.randint(1400, 3400)) * 1_000_000
            # Không ký trong tương lai: tháng này mới tới ngày `now.day`, mà
            # biểu đồ 6 tháng gộp theo THÁNG còn thẻ KPI cắt tới HÔM NAY —
            # để lọt hợp đồng ngày mai thì hai khối đó chỏi nhau.
            ngay_het_thang = now.day if lui_thang == 0 else 28
            ngay_ky = moc.replace(day=RNG.randint(1, max(ngay_het_thang, 1))).date()

            p = Project(
                id=str(uuid.uuid4()), code=_ma("DA", stt),
                name=f"Dự án demo {stt:03d}",
                client_name=f"KH HĐ Demo {stt:03d}",
                project_type="design_build" if la_thiet_ke else "construction_only",
                status="active", stage="design" if la_thiet_ke else "construction",
                total_value=gia_tri, sales_id=nguoi["id"],
                created_at=_utc(moc), updated_at=_utc(moc),
            )
            q = Quotation(
                id=str(uuid.uuid4()), code=_ma("BG", stt), project_id=p.id,
                type="design" if la_thiet_ke else "construction",
                title=f"Báo giá demo {stt:03d}", status="approved",
                total_amount=gia_tri, created_at=_utc(moc), updated_at=_utc(moc),
            )
            hop_dong.append(Contract(
                id=str(uuid.uuid4()), code=_ma("HD", stt), project_id=p.id,
                quotation_id=q.id, title=f"Hợp đồng demo {stt:03d}",
                status="signed", total_value=gia_tri, signed_date=ngay_ky,
                notes=f"{DAU_LEAD} hợp đồng minh hoạ",
                created_at=_utc(moc), updated_at=_utc(moc),
            ))
            du_an.append(p)
            bao_gia.append(q)
    ke_hoach.append(f"TẠO {len(du_an)} dự án + {len(bao_gia)} báo giá "
                    f"+ {len(hop_dong)} hợp đồng đã ký (12 tháng)")

    # (5) Mục tiêu từng nhóm — không có thì cột «% Mục tiêu» của bảng hiệu suất
    # nhóm hiện "chưa đặt mục tiêu" ở cả 3 dòng. Chia đều mục tiêu phòng
    # (14,4 tỷ/tháng) cho 3 nhóm. CHỈ ghi khi chưa ai đặt mục tiêu bao giờ —
    # có bản mục tiêu rồi thì để nguyên, đó có thể là số thật của phòng KD.
    mt_cu = await db.get(SystemSetting, SALES_TARGETS_KEY)
    ghi_muc_tieu = mt_cu is None or not mt_cu.value
    if ghi_muc_tieu:
        ke_hoach.append("TẠO mục tiêu theo nhóm (3 nhóm × 4,8 tỷ/tháng)")
    else:
        ke_hoach.append("GIỮ bản mục tiêu đang có — không ghi đè")

    print("\n".join(f"  · {d}" for d in ke_hoach))
    if not chay_that:
        print("\n→ CHẠY KHÔ: chưa ghi gì. Thêm --execute để nạp thật.")
        return

    if ghi_muc_tieu:
        chia = round(14_400_000_000 / len(NHOM_DEMO))
        db.add(SystemSetting(
            key=SALES_TARGETS_KEY,
            value=json.dumps({
                # `_demo` là dấu để `--undo` biết bản này do script đặt.
                "_demo": True,
                "theo_nhom": {
                    nhom_id[n["code"]]: {"doanh_thu_thang": chia} for n in NHOM_DEMO
                },
            }, ensure_ascii=False),
            updated_at=_utc(now),
        ))

    db.add_all(them_nhom)
    await db.flush()
    db.add_all(them_nguoi)
    await db.flush()
    db.add_all(leads)
    db.add_all(du_an)
    await db.flush()
    db.add_all(bao_gia)
    await db.flush()
    db.add_all(hop_dong)
    await db.commit()
    print("\nĐã nạp xong:", await dem_dau_vet(db))
    print("Mở /sale-dashboard bằng tài khoản admin để xem.")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="ghi thật (mặc định chạy khô)")
    ap.add_argument("--undo", action="store_true", help="xoá toàn bộ dữ liệu demo")
    args = ap.parse_args()

    st = get_settings()
    if not st.is_sqlite:
        print("DỪNG: script này chỉ chạy trên SQLite (máy dev).")
        print("DATABASE_URL hiện tại không phải SQLite — không nạp dữ liệu bịa vào đó.")
        return 2

    async with async_session() as db:
        try:
            if args.undo:
                await go_demo(db, args.execute)
            else:
                await nap_demo(db, args.execute)
        finally:
            await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
