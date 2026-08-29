"""Tách quyền soạn / duyệt / thu tiền (QC 29/08/2026).

QC gọi thử endpoint bằng token vai trò thấp và phát hiện 3 lỗ:

  1. `POST /quotations` — kế toán tạo được báo giá dù ma trận quyền
     (canCreateQuotations=False) LẪN tài liệu công ty đều ghi kế toán là «Đọc».
     Backend không kiểm gì, chỉ FE ẩn nút.
  2. `POST /quotations/{id}/approve` — MỌI tài khoản đăng nhập duyệt được, kể cả
     sale tự duyệt báo giá của chính mình → mất chốt kiểm soát giá bán.
  3. `PUT /contracts/{id}/payments/{idx}` — MỌI tài khoản xem được hợp đồng đều
     đánh dấu được «đã thu tiền» → mất chốt kiểm soát dòng tiền.

Chốt với chủ dự án 29/08: duyệt báo giá = Giám đốc + Trưởng nhóm + Giám sát;
xác nhận thu tiền = Kế toán + Giám đốc + Trưởng nhóm. Sale vẫn SOẠN báo giá và
XEM trạng thái thanh toán bình thường.
"""

import pytest

from tests.conftest import auth_header


async def _tao_bao_gia(client, user, title="BG test"):
    return await client.post(
        "/api/v1/quotations",
        json={"type": "design", "title": title},
        headers=auth_header(user),
    )


# ---------------------------------------------------------------------------
# 1. Tạo/sửa báo giá phải theo canCreateQuotations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ke_toan_khong_tao_duoc_bao_gia(client, accountant_user):
    """Ma trận + tài liệu công ty: kế toán chỉ ĐỌC báo giá."""
    resp = await _tao_bao_gia(client, accountant_user)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_sale_van_tao_va_sua_duoc_bao_gia(client, sales_user):
    """Không chặn nhầm: sale soạn báo giá là việc hằng ngày của họ."""
    resp = await _tao_bao_gia(client, sales_user, "BG cua sale")
    assert resp.status_code == 200, resp.text
    qt_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/quotations/{qt_id}",
        json={"title": "BG cua sale (sua)"},
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_ke_toan_khong_sua_duoc_bao_gia(client, admin_user, accountant_user):
    resp = await _tao_bao_gia(client, admin_user)
    qt_id = resp.json()["id"]
    resp = await client.put(
        f"/api/v1/quotations/{qt_id}",
        json={"title": "ke toan sua"},
        headers=auth_header(accountant_user),
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 2. Duyệt báo giá: tách khỏi quyền soạn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sale_khong_tu_duyet_bao_gia_cua_minh(client, sales_user):
    resp = await _tao_bao_gia(client, sales_user, "BG sale tu duyet")
    assert resp.status_code == 200, resp.text
    qt_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/quotations/{qt_id}/approve", headers=auth_header(sales_user))
    assert resp.status_code == 403, "sale soạn được nhưng KHÔNG được tự duyệt"

    # Vẫn còn ở draft, không bị đổi lén
    resp = await client.get(f"/api/v1/quotations/{qt_id}", headers=auth_header(sales_user))
    assert resp.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_admin_va_supervisor_duyet_duoc(client, admin_user, purchasing_user):
    resp = await _tao_bao_gia(client, admin_user, "BG admin duyet")
    qt_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/quotations/{qt_id}/approve", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# 3. Xác nhận đã thu tiền: chỉ kế toán / giám đốc / trưởng nhóm
# ---------------------------------------------------------------------------

@pytest.fixture
async def _hop_dong(client, admin_user, project):
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-PQ-01", "project_id": project.id, "title": "HD phan quyen"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_sale_khong_xac_nhan_duoc_thu_tien(client, admin_user, sales_user, project):
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-PQ-02", "project_id": project.id, "title": "HD sale"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/contracts/{cid}/payments/0", json={}, headers=auth_header(sales_user)
    )
    assert resp.status_code == 403, "ghi nhận tiền về là việc kế toán"

    # Nhưng sale VẪN xem được hợp đồng + trạng thái thanh toán
    resp = await client.get(f"/api/v1/contracts/{cid}", headers=auth_header(sales_user))
    assert resp.status_code == 200
    assert resp.json()["payment_terms"]["installments"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_ke_toan_xac_nhan_duoc_thu_tien(client, admin_user, accountant_user, project):
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-PQ-03", "project_id": project.id, "title": "HD ke toan"},
        headers=auth_header(admin_user),
    )
    cid = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/contracts/{cid}/payments/0", json={}, headers=auth_header(accountant_user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_terms"]["installments"][0]["status"] == "paid"
