"""Chuỗi migration Alembic: mỗi revision một mã riêng, đúng một head (21/11/2026).

Lỗi suýt dính: migration NFC và migration «hẹn tiếp lead» (R00, nhánh khác) cùng lấy mã
a27_2026b006, cùng nối sau a26_2026b005. Alembic gặp hai tệp cùng mã chỉ cảnh báo
(«Revision … is present more than once») rồi lặng lẽ giữ MỘT tệp — `alembic heads` vẫn in
một head, nên không ai thấy. Hậu quả: một migration không bao giờ chạy (cột R00 không được
tạo → «column does not exist», hoặc dữ liệu cũ không được chuẩn hoá) — cùng loại sự cố 13/10.
"""

import glob
import os
import re
import warnings

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THU_MUC_VERSIONS = os.path.join(BACKEND_DIR, "alembic", "versions")

_MA = re.compile(r"""^revision(?:\s*:\s*str)?\s*=\s*['"]([^'"]+)['"]""", re.M)


def test_moi_tep_migration_mot_ma_revision_rieng():
    theo_ma: dict[str, list[str]] = {}
    for duong in sorted(glob.glob(os.path.join(THU_MUC_VERSIONS, "*.py"))):
        with open(duong, encoding="utf-8") as f:
            ds = _MA.findall(f.read())
        assert len(ds) == 1, f"{os.path.basename(duong)}: cần đúng 1 dòng `revision = '…'`, thấy {ds}"
        theo_ma.setdefault(ds[0], []).append(os.path.basename(duong))
    trung = {ma: tep for ma, tep in theo_ma.items() if len(tep) > 1}
    assert not trung, f"Trùng mã revision (Alembic sẽ lặng lẽ bỏ một tệp): {trung}"


def test_alembic_nap_khong_canh_bao_va_dung_mot_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    with warnings.catch_warnings():
        # «Revision X is present more than once» chỉ là UserWarning → biến thành lỗi
        warnings.simplefilter("error", UserWarning)
        kho = ScriptDirectory.from_config(cfg)
        heads = kho.get_heads()
        ds = list(kho.walk_revisions())  # chuỗi đứt (down_revision trỏ mã không có) → nổ ở đây
    assert len(heads) == 1, (
        f"Nhiều head {heads}: nhánh vào main sau phải trỏ down_revision vào head còn lại")
    assert len({s.revision for s in ds}) == len(ds)
