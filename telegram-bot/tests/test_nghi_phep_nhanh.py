"""/nghiphep không tham số: số phép còn lại + nút chọn ngày → lý do → «Gửi đơn»."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from bot.handlers import hr
from conftest import bam, chay, nhan_nut, tin

THU_BAY = date(2026, 11, 14)
CHU_NHAT = date(2026, 11, 15)
THU_HAI = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _api(monkeypatch):
    monkeypatch.setattr(hr.api, "authenticate", AsyncMock())
    monkeypatch.setattr(hr.api, "my_leave_balance", AsyncMock(return_value={"annual_remaining": 7.5, "annual_total": 12}))
    monkeypatch.setattr(hr.api, "create_leave", AsyncMock(return_value={
        "leave": {"start_date": "2026-11-17", "end_date": "2026-11-17", "days": 0.5, "reason": "x"},
    }))
    monkeypatch.setattr(hr, "_hom_nay_vn", lambda: THU_HAI)


def test_ban_phim_ngay_thuong():
    nut = nhan_nut(hr._ban_phim_ngay(THU_HAI, 111))
    assert nut[:4] == [
        ("Hôm nay 16/11", "np:d:20261116:f:111"),
        ("Ngày mai 17/11", "np:d:20261117:f:111"),
        ("Sáng mai 17/11 (nửa ngày)", "np:d:20261117:s:111"),
        ("Chiều nay 16/11 (nửa ngày)", "np:d:20261116:c:111"),
    ]


def test_chu_nhat_khong_bao_gio_len_nut():
    # Thứ Bảy: «ngày mai» là Chủ nhật → nhảy sang thứ Hai
    t7 = nhan_nut(hr._ban_phim_ngay(THU_BAY, 111))
    assert ("Thứ Hai 16/11", "np:d:20261116:f:111") in t7
    assert ("Sáng thứ Hai 16/11 (nửa ngày)", "np:d:20261116:s:111") in t7
    # Chủ nhật: không có nút hôm nay / chiều nay
    cn = [d for _, d in nhan_nut(hr._ban_phim_ngay(CHU_NHAT, 111))]
    assert cn == ["np:d:20261116:f:111", "np:d:20261116:s:111", "np:huy:111"]
    for ngay in (THU_BAY, CHU_NHAT, THU_HAI):
        for _, d in nhan_nut(hr._ban_phim_ngay(ngay, 9_999_999_999)):
            assert len(d.encode()) <= 64 and "20261115" not in d


def test_lenh_trong_hien_so_phep_va_nut():
    async def kich_ban():
        m = tin("/nghiphep")
        await hr.cmd_nghiphep(m)
        goi = m.answer.await_args
        assert "Còn <b>7.5</b>/12 ngày phép năm" in goi.args[0]
        assert "/nghiphep [từ] [đến] [lý do]" in goi.args[0]  # cú pháp cũ vẫn được nhắc
        assert nhan_nut(goi.kwargs["reply_markup"])[0][1] == "np:d:20261116:f:111"
        hr.api.create_leave.assert_not_awaited()

        hr.api.my_leave_balance.return_value = {"annual_remaining": 0, "annual_total": 12}
        m = tin("/nghiphep")
        await hr.cmd_nghiphep(m)
        assert "Hết phép năm" in m.answer.await_args.args[0]

        hr.api.my_leave_balance.return_value = None  # lỗi tra số dư không chặn việc xin nghỉ
        m = tin("/nghiphep")
        await hr.cmd_nghiphep(m)
        assert "reply_markup" in m.answer.await_args.kwargs
    chay(kich_ban())


def test_cu_phap_go_tay_giu_nguyen():
    async def kich_ban():
        m = tin("/nghiphep 20/11 21/11 việc gia đình")
        await hr.cmd_nghiphep(m)
        hr.api.create_leave.assert_awaited_once_with(111, {
            "leave_type": "annual", "start_date": "2026-11-20", "end_date": "2026-11-21", "reason": "việc gia đình",
        })
    chay(kich_ban())


def test_ba_buoc_roi_moi_gui_don():
    async def kich_ban():
        cb = bam("np:d:20261117:s:111")
        await hr.on_nghi_phep_nhanh(cb)
        b1 = cb.message.edit_text.await_args
        assert "Thứ Ba 17/11/2026 — buổi sáng (0,5 ngày)" in b1.args[0]
        assert ("Khám bệnh / ốm", "np:r:20261117:s:om:111") in nhan_nut(b1.kwargs["reply_markup"])

        cb = bam("np:r:20261117:s:om:111")
        await hr.on_nghi_phep_nhanh(cb)
        b2 = cb.message.edit_text.await_args
        assert "Nghỉ ốm" in b2.args[0]
        assert nhan_nut(b2.kwargs["reply_markup"])[0] == ("Gửi đơn", "np:ok:20261117:s:om:111")
        hr.api.create_leave.assert_not_awaited()  # chưa bấm «Gửi đơn» thì chưa tạo đơn

        cb = bam("np:ok:20261117:s:om:111")
        await hr.on_nghi_phep_nhanh(cb)
        hr.api.create_leave.assert_awaited_once_with(111, {
            "leave_type": "sick", "start_date": "2026-11-17", "end_date": "2026-11-17",
            "half_day": True, "reason": "Nghỉ buổi sáng — Khám bệnh / ốm",
        })
        cb.message.edit_reply_markup.assert_awaited_once()  # gỡ nút chống bấm đúp
        assert "Đã gửi đơn nghỉ phép" in cb.message.edit_text.await_args.args[0]
    chay(kich_ban())


@pytest.mark.parametrize("ma,loai,ly_do", [
    ("gd", "annual", "Việc gia đình"),
    ("cn", "annual", "Việc cá nhân"),
    ("kl", "unpaid", "Việc cá nhân (nghỉ không lương)"),
])
def test_ca_ngay_theo_ly_do(ma, loai, ly_do):
    async def kich_ban():
        await hr.on_nghi_phep_nhanh(bam(f"np:ok:20261116:f:{ma}:111"))
        hr.api.create_leave.assert_awaited_once_with(111, {
            "leave_type": loai, "start_date": "2026-11-16", "end_date": "2026-11-16",
            "half_day": False, "reason": ly_do,
        })
    chay(kich_ban())


@pytest.mark.parametrize("data,uid", [
    ("np:ok:20261117:s:om:111", 222),   # người khác bấm trong nhóm
    ("np:ok:20261113:f:gd:111", 111),   # nút cũ: ngày đã qua
    ("np:ok:20261122:c:gd:111", 111),   # Chủ nhật (nửa ngày sẽ bị trừ 0,5 phép oan)
    ("np:ok:20261117:x:gd:111", 111),   # buổi lạ
    ("np:ok:20261117:s:zz:111", 111),   # lý do lạ
    ("np:ok:abc:s:gd:111", 111),
    ("np:d:20261117:s:gd:111", 111),    # thừa phần
])
def test_khong_tao_don_khi_nut_sai(data, uid):
    async def kich_ban():
        cb = bam(data, uid=uid)
        await hr.on_nghi_phep_nhanh(cb)
        hr.api.create_leave.assert_not_awaited()
        assert cb.answer.await_args.kwargs.get("show_alert") is True
    chay(kich_ban())


def test_loi_server_hien_ra_va_huy():
    async def kich_ban():
        hr.api.create_leave.return_value = {"error": "Không đủ phép năm"}
        cb = bam("np:ok:20261116:f:gd:111")
        await hr.on_nghi_phep_nhanh(cb)
        assert "Không đủ phép năm" in cb.message.edit_text.await_args.args[0]

        cb = bam("np:huy:111")
        await hr.on_nghi_phep_nhanh(cb)
        assert "Đã hủy" in cb.message.edit_text.await_args.args[0]
    chay(kich_ban())
