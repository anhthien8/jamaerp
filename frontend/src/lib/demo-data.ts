/**
 * JAMA HOME CRM — Complete Demo Data
 * Used when backend API is unavailable (demo mode).
 */

import type {
  User, Team, Lead, Activity, Project, ProjectTask,
  Transaction, AccountingSummary, Commission, PayrollEntry,
  PipelineStats, PipelineKanban, DashboardExecutive, DashboardPersonal,
  Customer, Contract, Quotation, Material, MaterialUsage, AISuggestion,
  SalaryGrade, FixedCost, VariableCost, CommissionStructure,
} from './api';

// ─── Users ──────────────────────────────────────────────
export const DEMO_USERS: User[] = [
  { id: 'demo-admin-001', full_name: 'Hồ Minh Tuấn', email: 'admin@jamahome.vn', phone: '0901234567', role: 'admin', department: 'EXEC', team_id: 'demo-team-04', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-leader-001', full_name: 'Lê Văn Leader', email: 'leader@jamahome.vn', phone: '0909876543', role: 'leader', department: 'SALES', team_id: 'demo-team-01', is_active: true, created_at: '2026-01-10T00:00:00Z' },
  { id: 'demo-sales-001', full_name: 'Trần Thị Sales', email: 'sales@jamahome.vn', phone: '0907654321', role: 'data_entry', department: 'SALES', team_id: 'demo-team-01', is_active: true, created_at: '2026-01-15T00:00:00Z' },
  { id: 'demo-acct-001', full_name: 'Phạm Thị Kế Toán', email: 'accountant@jamahome.vn', phone: '0905555666', role: 'accountant', department: 'ACCT', is_active: true, created_at: '2026-01-20T00:00:00Z' },
  { id: 'demo-exec-001', full_name: 'Đỗ Minh Tuấn', email: 'ceo@jamahome.vn', phone: '0901111222', role: 'executive', department: 'EXEC', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-supervisor-001', full_name: 'Nguyễn Văn Giám Sát', email: 'supervisor@jamahome.vn', role: 'supervisor', department: 'OPS', is_active: true, created_at: '2026-02-01T00:00:00Z' },
];

// ─── Teams ──────────────────────────────────────────────
export const DEMO_TEAMS: Team[] = [
  { id: 'demo-team-04', name: 'Ban Giám Đốc', code: 'BGD', department: 'EXEC', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-01', name: 'Đội Văn Toàn', code: 'JMH-VT', department: 'SALES', leader_id: 'demo-leader-001', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-02', name: 'Đội Thái Phượng', code: 'JMH-TP', department: 'SALES', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-03', name: 'Phòng Thiết Kế', code: 'DESIGN-1', department: 'DESIGN', created_at: '2026-01-01T00:00:00Z' },
];

// ─── Leads (9 leads — REAL data from Lark CRM) ─────────
export const DEMO_LEADS: Lead[] = [
  {
    id: 'demo-lead-001', name: 'Bống (Tô Ngọc Bống)', phone: '0901111222',
    address: 'Long An',
    needs: 'Thiết kế nội thất nhà phố, phong cách cao cấp',
    source: 'facebook', property_type: 'townhouse', area_sqm: 349, estimated_budget: 4188000000,
    stage: 'interested', priority: 'urgent', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 92,
    property_class: 'luxury', price_per_sqm: 12000000, region: 'Long An', segment: 'Biệt thự', plan_type: 'online', tags: ['Deal', 'VIP'], deal_value: 4188000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 3,
    created_at: '2026-06-06T07:40:31Z', updated_at: '2026-06-25T09:00:00Z', last_contacted_at: '2026-06-24T10:30:00Z',
  },
  {
    id: 'demo-lead-002', name: 'Dung', phone: '0902222333',
    address: 'Long An',
    needs: 'Thiết kế nội thất nhà phố, phân khúc hạng sang',
    source: 'facebook', property_type: 'townhouse', area_sqm: 300, estimated_budget: 3000000000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 85,
    property_class: 'luxury', price_per_sqm: 10000000, region: 'Long An', segment: 'Nhà ở', plan_type: 'none', tags: ['Deal'], deal_value: 3000000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-10T07:40:31Z', updated_at: '2026-06-24T14:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
  {
    id: 'demo-lead-003', name: 'Đức Anh (Phạm Đức Anh)', phone: '0903333444',
    address: 'Khánh Hòa',
    needs: 'Thiết kế nội thất nhà phố, ngân sách 1.5 tỷ',
    source: 'google_form', property_type: 'townhouse', area_sqm: 150, estimated_budget: 1500000000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 78,
    property_class: 'mid_range', price_per_sqm: 10000000, region: 'Khánh Hòa', segment: 'Nhà phố', plan_type: 'online', tags: ['Deal'], deal_value: 1500000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-12T07:40:31Z', updated_at: '2026-06-23T11:00:00Z', last_contacted_at: '2026-06-22T09:00:00Z',
  },
  {
    id: 'demo-lead-004', name: 'Cúc (Nguyễn Thị Cúc)', phone: '0904444555',
    address: 'Long An',
    needs: 'Thiết kế nội thất nhà phố 117m²',
    source: 'google_form', property_type: 'townhouse', area_sqm: 117, estimated_budget: 1170000000,
    stage: 'interested', priority: 'medium', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 72,
    property_class: 'mid_range', price_per_sqm: 10000000, region: 'Long An', segment: 'Nhà ở', plan_type: 'online', tags: ['Deal'], deal_value: 1170000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 1,
    created_at: '2026-06-15T07:40:31Z', updated_at: '2026-06-22T16:00:00Z', last_contacted_at: '2026-06-21T08:00:00Z',
  },
  {
    id: 'demo-lead-005', name: 'Kim Cúc (Lê Thị Kim Cúc)', phone: '0905555666',
    address: 'Q.9, TP.HCM',
    needs: 'Thiết kế nội thất nhà phố, phong cách cao cấp',
    source: 'facebook', property_type: 'townhouse', area_sqm: 145, estimated_budget: 2030000000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-leader-001', team_id: 'demo-team-01',
    ai_score: 82,
    property_class: 'luxury', price_per_sqm: 14000000, region: 'Q.9', segment: 'Nhà ở', plan_type: 'offline', tags: ['Deal', 'Ưu tiên'], deal_value: 2030000000,
    assigned_user_name: 'Lê Văn Leader', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-14T07:40:31Z', updated_at: '2026-06-24T16:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
  {
    id: 'demo-lead-006', name: 'Dung (2)', phone: '0906666777',
    address: 'Long An',
    needs: 'Thiết kế nội thất nhà phố 140m², hạng sang',
    source: 'google_form', property_type: 'townhouse', area_sqm: 140, estimated_budget: 1540000000,
    stage: 'interested', priority: 'medium', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 75,
    property_class: 'luxury', price_per_sqm: 11000000, region: 'Long An', segment: 'Nhà ở', plan_type: 'online', tags: ['Deal'], deal_value: 1540000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 1,
    created_at: '2026-06-18T07:40:31Z', updated_at: '2026-06-23T10:00:00Z', last_contacted_at: '2026-06-22T09:00:00Z',
  },
  {
    id: 'demo-lead-007', name: 'Trang', phone: '0907777888',
    address: 'Long An',
    needs: 'Thiết kế + thi công nội thất nhà phố 200m²',
    source: 'facebook', property_type: 'townhouse', area_sqm: 200, estimated_budget: 3400000000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 88,
    property_class: 'luxury', price_per_sqm: 17000000, region: 'Long An', segment: 'Nhà ở', plan_type: 'survey', tags: ['Deal', 'VIP'], deal_value: 3400000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-16T07:40:31Z', updated_at: '2026-06-25T14:00:00Z', last_contacted_at: '2026-06-25T10:00:00Z',
  },
  {
    id: 'demo-lead-008', name: 'Cúc (2)', phone: '0908888999',
    address: 'Long An',
    needs: 'Thiết kế + thi công biệt thự 500m², phong cách luxury',
    source: 'facebook', property_type: 'villa', area_sqm: 500, estimated_budget: 5500000000,
    stage: 'survey_scheduled', priority: 'urgent', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 95,
    property_class: 'luxury', price_per_sqm: 11000000, region: 'Long An', segment: 'Biệt thự', plan_type: 'offline', tags: ['Deal', 'VIP', 'Ưu tiên'], deal_value: 5500000000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 3,
    created_at: '2026-06-10T07:40:31Z', updated_at: '2026-06-25T16:00:00Z', last_contacted_at: '2026-06-25T14:00:00Z',
  },
  {
    id: 'demo-lead-009', name: 'Dung (3)', phone: '0909999000',
    address: 'TP.HCM',
    needs: 'Thiết kế nội thất nhà phố 120m²',
    source: 'referral', property_type: 'townhouse', area_sqm: 120, estimated_budget: 840000000,
    stage: 'survey_scheduled', priority: 'medium', assigned_to: 'demo-leader-001', team_id: 'demo-team-01',
    ai_score: 70,
    property_class: 'luxury', price_per_sqm: 7000000, region: 'TP.HCM', segment: 'Nhà ở', plan_type: 'offline', tags: ['Deal'], deal_value: 840000000,
    assigned_user_name: 'Lê Văn Leader', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-17T07:40:31Z', updated_at: '2026-06-24T10:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
];

// ─── Activities (15+) ───────────────────────────────────
export const DEMO_ACTIVITIES: Activity[] = [
  { id: 'demo-act-001', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'note', content: 'KH rất quan tâm phong cách hiện đại tối giản. Ngân sách linh hoạt.', created_at: '2026-05-16T09:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-002', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'call', content: 'Gọi tư vấn gói thiết kế, KH đồng ý hẹn khảo sát.', created_at: '2026-05-21T14:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-003', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'meeting', content: 'Khảo sát nhà 3 tầng Q7. Đo đạc hoàn tất, chụp ảnh hiện trạng.', created_at: '2026-06-02T10:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-004', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'meeting', content: 'Trình bày phương án thiết kế, KH chọn PA2 sửa đổi.', created_at: '2026-06-10T15:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-005', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'stage_change', content: 'Ký hợp đồng thiết kế 45 triệu.', created_at: '2026-06-15T09:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-006', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'note', content: 'KH VIP, biệt thự lớn. Cần bố trí KTS senior.', created_at: '2026-05-28T10:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-007', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'call', content: 'Trao đổi phong cách Indochine, gửi portfolio biệt thự.', created_at: '2026-06-01T11:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-008', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'meeting', content: 'Khảo sát biệt thự Bình Chánh. Khuôn viên 350m2, 2 tầng + sân vườn.', created_at: '2026-06-08T09:30:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-009', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'note', content: 'KH muốn xem thêm mẫu phòng khách Indochine. Đã gửi 3 mẫu.', created_at: '2026-06-23T08:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-010', lead_id: 'demo-lead-003', user_id: 'demo-sales-001', type: 'call', content: 'Tư vấn gói thiết kế căn hộ, KH thích Scandinavian.', created_at: '2026-06-13T14:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-011', lead_id: 'demo-lead-003', user_id: 'demo-sales-001', type: 'note', content: 'Đã hẹn khảo sát căn hộ Sunrise ngày 22/06.', created_at: '2026-06-20T16:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-012', lead_id: 'demo-lead-004', user_id: 'demo-leader-001', type: 'call', content: 'Anh Minh được giới thiệu bởi KH cũ. Shophouse Q2.', created_at: '2026-06-17T10:00:00Z', user_name: 'Lê Văn Leader' },
  { id: 'demo-act-013', lead_id: 'demo-lead-004', user_id: 'demo-leader-001', type: 'note', content: 'Ngân sách tốt, cần showroom design. Ưu tiên cao.', created_at: '2026-06-21T08:00:00Z', user_name: 'Lê Văn Leader' },
  { id: 'demo-act-014', lead_id: 'demo-lead-005', user_id: 'demo-sales-001', type: 'call', content: 'KH đã có bản vẽ, cần thi công. Gửi báo giá thi công.', created_at: '2026-06-08T11:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-015', lead_id: 'demo-lead-005', user_id: 'demo-sales-001', type: 'meeting', content: 'Gặp xem bản vẽ thi công, góp ý cải tiến.', created_at: '2026-06-19T10:00:00Z', user_name: 'Trần Thị Sales' },
];

// ─── Projects (5 projects) ──────────────────────────────
export const DEMO_PROJECTS: Project[] = [
  {
    id: 'demo-proj-001', code: 'PRJ-2026-001', name: 'Nhà phố Q7 - Chị Mai',
    lead_id: 'demo-lead-001', client_name: 'Chị Mai', client_phone: '0901234567',
    address: '123 Nguyễn Văn Linh, Q7', project_type: 'design_build', status: 'active', stage: 'construction',
    design_value: 45000000, construction_value: 455000000, total_value: 500000000,
    spent: 375000000, progress: 75,
    start_date: '2026-04-26T00:00:00Z', target_end_date: '2026-09-25T00:00:00Z',
    created_at: '2026-04-26T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-002', code: 'PRJ-2026-002', name: 'Biệt thự Bình Chánh - Anh Tuấn',
    lead_id: 'demo-lead-002', client_name: 'Anh Tuấn', client_phone: '0908765432',
    address: 'Biệt thự Vinhomes, Bình Chánh', project_type: 'design_build', status: 'active', stage: 'procurement',
    design_value: 120000000, construction_value: 2380000000, total_value: 2500000000,
    spent: 750000000, progress: 30,
    start_date: '2026-05-26T00:00:00Z', target_end_date: '2026-11-22T00:00:00Z',
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-003', code: 'PRJ-2026-003', name: 'Căn hộ Sunrise - Chị Hương',
    lead_id: 'demo-lead-003', client_name: 'Chị Hương', client_phone: '0912345678',
    address: 'Căn hộ Sunrise City, Q7', project_type: 'design_build', status: 'active', stage: 'acceptance',
    design_value: 25000000, construction_value: 155000000, total_value: 180000000,
    spent: 162000000, progress: 90,
    start_date: '2026-03-27T00:00:00Z', target_end_date: '2026-07-20T00:00:00Z',
    created_at: '2026-03-27T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-004', code: 'PRJ-2026-004', name: 'Shophouse Q2 - Anh Minh',
    lead_id: 'demo-lead-004', client_name: 'Anh Minh', client_phone: '0987654321',
    address: 'Shophouse Q2', project_type: 'design_only', status: 'paused', stage: 'design',
    design_value: 80000000, total_value: 80000000,
    spent: 12000000, progress: 15,
    start_date: '2026-06-11T00:00:00Z',
    created_at: '2026-06-11T00:00:00Z', updated_at: '2026-06-20T00:00:00Z',
  },
  {
    id: 'demo-proj-005', code: 'PRJ-2026-005', name: 'Nhà phố Gò Vấp - Chị Lan',
    lead_id: 'demo-lead-005', client_name: 'Chị Lan', client_phone: '0976543210',
    address: 'Nhà phố Gò Vấp', project_type: 'construction_only', status: 'active', stage: 'construction',
    construction_value: 680000000, total_value: 680000000,
    spent: 374000000, progress: 55,
    start_date: '2026-05-11T00:00:00Z', target_end_date: '2026-08-09T00:00:00Z',
    created_at: '2026-05-11T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
];

// ─── Tasks (10+) ────────────────────────────────────────
export const DEMO_TASKS: ProjectTask[] = [
  // Project 1 — Nhà phố Q7 (construction stage)
  // Design
  { id: 'demo-task-001', project_id: 'demo-proj-001', title: '2D Concept', status: 'done', stage: 'design', department: 'design', order: 1, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-002', project_id: 'demo-proj-001', title: '3D Demo', status: 'done', stage: 'design', department: 'design', order: 2, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-003', project_id: 'demo-proj-001', title: '3D Render', status: 'done', stage: 'design', department: 'design', order: 3, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-004', project_id: 'demo-proj-001', title: 'Bản vẽ kỹ thuật', status: 'done', stage: 'design', department: 'design', order: 4, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-005', project_id: 'demo-proj-001', title: 'Thiết kế Final — Gửi KH', status: 'done', stage: 'design', department: 'design', order: 5, created_at: '2026-04-26T00:00:00Z' },
  // Quotation
  { id: 'demo-task-006', project_id: 'demo-proj-001', title: 'Báo giá 2D', status: 'done', stage: 'quotation', department: 'quotation', order: 6, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-007', project_id: 'demo-proj-001', title: 'Báo giá 3D', status: 'done', stage: 'quotation', department: 'quotation', order: 7, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-008', project_id: 'demo-proj-001', title: 'Báo giá Nội thất', status: 'done', stage: 'quotation', department: 'quotation', order: 8, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-009', project_id: 'demo-proj-001', title: 'Báo giá Final — KH duyệt', status: 'done', stage: 'quotation', department: 'quotation', order: 9, created_at: '2026-04-26T00:00:00Z' },
  // Procurement
  { id: 'demo-task-010', project_id: 'demo-proj-001', title: 'Chuẩn bị vật liệu', status: 'done', stage: 'procurement', department: 'procurement', order: 10, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-011', project_id: 'demo-proj-001', title: 'Hoàn thiện SPECS', status: 'done', stage: 'procurement', department: 'procurement', order: 11, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-012', project_id: 'demo-proj-001', title: 'Đặt hàng & theo dõi giao nhận', status: 'done', stage: 'procurement', department: 'procurement', order: 12, created_at: '2026-04-26T00:00:00Z' },
  // Construction
  { id: 'demo-task-013', project_id: 'demo-proj-001', title: 'Giấy phép (nếu có)', status: 'done', stage: 'construction', department: 'construction', order: 13, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-014', project_id: 'demo-proj-001', title: 'Chuẩn bị tiến độ thi công', status: 'done', stage: 'construction', department: 'construction', order: 14, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-015', project_id: 'demo-proj-001', title: 'Thi công phần thô', status: 'done', stage: 'construction', department: 'construction', order: 15, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-016', project_id: 'demo-proj-001', title: 'Thi công nội thất', status: 'in_progress', stage: 'construction', department: 'construction', order: 16, due_date: '2026-07-15T00:00:00Z', created_at: '2026-04-26T00:00:00Z' },
  // Acceptance
  { id: 'demo-task-017', project_id: 'demo-proj-001', title: 'Bàn giao', status: 'not_started', stage: 'acceptance', department: 'construction', order: 17, due_date: '2026-08-15T00:00:00Z', created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-018', project_id: 'demo-proj-001', title: 'Nghiệm thu khối lượng', status: 'not_started', stage: 'acceptance', department: 'accounting', order: 18, created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-task-019', project_id: 'demo-proj-001', title: 'Bảo hành — Bảo trì', status: 'not_started', stage: 'acceptance', department: 'construction', order: 19, created_at: '2026-04-26T00:00:00Z' },

  // Project 2 — Biệt thự Bình Chánh (design stage)
  { id: 'demo-task-020', project_id: 'demo-proj-002', title: '2D Concept', status: 'done', stage: 'design', department: 'design', order: 1, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-021', project_id: 'demo-proj-002', title: '3D Demo', status: 'done', stage: 'design', department: 'design', order: 2, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-022', project_id: 'demo-proj-002', title: '3D Render', status: 'in_progress', stage: 'design', department: 'design', order: 3, due_date: '2026-07-30T00:00:00Z', created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-023', project_id: 'demo-proj-002', title: 'Bản vẽ kỹ thuật', status: 'not_started', stage: 'design', department: 'design', order: 4, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-024', project_id: 'demo-proj-002', title: 'Thiết kế Final — Gửi KH', status: 'not_started', stage: 'design', department: 'design', order: 5, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-025', project_id: 'demo-proj-002', title: 'Báo giá 2D', status: 'not_started', stage: 'quotation', department: 'quotation', order: 6, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-026', project_id: 'demo-proj-002', title: 'Báo giá 3D', status: 'not_started', stage: 'quotation', department: 'quotation', order: 7, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-027', project_id: 'demo-proj-002', title: 'Báo giá Nội thất', status: 'not_started', stage: 'quotation', department: 'quotation', order: 8, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-028', project_id: 'demo-proj-002', title: 'Báo giá Final — KH duyệt', status: 'not_started', stage: 'quotation', department: 'quotation', order: 9, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-029', project_id: 'demo-proj-002', title: 'Chuẩn bị vật liệu', status: 'not_started', stage: 'procurement', department: 'procurement', order: 10, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-030', project_id: 'demo-proj-002', title: 'Hoàn thiện SPECS', status: 'not_started', stage: 'procurement', department: 'procurement', order: 11, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-031', project_id: 'demo-proj-002', title: 'Đặt hàng & theo dõi giao nhận', status: 'not_started', stage: 'procurement', department: 'procurement', order: 12, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-032', project_id: 'demo-proj-002', title: 'Giấy phép (nếu có)', status: 'not_started', stage: 'construction', department: 'construction', order: 13, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-033', project_id: 'demo-proj-002', title: 'Chuẩn bị tiến độ thi công', status: 'not_started', stage: 'construction', department: 'construction', order: 14, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-034', project_id: 'demo-proj-002', title: 'Thi công phần thô', status: 'not_started', stage: 'construction', department: 'construction', order: 15, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-035', project_id: 'demo-proj-002', title: 'Thi công nội thất', status: 'not_started', stage: 'construction', department: 'construction', order: 16, due_date: '2026-11-15T00:00:00Z', created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-036', project_id: 'demo-proj-002', title: 'Bàn giao', status: 'not_started', stage: 'acceptance', department: 'construction', order: 17, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-037', project_id: 'demo-proj-002', title: 'Nghiệm thu khối lượng', status: 'not_started', stage: 'acceptance', department: 'accounting', order: 18, created_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-task-038', project_id: 'demo-proj-002', title: 'Bảo hành — Bảo trì', status: 'not_started', stage: 'acceptance', department: 'construction', order: 19, created_at: '2026-05-26T00:00:00Z' },

  // Project 3 — Căn hộ Sunrise (acceptance stage)
  { id: 'demo-task-039', project_id: 'demo-proj-003', title: '2D Concept', status: 'done', stage: 'design', department: 'design', order: 1, created_at: '2026-03-27T00:00:00Z' },
  { id: 'demo-task-040', project_id: 'demo-proj-003', title: 'Thi công nội thất', status: 'done', stage: 'construction', department: 'construction', order: 2, created_at: '2026-03-27T00:00:00Z' },
  { id: 'demo-task-041', project_id: 'demo-proj-003', title: 'Nghiệm thu & bàn giao', status: 'in_progress', stage: 'acceptance', department: 'construction', order: 3, due_date: '2026-07-10T00:00:00Z', created_at: '2026-03-27T00:00:00Z' },

  // Project 5 — Nhà phố Gò Vấp (procurement stage)
  { id: 'demo-task-042', project_id: 'demo-proj-005', title: 'Thi công phần thô', status: 'done', stage: 'construction', department: 'construction', order: 1, created_at: '2026-05-11T00:00:00Z' },
  { id: 'demo-task-043', project_id: 'demo-proj-005', title: 'Lắp đặt nội thất', status: 'in_progress', stage: 'construction', department: 'construction', order: 2, due_date: '2026-07-20T00:00:00Z', created_at: '2026-05-11T00:00:00Z' },
  { id: 'demo-task-044', project_id: 'demo-proj-005', title: 'Nghiệm thu & bàn giao', status: 'not_started', stage: 'acceptance', department: 'construction', order: 3, due_date: '2026-08-05T00:00:00Z', created_at: '2026-05-11T00:00:00Z' },
];

// ─── Transactions (12) ──────────────────────────────────
export const DEMO_TRANSACTIONS: Transaction[] = [
  { id: 'demo-tx-001', code: 'TX-001', type: 'income', category: 'design_contract', description: 'HĐ Thiết kế Chị Mai', amount: 45000000, project_id: 'demo-proj-001', status: 'completed', date: '2026-05-16T00:00:00Z', created_at: '2026-05-16T00:00:00Z' },
  { id: 'demo-tx-002', code: 'TX-002', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Mai - đợt 1', amount: 200000000, project_id: 'demo-proj-001', status: 'completed', date: '2026-05-21T00:00:00Z', created_at: '2026-05-21T00:00:00Z' },
  { id: 'demo-tx-003', code: 'TX-003', type: 'expense', category: 'material', description: 'Vật liệu thi công Q7 - đợt 1', amount: 85000000, project_id: 'demo-proj-001', status: 'completed', date: '2026-06-01T00:00:00Z', created_at: '2026-06-01T00:00:00Z' },
  { id: 'demo-tx-004', code: 'TX-004', type: 'expense', category: 'labor', description: 'Nhân công thi công Q7 - T6', amount: 45000000, project_id: 'demo-proj-001', status: 'completed', date: '2026-06-06T00:00:00Z', created_at: '2026-06-06T00:00:00Z' },
  { id: 'demo-tx-005', code: 'TX-005', type: 'income', category: 'design_contract', description: 'HĐ Thiết kế Anh Tuấn', amount: 120000000, project_id: 'demo-proj-002', status: 'completed', date: '2026-05-28T00:00:00Z', created_at: '2026-05-28T00:00:00Z' },
  { id: 'demo-tx-006', code: 'TX-006', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Anh Tuấn - đợt 1', amount: 630000000, project_id: 'demo-proj-002', status: 'completed', date: '2026-06-03T00:00:00Z', created_at: '2026-06-03T00:00:00Z' },
  { id: 'demo-tx-007', code: 'TX-007', type: 'expense', category: 'material', description: 'Vật liệu biệt thự Bình Chánh', amount: 350000000, project_id: 'demo-proj-002', status: 'completed', date: '2026-06-10T00:00:00Z', created_at: '2026-06-10T00:00:00Z' },
  { id: 'demo-tx-008', code: 'TX-008', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Hương', amount: 155000000, project_id: 'demo-proj-003', status: 'completed', date: '2026-04-11T00:00:00Z', created_at: '2026-04-11T00:00:00Z' },
  { id: 'demo-tx-009', code: 'TX-009', type: 'expense', category: 'material', description: 'Nội thất căn hộ Sunrise', amount: 95000000, project_id: 'demo-proj-003', status: 'completed', date: '2026-04-26T00:00:00Z', created_at: '2026-04-26T00:00:00Z' },
  { id: 'demo-tx-010', code: 'TX-010', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Lan - đợt 1', amount: 340000000, project_id: 'demo-proj-005', status: 'completed', date: '2026-05-16T00:00:00Z', created_at: '2026-05-16T00:00:00Z' },
  { id: 'demo-tx-011', code: 'TX-011', type: 'expense', category: 'salary', description: 'Lương tháng 6/2026', amount: 180000000, status: 'completed', date: '2026-06-25T00:00:00Z', created_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-tx-012', code: 'TX-012', type: 'expense', category: 'commission', description: 'Hoa hồng T6 - Sales team', amount: 28500000, status: 'pending', date: '2026-06-27T00:00:00Z', created_at: '2026-06-27T00:00:00Z' },
];

// ─── Accounting Summary ──────────────────────────────────
export const DEMO_ACCOUNTING_SUMMARY: AccountingSummary = {
  total_income: 1490000000,
  total_expense: 783500000,
  net: 706500000,
  by_category: [
    { category: 'design_contract', type: 'income', total: 165000000, count: 2 },
    { category: 'construction_contract', type: 'income', total: 1325000000, count: 4 },
    { category: 'material', type: 'expense', total: 530000000, count: 3 },
    { category: 'labor', type: 'expense', total: 45000000, count: 1 },
    { category: 'salary', type: 'expense', total: 180000000, count: 1 },
    { category: 'commission', type: 'expense', total: 28500000, count: 1 },
  ],
};

// ─── Commissions (4) ────────────────────────────────────
export const DEMO_COMMISSIONS: Commission[] = [
  { id: 'demo-comm-001', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-001', type: 'design_commission', rate: 0.03, base_amount: 45000000, commission_amount: 1350000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-002', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-001', type: 'construction_commission', rate: 0.02, base_amount: 455000000, commission_amount: 9100000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-003', user_id: 'demo-leader-001', user_name: 'Lê Văn Leader', project_id: 'demo-proj-001', type: 'leader_override', rate: 0.005, base_amount: 500000000, commission_amount: 2500000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-004', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-002', type: 'design_commission', rate: 0.03, base_amount: 120000000, commission_amount: 3600000, milestone: 'signing', status: 'pending', period: '2026-06' },
];

// ─── Payroll (3) ────────────────────────────────────────
export const DEMO_PAYROLL: PayrollEntry[] = [
  { id: 'demo-pay-001', user_id: 'demo-admin-001', user_name: 'Hồ Minh Tuấn', period: '2026-06', base_salary: 25000000, commission_total: 0, bonus: 0, deductions: 0, net_salary: 25000000, status: 'approved' },
  { id: 'demo-pay-002', user_id: 'demo-leader-001', user_name: 'Lê Văn Leader', period: '2026-06', base_salary: 15000000, commission_total: 2500000, bonus: 2000000, deductions: 1500000, net_salary: 18000000, status: 'approved' },
  { id: 'demo-pay-003', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', period: '2026-06', base_salary: 8000000, commission_total: 10450000, bonus: 1000000, deductions: 1200000, net_salary: 18250000, status: 'approved' },
];

// ─── Pipeline Stats (9 real leads) ───────────────────────
export const DEMO_PIPELINE_STATS: PipelineStats = {
  total_leads: 9,
  by_stage: { new: 0, interested: 7, survey_scheduled: 2, potential: 0, signed_design: 0 },
  conversion_rate: 0,
  pipeline_value: 23168000000,
  sla_compliance: 85.7,
  overdue_count: 2,
  today_count: 1,
  unassigned_count: 0,
};

// ─── Pipeline Kanban ─────────────────────────────────────
export const DEMO_PIPELINE_KANBAN: PipelineKanban[] = [
  { stage: 'new', stage_label: 'Tiếp nhận mới', leads: DEMO_LEADS.filter(l => l.stage === 'new'), count: 0 },
  { stage: 'interested', stage_label: 'Đang tư vấn', leads: DEMO_LEADS.filter(l => l.stage === 'interested'), count: 7 },
  { stage: 'survey_scheduled', stage_label: 'Đang chờ', leads: DEMO_LEADS.filter(l => l.stage === 'survey_scheduled'), count: 2 },
  { stage: 'potential', stage_label: 'Đã chốt hồ sơ', leads: DEMO_LEADS.filter(l => l.stage === 'potential'), count: 0 },
  { stage: 'signed_design', stage_label: 'Deal đã thắng', leads: DEMO_LEADS.filter(l => l.stage === 'signed_design'), count: 0 },
];

// ─── Dashboard Executive ─────────────────────────────────
export const DEMO_DASHBOARD_EXECUTIVE: DashboardExecutive = {
  total_leads: 9,
  total_leads_month: 9,
  conversion_rate: 0,
  pipeline_value: 23168000000,
  total_contracts: 3,
  total_contract_value: 264_900_000_000,
  active_projects: 3,
  avg_project_progress: 50,
  sla_compliance: 85.7,
  overdue_leads: 2,
  team_performance: [
    { team: 'Đội Văn Toàn', total_leads: 5, signed: 1, conversion: 20.0 },
    { team: 'Đội Thái Phượng', total_leads: 1, signed: 0, conversion: 0 },
    { team: 'Phòng Thiết Kế', total_leads: 0, signed: 0, conversion: 0 },
    { team: 'Ban Giám Đốc', total_leads: 1, signed: 0, conversion: 0 },
  ],
  stage_funnel: { new: 0, interested: 7, survey_scheduled: 2, potential: 0, signed_design: 0, lost: 0, dormant: 0 },
  monthly_trend: [],
  financial_summary: {
    total_revenue_ytd: 264_900_000_000,
    total_cost_ytd: 212_600_000_000,
    net_profit_ytd: 52_300_000_000,
    roi: 24.6,
    yoy_growth: 35.2,
    avg_project_margin: 19.7,
    cash_flow: 38_500_000_000,
    outstanding_receivable: 22_300_000_000,
  },
  forecast: {
    q3_2026: 58_500_000_000,
    q4_2026: 72_800_000_000,
    full_year_2026: 420_000_000_000,
    full_year_2025: 310_000_000_000,
  },
  growth_metrics: {
    lead_growth_rate: 15.2,
    conversion_improvement: 3.8,
    avg_deal_size: 8_500_000_000,
    customer_acquisition_cost: 25_000_000,
    customer_lifetime_value: 15_800_000_000,
    pipeline_velocity: 35,
  },
  risk_hedging: {
    concentration_risk: 'medium',
    top_client_pct: 28.5,
    pipeline_coverage: 2.8,
    cash_reserve_months: 4.2,
    overdue_receivable_pct: 12.1,
  },
};

// ─── Dashboard Personal ──────────────────────────────────
export const DEMO_DASHBOARD_PERSONAL: DashboardPersonal = {
  user_name: 'Trần Thị Sales',
  total_active_leads: 7,
  by_stage: { new: 0, interested: 6, survey_scheduled: 1, potential: 0, signed_design: 0 },
  overdue_followup: [
    { lead_name: 'Anh Phong', phone: '0965432109', days: 2 },
  ],
  today_appointments: [
    { lead_name: 'Chị Hương', time: '10:00', type: 'Khảo sát căn hộ' },
  ],
  weekly_kpis: { calls: 12, meetings: 3, new_leads: 1 },
  pipeline_value: 23168000000,
  ai_suggestions: [
    { action: 'Follow up Bống — deal 4.188 tỷ', reason: 'Đang tư vấn online, deal lớn Long An', priority: 'high' },
    { action: 'Hẹn khảo sát Trang — deal 3.4 tỷ', reason: 'Đang khảo sát, cần chốt lịch onsite', priority: 'urgent' },
  ],
};

// ─── Customers (5) ──────────────────────────────────────
export const DEMO_CUSTOMERS: Customer[] = [
  { id: 'demo-cust-001', name: 'Chị Mai', phone: '0901234567', email: 'mai.nguyen@gmail.com', address: '123 Nguyễn Văn Linh, Q7, TP.HCM', type: 'individual', lead_id: 'demo-lead-001', created_at: '2026-05-11T00:00:00Z', updated_at: '2026-05-11T00:00:00Z' },
  { id: 'demo-cust-002', name: 'Anh Tuấn', phone: '0908765432', email: 'tuan.pham@yahoo.com', address: 'Biệt thự Vinhomes Central Park, Bình Chánh', type: 'individual', lead_id: 'demo-lead-002', created_at: '2026-05-26T00:00:00Z', updated_at: '2026-05-26T00:00:00Z' },
  { id: 'demo-cust-003', name: 'Chị Hương', phone: '0912345678', email: 'huong.le@outlook.com', address: 'Căn hộ Sunrise City, Q7', type: 'individual', lead_id: 'demo-lead-003', created_at: '2026-06-11T00:00:00Z', updated_at: '2026-06-11T00:00:00Z' },
  { id: 'demo-cust-004', name: 'Chị Lan', phone: '0976543210', address: 'Nhà phố Gò Vấp', type: 'individual', lead_id: 'demo-lead-005', created_at: '2026-06-06T00:00:00Z', updated_at: '2026-06-06T00:00:00Z' },
  { id: 'demo-cust-005', name: 'Công ty TNHH Minh Design', phone: '0987654321', email: 'minh@minhdesign.vn', address: 'Shophouse Q2, TP.HCM', type: 'company', company_name: 'Công ty TNHH Minh Design', tax_code: '0316789012', lead_id: 'demo-lead-004', created_at: '2026-06-16T00:00:00Z', updated_at: '2026-06-16T00:00:00Z' },
];

// ─── Contracts (3) ──────────────────────────────────────
export const DEMO_CONTRACTS: Contract[] = [
  {
    id: 'demo-ct-001', code: 'HD-2026-001', project_id: 'demo-proj-001',
    title: 'HĐ Thiết kế + Thi công Nhà phố Q7 - Chị Mai',
    status: 'signed', total_value: 500000000, signed_date: '2026-05-11', working_days: 120, start_date: '2026-04-26',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 25, milestone: 'signing', status: 'paid', amount: 125000000, paid_date: '2026-05-11' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 25, milestone: 'rough_complete', status: 'paid', amount: 125000000, paid_date: '2026-06-06' },
      { name: 'Đợt 3 (Nội thất)', percentage: 25, milestone: 'interior_complete', status: 'pending', amount: 125000000 },
      { name: 'Đợt 4 (Bàn giao)', percentage: 25, milestone: 'handover', status: 'pending', amount: 125000000 },
    ]},
    created_at: '2026-04-26T00:00:00Z', updated_at: '2026-06-06T00:00:00Z',
  },
  {
    id: 'demo-ct-002', code: 'HD-2026-002', project_id: 'demo-proj-002',
    title: 'HĐ Thiết kế + Thi công Biệt thự Bình Chánh - Anh Tuấn',
    status: 'signed', total_value: 2500000000, signed_date: '2026-05-28', working_days: 180, start_date: '2026-05-26',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 25, milestone: 'signing', status: 'paid', amount: 625000000, paid_date: '2026-05-28' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 25, milestone: 'rough_complete', status: 'pending', amount: 625000000 },
      { name: 'Đợt 3 (Nội thất)', percentage: 25, milestone: 'interior_complete', status: 'pending', amount: 625000000 },
      { name: 'Đợt 4 (Bàn giao)', percentage: 25, milestone: 'handover', status: 'pending', amount: 625000000 },
    ]},
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-05-28T00:00:00Z',
  },
  {
    id: 'demo-ct-003', code: 'HD-2026-003', project_id: 'demo-proj-005',
    title: 'HĐ Thi công Nhà phố Gò Vấp - Chị Lan',
    status: 'signed', total_value: 680000000, signed_date: '2026-05-11', working_days: 90, start_date: '2026-05-11',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 30, milestone: 'signing', status: 'paid', amount: 204000000, paid_date: '2026-05-11' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 30, milestone: 'rough_complete', status: 'paid', amount: 204000000, paid_date: '2026-06-10' },
      { name: 'Đợt 3 (Bàn giao)', percentage: 40, milestone: 'handover', status: 'pending', amount: 272000000 },
    ]},
    created_at: '2026-05-11T00:00:00Z', updated_at: '2026-06-10T00:00:00Z',
  },
];

// ─── Quotations (4) ──────────────────────────────────────
export const DEMO_QUOTATIONS: Quotation[] = [
  {
    id: 'demo-q-001', code: 'BG-2026-001', type: 'design', project_id: 'demo-proj-001', lead_id: 'demo-lead-001',
    title: 'Báo giá thiết kế nội thất nhà phố Q7 - Chị Mai',
    status: 'approved', total_amount: 45000000, tax_amount: 4500000, revision: 2,
    items: { line_items: [
      { name: 'Thiết kế phòng khách', unit: 'gói', quantity: 1, unit_price: 15000000, total: 15000000 },
      { name: 'Thiết kế phòng ngủ master', unit: 'gói', quantity: 1, unit_price: 12000000, total: 12000000 },
      { name: 'Thiết kế bếp + phòng ăn', unit: 'gói', quantity: 1, unit_price: 10000000, total: 10000000 },
      { name: 'Thiết kế phòng tắm (x2)', unit: 'gói', quantity: 2, unit_price: 4000000, total: 8000000 },
    ]},
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-05T00:00:00Z',
  },
  {
    id: 'demo-q-002', code: 'BG-2026-002', type: 'construction', project_id: 'demo-proj-001', lead_id: 'demo-lead-001',
    title: 'Báo giá thi công nội thất nhà phố Q7 - Chị Mai',
    status: 'approved', total_amount: 455000000, tax_amount: 45500000, revision: 1,
    items: { line_items: [
      { name: 'Thi công trần thạch cao', unit: 'm2', quantity: 120, unit_price: 450000, total: 54000000 },
      { name: 'Hệ tủ bếp cao cấp', unit: 'bộ', quantity: 1, unit_price: 85000000, total: 85000000 },
      { name: 'Sàn gỗ công nghiệp', unit: 'm2', quantity: 150, unit_price: 650000, total: 97500000 },
      { name: 'Nội thất phòng khách', unit: 'bộ', quantity: 1, unit_price: 120000000, total: 120000000 },
      { name: 'Nội thất 2 phòng ngủ', unit: 'bộ', quantity: 2, unit_price: 49250000, total: 98500000 },
    ]},
    created_at: '2026-05-05T00:00:00Z', updated_at: '2026-05-05T00:00:00Z',
  },
  {
    id: 'demo-q-003', code: 'BG-2026-003', type: 'design', project_id: 'demo-proj-002', lead_id: 'demo-lead-002',
    title: 'Báo giá thiết kế biệt thự Indochine - Anh Tuấn',
    status: 'approved', total_amount: 120000000, tax_amount: 12000000, revision: 1,
    items: { line_items: [
      { name: 'Thiết kế kiến trúc mặt ngoài', unit: 'gói', quantity: 1, unit_price: 35000000, total: 35000000 },
      { name: 'Thiết kế nội thất tầng 1', unit: 'gói', quantity: 1, unit_price: 45000000, total: 45000000 },
      { name: 'Thiết kế nội thất tầng 2', unit: 'gói', quantity: 1, unit_price: 30000000, total: 30000000 },
      { name: 'Thiết kế sân vườn', unit: 'gói', quantity: 1, unit_price: 10000000, total: 10000000 },
    ]},
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-05-26T00:00:00Z',
  },
  {
    id: 'demo-q-004', code: 'BG-2026-004', type: 'construction', project_id: 'demo-proj-005', lead_id: 'demo-lead-005',
    title: 'Báo giá thi công nhà phố Gò Vấp - Chị Lan',
    status: 'sent', total_amount: 680000000, tax_amount: 68000000, revision: 1,
    items: { line_items: [
      { name: 'Thi công phần thô', unit: 'gói', quantity: 1, unit_price: 280000000, total: 280000000 },
      { name: 'Nội thất toàn bộ', unit: 'gói', quantity: 1, unit_price: 320000000, total: 320000000 },
      { name: 'Hệ thống điện + nước', unit: 'gói', quantity: 1, unit_price: 80000000, total: 80000000 },
    ]},
    created_at: '2026-06-08T00:00:00Z', updated_at: '2026-06-10T00:00:00Z',
  },
];

// ─── Materials (10) ──────────────────────────────────────
export const DEMO_MATERIALS: Material[] = [
  { id: 'demo-mat-001', code: 'VT-001', name: 'Gỗ công nghiệp MDF lõi xanh', category: 'wood', unit: 'tấm', unit_price: 350000, quantity_in_stock: 120, min_stock: 20, supplier: 'Công ty An Cường', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-002', code: 'VT-002', name: 'Sàn gỗ Egger 12mm', category: 'wood', unit: 'm2', unit_price: 650000, quantity_in_stock: 85, min_stock: 50, supplier: 'Egger Việt Nam', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-003', code: 'VT-003', name: 'Đá granite đen Ấn Độ', category: 'stone', unit: 'm2', unit_price: 1200000, quantity_in_stock: 45, min_stock: 15, supplier: 'Đá Hoàng Gia', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-004', code: 'VT-004', name: 'Sơn Dulux nội thất cao cấp', category: 'paint', unit: 'thùng', unit_price: 890000, quantity_in_stock: 30, min_stock: 10, supplier: 'AkzoNobel', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-005', code: 'VT-005', name: 'Inox 304 ống vuông 40x40', category: 'metal', unit: 'cây', unit_price: 285000, quantity_in_stock: 60, min_stock: 20, supplier: 'Inox Đại Dương', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-006', code: 'VT-006', name: 'Kính cường lực 10mm', category: 'glass', unit: 'm2', unit_price: 480000, quantity_in_stock: 35, min_stock: 10, supplier: 'Kính Hưng Thịnh', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-007', code: 'VT-007', name: 'Đèn LED panel 600x600', category: 'electrical', unit: 'cái', unit_price: 320000, quantity_in_stock: 8, min_stock: 15, supplier: 'Rạng Đông', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-008', code: 'VT-008', name: 'Vải sofa nhập Bỉ', category: 'fabric', unit: 'm', unit_price: 950000, quantity_in_stock: 40, min_stock: 10, supplier: 'Vải Hoàng Hà', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-009', code: 'VT-009', name: 'Ống PPR nóng 25mm', category: 'plumbing', unit: 'cây', unit_price: 125000, quantity_in_stock: 100, min_stock: 30, supplier: 'Vesbo', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-010', code: 'VT-010', name: 'Bản lề giảm chấn Blum', category: 'furniture', unit: 'cái', unit_price: 85000, quantity_in_stock: 200, min_stock: 50, supplier: 'Blum Việt Nam', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
];

// ─── Material Usages (6) ─────────────────────────────────
export const DEMO_MATERIAL_USAGES: MaterialUsage[] = [
  { id: 'demo-mu-001', material_id: 'demo-mat-001', project_id: 'demo-proj-001', quantity: 25, created_at: '2026-05-26T00:00:00Z', material_name: 'Gỗ MDF lõi xanh', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-002', material_id: 'demo-mat-002', project_id: 'demo-proj-001', quantity: 45, created_at: '2026-06-01T00:00:00Z', material_name: 'Sàn gỗ Egger 12mm', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-003', material_id: 'demo-mat-004', project_id: 'demo-proj-001', quantity: 8, created_at: '2026-06-06T00:00:00Z', material_name: 'Sơn Dulux nội thất', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-004', material_id: 'demo-mat-003', project_id: 'demo-proj-002', quantity: 15, created_at: '2026-06-10T00:00:00Z', material_name: 'Đá granite đen', project_name: 'Biệt thự Bình Chánh - Anh Tuấn' },
  { id: 'demo-mu-005', material_id: 'demo-mat-005', project_id: 'demo-proj-002', quantity: 20, created_at: '2026-06-15T00:00:00Z', material_name: 'Inox 304 ống vuông', project_name: 'Biệt thự Bình Chánh - Anh Tuấn' },
  { id: 'demo-mu-006', material_id: 'demo-mat-010', project_id: 'demo-proj-003', quantity: 24, created_at: '2026-06-17T00:00:00Z', material_name: 'Bản lề giảm chấn Blum', project_name: 'Căn hộ Sunrise - Chị Hương' },
];

// ─── AI Suggestions ──────────────────────────────────────
export const DEMO_AI_SUGGESTIONS: AISuggestion[] = [
  { action: 'Follow up Cúc (2) ngay — deal 5.5 tỷ', reason: 'Lead VIP 500m² Long An, biệt thự luxury, đang tư vấn offline', priority: 'urgent', message_template: 'Chào chị Cúc, JAMA HOME đã chuẩn bị phương án thiết kế cho biệt thự 500m². Chị có lịch khảo sát nào thuận tiện ạ?' },
  { action: 'Chốt khảo sát với Trang — deal 3.4 tỷ', reason: 'Đang khảo sát online, cần hẹn lịch khảo sát onsite Long An', priority: 'high', message_template: 'Chào chị Trang, JAMA HOME muốn hẹn lịch khảo sát trực tiếp nhà phố 200m². Cuối tuần này chị có rảnh không ạ?' },
  { action: 'Tư vấn cho Bống (4.188 tỷ)', reason: 'Deal lớn nhất, hạng sang 349m², đang tư vấn online', priority: 'high', message_template: 'Chào anh/chị Bống, JAMA HOME đã có phương án thiết kế cho nhà phố 349m² Long An. Anh/chị muốn xem bản demo không ạ?' },
];

// ─── P&L Summary ───────────────────────────────────────
export const DEMO_PNL_SUMMARY = {
  total_revenue: 264_900_000_000,
  total_costs: 212_600_000_000,
  net_profit: 52_300_000_000,
  margin_pct: 19.7,
  revenue_by_project: [
    { project_id: 'proj-001', project_code: 'JMH-0601', project_name: 'Biệt thự An Lạc - Long An', revenue: 25_800_000_000, costs: 20_100_000_000, profit: 5_700_000_000, margin_pct: 22.1, status: 'active' },
    { project_id: 'proj-002', project_code: 'JMH-0608', project_name: 'Villa Thảo Điền - Quận 2', revenue: 28_500_000_000, costs: 22_800_000_000, profit: 5_700_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-003', project_code: 'JMH-0593', project_name: 'Penthouse Sky Garden - Quận 7', revenue: 22_300_000_000, costs: 17_400_000_000, profit: 4_900_000_000, margin_pct: 22.0, status: 'completed' },
    { project_id: 'proj-004', project_code: 'JMH-0612', project_name: 'Biệt thự Phú Mỹ Hưng - Quận 7', revenue: 20_500_000_000, costs: 16_400_000_000, profit: 4_100_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-005', project_code: 'JMH-0618', project_name: 'Villa Riviera - Quận 2', revenue: 24_200_000_000, costs: 18_700_000_000, profit: 5_500_000_000, margin_pct: 22.7, status: 'active' },
    { project_id: 'proj-006', project_code: 'JMH-0587', project_name: 'Nhà phố Sunrise - Quận 7', revenue: 15_500_000_000, costs: 12_400_000_000, profit: 3_100_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-007', project_code: 'JMH-0595', project_name: 'Căn hộ Penthouse - Thủ Đức', revenue: 12_200_000_000, costs: 9_500_000_000, profit: 2_700_000_000, margin_pct: 22.1, status: 'completed' },
    { project_id: 'proj-008', project_code: 'JMH-0610', project_name: 'Villa The Manor - Bình Chánh', revenue: 11_800_000_000, costs: 9_400_000_000, profit: 2_400_000_000, margin_pct: 20.3, status: 'active' },
    { project_id: 'proj-009', project_code: 'JMH-0622', project_name: 'Nhà phố Lakeview - Quận 9', revenue: 9_500_000_000, costs: 7_600_000_000, profit: 1_900_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-010', project_code: 'JMH-0578', project_name: 'Căn hộ Vinhomes Central Park', revenue: 14_200_000_000, costs: 11_400_000_000, profit: 2_800_000_000, margin_pct: 19.7, status: 'completed' },
    { project_id: 'proj-011', project_code: 'JMH-0603', project_name: 'Duplex Masteri Thảo Điền', revenue: 8_800_000_000, costs: 7_000_000_000, profit: 1_800_000_000, margin_pct: 20.5, status: 'active' },
    { project_id: 'proj-012', project_code: 'JMH-0585', project_name: 'Nhà phố Mega Village - Quận 9', revenue: 7_500_000_000, costs: 6_000_000_000, profit: 1_500_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-013', project_code: 'JMH-0625', project_name: 'Căn hộ Diamond Island - Quận 2', revenue: 10_800_000_000, costs: 8_600_000_000, profit: 2_200_000_000, margin_pct: 20.4, status: 'active' },
    { project_id: 'proj-014', project_code: 'JMH-0575', project_name: 'Căn hộ The Sun Avenue - Quận 2', revenue: 5_500_000_000, costs: 4_400_000_000, profit: 1_100_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-015', project_code: 'JMH-0582', project_name: 'Studio Gateway Thảo Điền', revenue: 3_200_000_000, costs: 2_600_000_000, profit: 600_000_000, margin_pct: 18.8, status: 'completed' },
    { project_id: 'proj-016', project_code: 'JMH-0598', project_name: 'Căn hộ Saigon Pearl - Bình Thạnh', revenue: 4_800_000_000, costs: 3_800_000_000, profit: 1_000_000_000, margin_pct: 20.8, status: 'active' },
    { project_id: 'proj-017', project_code: 'JMH-0614', project_name: 'Nhà phố Bình Thạnh - Chị Hương', revenue: 4_500_000_000, costs: 3_600_000_000, profit: 900_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-018', project_code: 'JMH-0628', project_name: 'Văn phòng Quận 1 - Interior', revenue: 3_800_000_000, costs: 3_000_000_000, profit: 800_000_000, margin_pct: 21.1, status: 'active' },
    { project_id: 'proj-019', project_code: 'JMH-0632', project_name: 'Căn hộ Estella Heights - Quận 2', revenue: 6_200_000_000, costs: 5_000_000_000, profit: 1_200_000_000, margin_pct: 19.4, status: 'active' },
    { project_id: 'proj-020', project_code: 'JMH-0572', project_name: 'Sửa chữa VP Tân Bình', revenue: 2_500_000_000, costs: 2_000_000_000, profit: 500_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-021', project_code: 'JMH-0635', project_name: 'Căn hộ Midtown Phú Mỹ Hưng', revenue: 4_800_000_000, costs: 3_800_000_000, profit: 1_000_000_000, margin_pct: 20.8, status: 'active' },
    { project_id: 'proj-022', project_code: 'JMH-0640', project_name: 'Nhà phố Gò Vấp - Chị Lan', revenue: 3_500_000_000, costs: 2_800_000_000, profit: 700_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-023', project_code: 'JMH-0616', project_name: 'Căn hộ Masteri An Phú', revenue: 5_200_000_000, costs: 4_200_000_000, profit: 1_000_000_000, margin_pct: 19.2, status: 'active' },
    { project_id: 'proj-024', project_code: 'JMH-0615', project_name: 'Shophouse Bến Thành - Quận 1', revenue: 6_500_000_000, costs: 6_900_000_000, profit: -400_000_000, margin_pct: -6.2, status: 'at_risk' },
    { project_id: 'proj-025', project_code: 'JMH-0630', project_name: 'Căn hộ Quận 8 - Renovation', revenue: 2_800_000_000, costs: 3_200_000_000, profit: -400_000_000, margin_pct: -14.3, status: 'at_risk' },
  ],
};

// ─── Salary Grades (Finance) ────────────────────────────
export const DEMO_SALARY_GRADES: SalaryGrade[] = [
  { id: 'sg-1', grade_name: 'Bac 1', base_salary: 8000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-2', grade_name: 'Bac 2', base_salary: 10000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-3', grade_name: 'Bac 3', base_salary: 12000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-4', grade_name: 'Bac 4', base_salary: 15000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-5', grade_name: 'Bac 5', base_salary: 20000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-6', grade_name: 'Bac 6', base_salary: 25000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];

// ─── Fixed Costs (Finance) ──────────────────────────────
export const DEMO_FIXED_COSTS: FixedCost[] = [
  { id: 'fc-1', category: 'Tien mat bang', amount: 15000000, month: '2026-06', notes: 'Van phong Q1', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-2', category: 'Dien nuoc', amount: 3500000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-3', category: 'Internet', amount: 1200000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-4', category: 'Bao hiem office', amount: 2000000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
];

// ─── Variable Costs (Finance) ───────────────────────────
export const DEMO_VARIABLE_COSTS: VariableCost[] = [
  { id: 'vc-1', category: 'Di lai du an', amount: 5000000, month: '2026-06', notes: 'Xang xe thang 6', created_at: '2026-06-01T00:00:00Z' },
  { id: 'vc-2', category: 'Vun thi cong', amount: 3200000, month: '2026-06', notes: 'Hao hut vat lieu', created_at: '2026-06-01T00:00:00Z' },
];

// ─── Commission Structures (Finance) ────────────────────
export const DEMO_COMMISSION_STRUCTURES: CommissionStructure[] = [
  { id: 'cs-1', department: 'sales', commission_type: 'design_contract', rate: 0.03, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-2', department: 'sales', commission_type: 'construction_contract', rate: 0.02, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-3', department: 'leader', commission_type: 'leader_override', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-4', department: 'design', commission_type: 'design_fee', rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-5', department: 'supervisor', commission_type: 'project_value', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];

