"""Test bot: chạy `python -m pytest tests -q` từ thư mục telegram-bot."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def chay(coro):
    return asyncio.run(coro)


def tin(text: str = "", chat_type: str = "private", uid: int = 111) -> SimpleNamespace:
    """Tin nhắn giả: answer/edit_text là AsyncMock để soi nội dung + bàn phím."""
    return SimpleNamespace(
        text=text, caption=None,
        chat=SimpleNamespace(type=chat_type, id=uid),
        from_user=SimpleNamespace(id=uid, username="nv"),
        answer=AsyncMock(), edit_text=AsyncMock(), edit_reply_markup=AsyncMock(),
    )


def bam(data: str, message=None, uid: int = 111) -> SimpleNamespace:
    """Callback giả: người bấm là from_user (message.from_user là bot)."""
    return SimpleNamespace(
        data=data, message=message or tin(uid=999),
        from_user=SimpleNamespace(id=uid, username="nv"),
        answer=AsyncMock(),
    )


def nhan_nut(markup) -> list[tuple[str, str]]:
    return [(b.text, b.callback_data) for hang in markup.inline_keyboard for b in hang]


@pytest.fixture
def state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=111, user_id=111))
