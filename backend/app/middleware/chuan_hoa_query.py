"""Chuẩn hoá NFC cho query string — ô tìm kiếm của MỌI client (21/11/2026).

Người gõ bằng bộ gõ «Unicode tổ hợp» gửi `?search=Trịnh` ở dạng NFD (chữ + dấu rời);
dữ liệu đã chuẩn hoá NFC → ILIKE / so bằng trượt. Middleware ASGI thuần:
- chỉ xét `scope["type"] == "http"` có query string chứa `%` (chữ có dấu luôn được
  client mã hoá %XX; chuỗi không có `%` toàn ASCII nên đã là NFC);
- giải mã %XX theo UTF-8 từng khoá/giá trị; mảnh nào chưa NFC → mã hoá lại bản NFC
  (khoảng trắng → «+», tương đương với cách Starlette đọc); mảnh đã NFC giữ NGUYÊN byte;
- giải mã lỗi (UTF-8 hỏng) hoặc có ký tự thay thế U+FFFD, hoặc query string có byte
  ngoài ASCII (client không mã hoá) → KHÔNG viết lại gì, đi nguyên byte;
- giữ thứ tự, khoá lặp, giá trị rỗng (`a=`), khoá không có dấu bằng (`a`).
KHÔNG đụng body: webhook ký HMAC trên byte gốc — chữ trong body chuẩn hoá tại chỗ so
khớp bằng `app.chuan_hoa_unicode.nfc`.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote_plus, unquote_to_bytes


class _KhongVietLai(Exception):
    pass


def _manh_nfc(manh: bytes) -> bytes:
    """Một khoá hoặc giá trị (byte gốc) → byte NFC; giữ nguyên nếu đã NFC."""
    if b"%" not in manh:
        return manh  # toàn ASCII (đã kiểm ở chuan_hoa_query) → luôn NFC
    try:
        chu = unquote_to_bytes(manh.replace(b"+", b" ")).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _KhongVietLai from exc
    if "�" in chu:
        raise _KhongVietLai
    if unicodedata.is_normalized("NFC", chu):
        return manh
    return quote_plus(unicodedata.normalize("NFC", chu), safe="").encode("ascii")


def chuan_hoa_query(qs: bytes) -> bytes | None:
    """Query string (byte gốc) → bản NFC; None nếu không cần / không được viết lại."""
    if not qs or b"%" not in qs or not qs.isascii():
        return None
    try:
        doan_moi: list[bytes] = []
        for doan in qs.split(b"&"):
            khoa, bang, gia_tri = doan.partition(b"=")
            moi = _manh_nfc(khoa)
            if bang:
                moi += b"=" + _manh_nfc(gia_tri)
            doan_moi.append(moi)
    except _KhongVietLai:
        return None
    moi_qs = b"&".join(doan_moi)
    return moi_qs if moi_qs != qs else None


class ChuanHoaQueryNFC:
    """ASGI middleware: viết lại `scope["query_string"]` khi có giá trị chưa NFC."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            moi = chuan_hoa_query(scope.get("query_string") or b"")
            if moi is not None:
                scope = dict(scope)
                scope["query_string"] = moi
        await self.app(scope, receive, send)
