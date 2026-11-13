"""AI chỉ nhận dữ liệu cần thiết (11/11/2026): không email nhân viên, không cả công ty."""

from types import SimpleNamespace

from app.agents.task_coordinator import _build_project_context, _ma_nhan_vien


def _u(dept, email):
    return SimpleNamespace(id=email, full_name="Ten", email=email, role="x", department=dept)


def test_ngu_canh_giao_viec_khong_co_email_va_chi_phong_lam_du_an():
    ma_nv = _ma_nhan_vien([_u("DESIGN", "tk@jama.vn"), _u("ACCT", "kt@jama.vn"), _u("OPS", "gs@jama.vn")])
    assert set(ma_nv) == {"NV1", "NV2"}
    du_an = SimpleNamespace(code="JMH-1", name="A", client_name="B", project_type="c", design_value=1,
                            construction_value=1, total_value=2, start_date=None, target_end_date=None)
    ngu_canh = _build_project_context(du_an, ma_nv)
    assert "@" not in ngu_canh and "kt@" not in ngu_canh
    assert "NV1 | DESIGN" in ngu_canh
