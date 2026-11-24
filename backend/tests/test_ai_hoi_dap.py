"""Trợ lý hỏi đáp popup (24/11/2026): /ai/hoi-dap gọi chuỗi model với ngữ cảnh Sổ tay."""

from types import SimpleNamespace

import pytest

from app.api import ai as ai_api
from tests.conftest import auth_header


def _resp(text, model="groq/x"):
    return SimpleNamespace(model=model, choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.mark.asyncio
async def test_hoi_dap_tra_loi_kem_ngu_canh(client, sales_user, monkeypatch):
    goi = {}

    async def _co():
        return True

    async def _llm(messages, **kw):
        goi["messages"] = messages
        return _resp("Bấm **Tạo lead** ở trang Lead.")

    monkeypatch.setattr(ai_api, "llm_available", _co)
    monkeypatch.setattr(ai_api, "llm_complete", _llm)
    r = await client.post("/api/v1/ai/hoi-dap", headers=auth_header(sales_user), json={
        "messages": [{"role": "user", "content": "Tạo lead thế nào?"}],
        "ngu_canh": "## Lead\nBấm Tạo lead",
    })
    assert r.status_code == 200, r.text
    assert r.json() == {"tra_loi": "Bấm **Tạo lead** ở trang Lead.", "model": "groq/x"}
    he_thong = goi["messages"][0]
    assert he_thong["role"] == "system" and "Bấm Tạo lead" in he_thong["content"]
    assert goi["messages"][-1] == {"role": "user", "content": "Tạo lead thế nào?"}


@pytest.mark.asyncio
async def test_hoi_dap_chua_bat_ai_tra_503(client, sales_user, monkeypatch):
    async def _khong():
        return False

    monkeypatch.setattr(ai_api, "llm_available", _khong)
    r = await client.post("/api/v1/ai/hoi-dap", headers=auth_header(sales_user),
                          json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_hoi_dap_chan_tin_cuoi_khong_phai_cau_hoi_va_chua_dang_nhap(client, sales_user):
    r = await client.post("/api/v1/ai/hoi-dap", headers=auth_header(sales_user),
                          json={"messages": [{"role": "assistant", "content": "x"}]})
    assert r.status_code == 400
    r = await client.post("/api/v1/ai/hoi-dap", json={"messages": [{"role": "user", "content": "x"}]})
    assert r.status_code in (401, 403)
