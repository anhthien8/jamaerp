"""Vật tư Đợt 1 (22/11/2026) — migration a29 điền bù dữ liệu cũ.

Luật «khách đồng ý» đổi từ «bấm SAU lúc chốt, dòng đang ở đã chốt giá» sang «còn hiệu lực tới khi giá
bán đổi». Lời đồng ý mà theo luật cũ CHƯA có hiệu lực phải bị xoá lúc nâng cấp — để lại thì code mới coi
là hợp lệ và cho đặt hàng. Chạy lại migration sau khi code mới đã chạy thì không được xoá gì nữa.
"""
import importlib.util
import os

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T1, T2, T3 = "2026-11-01 08:00:00.000000", "2026-11-05 08:00:00.000000", "2026-11-09 08:00:00.000000"

# id → (trạng thái, giá bán, chốt lúc, khách đồng ý lúc, số lượng đã đặt, còn lời đồng ý sau khi nâng cấp)
DONG_CU = {
    "chot_dong_y_sau":    ("da_chot_gia", 300000, T1, T2, None, True),    # hợp lệ theo luật cũ → giữ
    "chot_khong_co_moc":  ("da_chot_gia", 300000, None, T1, None, True),
    "chot_dong_y_truoc":  ("da_chot_gia", 300000, T2, T1, None, False),   # bấm trước lần chốt gần nhất
    "hoi_ncc_co_gia":     ("hoi_ncc", 300000, T1, T2, None, False),       # vd khách nhận mẫu thay trước deploy
    "het_hang":           ("het_hang", 300000, T1, T2, None, False),
    "cho_duyet_lai":      ("cho_khach_duyet_lai", 300000, T1, T2, None, False),
    "huy_chua_dat":       ("huy", 300000, T1, T2, None, False),           # mở lại được → không mang lời đồng ý cũ
    "chua_co_gia":        ("khach_chon", None, None, T1, None, False),    # đồng ý khi chưa có giá là vô nghĩa → xoá
    "da_dat":             ("da_dat", 300000, T2, T1, 10, True),           # đã đặt hàng: chỉ còn là lịch sử
    "cho_duyet_dat":      ("cho_duyet_dat", 300000, T2, T1, 12, True),
    "giao_thieu":         ("giao_thieu", 300000, T2, T1, 10, True),
    "huy_sau_dat":        ("huy", 300000, T2, T1, 10, True),              # không mở lại được → giữ làm lịch sử
    "chot_chua_dong_y":   ("da_chot_gia", 300000, T2, None, None, False),
}
# id → (ghi chú, nguồn sau khi nâng cấp). Hai dạng đầu là chuỗi `bot_ghi_bao_gia` ghi từ commit 8beb7c6 tới nay
BAO_GIA_CU = {
    "bot_co_tep":   ("Còn hàng · Nhập từ tệp bg.xlsx bởi Trần Lan (bot)", "tep"),
    "bot_khong_tep": ("Nhập qua bot bởi Trần Lan", "tep"),
    "go_tay":       ("Chưa VAT, giao 3 ngày", "tay"),
    "khong_ghi_chu": (None, "tay"),
}


