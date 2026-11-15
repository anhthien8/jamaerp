"""HR handlers — nghỉ phép, bảng công, phiếu lương, tạm ứng, duyệt đơn.

Lệnh:
    /nghiphep                       — chọn nhanh bằng nút (1 ngày / nửa ngày) + số phép còn lại
    /nghiphep <từ> <đến> <lý do>   — xin nghỉ phép (dd/mm hoặc yyyy-mm-dd)
    /congcuatoi                     — bảng công tháng này
    /phieuluong                     — phiếu lương gần nhất (CHỈ chat riêng)
    /tamung <số tiền> <lý do>      — xin tạm ứng lương
    /choduyet                       — đơn chờ tôi duyệt (inline ✅/❌)
"""

import re
from datetime import date, datetime, timedelta, timezone

from aiogram import Router, types, F
from aiogram.filters import Command

from bot.api_client import api

router = Router()


def _parse_date(raw: str) -> str | None:
    """dd/mm | dd/mm/yyyy | yyyy-mm-dd -> 'yyyy-mm-dd'."""
    raw = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", raw)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year = int(m.group(3)) if m.group(3) else date.today().year
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _fmt_money(v: float) -> str:
    return f"{v:,.0f}đ"


# ---------------------------------------------------------------------------
# /nghiphep
# ---------------------------------------------------------------------------

_GIO_VN = timezone(timedelta(hours=7))  # máy chủ bot chạy UTC — «hôm nay» phải theo giờ Việt Nam
_THU = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật")
# buổi: f = cả ngày, s = buổi sáng, c = buổi chiều (backend chỉ có cờ half_day → sáng/chiều ghi vào lý do)
_BUOI = {"f": "cả ngày (1 ngày)", "s": "buổi sáng (0,5 ngày)", "c": "buổi chiều (0,5 ngày)"}
# mã lý do → (nhãn nút, leave_type, lý do ghi vào đơn)
_LY_DO = {
    "gd": ("Việc gia đình", "annual", "Việc gia đình"),
    "om": ("Khám bệnh / ốm", "sick", "Khám bệnh / ốm"),
    "cn": ("Việc cá nhân", "annual", "Việc cá nhân"),
    "kl": ("Nghỉ không lương", "unpaid", "Việc cá nhân (nghỉ không lương)"),
}
_LOAI = {"annual": "Phép năm", "sick": "Nghỉ ốm", "unpaid": "Nghỉ không lương"}


def _hoa_dau(s: str) -> str:
    return s[:1].upper() + s[1:]


def _hom_nay_vn() -> date:
    return datetime.now(_GIO_VN).date()


def _nut(text: str, data: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text=text, callback_data=data)


def _ban_phim_ngay(hom_nay: date, uid: int) -> types.InlineKeyboardMarkup:
    """Nút chọn ngày, ghi NGÀY THẬT lên nhãn và vào callback (`np:d:<yyyymmdd>:<buổi>:<uid>`)
    để tin cũ bấm lại không lệch ngày. Chủ nhật công ty nghỉ: ẩn nút hôm nay,
    «ngày mai» nhảy sang thứ Hai (backend không trừ Chủ nhật cho cả ngày nhưng
    nửa ngày thì vẫn trừ 0,5 → bot phải tự chặn)."""
    ke = hom_nay + timedelta(days=1)
    if ke.weekday() == 6:
        ke += timedelta(days=1)
    ten_ke = "Ngày mai" if ke == hom_nay + timedelta(days=1) else _hoa_dau(_THU[ke.weekday()])
    sang_ke = "Sáng mai" if ten_ke == "Ngày mai" else f"Sáng {_THU[ke.weekday()]}"
    hang = []
    if hom_nay.weekday() != 6:
        hang.append([_nut(f"Hôm nay {hom_nay:%d/%m}", f"np:d:{hom_nay:%Y%m%d}:f:{uid}")])
    hang.append([_nut(f"{ten_ke} {ke:%d/%m}", f"np:d:{ke:%Y%m%d}:f:{uid}")])
    hang.append([_nut(f"{sang_ke} {ke:%d/%m} (nửa ngày)", f"np:d:{ke:%Y%m%d}:s:{uid}")])
    if hom_nay.weekday() != 6:
        hang.append([_nut(f"Chiều nay {hom_nay:%d/%m} (nửa ngày)", f"np:d:{hom_nay:%Y%m%d}:c:{uid}")])
    hang.append([_nut("Hủy", f"np:huy:{uid}")])
    return types.InlineKeyboardMarkup(inline_keyboard=hang)


def _mo_ta_ngay(ngay: date, buoi: str) -> str:
    return f"{_hoa_dau(_THU[ngay.weekday()])} {ngay:%d/%m/%Y} — {_BUOI[buoi]}"


