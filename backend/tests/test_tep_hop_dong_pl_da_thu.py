"""Tệp hợp đồng đã ký + P&L tính doanh thu theo đợt đã thu (26/10/2026)."""
import uuid

import pytest
from httpx import AsyncClient

from app.cache import cache
from app.models.contract import Contract
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _hd(db, project_id, **kw) -> Contract:
    c = Contract(id=str(uuid.uuid4()), code=f"HD-{uuid.uuid4().hex[:6]}", project_id=project_id,
                 title="HĐ thi công", **kw)
    db.add(c)
    await db.commit()
    return c


class TestTepHopDong:
    async def test_tai_len_xem_tai_ve_go(self, client: AsyncClient, admin_user, sales_user, project_with_financials, db_session):
        hd = await _hd(db_session, project_with_financials.id, status="signed", total_value=1)
        pdf = b"%PDF-1.4 hop dong da ky"
        r = await client.post(f"/api/v1/contracts/{hd.id}/files",
                              files=[("files", ("HĐ đã ký.pdf", pdf, "application/pdf"))],
                              headers=auth_header(admin_user))
        assert r.status_code == 201, r.text
        fid = r.json()["items"][0]["id"]

        ds = await client.get(f"/api/v1/contracts/{hd.id}/files", headers=auth_header(admin_user))
        assert [x["filename"] for x in ds.json()["items"]] == ["HĐ đã ký.pdf"]

        g = await client.get(f"/api/v1/contracts/{hd.id}/files/{fid}/download?inline=true", headers=auth_header(admin_user))
        assert g.status_code == 200 and g.content == pdf
        assert g.headers["content-disposition"].startswith("inline")

        x = await client.delete(f"/api/v1/contracts/{hd.id}/files/{fid}", headers=auth_header(sales_user))
        assert x.status_code == 403
        x = await client.delete(f"/api/v1/contracts/{hd.id}/files/{fid}", headers=auth_header(admin_user))
        assert x.status_code == 200
        ds = await client.get(f"/api/v1/contracts/{hd.id}/files", headers=auth_header(admin_user))
        assert ds.json()["items"] == []

    async def test_chan_duoi_la_va_khong_quyen(self, client: AsyncClient, admin_user, designer_user, project_with_financials, db_session, monkeypatch):
        hd = await _hd(db_session, project_with_financials.id, status="draft")
        r = await client.post(f"/api/v1/contracts/{hd.id}/files",
                              files=[("files", ("x.exe", b"MZ", "application/octet-stream"))],
                              headers=auth_header(admin_user))
        assert r.status_code == 400
        from app.api import contracts as api_hd

        async def khong_quyen(u, db):
            return {}
        monkeypatch.setattr(api_hd, "quyen_hieu_luc", khong_quyen)  # vai không có ô «Tạo Hợp đồng»
        r = await client.post(f"/api/v1/contracts/{hd.id}/files",
                              files=[("files", ("a.pdf", b"%PDF", "application/pdf"))],
                              headers=auth_header(designer_user))
        assert r.status_code == 403


class TestPLDaThu:
    async def test_doanh_thu_la_tien_da_thu(self, client: AsyncClient, admin_user, project_with_financials, db_session):
        cache.clear_prefix("pl")
        p = project_with_financials.id
        await _hd(db_session, p, status="signed", total_value=1_000_000_000, payment_terms={"installments": [
            {"name": "Đợt 1", "percentage": 30, "status": "paid"},
            {"name": "Đợt 2", "percentage": 70, "status": "pending"},
        ]})
        await _hd(db_session, p, status="draft", total_value=None, payment_terms={"installments": [
            {"name": "Cọc", "percentage": 0, "status": "paid", "amount": 50_000_000},
        ]})
        await _hd(db_session, p, status="cancelled", total_value=9e9, payment_terms={"installments": [
            {"name": "x", "percentage": 100, "status": "paid"},
        ]})
        r = await client.get(f"/api/v1/pl/projects/{p}", headers=auth_header(admin_user))
        d = r.json()
        # fixture 4,5 tỷ đã thu đủ + 300tr + 50tr cọc
        assert d["revenue"] == 4_500_000_000 + 300_000_000 + 50_000_000
        assert d["contract_value"] == 4_500_000_000 + 1_000_000_000
        s = (await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))).json()
        assert s["total_revenue"] == d["revenue"] and s["total_contract_value"] == d["contract_value"]
