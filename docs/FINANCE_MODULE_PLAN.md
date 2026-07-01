# JAMA CRM — Module Finance Plan

> Kế hoạch triển khai Module Finance
> Dựa trên tài liệu BA từ C-level

---

## 📌 Tổng quan

Module Finance quản lý toàn bộ tài chính công ty: lương thưởng, BHXH, hoa hồng, chi phí định phí/biến phí, và P&L.

---

## 1. Database Models

### SalaryGrade (Bậc lương)
```sql
CREATE TABLE salary_grades (
    id UUID PRIMARY KEY,
    grade_name VARCHAR(100) NOT NULL,      -- "Bậc 1", "Bậc 2", ...
    base_salary DECIMAL(15,2) NOT NULL,    -- Lương gross cơ bản
    bhxh_rate DECIMAL(5,2) DEFAULT 10.5,   -- Tỷ lệ BHXH NLĐ (%)
    bhxh_company_rate DECIMAL(5,2) DEFAULT 21.5,  -- Tỷ lệ BHXH NSDLĐ
    bhyt_rate DECIMAL(5,2) DEFAULT 1.5,    -- BHYT
    bhtn_rate DECIMAL(5,2) DEFAULT 1.0,    -- BHTN
    effective_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### EmploymentContract (Hợp đồng lao động)
```sql
CREATE TABLE employment_contracts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    contract_no VARCHAR(50) UNIQUE,        -- "HĐLĐ-2026-001"
    contract_type VARCHAR(20),             -- fulltime, parttime, ctv
    position VARCHAR(100),                 -- Chức danh
    salary_grade_id UUID REFERENCES salary_grades(id),
    gross_salary DECIMAL(15,2),
    start_date DATE NOT NULL,
    end_date DATE,                         -- NULL = không xác định
    status VARCHAR(20) DEFAULT 'active',  -- active, expired, terminated
    created_at TIMESTAMP DEFAULT NOW()
);
```

### MonthlyPayroll (Bảng lương tháng)
```sql
CREATE TABLE monthly_payrolls (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    period VARCHAR(7) NOT NULL,            -- "2026-06"
    gross_salary DECIMAL(15,2),
    bhxh_employee DECIMAL(15,2),           -- BHXH NLĐ (10.5%)
    bhxh_company DECIMAL(15,2),            -- BHXH NSDLĐ (21.5%)
    bhyt DECIMAL(15,2),                    -- BHYT (1.5%)
    bhtn DECIMAL(15,2),                    -- BHTN (1%)
    pit DECIMAL(15,2),                     -- Thuế TNCN
    kpi_bonus DECIMAL(15,2) DEFAULT 0,     -- Thưởng KPI
    other_bonus DECIMAL(15,2) DEFAULT 0,   -- Thưởng khác
    deductions DECIMAL(15,2) DEFAULT 0,    -- Khấu trừ khác
    net_salary DECIMAL(15,2),
    status VARCHAR(20) DEFAULT 'draft',    -- draft, approved, paid
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### FixedCost (Chi phí Định phí)
```sql
CREATE TABLE fixed_costs (
    id UUID PRIMARY KEY,
    category VARCHAR(100) NOT NULL,        -- "Tiền mặt bằng", "Điện nước", ...
    amount DECIMAL(15,2) NOT NULL,
    month VARCHAR(7) NOT NULL,             -- "2026-06"
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### VariableCost (Chi phí Biến phí)
```sql
CREATE TABLE variable_costs (
    id UUID PRIMARY KEY,
    category VARCHAR(100) NOT NULL,        -- "Đi lại dự án", "Vụn thi công", ...
    amount DECIMAL(15,2) NOT NULL,
    project_id UUID REFERENCES projects(id),  -- NULL = chi phí chung
    month VARCHAR(7) NOT NULL,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### CommissionStructure (Cơ cấu hoa hồng)
```sql
CREATE TABLE commission_structures (
    id UUID PRIMARY KEY,
    department VARCHAR(50) NOT NULL,       -- "sales", "design", "pm"
    commission_type VARCHAR(50) NOT NULL,  -- "design_contract", "construction_contract", "leader_override"
    rate DECIMAL(5,4) NOT NULL,            -- 0.03 = 3%
    effective_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 2. Salary Calculation Formula

```
Gross Salary (nhập)
├── BHXH NLĐ = Gross × 10.5%
├── BHYT NLĐ = Gross × 1.5%
├── BHTN NLĐ = Gross × 1.0%
├── Tổng khấu trừ BHXH = 13%
├── Thuế TNCN = (Gross - 11,000,000 - BHXH) × tax_rate
├── Khấu trừ khác (nếu có)
└── NET = Gross - BHXH - Thuế - Khấu trừ khác

BHXH NSDLĐ = Gross × 21.5% (công ty đóng thêm)
```

### Tax Brackets (Thuế TNCN)
| Income Range (VNĐ/month) | Tax Rate |
|---------------------------|----------|
| Up to 5,000,000 | 5% |
| 5,000,001 - 10,000,000 | 10% |
| 10,000,001 - 18,000,000 | 15% |
| 18,000,001 - 32,000,000 | 20% |
| 32,000,001 - 52,000,000 | 25% |
| 52,000,001 - 80,000,000 | 30% |
| Over 80,000,000 | 35% |

---

## 3. Commission Structure (theo docs)

| Department | Rate | Base | Milestone |
|------------|------|------|-----------|
| Sales | 3% | Design contract value | Signing |
| Sales | 2% | Construction contract value | Signing |
| Leader | 0.5% | Total project value | Signing |
| Designer | 1% | Design fee | Final design |
| PM | 0.5% | Project value | Handover |

---

## 4. Fixed Costs (cần nhập từ nhân sự)

| Category | Default Amount | Frequency |
|----------|---------------|-----------|
| Tiền mặt bằng | ? | Monthly |
| Điện nước | ? | Monthly |
| Internet | ? | Monthly |
| Bảo hiểm office | ? | Quarterly |
| Thuê bãi xe | ? | Monthly |

**Cần hỏi chị LA**: Liệt kê chi tiết các khoản cố định hàng tháng và số tiền.

---

## 5. UI Tabs

1. **Nhân sự** — CRUD nhân viên, HĐ lao động, Bậc lương
2. **Lương thưởng** — Tính lương tự động, KPI bonus
3. **Bảng lương** — Payslip theo tháng, phân bổ NV
4. **BHXH** — Tổng hợp BHXH/BHYT/BHTN
5. **Hoa hồng** — Cơ cấu HH, tính toán theo dự án
6. **Chi phí** — Định phí + Biến phí theo tháng
7. **Cài đặt** — Bậc lương, tỷ lệ BHXH, tham số hệ thống

---

## 6. Implementation Phases

### Phase 1 (2-3 tuần): Foundation
- [ ] Tạo models: SalaryGrade, EmploymentContract, FixedCost, VariableCost
- [ ] Seed data: Bậc lương mẫu, Chi phí định phí
- [ ] API CRUD endpoints
- [ ] Frontend tabs: Nhân sự, Chi phí

### Phase 2 (2-3 tuần): Salary Calculation
- [ ] Tính lương tự động: Gross → BHXH → BHYT → BHTN → PIT → NET
- [ ] Bảng lương theo tháng
- [ ] KPI bonus integration
- [ ] Export file chuyển khoản

### Phase 3 (2 tuần): Commission & Reporting
- [ ] Tính hoa hồng tự động theo milestone
- [ ] P&L tổng hợp
- [ ] Báo cáo tài chính theo tháng/quý

### Phase 4 (2-3 tuần): Advanced
- [ ] Auto-invoice từ contract milestone
- [ ] Bank reconciliation
- [ ] Tax report generation
- [ ] Budget vs Actual alerts

---

## 7. Câu hỏi cần xác nhận

1. **Bậc lương**: Công ty có bao nhiêu bậc? Mức lương gross cụ thể?
2. **Tỷ lệ BHXH**: Áp dụng đúng luật VN (10.5% NLĐ, 21.5% NSDLĐ)?
3. **Chi phí cố định**: Liệt kê chi tiết các khoản cố định hàng tháng?
4. **Hoa hồng**: Tỷ lệ chính xác cho từng phòng ban?
5. **KPI**: Công ty có dùng KPI để tính thưởng không?

---

*Last updated: 30/06/2026*