@router.message(Command("nghiphep"))
async def cmd_nghiphep(message: types.Message):
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        uid = message.from_user.id
        await api.authenticate(uid, message.from_user.username)
        so_du = await api.my_leave_balance(uid)
        dong_phep = ""
        if isinstance(so_du, dict) and so_du.get("annual_remaining") is not None:
            con = so_du["annual_remaining"]
            dong_phep = f"Còn <b>{con:g}</b>/{so_du.get('annual_total', 0):g} ngày phép năm.\n"
            if con < 0.5:
                dong_phep += "⚠️ Hết phép năm — ở bước lý do chọn «Nghỉ không lương» hoặc «Khám bệnh / ốm».\n"
        await message.answer(
            "🏖️ <b>Xin nghỉ phép</b>\n\n"
            f"{dong_phep}"
            "Bấm chọn ngày nghỉ bên dưới (1 ngày hoặc nửa ngày).\n\n"
            "Nghỉ nhiều ngày thì gõ:\n"
            "<code>/nghiphep [từ] [đến] [lý do]</code>\n"
            "Ví dụ: <code>/nghiphep 20/07 21/07 việc gia đình</code>\n\n"
            "💡 Đơn sẽ gửi leader duyệt.",
            reply_markup=_ban_phim_ngay(_hom_nay_vn(), uid),
        )
        return

    start = _parse_date(args[1])
    end = _parse_date(args[2])
    reason = args[3].strip()
    if not start or not end:
        await message.answer("❌ Ngày không hợp lệ. Dùng dạng <code>dd/mm</code> hoặc <code>yyyy-mm-dd</code>.")
        return

    await api.authenticate(message.from_user.id, message.from_user.username)
    result = await api.create_leave(message.from_user.id, {
        "leave_type": "annual",
        "start_date": start,
        "end_date": end,
        "reason": reason,
    })
    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        return
    if result.get("error"):
        await message.answer(f"❌ {result['error']}")
        return

    leave = result.get("leave", {})
    await message.answer(
        f"✅ <b>Đã gửi đơn nghỉ phép!</b>\n\n"
        f"📅 {leave.get('start_date')} → {leave.get('end_date')} ({leave.get('days')} ngày)\n"
        f"📝 {leave.get('reason')}\n\n"
        f"⏳ Đơn đang chờ duyệt — bạn sẽ nhận thông báo khi có kết quả."
    )


@router.callback_query(F.data.startswith("np:"))
async def on_nghi_phep_nhanh(callback: types.CallbackQuery):
    """Chọn ngày → chọn lý do → xác nhận → «Gửi đơn». Không FSM: mọi thứ nằm trong
    callback_data, phần cuối là Telegram ID người đã gõ lệnh (trong nhóm, người
    khác bấm sẽ bị chặn — đơn luôn tạo cho callback.from_user)."""
    parts = callback.data.split(":")
    buoc, uid = parts[1] if len(parts) > 1 else "", parts[-1]
    if uid != str(callback.from_user.id):
        await callback.answer("Nút này của người khác. Gõ /nghiphep để tạo đơn của bạn.", show_alert=True)
        return

    async def sua(text: str, ban_phim: types.InlineKeyboardMarkup | None = None) -> None:
        try:
            await callback.message.edit_text(text, reply_markup=ban_phim)
        except Exception:
            pass

    if buoc == "huy":
        await callback.answer("Đã hủy")
        await sua("🚫 Đã hủy xin nghỉ phép.")
        return

    try:
        ngay = datetime.strptime(parts[2], "%Y%m%d").date()
        buoi = parts[3]
        ly_do = _LY_DO[parts[4]] if buoc in ("r", "ok") else None
        if buoi not in _BUOI or len(parts) != (5 if buoc == "d" else 6):
            raise ValueError
    except (ValueError, IndexError, KeyError):
        await callback.answer("Dữ liệu không hợp lệ", show_alert=True)
        return
    if ngay < _hom_nay_vn() or ngay.weekday() == 6:
        await callback.answer("Nút này đã cũ. Gõ /nghiphep để chọn lại ngày.", show_alert=True)
        return
    goc = f"{parts[2]}:{buoi}"

    if buoc == "d":
        await callback.answer()
        await sua(
            f"🏖️ <b>Xin nghỉ phép</b>\n\n📅 {_mo_ta_ngay(ngay, buoi)}\n\nChọn lý do:",
            types.InlineKeyboardMarkup(inline_keyboard=[
                *[[_nut(nhan, f"np:r:{goc}:{ma}:{uid}")] for ma, (nhan, _, _) in _LY_DO.items()],
                [_nut("Hủy", f"np:huy:{uid}")],
            ]),
        )
        return

    _, loai, ly_do_text = ly_do
    if buoc == "r":
        await callback.answer()
        await sua(
            "🏖️ <b>Xác nhận đơn nghỉ phép</b>\n\n"
            f"📅 {_mo_ta_ngay(ngay, buoi)}\n"
            f"Loại: <b>{_LOAI[loai]}</b>\n"
            f"📝 {ly_do_text}\n\n"
            "Bấm «Gửi đơn» để gửi leader duyệt.",
            types.InlineKeyboardMarkup(inline_keyboard=[[
                _nut("Gửi đơn", f"np:ok:{goc}:{parts[4]}:{uid}"),
                _nut("Hủy", f"np:huy:{uid}"),
            ]]),
        )
        return
    if buoc != "ok":
        await callback.answer("Dữ liệu không hợp lệ", show_alert=True)
        return

    await callback.answer("Đang gửi đơn…")
    try:  # gỡ nút trước khi gọi API → bấm đúp không tạo hai đơn (backend cũng chặn trùng)
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if buoi != "f":
        ly_do_text = f"Nghỉ {'buổi sáng' if buoi == 's' else 'buổi chiều'} — {ly_do_text}"
    await api.authenticate(callback.from_user.id, callback.from_user.username)
    result = await api.create_leave(callback.from_user.id, {
        "leave_type": loai,
        "start_date": ngay.isoformat(),
        "end_date": ngay.isoformat(),
        "half_day": buoi != "f",
        "reason": ly_do_text,
    })
    if not result:
        await sua("❌ Không kết nối được server. Gõ /nghiphep để thử lại.")
        return
    if result.get("error"):
        await sua(f"❌ {result['error']}")
        return
    leave = result.get("leave", {})
    await sua(
        f"✅ <b>Đã gửi đơn nghỉ phép!</b>\n\n"
        f"📅 {leave.get('start_date')} → {leave.get('end_date')} ({leave.get('days')} ngày) · {_LOAI[loai]}\n"
        f"📝 {leave.get('reason')}\n\n"
        f"⏳ Đơn đang chờ duyệt — bạn sẽ nhận thông báo khi có kết quả."
    )


