"""Chữ gõ bằng bộ gõ «Unicode tổ hợp» (NFD) vẫn khớp chữ hằng của bot (21/11/2026).

Bot không ghi DB, chỉ gọi API backend (backend tự chuẩn hoá NFC khi ghi/tìm) — hai chỗ
bot tự so chữ người gõ với chữ hằng phải chuẩn hoá NFC trước khi so.
"""

import unicodedata

from bot.handlers import lead_intake
from bot.handlers.site_report import _la_tu_xong
from conftest import chay, tin


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def test_go_to_hop_khac_byte_voi_dung_san():
    assert nfd("gửi") != "gửi" and nfd("Chị") != "Chị"


def test_tu_xong_go_to_hop_van_khop():
    assert _la_tu_xong(nfd("gửi"))
    assert _la_tu_xong(nfd(" Gửi@jama_bot "))
    assert _la_tu_xong("xong")
    assert not _la_tu_xong(nfd("gửi báo giá phần thô"))
    assert not _la_tu_xong(None)


def test_tin_lead_go_to_hop_van_nhan_dien(state, monkeypatch):
    da_chuyen = []

    async def _phan_tich(message, st):
        da_chuyen.append(message)

    monkeypatch.setattr(lead_intake, "process_lead_text", _phan_tich)
    m = tin(nfd("Chị Hạnh cần thiết kế căn hộ 80m2 ở quận 7, ngân sách khoảng 500 triệu"))
    chay(lead_intake.auto_parse_message(m, state))
    assert da_chuyen, "tin có «Chị» dạng tổ hợp phải được chuyển sang luồng phân tích lead"
    m.answer.assert_not_awaited()
