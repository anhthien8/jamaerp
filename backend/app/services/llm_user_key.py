"""Khóa LLM cá nhân của user trong request hiện tại.

Module riêng, không import gì nặng — cả middleware/auth lẫn llm_config đều
import được mà không kéo theo litellm vào chuỗi import của auth.

auth.get_current_user set giá trị sau khi load user; llm_complete đọc để
ưu tiên key cá nhân trước key hệ thống. Worker nền / Telegram bot không đi
qua get_current_user → giữ default rỗng → dùng key hệ thống.
"""

from contextvars import ContextVar

current_user_llm_key: ContextVar[str] = ContextVar("current_user_llm_key", default="")
