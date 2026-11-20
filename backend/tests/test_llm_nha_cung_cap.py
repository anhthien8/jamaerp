"""OpenAI (ChatGPT) + Claude trong chuỗi model: khoá đúng nhà, tham số đúng nhà, JSON, ảnh."""

from types import SimpleNamespace

import pytest

from app.services import llm_config as lc

# Khoá giả — chỉ tiền tố là thật
K_GROQ = "gsk_" + "x" * 20
K_ANT = "sk-ant-" + "x" * 20
K_OAI = "sk-proj-" + "x" * 20
K_OR = "sk-or-" + "x" * 20


def _resp(content, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish, message=SimpleNamespace(content=content))])


def test_nhan_dien_khoa():
    assert lc.ncc_cua_khoa(K_GROQ) == "groq"
    assert lc.ncc_cua_khoa(K_ANT) == "anthropic"
    assert lc.ncc_cua_khoa(K_OR) == "openrouter"
    assert lc.ncc_cua_khoa(K_OAI) == "openai"
    assert lc.ncc_cua_khoa("abc") is None


@pytest.mark.parametrize("model,key,hop", [
    ("anthropic/claude-haiku-5-5", K_ANT, True),
    ("anthropic/claude-haiku-5-5", K_OAI, False),
    ("anthropic/claude-haiku-5-5", K_GROQ, False),
    ("openai/gpt-5.4-mini", K_OAI, True),
    ("openai/gpt-5.4-mini", K_ANT, False),
    ("openai/gpt-5.4-mini", K_GROQ, False),
    ("groq/openai/gpt-oss-120b", K_OAI, False),
    ("opencode/deepseek-v4-pro", K_ANT, False),
    ("openrouter/x/y", K_OR, True),
    ("openrouter/x/y", K_OAI, False),
])
def test_khoa_chi_di_dung_nha(model, key, hop):
    assert lc._khoa_hop(model, key) is hop


def test_ten_tran_gan_tien_to():
    assert lc.chuan_model("claude-sonnet-5-5") == "anthropic/claude-sonnet-5-5"
    assert lc.chuan_model("gpt-5.5") == "openai/gpt-5.5"
    assert lc.nha_cung_cap("claude-opus-5-5") == "anthropic"
    assert lc.chuan_model("groq/openai/gpt-oss-120b") == "groq/openai/gpt-oss-120b"


def test_presets_co_ca_tra_phi():
    tra_phi = [p["model"] for p in lc.MODEL_PRESETS if p.get("tra_phi")]
    assert "openai/gpt-5.5" in tra_phi and "anthropic/claude-haiku-5-5" in tra_phi


def test_tham_so_claude_bo_temperature_va_json():
    p = lc.tham_so_goi("anthropic/claude-sonnet-5-5", [], 0.3, 200, K_ANT, {"type": "json_object"})
    assert "temperature" not in p and "response_format" not in p
    assert p["max_tokens"] >= 4000 and p["api_key"] == K_ANT


def test_tham_so_gpt5_suy_luan():
    p = lc.tham_so_goi("openai/gpt-5.4-mini", [], 0.3, 200, K_OAI, {"type": "json_object"})
    assert "temperature" not in p and p["reasoning_effort"] == "low"
    assert p["response_format"] == {"type": "json_object"} and p["max_tokens"] >= 4000


def test_tham_so_groq_giu_nguyen():
    p = lc.tham_so_goi("groq/openai/gpt-oss-120b", [], 0.3, 200, K_GROQ)
    assert p["temperature"] == 0.3 and p["max_tokens"] == 200 and "drop_params" not in p


def test_boc_json():
    rao = chr(96) * 3
    assert lc.boc_json(rao + "json\n{\"a\": 1}\n" + rao) == '{"a": 1}'
    assert lc.boc_json('Đây là kết quả: {"a": [1]} xong') == '{"a": [1]}'
    assert lc.boc_json("không có json") == "không có json"


@pytest.mark.asyncio
async def test_claude_tu_choi_thi_sang_model_ke(monkeypatch):
    cfg = {"llm_model": "anthropic/claude-haiku-5-5", "llm_api_key": K_ANT,
           "llm_fallbacks": '[{"model": "openai/gpt-5.4-mini", "api_key": "' + K_OAI + '"}]'}

    async def _cfg(db=None):
        return cfg
    goi = []

    async def gia(**kw):
        goi.append(kw["model"])
        if kw["model"].startswith("anthropic/"):
            return _resp("", "refusal")
        return _resp(chr(96) * 3 + '\n{"ok": true}\n' + chr(96) * 3)
    monkeypatch.setattr(lc, "get_llm_config", _cfg)
    monkeypatch.setattr(lc, "acompletion", gia)
    r = await lc.llm_complete([{"role": "user", "content": "x"}], response_format={"type": "json_object"})
    assert goi == ["anthropic/claude-haiku-5-5", "openai/gpt-5.4-mini"]
    assert r.choices[0].message.content == '{"ok": true}'


def test_anh_bo_qua_opencode_openrouter():
    cfg = {"llm_model": "opencode/deepseek-v4-pro", "llm_api_key": K_OAI,
           "llm_fallbacks": ('[{"model": "openrouter/x/y", "api_key": "' + K_OR + '"},'
                             '{"model": "groq/openai/gpt-oss-120b", "api_key": "' + K_GROQ + '"},'
                             '{"model": "anthropic/claude-haiku-5-5", "api_key": "' + K_ANT + '"}]')}
    ds = lc.ds_lan_thu_anh(cfg, "groq/meta-llama/vision")
    assert [m for m, _ in ds] == ["groq/meta-llama/vision", "anthropic/claude-haiku-5-5"]


def test_mask_giu_tien_to():
    from app.api.ai_settings import _mask
    assert _mask(K_ANT).startswith("sk-ant-****") and _mask(K_ANT).endswith("xxxx")
    assert K_ANT not in _mask(K_ANT)


@pytest.mark.asyncio
async def test_doc_cccd_chuyen_model_khi_loi(monkeypatch):
    from app.services import khach_hang
    cfg = {"llm_model": "groq/openai/gpt-oss-120b", "llm_api_key": K_GROQ,
           "llm_fallbacks": '[{"model": "anthropic/claude-haiku-5-5", "api_key": "' + K_ANT + '"}]'}

    async def _cfg(db=None):
        return cfg
    goi = []

    async def gia(**kw):
        goi.append(kw["model"])
        if kw["model"].startswith("groq/"):
            raise RuntimeError("quota")
        assert "response_format" not in kw
        return _resp('Kết quả: {"ho_ten": "Nguyễn Văn A", "so_cccd": "079123456789", "ngay_sinh": "1990-01-02"}')
    monkeypatch.setattr(lc, "get_llm_config", _cfg)
    monkeypatch.setattr(lc, "acompletion", gia)
    kq = await khach_hang.doc_cccd(b"anh")
    assert goi[-1] == "anthropic/claude-haiku-5-5" and kq["national_id"] == "079123456789"


@pytest.mark.asyncio
async def test_trich_anh_khong_co_model_doc_anh_bao_503(monkeypatch):
    from app.services import vat_tu_bao_gia_tep as vt

    async def _cfg(db=None):
        return {"llm_model": "opencode/deepseek-v4-pro", "llm_api_key": K_OAI}
    monkeypatch.setattr(lc, "get_llm_config", _cfg)
    with pytest.raises(vt.TepError) as e:
        await vt.trich_tu_anh(b"anh", "image/png")
    assert e.value.status == 503
