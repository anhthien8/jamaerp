"""Thả ảnh thẳng vào topic dự án trong nhóm «JAMA Công trình» (23/10/2026).

Không cần lệnh: chụp ở công trình → gửi vào đúng topic dự án → bot báo
backend ghi nhận vào Kho ảnh (ảnh đã nằm sẵn trong nhóm, không đăng lại).
Backend tự kiểm đây có phải nhóm Kho ảnh và topic có gắn dự án không (404
thì bot im lặng — ảnh ở nhóm khác không phải việc của Kho ảnh).

Yêu cầu: BotFather /setprivacy → Disable, nếu không bot không thấy ảnh thường.
"""

import logging

from aiogram import F, Router, types
from aiogram.types import ReactionTypeEmoji

from bot.api_client import api

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    F.photo,
    F.chat.type == "supergroup",
    F.is_topic_message == True,  # noqa: E712 — filter magic của aiogram
)
async def anh_vao_topic(message: types.Message):
    if not message.from_user or message.from_user.is_bot:
        return
    photo = message.photo[-1]
    res = await api.ingest_storage_photo(message.from_user.id, {
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "thread_id": message.message_thread_id,
        "caption": message.caption,
        "width": photo.width,
        "height": photo.height,
        "file_size": photo.file_size,
    })
    if res is None:
        return
    if res.get("error"):
        # 401: người gửi chưa liên kết tài khoản JAMA. Không trả lời trong nhóm
        # vì bot chưa biết đây có phải nhóm Kho ảnh (backend mới biết) — tránh
        # làm phiền các nhóm có Topics khác. Ảnh thiếu → thêm từ web sau.
        if res.get("status") != 404:
            logger.warning("Kho ảnh từ chối ảnh topic: %s", res)
        return
    try:
        await message.react([ReactionTypeEmoji(emoji="👍")])
    except Exception:
        pass
