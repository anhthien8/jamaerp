/**
 * JAMA HOME CRM — Complete Demo Data
 * Used when backend API is unavailable (demo mode).
 *
 * CÂU CHUYỆN SỐ (giữ nhất quán khi sửa): doanh thu YTD 7 tháng ≈ 687 tỷ (~98 tỷ/tháng),
 * lãi ròng ≈ 135 tỷ (margin ~20%). 9 lead → 3 deal thắng = 3 hợp đồng đang chạy (72 tỷ).
 * Kế toán hiển thị THÁNG hiện tại: thu 98,6 tỷ / chi 79,2 tỷ. Hoa hồng sales 2% thi công +
 * 3% thiết kế → thu nhập sales demo 250-320tr/tháng (mục tiêu: nhân sự thấy phấn khởi).
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

// ─── Leads (9 leads: 3 đã thắng = 3 HĐ, 6 đang mở ≈ 61 tỷ pipeline) ─────────
export const DEMO_LEADS: Lead[] = [
  {
    id: 'demo-lead-001', name: 'Bống (Tô Ngọc Bống)', phone: '0901111222',
    address: 'Long An',
    needs: 'Thiết kế + thi công trọn gói biệt thự, phong cách cao cấp',
    source: 'facebook', property_type: 'townhouse', area_sqm: 349, estimated_budget: 20_000_000_000,
    stage: 'signed_design', priority: 'urgent', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 92,
    property_class: 'luxury', price_per_sqm: 57_000_000, region: 'Long An', segment: 'Biệt thự', plan_type: 'online', tags: ['Deal', 'VIP'], deal_value: 20_000_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 3,
    created_at: '2026-06-06T07:40:31Z', updated_at: '2026-06-25T09:00:00Z', last_contacted_at: '2026-06-24T10:30:00Z',
  },
  {
    id: 'demo-lead-002', name: 'Dung', phone: '0902222333',
    address: 'Long An',
    needs: 'Thiết kế + thi công nhà phố trọn gói, phân khúc hạng sang',
    source: 'facebook', property_type: 'townhouse', area_sqm: 300, estimated_budget: 15_000_000_000,
    stage: 'signed_design', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 85,
    property_class: 'luxury', price_per_sqm: 50_000_000, region: 'Long An', segment: 'Nhà ở', plan_type: 'none', tags: ['Deal'], deal_value: 15_000_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-10T07:40:31Z', updated_at: '2026-06-24T14:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
  {
    id: 'demo-lead-003', name: 'Đức Anh (Phạm Đức Anh)', phone: '0903333444',
    address: 'Khánh Hòa',
    needs: 'Thiết kế + thi công nội thất nhà phố, ngân sách 6 tỷ',
    source: 'google_form', property_type: 'townhouse', area_sqm: 150, estimated_budget: 6_000_000_000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 78,
    property_class: 'mid_range', price_per_sqm: 40_000_000, region: 'Khánh Hòa', segment: 'Nhà phố', plan_type: 'online', tags: ['Deal'], deal_value: 6_000_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-12T07:40:31Z', updated_at: '2026-06-23T11:00:00Z', last_contacted_at: '2026-06-22T09:00:00Z',
  },
  {
    id: 'demo-lead-004', name: 'Cúc (Nguyễn Thị Cúc)', phone: '0904444555',
    address: 'Long An',
    needs: 'Thiết kế + thi công nội thất nhà phố 117m²',
    source: 'google_form', property_type: 'townhouse', area_sqm: 117, estimated_budget: 4_700_000_000,
    stage: 'interested', priority: 'medium', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 72,
    property_class: 'mid_range', price_per_sqm: 40_000_000, region: 'Long An', segment: 'Nhà ở', plan_type: 'online', tags: ['Deal'], deal_value: 4_700_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 1,
    created_at: '2026-06-15T07:40:31Z', updated_at: '2026-06-22T16:00:00Z', last_contacted_at: '2026-06-21T08:00:00Z',
  },
  {
    id: 'demo-lead-005', name: 'Kim Cúc (Lê Thị Kim Cúc)', phone: '0905555666',
    address: 'Q.9, TP.HCM',
    needs: 'Thi công nội thất nhà phố theo bản vẽ có sẵn, phong cách cao cấp',
    source: 'facebook', property_type: 'townhouse', area_sqm: 145, estimated_budget: 8_100_000_000,
    stage: 'signed_design', priority: 'high', assigned_to: 'demo-leader-001', team_id: 'demo-team-01',
    ai_score: 82,
    property_class: 'luxury', price_per_sqm: 56_000_000, region: 'Q.9', segment: 'Nhà ở', plan_type: 'offline', tags: ['Deal', 'Ưu tiên'], deal_value: 8_100_000_000,
    assigned_user_name: 'Lê Văn Leader', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-14T07:40:31Z', updated_at: '2026-06-24T16:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
  {
    id: 'demo-lead-006', name: 'Dung (2)', phone: '0906666777',
    address: 'Long An',
    needs: 'Thiết kế + thi công nội thất nhà phố 140m², hạng sang',
    source: 'google_form', property_type: 'townhouse', area_sqm: 140, estimated_budget: 6_200_000_000,
    stage: 'interested', priority: 'medium', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 75,
    property_class: 'luxury', price_per_sqm: 44_000_000, region: 'Long An', segment: 'Nhà ở', plan_type: 'online', tags: ['Deal'], deal_value: 6_200_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 1,
    created_at: '2026-06-18T07:40:31Z', updated_at: '2026-06-23T10:00:00Z', last_contacted_at: '2026-06-22T09:00:00Z',
  },
  {
    id: 'demo-lead-007', name: 'Trang', phone: '0907777888',
    address: 'Long An',
    needs: 'Thiết kế + thi công trọn gói nhà phố 200m²',
    source: 'facebook', property_type: 'townhouse', area_sqm: 200, estimated_budget: 13_600_000_000,
    stage: 'interested', priority: 'high', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 88,
    property_class: 'luxury', price_per_sqm: 68_000_000, region: 'Long An', segment: 'Nhà ở', plan_type: 'survey', tags: ['Deal', 'VIP'], deal_value: 13_600_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-16T07:40:31Z', updated_at: '2026-06-25T14:00:00Z', last_contacted_at: '2026-06-25T10:00:00Z',
  },
  {
    id: 'demo-lead-008', name: 'Cúc (2)', phone: '0908888999',
    address: 'Long An',
    needs: 'Thiết kế + thi công trọn gói biệt thự 500m², phong cách luxury',
    source: 'facebook', property_type: 'villa', area_sqm: 500, estimated_budget: 27_500_000_000,
    stage: 'survey_scheduled', priority: 'urgent', assigned_to: 'demo-sales-001', team_id: 'demo-team-01',
    ai_score: 95,
    property_class: 'luxury', price_per_sqm: 55_000_000, region: 'Long An', segment: 'Biệt thự', plan_type: 'offline', tags: ['Deal', 'VIP', 'Ưu tiên'], deal_value: 27_500_000_000,
    assigned_user_name: 'Trần Thị Sales', team_name: 'Đội Văn Toàn', activity_count: 3,
    created_at: '2026-06-10T07:40:31Z', updated_at: '2026-06-25T16:00:00Z', last_contacted_at: '2026-06-25T14:00:00Z',
  },
  {
    id: 'demo-lead-009', name: 'Dung (3)', phone: '0909999000',
    address: 'TP.HCM',
    needs: 'Thiết kế + thi công nội thất nhà phố 120m²',
    source: 'referral', property_type: 'townhouse', area_sqm: 120, estimated_budget: 3_400_000_000,
    stage: 'survey_scheduled', priority: 'medium', assigned_to: 'demo-leader-001', team_id: 'demo-team-01',
    ai_score: 70,
    property_class: 'luxury', price_per_sqm: 28_000_000, region: 'TP.HCM', segment: 'Nhà ở', plan_type: 'offline', tags: ['Deal'], deal_value: 3_400_000_000,
    assigned_user_name: 'Lê Văn Leader', team_name: 'Đội Văn Toàn', activity_count: 2,
    created_at: '2026-06-17T07:40:31Z', updated_at: '2026-06-24T10:00:00Z', last_contacted_at: '2026-06-23T08:00:00Z',
  },
];

// ─── Activities (15+) ───────────────────────────────────
export const DEMO_ACTIVITIES: Activity[] = [
  { id: 'demo-act-001', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'note', content: 'KH rất quan tâm phong cách hiện đại tối giản. Ngân sách linh hoạt.', created_at: '2026-05-16T09:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-002', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'call', content: 'Gọi tư vấn gói thiết kế, KH đồng ý hẹn khảo sát.', created_at: '2026-05-21T14:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-003', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'meeting', content: 'Khảo sát biệt thự 349m² Long An. Đo đạc hoàn tất, chụp ảnh hiện trạng.', created_at: '2026-06-02T10:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-004', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'meeting', content: 'Trình bày phương án thiết kế, KH chọn PA2 sửa đổi.', created_at: '2026-06-10T15:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-005', lead_id: 'demo-lead-001', user_id: 'demo-sales-001', type: 'stage_change', content: 'Ký hợp đồng trọn gói 20 tỷ — deal lớn nhất quý!', created_at: '2026-06-15T09:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-006', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'note', content: 'KH VIP, nhà phố lớn. Cần bố trí KTS senior.', created_at: '2026-05-28T10:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-007', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'call', content: 'Trao đổi phong cách Indochine, gửi portfolio biệt thự.', created_at: '2026-06-01T11:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-008', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'meeting', content: 'Khảo sát nhà 300m² Long An. Khuôn viên rộng, 2 tầng + sân vườn.', created_at: '2026-06-08T09:30:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-009', lead_id: 'demo-lead-002', user_id: 'demo-sales-001', type: 'stage_change', content: 'Chốt ký HĐ trọn gói 15 tỷ. KH muốn khởi công trong tháng.', created_at: '2026-06-23T08:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-010', lead_id: 'demo-lead-003', user_id: 'demo-sales-001', type: 'call', content: 'Tư vấn gói thiết kế, KH thích Scandinavian. Ngân sách 6 tỷ.', created_at: '2026-06-13T14:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-011', lead_id: 'demo-lead-003', user_id: 'demo-sales-001', type: 'note', content: 'Đã hẹn khảo sát ngày 22/06.', created_at: '2026-06-20T16:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-012', lead_id: 'demo-lead-004', user_id: 'demo-leader-001', type: 'call', content: 'Được giới thiệu bởi KH cũ. Nhà phố Long An 117m².', created_at: '2026-06-17T10:00:00Z', user_name: 'Lê Văn Leader' },
  { id: 'demo-act-013', lead_id: 'demo-lead-004', user_id: 'demo-leader-001', type: 'note', content: 'Ngân sách tốt (4,7 tỷ), ưu tiên cao.', created_at: '2026-06-21T08:00:00Z', user_name: 'Lê Văn Leader' },
  { id: 'demo-act-014', lead_id: 'demo-lead-005', user_id: 'demo-sales-001', type: 'call', content: 'KH đã có bản vẽ, cần thi công 8,1 tỷ. Gửi báo giá thi công.', created_at: '2026-06-08T11:00:00Z', user_name: 'Trần Thị Sales' },
  { id: 'demo-act-015', lead_id: 'demo-lead-005', user_id: 'demo-sales-001', type: 'stage_change', content: 'KH đồng ý ký — chuyển hồ sơ sang lập HĐ thi công.', created_at: '2026-06-19T10:00:00Z', user_name: 'Trần Thị Sales' },
];

// ─── Projects (5 dự án — tổng giá trị đang chạy ≈ 80,9 tỷ) ──────────────────
export const DEMO_PROJECTS: Project[] = [
  {
    id: 'demo-proj-001', code: 'PRJ-2026-001', name: 'Nhà phố Q7 - Chị Mai',
    lead_id: 'demo-lead-001', client_name: 'Chị Mai', client_phone: '0901234567',
    address: '123 Nguyễn Văn Linh, Q7', project_type: 'design_build', status: 'active', stage: 'construction',
    design_value: 450_000_000, construction_value: 11_550_000_000, total_value: 12_000_000_000,
    spent: 9_000_000_000, progress: 75,
    start_date: '2026-04-26T00:00:00Z', target_end_date: '2026-09-25T00:00:00Z',
    created_at: '2026-04-26T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-002', code: 'PRJ-2026-002', name: 'Biệt thự Bình Chánh - Anh Tuấn',
    lead_id: 'demo-lead-002', client_name: 'Anh Tuấn', client_phone: '0908765432',
    address: 'Biệt thự Vinhomes, Bình Chánh', project_type: 'design_build', status: 'active', stage: 'procurement',
    design_value: 1_800_000_000, construction_value: 43_200_000_000, total_value: 45_000_000_000,
    spent: 13_500_000_000, progress: 30,
    start_date: '2026-05-26T00:00:00Z', target_end_date: '2026-11-22T00:00:00Z',
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-003', code: 'PRJ-2026-003', name: 'Căn hộ Sunrise - Chị Hương',
    lead_id: 'demo-lead-003', client_name: 'Chị Hương', client_phone: '0912345678',
    address: 'Căn hộ Sunrise City, Q7', project_type: 'design_build', status: 'active', stage: 'acceptance',
    design_value: 400_000_000, construction_value: 6_100_000_000, total_value: 6_500_000_000,
    spent: 5_850_000_000, progress: 90,
    start_date: '2026-03-27T00:00:00Z', target_end_date: '2026-07-20T00:00:00Z',
    created_at: '2026-03-27T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'demo-proj-004', code: 'PRJ-2026-004', name: 'Shophouse Q2 - Anh Minh',
    lead_id: 'demo-lead-004', client_name: 'Anh Minh', client_phone: '0987654321',
    address: 'Shophouse Q2', project_type: 'design_only', status: 'paused', stage: 'design',
    design_value: 2_400_000_000, total_value: 2_400_000_000,
    spent: 360_000_000, progress: 15,
    start_date: '2026-06-11T00:00:00Z',
    created_at: '2026-06-11T00:00:00Z', updated_at: '2026-06-20T00:00:00Z',
  },
  {
    id: 'demo-proj-005', code: 'PRJ-2026-005', name: 'Nhà phố Gò Vấp - Chị Lan',
    lead_id: 'demo-lead-005', client_name: 'Chị Lan', client_phone: '0976543210',
    address: 'Nhà phố Gò Vấp', project_type: 'construction_only', status: 'active', stage: 'construction',
    construction_value: 15_000_000_000, total_value: 15_000_000_000,
    spent: 8_250_000_000, progress: 55,
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

// ─── Transactions (tháng hiện tại — khớp DEMO_ACCOUNTING_SUMMARY: thu 98,6 tỷ / chi 79,2 tỷ) ──
export const DEMO_TRANSACTIONS: Transaction[] = [
  { id: 'demo-tx-001', code: 'TX-001', type: 'income', category: 'design_contract', description: 'HĐ Thiết kế Chị Mai (Q7)', amount: 450_000_000, project_id: 'demo-proj-001', status: 'completed', date: '2026-05-16T00:00:00Z', created_at: '2026-05-16T00:00:00Z' },
  { id: 'demo-tx-002', code: 'TX-002', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Mai - đợt 1+2', amount: 6_000_000_000, project_id: 'demo-proj-001', status: 'completed', date: '2026-05-21T00:00:00Z', created_at: '2026-05-21T00:00:00Z' },
  { id: 'demo-tx-003', code: 'TX-003', type: 'income', category: 'design_contract', description: 'HĐ Thiết kế Anh Tuấn (Bình Chánh)', amount: 1_800_000_000, project_id: 'demo-proj-002', status: 'completed', date: '2026-05-28T00:00:00Z', created_at: '2026-05-28T00:00:00Z' },
  { id: 'demo-tx-004', code: 'TX-004', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Anh Tuấn - đợt 1', amount: 11_250_000_000, project_id: 'demo-proj-002', status: 'completed', date: '2026-06-03T00:00:00Z', created_at: '2026-06-03T00:00:00Z' },
  { id: 'demo-tx-005', code: 'TX-005', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Hương (Sunrise)', amount: 6_100_000_000, project_id: 'demo-proj-003', status: 'completed', date: '2026-04-11T00:00:00Z', created_at: '2026-04-11T00:00:00Z' },
  { id: 'demo-tx-006', code: 'TX-006', type: 'income', category: 'construction_contract', description: 'HĐ Thi công Chị Lan - đợt 1+2', amount: 9_000_000_000, project_id: 'demo-proj-005', status: 'completed', date: '2026-05-16T00:00:00Z', created_at: '2026-05-16T00:00:00Z' },
  { id: 'demo-tx-007', code: 'TX-007', type: 'income', category: 'construction_contract', description: 'Villa Thảo Điền - đợt nghiệm thu thô', amount: 18_000_000_000, status: 'completed', date: '2026-06-08T00:00:00Z', created_at: '2026-06-08T00:00:00Z' },
  { id: 'demo-tx-008', code: 'TX-008', type: 'income', category: 'construction_contract', description: 'Biệt thự An Lạc Long An - đợt 2', amount: 15_500_000_000, status: 'completed', date: '2026-06-12T00:00:00Z', created_at: '2026-06-12T00:00:00Z' },
  { id: 'demo-tx-009', code: 'TX-009', type: 'income', category: 'construction_contract', description: 'Penthouse Sky Garden - quyết toán', amount: 12_800_000_000, status: 'completed', date: '2026-06-18T00:00:00Z', created_at: '2026-06-18T00:00:00Z' },
  { id: 'demo-tx-010', code: 'TX-010', type: 'income', category: 'construction_contract', description: 'Villa Riviera Q2 - đợt 3', amount: 10_600_000_000, status: 'completed', date: '2026-06-21T00:00:00Z', created_at: '2026-06-21T00:00:00Z' },
  { id: 'demo-tx-011', code: 'TX-011', type: 'income', category: 'design_contract', description: 'Gói thiết kế các công trình mới (5 HĐ)', amount: 7_100_000_000, status: 'completed', date: '2026-06-24T00:00:00Z', created_at: '2026-06-24T00:00:00Z' },
  { id: 'demo-tx-012', code: 'TX-012', type: 'expense', category: 'material', description: 'Vật liệu các công trình - kỳ T6', amount: 38_000_000_000, status: 'completed', date: '2026-06-15T00:00:00Z', created_at: '2026-06-15T00:00:00Z' },
  { id: 'demo-tx-013', code: 'TX-013', type: 'expense', category: 'labor', description: 'Nhân công + thầu phụ - kỳ T6', amount: 34_650_000_000, status: 'completed', date: '2026-06-20T00:00:00Z', created_at: '2026-06-20T00:00:00Z' },
  { id: 'demo-tx-014', code: 'TX-014', type: 'expense', category: 'salary', description: 'Lương văn phòng + đội ngũ T6 (100 nhân sự)', amount: 4_600_000_000, status: 'completed', date: '2026-06-25T00:00:00Z', created_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-tx-015', code: 'TX-015', type: 'expense', category: 'commission', description: 'Hoa hồng T6 - đội Sales', amount: 1_950_000_000, status: 'pending', date: '2026-06-27T00:00:00Z', created_at: '2026-06-27T00:00:00Z' },
];

// ─── Accounting Summary (tháng hiện tại ≈ doanh thu 98,6 tỷ) ─────────────────
export const DEMO_ACCOUNTING_SUMMARY: AccountingSummary = {
  total_income: 98_600_000_000,
  total_expense: 79_200_000_000,
  net: 19_400_000_000,
  by_category: [
    { category: 'design_contract', type: 'income', total: 9_350_000_000, count: 3 },
    { category: 'construction_contract', type: 'income', total: 89_250_000_000, count: 8 },
    { category: 'material', type: 'expense', total: 38_000_000_000, count: 1 },
    { category: 'labor', type: 'expense', total: 34_650_000_000, count: 1 },
    { category: 'salary', type: 'expense', total: 4_600_000_000, count: 1 },
    { category: 'commission', type: 'expense', total: 1_950_000_000, count: 1 },
  ],
};

// ─── Commissions (hoa hồng "phấn khởi": sales 2% thi công + 3% thiết kế) ─────
export const DEMO_COMMISSIONS: Commission[] = [
  { id: 'demo-comm-001', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-001', type: 'design_commission', rate: 0.03, base_amount: 450_000_000, commission_amount: 13_500_000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-002', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-001', type: 'construction_commission', rate: 0.02, base_amount: 11_550_000_000, commission_amount: 231_000_000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-003', user_id: 'demo-leader-001', user_name: 'Lê Văn Leader', project_id: 'demo-proj-001', type: 'leader_override', rate: 0.005, base_amount: 12_000_000_000, commission_amount: 60_000_000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-004', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-002', type: 'design_commission', rate: 0.03, base_amount: 1_800_000_000, commission_amount: 54_000_000, milestone: 'signing', status: 'approved', period: '2026-06' },
  { id: 'demo-comm-005', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', project_id: 'demo-proj-002', type: 'construction_commission', rate: 0.02, base_amount: 43_200_000_000, commission_amount: 864_000_000, milestone: 'rough_complete', status: 'pending', period: '2026-07' },
  { id: 'demo-comm-006', user_id: 'demo-leader-001', user_name: 'Lê Văn Leader', project_id: 'demo-proj-002', type: 'leader_override', rate: 0.005, base_amount: 45_000_000_000, commission_amount: 225_000_000, milestone: 'signing', status: 'pending', period: '2026-07' },
];

// ─── Payroll (thu nhập demo hấp dẫn: sales ~253tr nhờ hoa hồng) ──────────────
export const DEMO_PAYROLL: PayrollEntry[] = [
  { id: 'demo-pay-001', user_id: 'demo-admin-001', user_name: 'Hồ Minh Tuấn', period: '2026-06', base_salary: 45_000_000, commission_total: 0, bonus: 10_000_000, deductions: 5_200_000, net_salary: 49_800_000, status: 'approved' },
  { id: 'demo-pay-002', user_id: 'demo-leader-001', user_name: 'Lê Văn Leader', period: '2026-06', base_salary: 25_000_000, commission_total: 285_000_000, bonus: 10_000_000, deductions: 8_000_000, net_salary: 312_000_000, status: 'approved' },
  { id: 'demo-pay-003', user_id: 'demo-sales-001', user_name: 'Trần Thị Sales', period: '2026-06', base_salary: 10_000_000, commission_total: 244_500_000, bonus: 5_000_000, deductions: 6_500_000, net_salary: 253_000_000, status: 'approved' },
];

// ─── Pipeline Stats (9 lead: 3 thắng, 6 mở ≈ 61,4 tỷ pipeline) ───────────────
export const DEMO_PIPELINE_STATS: PipelineStats = {
  total_leads: 9,
  by_stage: { new: 0, interested: 4, survey_scheduled: 2, potential: 0, signed_design: 3 },
  conversion_rate: 33.3,
  pipeline_value: 61_400_000_000,
  sla_compliance: 85.7,
  overdue_count: 2,
  today_count: 1,
  unassigned_count: 0,
};

// ─── Pipeline Kanban ─────────────────────────────────────
export const DEMO_PIPELINE_KANBAN: PipelineKanban[] = [
  { stage: 'new', stage_label: 'Tiếp nhận mới', leads: DEMO_LEADS.filter(l => l.stage === 'new'), count: 0 },
  { stage: 'interested', stage_label: 'Đang tư vấn', leads: DEMO_LEADS.filter(l => l.stage === 'interested'), count: 4 },
  { stage: 'survey_scheduled', stage_label: 'Đang chờ', leads: DEMO_LEADS.filter(l => l.stage === 'survey_scheduled'), count: 2 },
  { stage: 'potential', stage_label: 'Đã chốt hồ sơ', leads: DEMO_LEADS.filter(l => l.stage === 'potential'), count: 0 },
  { stage: 'signed_design', stage_label: 'Deal đã thắng', leads: DEMO_LEADS.filter(l => l.stage === 'signed_design'), count: 3 },
];

// ─── Dashboard Executive (khớp P&L YTD 687,4 tỷ ≈ 98 tỷ/tháng) ───────────────
export const DEMO_DASHBOARD_EXECUTIVE: DashboardExecutive = {
  total_leads: 9,
  total_leads_month: 9,
  conversion_rate: 33.3,
  pipeline_value: 61_400_000_000,
  total_contracts: 3,
  total_contract_value: 72_000_000_000,
  active_projects: 4,
  avg_project_progress: 53,
  sla_compliance: 85.7,
  overdue_leads: 2,
  team_performance: [
    { team: 'Đội Văn Toàn', total_leads: 9, signed: 3, conversion: 33.3 },
    { team: 'Đội Thái Phượng', total_leads: 0, signed: 0, conversion: 0 },
    { team: 'Phòng Thiết Kế', total_leads: 0, signed: 0, conversion: 0 },
    { team: 'Ban Giám Đốc', total_leads: 0, signed: 0, conversion: 0 },
  ],
  stage_funnel: { new: 0, interested: 4, survey_scheduled: 2, potential: 0, signed_design: 3, lost: 0, dormant: 0 },
  monthly_trend: [],
  financial_summary: {
    total_revenue_ytd: 687_400_000_000,
    total_cost_ytd: 552_400_000_000,
    net_profit_ytd: 135_000_000_000,
    roi: 24.4,
    yoy_growth: 38.5,
    avg_project_margin: 19.6,
    cash_flow: 92_000_000_000,
    outstanding_receivable: 45_750_000_000,
  },
  forecast: {
    q3_2026: 310_000_000_000,
    q4_2026: 345_000_000_000,
    full_year_2026: 1_180_000_000_000,
    full_year_2025: 820_000_000_000,
  },
  growth_metrics: {
    lead_growth_rate: 15.2,
    conversion_improvement: 3.8,
    avg_deal_size: 14_500_000_000,
    customer_acquisition_cost: 45_000_000,
    customer_lifetime_value: 28_000_000_000,
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

// ─── Dashboard Personal (sales: 5 lead mở = leads 003/004/006/007/008) ───────
export const DEMO_DASHBOARD_PERSONAL: DashboardPersonal = {
  user_name: 'Trần Thị Sales',
  total_active_leads: 5,
  by_stage: { new: 0, interested: 4, survey_scheduled: 1, potential: 0, signed_design: 0 },
  overdue_followup: [
    { lead_name: 'Anh Phong', phone: '0965432109', days: 2 },
  ],
  today_appointments: [
    { lead_name: 'Chị Hương', time: '10:00', type: 'Khảo sát căn hộ' },
  ],
  weekly_kpis: { calls: 12, meetings: 3, new_leads: 1 },
  pipeline_value: 58_000_000_000,
  commission_month: 244_500_000,
  ai_suggestions: [
    { action: 'Follow up Cúc (2) — deal 27,5 tỷ', reason: 'Biệt thự 500m² Long An, đang chờ chốt lịch khảo sát', priority: 'high' },
    { action: 'Hẹn khảo sát Trang — deal 13,6 tỷ', reason: 'Trọn gói nhà phố 200m², cần chốt lịch onsite', priority: 'urgent' },
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

// ─── Contracts (3 HĐ = 72 tỷ; phải thu còn 45,75 tỷ) ─────────────────────────
export const DEMO_CONTRACTS: Contract[] = [
  {
    id: 'demo-ct-001', code: 'HD-2026-001', project_id: 'demo-proj-001',
    title: 'HĐ Thiết kế + Thi công Nhà phố Q7 - Chị Mai',
    status: 'signed', total_value: 12_000_000_000, signed_date: '2026-05-11', working_days: 120, start_date: '2026-04-26',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 25, milestone: 'signing', status: 'paid', amount: 3_000_000_000, paid_date: '2026-05-11' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 25, milestone: 'rough_complete', status: 'paid', amount: 3_000_000_000, paid_date: '2026-06-06' },
      { name: 'Đợt 3 (Nội thất)', percentage: 25, milestone: 'interior_complete', status: 'pending', amount: 3_000_000_000 },
      { name: 'Đợt 4 (Bàn giao)', percentage: 25, milestone: 'handover', status: 'pending', amount: 3_000_000_000 },
    ]},
    created_at: '2026-04-26T00:00:00Z', updated_at: '2026-06-06T00:00:00Z',
  },
  {
    id: 'demo-ct-002', code: 'HD-2026-002', project_id: 'demo-proj-002',
    title: 'HĐ Thiết kế + Thi công Biệt thự Bình Chánh - Anh Tuấn',
    status: 'signed', total_value: 45_000_000_000, signed_date: '2026-05-28', working_days: 180, start_date: '2026-05-26',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 25, milestone: 'signing', status: 'paid', amount: 11_250_000_000, paid_date: '2026-05-28' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 25, milestone: 'rough_complete', status: 'pending', amount: 11_250_000_000 },
      { name: 'Đợt 3 (Nội thất)', percentage: 25, milestone: 'interior_complete', status: 'pending', amount: 11_250_000_000 },
      { name: 'Đợt 4 (Bàn giao)', percentage: 25, milestone: 'handover', status: 'pending', amount: 11_250_000_000 },
    ]},
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-05-28T00:00:00Z',
  },
  {
    id: 'demo-ct-003', code: 'HD-2026-003', project_id: 'demo-proj-005',
    title: 'HĐ Thi công Nhà phố Gò Vấp - Chị Lan',
    status: 'signed', total_value: 15_000_000_000, signed_date: '2026-05-11', working_days: 90, start_date: '2026-05-11',
    payment_terms: { installments: [
      { name: 'Đợt 1 (Đặt cọc)', percentage: 30, milestone: 'signing', status: 'paid', amount: 4_500_000_000, paid_date: '2026-05-11' },
      { name: 'Đợt 2 (Nghiệm thu thô)', percentage: 30, milestone: 'rough_complete', status: 'paid', amount: 4_500_000_000, paid_date: '2026-06-10' },
      { name: 'Đợt 3 (Bàn giao)', percentage: 40, milestone: 'handover', status: 'pending', amount: 6_000_000_000 },
    ]},
    created_at: '2026-05-11T00:00:00Z', updated_at: '2026-06-10T00:00:00Z',
  },
];

// ─── Quotations (4) ──────────────────────────────────────
export const DEMO_QUOTATIONS: Quotation[] = [
  {
    id: 'demo-q-001', code: 'BG-2026-001', type: 'design', project_id: 'demo-proj-001', lead_id: 'demo-lead-001',
    title: 'Báo giá thiết kế nội thất nhà phố Q7 - Chị Mai',
    status: 'approved', total_amount: 450_000_000, tax_amount: 45_000_000, revision: 2,
    items: { line_items: [
      { name: 'Thiết kế phòng khách', unit: 'gói', quantity: 1, unit_price: 150_000_000, total: 150_000_000 },
      { name: 'Thiết kế phòng ngủ master', unit: 'gói', quantity: 1, unit_price: 120_000_000, total: 120_000_000 },
      { name: 'Thiết kế bếp + phòng ăn', unit: 'gói', quantity: 1, unit_price: 100_000_000, total: 100_000_000 },
      { name: 'Thiết kế phòng tắm (x2)', unit: 'gói', quantity: 2, unit_price: 40_000_000, total: 80_000_000 },
    ]},
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-05T00:00:00Z',
  },
  {
    id: 'demo-q-002', code: 'BG-2026-002', type: 'construction', project_id: 'demo-proj-001', lead_id: 'demo-lead-001',
    title: 'Báo giá thi công nội thất nhà phố Q7 - Chị Mai',
    status: 'approved', total_amount: 11_550_000_000, tax_amount: 1_155_000_000, revision: 1,
    items: { line_items: [
      { name: 'Thi công trần thạch cao', unit: 'm2', quantity: 320, unit_price: 550_000, total: 176_000_000 },
      { name: 'Hệ tủ bếp cao cấp nhập khẩu', unit: 'bộ', quantity: 1, unit_price: 1_850_000_000, total: 1_850_000_000 },
      { name: 'Sàn gỗ tự nhiên Óc Chó', unit: 'm2', quantity: 350, unit_price: 2_800_000, total: 980_000_000 },
      { name: 'Nội thất phòng khách + thang', unit: 'gói', quantity: 1, unit_price: 3_650_000_000, total: 3_650_000_000 },
      { name: 'Nội thất 4 phòng ngủ', unit: 'gói', quantity: 1, unit_price: 4_894_000_000, total: 4_894_000_000 },
    ]},
    created_at: '2026-05-05T00:00:00Z', updated_at: '2026-05-05T00:00:00Z',
  },
  {
    id: 'demo-q-003', code: 'BG-2026-003', type: 'design', project_id: 'demo-proj-002', lead_id: 'demo-lead-002',
    title: 'Báo giá thiết kế biệt thự Indochine - Anh Tuấn',
    status: 'approved', total_amount: 1_800_000_000, tax_amount: 180_000_000, revision: 1,
    items: { line_items: [
      { name: 'Thiết kế kiến trúc mặt ngoài', unit: 'gói', quantity: 1, unit_price: 550_000_000, total: 550_000_000 },
      { name: 'Thiết kế nội thất tầng 1', unit: 'gói', quantity: 1, unit_price: 650_000_000, total: 650_000_000 },
      { name: 'Thiết kế nội thất tầng 2', unit: 'gói', quantity: 1, unit_price: 450_000_000, total: 450_000_000 },
      { name: 'Thiết kế sân vườn', unit: 'gói', quantity: 1, unit_price: 150_000_000, total: 150_000_000 },
    ]},
    created_at: '2026-05-26T00:00:00Z', updated_at: '2026-05-26T00:00:00Z',
  },
  {
    id: 'demo-q-004', code: 'BG-2026-004', type: 'construction', project_id: 'demo-proj-005', lead_id: 'demo-lead-005',
    title: 'Báo giá thi công nhà phố Gò Vấp - Chị Lan',
    status: 'sent', total_amount: 15_000_000_000, tax_amount: 1_500_000_000, revision: 1,
    items: { line_items: [
      { name: 'Thi công phần thô', unit: 'gói', quantity: 1, unit_price: 6_200_000_000, total: 6_200_000_000 },
      { name: 'Nội thất toàn bộ', unit: 'gói', quantity: 1, unit_price: 7_000_000_000, total: 7_000_000_000 },
      { name: 'Hệ thống điện + nước thông minh', unit: 'gói', quantity: 1, unit_price: 1_800_000_000, total: 1_800_000_000 },
    ]},
    created_at: '2026-06-08T00:00:00Z', updated_at: '2026-06-10T00:00:00Z',
  },
];

// ─── Materials (10) ──────────────────────────────────────
export const DEMO_MATERIALS: Material[] = [
  { id: 'demo-mat-001', code: 'VT-001', name: 'Gỗ công nghiệp MDF lõi xanh', category: 'wood', unit: 'tấm', unit_price: 350000, quantity_in_stock: 1200, min_stock: 200, supplier: 'Công ty An Cường', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-002', code: 'VT-002', name: 'Sàn gỗ Egger 12mm', category: 'wood', unit: 'm2', unit_price: 650000, quantity_in_stock: 850, min_stock: 500, supplier: 'Egger Việt Nam', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-003', code: 'VT-003', name: 'Đá granite đen Ấn Độ', category: 'stone', unit: 'm2', unit_price: 1200000, quantity_in_stock: 450, min_stock: 150, supplier: 'Đá Hoàng Gia', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-004', code: 'VT-004', name: 'Sơn Dulux nội thất cao cấp', category: 'paint', unit: 'thùng', unit_price: 890000, quantity_in_stock: 300, min_stock: 100, supplier: 'AkzoNobel', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-005', code: 'VT-005', name: 'Inox 304 ống vuông 40x40', category: 'metal', unit: 'cây', unit_price: 285000, quantity_in_stock: 600, min_stock: 200, supplier: 'Inox Đại Dương', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-006', code: 'VT-006', name: 'Kính cường lực 10mm', category: 'glass', unit: 'm2', unit_price: 480000, quantity_in_stock: 350, min_stock: 100, supplier: 'Kính Hưng Thịnh', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-007', code: 'VT-007', name: 'Đèn LED panel 600x600', category: 'electrical', unit: 'cái', unit_price: 320000, quantity_in_stock: 80, min_stock: 150, supplier: 'Rạng Đông', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-008', code: 'VT-008', name: 'Vải sofa nhập Bỉ', category: 'fabric', unit: 'm', unit_price: 950000, quantity_in_stock: 400, min_stock: 100, supplier: 'Vải Hoàng Hà', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-009', code: 'VT-009', name: 'Ống PPR nóng 25mm', category: 'plumbing', unit: 'cây', unit_price: 125000, quantity_in_stock: 1000, min_stock: 300, supplier: 'Vesbo', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
  { id: 'demo-mat-010', code: 'VT-010', name: 'Bản lề giảm chấn Blum', category: 'furniture', unit: 'cái', unit_price: 85000, quantity_in_stock: 2000, min_stock: 500, supplier: 'Blum Việt Nam', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z' },
];

// ─── Material Usages (6) ─────────────────────────────────
export const DEMO_MATERIAL_USAGES: MaterialUsage[] = [
  { id: 'demo-mu-001', material_id: 'demo-mat-001', project_id: 'demo-proj-001', quantity: 250, created_at: '2026-05-26T00:00:00Z', material_name: 'Gỗ MDF lõi xanh', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-002', material_id: 'demo-mat-002', project_id: 'demo-proj-001', quantity: 350, created_at: '2026-06-01T00:00:00Z', material_name: 'Sàn gỗ Egger 12mm', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-003', material_id: 'demo-mat-004', project_id: 'demo-proj-001', quantity: 80, created_at: '2026-06-06T00:00:00Z', material_name: 'Sơn Dulux nội thất', project_name: 'Nhà phố Q7 - Chị Mai' },
  { id: 'demo-mu-004', material_id: 'demo-mat-003', project_id: 'demo-proj-002', quantity: 150, created_at: '2026-06-10T00:00:00Z', material_name: 'Đá granite đen', project_name: 'Biệt thự Bình Chánh - Anh Tuấn' },
  { id: 'demo-mu-005', material_id: 'demo-mat-005', project_id: 'demo-proj-002', quantity: 200, created_at: '2026-06-15T00:00:00Z', material_name: 'Inox 304 ống vuông', project_name: 'Biệt thự Bình Chánh - Anh Tuấn' },
  { id: 'demo-mu-006', material_id: 'demo-mat-010', project_id: 'demo-proj-003', quantity: 240, created_at: '2026-06-17T00:00:00Z', material_name: 'Bản lề giảm chấn Blum', project_name: 'Căn hộ Sunrise - Chị Hương' },
];

// ─── AI Suggestions ──────────────────────────────────────
export const DEMO_AI_SUGGESTIONS: AISuggestion[] = [
  { action: 'Follow up Cúc (2) ngay — deal 27,5 tỷ', reason: 'Lead VIP biệt thự 500m² Long An, luxury trọn gói, đang chờ chốt lịch khảo sát', priority: 'urgent', message_template: 'Chào chị Cúc, JAMA HOME đã chuẩn bị phương án thiết kế cho biệt thự 500m². Chị có lịch khảo sát nào thuận tiện ạ?' },
  { action: 'Chốt khảo sát với Trang — deal 13,6 tỷ', reason: 'Trọn gói nhà phố 200m², cần hẹn lịch khảo sát onsite Long An', priority: 'high', message_template: 'Chào chị Trang, JAMA HOME muốn hẹn lịch khảo sát trực tiếp nhà phố 200m². Cuối tuần này chị có rảnh không ạ?' },
  { action: 'Tư vấn thêm cho Đức Anh (6 tỷ)', reason: 'Đang tư vấn online, KH thích Scandinavian, ngân sách rõ ràng', priority: 'high', message_template: 'Chào anh Đức Anh, JAMA HOME đã có phương án thiết kế Scandinavian cho nhà phố 150m². Anh muốn xem bản demo không ạ?' },
];

// ─── P&L Summary (YTD 7 tháng: 687,4 tỷ doanh thu ≈ 98 tỷ/tháng, lãi 135 tỷ) ──
export const DEMO_PNL_SUMMARY = {
  total_revenue: 687_400_000_000,
  total_costs: 552_400_000_000,
  net_profit: 135_000_000_000,
  margin_pct: 19.6,
  revenue_by_project: [
    { project_id: 'proj-001', project_code: 'JMH-0601', project_name: 'Biệt thự An Lạc - Long An', revenue: 67_000_000_000, costs: 52_300_000_000, profit: 14_700_000_000, margin_pct: 21.9, status: 'active' },
    { project_id: 'proj-002', project_code: 'JMH-0608', project_name: 'Villa Thảo Điền - Quận 2', revenue: 74_000_000_000, costs: 59_200_000_000, profit: 14_800_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-003', project_code: 'JMH-0593', project_name: 'Penthouse Sky Garden - Quận 7', revenue: 58_000_000_000, costs: 45_200_000_000, profit: 12_800_000_000, margin_pct: 22.1, status: 'completed' },
    { project_id: 'proj-004', project_code: 'JMH-0612', project_name: 'Biệt thự Phú Mỹ Hưng - Quận 7', revenue: 53_000_000_000, costs: 42_400_000_000, profit: 10_600_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-005', project_code: 'JMH-0618', project_name: 'Villa Riviera - Quận 2', revenue: 63_000_000_000, costs: 48_800_000_000, profit: 14_200_000_000, margin_pct: 22.5, status: 'active' },
    { project_id: 'proj-006', project_code: 'JMH-0587', project_name: 'Nhà phố Sunrise - Quận 7', revenue: 40_000_000_000, costs: 32_000_000_000, profit: 8_000_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-007', project_code: 'JMH-0595', project_name: 'Căn hộ Penthouse - Thủ Đức', revenue: 32_000_000_000, costs: 25_000_000_000, profit: 7_000_000_000, margin_pct: 21.9, status: 'completed' },
    { project_id: 'proj-008', project_code: 'JMH-0610', project_name: 'Villa The Manor - Bình Chánh', revenue: 30_500_000_000, costs: 24_400_000_000, profit: 6_100_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-009', project_code: 'JMH-0622', project_name: 'Nhà phố Lakeview - Quận 9', revenue: 24_500_000_000, costs: 19_600_000_000, profit: 4_900_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-010', project_code: 'JMH-0578', project_name: 'Căn hộ Vinhomes Central Park', revenue: 37_000_000_000, costs: 29_600_000_000, profit: 7_400_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-011', project_code: 'JMH-0603', project_name: 'Duplex Masteri Thảo Điền', revenue: 23_000_000_000, costs: 18_400_000_000, profit: 4_600_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-012', project_code: 'JMH-0585', project_name: 'Nhà phố Mega Village - Quận 9', revenue: 19_500_000_000, costs: 15_600_000_000, profit: 3_900_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-013', project_code: 'JMH-0625', project_name: 'Căn hộ Diamond Island - Quận 2', revenue: 28_000_000_000, costs: 22_400_000_000, profit: 5_600_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-014', project_code: 'JMH-0575', project_name: 'Căn hộ The Sun Avenue - Quận 2', revenue: 14_200_000_000, costs: 11_400_000_000, profit: 2_800_000_000, margin_pct: 19.7, status: 'completed' },
    { project_id: 'proj-015', project_code: 'JMH-0582', project_name: 'Studio Gateway Thảo Điền', revenue: 8_300_000_000, costs: 6_700_000_000, profit: 1_600_000_000, margin_pct: 19.3, status: 'completed' },
    { project_id: 'proj-016', project_code: 'JMH-0598', project_name: 'Căn hộ Saigon Pearl - Bình Thạnh', revenue: 12_400_000_000, costs: 9_900_000_000, profit: 2_500_000_000, margin_pct: 20.2, status: 'active' },
    { project_id: 'proj-017', project_code: 'JMH-0614', project_name: 'Nhà phố Bình Thạnh - Chị Hương', revenue: 11_700_000_000, costs: 9_400_000_000, profit: 2_300_000_000, margin_pct: 19.7, status: 'completed' },
    { project_id: 'proj-018', project_code: 'JMH-0628', project_name: 'Văn phòng Quận 1 - Interior', revenue: 9_900_000_000, costs: 7_900_000_000, profit: 2_000_000_000, margin_pct: 20.2, status: 'active' },
    { project_id: 'proj-019', project_code: 'JMH-0632', project_name: 'Căn hộ Estella Heights - Quận 2', revenue: 16_000_000_000, costs: 12_900_000_000, profit: 3_100_000_000, margin_pct: 19.4, status: 'active' },
    { project_id: 'proj-020', project_code: 'JMH-0572', project_name: 'Sửa chữa VP Tân Bình', revenue: 6_500_000_000, costs: 5_200_000_000, profit: 1_300_000_000, margin_pct: 20.0, status: 'completed' },
    { project_id: 'proj-021', project_code: 'JMH-0635', project_name: 'Căn hộ Midtown Phú Mỹ Hưng', revenue: 12_400_000_000, costs: 9_900_000_000, profit: 2_500_000_000, margin_pct: 20.2, status: 'active' },
    { project_id: 'proj-022', project_code: 'JMH-0640', project_name: 'Nhà phố Gò Vấp - Chị Lan', revenue: 9_000_000_000, costs: 7_200_000_000, profit: 1_800_000_000, margin_pct: 20.0, status: 'active' },
    { project_id: 'proj-023', project_code: 'JMH-0616', project_name: 'Căn hộ Masteri An Phú', revenue: 13_400_000_000, costs: 10_800_000_000, profit: 2_600_000_000, margin_pct: 19.4, status: 'active' },
    { project_id: 'proj-024', project_code: 'JMH-0615', project_name: 'Shophouse Bến Thành - Quận 1', revenue: 16_900_000_000, costs: 17_900_000_000, profit: -1_000_000_000, margin_pct: -5.9, status: 'at_risk' },
    { project_id: 'proj-025', project_code: 'JMH-0630', project_name: 'Căn hộ Quận 8 - Renovation', revenue: 7_200_000_000, costs: 8_300_000_000, profit: -1_100_000_000, margin_pct: -15.3, status: 'at_risk' },
  ],
};

// ─── Salary Grades (Finance) ────────────────────────────
export const DEMO_SALARY_GRADES: SalaryGrade[] = [
  { id: 'sg-1', grade_name: 'Bậc 1', base_salary: 8000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-2', grade_name: 'Bậc 2', base_salary: 10000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-3', grade_name: 'Bậc 3', base_salary: 12000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-4', grade_name: 'Bậc 4', base_salary: 15000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-5', grade_name: 'Bậc 5', base_salary: 20000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'sg-6', grade_name: 'Bậc 6', base_salary: 25000000, bhxh_rate: 10.5, bhxh_company_rate: 21.5, bhyt_rate: 1.5, bhtn_rate: 1.0, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];

// ─── Fixed Costs (Finance) ──────────────────────────────
export const DEMO_FIXED_COSTS: FixedCost[] = [
  { id: 'fc-1', category: 'Tiền mặt bằng', amount: 180_000_000, month: '2026-06', notes: 'Văn phòng Q1 + xưởng Bình Chánh', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-2', category: 'Điện nước', amount: 42_000_000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-3', category: 'Internet + phần mềm', amount: 8_000_000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
  { id: 'fc-4', category: 'Bảo hiểm văn phòng', amount: 25_000_000, month: '2026-06', created_at: '2026-06-01T00:00:00Z' },
];

// ─── Variable Costs (Finance) ───────────────────────────
export const DEMO_VARIABLE_COSTS: VariableCost[] = [
  { id: 'vc-1', category: 'Đi lại dự án', amount: 65_000_000, month: '2026-06', notes: 'Xăng xe + công tác tháng 6', created_at: '2026-06-01T00:00:00Z' },
  { id: 'vc-2', category: 'Hao hụt thi công', amount: 38_000_000, month: '2026-06', notes: 'Hao hụt vật liệu', created_at: '2026-06-01T00:00:00Z' },
];

// ─── Commission Structures (Finance) ────────────────────
export const DEMO_COMMISSION_STRUCTURES: CommissionStructure[] = [
  { id: 'cs-1', department: 'sales', commission_type: 'design_contract', rate: 0.03, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-2', department: 'sales', commission_type: 'construction_contract', rate: 0.02, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-3', department: 'leader', commission_type: 'leader_override', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-4', department: 'design', commission_type: 'design_fee', rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
  { id: 'cs-5', department: 'supervisor', commission_type: 'project_value', rate: 0.005, effective_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z' },
];
