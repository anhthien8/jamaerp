"""Hai trường khi thêm lead: Khu vực + Ngân sách 3 mức (22/09/2026).

Chủ dự án yêu cầu bổ sung 2 trường. Đo prod trước khi làm:
  - `region` (Khu vực): ĐÃ có cột, ĐÃ có ô chọn 10 khu vực trên form thêm lead,
    ĐÃ có bộ lọc. 94/615 lead có giá trị. ⇒ không làm lại, chỉ khóa bằng test.
  - `estimated_budget`: là SỐ TIỀN, 79/615 lead đã có số thật, và báo giá/hợp
    đồng đang dùng. ⇒ thêm cột mức riêng `ngan_sach_khoang`, giữ cột số.
"""

import pytest
from sqlalchemy import select

from app.models.lead import Lead, NGAN_SACH_KHOANG
from tests.conftest import auth_header


async def _tao_lead(client, admin, **truong):
    resp = await client.post(
        "/api/v1/leads",
        json={"name": "Chị Hoa", "phone": "0901112223", **truong},
        headers=auth_header(admin),
    )
    return resp


@pytest.mark.asyncio
async def test_ba_muc_ngan_sach_dung_nhu_chot(client):
    assert list(NGAN_SACH_KHOANG) == ["duoi_200", "tu_200_500", "tren_500"]


@pytest.mark.asyncio
@pytest.mark.parametrize("muc", ["duoi_200", "tu_200_500", "tren_500"])
async def test_them_lead_luu_duoc_muc_ngan_sach(client, db_session, admin_user, muc):
    resp = await _tao_lead(client, admin_user, ngan_sach_khoang=muc)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ngan_sach_khoang"] == muc
    lead = (await db_session.execute(
        select(Lead).where(Lead.id == resp.json()["id"])
    )).scalar_one()
    assert lead.ngan_sach_khoang == muc


@pytest.mark.asyncio
async def test_them_lead_luu_duoc_khu_vuc(client, admin_user):
    resp = await _tao_lead(client, admin_user, region="Gò Vấp")
    assert resp.status_code == 200, resp.text
    assert resp.json()["region"] == "Gò Vấp"


@pytest.mark.asyncio
async def test_muc_ngan_sach_la_khoang_va_so_tien_song_song(client, admin_user):
    """Mức để lọc/phân khúc, số tiền để tính — hai trường ĐỘC LẬP, không ghi đè nhau."""
    resp = await _tao_lead(client, admin_user, ngan_sach_khoang="tren_500",
                           estimated_budget=800000)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ngan_sach_khoang"] == "tren_500"
    assert resp.json()["estimated_budget"] == 800000


@pytest.mark.asyncio
async def test_muc_ngan_sach_sai_thi_bao_loi(client, admin_user):
    """Sai khóa phải 400 rõ ràng, không lặng lẽ lưu rác vào cột."""
    resp = await _tao_lead(client, admin_user, ngan_sach_khoang="rat_nhieu_tien")
    assert resp.status_code == 400, resp.text
    assert "không hợp lệ" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_bo_trong_hai_truong_van_tao_duoc(client, admin_user):
    """Hai trường là tùy chọn — sale chưa hỏi được thì vẫn nhập lead trước."""
    resp = await _tao_lead(client, admin_user)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ngan_sach_khoang"] is None
    assert resp.json()["region"] is None


@pytest.mark.asyncio
async def test_sua_lead_doi_duoc_hai_truong(client, admin_user):
    """LeadUpdate có `extra: forbid` — trường mới phải được khai báo, không thì
    API trả 200 mà chẳng đổi gì (lớp bug «lưu giả» đã gặp nhiều lần)."""
    lead_id = (await _tao_lead(client, admin_user)).json()["id"]
    resp = await client.put(
        f"/api/v1/leads/{lead_id}",
        json={"region": "Thủ Đức", "ngan_sach_khoang": "duoi_200"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["region"] == "Thủ Đức"
    assert resp.json()["ngan_sach_khoang"] == "duoi_200"


@pytest.mark.asyncio
async def test_sua_lead_muc_sai_thi_bao_loi(client, admin_user):
    lead_id = (await _tao_lead(client, admin_user)).json()["id"]
    resp = await client.put(f"/api/v1/leads/{lead_id}",
                            json={"ngan_sach_khoang": "sai_be_bet"},
                            headers=auth_header(admin_user))
    assert resp.status_code == 400