# ---------------------------------------------------------------------------
# /congcuatoi
# ---------------------------------------------------------------------------

@router.message(Command("congcuatoi"))
async def cmd_congcuatoi(message: types.Message):
    await api.authenticate(message.from_user.id, message.from_user.username)
    result = await api.my_attendance_summary(message.from_user.id)
    if not result:
        await message.answer("❌ Không kết nối được server.")
        return
    if result.get("error"):
        await message.answer(f"❌ {result['error']}")
        return

    review = result.get("needs_review", 0)
    review_line = f"\n⚠️ Ca cần xác nhận (quên checkout): {review}" if review else ""
    await message.answer(
        f"📊 <b>Bảng công {result.get('period')}</b> — {result.get('user')}\n\n"
        f"✅ Công: <b>{result.get('work_days_fraction')}</b> ngày\n"
        f"🕐 Tổng giờ: {result.get('total_hours')}h\n"
        f"⏰ OT đã duyệt: {result.get('ot_approved_hours')}h{review_line}"
    )


# ---------------------------------------------------------------------------
# /phieuluong — CHỈ chat riêng (bảo mật lương)
# ---------------------------------------------------------------------------

@router.message(Command("phieuluong"))
async def cmd_phieuluong(message: types.Message):
    if message.chat.type != "private":
        await message.answer("🔒 Phiếu lương chỉ xem được trong <b>chat riêng</b> với bot — nhắn riêng cho mình nhé.")
        return

    await api.authenticate(message.from_user.id, message.from_user.username)
    result = await api.my_payslips(message.from_user.id)
    if not result:
        await message.answer("❌ Không kết nối được server.")
        return
    if result.get("error"):
        await message.answer(f"❌ {result['error']}")
        return

    items = result.get("items", [])
    if not items:
        await message.answer("📭 Chưa có phiếu lương nào (chỉ hiển thị các kỳ đã chi).")
        return

    p = items[0]
    lines = [
        f"🧾 <b>Phiếu lương kỳ {p['period']}</b>",
        "",
        f"Lương cơ bản: {_fmt_money(p['base_salary'])}",
        f"Công: {p['work_days']:g}/{p['standard_days']:g} ngày",
    ]
    if p.get("ot_pay"):
        lines.append(f"Tăng ca ({p['ot_hours']:g}h): +{_fmt_money(p['ot_pay'])}")
    if p.get("commission_total"):
        lines.append(f"Hoa hồng: +{_fmt_money(p['commission_total'])}")
    if p.get("bonus"):
        lines.append(f"Thưởng: +{_fmt_money(p['bonus'])}")
    if p.get("allowance"):
        lines.append(f"Phụ cấp: +{_fmt_money(p['allowance'])}")
    lines += [
        f"Gross: <b>{_fmt_money(p['gross_salary'])}</b>",
        "",
        f"BHXH/BHYT/BHTN: −{_fmt_money(p['bhxh_employee'])}",
        f"Thuế TNCN: −{_fmt_money(p['pit'])}",
    ]
    if p.get("advance_deduction"):
        lines.append(f"Trừ tạm ứng: −{_fmt_money(p['advance_deduction'])}")
    if p.get("deductions"):
        lines.append(f"Khấu trừ khác: −{_fmt_money(p['deductions'])}")
    lines += ["", f"💵 <b>THỰC LĨNH: {_fmt_money(p['net_salary'])}</b>"]
    if len(items) > 1:
        lines.append(f"\n<i>(Xem {len(items)} kỳ gần nhất trên web → Chấm công → Phiếu lương)</i>")

    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# /tamung
