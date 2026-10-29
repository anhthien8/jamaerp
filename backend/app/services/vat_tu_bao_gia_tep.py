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
TOI_DA_CHU = 30000  # ký tự đưa vào prompt (báo giá tổng hợp gửi khách có thể dài)
MODEL_VISION_MAC_DINH = "groq/qwen/qwen3.8-27b"


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
    '"ncc_mst": "mã số thuế NCC nếu có in trong tệp, không thì null", '
    '"ncc_dia_chi": "địa chỉ NCC nếu có, không thì null", '
    '"items": [{"ma": "mã sản phẩm y nguyên trong tệp", "gia": số VNĐ (không dấu chấm/phẩy, không chữ), '
    '"don_vi": "m2|viên|thùng|bộ|cái|null", "con_hang": true/false/null, "ghi_chu": "ghi chú ngắn hoặc null", '
    '"ten": "tên/mô tả sản phẩm hoặc null", "so_luong": số lượng nếu bảng có cột số lượng/khối lượng, không thì null, '
    '"phong": "phòng/khu vực/hạng mục của dòng (vd Phòng khách, WC1) hoặc null"}]}\n'
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


def _so_luong(v: Any) -> float | None:
    """Số lượng có thể lẻ (12.5 m2) — không bỏ dấu thập phân như giá."""
    if v is None or isinstance(v, bool):
        return None
    try:
        n = float(v) if isinstance(v, (int, float)) else float(str(v).strip().replace(",", "."))
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
            "ten": (str(it["ten"]).strip()[:255] if it.get("ten") else None),
            "so_luong": _so_luong(it.get("so_luong")),
            "phong": (str(it["phong"]).strip()[:100] if it.get("phong") else None),
        })
    ncc = data.get("ncc_ten")
    mst, dc = data.get("ncc_mst"), data.get("ncc_dia_chi")
    return {"ncc_ten": (str(ncc).strip()[:150] if ncc else None),
            "ncc_mst": (str(mst).strip()[:20] if mst else None),
            "ncc_dia_chi": (str(dc).strip()[:500] if dc else None), "items": items}


def _noi_dung_tra_ve(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    try:
        return raw.choices[0].message.content
    except (AttributeError, IndexError, KeyError):
        return raw["choices"][0]["message"]["content"]


def _boc_json(s: str) -> str:
    """Lấy khối JSON trong câu trả lời có thể kèm ```json … ``` hoặc lời dẫn."""
    s = (s or "").strip()
    vt = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if not vt:
        return s
    dau = min(vt)
    cuoi = max(s.rfind("}"), s.rfind("]"))
    return s[dau:cuoi + 1] if cuoi > dau else s[dau:]


async def trich_tu_chu(chu: str, prompt: str | None = None, chuan=None) -> dict:
    """Chữ (từ Excel/PDF/CSV) → {ncc_ten, items}. Lỗi AI → TepError 503."""
    from app.services.llm_config import llm_available, llm_complete

    if not await llm_available():
        raise TepError("Chưa cấu hình AI (Cài đặt → Cấu hình AI) nên bot chưa đọc được tệp", 503)
    chu = chu.strip()
    if not chu:
        raise TepError("Tệp không có nội dung để đọc")
    tin = [{"role": "system", "content": prompt or _PROMPT},
           {"role": "user", "content": f"Nội dung tệp báo giá:\n\n{chu[:TOI_DA_CHU]}"}]
    try:
        try:
            raw = await llm_complete(tin, temperature=0.0, max_tokens=8000, response_format={"type": "json_object"})
            return (chuan or _chuan_hoa)(_noi_dung_tra_ve(raw))
        except Exception as exc:  # noqa: BLE001
            # Báo giá dài: chế độ JSON của Groq hay hỏng (json_validate_failed) → thử lại không ép JSON, tự bóc
            logger.info("Trích báo giá: chế độ JSON lỗi (%s) → thử lại dạng chữ", exc)
            raw = await llm_complete(tin, temperature=0.0, max_tokens=16000)
            return (chuan or _chuan_hoa)(_boc_json(_noi_dung_tra_ve(raw)))
    except TepError:
        raise
    except Exception as exc:  # noqa: BLE001 — model/khóa/quota
        logger.warning("Trích báo giá bằng AI lỗi: %s", exc)
        raise TepError("AI không đọc được tệp lúc này, thử lại sau hoặc nhập tay", 503) from exc


async def trich_tu_anh(anh: bytes, mime: str | None, prompt: str | None = None, chuan=None) -> dict:
    """Ảnh chụp bảng giá → model vision (cùng key Groq với model chữ)."""
    from litellm import acompletion

    from app.services.llm_config import get_llm_config

    cfg = await get_llm_config()
    from app.services.llm_config import chuan_model
    model = chuan_model(get_settings().LLM_VISION_MODEL or MODEL_VISION_MAC_DINH)
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
                {"type": "text", "text": (prompt or _PROMPT) + "\nĐây là ảnh chụp bảng báo giá."},
                {"type": "image_url", "image_url": {"url": url}},
            ]}],
        )
        return (chuan or _chuan_hoa)(_noi_dung_tra_ve(raw))
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


# ── Báo giá PHÁT SINH của JAMA gửi khách (30/10/2026) ───────────────────────
# Cột: STT | Hạng mục | Hình ảnh | Kích thước | ĐVT | KL | SL | Đơn giá | Thành tiền | Ghi chú.
# SL âm = giảm trừ (CĐT cấp). Dòng in nghiêng không giá = diễn giải dòng trên.

