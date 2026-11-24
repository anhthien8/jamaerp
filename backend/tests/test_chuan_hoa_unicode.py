"""Chuẩn hoá Unicode NFC (21/11/2026): ghi (listener), tìm kiếm (middleware query string),
so khớp chữ người dùng gửi trong body/tệp/path (D3), dọn dữ liệu cũ (migration a28_2026b007
+ quét lại một lần sau deploy).

Chữ tiếng Việt có 2 dạng trông y hệt: NFC (dựng sẵn) và NFD (tổ hợp — bộ gõ «Unicode tổ
hợp»). Máy so chữ coi là khác nhau → tìm «Trịnh» không ra người lưu dạng tổ hợp.

CỐ Ý không import `app.chuan_hoa_unicode` ở file này: listener phải tự có mặt nhờ
`app.database`. Đường worker/script (chỉ import models, không qua app.main) kiểm bằng
subprocess riêng — `test_listener_co_san_khi_chi_import_models_va_worker`.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unicodedata
from urllib.parse import parse_qsl, quote, quote_plus

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from app.middleware.auth import hash_password
from app.middleware.chuan_hoa_query import ChuanHoaQueryNFC, chuan_hoa_query
from app.models.contract import Contract
from app.models.inventory import Material
from app.models.lead import Lead
from app.models.notification import Notification, SystemSetting
from app.models.pricing import PriceItem
from app.models.project import Project, TaskActivity
from app.models.supplier import Supplier, SupplierQuote
from app.models.user import Team, User
from app.models.vat_tu import DongPhieuVatTu, GiaNhomVatTu
from tests.conftest import _uid, auth_header

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def NFC(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def NFD(s: str) -> str:
    return unicodedata.normalize("NFD", s)


TEN = NFC("Trịnh Đình Giao")


def test_hai_dang_khac_byte():
    """Tiền đề của cả file: dạng tổ hợp KHÁC byte dạng dựng sẵn."""
    assert NFD(TEN) != TEN and NFC(NFD(TEN)) == TEN


# Chuỗi JSON hợp lệ mà NFC làm hỏng: dấu ngã đứng trơ sau xuống dòng → mã thoát «\n» + dấu
# ngã bị ghép thành «\ñ» (cũng vậy với \t \r \b \f và chữ số hex cuối của \uXXXX)
JSON_NFC_HONG = json.dumps({"ghi_chu": "dòng 1\ñdòng 2"}, ensure_ascii=False)


def _la_json(s: str) -> bool:
    try:
        json.loads(s)
    except ValueError:
        return False
    return True


def test_tien_de_json_nfc_hong():
    assert _la_json(JSON_NFC_HONG) and not _la_json(NFC(JSON_NFC_HONG))


# ═══════════════════════════════════════════════════════════════════════════
# D1 — Listener before_flush
# ═══════════════════════════════════════════════════════════════════════════

async def _mot(db: AsyncSession, sql: str, **ts):
    return (await db.execute(text(sql), ts)).one()


@pytest.mark.asyncio
class TestListenerGhi:
    async def test_tao_moi_chu_to_hop_luu_dung_san(self, db_session: AsyncSession, db_engine):
        uid, lid = _uid(), _uid()
        db_session.add(User(id=uid, full_name=NFD(TEN), email="giao@test.vn", password_hash="x",
                            role="data_entry", department="OPS"))
        db_session.add(Lead(id=lid, name=NFD("Chị Hạnh"), phone="0901000111",
                            address=NFD("Quận 7, TP Hồ Chí Minh"), needs=NFD("Thiết kế căn hộ")))
        await db_session.commit()

        # Đọc lại bằng session MỚI — không dính identity map của session đã ghi
        async with async_sessionmaker(db_engine, class_=AsyncSession)() as moi:
            u = await moi.get(User, uid)
            ld = await moi.get(Lead, lid)
            assert u.full_name == TEN
            assert (ld.name, ld.address, ld.needs) == (
                NFC("Chị Hạnh"), NFC("Quận 7, TP Hồ Chí Minh"), NFC("Thiết kế căn hộ"))
        # …và byte trong DB đúng là dạng dựng sẵn
        assert (await _mot(db_session, "SELECT full_name FROM users WHERE id=:i", i=uid))[0] == TEN

    async def test_sua_mot_cot_khong_dung_cot_to_hop_khac(self, db_session: AsyncSession):
        ld = Lead(id=_uid(), name="Lead tam", phone="0901000222")
        db_session.add(ld)
        await db_session.commit()
        # Dữ liệu CŨ dạng tổ hợp (trước 21/11) — cài bằng SQL thô, đi vòng listener
        await db_session.execute(text("UPDATE leads SET name=:n, address=:a WHERE id=:i"),
                                 {"n": NFD("Anh Thịnh"), "a": NFD("Thủ Đức"), "i": ld.id})
        await db_session.commit()
        await db_session.refresh(ld)
        assert ld.name == NFD("Anh Thịnh")

        ld.needs = NFD("Ốp lát phòng tắm")  # chỉ sửa MỘT cột
        await db_session.commit()
        ten, dia_chi, nhu_cau = await _mot(db_session, "SELECT name, address, needs FROM leads WHERE id=:i", i=ld.id)
        assert nhu_cau == NFC("Ốp lát phòng tắm")
        # Cột không đổi giữ nguyên byte cũ (migration mới là nơi dọn chúng)
        assert ten == NFD("Anh Thịnh") and dia_chi == NFD("Thủ Đức")

    async def test_gan_ban_to_hop_cua_gia_tri_dang_luu_khong_sinh_update(self, db_session: AsyncSession, db_engine):
        ld = Lead(id=_uid(), name=NFC("Chị Lan"), phone="0901000333")
        db_session.add(ld)
        await db_session.commit()
        moc = (await _mot(db_session, "SELECT updated_at FROM leads WHERE id=:i", i=ld.id))[0]

        cau_update: list[str] = []

        def _bat(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE"):
                cau_update.append(statement)

        event.listen(db_engine.sync_engine, "before_cursor_execute", _bat)
        try:
            ld.name = NFD("Chị Lan")  # trông y hệt giá trị đang lưu
            await db_session.commit()
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", _bat)

        assert cau_update == []  # không UPDATE thừa
        ten, moc_sau = await _mot(db_session, "SELECT name, updated_at FROM leads WHERE id=:i", i=ld.id)
        assert ten == NFC("Chị Lan") and moc_sau == moc

    async def test_chuoi_ascii_hash_token_va_cot_json_giu_nguyen(self, db_session: AsyncSession, project):
        bam = hash_password("Mật khẩu 123")  # bcrypt → ASCII
        u = User(id=_uid(), full_name="Nguyen Van A", email="ascii@test.vn", password_hash=bam,
                 role="data_entry", department="SALES", llm_api_key="gsk_AbC123xyz", telegram_username="nv_a")
        db_session.add(u)
        # Cột JSON: listener KHÔNG đụng (dict lồng nhau; prod 21/11 không có giá trị nào chưa NFC)
        project.stage_acceptances = {"thiet_ke": {"ghi_chu": NFD("Đã nghiệm thu")}}
        await db_session.commit()

        hang = await _mot(db_session, "SELECT full_name, email, password_hash, llm_api_key, telegram_username "
                                      "FROM users WHERE id=:i", i=u.id)
        assert tuple(hang) == ("Nguyen Van A", "ascii@test.vn", bam, "gsk_AbC123xyz", "nv_a")
        raw = (await _mot(db_session, "SELECT stage_acceptances FROM projects WHERE id=:i", i=project.id))[0]
        assert json.loads(raw)["thiet_ke"]["ghi_chu"] == NFD("Đã nghiệm thu")

    async def test_cot_chu_dung_json_nfc_lam_hong_thi_giu_nguyen(self, db_session: AsyncSession):
        """users.custom_permissions / system_settings.value là cột CHỮ đựng JSON: json.loads không
        được nổ (danh sách nhân viên 500, cấu hình rơi về mặc định) vì NFC ghép dấu vào mã thoát."""
        hop_le = json.dumps({"ghi_chu": NFD("Trưởng kho")}, ensure_ascii=False)
        u = User(id=_uid(), full_name="NV JSON", email="json@test.vn", password_hash="x", role="data_entry",
                 department="OPS", custom_permissions=JSON_NFC_HONG)
        db_session.add(u)
        db_session.add(SystemSetting(key="thu_nfc_json", value=hop_le))
        await db_session.commit()
        quyen = (await _mot(db_session, "SELECT custom_permissions FROM users WHERE id=:i", i=u.id))[0]
        gia_tri = (await _mot(db_session, "SELECT value FROM system_settings WHERE key='thu_nfc_json'"))[0]
        assert quyen == JSON_NFC_HONG and json.loads(quyen)  # giữ nguyên → vẫn đọc được
        assert gia_tri == NFC(hop_le) and json.loads(gia_tri) == {"ghi_chu": NFC("Trưởng kho")}

        # Đường sửa (dirty) cũng vậy; chữ thường (không phải JSON) vẫn được chuẩn hoá như cũ
        u.custom_permissions = JSON_NFC_HONG.replace("1", "3")
        u.full_name = NFD(TEN)
        await db_session.commit()
        quyen, ten = await _mot(db_session, "SELECT custom_permissions, full_name FROM users WHERE id=:i", i=u.id)
        assert quyen == JSON_NFC_HONG.replace("1", "3") and json.loads(quyen)
        assert ten == TEN


def test_listener_co_san_khi_chi_import_models_va_worker(tmp_path):
    """Worker/script không đi qua app.main: chỉ cần import models (→ app.database) là listener có mặt."""
    ma = (
        "import importlib, pkgutil, sys, unicodedata\n"
        "import app.worker\n"
        "import app.models\n"
        # nạp đủ module model (quan hệ Lead→Quotation… cần đủ lớp mới cấu hình được mapper)
        "for m in pkgutil.iter_modules(app.models.__path__):\n"
        "    importlib.import_module('app.models.' + m.name)\n"
        "from sqlalchemy import create_engine, text\n"
        "from sqlalchemy.orm import Session\n"
        "from app.models.user import User\n"
        "assert 'app.main' not in sys.modules\n"
        "eng = create_engine('sqlite://')\n"
        "User.__table__.create(eng)\n"
        "ten = unicodedata.normalize('NFD', 'Tr\\u1ecbnh \\u0110\\u00ecnh Giao')\n"
        "with Session(eng) as s:\n"
        "    s.add(User(full_name=ten, email='a@b.vn', password_hash='x', role='admin', department='EXEC'))\n"
        "    s.commit()\n"
        "    luu = s.execute(text('SELECT full_name FROM users')).scalar_one()\n"
        "print('NFC_OK' if luu == unicodedata.normalize('NFC', ten) != ten else 'CHUA_NFC')\n"
    )
    env = {**os.environ, "APP_ENV": "test", "EMBED_WORKER": "false",
           "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'nfc.db'}"}
    kq = subprocess.run([sys.executable, "-c", ma], cwd=BACKEND_DIR, env=env,
                        capture_output=True, text=True, timeout=120)
    assert kq.returncode == 0, kq.stderr[-2000:]
    assert "NFC_OK" in kq.stdout, kq.stdout + kq.stderr[-2000:]


# ═══════════════════════════════════════════════════════════════════════════
# D2 — Middleware query string
# ═══════════════════════════════════════════════════════════════════════════

class TestQueryString:
    def test_da_nfc_hoac_ascii_khong_viet_lai(self):
        assert chuan_hoa_query(("q=" + quote_plus(TEN)).encode()) is None
        assert chuan_hoa_query(b"page=1&page_size=50&stage=new") is None
        assert chuan_hoa_query(b"") is None

    def test_to_hop_viet_lai_giu_khoa_lap_cong_rong_thu_tu(self):
        qs = ("a=1&a=2&q=" + quote_plus(NFD("Trịnh Văn")) + "&rong=&co&cong=%2B1&&b=x+y").encode()
        moi = chuan_hoa_query(qs)
        assert moi is not None
        cu, sau = qs.split(b"&"), moi.split(b"&")
        assert len(sau) == len(cu)
        for i in (0, 1, 3, 4, 5, 6, 7):
            assert sau[i] == cu[i]  # mảnh đã NFC giữ nguyên từng byte
        assert sau[2].count(b"+") == 1  # khoảng trắng vẫn là «+»
        assert parse_qsl(moi.decode(), keep_blank_values=True) == [
            ("a", "1"), ("a", "2"), ("q", NFC("Trịnh Văn")), ("rong", ""), ("co", ""), ("cong", "+1"), ("b", "x y"),
        ]

    def test_khoa_to_hop_cung_chuan_hoa(self):
        moi = chuan_hoa_query((quote(NFD("tên")) + "=1").encode())
        assert parse_qsl(moi.decode()) == [(NFC("tên"), "1")]

    def test_percent_hong_hoac_ky_tu_thay_the_khong_viet_lai(self):
        assert chuan_hoa_query(b"q=%E1%BB") is None  # UTF-8 cụt
        assert chuan_hoa_query(b"q=%ZZ%") is None  # %XX sai → giữ nguyên
        # Có MỘT mảnh hỏng → không viết lại cả chuỗi (kể cả mảnh tổ hợp hợp lệ)
        assert chuan_hoa_query(("q=" + quote_plus(NFD("Trịnh")) + "&x=%E1").encode()) is None
        assert chuan_hoa_query(("q=" + quote("\ufffd" + NFD("ệ"))).encode()) is None

    def test_byte_ngoai_ascii_khong_viet_lai(self):
        assert chuan_hoa_query(NFD("q=Trịnh&x=%41").encode("utf-8")) is None

    @pytest.mark.asyncio
    async def test_asgi_chi_viet_lai_http_co_chu_to_hop(self):
        thay: list[dict] = []

        async def app_trong(scope, receive, send):
            thay.append(scope)

        mw = ChuanHoaQueryNFC(app_trong)
        s1 = {"type": "http", "query_string": ("q=" + quote_plus(TEN)).encode()}
        await mw(s1, None, None)
        assert thay[-1] is s1  # đã NFC → scope đi nguyên

        goc = ("q=" + quote_plus(NFD(TEN))).encode()
        s2 = {"type": "http", "query_string": goc}
        await mw(s2, None, None)
        assert thay[-1] is not s2 and s2["query_string"] == goc  # không sửa scope gốc
        assert parse_qsl(thay[-1]["query_string"].decode()) == [("q", TEN)]

        s3 = {"type": "websocket", "query_string": goc}
        await mw(s3, None, None)
        assert thay[-1] is s3

        s4 = {"type": "lifespan"}
        await mw(s4, None, None)
        assert thay[-1] is s4


@pytest.mark.asyncio
async def test_tim_nhan_vien_bang_chu_to_hop(client: AsyncClient, db_session: AsyncSession, admin_user):
    db_session.add(User(id=_uid(), full_name=TEN, email="giao2@test.vn", password_hash="x",
                        role="data_entry", department="OPS"))
    await db_session.commit()
    # Đúng lỗi prod 21/11: so thẳng dạng tổ hợp với dữ liệu dựng sẵn là trượt
    tho = (await db_session.execute(select(User).where(User.full_name.ilike(f"%{NFD('Trịnh')}%")))).scalars().all()
    assert tho == []

    r = await client.get("/api/v1/users", params={"q": NFD("Trịnh")}, headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    assert [u["full_name"] for u in r.json()["items"]] == [TEN]

    r = await client.get("/api/v1/leads", params={"search": NFD("Trịnh"), "page_size": 5},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text

    # %XX hỏng: không viết lại, không 500
    r = await client.get("/api/v1/users?q=%E1%BB", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text


# ═══════════════════════════════════════════════════════════════════════════
# D3 — So khớp chữ người dùng gửi trong body / tệp / path
# ═══════════════════════════════════════════════════════════════════════════

async def _dem(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar()


@pytest.mark.asyncio
class TestTimTaoTheoTen:
    """Loại «tìm theo tên, chưa có thì tạo» — NCC gõ ở Vật tư (BoNcc / chuan_ten)."""

    async def test_mau_vat_tu_ten_ncc_to_hop_khop_ncc_san_co(self, client: AsyncClient, db_session, admin_user):
        db_session.add(Supplier(id=_uid(), name=NFC("Hiệp Phát Đồng Nai")))
        await db_session.commit()
        truoc = await _dem(db_session, Supplier)
        r = await client.post("/api/v1/vat-tu/mau", headers=auth_header(admin_user),
                              json={"ma": "HP-NFD", "ncc_gan_nhat_ten": NFD("  hiệp phát   đồng nai ")})
        assert r.status_code == 201, r.text
        assert r.json()["ncc_gan_nhat_ten"] == NFC("Hiệp Phát Đồng Nai")
        assert await _dem(db_session, Supplier) == truoc  # không tạo NCC trùng

    async def test_phat_sinh_hang_muc_to_hop_khong_tao_dong_trung(self, client: AsyncClient, db_session, admin_user):
        du_an = Project(id=_uid(), code="JMH-NFC1", name="Nhà anh Bảy", client_name="Anh Bảy",
                        status="active", total_value=1)
        db_session.add(du_an)
        await db_session.flush()
        hd = Contract(id=_uid(), code="HD-NFC1", project_id=du_an.id, title="Thi công", status="signed",
                      total_value=500_000_000, contract_kind="thi_cong", payment_terms={"installments": []})
        db_session.add(hd)
        await db_session.commit()
        h = auth_header(admin_user)
        mon = {"dvt": "md", "kl": 3.8, "sl": 1, "don_gia": 2_500_000, "thanh_tien": 9_500_000}
        r = await client.post("/api/v1/vat-tu/bot/ghi-phat-sinh", headers=h, json={
            "project_id": du_an.id, "contract_id": hd.id, "tieu_de": "Phát sinh 5/10",
            "items": [{"hang_muc": NFC("Tủ bếp trên"), **mon}]})
        assert r.status_code == 201, r.text
        d = (await db_session.execute(select(DongPhieuVatTu))).scalar_one()
        d.trang_thai = "hoi_ncc"  # Thu mua đã hỏi giá → tệp sau phải GIỮ, không tạo lại
        await db_session.commit()

        r = await client.post("/api/v1/vat-tu/bot/ghi-phat-sinh", headers=h, json={
            "project_id": du_an.id, "contract_id": hd.id, "tieu_de": "Phát sinh 8/10",
            "items": [{"hang_muc": NFD("Tủ bếp trên"), **mon}]})
        assert r.status_code == 201, r.text
        assert r.json()["tao_dong"] == 0 and r.json()["giu_dong"] == 1
        assert await _dem(db_session, DongPhieuVatTu) == 1


@pytest.mark.asyncio
class TestSoBangTrongSql:
    """Loại «== / ILIKE trong SQL với chuỗi body hoặc path»."""

    async def test_so_gia_va_lich_su_gia_ten_vat_tu_to_hop(self, client: AsyncClient, db_session, admin_user):
        s = Supplier(id=_uid(), name="NCC So Gia")
        db_session.add(s)
        await db_session.flush()
        db_session.add(SupplierQuote(id=_uid(), supplier_id=s.id, material_name=NFC("Gạch lát nền 60x60"),
                                     unit_price=250_000))
        await db_session.commit()
        h = auth_header(admin_user)
        r = await client.post("/api/v1/suppliers/compare", headers=h, json={"materials": [NFD("Gạch lát nền 60x60")]})
        assert r.status_code == 200, r.text
        assert r.json()["comparisons"][0]["quote_count"] == 1
        # Path param không qua middleware query string → cũng phải chuẩn hoá tại chỗ
        r = await client.get("/api/v1/suppliers/price-history/" + quote(NFD("Gạch lát nền 60x60")), headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1

    async def test_bot_vat_lieu_ten_to_hop_khop_kho_khong_500(self, client: AsyncClient, db_session, admin_user, project):
        # Hai vật tư cùng chứa «Gỗ sồi» — trước đây scalar_one_or_none nổ MultipleResultsFound (500);
        # lấy đại 1 dòng (không ORDER BY) thì giá — và kết luận vượt định mức — tuỳ thứ tự Postgres trả
        db_session.add(Material(id=_uid(), code="GS-1", name=NFC("Gỗ sồi tấm"), unit_price=500_000))
        db_session.add(Material(id=_uid(), code="GS-2", name=NFC("Gỗ sồi thanh"), unit_price=300_000))
        db_session.add(Material(id=_uid(), code="OC-1", name=NFC("Gỗ óc chó"), unit_price=900_000))
        await db_session.commit()

        async def _gui(ten: str) -> dict:
            r = await client.post("/api/v1/telegram/material-request", headers=auth_header(admin_user), json={
                "project_code": project.code, "material_name": ten, "quantity": 2, "unit": "tấm",
                "requester_tg_id": admin_user.telegram_user_id})
            assert r.status_code == 201, r.text
            return r.json()

        # Mơ hồ: 2 vật tư cùng khớp, không cái nào trùng tên → không đoán giá, không phán vượt định mức
        j = await _gui(NFD("Gỗ sồi"))
        assert (j["estimated_cost"], j["over_budget"]) == (0, False)
        # Chỉ một vật tư khớp (gõ tổ hợp, chữ thường) → có giá
        assert (await _gui(NFD("gỗ óc")))["estimated_cost"] == 1_800_000
        # «%», «_» là chữ thường chứ không phải ký tự đại diện → không khớp bừa («G_ óc» ≠ «Gỗ óc chó»)
        assert (await _gui("G_ óc"))["estimated_cost"] == 0

        # Có vật tư TRÙNG đúng tên → dùng nó, dù tên dài hơn cũng khớp; kết quả lặp lại y hệt
        db_session.add(Material(id=_uid(), code="GS-9", name=NFC("Gỗ sồi"), unit_price=400_000))
        await db_session.commit()
        for _ in range(2):
            assert (await _gui(NFD(" gỗ sồi ")))["estimated_cost"] == 800_000

    async def test_bot_tra_du_an_theo_ma_to_hop(self, client: AsyncClient, db_session, admin_user):
        db_session.add(Project(id=_uid(), code=NFC("NHÀ-01"), name="Nhà chị Mai", client_name="Chị Mai"))
        await db_session.commit()
        r = await client.get("/api/v1/telegram/project/" + quote(NFD("NHÀ-01")), headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json()["project"]["code"] == NFC("NHÀ-01")

        from app.api.media import _tim_du_an
        assert (await _tim_du_an(db_session, None, NFD(" nhà-01 "))).code == NFC("NHÀ-01")


@pytest.mark.asyncio
class TestKhoaVaMaTrung:
    """Loại «khoá chính tự nhiên / kiểm trùng mã trước khi ghi» — listener ghi bản NFC nên chỗ
    tra trước cũng phải tra bằng NFC, kẻo lọt kiểm tra rồi nổ IntegrityError (500)."""

    async def test_cai_gia_nhom_to_hop_sua_dong_san_co(self, client: AsyncClient, db_session, admin_user):
        db_session.add(GiaNhomVatTu(nhom=NFC("Gạch ốp"), phan_tram_lai=15))
        await db_session.commit()
        r = await client.put("/api/v1/vat-tu/cai-gia", headers=auth_header(admin_user),
                             json=[{"nhom": NFD("Gạch ốp"), "phan_tram_lai": 22}])
        assert r.status_code == 200, r.text
        ds = (await db_session.execute(select(GiaNhomVatTu))).scalars().all()
        assert [(g.nhom, g.phan_tram_lai) for g in ds] == [(NFC("Gạch ốp"), 22)]

    async def test_ma_du_an_doi_ma_bang_gia_to_hop_bao_trung(self, client: AsyncClient, db_session, admin_user):
        db_session.add(Project(id=_uid(), code=NFC("NHÀ-02"), name="Nhà A", client_name="Khách A"))
        db_session.add(Team(id=_uid(), name="Đội Hà Nội", code=NFC("HÀ-NỘI"), department="SALES"))
        db_session.add(PriceItem(id=_uid(), code=NFC("TRẦN-01"), name="Trần thạch cao", category="tran_vach"))
        await db_session.commit()
        h = auth_header(admin_user)

        r = await client.post("/api/v1/projects", headers=h,
                              json={"code": NFD("NHÀ-02"), "name": "Nhà B", "client_name": "Khách B"})
        assert r.status_code == 400, r.text
        r = await client.post("/api/v1/users/teams", headers=h, json={"name": "Đội HN 2", "code": NFD("hà-nội")})
        assert r.status_code == 400, r.text
        r = await client.post("/api/v1/instant-quote/price-items", headers=h, json={
            "code": NFD("TRẦN-01"), "name": "Trần 2", "category": "tran_vach", "unit": "m2",
            "price_basic": 1, "price_standard": 2, "price_premium": 3})
        assert r.status_code == 400, r.text

    async def test_vai_tro_tuy_chinh_khoa_to_hop_bao_trung(self, client: AsyncClient, admin_user):
        h = auth_header(admin_user)
        r = await client.post("/api/v1/users/roles", headers=h,
                              json={"role_key": NFC("trưởng kho"), "role_name": "Trưởng kho", "department": "OPS"})
        assert r.status_code == 200, r.text
        r = await client.post("/api/v1/users/roles", headers=h,
                              json={"role_key": NFD("Trưởng kho"), "role_name": "Trưởng kho 2", "department": "OPS"})
        assert r.status_code == 400, r.text


class TestChuHangTiengViet:
    """Loại «so với chữ hằng tiếng Việt» — từ khoá / regex trong code."""

    @pytest.mark.asyncio
    async def test_phan_tich_lead_tu_khoa_to_hop(self, client: AsyncClient, admin_user):
        r = await client.post("/api/v1/ai/parse-lead", headers=auth_header(admin_user), json={
            "text": NFD("Chị Hạnh 0901234567 cần làm căn hộ 80m2, ngân sách 2 tỷ, được giới thiệu")})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["property_type"] == "apartment" and j["source"] == "referral"
        assert j["estimated_budget"] == 2_000_000_000

    @pytest.mark.asyncio
    async def test_lead_intake_regex_du_phong_to_hop(self, monkeypatch):
        from app.agents import lead_intake

        async def _khong_co_llm(*a, **k):
            raise RuntimeError("không có LLM")

        monkeypatch.setattr(lead_intake, "llm_complete", _khong_co_llm)
        kq = await lead_intake.parse_lead_text(NFD("Chị Hạnh 0901234567"))
        assert kq.name == NFC("Hạnh") and kq.phone == "0901234567"

    @pytest.mark.asyncio
    async def test_bao_cao_noi_bo_go_to_hop(self, client: AsyncClient, db_session, admin_user, project):
        r = await client.post("/api/v1/telegram/site-report", headers=auth_header(admin_user), json={
            "project_code": project.code, "content": NFD("#nội bộ Thợ nghỉ ốm 2 hôm"),
            "reporter_tg_id": admin_user.telegram_user_id})
        assert r.status_code == 201, r.text
        hd = await db_session.get(TaskActivity, r.json()["activity_id"])
        assert hd.kind == "noi_bo"  # không lộ ra portal khách
        assert hd.content == NFC("#nội bộ Thợ nghỉ ốm 2 hôm")

    def test_zalo_tu_khoa_to_hop(self):
        from app.services.zalo_analysis import _rule_based_signals

        loai = {s["type"] for s in _rule_based_signals(NFD("Chị ơi báo giá giúp em, em không hài lòng lắm"))}
        assert {"quote_request", "deal_risk"} <= loai


class TestNhapTepVaCauHinh:
    """Loại «nhập tệp (Sheet/Excel) khớp tiêu đề/tên/danh mục» và «khoá cấu hình»."""

    def test_sheet_vat_tu_tieu_de_va_nhom_to_hop(self):
        from app.services import vat_tu_sheet

        csv_to_hop = NFD(
            "STT,MÃ (NẾU CÓ),THƯƠNG HIỆU,TÍNH CHẤT,ĐƠN GIÁ (M2),NCC\n"
            "1,MÃ,,,,\n"
            "2,6A01,Đồng Tâm,Bóng kính,\"280,000\",Hiệp Phát\n"
        )
        ds = vat_tu_sheet.doc_csv(csv_to_hop, NFD("Gạch 60x60"))
        assert len(ds) == 1  # dòng «MÃ» lặp tiêu đề bị bỏ
        d = ds[0]
        assert (d["ma"], d["hang"], d["nhom"], d["be_mat"], d["ncc_gan_nhat_ten"], d["gia_tham_khao"]) == (
            "6A01", NFC("Đồng Tâm"), NFC("Gạch 60x60"), NFC("Bóng kính"), NFC("Hiệp Phát"), 280_000)

    @pytest.mark.asyncio
    async def test_nhap_vat_tu_ten_va_danh_muc_to_hop(self, client: AsyncClient, db_session, accountant_user):
        db_session.add(Material(id=_uid(), code="VT-777", name=NFC("Gỗ óc chó"), category="wood", unit_price=100))
        await db_session.commit()
        r = await client.post("/api/v1/inventory/import", headers=auth_header(accountant_user), json={"rows": [
            {"name": NFD("Gỗ óc chó"), "category": NFD("Gỗ"), "unit_price": 150},
            {"name": NFD("Đá hoa cương"), "category": NFD("Đá"), "unit_price": 90},
        ]})
        assert r.status_code == 200, r.text
        kq = r.json()
        assert kq["errors"] == [] and kq["updated"] == 1 and kq["created"] == 1
        m = (await db_session.execute(select(Material).where(Material.code == "VT-777"))).scalar_one()
        assert m.unit_price == 150

    def test_excel_nhan_su_o_chu_to_hop(self):
        from app.services import nhap_nhan_su

        assert nhap_nhan_su._chu(NFD(" Quận 7, TP HCM "), 255) == NFC("Quận 7, TP HCM")

    @pytest.mark.asyncio
    async def test_cau_hinh_sla_khoa_ten_viec_to_hop(self, db_session):
        from app.services import task_sla

        await task_sla.luu_cau_hinh_sla(db_session, dau_viec={NFD("Thi công thô"): 20, NFD("Đặt hàng"): 4})
        luu = json.loads((await db_session.get(SystemSetting, task_sla.KEY_SLA_DAU_VIEC)).value)
        assert luu == {NFC("Đặt hàng"): 4}  # bằng mặc định (20 ngày) thì không lưu
        assert (await task_sla.lay_cau_hinh_sla(db_session))["dau_viec"][NFC("Đặt hàng")] == 4


# ═══════════════════════════════════════════════════════════════════════════
# Khoá chống trùng dựng từ nguồn chưa chuẩn hoá (cột JSON)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestKhoaChongTrung:
    async def test_nhac_thanh_toan_ref_id_to_hop_chi_mot_thong_bao(self, db_session, monkeypatch):
        """ref_id «{hđ}:{tên đợt}» lấy tên đợt từ cột JSON payment_terms (listener không chuẩn hoá):
        listener ghi ref_id NFC mà dò bằng bản tổ hợp → không bao giờ khớp → ngày nào cũng nhắc lại."""
        from app.services import automation

        gui: list[str] = []

        async def _gia(chat_id, tin, **kw):
            gui.append(tin)
            return True

        monkeypatch.setattr(automation, "send_telegram", _gia)
        kt = User(id=_uid(), full_name="Kế toán NFC", email="kt-nfc@test.vn", password_hash="x",
                  role="accountant", department="ACCT", telegram_user_id=900777)
        db_session.add(kt)
        await db_session.commit()
        ref = f"hd-1:{NFD('Đợt 2 – Hoàn thiện')}"
        kq = []
        for _ in range(3):  # 3 ngày chạy job nhắc thanh toán quá hạn
            kq.append(await automation._notify(db_session, kt, "payment_reminder", "Nhắc thanh toán: HĐ X",
                                                "Đợt thanh toán đã quá hạn", ref_id=ref))
            await db_session.commit()
        assert kq == [True, False, False] and len(gui) == 1
        luu = (await db_session.execute(
            select(Notification.ref_id).where(Notification.user_id == kt.id))).scalars().all()
        assert luu == [NFC(ref)]

    async def test_sua_lich_thu_ten_dot_luu_nfc(self, client: AsyncClient, db_session, admin_user):
        du_an = Project(id=_uid(), code="JMH-NFC2", name="Nhà chị Tư", client_name="Chị Tư",
                        status="active", total_value=1)
        db_session.add(du_an)
        await db_session.flush()
        hd = Contract(id=_uid(), code="HD-NFC2", project_id=du_an.id, title="Thi công", status="signed",
                      total_value=100_000_000, contract_kind="thi_cong", payment_terms={"installments": []})
        db_session.add(hd)
        await db_session.commit()
        r = await client.put(f"/api/v1/contracts/{hd.id}/lich-thu", headers=auth_header(admin_user), json={"dot": [
            {"name": NFD(" Đợt 1 – Đặt cọc "), "percentage": 40}, {"name": NFD("Hoàn thiện"), "percentage": 60}]})
        assert r.status_code == 200, r.text
        assert [d["name"] for d in r.json()["payment_terms"]["installments"]] == [
            NFC("Đợt 1 – Đặt cọc"), NFC("Hoàn thiện")]


# ═══════════════════════════════════════════════════════════════════════════
# D4 — Migration dọn dữ liệu cũ
# ═══════════════════════════════════════════════════════════════════════════

def _nap_migration():
    duong = os.path.join(BACKEND_DIR, "alembic", "versions", "a28_2026b007_chuan_hoa_unicode_nfc.py")
    spec = importlib.util.spec_from_file_location("a28_nfc", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOC = "2026-01-02 03:04:05.000000"


class TestMigrationDuLieuCu:
    @staticmethod
    def _db(tmp_path):
        from app.database import Base

        eng = create_engine(f"sqlite:///{tmp_path / 'nfc_cu.db'}")
        Base.metadata.create_all(eng)
        with Session(eng) as s:
            s.add(User(id="u1", full_name="tam", email="u1@test.vn", password_hash="x", role="admin", department="EXEC"))
            s.add(Lead(id="l1", name="tam", phone="0900000001"))
            s.add(Notification(id="n1", user_id="u1", title="tam", body="tam"))
            s.add(GiaNhomVatTu(nhom="tam", phan_tram_lai=15))
            s.add(Project(id="p1", code="P-NFC", name="tam", client_name="tam"))
            s.commit()
        # Cài dữ liệu CŨ dạng tổ hợp bằng SQL thô (listener chỉ chạy khi flush ORM)
        with eng.begin() as c:
            c.execute(text("UPDATE users SET full_name=:v, updated_at=:t WHERE id='u1'"), {"v": NFD(TEN), "t": MOC})
            c.execute(text("UPDATE leads SET name=:n, address=:a, updated_at=:t WHERE id='l1'"),
                      {"n": NFD("Chị Hạnh"), "a": NFD("Thủ Đức"), "t": MOC})
            c.execute(text("UPDATE notifications SET title=:t1, body=:b WHERE id='n1'"),
                      {"t1": NFD("Lead mới"), "b": NFD("Anh Thịnh gọi lại")})
            c.execute(text("UPDATE gia_nhom_vat_tu SET nhom=:v WHERE nhom='tam'"), {"v": NFD("Gạch ốp")})
            c.execute(text("UPDATE projects SET stage_acceptances=:j WHERE id='p1'"),
                      {"j": json.dumps({"ghi_chu": NFD("Đã nghiệm thu")}, ensure_ascii=False)})
        return eng

    def test_sqlite_chuan_hoa_giu_updated_at_bo_json_chay_lai_khong_doi(self, tmp_path, caplog):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mod = _nap_migration()
        eng = self._db(tmp_path)
        with eng.begin() as c:
            assert mod.chuan_hoa_csdl(c) == {
                "gia_nhom_vat_tu.nhom": 1, "leads.address": 1, "leads.name": 1,
                "notifications.body": 1, "notifications.title": 1, "users.full_name": 1,
            }
        with eng.connect() as c:
            assert tuple(c.execute(text("SELECT full_name, updated_at FROM users WHERE id='u1'")).one()) == (TEN, MOC)
            assert tuple(c.execute(text("SELECT name, address, updated_at FROM leads WHERE id='l1'")).one()) == (
                NFC("Chị Hạnh"), NFC("Thủ Đức"), MOC)
            assert tuple(c.execute(text("SELECT title, body FROM notifications WHERE id='n1'")).one()) == (
                NFC("Lead mới"), NFC("Anh Thịnh gọi lại"))
            assert c.execute(text("SELECT nhom FROM gia_nhom_vat_tu")).scalars().all() == [NFC("Gạch ốp")]
            raw = c.execute(text("SELECT stage_acceptances FROM projects WHERE id='p1'")).scalar_one()
            assert NFD("Đã nghiệm thu") in raw  # cột JSON không phải kiểu chữ → không đụng

        # Chạy lại qua đúng điểm vào upgrade() của Alembic: không còn gì để sửa
        with caplog.at_level("INFO", logger="alembic"):
            with eng.begin() as c:
                with Operations.context(MigrationContext.configure(c)):
                    mod.upgrade()
            with eng.begin() as c:
                assert mod.chuan_hoa_csdl(c) == {}
        assert "0 dòng-cột ở 0 cột" in caplog.text
        eng.dispose()

    def test_sqlite_cot_chu_dung_json_nfc_lam_hong_thi_giu_nguyen(self, tmp_path):
        mod = _nap_migration()
        eng = self._db(tmp_path)
        hop_le = json.dumps({"ten": NFD(TEN)}, ensure_ascii=False)
        with eng.begin() as c:
            c.execute(text("INSERT INTO audit_logs (id, action, entity_type, before_json, after_json, created_at) "
                           "VALUES ('a1', 'user.update', 'user', :b, :a, :t)"),
                      {"b": hop_le, "a": JSON_NFC_HONG, "t": MOC})
            c.execute(text("UPDATE users SET custom_permissions=:p WHERE id='u1'"), {"p": JSON_NFC_HONG})
        with eng.begin() as c:
            kq = mod.chuan_hoa_csdl(c)
        assert kq["audit_logs.before_json"] == 1
        assert "audit_logs.after_json" not in kq and "users.custom_permissions" not in kq
        with eng.connect() as c:
            truoc, sau = c.execute(text("SELECT before_json, after_json FROM audit_logs WHERE id='a1'")).one()
            quyen = c.execute(text("SELECT custom_permissions FROM users WHERE id='u1'")).scalar_one()
        assert truoc == NFC(hop_le) and json.loads(truoc) == {"ten": TEN}  # JSON vẫn hợp lệ sau NFC → chuẩn hoá
        assert sau == JSON_NFC_HONG and quyen == JSON_NFC_HONG  # NFC sẽ làm hỏng → giữ nguyên, vẫn đọc được
        eng.dispose()

    def test_postgres_moi_cot_mot_cau_savepoint_rieng_loi_di_tiep(self, caplog):
        from sqlalchemy.dialects import postgresql

        from app.chuan_hoa_unicode import _postgres

        mod = _nap_migration()

        class _KetQua:
            rowcount = 2

        class _BindGia:
            def __init__(self, phien_ban=None):
                self.dialect = postgresql.dialect()
                self.dialect.server_version_info = phien_ban
                self.cau: list[str] = []
                self.savepoint: list[str] = []

            def begin_nested(self):
                bind = self

                class _SP:
                    def __enter__(self):
                        bind.savepoint.append("mo")

                    def __exit__(self, kieu, *_):
                        bind.savepoint.append("huy" if kieu else "giai_phong")
                        return False

                return _SP()

            def execute(self, cau):
                sql = str(cau)
                self.cau.append(sql)
                if "email" in sql:
                    raise RuntimeError("duplicate key value violates unique constraint")
                return _KetQua()

        bind, kq = _BindGia((18, 6)), {}
        with caplog.at_level("WARNING", logger="alembic"):
            _postgres(bind, "users", ["full_name", "email", "user"], kq, mod.logger)
        assert bind.cau[0] == ("UPDATE users SET full_name = normalize(full_name, NFC) "
                               "WHERE full_name IS NOT NULL AND NOT (full_name IS NFC NORMALIZED) "
                               "AND (NOT (full_name IS JSON) OR normalize(full_name, NFC) IS JSON)")
        assert 'SET "user" = normalize("user", NFC)' in bind.cau[2]  # từ khoá SQL được đặt trong ngoặc kép
        assert bind.savepoint == ["mo", "giai_phong", "mo", "huy", "mo", "giai_phong"]
        assert kq == {"users.full_name": 2, "users.user": 2}  # cột lỗi bỏ qua, cột sau vẫn chạy
        assert "users.email" in caplog.text
        assert any(r.name == "alembic.a28_chuan_hoa_nfc" for r in caplog.records)  # log deploy thấy được

        # Postgres < 16 chưa có `IS JSON` → bỏ vế đó thay vì nổ (và bỏ qua) MỌI cột
        cu = _BindGia((15, 4))
        _postgres(cu, "users", ["full_name"], {})
        assert cu.cau == ["UPDATE users SET full_name = normalize(full_name, NFC) "
                          "WHERE full_name IS NOT NULL AND NOT (full_name IS NFC NORMALIZED)"]


@pytest.mark.asyncio
class TestQuetLaiSauDeploy:
    """Khoảng giao thời: start.sh chạy migration trước uvicorn, bản CŨ (chưa có listener) còn
    phục vụ tới khi /health bản mới qua → chữ tổ hợp ghi lúc đó phải được quét lại một lần."""

    async def test_quet_mot_lan_roi_ghi_co(self, tmp_path):
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.chuan_hoa_unicode import KHOA_QUET_LAI, quet_lai_sau_deploy
        from app.database import Base

        eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'quet_lai.db'}")
        tao = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with eng.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        async with tao() as db:
            db.add(User(id="u1", full_name="tam", email="u1@t.vn", password_hash="x", role="admin", department="EXEC"))
            db.add(Notification(id="n1", user_id="u1", type="x", title="tam", body=JSON_NFC_HONG))
            await db.commit()
        # Bản CŨ (chưa có listener) ghi chữ tổ hợp SAU câu UPDATE của migration — mô phỏng bằng SQL thô
        async with eng.begin() as c:
            await c.execute(text("UPDATE users SET full_name=:t, updated_at=:m"), {"t": NFD(TEN), "m": MOC})
            await c.execute(text("UPDATE notifications SET title=:t"), {"t": NFD("Lead mới")})
        try:
            kq = await quet_lai_sau_deploy(engine=eng, session_factory=tao, cho_giay=0)
            assert kq == {"notifications.title": 1, "users.full_name": 1}
            async with eng.connect() as c:
                assert tuple((await c.execute(text("SELECT full_name, updated_at FROM users"))).one()) == (TEN, MOC)
                tieu_de, than = (await c.execute(text("SELECT title, body FROM notifications"))).one()
                assert (tieu_de, than) == (NFC("Lead mới"), JSON_NFC_HONG)
            async with tao() as db:
                co = await db.get(SystemSetting, KHOA_QUET_LAI)
                assert co is not None and json.loads(co.value)["so_dong"] == 2

            # Cờ đã có → các lần khởi động sau không quét nữa (một lần duy nhất)
            async with eng.begin() as c:
                await c.execute(text("UPDATE users SET full_name=:t"), {"t": NFD(TEN)})
            assert await quet_lai_sau_deploy(engine=eng, session_factory=tao, cho_giay=0) is None
            async with eng.connect() as c:
                assert (await c.execute(text("SELECT full_name FROM users"))).scalar_one() == NFD(TEN)
        finally:
            await eng.dispose()

    async def test_nen_loi_chi_canh_bao_khong_lam_sap_app(self, monkeypatch, capsys):
        from app import chuan_hoa_unicode, main

        async def _no(*a, **k):
            raise RuntimeError("mất kết nối DB")

        monkeypatch.setattr(chuan_hoa_unicode, "quet_lai_sau_deploy", _no)
        await main._quet_lai_nfc_nen()  # không ném lỗi ra ngoài
        assert "mất kết nối DB" in capsys.readouterr().out