# ---------------------------------------------------------------------------

@router.message(Command("tamung"))
async def cmd_tamung(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "💸 <b>Xin tạm ứng lương</b>\n\n"
            "Cách dùng:\n"
            "<code>/tamung [số tiền] [lý do]</code>\n\n"
            "Ví dụ: <code>/tamung 2000000 đóng học phí cho con</code>\n\n"
            "💡 Tối đa 30% lương cơ bản. Trừ vào kỳ lương kế tiếp."
        )
        return

    raw_amount = args[1].replace(".", "").replace(",", "").replace("đ", "").replace("d", "")
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer("❌ Số tiền không hợp lệ. Ví dụ: <code>/tamung 2000000 lý do</code>")
        return

    await api.authenticate(message.from_user.id, message.from_user.username)
    result = await api.create_advance(message.from_user.id, amount, args[2].strip())
    if not result:
        await message.answer("❌ Không kết nối được server.")
        return
    if result.get("error"):
        await message.answer(f"❌ {result['error']}")
        return

    await message.answer(
        f"✅ <b>Đã gửi đơn tạm ứng {_fmt_money(amount)}</b>\n\n"
        f"⏳ Kế toán sẽ duyệt trong 48h — bạn sẽ nhận thông báo khi có kết quả."
    )


# ---------------------------------------------------------------------------
# /choduyet — danh sách đơn chờ tôi duyệt (inline buttons)
# ---------------------------------------------------------------------------

@router.message(Command("choduyet"))
async def cmd_choduyet(message: types.Message):
    await api.authenticate(message.from_user.id, message.from_user.username)
    result = await api.pending_approvals(message.from_user.id)
    if not result:
        await message.answer("❌ Không kết nối được server.")
        return
    if result.get("error"):
        await message.answer(f"❌ {result['error']}")
        return

    items = result.get("items", [])
    if not items:
        await message.answer("🎉 Không có đơn nào chờ bạn duyệt.")
        return

    await message.answer(f"📋 <b>{len(items)} đơn chờ bạn duyệt:</b>")
    for item in items[:10]:
        amount_line = f"\n💰 {_fmt_money(item['amount'])}" if item.get("amount") else ""
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text="✅ Duyệt", callback_data=f"apr:a:{item['id']}"),
            types.InlineKeyboardButton(text="❌ Từ chối", callback_data=f"apr:r:{item['id']}"),
        ]])
        await message.answer(
            f"<b>[{item['type_label']}]</b> {item['title']}{amount_line}\n"
            f"👤 {item.get('requester_name', '')} · cấp {item['step']}/{item['total_steps']}",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("apr:"))
async def on_approval_action(callback: types.CallbackQuery):
    try:
        _, action, request_id = callback.data.split(":", 2)
    except ValueError:
        await callback.answer("Dữ liệu không hợp lệ", show_alert=True)
        return

    await api.authenticate(callback.from_user.id, callback.from_user.username)
    if action == "a":
        result = await api.approve_generic(callback.from_user.id, request_id)
        verb = "duyệt"
    else:
        result = await api.reject_generic(callback.from_user.id, request_id, "Từ chối qua Telegram")
        verb = "từ chối"

    if not result:
        await callback.answer("Không kết nối được server", show_alert=True)
        return
    if result.get("error"):
        await callback.answer(result["error"], show_alert=True)
        return

    request = result.get("request", {})
    status = request.get("status")
    if status == "pending":
        note = f"✅ Đã duyệt cấp {request.get('step', 1) - 1} — chuyển tiếp cấp {request.get('step')}/{request.get('total_steps')}."
    else:
        note = f"{'✅ Đã duyệt' if action == 'a' else '❌ Đã từ chối'} bởi {result.get('actor', '')} lúc {datetime.now().strftime('%H:%M')}."

    # Cập nhật tin nhắn gốc: bỏ nút, thêm kết quả
    try:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{note}",
            reply_markup=None,
        )
    except Exception:
        pass
    await callback.answer(f"Đã {verb}!")
