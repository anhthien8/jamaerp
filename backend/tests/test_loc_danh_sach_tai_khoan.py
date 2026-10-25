"""Lọc bảng Tài khoản theo đội / tìm trên cả danh sách (25/10/2026)."""

import pytest

from app.models.user import Team
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_loc_theo_doi_va_tim(client, db_session, admin_user, sales_user, accountant_user):
    doi = Team(name="Đội A", code="DOI-A", department="SALES")
    db_session.add(doi)
    await db_session.flush()
    sales_user.team_id = doi.id
    await db_session.commit()
    h = auth_header(admin_user)

    ds = (await client.get(f"/api/v1/users?team_id={doi.id}", headers=h)).json()
    assert [u["id"] for u in ds["items"]] == [sales_user.id] and ds["total"] == 1

    ds = (await client.get("/api/v1/users?team_id=none", headers=h)).json()
    assert {u["id"] for u in ds["items"]} == {admin_user.id, accountant_user.id}

    ds = (await client.get("/api/v1/users?q=ACCOUNTANT&department=ACCT", headers=h)).json()
    assert [u["id"] for u in ds["items"]] == [accountant_user.id]
