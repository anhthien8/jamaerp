"""Bộ nhớ cho AI Agents — mỗi lần agent chạy là một dòng `ai_runs`.

Trước 12/08/2026 hệ thống KHÔNG nhớ gì về AI: mọi lời gọi LLM đều dựng lại
`messages=[system, user]` từ đầu, kết quả dùng xong là vứt (Insight Agent chạy
hằng ngày rồi chỉ ghi log). Hệ quả: đốt quota free tier để tính lại đúng thứ vừa
tính, không so được nhận định kỳ này với kỳ trước, và người đọc báo cáo không
biết bản mình đang xem do LLM viết hay do bộ luật dự phòng sinh ra.

Bảng này giải quyết cả ba:
  * `input_hash` — cùng đầu vào trong thời hạn còn hiệu lực thì dùng lại, không gọi LLM.
  * `created_at` + `scope_*` — có lịch sử để so kỳ trước và vẽ xu hướng điểm lead.
  * `source` + `model_used` — luôn biết bản này do đâu mà ra.
  * `outcome` — sale bấm "Đã làm"/"Bỏ qua", vòng sau Co-Pilot đọc lại để khỏi gợi ý lặp.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Tên agent — dùng hằng số để không gõ sai chuỗi ở nơi ghi và nơi đọc
AGENT_LEAD_SCORING = "lead_scoring"
AGENT_SALES_COPILOT = "sales_copilot"
AGENT_INSIGHT = "insight"

# Phạm vi bản ghi: gắn với 1 lead, 1 dự án, hay toàn công ty
SCOPE_LEAD = "lead"
SCOPE_PROJECT = "project"
SCOPE_GLOBAL = "global"

# Nguồn kết quả
SOURCE_LLM = "llm"
SOURCE_RULE = "rule"

# Phản hồi của người dùng với gợi ý
OUTCOME_DONE = "done"
OUTCOME_SKIPPED = "skipped"
OUTCOMES = (OUTCOME_DONE, OUTCOME_SKIPPED)


class AiRun(Base):
    """Một lần chạy của AI agent, kèm đầu ra và phản hồi của người dùng."""

    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    agent: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default=SCOPE_GLOBAL)
    # Không đặt ForeignKey: scope_id trỏ tới nhiều bảng khác nhau tuỳ scope_type,
    # và bản ghi nhớ phải sống sót khi lead/dự án bị xoá.
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # sha256 của CHÍNH chuỗi đã gửi cho LLM — trùng băm nghĩa là hỏi y hệt câu cũ
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    source: Mapped[str] = mapped_column(String(10), nullable=False, default=SOURCE_RULE)
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)

    outcome: Mapped[str | None] = mapped_column(String(12), nullable=True)
    outcome_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        # Đọc lịch sử của 1 lead: lọc agent + scope rồi sắp theo thời gian
        Index("ix_ai_runs_scope", "agent", "scope_type", "scope_id", "created_at"),
        # Tra cache: cùng agent + cùng câu hỏi
        Index("ix_ai_runs_hash", "agent", "input_hash", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AiRun {self.agent} {self.scope_type}:{self.scope_id} {self.source}>"