def _a29():
    duong = os.path.join(BACKEND_DIR, "alembic", "versions", "a29_2026b008_vat_tu_ncc_dot_1.py")
    spec = importlib.util.spec_from_file_location("a29_vat_tu_ncc", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chay(eng, ham) -> None:
    with eng.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            ham()


def _con_dong_y(eng) -> dict[str, bool]:
    with eng.connect() as c:
        return {i: bool(co) for i, co in c.execute(text("SELECT id, khach_dong_y_luc IS NOT NULL FROM dong_phieu_vat_tu"))}


def _nguon(eng) -> dict[str, str]:
    with eng.connect() as c:
        return dict(c.execute(text("SELECT id, nguon FROM bao_gia_dong_vat_tu")).all())


def test_a29_xoa_dung_loi_dong_y_chua_hieu_luc_theo_luat_cu_va_chay_lai_khong_doi_gi(tmp_path):
    from app.database import Base

    mod = _a29()
    eng = create_engine(f"sqlite:///{tmp_path / 'a29.db'}")
    Base.metadata.create_all(eng)
    _chay(eng, mod.downgrade)  # về lược đồ a28: chưa có cột / bảng của Đợt 1
    with eng.connect() as c:
        assert not {"gia_xac_nhan_luc", "ngay_giao_hen", "huy_luc"} & {x["name"] for x in inspect(c).get_columns("dong_phieu_vat_tu")}
        assert not {"nhan_hang_vat_tu", "gia_nhap_mau_vat_tu"} & set(inspect(c).get_table_names())
    with eng.begin() as c:
        for i, (tt, gia, chot, dong_y, sl_dat, _) in DONG_CU.items():
            da_nhan = tt == "giao_thieu"
            c.execute(text(
                "INSERT INTO dong_phieu_vat_tu (id, project_id, phong, so_luong, don_vi, trang_thai, thu_tu, created_at, "
                "updated_at, gia_ban, chot_luc, khach_dong_y_luc, sl_dat, nhan_luc, nhan_ket_qua, sl_nhan, nhan_ghi_chu) "
                "VALUES (:i, 'p1', 'Bếp', 10, 'm2', :tt, 0, :t, :t, :gia, :chot, :dy, :sl, :nhan, :kq, :sl_nhan, :gc)"),
                {"i": i, "tt": tt, "t": T1, "gia": gia, "chot": chot, "dy": dong_y, "sl": sl_dat,
                 "nhan": T3 if da_nhan else None, "kq": "thieu" if da_nhan else None,
                 "sl_nhan": 4 if da_nhan else None, "gc": "Về 4" if da_nhan else None})
        for i, (ghi_chu, _) in BAO_GIA_CU.items():
            c.execute(text(
                "INSERT INTO bao_gia_dong_vat_tu (id, dong_id, ncc_ten, gia, con_hang, duoc_chon, ghi_chu, created_at) "
                "VALUES (:i, 'chot_dong_y_sau', 'Hiệp Phát', 200000, 1, 0, :g, :t)"), {"i": i, "g": ghi_chu, "t": T1})

    _chay(eng, mod.upgrade)
    assert _con_dong_y(eng) == {i: r[5] for i, r in DONG_CU.items()}
    assert _nguon(eng) == {i: r[1] for i, r in BAO_GIA_CU.items()}
    with eng.connect() as c:
        moc = dict(c.execute(text("SELECT id, gia_xac_nhan_luc FROM dong_phieu_vat_tu")).all())
        assert moc == {i: r[2] for i, r in DONG_CU.items()}, "ngày bằng chứng giá của dòng cũ = ngày chốt"
        nhan = c.execute(text("SELECT dong_id, ket_qua, sl_lan_nay, sl_luy_ke, ghi_chu FROM nhan_hang_vat_tu")).all()
        assert [tuple(x) for x in nhan] == [("giao_thieu", "thieu", 4, 4, "Về 4")]

    # Sau deploy, code mới ghi «đồng ý giá chuẩn TRƯỚC, Thu mua chốt giá vốn SAU» là hợp lệ. Migration chạy lại
    # (bảng alembic_version rỗng → chạy lại cả chuỗi) không được xoá lời đồng ý đó, không đổi nguồn báo giá.
    with eng.begin() as c:
        c.execute(text("UPDATE dong_phieu_vat_tu SET khach_dong_y_luc = :t WHERE id = 'chot_chua_dong_y'"), {"t": T1})
        c.execute(text(
            "INSERT INTO bao_gia_dong_vat_tu (id, dong_id, ncc_ten, gia, con_hang, duoc_chon, ghi_chu, nguon, created_at) "
            "VALUES ('tay_sau_deploy', 'chot_dong_y_sau', 'Daisan', 190000, 1, 0, 'NCC báo qua Zalo (bot)', 'tay', :t)"), {"t": T3})
    _chay(eng, mod.upgrade)
    assert _con_dong_y(eng) == {i: r[5] for i, r in DONG_CU.items()} | {"chot_chua_dong_y": True}
    assert _nguon(eng) == {i: r[1] for i, r in BAO_GIA_CU.items()} | {"tay_sau_deploy": "tay"}
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM nhan_hang_vat_tu")).scalar_one() == 1, "không điền bù lịch sử nhận hàng lần hai"
    eng.dispose()