_PROMPT_PHAT_SINH = (
    "Bạn đọc BẢNG BÁO GIÁ PHÁT SINH mà công ty nội thất JAMA gửi khách hàng. "
    "Cột thường gặp: STT, Hạng mục, Hình ảnh, Kích thước (Dài/Sâu/Cao), ĐVT, KL (khối lượng), SL (số lượng), "
    "Đơn giá, Thành tiền, Ghi chú vật liệu. Trả JSON đúng dạng:\n"
    '{"khach_hang": "tên khách/chủ nhà nếu thấy, không thì null", '
    '"tieu_de": "tiêu đề đợt phát sinh, vd PHÁT SINH NGÀY 5/10/2026, không thì null", '
    '"tong_file": số tổng chi phí in trong tệp hoặc null, '
    '"items": [{"hang_muc": "tên hạng mục", "dvt": "md|m2|bộ|cái|... hoặc null", "kl": số hoặc null, '
    '"sl": số (có thể ÂM nếu là giảm trừ) hoặc null, "don_gia": số VNĐ hoặc null, '
    '"thanh_tien": số VNĐ (âm nếu giảm trừ) hoặc null, "kich_thuoc": "DxSxC hoặc null", '
    '"ghi_chu": "ghi chú vật liệu + diễn giải dòng con, hoặc null"}]}\n'
    "Quy tắc: dòng con KHÔNG có đơn giá (vd «Tầng 1-lửng 3.80») là diễn giải của dòng trên — gộp vào ghi_chu "
    "của dòng trên, KHÔNG tạo item riêng. Bỏ dòng tiêu đề nhóm (A, B...) và dòng tổng. "
    "Số viết 1.250.000 → 1250000; KL 3,8 → 3.8. KHÔNG bịa dòng. Không thấy bảng thì items rỗng."
)


def _so_am(v: Any) -> float | None:
    """Số có dấu (SL/thành tiền âm = giảm trừ). «1.250.000» → 1250000, «3,8» → 3.8."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    am = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^\d,.]", "", s)
    if not s:
        return None
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        s = re.sub(r"[.,]", "", s)
    else:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if am else n


def chuan_hoa_phat_sinh(data: Any) -> dict:
    """Chuẩn hoá + TỰ TÍNH thành tiền (KL × SL × đơn giá) — không tin số AI cộng."""
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, list):
        data = {"items": data}
    items = []
    for it in (data.get("items") or [])[:200]:
        if not isinstance(it, dict) or not str(it.get("hang_muc") or "").strip():
            continue
        kl, sl, dg = _so_am(it.get("kl")), _so_am(it.get("sl")), _so_am(it.get("don_gia"))
        tt_file = _so_am(it.get("thanh_tien"))
        if dg is not None and (kl is not None or sl is not None):
            tt = round((kl if kl is not None else 1) * (sl if sl is not None else 1) * abs(dg))
        else:
            tt = tt_file
        if tt is None:
            continue  # dòng không giá = diễn giải, AI quên gộp
        items.append({
            "hang_muc": str(it["hang_muc"]).strip()[:255],
            "dvt": (str(it["dvt"]).strip()[:20] if it.get("dvt") else None),
            "kl": kl, "sl": sl, "don_gia": (abs(dg) if dg is not None else None),
            "thanh_tien": float(tt), "thanh_tien_file": tt_file,
            "kich_thuoc": (str(it["kich_thuoc"]).strip()[:60] if it.get("kich_thuoc") else None),
            "ghi_chu": (str(it["ghi_chu"]).strip()[:300] if it.get("ghi_chu") else None),
        })
    kh, td = data.get("khach_hang"), data.get("tieu_de")
    return {"khach_hang": (str(kh).strip()[:150] if kh else None),
            "tieu_de": (str(td).strip()[:200] if td else None),
            "tong_file": _so_am(data.get("tong_file")), "items": items}


def bo_dau(s: str | None) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower()).replace("đ", "d")
    return re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def ten_khop(ten_khach: str | None, *chuoi: str | None) -> bool | None:
    """Tên khách (vd «Chị Lan») có xuất hiện trong tên tệp/tiêu đề không. None = không đủ dữ liệu."""
    bo_xung_ho = {"anh", "chi", "co", "chu", "ong", "ba", "a", "c", "kh", "khach", "nha"}
    tu = [t for t in bo_dau(ten_khach).split() if t not in bo_xung_ho and len(t) > 1]
    nguon = " ".join(bo_dau(c) for c in chuoi if c)
    if not tu or not nguon.strip():
        return None
    return tu[-1] in nguon.split()


def la_bao_gia_khach(filename: str | None, chu: str | None) -> bool:
    """Tệp là báo giá JAMA GỬI KHÁCH (không phải báo giá NCC gửi JAMA)?
    Tên tệp bắt đầu «JAMA_BÁO_GIÁ…», hoặc bảng có «hạng mục» + «phát sinh» / «KL … SL … thành tiền»."""
    ten = bo_dau(filename).split()
    if ten[:1] == ["jama"] and "bao" in ten[:4]:
        return True
    c = bo_dau((chu or "")[:6000])
    if "hang muc" not in c:
        return False
    return "phat sinh" in c or ("thanh tien" in c and " kl " in f" {c} " and "ma sp" not in c and "ma hang" not in c)
