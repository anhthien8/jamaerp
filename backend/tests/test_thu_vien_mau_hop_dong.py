"""Thư viện mẫu hợp đồng / biên bản (25/10/2026)."""

import json

import pytest

from app.api.contract_templates import khoa_tep, phan_loai
from tests.conftest import auth_header

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _tep(ten: str, noi_dung: bytes = b"PK\x03\x04 mau", mime: str = DOCX):
    return ("files", (ten, noi_dung, mime))


@pytest.mark.parametrize("ten,nhom,loai,ten_dep", [
    ("JAMA - HỢP ĐỒNG THI CÔNG CẢI TẠO_2026.docx", "hop_dong", "thi_cong", "Hợp đồng thi công cải tạo"),
    ("JAMA - HỢP ĐỒNG THIẾT KẾ NỘI THẤT - 2026.docx", "hop_dong", "thiet_ke", "Hợp đồng thiết kế nội thất"),
    ("BIÊN BẢN NHẬN MẶT BẰNG.doc", "bien_ban", None, "Biên bản nhận mặt bằng"),
    ("ĐỀ NGHỊ THANH TOÁN CÓ VAT.doc", "thanh_toan", None, "Đề nghị thanh toán có vat"),
    ("XÁC NHẬN THANH TOÁN.doc", "thanh_toan", None, "Xác nhận thanh toán"),
    ("PL02_JMH_PHẠM VI THI CÔNG & VẬT TƯ THÔ THI CÔNG.xlsx", "phu_luc", "thi_cong", None),
    ("PHỤ LỤC C- VẬT TƯ SỬ DỤNG VÀ PHẠM VI CÔNG VIỆC CẢI TẠO - 19.03.docx", "phu_luc", "thi_cong", None),
])
def test_phan_loai_theo_ten_tep(ten, nhom, loai, ten_dep):
    t, n, l = phan_loai(ten)
    assert (n, l) == (nhom, loai)
    if ten_dep:
        assert t == ten_dep


def test_khoa_tep_bo_dau_va_duoi():
    assert khoa_tep("BIÊN BẢN NHẬN MẶT BẰNG.doc") == khoa_tep("bien ban nhan mat bang.docx")


@pytest.mark.asyncio
async def test_ke_toan_tai_len_ca_bo_roi_sale_tai_ve(client, accountant_user, sales_user):
    r = await client.post(
        "/api/v1/contract-templates",
        files=[
            _tep("JAMA - HỢP ĐỒNG THI CÔNG NỘI THẤT.docx", b"PK noi that"),
            _tep("BIÊN BẢN NHẬN MẶT BẰNG.doc", b"\xd0\xcf doc", "application/msword"),
        ],
        headers=auth_header(accountant_user),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] == 2 and body["replaced"] == 0

    r = await client.get("/api/v1/contract-templates", headers=auth_header(sales_user))
    assert r.status_code == 200
    ds = r.json()
    assert ds["can_manage"] is False
    assert {m["category"] for m in ds["items"]} == {"hop_dong", "bien_ban"}
    assert "data" not in ds["items"][0]

    hd = next(m for m in ds["items"] if m["category"] == "hop_dong")
    r = await client.get(f"/api/v1/contract-templates/{hd['id']}/download", headers=auth_header(sales_user))
    assert r.status_code == 200
    assert r.content == b"PK noi that"
    assert "filename*=UTF-8''" in r.headers["content-disposition"]


@pytest.mark.asyncio
async def test_tai_lai_cung_ten_thay_ban_moi(client, admin_user):
    h = auth_header(admin_user)
    await client.post("/api/v1/contract-templates", files=[_tep("XÁC NHẬN THANH TOÁN.doc", b"v1")], headers=h)
    r = await client.post("/api/v1/contract-templates", files=[_tep("Xac nhan thanh toan.docx", b"v2")], headers=h)
    assert r.json()["replaced"] == 1
    ds = (await client.get("/api/v1/contract-templates", headers=h)).json()["items"]
    assert len(ds) == 1 and ds[0]["version"] == 2
    r = await client.get(f"/api/v1/contract-templates/{ds[0]['id']}/download", headers=h)
    assert r.content == b"v2"


@pytest.mark.asyncio
async def test_sale_khong_duoc_tai_len_hay_sua(client, sales_user, admin_user):
    r = await client.post("/api/v1/contract-templates", files=[_tep("a.docx")], headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.post("/api/v1/contract-templates", files=[_tep("a.docx")], headers=auth_header(admin_user))
    mid = r.json()["items"][0]["id"]
    r = await client.patch(f"/api/v1/contract-templates/{mid}", json={"name": "x"}, headers=auth_header(sales_user))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_sai_dinh_dang_bi_tu_choi_khong_ghi_gi(client, admin_user):
    h = auth_header(admin_user)
    r = await client.post(
        "/api/v1/contract-templates",
        files=[_tep("tot.docx"), _tep("virus.exe", b"MZ", "application/octet-stream")],
        headers=h,
    )
    assert r.status_code == 400
    assert (await client.get("/api/v1/contract-templates", headers=h)).json()["items"] == []


@pytest.mark.asyncio
async def test_an_mau_thi_nguoi_xem_khong_thay(client, admin_user, sales_user):
    h = auth_header(admin_user)
    mid = (await client.post("/api/v1/contract-templates", files=[_tep("cu.docx")], headers=h)).json()["items"][0]["id"]
    r = await client.patch(f"/api/v1/contract-templates/{mid}", json={"is_active": False, "category": "khac"}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False

    assert (await client.get("/api/v1/contract-templates", headers=auth_header(sales_user))).json()["items"] == []
    r = await client.get(f"/api/v1/contract-templates/{mid}/download", headers=auth_header(sales_user))
    assert r.status_code == 404
    an = (await client.get("/api/v1/contract-templates?include_hidden=1", headers=h)).json()["items"]
    assert len(an) == 1


@pytest.mark.asyncio
async def test_khong_co_quyen_xem_hop_dong_thi_403(client, db_session, sales_user):
    sales_user.custom_permissions = json.dumps({"canViewContracts": False})
    await db_session.commit()
    r = await client.get("/api/v1/contract-templates", headers=auth_header(sales_user))
    assert r.status_code == 403
