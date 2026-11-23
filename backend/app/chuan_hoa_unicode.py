"""Chuẩn hoá Unicode NFC cho chữ tiếng Việt (21/11/2026).

Một chữ tiếng Việt có 2 cách mã hoá trông y hệt nhau:
- NFC (dựng sẵn): «ệ» là 1 ký tự — bàn phím điện thoại, Unikey «Unicode dựng sẵn».
- NFD (tổ hợp): «e» + dấu mũ + dấu nặng = 3 ký tự — Unikey «Unicode tổ hợp».
Máy so chữ coi 2 dạng là KHÁC nhau → `ILIKE '%Trịnh%'` không ra tên lưu dạng tổ hợp,
NCC gõ tên tổ hợp bị tạo trùng… Quy ước toàn hệ thống: mọi chữ GHI vào DB và mọi chữ
đem đi SO đều ở dạng NFC.

- `nfc(s)`: chuẩn hoá một chuỗi — dùng tại chỗ so khớp chữ người dùng gửi trong body
  (JSON, form, tệp Excel/CSV, path) với dữ liệu DB / chữ hằng. Query string đã được
  middleware `ChuanHoaQueryNFC` chuẩn hoá sẵn.
- Listener `before_flush` cấp class `Session` — đăng ký khi import module này, và
  `app.database` import nó nên app, worker nhúng, script, test đều có:
  * `session.new`: mọi thuộc tính cột kiểu String/Text (kể cả lớp con, trừ Enum) đang
    mang `str` chưa NFC → gán bản NFC.
  * `session.dirty`: CHỈ thuộc tính có `history.added` (cột vừa được gán) — cột không
    đổi không bị đụng, không sinh UPDATE thừa. Gán lại bản NFD của đúng giá trị NFC đang
    lưu → sau chuẩn hoá bằng giá trị cũ → SQLAlchemy không UPDATE (updated_at giữ nguyên).
  * Đọc thẳng `state.dict` / lịch sử thuộc tính → không kích lazy-load.
  * KHÔNG đụng cột JSON (dict/list lồng nhau — prod 21/11 không có giá trị nào chưa NFC),
    cột nhị phân, TypeDecorator (chưa model nào dùng). Chuỗi ASCII (hash, token, mã, email)
    luôn là NFC nên giữ nguyên từng byte.
  * Cột CHỮ đựng JSON (audit_logs.*_json, users.custom_permissions, system_settings.value…):
    bản NFC làm hỏng JSON thì giữ nguyên bản gốc — xem `nfc_giu_json`.
  * Không phủ câu lệnh core `insert()/update()` (bỏ qua flush) — chỗ nào ghi chữ người
    dùng bằng core thì gọi `nfc()` tại chỗ.
- `chuan_hoa_csdl(bind)`: dọn chữ ĐÃ LƯU (migration a28_2026b007 gọi), và
  `quet_lai_sau_deploy()`: chạy lại hàm đó MỘT lần sau khi bản mới nhận traffic.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from typing import TypeVar

from sqlalchemy import Column, Enum, String, event, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapper, Session

T = TypeVar("T")

logger = logging.getLogger(__name__)


def chua_nfc(s: object) -> bool:
    """True nếu là chuỗi và CHƯA ở dạng NFC."""
    return isinstance(s, str) and not unicodedata.is_normalized("NFC", s)


def nfc(s: T) -> T:
    """Chuỗi → bản NFC; đã NFC (gồm mọi chuỗi ASCII) thì trả NGUYÊN đối tượng cũ.
    None / không phải chuỗi → trả nguyên."""
    if chua_nfc(s):
        return unicodedata.normalize("NFC", s)  # type: ignore[arg-type, return-value]
    return s


def _la_json(s: str) -> bool:
    try:
        json.loads(s)
    except (ValueError, RecursionError):
        return False
    return True


def nfc_giu_json(s: str) -> str:
    """Bản NFC để GHI vào DB — trừ khi chuỗi là JSON hợp lệ mà bản NFC thì hết hợp lệ.

    Cột chữ đựng JSON (audit_logs.before_json/after_json, users.custom_permissions,
    system_settings.value, ai_runs.output_json…): dấu đứng trơ ngay sau chữ của một mã
    thoát JSON (\\n \\t \\r \\b \\f, chữ số hex cuối của \\uXXXX) bị NFC ghép luôn vào chữ đó
    («\\n» + dấu ngã → «\\ñ») → json.loads nổ (danh sách nhân viên 500, cấu hình rơi về
    mặc định). Gặp ca đó thì giữ NGUYÊN bản gốc: vẫn đọc được, chỉ là chưa NFC. Gõ Unikey
    bình thường không sinh dấu trơ sau xuống dòng / mã thoát nên rất hiếm.
    """
    moi = unicodedata.normalize("NFC", s)
    if moi != s and s.lstrip()[:1] in ("{", "[", '"') and _la_json(s) and not _la_json(moi):
        return s
    return moi


# Khoá thuộc tính các cột chữ của từng mapper (tính một lần)
_COT_CHU: dict[Mapper, tuple[str, ...]] = {}


def _cot_chu(mapper: Mapper) -> tuple[str, ...]:
    kq = _COT_CHU.get(mapper)
    if kq is None:
        ds = []
        for prop in mapper.column_attrs:
            cot = prop.columns[0]
            # column_property biểu thức (không phải cột bảng) → bỏ; Enum là lớp con String
            # nhưng giá trị phải khớp đúng tập khai báo → không đụng
            if isinstance(cot, Column) and isinstance(cot.type, String) and not isinstance(cot.type, Enum):
                ds.append(prop.key)
        kq = _COT_CHU[mapper] = tuple(ds)
    return kq


@event.listens_for(Session, "before_flush")
def _chuan_hoa_truoc_flush(session: Session, _flush_context, _instances) -> None:
    for obj in session.new:
        state = sa_inspect(obj)
        gia_tri = state.dict
        for key in _cot_chu(state.mapper):
            v = gia_tri.get(key)
            if chua_nfc(v):
                ban_nfc = nfc_giu_json(v)
                if ban_nfc != v:
                    setattr(obj, key, ban_nfc)
    for obj in session.dirty:
        state = sa_inspect(obj)
        for key in _cot_chu(state.mapper):
            moi = state.attrs[key].history.added
            if moi and chua_nfc(moi[0]):
                ban_nfc = nfc_giu_json(moi[0])
                if ban_nfc != moi[0]:
                    setattr(obj, key, ban_nfc)


# ═══════════════════════════════════════════════════════════════════════════
# Dọn chữ ĐÃ LƯU — migration a28_2026b007 + quét lại một lần sau deploy
# ═══════════════════════════════════════════════════════════════════════════

def _cot_chu_bang(insp, bang: str) -> list[str]:
    """Cột kiểu chữ (varchar/text/char, trừ enum) của bảng, theo inspector. JSON/JSONB
    không phải kiểu chữ → không có trong danh sách."""
    return [
        c["name"] for c in insp.get_columns(bang)
        if isinstance(c["type"], String) and not isinstance(c["type"], Enum)
    ]


def _postgres(bind, bang: str, cot: list[str], kq: dict[str, int], log: logging.Logger | None = None) -> None:
    """Mỗi cột 1 câu UPDATE trong SAVEPOINT riêng — cột lỗi (vd trùng khoá unique) bị bỏ
    qua, ghi log, cột sau vẫn chạy."""
    log = log or logger
    q = bind.dialect.identifier_preparer.quote
    # `IS JSON` có từ Postgres 16 (prod 18.6, docker-compose 16). Chưa biết phiên bản (chưa
    # kết nối) → coi như mới. Bản cũ hơn → bỏ chốt JSON thay vì nổ cả cột.
    phien_ban = bind.dialect.server_version_info
    giu_json = phien_ban is None or tuple(phien_ban) >= (16,)
    for c in cot:
        ten = q(c)
        cau = (f"UPDATE {q(bang)} SET {ten} = normalize({ten}, NFC) "
               f"WHERE {ten} IS NOT NULL AND NOT ({ten} IS NFC NORMALIZED)")
        if giu_json:
            # Dòng đang là JSON hợp lệ mà bản NFC hết hợp lệ → để nguyên (xem nfc_giu_json)
            cau += f" AND (NOT ({ten} IS JSON) OR normalize({ten}, NFC) IS JSON)"
        try:
            with bind.begin_nested():  # SAVEPOINT: cột lỗi không làm hỏng cả giao dịch
                n = bind.execute(text(cau)).rowcount
        except Exception as exc:  # noqa: BLE001 — một cột lỗi không được chặn khởi động
            log.warning("[NFC] Bỏ qua %s.%s — %s: %s", bang, c, type(exc).__name__, exc)
            continue
        if n and n > 0:
            kq[f"{bang}.{c}"] = n


def _sqlite(bind, insp, bang: str, cot: list[str], kq: dict[str, int], log: logging.Logger) -> None:
    """SQLite (máy dev/test) không có normalize() → duyệt bằng Python theo khoá chính
    (không có thì rowid)."""
    q = bind.dialect.identifier_preparer.quote
    khoa = list(insp.get_pk_constraint(bang).get("constrained_columns") or [])
    ten_khoa = [q(k) for k in khoa] or ["rowid"]
    dong = bind.execute(text(
        f"SELECT {', '.join(ten_khoa + [q(c) for c in cot])} FROM {q(bang)}"
    )).fetchall()
    for r in dong:
        gia_tri_khoa, gia_tri_chu = r[:len(ten_khoa)], r[len(ten_khoa):]
        doi: dict[str, str] = {}
        for c, v in zip(cot, gia_tri_chu):
            if chua_nfc(v):
                ban_nfc = nfc_giu_json(v)
                if ban_nfc != v:
                    doi[c] = ban_nfc
        if not doi:
            continue
        tham_so = {f"m{i}": v for i, v in enumerate(doi.values())}
        tham_so.update({f"k{i}": v for i, v in enumerate(gia_tri_khoa)})
        dat = ", ".join(f"{q(c)} = :m{i}" for i, c in enumerate(doi))
        loc = " AND ".join(f"{k} = :k{i}" for i, k in enumerate(ten_khoa))
        try:
            # WHERE dùng khoá CŨ: khoá chính là chữ (vd gia_nhom_vat_tu.nhom) cũng được chuẩn hoá
            n = bind.execute(text(f"UPDATE {q(bang)} SET {dat} WHERE {loc}"), tham_so).rowcount
        except Exception as exc:  # noqa: BLE001 — SQLite chỉ huỷ câu lỗi, giao dịch vẫn dùng được
            log.warning("[NFC] Bỏ qua 1 dòng %s — %s: %s", bang, type(exc).__name__, exc)
            continue
        if n and n > 0:
            for c in doi:
                kq[f"{bang}.{c}"] = kq.get(f"{bang}.{c}", 0) + 1


def chuan_hoa_csdl(bind, log: logging.Logger | None = None) -> dict[str, int]:
    """Đưa mọi giá trị chữ chưa NFC (mọi bảng, trừ alembic_version) về NFC.

    `bind`: Connection đồng bộ (op.get_bind() của Alembic, hoặc AsyncConnection.run_sync).
    SQL thô → KHÔNG kích `onupdate` của ORM (updated_at giữ nguyên — kpi_engine đếm lead
    «được cập nhật trong kỳ» theo leads.updated_at). Chạy lại = chỉ đụng giá trị còn chưa
    NFC. Trả {"bảng.cột": số dòng đã sửa}.
    """
    log = log or logger
    insp = sa_inspect(bind)
    kq: dict[str, int] = {}
    for bang in sorted(insp.get_table_names()):
        if bang == "alembic_version":
            continue
        cot = _cot_chu_bang(insp, bang)
        if not cot:
            continue
        if bind.dialect.name == "postgresql":
            _postgres(bind, bang, cot, kq, log)
        else:
            try:
                _sqlite(bind, insp, bang, cot, kq, log)
            except Exception as exc:  # noqa: BLE001
                log.warning("[NFC] Bỏ qua bảng %s — %s: %s", bang, type(exc).__name__, exc)
    return kq


# Cờ trong system_settings: đã quét lại sau deploy → các lần khởi động sau bỏ qua
KHOA_QUET_LAI = "nfc_quet_lai_sau_deploy"
# Chờ bản CŨ tắt hẳn: Railway chuyển traffic khi /health bản mới qua rồi mới dừng bản cũ
CHO_QUET_LAI_GIAY = 300


async def quet_lai_sau_deploy(engine=None, session_factory=None,
                              cho_giay: float = CHO_QUET_LAI_GIAY) -> dict[str, int] | None:
    """Chạy lại `chuan_hoa_csdl` MỘT lần, sau khi bản có listener đã nhận traffic.

    Vì sao: start.sh chạy migration TRƯỚC uvicorn, còn Railway giữ bản CŨ (chưa có
    listener) phục vụ tới khi /health của bản mới qua. Chữ tổ hợp bản cũ ghi trong khoảng
    đó (người dùng sửa, thông báo worker nhúng bản cũ dựng) commit SAU câu UPDATE của cột
    → còn tổ hợp mãi (alembic_version đã qua a28, migration không chạy lại) → ô tìm kiếm
    (đã chuẩn hoá NFC) không ra, kể cả với chính người gõ. Hàm chỉ đụng giá trị chưa NFC.

    Chạy nền từ lifespan (production) để không làm chậm /health. Cờ `KHOA_QUET_LAI` có rồi
    → trả None ngay (không chờ, không quét). Quét xong mới ghi cờ: tiến trình bị dừng giữa
    chừng thì lần khởi động sau quét lại. Trả {"bảng.cột": số dòng đã sửa}.
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy.exc import IntegrityError

    from app.models.notification import SystemSetting

    if engine is None or session_factory is None:
        from app import database

        engine = engine or database.engine
        session_factory = session_factory or database.async_session

    async with session_factory() as db:
        if await db.get(SystemSetting, KHOA_QUET_LAI) is not None:
            return None
    if cho_giay > 0:
        await asyncio.sleep(cho_giay)
    async with engine.begin() as conn:
        kq = await conn.run_sync(chuan_hoa_csdl)
    async with session_factory() as db:
        if await db.get(SystemSetting, KHOA_QUET_LAI) is None:
            db.add(SystemSetting(key=KHOA_QUET_LAI, value=json.dumps({
                "luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "so_dong": sum(kq.values()), "cot": kq,
            }, ensure_ascii=False)))
            try:
                await db.commit()
            except IntegrityError:  # tiến trình khác (2 lần deploy sát nhau) vừa ghi cờ — coi như xong
                await db.rollback()
    return kq
