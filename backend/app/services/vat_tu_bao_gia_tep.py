"""Đọc tệp báo giá NCC (Excel / CSV / PDF / ảnh) gửi qua bot Telegram → danh sách
«mã · giá · NCC · còn hàng» để Thu mua xem trước rồi mới ghi vào phiếu vật tư.

Nguyên tắc: bot đọc → bản xem trước → người xác nhận → mới ghi. Hàm ở đây chỉ
TRÍCH, không ghi DB. AI chỉ được dùng để đọc nội dung; việc khớp mã với dòng
phiếu làm bằng so chuỗi để không «sáng tạo» mã.

Model chữ hiện tại (Groq Llama 3.3) không đọc ảnh → ảnh đi qua model vision
riêng (`LLM_VISION_MODEL`, cùng key Groq). Không có key phù hợp thì báo rõ,
không đoán.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TOI_DA_BYTES = 20 * 1024 * 1024  # Bot API getFile chỉ cho tải ≤ 20 MB
TOI_DA_CHU = 12000  # ký tự đưa vào prompt (báo giá NCC thường < 200 dòng)
MODEL_VISION_MAC_DINH = "groq/meta-llama/llama-4-scout-17b-16e-instruct"


class TepError(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ── Tải tệp từ Telegram ───────────────────────────────────────────────────

async def tai_tep_telegram(file_id: str) -> bytes:
    """Bytes của tệp người dùng gửi cho bot (backend giữ token, bot không cần tải)."""
    from app.services.media_gateway import MediaError, _tg

    try:
        info = await _tg("getFile", {"file_id": file_id})
    except MediaError as exc:
        raise TepError(str(exc), exc.status) from exc
    if (info.get("file_size") or 0) > TOI_DA_BYTES:
        raise TepError("Tệp quá 20 MB — bot không tải được, hãy nhập tay hoặc chia nhỏ tệp")
    url = f"https://api.telegram.org/file/bot{get_settings().TELEGRAM_BOT_TOKEN}/{info.get('file_path')}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise TepError(f"Không tải được tệp từ Telegram ({type(exc).__name__})", 502) from exc
    return resp.content


# ── Tệp → chữ ─────────────────────────────────────────────────────────────

def _loai_tep(filename: str | None, mime: str | None) -> str:
    ten = (filename or "").lower()
    mime = (mime or "").lower()
    if ten.endswith((".xlsx", ".xlsm")) or "spreadsheetml" in mime:
        return "xlsx"
    if ten.endswith(".xls") or mime == "application/vnd.ms-excel":
        return "xls"
    if ten.endswith((".csv", ".txt")) or mime.startswith("text/"):
        return "text"
    if ten.endswith(".pdf") or mime == "application/pdf":
        return "pdf"
    if ten.endswith((".jpg", ".jpeg", ".png", ".webp")) or mime.startswith("image/"):
        return "image"
    if ten.endswith((".doc", ".docx")) or "wordprocessingml" in mime or mime == "application/msword":
        return "word"
    return "khac"


def _xlsx_sang_chu(data: bytes) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    dong: list[str] = []
    for ws in wb.worksheets:
        dong.append(f"## Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            o = [str(c).strip() for c in row if c is not None and str(c).strip() != ""]
            if o:
                dong.append(" | ".join(o))
    return "\n".join(dong)


def _pdf_sang_chu(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise TepError("Máy chủ chưa cài pypdf để đọc PDF") from exc
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:20])


def _text_sang_chu(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            chu = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        chu = data.decode("utf-8", errors="ignore")
    try:
        rows = list(csv.reader(io.StringIO(chu)))
        if rows and max(len(r) for r in rows) > 1:
            return "\n".join(" | ".join(c.strip() for c in r if c.strip()) for r in rows if any(c.strip() for c in r))
    except csv.Error:
        pass
    return chu


def tep_sang_chu(data: bytes, filename: str | None, mime: str | None) -> tuple[str, str]:
    """→ (loại, chữ). Ảnh trả chữ rỗng (đi đường vision). Word/khác → TepError."""
    loai = _loai_tep(filename, mime)
    if loai == "xlsx":
        return loai, _xlsx_sang_chu(data)
    if loai == "pdf":
        chu = _pdf_sang_chu(data)
        if len(chu.strip()) < 20:
            raise TepError("PDF này là ảnh scan, không có chữ để đọc — gửi ảnh chụp rõ bảng giá hoặc tệp Excel")
        return loai, chu
    if loai == "text":
        return loai, _text_sang_chu(data)
    if loai == "image":
        return loai, ""
    if loai == "xls":
        raise TepError("Excel .xls cũ chưa đọc được — mở bằng Excel rồi «Lưu dưới dạng» .xlsx")
    if loai == "word":
        raise TepError("Bot không nhập từ Word (hợp đồng, biên bản) — chỉ nhận bảng giá Excel/CSV/PDF/ảnh")
    raise TepError("Chưa hỗ trợ loại tệp này — gửi Excel (.xlsx), CSV, PDF hoặc ảnh chụp bảng giá")


# ── AI trích ──────────────────────────────────────────────────────────────

_PROMPT = (
    "Bạn đọc BẢNG BÁO GIÁ của nhà cung cấp vật liệu (gạch, đá, thiết bị) cho công ty nội thất Việt Nam. "
    "Trích MỌI dòng có mã sản phẩm và giá. Trả JSON đúng dạng:\n"
    '{"ncc_ten": "tên nhà cung cấp nếu thấy, không thì null", '
    '"items": [{"ma": "mã sản phẩm y nguyên trong tệp", "gia": số VNĐ (không dấu chấm/phẩy, không chữ), '
    '"don_vi": "m2|viên|thùng|bộ|cái|null", "con_hang": true/false/null, "ghi_chu": "ghi chú ngắn hoặc null"}]}\n'
    "Quy tắc: giá ghi 'liên hệ'/'hết hàng' → gia null, con_hang false nếu ghi hết hàng. "
    "Giá bằng nghìn (vd 185k, 185.000đ, 185,000) → 185000. KHÔNG bịa mã không có trong tệp. "
    "Không có bảng giá thì trả {\"ncc_ten\": null, \"items\": []}."
)


def _so(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = re.sub(r"[^\d,.]", "", str(v))
    if not s:
        return None
    s = s.replace(",", "").replace(".", "")
    try:
        n = float(s)
    except ValueError:
        return None
    return n if n > 0 else None


def _chuan_hoa(data: Any) -> dict:
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, list):
        data = {"items": data}
    items = []
    for it in (data.get("items") or [])[:300]:
        if not isinstance(it, dict) or not it.get("ma"):
            continue
        ch = it.get("con_hang")
        items.append({
            "ma": str(it["ma"]).strip()[:150],
            "gia": _so(it.get("gia")),
            "don_vi": (str(it["don_vi"]).strip()[:20] if it.get("don_vi") else None),
            "con_hang": (bool(ch) if ch is not None else True),
            "ghi_chu": (str(it["ghi_chu"]).strip()[:200] if it.get("ghi_chu") else None),
        })
    ncc = data.get("ncc_ten")
    return {"ncc_ten": (str(ncc).strip()[:150] if ncc else None), "items": items}


def _noi_dung_tra_ve(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    try:
        return raw.choices[0].message.content
    except (AttributeError, IndexError, KeyError):
        return raw["choices"][0]["message"]["content"]


async def trich_tu_chu(chu: str) -> dict:
    """Chữ (từ Excel/PDF/CSV) → {ncc_ten, items}. Lỗi AI → TepError 503."""
    from app.services.llm_config import llm_available, llm_complete

    if not await llm_available():
        raise TepError("Chưa cấu hình AI (Cài đặt → Cấu hình AI) nên bot chưa đọc được tệp", 503)
    chu = chu.strip()
    if not chu:
        raise TepError("Tệp không có nội dung để đọc")
    try:
        raw = await llm_complete(
            [{"role": "system", "content": _PROMPT},
             {"role": "user", "content": f"Nội dung tệp báo giá:\n\n{chu[:TOI_DA_CHU]}"}],
            temperature=0.0, max_tokens=4000, response_format={"type": "json_object"},
        )
        return _chuan_hoa(_noi_dung_tra_ve(raw))
    except TepError:
        raise
    except Exception as exc:  # noqa: BLE001 — model/khóa/quota
        logger.warning("Trích báo giá bằng AI lỗi: %s", exc)
        raise TepError("AI không đọc được tệp lúc này, thử lại sau hoặc nhập tay", 503) from exc


async def trich_tu_anh(anh: bytes, mime: str | None) -> dict:
    """Ảnh chụp bảng giá → model vision (cùng key Groq với model chữ)."""
    from litellm import acompletion

    from app.services.llm_config import get_llm_config

    cfg = await get_llm_config()
    model = get_settings().LLM_VISION_MODEL or MODEL_VISION_MAC_DINH
    key = cfg.get("llm_api_key", "")
    if not key or not (cfg.get("llm_model", "").split("/")[0] == model.split("/")[0]):
        raise TepError(
            "Bot chưa đọc được ảnh với cấu hình AI hiện tại — gửi tệp Excel/PDF của NCC thay cho ảnh", 503,
        )
    b64 = base64.b64encode(anh).decode()
    url = f"data:{mime or 'image/jpeg'};base64,{b64}"
    try:
        raw = await acompletion(
            model=model, api_key=key, temperature=0.0, max_tokens=4000,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _PROMPT + "\nĐây là ảnh chụp bảng báo giá."},
                {"type": "image_url", "image_url": {"url": url}},
            ]}],
        )
        return _chuan_hoa(_noi_dung_tra_ve(raw))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision đọc ảnh báo giá lỗi: %s", exc)
        raise TepError("AI không đọc được ảnh này — chụp rõ hơn hoặc gửi tệp Excel/PDF", 503) from exc


# ── Khớp mã với dòng phiếu ─────────────────────────────────────────────────

def chuan_ma(ma: str | None) -> str:
    """So mã bỏ khoảng trắng/dấu chấm/gạch, không phân biệt hoa thường:
    «TM 76006» ≡ «TM-76006» ≡ «tm76006»."""
    return re.sub(r"[\s\.\-_/]", "", (ma or "")).upper()


def khop_ma(items: list[dict], dong: list[dict]) -> tuple[list[dict], list[dict]]:
    """dong: [{dong_id, ma, ...}] của phiếu dự án. Mỗi mã trong tệp ghép với MỌI
    dòng phiếu có cùng mã (một mã có thể ở nhiều phòng). Trả (khớp, không khớp)."""
    theo_ma: dict[str, list[dict]] = {}
    for d in dong:
        k = chuan_ma(d.get("ma"))
        if k:
            theo_ma.setdefault(k, []).append(d)
    khop, khong = [], []
    for it in items:
        ds = theo_ma.get(chuan_ma(it["ma"]))
        if not ds or it.get("gia") is None:
            khong.append(it)
            continue
        for d in ds:
            khop.append({**it, **{k: d[k] for k in ("dong_id", "phong", "so_luong", "don_vi_phieu", "ma_phieu") if k in d}})
    return khop, khong
