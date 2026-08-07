"""Kiểm thử cờ nhúng worker (EMBED_WORKER) — CHỈ test gating, không chạy vòng lặp.

Mục tiêu: chắc chắn worker nền chỉ được nhúng khi đúng điều kiện (prod/dev bật cờ)
và bị chặn trong môi trường test. KHÔNG khởi động vòng lặp job nền thật ở đây.
"""

from app.config import Settings
from app import worker as worker_mod


def test_embed_worker_mac_dinh_true(monkeypatch):
    """Mặc định EMBED_WORKER = True (Railway prod cần worker nhúng)."""
    monkeypatch.delenv("EMBED_WORKER", raising=False)
    s = Settings(_env_file=None)
    assert s.EMBED_WORKER is True


def test_embed_worker_tat_qua_env(monkeypatch):
    """Env EMBED_WORKER=false → parse thành False (compose/VPS chống chạy đôi)."""
    monkeypatch.setenv("EMBED_WORKER", "false")
    s = Settings(_env_file=None)
    assert s.EMBED_WORKER is False


def _should_embed(s: Settings) -> bool:
    """Tái hiện điều kiện gating trong lifespan của main.py."""
    return bool(s.EMBED_WORKER) and s.APP_ENV != "test"


def test_gating_chan_khi_app_env_test():
    """APP_ENV=test → KHÔNG nhúng worker dù cờ bật (bảo vệ pytest)."""
    s = Settings(_env_file=None, EMBED_WORKER=True, APP_ENV="test")
    assert _should_embed(s) is False


def test_gating_chan_khi_co_tat():
    """EMBED_WORKER=false → KHÔNG nhúng worker (compose/VPS)."""
    s = Settings(_env_file=None, EMBED_WORKER=False, APP_ENV="production")
    assert _should_embed(s) is False


def test_gating_bat_khi_prod():
    """Prod + cờ bật → nhúng worker (đúng hành vi trên Railway)."""
    s = Settings(_env_file=None, EMBED_WORKER=True, APP_ENV="production")
    assert _should_embed(s) is True


def test_gating_bat_khi_dev():
    """Dev (mặc định) + cờ bật → nhúng worker (start-demo dùng bản nhúng)."""
    s = Settings(_env_file=None, EMBED_WORKER=True, APP_ENV="development")
    assert _should_embed(s) is True


def test_worker_expose_ham_nhung():
    """worker.py phải expose start_embedded/stop_embedded cho lifespan dùng."""
    assert callable(worker_mod.start_embedded)
    assert callable(worker_mod.stop_embedded)
