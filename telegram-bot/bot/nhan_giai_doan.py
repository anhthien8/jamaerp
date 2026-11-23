"""Nhãn giai đoạn lead — BẢN SAO của STAGE_LABELS backend (backend/app/api/leads.py)
và STAGE_CONFIG web (frontend/src/lib/utils.ts). Đổi một chỗ thì đổi cả ba (R00 §E).

Tin nào có sẵn `stage_label` từ server thì dùng nhãn đó, bảng này chỉ cho chỗ server
chỉ trả mã giai đoạn (thống kê /pipeline, kết quả đọc lead mới).
"""

NHAN_GIAI_DOAN: dict[str, str] = {
    "new": "Tiếp nhận mới",
    "interested": "Đang tư vấn",
    "surveyed": "Đã khảo sát",
    "survey_scheduled": "Đã gửi báo giá",
    "potential": "Đang đàm phán",
    "signed_design": "Deal đã thắng",
    "lost": "Mất",
    "dormant": "Ngủ đông",
}
