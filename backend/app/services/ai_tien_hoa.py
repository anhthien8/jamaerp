"""AI Tiến Hoá — đo xem AI có khôn lên không, và học từ phản hồi thật của sale (13/11/2026).

Hai việc, chỉ quản trị (role admin) thấy:

1. **Bảng theo dõi** — đọc thẳng `ai_runs`, không thêm bảng:
   * tỷ lệ sale làm theo gợi ý Co-Pilot từng tuần = Đã làm / (Đã làm + Bỏ qua).
     Đường đi lên nghĩa là AI đang khôn ra;
   * số lượt chạy từng agent, LLM hay bộ luật, model nào thật sự trả lời;
   * tỷ lệ trả lời từ bộ nhớ (không tốn lượt gọi LLM);
   * loại gợi ý hay bị bỏ qua nhất.

2. **Vòng tự học** — gom phản hồi theo LOẠI gợi ý thành «bài học» đề xuất. Chỉ khi quản trị
   bấm Duyệt thì Co-Pilot mới áp: bộ luật đẩy loại hay bị bỏ qua xuống sau, đưa loại hay
   được làm lên trước; LLM nhận bài học trong prompt. Chưa duyệt thì không có gì đổi — AI
   không tự sửa hành vi khi chưa có người gật đầu.

Module này KHÔNG import agent nào, để agent import ngược lại được mà không vòng.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import (
    AGENT_INSIGHT,
    AGENT_LEAD_SCORING,
    AGENT_SALES_COPILOT,
    OUTCOME_DONE,
    OUTCOME_SKIPPED,
    SOURCE_LLM,
    AiRun,
)
from app.services import ai_memory
from app.services.attendance_service import get_setting_json, set_setting_json

logger = logging.getLogger(__name__)

KHOA_BAI_HOC = "ai_bai_hoc"

# Ít hơn MAU_TOI_THIEU phản hồi thì chưa đủ để kết luận gì về một loại gợi ý.
MAU_TOI_THIEU = 5
NGUONG_BO_QUA = 0.6  # ≥ 60% bị bỏ qua → đề xuất hạ xuống
NGUONG_LAM = 0.7     # ≥ 70% được làm theo → đề xuất đưa lên trước

HUONG_UU_TIEN = "uu_tien"
HUONG_HA = "ha"
HUONG = (HUONG_UU_TIEN, HUONG_HA)

DA_DUYET = "da_duyet"
TU_CHOI = "tu_choi"
QUYET_DINH = ("duyet", "tu_choi", "go")

GIO_VN = timedelta(hours=7)

TEN_AGENT = {
    AGENT_SALES_COPILOT: "Co-Pilot gợi ý việc",
    AGENT_LEAD_SCORING: "Chấm điểm lead",
    AGENT_INSIGHT: "Nhận định cho BGĐ",
}

# Loại gợi ý của Co-Pilot. Mã trùng `code` của bộ luật trong sales_copilot.
LOAI_KHAC = "khac"
LOAI_GOI_Y = {
    "call": "Gọi tư vấn",
    "recontact": "Liên hệ lại",
    "survey": "Hẹn khảo sát",
    "meeting": "Xác nhận lịch khảo sát",
    "proposal": "Gửi báo giá / phương án",
    "escalate": "Báo trưởng nhóm",
    "assign": "Phân công sale",
    "note": "Cập nhật tình trạng",
    LOAI_KHAC: "Việc khác",
}

# Đoán loại cho gợi ý LLM cũ (trước 13/11 LLM không trả loại) hoặc khi LLM quên trả.
# Thứ tự quan trọng: «Xác nhận lịch khảo sát» ra meeting, «Gửi báo giá sau khảo sát» ra
# proposal — cả hai phải được xét trước chữ «khảo sát» trơn.
_TU_KHOA_LOAI = (
    ("assign", ("phân công", "giao lead", "chia lead")),
    ("escalate", ("trưởng nhóm", "báo quản lý", "báo sếp", "leader")),
    ("meeting", ("xác nhận lịch", "nhắc lịch", "chuẩn bị hồ sơ")),
    ("proposal", ("báo giá", "phương án", "hợp đồng", "ký ")),
    ("survey", ("khảo sát",)),
    ("recontact", ("liên hệ lại", "hâm nóng", "hỏi thăm", "chăm lại", "nhắc lại")),
    ("call", ("gọi", "điện", "zalo", "nhắn tin", "tư vấn")),
    ("note", ("cập nhật", "ghi chú", "ghi lại")),
)


def doan_loai(action: str | None) -> str:
    chu = f" {(action or '').lower()} "
    for code, tu_khoa in _TU_KHOA_LOAI:
        if any(t in chu for t in tu_khoa):
            return code
    return LOAI_KHAC


def loai_cua(output: dict) -> str:
    """Loại của một gợi ý đã lưu: lấy `code` nếu là loại đã biết, không thì đoán từ câu chữ."""
    code = output.get("code")
    if code in LOAI_GOI_Y:
        return code
    return doan_loai(output.get("action"))


# ---------------------------------------------------------------------------
# Bài học — Co-Pilot đọc mỗi lượt gợi ý
# ---------------------------------------------------------------------------

def _cua_agent(kho: dict, agent: str) -> dict:
    v = kho.get(agent)
    return dict(v) if isinstance(v, dict) else {}


async def bai_hoc_dang_ap_dung(db: AsyncSession, agent: str = AGENT_SALES_COPILOT) -> dict[str, str]:
    """{loại: hướng} của các bài học quản trị đã duyệt. Lỗi thì coi như chưa có bài nào."""
    try:
        async with db.begin_nested():
            kho = await get_setting_json(db, KHOA_BAI_HOC)
    except Exception as exc:  # noqa: BLE001 — bài học hỏng không được làm hỏng gợi ý
        logger.warning("Không đọc được bài học AI: %s", exc)
        return {}
    return {
        code: v["huong"]
        for code, v in _cua_agent(kho, agent).items()
        if isinstance(v, dict) and v.get("trang_thai") == DA_DUYET
        and v.get("huong") in HUONG and code in LOAI_GOI_Y and code != LOAI_KHAC
    }


def loi_dan_bai_hoc(bai_hoc: dict[str, str]) -> str:
    """Bài học viết thành văn để nối vào prompt LLM. Không có bài nào → chuỗi rỗng."""
    if not bai_hoc:
        return ""
    dong = []
    for code, huong in sorted(bai_hoc.items()):
        nhan = LOAI_GOI_Y[code]
        if huong == HUONG_HA:
            dong.append(f"- Sale thường BỎ QUA loại «{nhan}» → chỉ đề xuất khi thật sự cần.")
        else:
            dong.append(f"- Sale thường LÀM THEO loại «{nhan}» → ưu tiên khi hợp giai đoạn.")
    return "Bài học từ phản hồi của sale (quản trị đã duyệt):\n" + "\n".join(dong)


def xep_theo_bai_hoc(ung_vien: list[dict], bai_hoc: dict[str, str]) -> list[dict]:
    """Xếp lại ứng viên bộ luật: loại được ưu tiên lên trước, loại bị hạ xuống sau.

    Trong cùng một bậc giữ nguyên thứ tự gốc. «Cập nhật tình trạng» là việc lấp chỗ trống
    nên luôn đứng cuối. Không có bài học → trả nguyên danh sách.
    """
    if not bai_hoc:
        return ung_vien
    bac = {HUONG_UU_TIEN: 0, HUONG_HA: 2}
    return [
        uv for _, uv in sorted(
            enumerate(ung_vien),
            key=lambda t: (t[1]["code"] == "note", bac.get(bai_hoc.get(t[1]["code"]), 1), t[0]),
        )
    ]


def de_xuat_huong(lam: int, bo_qua: int) -> str | None:
    tong = lam + bo_qua
    if tong < MAU_TOI_THIEU:
        return None
    if bo_qua / tong >= NGUONG_BO_QUA:
        return HUONG_HA
    if lam / tong >= NGUONG_LAM:
        return HUONG_UU_TIEN
    return None


def _cau_bai_hoc(nhan: str, huong: str, lam: int, bo_qua: int) -> str:
    tong = lam + bo_qua
    if huong == HUONG_HA:
        so = f"Sale bỏ qua «{nhan}» {bo_qua}/{tong} lần. " if tong else f"«{nhan}»: "
        return so + "Co-Pilot đẩy loại việc này xuống sau, chỉ đưa ra khi không còn việc khác."
    so = f"Sale làm theo «{nhan}» {lam}/{tong} lần. " if tong else f"«{nhan}»: "
    return so + "Co-Pilot đưa loại việc này lên trước khi hợp giai đoạn của lead."


async def quyet_dinh_bai_hoc(db: AsyncSession, nguoi, code: str, huong: str | None, quyet_dinh: str) -> dict | None:
    """Quản trị duyệt / bỏ qua / gỡ một bài học. Trả bản ghi đã lưu (None khi gỡ)."""
    if code not in LOAI_GOI_Y or code == LOAI_KHAC:
        raise ValueError("Loại gợi ý không hợp lệ")
    if quyet_dinh not in QUYET_DINH:
        raise ValueError("Quyết định phải là duyet, tu_choi hoặc go")
    if quyet_dinh != "go" and huong not in HUONG:
        raise ValueError("Hướng phải là uu_tien hoặc ha")

    kho = await get_setting_json(db, KHOA_BAI_HOC)
    cua_agent = _cua_agent(kho, AGENT_SALES_COPILOT)
    if quyet_dinh == "go":
        cua_agent.pop(code, None)
        ban = None
    else:
        ban = {
            "huong": huong,
            "trang_thai": DA_DUYET if quyet_dinh == "duyet" else TU_CHOI,
            "boi": nguoi.id,
            "ten": nguoi.full_name,
            "luc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        }
        cua_agent[code] = ban
    kho[AGENT_SALES_COPILOT] = cua_agent
    await set_setting_json(db, KHOA_BAI_HOC, kho)
    return ban


# ---------------------------------------------------------------------------
# Bảng theo dõi
# ---------------------------------------------------------------------------

def _tuan_vn(moc: datetime) -> date:
    """Thứ Hai (giờ VN) của tuần chứa mốc này. Cột lưu UTC naive."""
    if moc.tzinfo is not None:
        moc = moc.astimezone(timezone.utc).replace(tzinfo=None)
    ngay = (moc + GIO_VN).date()
    return ngay - timedelta(days=ngay.weekday())


def _ty_le(tu: int, mau: int) -> float | None:
    return round(tu / mau, 4) if mau else None


def _ty_le_lam_theo(tuan: list[dict]) -> float | None:
    lam = sum(t["lam"] for t in tuan)
    return _ty_le(lam, lam + sum(t["bo_qua"] for t in tuan))


async def bang_theo_doi(db: AsyncSession, so_tuan: int = 12, bay_gio: datetime | None = None) -> dict:
    bay_gio = bay_gio or datetime.now(timezone.utc)
    tuan_nay = _tuan_vn(bay_gio)
    tuan_dau = tuan_nay - timedelta(weeks=so_tuan - 1)
    moc = datetime.combine(tuan_dau, time()) - GIO_VN  # UTC naive, khớp kiểu cột

    rows = (await db.execute(
        select(AiRun.agent, AiRun.source, AiRun.model_used, AiRun.created_at, AiRun.so_lan_dung_lai)
        .where(AiRun.created_at >= moc)
    )).all()
    goi_y = (await db.execute(
        select(AiRun.output_json, AiRun.outcome, AiRun.created_at)
        .where(AiRun.agent == AGENT_SALES_COPILOT, AiRun.created_at >= moc)
    )).all()

    tuan_ds = [tuan_dau + timedelta(weeks=i) for i in range(so_tuan)]
    theo_tuan = {t: {"chay": 0, "llm": 0, "rule": 0, "dung_lai": 0, "lam": 0, "bo_qua": 0} for t in tuan_ds}
    theo_agent: dict[str, dict] = defaultdict(lambda: {"chay": 0, "llm": 0, "rule": 0, "dung_lai": 0})
    theo_model: Counter = Counter()

    for r in rows:
        o = theo_tuan.get(_tuan_vn(r.created_at))
        if o is None:
            continue
        nguon = "llm" if r.source == SOURCE_LLM else "rule"
        dung_lai = r.so_lan_dung_lai or 0
        a = theo_agent[r.agent]
        for kho in (o, a):
            kho["chay"] += 1
            kho[nguon] += 1
            kho["dung_lai"] += dung_lai
        if r.source == SOURCE_LLM and r.model_used:
            theo_model[r.model_used] += 1

    loai: dict[str, dict] = defaultdict(lambda: {"lam": 0, "bo_qua": 0, "chua_phan_hoi": 0})
    ap_bai_hoc = {"so_goi_y": 0, "lam": 0, "bo_qua": 0}
    for r in goi_y:
        o = theo_tuan.get(_tuan_vn(r.created_at))
        if o is None:
            continue
        noi_dung = ai_memory.doc_output(r)
        tk = loai[loai_cua(noi_dung)]
        khoa = {OUTCOME_DONE: "lam", OUTCOME_SKIPPED: "bo_qua"}.get(r.outcome or "")
        if khoa:
            o[khoa] += 1
            tk[khoa] += 1
        else:
            tk["chua_phan_hoi"] += 1
        if noi_dung.get("theo_bai_hoc"):
            ap_bai_hoc["so_goi_y"] += 1
            if khoa:
                ap_bai_hoc[khoa] += 1
    ap_bai_hoc["ty_le_lam_theo"] = _ty_le(ap_bai_hoc["lam"], ap_bai_hoc["lam"] + ap_bai_hoc["bo_qua"])

    tuan_list = [
        {
            "tuan": t.isoformat(),
            "nhan": t.strftime("%d/%m"),
            **o,
            "ty_le_lam_theo": _ty_le(o["lam"], o["lam"] + o["bo_qua"]),
        }
        for t, o in theo_tuan.items()
    ]

    so_chay = sum(o["chay"] for o in tuan_list)
    dung_lai = sum(o["dung_lai"] for o in tuan_list)
    llm = sum(o["llm"] for o in tuan_list)
    lam = sum(o["lam"] for o in tuan_list)
    bo_qua = sum(o["bo_qua"] for o in tuan_list)
    gan = _ty_le_lam_theo(tuan_list[-4:])
    truoc = _ty_le_lam_theo(tuan_list[-8:-4]) if len(tuan_list) >= 8 else None

    from app.services.llm_config import ds_du_phong, get_llm_config, llm_available

    cfg = await get_llm_config(db)
    try:
        dang_bat = await llm_available()
    except Exception:  # noqa: BLE001
        dang_bat = False

    loai_list = sorted(
        (
            {
                "code": code,
                "nhan": LOAI_GOI_Y.get(code, code),
                **tk,
                "ty_le_lam": _ty_le(tk["lam"], tk["lam"] + tk["bo_qua"]),
                "ty_le_bo_qua": _ty_le(tk["bo_qua"], tk["lam"] + tk["bo_qua"]),
            }
            for code, tk in loai.items()
        ),
        key=lambda x: (-x["bo_qua"], -(x["ty_le_bo_qua"] or 0), x["code"]),
    )

    bai_hoc = await _ds_bai_hoc(db, loai)

    return {
        "so_tuan": so_tuan,
        "tu_ngay": tuan_dau.isoformat(),
        "tong": {
            "so_lan_chay": so_chay,
            "dung_lai": dung_lai,
            # phần câu trả lời lấy từ bộ nhớ trên tổng câu trả lời (chạy mới + dùng lại)
            "ty_le_dung_lai": _ty_le(dung_lai, so_chay + dung_lai),
            "llm": llm,
            "rule": so_chay - llm,
            "ty_le_llm": _ty_le(llm, so_chay),
            "so_goi_y": len(goi_y),
            "lam": lam,
            "bo_qua": bo_qua,
            "ty_le_phan_hoi": _ty_le(lam + bo_qua, len(goi_y)),
            "ty_le_lam_theo": _ty_le(lam, lam + bo_qua),
            "ty_le_lam_theo_4_tuan": gan,
            "ty_le_lam_theo_4_tuan_truoc": truoc,
            "chenh_lech": round(gan - truoc, 4) if gan is not None and truoc is not None else None,
            "ap_bai_hoc": ap_bai_hoc,
        },
        "theo_tuan": tuan_list,
        "theo_agent": sorted(
            ({"agent": k, "ten": TEN_AGENT.get(k, k), **v} for k, v in theo_agent.items()),
            key=lambda x: -x["chay"],
        ),
        "model": {
            "dang_bat": bool(dang_bat),
            "chinh": cfg.get("llm_model") or None,
            "du_phong": [x["model"] for x in ds_du_phong(cfg)],
            "da_tra_loi": [{"model": m, "so_lan": n} for m, n in theo_model.most_common(8)],
        },
        "theo_loai": loai_list,
        "bai_hoc": bai_hoc,
        "so_cho_duyet": sum(1 for b in bai_hoc if b["trang_thai"] == "cho_duyet" or b["de_xuat_moi"]),
        "nguong": {"mau_toi_thieu": MAU_TOI_THIEU, "bo_qua": NGUONG_BO_QUA, "lam": NGUONG_LAM},
    }


_THU_TU_TRANG_THAI = {"cho_duyet": 0, "dang_ap_dung": 1, "da_bo_qua": 2}


async def _ds_bai_hoc(db: AsyncSession, loai: dict[str, dict]) -> list[dict]:
    """Ghép số liệu từng loại với quyết định đã lưu thành danh sách bài học cho quản trị."""
    kho = _cua_agent(await get_setting_json(db, KHOA_BAI_HOC), AGENT_SALES_COPILOT)
    ds = []
    for code in sorted(set(loai) | set(kho)):
        if code not in LOAI_GOI_Y or code == LOAI_KHAC:
            continue
        tk = loai.get(code) or {"lam": 0, "bo_qua": 0}
        luu = kho.get(code) if isinstance(kho.get(code), dict) else None
        de_xuat = de_xuat_huong(tk["lam"], tk["bo_qua"])
        de_xuat_moi = None
        if luu and luu.get("trang_thai") == DA_DUYET and luu.get("huong") in HUONG:
            trang_thai, huong = "dang_ap_dung", luu["huong"]
            if de_xuat and de_xuat != huong:
                de_xuat_moi = de_xuat
        elif luu and luu.get("trang_thai") == TU_CHOI and luu.get("huong") == de_xuat:
            trang_thai, huong = "da_bo_qua", de_xuat
        elif de_xuat:
            trang_thai, huong = "cho_duyet", de_xuat
        else:
            continue
        nhan = LOAI_GOI_Y[code]
        ds.append({
            "code": code,
            "nhan": nhan,
            "huong": huong,
            "trang_thai": trang_thai,
            "de_xuat_moi": de_xuat_moi,
            "lam": tk["lam"],
            "bo_qua": tk["bo_qua"],
            "noi_dung": _cau_bai_hoc(nhan, huong, tk["lam"], tk["bo_qua"]),
            "quyet_boi": (luu or {}).get("ten"),
            "quyet_luc": (luu or {}).get("luc"),
        })
    ds.sort(key=lambda b: (0 if b["de_xuat_moi"] else _THU_TU_TRANG_THAI[b["trang_thai"]], b["code"]))
    return ds
