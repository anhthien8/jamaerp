"""Nút «việc tiếp theo» (nx:<lệnh>:<MÃ>) dưới thẻ /duan, tin điểm danh, tin báo cáo."""

from unittest.mock import AsyncMock

import pytest

from bot.handlers import checkin_out, incident, material_request, site_report
from bot.handlers.site_report import cb_tiep_theo, nut_tiep_theo
from conftest import bam, chay, nhan_nut, tin


def test_bon_nut_mang_ma_du_an():
    nut = nhan_nut(nut_tiep_theo("JMH-0601", tin()))
    assert [d for _, d in nut] == [
        "nx:baocao:JMH-0601", "nx:suco:JMH-0601", "nx:vatlieu:JMH-0601", "nx:checkout:JMH-0601",
    ]
    assert all(len(d.encode()) <= 64 for _, d in nut)


def test_trong_nhom_an_tan_ca_va_bo_nut_theo_yeu_cau():
    nhom = [d for _, d in nhan_nut(nut_tiep_theo("JMH-0601", tin(chat_type="supergroup")))]
    assert "nx:checkout:JMH-0601" not in nhom and len(nhom) == 3
    sau_bao_cao = [d for _, d in nhan_nut(nut_tiep_theo("JMH-0601", tin(), bo=("baocao",)))]
    assert "nx:baocao:JMH-0601" not in sau_bao_cao and "nx:checkout:JMH-0601" in sau_bao_cao
    assert nut_tiep_theo("", tin()) is None


@pytest.mark.parametrize("cmd,state_mong", [
    ("baocao", site_report.SiteReportState.waiting_content),
    ("suco", incident.IncidentState.waiting_description),
    ("vatlieu", material_request.VatTuState.waiting_item),
    ("checkout", checkin_out.CheckoutState.waiting_location),
])
def test_bam_nut_vao_thang_luong_khong_sua_the(state, cmd, state_mong):
    async def kich_ban():
        await state.update_data(rac="luồng cũ")
        cb = bam(f"nx:{cmd}:JMH-0601")
        await cb_tiep_theo(cb, state)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_not_awaited()  # thẻ dự án còn nguyên
        cb.message.answer.assert_awaited_once()
        assert "JMH-0601" in cb.message.answer.await_args.args[0]
        assert await state.get_state() == state_mong.state
        data = await state.get_data()
        assert data["project_code"] == "JMH-0601" and "rac" not in data
    chay(kich_ban())


def test_nut_hong_thi_bo_qua(state):
    async def kich_ban():
        cb = bam("nx:baocao")
        await cb_tiep_theo(cb, state)
        cb.message.answer.assert_not_awaited()
        assert await state.get_state() is None
    chay(kich_ban())


def test_the_du_an_va_tin_diem_danh_co_nut(state, monkeypatch):
    async def kich_ban():
        monkeypatch.setattr(site_report.api, "get_project", AsyncMock(return_value={
            "project": {"code": "JMH-0601", "name": "Nhà A"}, "tasks_summary": {}, "team": {},
        }))
        m = tin()
        await site_report.hien_du_an(m, 111, "jmh-0601")
        the = m.answer.await_args_list[-1]
        assert "nx:baocao:JMH-0601" in [d for _, d in nhan_nut(the.kwargs["reply_markup"])]

        monkeypatch.setattr(checkin_out.api, "checkin", AsyncMock(return_value={
            "project_code": "JMH-0601", "user": "A", "checkin_time": "08:00", "message": "ok",
        }))
        await state.update_data(project_code="JMH-0601")
        m = tin()
        m.location = type("L", (), {"latitude": 10.0, "longitude": 106.0})()
        await checkin_out.process_checkin_location(m, state)
        cuoi = m.answer.await_args_list[-1]
        assert "Điểm danh thành công" in cuoi.args[0]
        assert len(nhan_nut(cuoi.kwargs["reply_markup"])) == 4
    chay(kich_ban())
