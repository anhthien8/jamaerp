"""NCC tự tạo từ Vật tư + mã số thuế (26/10/2026)."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.project import Project
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu
from app.services import ncc as ncc_svc
from tests.conftest import _uid, auth_header


@pytest_asyncio.fixture
async def thu_mua(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Thu Mua NCC", email="thumua.ncc@test.com", password_hash=hash_password("x"),
             role="data_entry", department="PURCHASING", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


async def _so_ncc(db) -> int:
    return (await db.execute(select(func.count()).select_from(Supplier))).scalar()


def test_chuan_mst():
    assert ncc_svc.chuan_mst(" 0100109106 ") == "0100109106"
    assert ncc_svc.chuan_mst("0100109106-001") == "0100109106-001"
    assert ncc_svc.chuan_mst("12345") is None


@pytest.mark.asyncio
async def test_mau_go_ten_ncc_tu_tao_va_khong_trung(client: AsyncClient, db_session, thu_mua):
    db_session.add(Supplier(id=_uid(), name="Hiệp Phát"))
    await db_session.commit()
    truoc = await _so_ncc(db_session)
    r = await client.post("/api/v1/vat-tu/mau", json={"ma": "HP1", "ncc_gan_nhat_ten": "  hiệp   phát "},
                          headers=auth_header(thu_mua))
    assert r.status_code == 201 and r.json()["ncc_gan_nhat_ten"] == "Hiệp Phát"
    assert await _so_ncc(db_session) == truoc
    r = await client.post("/api/v1/vat-tu/mau", json={"ma": "DS1", "ncc_gan_nhat_ten": "Daisan"},
                          headers=auth_header(thu_mua))
    assert r.status_code == 201
    assert await _so_ncc(db_session) == truoc + 1
    ten = [x["name"] for x in (await client.get("/api/v1/vat-tu/ncc", headers=auth_header(thu_mua))).json()]
    assert "Daisan" in ten and "Hiệp Phát" in ten


@pytest.mark.asyncio
async def test_bao_gia_bot_tao_ncc_kem_mst(client: AsyncClient, db_session, thu_mua):
    p = Project(id=_uid(), code="JMH-NCC1", name="Nhà", client_name="K", status="active", total_value=1)
    db_session.add(p)
    await db_session.flush()
    d = DongPhieuVatTu(id=_uid(), project_id=p.id, ma_tu_do="X1", so_luong=1)
    db_session.add(d)
    await db_session.commit()
    r = await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", json={
        "items": [{"dong_id": d.id, "ncc_ten": "Gạch Minh Long", "gia": 100000}],
        "ncc_mst": "0312345678", "ncc_dia_chi": "Q7, TP HCM"}, headers=auth_header(thu_mua))
    assert r.status_code == 201
    s = (await db_session.execute(select(Supplier).where(Supplier.name == "Gạch Minh Long"))).scalar_one()
    assert s.ma_so_thue == "0312345678" and s.address == "Q7, TP HCM"
    b = (await db_session.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalar_one()
    assert b.supplier_id == s.id
    # «NCC chưa rõ» không tạo NCC rác
    truoc = await _so_ncc(db_session)
    await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", json={
        "items": [{"dong_id": d.id, "ncc_ten": "NCC chưa rõ", "gia": 1}]}, headers=auth_header(thu_mua))
    assert await _so_ncc(db_session) == truoc


@pytest.mark.asyncio
async def test_tra_mst(client: AsyncClient, admin_user, monkeypatch):
    async def gia(mst):
        return {"ma_so_thue": mst, "ten_cong_ty": "CÔNG TY A", "dia_chi": "HN"}
    monkeypatch.setattr(ncc_svc, "tra_mst", gia)
    r = await client.get("/api/v1/suppliers/tra-mst/abc", headers=auth_header(admin_user))
    assert r.status_code == 400
    r = await client.get("/api/v1/suppliers/tra-mst/0100109106", headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["ten_cong_ty"] == "CÔNG TY A"


def test_model_ai_da_tat_va_opencode():
    from app.services import llm_config as lc
    assert lc.chuan_model("groq/llama-3.1-8b-instant") == "groq/openai/gpt-oss-20b"
    assert lc.tham_so_model("opencode/deepseek-v4.1-flash-free") == {
        "model": "openai/deepseek-v4.1-flash-free", "api_base": lc.OPENCODE_API_BASE}
    assert lc.tham_so_model("groq/llama-3.3-70b-versatile") == {"model": "groq/openai/gpt-oss-120b"}


@pytest.mark.asyncio
async def test_fallback_khac_nha_cung_cap_khong_muon_key(monkeypatch):
    from app.services import llm_config as lc
    async def cfg(db=None):
        return {"llm_model": "groq/openai/gpt-oss-120b", "llm_api_key": "gsk_x",
                "llm_fallback_model": "opencode/deepseek-v4.1-flash-free", "llm_fallback_api_key": ""}
    goi = []
    async def fake(**p):
        goi.append(p)
        raise RuntimeError("down")
    monkeypatch.setattr(lc, "get_llm_config", cfg)
    monkeypatch.setattr(lc, "acompletion", fake)
    with pytest.raises(RuntimeError):
        await lc.llm_complete([{"role": "user", "content": "hi"}])
    assert [p["model"] for p in goi] == ["groq/openai/gpt-oss-120b"]


@pytest.mark.asyncio
async def test_chuoi_nhieu_du_phong_muon_khoa_cung_nha(monkeypatch):
    import json
    from app.services import llm_config as lc
    async def cfg(db=None):
        return {"llm_model": "opencode/deepseek-v4.1-flash-free", "llm_api_key": "gsk_sai_nha",
                "llm_fallbacks": json.dumps([
                    {"model": "groq/openai/gpt-oss-120b", "api_key": "gsk_dung"},
                    {"model": "opencode/deepseek-v4.1-flash", "api_key": "sk-oc"},
                    {"model": "groq/qwen/qwen3.8-27b", "api_key": ""},
                ])}
    goi = []
    async def fake(**p):
        goi.append((p["model"], p.get("api_key")))
        raise RuntimeError("down")
    monkeypatch.setattr(lc, "get_llm_config", cfg)
    monkeypatch.setattr(lc, "acompletion", fake)
    with pytest.raises(RuntimeError):
        await lc.llm_complete([{"role": "user", "content": "hi"}])
    # model chính bị bỏ vì khoá Groq không gửi sang OpenCode; dự phòng 3 mượn khoá Groq
    assert goi == [("groq/openai/gpt-oss-120b", "gsk_dung"), ("openai/deepseek-v4.1-flash", "sk-oc"),
                   ("groq/qwen/qwen3.8-27b", "gsk_dung")]


@pytest.mark.asyncio
async def test_api_luu_chuoi_du_phong_giu_khoa(client, admin_user):
    from app.services.llm_config import invalidate_llm_cache
    r = await client.put("/api/v1/ai-settings", json={"fallbacks": [
        {"model": "groq/openai/gpt-oss-120b", "api_key": "gsk_abcdefghijkl"},
        {"model": "opencode/deepseek-v4.1-flash", "api_key": "sk-ocabcdefgh"}]}, headers=auth_header(admin_user))
    assert r.status_code == 200 and len(r.json()["fallbacks"]) == 2
    invalidate_llm_cache()
    r = await client.put("/api/v1/ai-settings", json={"fallbacks": [
        {"model": "opencode/deepseek-v4.1-flash", "api_key": ""}]}, headers=auth_header(admin_user))
    fb = r.json()["fallbacks"]
    assert fb[0]["api_key_set"] is True and "sk-ocabcdefgh" not in r.text
    assert r.json()["llm_fallback_model"] == "opencode/deepseek-v4.1-flash"


@pytest.mark.asyncio
async def test_nut_test_thu_tung_mat_xich(client, admin_user, monkeypatch):
    from app.services import llm_config as lc
    import json
    async def cfg(db=None):
        return {"llm_model": "groq/openai/gpt-oss-120b", "llm_api_key": "gsk_chinh12345",
                "llm_fallbacks": json.dumps([{"model": "groq/openai/gpt-oss-20b", "api_key": "gsk_phu123456"},
                                             {"model": "opencode/deepseek-v4.1-flash", "api_key": "sk-oc12345678"}])}
    monkeypatch.setattr(lc, "get_llm_config", cfg)
    goi = []
    class R:
        def __init__(s, t): s.choices = [type("C", (), {"message": type("M", (), {"content": t})()})()]
    async def fake(**p):
        goi.append(p.get("api_key"))
        if p.get("api_key") == "gsk_phu123456":
            raise RuntimeError("401 sai khoá")
        return R("Chào")
    monkeypatch.setattr(lc, "acompletion", fake)
    r = (await client.post("/api/v1/ai-settings/test", headers=auth_header(admin_user))).json()
    assert goi == ["gsk_chinh12345", "gsk_phu123456", "sk-oc12345678"]
    assert [x["status"] for x in r["ket_qua"]] == ["ok", "error", "ok"] and r["status"] == "ok"
    assert "gsk_phu123456" not in str(r)
