"""/vatlieu nhận nhiều dòng: xem trước → «Gửi N dòng» → một tin tổng kết."""

from unittest.mock import AsyncMock

from bot.handlers import material_request as mr
from bot.handlers.material_request import VatTuState
from conftest import bam, chay, nhan_nut, tin

DS = "- Xi măng Portland - 50 bao\n2. Sắt phi 12 - 200 kg\n\ndòng sai mẫu\n• Ống PVC 27 - 10,5 cây"


def test_bo_dau_dong():
    assert mr._bo_dau_dong("- Xi măng - 5 bao") == "Xi măng - 5 bao"
    assert mr._bo_dau_dong("1) Cát - 2 m3") == "Cát - 2 m3"
    assert mr._bo_dau_dong("2.5mm dây điện - 3 cuộn") == "2.5mm dây điện - 3 cuộn"


def test_mot_dong_giu_luong_cu(state, monkeypatch):
    async def kich_ban():
        gui = AsyncMock()
        monkeypatch.setattr(mr, "gui_vat_tu", gui)
        await state.update_data(project_code="JMH-0601")
        await state.set_state(VatTuState.waiting_item)
        m = tin("Xi măng Portland - 50 bao")
        await mr.nhan_vat_tu(m, state)
        gui.assert_awaited_once_with(m, 111, "JMH-0601 Xi măng Portland - 50 bao")
        assert await state.get_state() is None
    chay(kich_ban())


def test_nhieu_dong_xem_truoc_roi_gui(state, monkeypatch):
    async def kich_ban():
        tao = AsyncMock(side_effect=[
            {"request_id": "a", "over_budget": True, "estimated_cost": 9_000_000},
            {"error": "Dự án đã đóng"},
            None,
        ])
        monkeypatch.setattr(mr.api, "create_material_request", tao)
        await state.update_data(project_code="JMH-0601")
        await state.set_state(VatTuState.waiting_item)

        m = tin(DS)
        await mr.nhan_vat_tu(m, state)
        tao.assert_not_awaited()  # chưa bấm thì chưa ghi gì
        xem = m.answer.await_args
        assert "Đọc được 3 dòng" in xem.args[0] and "dòng sai mẫu" in xem.args[0]
        assert "10.5 cây" in xem.args[0]
        assert nhan_nut(xem.kwargs["reply_markup"])[0] == ("Gửi 3 dòng", "vt_batch:send")
        assert await state.get_state() == VatTuState.confirm_batch.state

        cb = bam("vt_batch:send", uid=222)
        await mr.cb_gui_nhieu_dong(cb, state)
        assert tao.await_count == 3
        tg, payload = tao.await_args_list[0].args
        assert tg == 222 and payload == {
            "project_code": "JMH-0601", "material_name": "Xi măng Portland",
            "quantity": 50.0, "unit": "bao", "requester_tg_id": 222,
        }
        tong = cb.message.edit_text.await_args
        assert "Đã gửi 1/3 dòng" in tong.args[0] and "vượt định mức" in tong.args[0]
        assert "2 dòng CHƯA gửi được" in tong.args[0] and "Dự án đã đóng" in tong.args[0]
        assert "9" not in tong.args[0].replace("JMH-0601", "")  # không in số tiền
        assert nhan_nut(tong.kwargs["reply_markup"]) == [("Thêm vật tư cho JMH-0601", "vt_more:JMH-0601")]
        assert await state.get_state() is None  # bấm lần hai không còn gì để gửi
    chay(kich_ban())


def test_toan_dong_sai_va_qua_gioi_han(state, monkeypatch):
    async def kich_ban():
        await state.update_data(project_code="JMH-0601")
        await state.set_state(VatTuState.waiting_item)
        m = tin("abc\nxyz")
        await mr.nhan_vat_tu(m, state)
        assert "Chưa dòng nào đúng mẫu" in m.answer.await_args.args[0]
        m = tin("\n".join(f"Vật tư {i} - {i + 1} cái" for i in range(mr.MAX_DONG + 1)))
        await mr.nhan_vat_tu(m, state)
        assert "tối đa" in m.answer.await_args.args[0]
        assert await state.get_state() == VatTuState.waiting_item.state
    chay(kich_ban())


def test_them_vat_tu_cho_dung_du_an(state):
    async def kich_ban():
        cb = bam("vt_more:JMH-0601")
        await mr.cb_them_vat_tu(cb, state)
        assert await state.get_state() == VatTuState.waiting_item.state
        assert (await state.get_data())["project_code"] == "JMH-0601"
        cb.message.edit_text.assert_not_awaited()
    chay(kich_ban())
