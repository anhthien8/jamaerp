"""Ảnh mẫu vật tư tải từ máy + link Shopee + «Gửi thử» Web Push trả kết quả thật (25/10/2026)."""
import base64
import io

import pytest

pytestmark = pytest.mark.asyncio
from httpx import AsyncClient

from app.services import web_push
from tests.conftest import auth_header
from tests.test_vat_tu import thiet_ke, thu_mua  # noqa: F401 — fixture dùng chung


def _png(w=1200, h=600) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (w, h), (200, 30, 30, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _b64(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


class TestTaiAnhMau:
    async def test_thu_mua_tai_anh_ra_url_ky_va_xem_duoc(self, client: AsyncClient, thu_mua):
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": _b64(_png())}, headers=auth_header(thu_mua))
        assert r.status_code == 201, r.text
        url = r.json()["anh_url"]
        assert url.startswith("/media/vat-tu/") and url.endswith(".jpg")
        # Server ép về JPG cạnh dài ≤800
        g = await client.get("/api/v1" + url)
        assert g.status_code == 200 and g.headers["content-type"] == "image/jpeg"
        from PIL import Image

        im = Image.open(io.BytesIO(g.content))
        assert max(im.size) <= 800 and im.size[0] == 2 * im.size[1]

    async def test_chu_ky_sai_404(self, client: AsyncClient, thu_mua):
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": _b64(_png(50, 50))}, headers=auth_header(thu_mua))
        anh_id = r.json()["id"]
        g = await client.get(f"/api/v1/media/vat-tu/{anh_id}/0000000000000000.jpg")
        assert g.status_code == 404

    async def test_thiet_ke_khong_duoc_tai(self, client: AsyncClient, thiet_ke):
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": _b64(_png(50, 50))}, headers=auth_header(thiet_ke))
        assert r.status_code == 403

    async def test_khong_phai_anh_422(self, client: AsyncClient, thu_mua):
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": _b64(b"khong phai anh")}, headers=auth_header(thu_mua))
        assert r.status_code == 422
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": "@@@"}, headers=auth_header(thu_mua))
        assert r.status_code == 422

    async def test_mau_luu_anh_url_va_link_shopee(self, client: AsyncClient, thu_mua):
        r = await client.post("/api/v1/vat-tu/anh", json={"data_base64": _b64(_png(50, 50))}, headers=auth_header(thu_mua))
        url = r.json()["anh_url"]
        m = await client.post("/api/v1/vat-tu/mau", json={
            "ma": "VT-ANH-1", "nhom": "60x60", "anh_url": url, "link_shopee": "https://shopee.vn/x-i.1.2",
        }, headers=auth_header(thu_mua))
        assert m.status_code in (200, 201), m.text
        d = m.json()
        assert d["anh_url"] == url and d["link_shopee"] == "https://shopee.vn/x-i.1.2"
        s = await client.put(f"/api/v1/vat-tu/mau/{d['id']}", json={"ma": "VT-ANH-1", "link_shopee": None}, headers=auth_header(thu_mua))
        assert s.json()["link_shopee"] is None


class TestGuiThuPush:
    async def test_chua_cau_hinh_vapid_bao_ro(self, client: AsyncClient, thu_mua, monkeypatch):
        monkeypatch.setattr(web_push, "bat", lambda: False)
        r = await client.post("/api/v1/push/test", headers=auth_header(thu_mua))
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is False and "VAPID" in d["reason"]

    async def test_chua_dang_ky_may_bao_ro(self, client: AsyncClient, thu_mua, monkeypatch):
        monkeypatch.setattr(web_push, "bat", lambda: True)
        r = await client.post("/api/v1/push/test", headers=auth_header(thu_mua))
        d = r.json()
        assert d["ok"] is False and d["devices"] == 0 and "đăng ký" in d["reason"]

    async def test_tra_ma_tung_may(self, client: AsyncClient, thu_mua, monkeypatch):
        monkeypatch.setattr(web_push, "bat", lambda: True)
        sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "p" * 20, "auth": "a" * 10}}
        r = await client.post("/api/v1/push/subscribe", json=sub, headers=auth_header(thu_mua))
        assert r.status_code == 201, r.text
        goi = []

        def gia_gui(s, payload):
            goi.append(payload)
            return 403

        monkeypatch.setattr(web_push, "_gui_mot", gia_gui)
        r = await client.post("/api/v1/push/test", headers=auth_header(thu_mua))
        d = r.json()
        assert d == {"ok": False, "devices": 1, "sent": 0, "codes": [403]}
        assert "ERP" in goi[0]

        monkeypatch.setattr(web_push, "_gui_mot", lambda s, p: 201)
        r = await client.post("/api/v1/push/test", headers=auth_header(thu_mua))
        assert r.json()["ok"] is True and r.json()["sent"] == 1
