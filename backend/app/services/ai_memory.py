"""Tầng bộ nhớ dùng chung cho mọi AI agent.

Ba việc, không hơn:
  1. **Nhớ** — ghi mọi kết quả agent vào `ai_runs` kèm nguồn (LLM hay luật) và model đã dùng.
  2. **Dùng lại** — hỏi y hệt câu cũ trong thời hạn còn hiệu lực thì trả bản cũ, không gọi LLM.
  3. **Đọc lại** — lấy N lần chạy gần nhất của một lead để nhét vào prompt vòng sau.

Nguyên tắc băm: băm **chính chuỗi đã gửi cho LLM**, không băm bản tóm tắt riêng.
Nhờ vậy "trúng cache" có nghĩa đen là *hỏi lại đúng câu đã hỏi*, khỏi phải phán đoán
xem trường nào đáng kể trường nào không. Đầu vào của chấm điểm lead có kèm số ngày
kể từ lần liên hệ cuối, nên sang ngày mới là băm đổi và lead tự được chấm lại — đúng
ý muốn với một điểm số nhạy cảm về độ tươi.

Toàn bộ hàm ở đây **không được phép làm hỏng luồng chính**: bộ nhớ lỗi thì agent vẫn
phải chạy. Nên mọi lỗi đều nuốt + ghi log, không ném lên trên.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import (
    OUTCOMES,
    SOURCE_LLM,
    SOURCE_RULE,
    AiRun,
)

logger = logging.getLogger(__name__)

# Mặc định 24 giờ: đủ lâu để một ngày làm việc không gọi lại LLM cho cùng dữ liệu,
# đủ ngắn để không ai đọc phải nhận định của hôm kia mà tưởng của hôm nay.
TTL_MAC_DINH_GIO = 24

# Trần số lần chạy nhét vào prompt — nhiều hơn chỉ tổ phình token, không thêm thông tin
GIOI_HAN_NHO_LAI = 5


def bam_dau_vao(noi_dung: str | dict | list) -> str:
    """sha256 của đầu vào. Dict/list được chuẩn hoá (sort key) để thứ tự không đổi băm."""
    if isinstance(noi_dung, str):
        raw = noi_dung
    else:
        raw = json.dumps(noi_dung, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sang_utc(moc: datetime | None) -> datetime | None:
    """Cột DateTime lưu naive; gắn lại UTC để so sánh không nổ TypeError."""
    if moc is None:
        return None
    return moc if moc.tzinfo else moc.replace(tzinfo=timezone.utc)


async def tim_ban_cu(
    db: AsyncSession,
    agent: str,
    input_hash: str,
    ttl_gio: int = TTL_MAC_DINH_GIO,
) -> AiRun | None:
    """Bản chạy gần nhất cùng agent + cùng câu hỏi, còn trong hạn. Không có thì None.

    Chỉ nhận bản do LLM sinh ra: bản luật vốn đã rẻ, tính lại còn nhanh hơn tra bảng,
    mà dùng lại bản luật cũ thì lỡ mất cơ hội gọi LLM khi quota đã hồi.
    """
    if ttl_gio <= 0:
        return None
    try:
        rows = (
            await db.execute(
                select(AiRun)
                .where(
                    AiRun.agent == agent,
                    AiRun.input_hash == input_hash,
                    AiRun.source == SOURCE_LLM,
                )
                .order_by(AiRun.created_at.desc())
                .limit(1)
            )
        ).scalars().all()
    except Exception as exc:  # bảng chưa migrate, DB chập chờn…
        logger.warning("Không tra được bộ nhớ AI (%s): %s", agent, exc)
        return None

    if not rows:
        return None

    ban = rows[0]
    tao_luc = _sang_utc(ban.created_at)
    if tao_luc is None:
        return None
    if datetime.now(timezone.utc) - tao_luc > timedelta(hours=ttl_gio):
        return None
    return ban


async def nho_lai(
    db: AsyncSession,
    agent: str,
    scope_type: str,
    scope_id: str | None = None,
    limit: int = GIOI_HAN_NHO_LAI,
) -> list[AiRun]:
    """N lần chạy gần nhất trong phạm vi này, mới nhất trước."""
    try:
        rows = (
            await db.execute(
                select(AiRun)
                .where(
                    AiRun.agent == agent,
                    AiRun.scope_type == scope_type,
                    AiRun.scope_id == scope_id,
                )
                .order_by(AiRun.created_at.desc())
                .limit(max(1, min(limit, 50)))
            )
        ).scalars().all()
        return list(rows)
    except Exception as exc:
        logger.warning("Không đọc được bộ nhớ AI (%s/%s): %s", agent, scope_id, exc)
        return []


async def ghi_lai(
    db: AsyncSession,
    agent: str,
    scope_type: str,
    input_hash: str,
    output: Any,
    source: str = SOURCE_RULE,
    scope_id: str | None = None,
    model_used: str | None = None,
    commit: bool = False,
) -> AiRun | None:
    """Lưu một lần chạy. Trả về bản ghi (để API gửi `run_id` cho giao diện)."""
    try:
        ban = AiRun(
            agent=agent,
            scope_type=scope_type,
            scope_id=scope_id,
            input_hash=input_hash,
            output_json=json.dumps(output, ensure_ascii=False, default=str),
            source=source if source in (SOURCE_LLM, SOURCE_RULE) else SOURCE_RULE,
            model_used=(model_used or None),
            created_at=datetime.now(timezone.utc),
        )
        db.add(ban)
        await db.flush()
        if commit:
            await db.commit()
        return ban
    except Exception as exc:
        logger.warning("Không ghi được bộ nhớ AI (%s): %s", agent, exc)
        return None


async def danh_dau_ket_qua(
    db: AsyncSession,
    run_id: str,
    outcome: str,
    user_id: str,
    note: str | None = None,
) -> AiRun | None:
    """Sale bấm "Đã làm" / "Bỏ qua". Trả None nếu không có bản ghi đó."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome phải là một trong {OUTCOMES}")

    ban = await db.get(AiRun, run_id)
    if ban is None:
        return None

    ban.outcome = outcome
    ban.outcome_by = user_id
    ban.outcome_at = datetime.now(timezone.utc)
    ban.outcome_note = (note or None)
    await db.flush()
    return ban


def doc_output(ban: AiRun) -> dict:
    """Bung `output_json`; hỏng thì trả dict rỗng chứ không nổ."""
    try:
        data = json.loads(ban.output_json or "{}")
        return data if isinstance(data, dict) else {"value": data}
    except (json.JSONDecodeError, TypeError):
        return {}


def ten_model(response: Any) -> str | None:
    """Model thật sự đã trả lời — có thể là model dự phòng chứ không phải model chính."""
    return getattr(response, "model", None) or None
