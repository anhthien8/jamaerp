"""Seed database with demo data — users, teams, leads, projects, activities, transactions."""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.project import Project, Task
from app.models.payroll import Transaction, Commission, Payroll


def _id():
    return str(uuid.uuid4())


def _dt(days_ago: int = 0, hours_ago: int = 0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)


async def seed_database(db: AsyncSession):
    """Seed if no users exist."""
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return  # Already seeded

    print("[SEED] Seeding database...")

    # ── Teams ──
    team_exec_id = _id()
    team_sales1_id = _id()
    team_sales2_id = _id()
    team_design_id = _id()
    team_purchasing_id = _id()

    teams = [
        Team(id=team_exec_id, name="Ban Giám Đốc", code="BGD", department="EXEC"),
        Team(id=team_sales1_id, name="Đội Văn Toàn", code="JMH-VT", department="SALES"),
        Team(id=team_sales2_id, name="Đội Thái Phượng", code="JMH-TP", department="SALES"),
        Team(id=team_design_id, name="Phòng Thiết Kế", code="DESIGN-1", department="DESIGN"),
        Team(id=team_purchasing_id, name="Phòng Thu mua", code="JMH-TM", department="PURCHASING"),
    ]
    for t in teams:
        db.add(t)
    await db.flush()

    # ── Users (5 roles) ──
    admin_id = _id()
    leader_id = _id()
    sales_id = _id()
    accountant_id = _id()
    executive_id = _id()
    purchasing_id = _id()

    users = [
        User(
            id=admin_id, full_name="Nguyễn Văn Admin", email="admin@jamahome.vn",
            phone="0901234567", password_hash=hash_password("admin123"),
            role="admin", department="EXEC", team_id=team_exec_id,
        ),
        User(
            id=leader_id, full_name="Lê Văn Leader", email="leader@jamahome.vn",
            phone="0909876543", password_hash=hash_password("leader123"),
            role="leader", department="SALES", team_id=team_sales1_id,
        ),
        User(
            id=sales_id, full_name="Trần Thị Sales", email="sales@jamahome.vn",
            phone="0907654321", password_hash=hash_password("sales123"),
            role="data_entry", department="SALES", team_id=team_sales1_id,
        ),
        User(
            id=accountant_id, full_name="Phạm Thị Kế Toán", email="accountant@jamahome.vn",
            phone="0905555666", password_hash=hash_password("account123"),
            role="accountant", department="ACCT",
        ),
        User(
            id=executive_id, full_name="Đỗ Minh Tuấn", email="ceo@jamahome.vn",
            phone="0901111222", password_hash=hash_password("ceo123"),
            role="executive", department="EXEC",
        ),
        User(
            id=purchasing_id, full_name="Trần Văn Thu Mua", email="purchasing@jamahome.vn",
            phone="0902222333", password_hash=hash_password("purchase123"),
            role="purchasing", department="PURCHASING", team_id=team_purchasing_id,
        ),
    ]
    for u in users:
        db.add(u)
    await db.flush()

    # ── Leads (9 real leads from Lark CRM) ──
    lead_ids = {}
    lead_names = ["bong", "dung1", "duc_anh", "cuc1", "kim_cuc", "dung2", "trang", "cuc2", "dung3"]
    for n in lead_names:
        lead_ids[n] = _id()

    leads = [
        Lead(
            id=lead_ids["bong"], name="Bong (To Ngoc Bong)", phone="0901111222",
            address="Long An",
            needs="Thiet ke noi that nha pho, phong cach cao cap",
            source="facebook", property_type="townhouse", area_sqm=349, estimated_budget=4188000000,
            stage="interested", priority="urgent",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=92,
            property_class="luxury", price_per_sqm=12000000, region="Long An",
            segment="Biet thu", plan_type="online", tags='["Deal","VIP"]',
            deal_value=4188000000,
            created_at=_dt(20), last_contacted_at=_dt(1),
        ),
        Lead(
            id=lead_ids["dung1"], name="Dung", phone="0902222333",
            address="Long An",
            needs="Thiet ke noi that nha pho, phan khuc hang sang",
            source="facebook", property_type="townhouse", area_sqm=300, estimated_budget=3000000000,
            stage="interested", priority="high",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=85,
            property_class="luxury", price_per_sqm=10000000, region="Long An",
            segment="Nha o", plan_type="none", tags='["Deal"]',
            deal_value=3000000000,
            created_at=_dt(16), last_contacted_at=_dt(2),
        ),
        Lead(
            id=lead_ids["duc_anh"], name="Duc Anh (Pham Duc Anh)", phone="0903333444",
            address="Khanh Hoa",
            needs="Thiet ke noi that nha pho, ngan sach 1.5 ty",
            source="google_form", property_type="townhouse", area_sqm=150, estimated_budget=1500000000,
            stage="interested", priority="high",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=78,
            property_class="mid_range", price_per_sqm=10000000, region="Khanh Hoa",
            segment="Nha pho", plan_type="online", tags='["Deal"]',
            deal_value=1500000000,
            created_at=_dt(14), last_contacted_at=_dt(3),
        ),
        Lead(
            id=lead_ids["cuc1"], name="Cuc (Nguyen Thi Cuc)", phone="0904444555",
            address="Long An",
            needs="Thiet ke noi that nha pho 117m2",
            source="google_form", property_type="townhouse", area_sqm=117, estimated_budget=1170000000,
            stage="interested", priority="medium",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=72,
            property_class="mid_range", price_per_sqm=10000000, region="Long An",
            segment="Nha o", plan_type="online", tags='["Deal"]',
            deal_value=1170000000,
            created_at=_dt(11), last_contacted_at=_dt(4),
        ),
        Lead(
            id=lead_ids["kim_cuc"], name="Kim Cuc (Le Thi Kim Cuc)", phone="0905555666",
            address="Q.9, TP.HCM",
            needs="Thiet ke noi that nha pho, phong cach cao cap",
            source="facebook", property_type="townhouse", area_sqm=145, estimated_budget=2030000000,
            stage="interested", priority="high",
            assigned_to=leader_id, team_id=team_sales1_id,
            ai_score=82,
            property_class="luxury", price_per_sqm=14000000, region="Q.9",
            segment="Nha o", plan_type="offline", tags='["Deal","Uu tien"]',
            deal_value=2030000000,
            created_at=_dt(12), last_contacted_at=_dt(2),
        ),
        Lead(
            id=lead_ids["dung2"], name="Dung (2)", phone="0906666777",
            address="Long An",
            needs="Thiet ke noi that nha pho 140m2, hang sang",
            source="google_form", property_type="townhouse", area_sqm=140, estimated_budget=1540000000,
            stage="interested", priority="medium",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=75,
            property_class="luxury", price_per_sqm=11000000, region="Long An",
            segment="Nha o", plan_type="online", tags='["Deal"]',
            deal_value=1540000000,
            created_at=_dt(8), last_contacted_at=_dt(3),
        ),
        Lead(
            id=lead_ids["trang"], name="Trang", phone="0907777888",
            address="Long An",
            needs="Thiet ke + thi cong noi that nha pho 200m2",
            source="facebook", property_type="townhouse", area_sqm=200, estimated_budget=3400000000,
            stage="interested", priority="high",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=88,
            property_class="luxury", price_per_sqm=17000000, region="Long An",
            segment="Nha o", plan_type="survey", tags='["Deal","VIP"]',
            deal_value=3400000000,
            created_at=_dt(10), last_contacted_at=_dt(0),
        ),
        Lead(
            id=lead_ids["cuc2"], name="Cuc (2)", phone="0908888999",
            address="Long An",
            needs="Thiet ke + thi cong biet thu 500m2, phong cach luxury",
            source="facebook", property_type="villa", area_sqm=500, estimated_budget=5500000000,
            stage="survey_scheduled", priority="urgent",
            assigned_to=sales_id, team_id=team_sales1_id,
            ai_score=95,
            property_class="luxury", price_per_sqm=11000000, region="Long An",
            segment="Biet thu", plan_type="offline", tags='["Deal","VIP","Uu tien"]',
            deal_value=5500000000,
            created_at=_dt(16), last_contacted_at=_dt(0),
        ),
        Lead(
            id=lead_ids["dung3"], name="Dung (3)", phone="0909999000",
            address="TP.HCM",
            needs="Thiet ke noi that nha pho 120m2",
            source="referral", property_type="townhouse", area_sqm=120, estimated_budget=840000000,
            stage="survey_scheduled", priority="medium",
            assigned_to=leader_id, team_id=team_sales1_id,
            ai_score=70,
            property_class="luxury", price_per_sqm=7000000, region="TP.HCM",
            segment="Nha o", plan_type="offline", tags='["Deal"]',
            deal_value=840000000,
            created_at=_dt(9), last_contacted_at=_dt(2),
        ),
    ]
    for l in leads:
        db.add(l)
    await db.flush()

    # ── Activities ──
    activities_data = [
        (lead_ids["bong"], sales_id, "note", "KH rat quan tam phong cach cao cap. Ngan sach linh hoat.", 18),
        (lead_ids["bong"], sales_id, "call", "Tu van goi thiet ke, KH dong y hen khao sat.", 14),
        (lead_ids["bong"], sales_id, "meeting", "Khao sat nha pho 349m2 Long An. Do dac hoan tat.", 8),
        (lead_ids["dung1"], sales_id, "note", "KH VIP, nha pho 300m2 Long An. Hang sang.", 14),
        (lead_ids["dung1"], sales_id, "call", "Trao doi phong cach cao cap, gui portfolio.", 10),
        (lead_ids["duc_anh"], sales_id, "call", "Tu van nha pho 150m2, ngan sach 1.5 ty.", 12),
        (lead_ids["duc_anh"], sales_id, "note", "KH quan tam, dang cho lich khao sat.", 6),
        (lead_ids["cuc1"], sales_id, "note", "Nha pho 117m2 Long An. Ngan sach 1.17 ty.", 10),
        (lead_ids["kim_cuc"], leader_id, "call", "Nha pho 145m2 Q.9. Phong cach cao cap.", 10),
        (lead_ids["kim_cuc"], leader_id, "note", "KH quan tam, can tu van offline.", 5),
        (lead_ids["trang"], sales_id, "meeting", "Khao sat nha pho 200m2 Long An.", 8),
        (lead_ids["trang"], sales_id, "call", "Dang khao sat online, can hen lich onsite.", 2),
        (lead_ids["cuc2"], sales_id, "note", "VIP! Biet thu 500m2 Long An. Deal lon nhat.", 14),
        (lead_ids["cuc2"], sales_id, "meeting", "Khao sat biet thu, chu bi phuong an thiet ke.", 5),
        (lead_ids["dung3"], leader_id, "call", "Nha pho 120m2 TP.HCM. Dang tu van.", 7),
    ]
    for lead_id, user_id, atype, content, days in activities_data:
        db.add(Activity(
            id=_id(), lead_id=lead_id, user_id=user_id,
            type=atype, content=content, created_at=_dt(days),
        ))
    await db.flush()

    # ── Projects ──
    proj_ids = {"p1": _id(), "p2": _id(), "p3": _id(), "p4": _id(), "p5": _id()}

    projects = [
        Project(
            id=proj_ids["p1"], code="PRJ-2026-001", name="Nhà phố Q7 - Chị Mai",
            lead_id=lead_ids["bong"], client_name="Chị Mai", client_phone="0901234567",
            address="123 Nguyễn Văn Linh, Q7", project_type="design_build",
            design_value=45000000, construction_value=455000000, total_value=500000000,
            spent=375000000, progress=75, status="active", stage="construction",
            pm_id=leader_id, designer_id=admin_id, sales_id=sales_id,
            start_date=_dt(60), target_end_date=_dt(-30),
        ),
        Project(
            id=proj_ids["p2"], code="PRJ-2026-002", name="Biệt thự Bình Chánh - Anh Tuấn",
            lead_id=lead_ids["dung1"], client_name="Anh Tuấn", client_phone="0908765432",
            address="Biệt thự Vinhomes, Bình Chánh", project_type="design_build",
            design_value=120000000, construction_value=2380000000, total_value=2500000000,
            spent=750000000, progress=30, status="active", stage="quotation",
            pm_id=leader_id, sales_id=sales_id,
            start_date=_dt(30), target_end_date=_dt(-90),
        ),
        Project(
            id=proj_ids["p3"], code="PRJ-2026-003", name="Căn hộ Sunrise - Chị Hương",
            lead_id=lead_ids["duc_anh"], client_name="Chị Hương", client_phone="0912345678",
            address="Căn hộ Sunrise City, Q7", project_type="design_build",
            design_value=25000000, construction_value=155000000, total_value=180000000,
            spent=162000000, progress=90, status="active", stage="acceptance",
            pm_id=leader_id, sales_id=sales_id,
            start_date=_dt(90), target_end_date=_dt(-5),
        ),
        Project(
            id=proj_ids["p4"], code="PRJ-2026-004", name="Shophouse Q2 - Anh Minh",
            lead_id=lead_ids["kim_cuc"], client_name="Anh Minh", client_phone="0987654321",
            address="Shophouse Q2", project_type="design_only",
            design_value=80000000, total_value=80000000,
            spent=12000000, progress=15, status="paused", stage="design",
            pm_id=leader_id, sales_id=leader_id,
            start_date=_dt(15),
        ),
        Project(
            id=proj_ids["p5"], code="PRJ-2026-005", name="Nhà phố Gò Vấp - Chị Lan",
            lead_id=lead_ids["trang"], client_name="Chị Lan", client_phone="0976543210",
            address="Nhà phố Gò Vấp", project_type="construction_only",
            construction_value=680000000, total_value=680000000,
            spent=374000000, progress=55, status="active", stage="procurement",
            sales_id=sales_id,
            start_date=_dt(45), target_end_date=_dt(-15),
        ),
    ]
    for p in projects:
        db.add(p)
    await db.flush()

    # ── Tasks ──
    task_data = [
        (proj_ids["p1"], "Thiết kế concept", "completed", "design", 1),
        (proj_ids["p1"], "Bản vẽ kỹ thuật", "completed", "design", 2),
        (proj_ids["p1"], "Thi công phần thô", "completed", "construction", 3),
        (proj_ids["p1"], "Lắp đặt nội thất", "in_progress", "construction", 4),
        (proj_ids["p1"], "Hoàn thiện & bàn giao", "pending", "acceptance", 5),
        (proj_ids["p2"], "Khảo sát hiện trạng", "completed", "design", 1),
        (proj_ids["p2"], "Thiết kế concept Indochine", "completed", "design", 2),
        (proj_ids["p2"], "Bản vẽ thi công", "in_progress", "design", 3),
        (proj_ids["p2"], "Thi công kết cấu", "pending", "construction", 4),
        (proj_ids["p2"], "Hoàn thiện nội thất", "pending", "construction", 5),
    ]
    for pid, title, status, tstage, order in task_data:
        db.add(Task(id=_id(), project_id=pid, title=title, status=status, stage=tstage, order=order))
    await db.flush()

    # ── Transactions ──
    tx_data = [
        ("TX-001", "income", "design_contract", "HĐ Thiết kế Chị Mai", 45000000, proj_ids["p1"], 40),
        ("TX-002", "income", "construction_contract", "HĐ Thi công Chị Mai - đợt 1", 200000000, proj_ids["p1"], 35),
        ("TX-003", "expense", "material", "Vật liệu thi công Q7 - đợt 1", 85000000, proj_ids["p1"], 25),
        ("TX-004", "expense", "labor", "Nhân công thi công Q7 - T5", 45000000, proj_ids["p1"], 20),
        ("TX-005", "income", "design_contract", "HĐ Thiết kế Anh Tuấn", 120000000, proj_ids["p2"], 28),
        ("TX-006", "income", "construction_contract", "HĐ Thi công Anh Tuấn - đợt 1", 630000000, proj_ids["p2"], 22),
        ("TX-007", "expense", "material", "Vật liệu biệt thự Bình Chánh", 350000000, proj_ids["p2"], 15),
        ("TX-008", "income", "construction_contract", "HĐ Thi công Chị Hương", 155000000, proj_ids["p3"], 85),
        ("TX-009", "expense", "material", "Nội thất căn hộ Sunrise", 95000000, proj_ids["p3"], 60),
        ("TX-010", "income", "construction_contract", "HĐ Thi công Chị Lan - đợt 1", 340000000, proj_ids["p5"], 40),
        ("TX-011", "expense", "salary", "Lương tháng 5/2026", 180000000, None, 30),
        ("TX-012", "expense", "commission", "Hoa hồng T5 - Sales team", 28500000, None, 28),
    ]
    for code, ttype, cat, desc, amount, pid, days in tx_data:
        db.add(Transaction(
            id=_id(), code=code, type=ttype, category=cat,
            description=desc, amount=amount, project_id=pid,
            created_by=admin_id, date=_dt(days),
        ))
    await db.flush()

    # ── Commissions ──
    comm_data = [
        (sales_id, proj_ids["p1"], "design_commission", 0.03, 45000000, "signing"),
        (sales_id, proj_ids["p1"], "construction_commission", 0.02, 455000000, "signing"),
        (leader_id, proj_ids["p1"], "leader_override", 0.005, 500000000, "signing"),
        (sales_id, proj_ids["p2"], "design_commission", 0.03, 120000000, "signing"),
    ]
    for uid, pid, ctype, rate, base, milestone in comm_data:
        db.add(Commission(
            id=_id(), user_id=uid, project_id=pid, type=ctype,
            rate=rate, base_amount=base, commission_amount=base * rate,
            milestone=milestone, milestone_pct=0.5, status="approved",
            period="2026-06",
        ))
    await db.flush()

    # ── Payroll ──
    payroll_data = [
        (admin_id, 25000000, 0, 0, 0),
        (leader_id, 15000000, 1250000, 2000000, 1500000),
        (sales_id, 8000000, 6250000, 1000000, 1200000),
    ]
    for uid, base, comm, bonus, ded in payroll_data:
        db.add(Payroll(
            id=_id(), user_id=uid, period="2026-06",
            base_salary=base, commission_total=comm, bonus=bonus,
            deductions=ded, net_salary=base + comm + bonus - ded,
            status="approved",
        ))

    await db.flush()

    # ── Customers (auto-convert from leads that signed) ──
    from app.models.customer import Customer
    from app.models.inventory import Material, MaterialUsage

    cust_ids = {"mai": _id(), "tuan": _id(), "huong": _id(), "lan": _id(), "minh": _id()}
    customers = [
        Customer(
            id=cust_ids["mai"], name="Chị Mai", phone="0901234567",
            email="mai.nguyen@gmail.com", address="123 Nguyễn Văn Linh, Q7, TP.HCM",
            type="individual", lead_id=lead_ids["bong"],
        ),
        Customer(
            id=cust_ids["tuan"], name="Anh Tuấn", phone="0908765432",
            email="tuan.pham@yahoo.com", address="Biệt thự Vinhomes Central Park, Bình Chánh",
            type="individual", lead_id=lead_ids["dung1"],
        ),
        Customer(
            id=cust_ids["huong"], name="Chị Hương", phone="0912345678",
            email="huong.le@outlook.com", address="Căn hộ Sunrise City, Q7",
            type="individual", lead_id=lead_ids["duc_anh"],
        ),
        Customer(
            id=cust_ids["lan"], name="Chị Lan", phone="0976543210",
            address="Nhà phố Gò Vấp",
            type="individual", lead_id=lead_ids["trang"],
        ),
        Customer(
            id=cust_ids["minh"], name="Công ty TNHH Minh Design", phone="0987654321",
            email="minh@minhdesign.vn", address="Shophouse Q2, TP.HCM",
            type="company", company_name="Công ty TNHH Minh Design",
            tax_code="0316789012", lead_id=lead_ids["kim_cuc"],
        ),
    ]
    for c in customers:
        db.add(c)
    await db.flush()

    # ── Contracts ──
    from app.models.contract import Contract
    contract_ids = {"c1": _id(), "c2": _id(), "c3": _id()}
    contracts = [
        Contract(
            id=contract_ids["c1"], code="HD-2026-001",
            project_id=proj_ids["p1"], title="HĐ Thiết kế + Thi công Nhà phố Q7 - Chị Mai",
            status="signed", total_value=500000000,
            signed_date=_dt(55).date(), working_days=120, start_date=_dt(60).date(),
            payment_terms={"installments": [
                {"name": "Đợt 1 (Đặt cọc)", "percentage": 25, "milestone": "signing", "status": "paid", "amount": 125000000, "paid_date": str(_dt(55).date())},
                {"name": "Đợt 2 (Nghiệm thu thô)", "percentage": 25, "milestone": "rough_complete", "status": "paid", "amount": 125000000, "paid_date": str(_dt(20).date())},
                {"name": "Đợt 3 (Nội thất)", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
                {"name": "Đợt 4 (Bàn giao)", "percentage": 25, "milestone": "handover", "status": "pending"},
            ]},
        ),
        Contract(
            id=contract_ids["c2"], code="HD-2026-002",
            project_id=proj_ids["p2"], title="HĐ Thiết kế + Thi công Biệt thự Bình Chánh - Anh Tuấn",
            status="signed", total_value=2500000000,
            signed_date=_dt(28).date(), working_days=180, start_date=_dt(30).date(),
            payment_terms={"installments": [
                {"name": "Đợt 1 (Đặt cọc)", "percentage": 25, "milestone": "signing", "status": "paid", "amount": 625000000, "paid_date": str(_dt(28).date())},
                {"name": "Đợt 2 (Nghiệm thu thô)", "percentage": 25, "milestone": "rough_complete", "status": "pending"},
                {"name": "Đợt 3 (Nội thất)", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
                {"name": "Đợt 4 (Bàn giao)", "percentage": 25, "milestone": "handover", "status": "pending"},
            ]},
        ),
        Contract(
            id=contract_ids["c3"], code="HD-2026-003",
            project_id=proj_ids["p5"], title="HĐ Thi công Nhà phố Gò Vấp - Chị Lan",
            status="signed", total_value=680000000,
            signed_date=_dt(40).date(), working_days=90, start_date=_dt(45).date(),
            payment_terms={"installments": [
                {"name": "Đợt 1 (Đặt cọc)", "percentage": 30, "milestone": "signing", "status": "paid", "amount": 204000000, "paid_date": str(_dt(40).date())},
                {"name": "Đợt 2 (Nghiệm thu thô)", "percentage": 30, "milestone": "rough_complete", "status": "paid", "amount": 204000000, "paid_date": str(_dt(15).date())},
                {"name": "Đợt 3 (Bàn giao)", "percentage": 40, "milestone": "handover", "status": "pending"},
            ]},
        ),
    ]
    for c in contracts:
        db.add(c)
    await db.flush()

    # ── Quotations ──
    from app.models.quotation import Quotation
    quotations = [
        Quotation(
            id=_id(), code="BG-2026-001", type="design",
            project_id=proj_ids["p1"], lead_id=lead_ids["bong"],
            title="Báo giá thiết kế nội thất nhà phố Q7 - Chị Mai",
            status="approved", total_amount=45000000, tax_amount=4500000,
            created_by=sales_id, revision=2,
            items={"line_items": [
                {"name": "Thiết kế phòng khách", "category": "phong_khach", "unit": "gói", "quantity": 1, "unit_price": 15000000, "total": 15000000},
                {"name": "Thiết kế phòng ngủ master", "category": "phong_ngu", "unit": "gói", "quantity": 1, "unit_price": 12000000, "total": 12000000},
                {"name": "Thiết kế bếp + phòng ăn", "category": "bep", "unit": "gói", "quantity": 1, "unit_price": 10000000, "total": 10000000},
                {"name": "Thiết kế phòng tắm (x2)", "category": "phong_tam", "unit": "gói", "quantity": 2, "unit_price": 4000000, "total": 8000000},
            ]},
        ),
        Quotation(
            id=_id(), code="BG-2026-002", type="construction",
            project_id=proj_ids["p1"], lead_id=lead_ids["bong"],
            title="Báo giá thi công nội thất nhà phố Q7 - Chị Mai",
            status="approved", total_amount=455000000, tax_amount=45500000,
            created_by=sales_id,
            items={"line_items": [
                {"name": "Thi công trần thạch cao", "category": "general", "unit": "m2", "quantity": 120, "unit_price": 450000, "total": 54000000},
                {"name": "Hệ tủ bếp cao cấp", "category": "bep", "unit": "bộ", "quantity": 1, "unit_price": 85000000, "total": 85000000},
                {"name": "Sàn gỗ công nghiệp", "category": "general", "unit": "m2", "quantity": 150, "unit_price": 650000, "total": 97500000},
                {"name": "Nội thất phòng khách", "category": "phong_khach", "unit": "bộ", "quantity": 1, "unit_price": 120000000, "total": 120000000},
                {"name": "Nội thất 2 phòng ngủ", "category": "phong_ngu", "unit": "bộ", "quantity": 2, "unit_price": 49250000, "total": 98500000},
            ]},
        ),
        Quotation(
            id=_id(), code="BG-2026-003", type="design",
            project_id=proj_ids["p2"], lead_id=lead_ids["dung1"],
            title="Báo giá thiết kế biệt thự Indochine - Anh Tuấn",
            status="approved", total_amount=120000000, tax_amount=12000000,
            created_by=leader_id,
            items={"line_items": [
                {"name": "Thiết kế kiến trúc mặt ngoài", "category": "custom", "unit": "gói", "quantity": 1, "unit_price": 35000000, "total": 35000000},
                {"name": "Thiết kế nội thất tầng 1", "category": "phong_khach", "unit": "gói", "quantity": 1, "unit_price": 45000000, "total": 45000000},
                {"name": "Thiết kế nội thất tầng 2", "category": "phong_ngu", "unit": "gói", "quantity": 1, "unit_price": 30000000, "total": 30000000},
                {"name": "Thiết kế sân vườn", "category": "custom", "unit": "gói", "quantity": 1, "unit_price": 10000000, "total": 10000000},
            ]},
        ),
        Quotation(
            id=_id(), code="BG-2026-004", type="construction",
            project_id=proj_ids["p5"], lead_id=lead_ids["trang"],
            title="Báo giá thi công nhà phố Gò Vấp - Chị Lan",
            status="sent", total_amount=680000000, tax_amount=68000000,
            created_by=sales_id,
            items={"line_items": [
                {"name": "Thi công phần thô", "category": "general", "unit": "gói", "quantity": 1, "unit_price": 280000000, "total": 280000000},
                {"name": "Nội thất toàn bộ", "category": "general", "unit": "gói", "quantity": 1, "unit_price": 320000000, "total": 320000000},
                {"name": "He thong dien + nuoc", "category": "custom", "unit": "goi", "quantity": 1, "unit_price": 80000000, "total": 80000000},
            ]},
        ),
    ]
    for q in quotations:
        db.add(q)
    await db.flush()

    # ── Materials (Inventory) ──
    mat_ids = {f"m{i}": _id() for i in range(1, 11)}
    materials = [
        Material(id=mat_ids["m1"], code="VT-001", name="Go cong nghiep MDF loi xanh", category="wood", unit="tam", unit_price=350000, quantity_in_stock=120, min_stock=20, supplier="An Cuong"),
        Material(id=mat_ids["m2"], code="VT-002", name="San go Egger 12mm", category="wood", unit="m2", unit_price=650000, quantity_in_stock=85, min_stock=50, supplier="Egger Viet Nam"),
        Material(id=mat_ids["m3"], code="VT-003", name="Da granite den An Do", category="stone", unit="m2", unit_price=1200000, quantity_in_stock=45, min_stock=15, supplier="Da Hoang Gia"),
        Material(id=mat_ids["m4"], code="VT-004", name="Son Dulux noi that cao cap", category="paint", unit="thung", unit_price=890000, quantity_in_stock=30, min_stock=10, supplier="AkzoNobel"),
        Material(id=mat_ids["m5"], code="VT-005", name="Inox 304 ong vuong 40x40", category="metal", unit="cay", unit_price=285000, quantity_in_stock=60, min_stock=20, supplier="Inox Dai Duong"),
        Material(id=mat_ids["m6"], code="VT-006", name="Kinh cuong luc 10mm", category="glass", unit="m2", unit_price=480000, quantity_in_stock=35, min_stock=10, supplier="Kinh Hung Thinh"),
        Material(id=mat_ids["m7"], code="VT-007", name="Den LED panel 600x600", category="electrical", unit="cai", unit_price=320000, quantity_in_stock=8, min_stock=15, supplier="Rang Dong"),
        Material(id=mat_ids["m8"], code="VT-008", name="Vai sofa nhap Bi", category="fabric", unit="m", unit_price=950000, quantity_in_stock=40, min_stock=10, supplier="Vai Hoang Ha"),
        Material(id=mat_ids["m9"], code="VT-009", name="Ong PPR nong 25mm", category="plumbing", unit="cay", unit_price=125000, quantity_in_stock=100, min_stock=30, supplier="Vesbo"),
        Material(id=mat_ids["m10"], code="VT-010", name="Ban le giam chan Blum", category="furniture", unit="cai", unit_price=85000, quantity_in_stock=200, min_stock=50, supplier="Blum Viet Nam"),
    ]
    for m in materials:
        db.add(m)
    await db.flush()

    # ── Material Usage ──
    usages = [
        MaterialUsage(id=_id(), material_id=mat_ids["m1"], project_id=proj_ids["p1"], quantity=25, unit_price_at_use=350000, total_cost=8750000, date=_dt(30), created_by=admin_id),
        MaterialUsage(id=_id(), material_id=mat_ids["m2"], project_id=proj_ids["p1"], quantity=45, unit_price_at_use=650000, total_cost=29250000, date=_dt(25), created_by=admin_id),
        MaterialUsage(id=_id(), material_id=mat_ids["m4"], project_id=proj_ids["p1"], quantity=8, unit_price_at_use=890000, total_cost=7120000, date=_dt(20), created_by=admin_id),
        MaterialUsage(id=_id(), material_id=mat_ids["m3"], project_id=proj_ids["p2"], quantity=15, unit_price_at_use=1200000, total_cost=18000000, date=_dt(15), created_by=leader_id),
        MaterialUsage(id=_id(), material_id=mat_ids["m5"], project_id=proj_ids["p2"], quantity=20, unit_price_at_use=285000, total_cost=5700000, date=_dt(10), created_by=leader_id),
        MaterialUsage(id=_id(), material_id=mat_ids["m10"], project_id=proj_ids["p3"], quantity=24, unit_price_at_use=85000, total_cost=2040000, date=_dt(8), created_by=sales_id),
    ]
    for u in usages:
        db.add(u)

    await db.flush()
    print("[OK] Seed complete: 5 users, 4 teams, 9 leads, 5 projects, 5 customers, 3 contracts, 4 quotations, 10 materials")
