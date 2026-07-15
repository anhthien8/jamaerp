"""HR handlers — nghỉ phép, bảng công, phiếu lương, tạm ứng, duyệt đơn.

Lệnh:
    /nghiphep <từ> <đến> <lý do>   — xin nghỉ phép (dd/mm hoặc yyyy-mm-dd)
    /congcuatoi                     — bảng công tháng này
    /phieuluong                     — phiếu lương gần nhất (CHỈ chat riêng)
    /tamung <số tiền> <lý do>      — xin tạm ứng lương
    /choduyet                       — đơn chờ tôi duyệt (inline ✅/❌)
"""

import re
from datetime import date, datetime

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

@router.message(Command("nghiphep"))
async def cmd_nghiphep(message: types.Message):
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer(
            "🏖️ <b>Xin nghỉ phép</b>\n\n"
            "Cách dùng:\n"
            "<code>/nghiphep [từ] [đến] [lý do]</code>\n\n"
            "Ví dụ:\n"
            "<code>/nghiphep 20/07 21/07 việc gia đình</code>\n"
            "<code>/nghiphep 2026-07-20 2026-07-20 khám bệnh</code>\n\n"
            "💡 Mặc định là phép năm (có lương). Đơn sẽ gửi leader duyệt."
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
