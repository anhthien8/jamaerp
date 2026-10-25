"""Nhập danh mục mẫu vật tư từ Google Sheet công khai (25/10/2026).

Sheet của JAMA: 12 tab theo kích thước gạch (30X30, 60x60, 60x120, Bông gió…),
cột STT · MÃ (NẾU CÓ) · THƯƠNG HIỆU · HÌNH ẢNH · TÍNH CHẤT · TÌNH TRẠNG ·
ĐƠN GIÁ (M2) · NCC · GHI CHÚ · LINK MAP. Tên tab = nhóm vật tư.

Chỉ cần sheet «Bất kỳ ai có liên kết đều xem được» — đọc qua htmlview để lấy
danh sách tab, rồi export CSV từng tab. Không cần Google API/credential.
"""

from __future__ import annotations

import csv
import io
import re

import httpx

_RE_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_RE_TAB = re.compile(r'items\.push\(\{name:\s*"((?:[^"\\]|\\.)*)"[^}]*?gid:\s*"?(\d+)"?', re.S)


class SheetError(Exception):
    pass


def lay_id_sheet(url: str) -> str:
    m = _RE_ID.search(url or "")
    if not m:
        raise SheetError("Link Google Sheet không hợp lệ")
    return m.group(1)


def _doc_gia(s: str) -> float | None:
    """'280,000' / '280.000đ' / '280000' → 280000. Trả None nếu không có số."""
    so = re.sub(r"[^\d]", "", s or "")
    return float(so) if so else None


def _o(row: dict, *ten: str) -> str:
    """Lấy ô theo tên cột, bỏ dấu cách/hoa thường; thử lần lượt nhiều tên."""
    chuan = {re.sub(r"\s+", " ", (k or "")).strip().upper(): (v or "").strip() for k, v in row.items()}
    for t in ten:
        for k, v in chuan.items():
            if k.startswith(t.upper()):
                return v
    return ""


def doc_csv(noi_dung: str, nhom: str) -> list[dict]:
    """CSV một tab → danh sách mẫu (dict khớp cột MauVatTu). Bỏ dòng không có mã."""
    reader = csv.DictReader(io.StringIO(noi_dung))
    ket_qua: list[dict] = []
    for row in reader:
        # Ô mã đôi khi xuống dòng ghi 2 mã (6A01⏎6A02) → nối bằng « / » cho sạch
        ma = " / ".join(p.strip() for p in _o(row, "MÃ").splitlines() if p.strip())
        hang = " ".join(_o(row, "THƯƠNG HIỆU", "HÃNG").split())
        if ma.upper() in ("MÃ", "MÃ (NẾU CÓ)"):
            continue
        if not ma:
            # Sheet có dòng chỉ ghi hãng (Viglacera, China…) chưa có mã → vẫn giữ để chọn
            if not hang:
                continue
            ma = f"{' '.join(hang.split())} (chưa có mã)"
            hang = " ".join(hang.split())
        ket_qua.append({
            "ma": ma[:100],
            "hang": hang[:100] or None,
            "nhom": nhom[:100],
            "be_mat": (_o(row, "TÍNH CHẤT", "BỀ MẶT")[:50] or None),
            "tinh_trang": (_o(row, "TÌNH TRẠNG")[:100] or None),
            "gia_tham_khao": _doc_gia(_o(row, "ĐƠN GIÁ", "GIÁ")),
            "ncc_gan_nhat_ten": (_o(row, "NCC", "NHÀ CUNG CẤP")[:255] or None),
            "ghi_chu": (_o(row, "GHI CHÚ") or None),
            "anh_url": (_o(row, "HÌNH ẢNH", "ẢNH")[:500] or None),
        })
    return ket_qua


async def tai_tabs(sheet_id: str, client: httpx.AsyncClient) -> list[tuple[str, str]]:
    """[(tên tab, gid)] từ trang htmlview."""
    r = await client.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/htmlview", follow_redirects=True)
    if r.status_code != 200:
        raise SheetError("Không đọc được sheet — kiểm tra đã chia sẻ «Bất kỳ ai có liên kết»")
    tabs = [(bytes(n, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\u" in n else n, g)
            for n, g in _RE_TAB.findall(r.text)]
    return tabs or [("Khác", "0")]


async def tai_csv(sheet_id: str, gid: str, client: httpx.AsyncClient) -> str:
    r = await client.get(
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export", params={"format": "csv", "gid": gid},
        follow_redirects=True,
    )
    if r.status_code != 200:
        raise SheetError(f"Không tải được tab gid={gid}")
    return r.content.decode("utf-8-sig", errors="replace")


async def doc_sheet(url: str, bo_qua_tab: tuple[str, ...] = ("FROM", "FORM")) -> list[dict]:
    """Đọc toàn bộ sheet → danh sách mẫu (chưa ghi DB)."""
    sheet_id = lay_id_sheet(url)
    async with httpx.AsyncClient(timeout=30) as client:
        tabs = await tai_tabs(sheet_id, client)
        tat_ca: list[dict] = []
        for ten, gid in tabs:
            if ten.strip().upper() in bo_qua_tab:
                continue
            tat_ca.extend(doc_csv(await tai_csv(sheet_id, gid, client), ten.strip()))
    return tat_ca
