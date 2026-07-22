/**
 * JAMA HOME CRM — Realistic Demo Data (100 leads, HCMC market)
 *
 * CÂU CHUYỆN: JAMA HOME là công ty thiết kế nội thất cao cấp tại TP.HCM,
 * 100 nhân sự, doanh thu ~98 tỷ/tháng, 100+ đơn hàng đang xử lý.
 * Pipeline: 100 leads phân bổ đều qua các giai đoạn, 30+ dự án đang chạy.
 * Thị trường: Nhà phố Q7, Biệt thự Bình Chánh, Căn hộ Vinhomes, Shophouse Q2...
 */

import type {
  User, Team, Lead, Activity, Project, ProjectTask,
  Transaction, AccountingSummary, Commission, PayrollEntry,
  PipelineStats, PipelineKanban, DashboardExecutive, DashboardPersonal,
  Customer, Contract, Quotation, Material, MaterialUsage, AISuggestion,
  SalaryGrade, FixedCost, VariableCost, CommissionStructure,
} from './api';

// ─── Generator helpers ──────────────────────────────────────
const NAMES = ['Nguyễn Văn An', 'Trần Thị Bình', 'Lê Hoàng Chương', 'Phạm Minh Đức', 'Hoàng Thu Em',
  'Vũ Thanh Giang', 'Đặng Văn Hùng', 'Bùi Thị Iris', 'Ngô Cảnh Khoa', 'Mai Phương Linh',
  'Đỗ Quang Minh', 'Lý Thanh Nga', 'Trịnh Văn Oanh', 'Tạ Thị Phượng', 'Đinh Hoàng Quân',
  'Cao Thanh Ruby', 'Lưu Văn Sơn', 'Phan Thị Trang', 'Võ Minh Uyên', 'Bạch Văn Vượng',
  'Chu Thị Xuân', 'Hứa Nam Yến', 'Khúc Văn Zôn', 'Lương Thanh Ái', 'Nguyễn Bình Bảo',
  'Trương Văn Cảnh', 'Đoàn Thị Diệu', 'Giang Minh Đức', 'Hà Thanh Em', 'Khoa Văn Fpt',
  'La Thị Giáng', 'Mạc Văn Hậu', 'Ninh Thanh Irish', 'Ôn Văn Khánh', 'Phùng Thị Lan',
  'Quách Minh Mẫn', 'Sầm Thanh Nhung', 'Tôn Văn Ơn', 'Ung Thị Phượng', 'Vương Văn Quyền',
  'Văn Thanh Ruby', 'Vương Nam Sương', 'Vũ Thanh Tuyền', 'Vương Thanh Uyên', 'Vũ Nam Việt',
  'Vương Thanh Vy', 'Vương Nam Xuân', 'Vương Văn Yến', 'Vương Thanh Zôn', 'Vũ Nam Anh',
  'Bạch Thanh Bảo', 'Bùi Văn Cường', 'Cao Thanh Dung', 'Đặng Nam Em', 'Đỗ Văn Fpt',
  'Đoàn Thanh Giang', 'Giang Văn Hùng', 'Hà Nam Iris', 'Hứa Thanh Khoa', 'Khúc Văn Linh',
  'La Nam Minh', 'Lý Văn Nga', 'Lưu Thanh Oanh', 'Mạc Nam Phượng', 'Mai Văn Quân',
  'Ngô Thanh Ruby', 'Nguyễn Nam Sơn', 'Ôn Văn Trang', 'Phan Thanh Uyên', 'Phùng Nam Vượng',
  'Quách Thanh Xuân', 'Sầm Nam Yến', 'Tạ Văn Zôn', 'Tôn Thanh Anh', 'Trịnh Nam Bảo',
  'Trương Văn Cường', 'Vũ Thanh Dung', 'Vương Nam Em', 'Văn Thanh Fpt', 'Vũ Văn Giang',
];

const DISTRICTS = ['Q1', 'Q2', 'Q3', 'Q7', 'Q9', 'Q10', 'Q12', 'Bình Thạnh', 'Thủ Đức',
  'Gò Vấp', 'Phú Nhuận', 'Tân Bình', 'Bình Tân', 'Nhà Bè', 'Long An', 'Đồng Nai'];

const STREETS = ['Lê Lợi', 'Nguyễn Huệ', 'Võ Văn Tần', 'Điện Biên Phủ', 'Hai Bà Trưng',
  'Nguyễn Đình Chiểu', 'Cách Mạng Tháng 8', 'Lý Tự Trọng', 'Pasteur', 'Ngo Đức Kế',
  'Nguyễn Văn Trỗi', 'Phan Xích Long', 'Hoàng Văn Thụ', 'Lý Chính Thắng', 'Nguyễn Thị Minh Khai'];

function randItem<T>(arr: T[]): T { return arr[Math.floor(Math.random() * arr.length)]; }
function randBetween(min: number, max: number): number { return Math.floor(Math.random() * (max - min + 1)) + min; }
function randDate(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo - Math.floor(Math.random() * 5));
  d.setHours(randBetween(7, 18), randBetween(0, 59), 0, 0);
  return d.toISOString();
}
function genPhone(): string { return `0${randItem([90, 91, 97, 98])}${String(randBetween(10000000, 99999999)).padStart(8, '0')}`; }

// ─── Users (100+ nhân sự) ─────────────────────────────────
export const DEMO_USERS: User[] = [
  { id: 'demo-admin-001', full_name: 'Hồ Minh Tuấn', email: 'admin@jamahome.vn', phone: '0901234567', role: 'admin', department: 'EXEC', team_id: 'demo-team-04', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-leader-001', full_name: 'Lê Văn Leader', email: 'leader@jamahome.vn', phone: '0909876543', role: 'leader', department: 'SALES', team_id: 'demo-team-01', is_active: true, created_at: '2026-01-10T00:00:00Z' },
  { id: 'demo-sales-001', full_name: 'Trần Thị Sales', email: 'sales@jamahome.vn', phone: '0907654321', role: 'data_entry', department: 'SALES', team_id: 'demo-team-01', is_active: true, created_at: '2026-01-15T00:00:00Z' },
  { id: 'demo-sales-002', full_name: 'Nguyễn Văn Bán', email: 'sales2@jamahome.vn', phone: '0908123456', role: 'data_entry', department: 'SALES', team_id: 'demo-team-01', is_active: true, created_at: '2026-02-01T00:00:00Z' },
  { id: 'demo-sales-003', full_name: 'Phạm Thị Chăm', email: 'sales3@jamahome.vn', phone: '0909234567', role: 'data_entry', department: 'SALES', team_id: 'demo-team-02', is_active: true, created_at: '2026-02-15T00:00:00Z' },
  { id: 'demo-acct-001', full_name: 'Phạm Thị Kế Toán', email: 'accountant@jamahome.vn', phone: '0905555666', role: 'accountant', department: 'ACCT', is_active: true, created_at: '2026-01-20T00:00:00Z' },
  { id: 'demo-exec-001', full_name: 'Đỗ Minh Tuấn', email: 'ceo@jamahome.vn', phone: '0901111222', role: 'executive', department: 'EXEC', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-supervisor-001', full_name: 'Nguyễn Văn Giám Sát', email: 'supervisor@jamahome.vn', role: 'supervisor', department: 'OPS', is_active: true, created_at: '2026-02-01T00:00:00Z' },
  { id: 'demo-supervisor-002', full_name: 'Võ Thị Thiết Kế', email: 'designer@jamahome.vn', role: 'supervisor', department: 'DESIGN', is_active: true, created_at: '2026-02-15T00:00:00Z' },
];

export const DEMO_TEAMS: Team[] = [
  { id: 'demo-team-04', name: 'Ban Giám Đốc', code: 'BGD', department: 'EXEC', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-01', name: 'Đội Văn Toàn', code: 'JMH-VT', department: 'SALES', leader_id: 'demo-leader-001', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-02', name: 'Đội Thái Phượng', code: 'JMH-TP', department: 'SALES', created_at: '2026-01-01T00:00:00Z' },
  { id: 'demo-team-03', name: 'Phòng Thiết Kế', code: 'DESIGN-1', department: 'DESIGN', created_at: '2026-01-01T00:00:00Z' },
];

// ─── Helper: Generate realistic leads ──────────────────────
const STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design', 'lost', 'dormant'] as const;
const STAGE_DISTRIBUTION = { new: 15, interested: 20, survey_scheduled: 15, potential: 15, signed_design: 20, lost: 10, dormant: 5 };
const PROPERTIES = ['townhouse', 'apartment', 'villa', 'office', 'shophouse'] as const;
const PROP_WEIGHTS = [0.55, 0.25, 0.10, 0.05, 0.05];
const SOURCES = ['facebook', 'zalo', 'referral', 'website', 'tiktok'] as const;
const SOURCE_WEIGHTS = [0.40, 0.30, 0.15, 0.10, 0.05];
const CHANNELS = ['kenh_a', 'kenh_b', 'kenh_chinh', 'kenh_sale', 'kenh_affiliate'];
const BUDGET_RANGES = { townhouse: [800_000_000, 15_000_000_000], apartment: [300_000_000, 5_000_000_000], villa: [5_000_000_000, 25_000_000_000], office: [500_000_000, 8_000_000_000], shophouse: [1_000_000_000, 10_000_000_000] };
const SALES_IDS = ['demo-sales-001', 'demo-sales-002', 'demo-sales-003'];

function weightedRandom<T>(items: readonly T[], weights: readonly number[]): T {
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i];
    if (r <= 0) return items[i];
  }
  return items[items.length - 1];
}

function generateLead(index: number, stage: string): Lead {
  const name = NAMES[index % NAMES.length];
  const propType = weightedRandom(PROPERTIES, PROP_WEIGHTS);
  const source = weightedRandom(SOURCES, SOURCE_WEIGHTS);
  const district = randItem(DISTRICTS);
  const street = randItem(STREETS);
  const [minBudget, maxBudget] = BUDGET_RANGES[propType];
  const budget = randBetween(minBudget, maxBudget);
  const area = propType === 'apartment' ? randBetween(45, 150) : propType === 'villa' ? randBetween(200, 500) : propType === 'office' ? randBetween(80, 300) : randBetween(60, 250);
  const isLost = stage === 'lost';
  const isDormant = stage === 'dormant';
  const daysAgo = isLost ? randBetween(30, 90) : isDormant ? randBetween(60, 120) : randBetween(1, 45);

  return {
    id: `demo-lead-${String(index + 1).padStart(3, '0')}`,
    name, phone: genPhone(),
    address: `${district}, TP.HCM`,
    needs: `Thiết kế nội thất ${propType === 'villa' ? 'biệt thự' : propType === 'apartment' ? 'căn hộ' : 'nhà phố'} ${randItem(['hiện đại', 'cổ điển', 'tân cổ điển', 'minimal', 'scandinavian'])}`,
    source, channel: randItem(CHANNELS),
    property_type: propType, area_sqm: area, estimated_budget: budget,
    stage, priority: randItem(['low', 'medium', 'high', 'urgent'] as const),
    assigned_to: randItem(SALES_IDS), team_id: 'demo-team-01',
    ai_score: randBetween(20, 98),
    property_class: budget > 10_000_000_000 ? 'luxury' : budget > 3_000_000_000 ? 'mid_range' : 'budget',
    price_per_sqm: Math.round(budget / area), region: district, segment: propType === 'villa' ? 'Biệt thự' : 'Nhà ở',
    plan_type: randItem(['online', 'offline', 'survey', 'none'] as const),
    tags: (Math.random() > 0.7 ? ['VIP'] : []).concat(Math.random() > 0.8 ? ['Deal'] : []),
    deal_value: isLost ? 0 : budget,
    assigned_user_name: SALES_IDS.includes('demo-sales-001') ? 'Trần Thị Sales' : 'Nhân viên Sale',
    team_name: 'Đội Văn Toàn', activity_count: randBetween(0, 15),
    contact_status: isLost ? 'unreachable' : isDormant ? 'no_need' : randItem(['reachable', 'reachable', 'unreachable', 'pending'] as const),
    created_at: randDate(daysAgo + 30), updated_at: randDate(daysAgo),
    last_contacted_at: isLost || isDormant ? undefined : randDate(daysAgo),
  };
}

// Generate 100 leads
let _leadSeed = 42;
function seededRandom(): number { _leadSeed = (_leadSeed * 16807) % 2147483647; return _leadSeed / 2147483647; }
function seededItem<T>(arr: T[]): T { return arr[Math.floor(seededRandom() * arr.length)]; }
function seededBetween(min: number, max: number): number { return Math.floor(seededRandom() * (max - min + 1)) + min; }
function seededDate(daysAgo: number): string { const d = new Date(); d.setDate(d.getDate() - daysAgo - Math.floor(seededRandom() * 5)); d.setHours(seededBetween(7, 18), seededBetween(0, 59), 0, 0); return d.toISOString(); }
function seededPhone(): string { return `0${seededItem([90, 91, 97, 98])}${String(seededBetween(10000000, 99999999)).padStart(8, '0')}`; }
function seededWeighted<T>(items: readonly T[], weights: readonly number[]): T { const total = weights.reduce((a, b) => a + b, 0); let r = seededRandom() * total; for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r <= 0) return items[i]; } return items[items.length - 1]; }

function seededLead(index: number, stage: string): Lead {
  const name = NAMES[index % NAMES.length];
  const propType = seededWeighted(PROPERTIES, PROP_WEIGHTS);
  const source = seededWeighted(SOURCES, SOURCE_WEIGHTS);
  const district = seededItem(DISTRICTS);
  const [minB, maxB] = BUDGET_RANGES[propType];
  const budget = seededBetween(minB, maxB);
  const area = propType === 'apartment' ? seededBetween(45, 150) : propType === 'villa' ? seededBetween(200, 500) : propType === 'office' ? seededBetween(80, 300) : seededBetween(60, 250);
  const isLost = stage === 'lost';
  const isDormant = stage === 'dormant';
  const daysAgo = isLost ? seededBetween(30, 90) : isDormant ? seededBetween(60, 120) : seededBetween(1, 45);

  return {
    id: `demo-lead-${String(index + 1).padStart(3, '0')}`,
    name, phone: seededPhone(), address: `${district}, TP.HCM`,
    needs: `Thiết kế nội thất ${propType === 'villa' ? 'biệt thự' : propType === 'apartment' ? 'căn hộ' : 'nhà phố'} ${seededItem(['hiện đại', 'cổ điển', 'tân cổ điển', 'minimal', 'scandinavian'])}`,
    source, channel: seededItem(CHANNELS), property_type: propType, area_sqm: area, estimated_budget: budget,
    stage, priority: seededItem(['low', 'medium', 'high', 'urgent'] as const),
    assigned_to: seededItem(SALES_IDS), team_id: 'demo-team-01',
    ai_score: seededBetween(20, 98),
    property_class: budget > 10_000_000_000 ? 'luxury' : budget > 3_000_000_000 ? 'mid_range' : 'budget',
    price_per_sqm: Math.round(budget / area), region: district,
    segment: propType === 'villa' ? 'Biệt thự' : 'Nhà ở',
    plan_type: seededItem(['online', 'offline', 'survey', 'none'] as const),
    tags: (seededRandom() > 0.7 ? ['VIP'] : []).concat(seededRandom() > 0.8 ? ['Deal'] : []),
    deal_value: isLost ? 0 : budget,
    assigned_user_name: seededItem(['Trần Thị Sales', 'Nguyễn Văn Bán', 'Phạm Thị Chăm']),
    team_name: seededItem(['Đội Văn Toàn', 'Đội Thái Phượng']),
    activity_count: seededBetween(0, 15),
    contact_status: isLost ? 'unreachable' : isDormant ? 'no_need' : seededItem(['reachable', 'reachable', 'unreachable', 'pending'] as const),
    created_at: seededDate(daysAgo + 30), updated_at: seededDate(daysAgo),
    last_contacted_at: isLost || isDormant ? undefined : seededDate(daysAgo),
  };
}

// Build 100 leads across stages
const _leadBuckets: Lead[] = [];
let _leadIdx = 0;
for (const [stage, count] of Object.entries(STAGE_DISTRIBUTION)) {
  for (let i = 0; i < count; i++) { _leadBuckets.push(seededLead(_leadIdx, stage)); _leadIdx++; }
}

export const DEMO_LEADS: Lead[] = _leadBuckets;

// ─── Projects (30+ from signed_design leads) ──────────────
const PROJECT_STAGES = ['design', 'quotation', 'procurement', 'construction', 'acceptance', 'completed'];
const signedLeads = DEMO_LEADS.filter(l => l.stage === 'signed_design');
export const DEMO_PROJECTS: Project[] = signedLeads.map((lead, i) => ({
  id: `demo-proj-${String(i + 1).padStart(3, '0')}`,
  code: `JMH-${String(2026)}.${String(i + 1).padStart(3, '0')}`,
  name: `Dự án ${lead.name.split(' ')[0]} — ${lead.address}`,
  lead_id: lead.id, customer_id: `demo-cust-${String(i + 1).padStart(3, '0')}`,
  client_name: lead.name, client_phone: lead.phone, address: lead.address,
  project_type: lead.property_type === 'villa' ? 'design_build' : 'design_build',
  status: i < 25 ? 'active' : 'completed',
  stage: seededItem(PROJECT_STAGES),
  total_value: lead.deal_value || 0, spent: Math.round((lead.deal_value || 0) * seededBetween(20, 80) / 100),
  progress: seededBetween(5, 95),
  pm_id: 'demo-supervisor-001', designer_id: 'demo-supervisor-002', sales_id: lead.assigned_to,
  start_date: seededDate(lead.created_at ? 90 : 60),
  target_end_date: seededDate(-30),
  created_at: lead.created_at, updated_at: seededDate(seededBetween(1, 10)),
}));

// ─── Activities (50+) ──────────────────────────────────────
export const DEMO_ACTIVITIES: Activity[] = DEMO_LEADS.slice(0, 30).flatMap((lead, i) => {
  const types: Array<[string, string]> = [
    ['call', `Gọi điện tư vấn cho ${lead.name}`],
    ['note', `Ghi chú: ${lead.needs || 'Khách quan tâm'}`],
    ['meeting', `Họp tư vấn với ${lead.name} tại ${lead.address}`],
    ['survey', `Khảo sát hiện trường ${lead.address}`],
  ];
  return types.slice(0, seededBetween(1, 3)).map(([type, content], j) => ({
    id: `demo-act-${String(i * 4 + j + 1).padStart(4, '0')}`,
    lead_id: lead.id, user_id: lead.assigned_to || 'demo-sales-001',
    type, content, created_at: seededDate(seededBetween(1, 30)),
    user_name: seededItem(['Trần Thị Sales', 'Nguyễn Văn Bán', 'Phạm Thị Chăm']),
  }));
});

// ─── Tasks (200+ across projects) ──────────────────────────
const TASK_TITLES = ['Thiết kế 2D', '3D Demo', '3D Render', 'Bản vẽ kỹ thuật', 'Thiết kế Final',
  'Báo giá 2D', 'Báo giá 3D', 'Báo giá Nội thất', 'Báo giá Final',
  'Chuẩn bị vật liệu', 'Hoàn thành SPECS', 'Đặt hàng',
  'Xin phép thi công', 'Lập tiến độ', 'Thi công thô', 'Thi công nội thất',
  'Bàn giao', 'Nghiệm thu', 'Bảo hành'];

export const DEMO_TASKS: ProjectTask[] = DEMO_PROJECTS.slice(0, 25).flatMap((proj, pi) =>
  TASK_TITLES.map((title, ti) => ({
    id: `demo-task-${String(pi * 19 + ti + 1).padStart(4, '0')}`,
    project_id: proj.id, title, description: `${title} cho ${proj.name}`,
    status: ti < 3 ? 'done' : ti < 8 ? 'in_progress' : 'not_started',
    stage: ti < 5 ? 'design' : ti < 9 ? 'quotation' : ti < 12 ? 'procurement' : ti < 16 ? 'construction' : 'acceptance',
    department: ti < 5 ? 'design' : ti < 9 ? 'quotation' : ti < 12 ? 'procurement' : 'ops',
    order: ti + 1, created_at: proj.created_at,
  }))
);

// ─── Customers ─────────────────────────────────────────────
export const DEMO_CUSTOMERS: Customer[] = DEMO_PROJECTS.slice(0, 20).map((proj, i) => ({
  id: `demo-cust-${String(i + 1).padStart(3, '0')}`,
  name: proj.client_name, phone: proj.client_phone, address: proj.address,
  type: 'individual' as const, notes: `Khách hàng từ lead ${proj.lead_id}`,
  created_at: proj.created_at, updated_at: proj.updated_at,
}));

// ─── Contracts (20+) ──────────────────────────────────────
export const DEMO_CONTRACTS: Contract[] = DEMO_PROJECTS.slice(0, 20).map((proj, i) => ({
  id: `demo-hd-${String(i + 1).padStart(3, '0')}`,
  code: `HD-${proj.code}`, project_id: proj.id, title: `Hợp đồng ${proj.name}`,
  status: proj.status === 'completed' ? 'completed' : 'signed',
  total_value: proj.total_value || 0,
  payment_terms: {
    installments: [
      { name: 'Đợt 1 - Ký hợp đồng', percentage: 25, milestone: 'signed', status: 'paid', amount: Math.round((proj.total_value || 0) * 0.25) },
      { name: 'Đợt 2 - Thi công thô', percentage: 25, milestone: 'construction', status: 'paid', amount: Math.round((proj.total_value || 0) * 0.25) },
      { name: 'Đợt 3 - Hoàn thiện', percentage: 25, milestone: 'completion', status: i < 15 ? 'paid' : 'pending', amount: Math.round((proj.total_value || 0) * 0.25) },
      { name: 'Đợt 4 - Nghiệm thu', percentage: 25, milestone: 'acceptance', status: 'pending', amount: Math.round((proj.total_value || 0) * 0.25) },
    ],
  },
  created_at: proj.created_at, updated_at: proj.updated_at,
}));

// ─── Transactions (50+ across months) ─────────────────────
export const DEMO_TRANSACTIONS: Transaction[] = DEMO_PROJECTS.slice(0, 30).flatMap((proj, i) => [
  { id: `demo-txn-${i * 3 + 1}`, code: `TXN-${String(i * 3 + 1).padStart(4, '0')}`, type: 'income', category: 'design_contract', description: `Thu tiền thiết kế ${proj.name}`, amount: Math.round((proj.total_value || 0) * 0.25), status: 'completed', project_id: proj.id, date: seededDate(30 + i), created_at: seededDate(30 + i) },
  { id: `demo-txn-${i * 3 + 2}`, code: `TXN-${String(i * 3 + 2).padStart(4, '0')}`, type: 'expense', category: 'material', description: `Vật tư thi công ${proj.name}`, amount: Math.round((proj.total_value || 0) * 0.15), status: 'completed', project_id: proj.id, date: seededDate(20 + i), created_at: seededDate(20 + i) },
  { id: `demo-txn-${i * 3 + 3}`, code: `TXN-${String(i * 3 + 3).padStart(4, '0')}`, type: 'expense', category: 'labor', description: `Nhân công ${proj.name}`, amount: Math.round((proj.total_value || 0) * 0.10), status: 'completed', project_id: proj.id, date: seededDate(10 + i), created_at: seededDate(10 + i) },
]);

// ─── Accounting Summary ────────────────────────────────────
const totalIncome = DEMO_TRANSACTIONS.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0);
const totalExpense = DEMO_TRANSACTIONS.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0);
export const DEMO_ACCOUNTING_SUMMARY: AccountingSummary = {
  total_income: totalIncome, total_expense: totalExpense, net: totalIncome - totalExpense,
  by_category: [
    { category: 'design_contract', type: 'income', total: DEMO_TRANSACTIONS.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0), count: DEMO_TRANSACTIONS.filter(t => t.type === 'income').length },
    { category: 'material', type: 'expense', total: DEMO_TRANSACTIONS.filter(t => t.category === 'material').reduce((s, t) => s + t.amount, 0), count: DEMO_TRANSACTIONS.filter(t => t.category === 'material').length },
    { category: 'labor', type: 'expense', total: DEMO_TRANSACTIONS.filter(t => t.category === 'labor').reduce((s, t) => s + t.amount, 0), count: DEMO_TRANSACTIONS.filter(t => t.category === 'labor').length },
  ],
};

// ─── Pipeline Stats ────────────────────────────────────────
const stageCounts: Record<string, number> = {};
DEMO_LEADS.forEach(l => { stageCounts[l.stage] = (stageCounts[l.stage] || 0) + 1; });
const pipelineValue = DEMO_LEADS.filter(l => !['lost', 'dormant', 'signed_design'].includes(l.stage)).reduce((s, l) => s + (l.estimated_budget || 0), 0);
export const DEMO_PIPELINE_STATS: PipelineStats = {
  total_leads: DEMO_LEADS.length, by_stage: stageCounts,
  conversion_rate: ((stageCounts['signed_design'] || 0) / DEMO_LEADS.length * 100),
  pipeline_value: pipelineValue,
  sla_compliance: 87.5, overdue_count: DEMO_LEADS.filter(l => l.contact_status === 'unreachable').length,
  today_count: DEMO_LEADS.filter(l => { const d = new Date(); const ld = new Date(l.last_contacted_at || ''); return ld.toDateString() === d.toDateString(); }).length,
  unassigned_count: DEMO_LEADS.filter(l => !l.assigned_to).length,
};

// ─── Pipeline Kanban ───────────────────────────────────────
export const DEMO_PIPELINE_KANBAN: PipelineKanban[] = [
  { stage: 'new', stage_label: 'Tiếp nhận mới', leads: DEMO_LEADS.filter(l => l.stage === 'new'), count: stageCounts['new'] || 0 },
  { stage: 'interested', stage_label: 'Đang tư vấn', leads: DEMO_LEADS.filter(l => l.stage === 'interested'), count: stageCounts['interested'] || 0 },
  { stage: 'survey_scheduled', stage_label: 'Khảo sát', leads: DEMO_LEADS.filter(l => l.stage === 'survey_scheduled'), count: stageCounts['survey_scheduled'] || 0 },
  { stage: 'potential', stage_label: 'Dự toán & tư vấn', leads: DEMO_LEADS.filter(l => l.stage === 'potential'), count: stageCounts['potential'] || 0 },
  { stage: 'signed_design', stage_label: 'Ký HĐ Thiết kế', leads: DEMO_LEADS.filter(l => l.stage === 'signed_design'), count: stageCounts['signed_design'] || 0 },
];

// ─── Commissions ───────────────────────────────────────────
export const DEMO_COMMISSIONS: Commission[] = DEMO_CONTRACTS.slice(0, 10).map((c, i) => ({
  id: `demo-comm-${String(i + 1).padStart(3, '0')}`,
  user_id: SALES_IDS[i % SALES_IDS.length], user_name: seededItem(['Trần Thị Sales', 'Nguyễn Văn Bán', 'Phạm Thị Chăm']),
  project_id: c.project_id, type: 'design', rate: 0.03,
  base_amount: Math.round((c.total_value || 0) * 0.3),
  commission_amount: Math.round((c.total_value || 0) * 0.03),
  milestone: 'design_signed', status: 'approved', period: '2026-07',
}));

// ─── Payroll ───────────────────────────────────────────────
export const DEMO_PAYROLL: PayrollEntry[] = DEMO_USERS.filter(u => u.role === 'data_entry').map((u, i) => {
  const base = 15_000_000;
  const comm = seededBetween(100_000_000, 400_000_000);
  const bonus = seededBetween(0, 50_000_000);
  const deductions = Math.round(base * 0.11);
  return {
    id: `demo-pay-${String(i + 1).padStart(3, '0')}`,
    user_id: u.id, user_name: u.full_name, period: '2026-07',
    base_salary: base, commission_total: comm, bonus, deductions,
    net_salary: base + comm + bonus - deductions, status: 'pending',
  };
});

// ─── Dashboard Executive ───────────────────────────────────
export const DEMO_DASHBOARD_EXECUTIVE: DashboardExecutive = {
  total_leads: DEMO_LEADS.length,
  total_leads_month: DEMO_LEADS.filter(l => new Date(l.created_at).getMonth() === new Date().getMonth()).length,
  conversion_rate: DEMO_PIPELINE_STATS.conversion_rate,
  pipeline_value: pipelineValue,
  total_contracts: DEMO_CONTRACTS.length,
  total_contract_value: DEMO_CONTRACTS.reduce((s, c) => s + (c.total_value || 0), 0),
  active_projects: DEMO_PROJECTS.filter(p => p.status === 'active').length,
  avg_project_progress: Math.round(DEMO_PROJECTS.reduce((s, p) => s + p.progress, 0) / Math.max(DEMO_PROJECTS.length, 1)),
  sla_compliance: 87.5, overdue_leads: DEMO_LEADS.filter(l => l.contact_status === 'unreachable').length,
  stage_funnel: stageCounts,
  team_performance: [{ team: 'Đội Văn Toàn', total_leads: 40, signed: 8, conversion: 20 }, { team: 'Đội Thái Phượng', total_leads: 35, signed: 7, conversion: 20 }, { team: 'Phòng Thiết Kế', total_leads: 25, signed: 5, conversion: 20 }],
  monthly_trend: [],
  financial_summary: { total_revenue_ytd: 687_400_000_000, total_cost_ytd: 552_400_000_000, net_profit_ytd: 135_000_000_000, roi: 24.5, yoy_growth: 15.2, avg_project_margin: 20.0, cash_flow: 45_000_000_000, outstanding_receivable: 25_000_000_000 },
};

// ─── Dashboard Personal ────────────────────────────────────
export const DEMO_DASHBOARD_PERSONAL: DashboardPersonal = {
  user_name: 'Trần Thị Sales', total_active_leads: 33,
  by_stage: { new: 5, interested: 7, survey_scheduled: 5, potential: 5, signed_design: 8, lost: 3, dormant: 2 },
  overdue_followup: DEMO_LEADS.filter(l => l.assigned_to === 'demo-sales-001' && l.contact_status === 'unreachable').slice(0, 5).map(l => ({ id: l.id, name: l.name, phone: l.phone, stage: l.stage, last_contacted_at: l.last_contacted_at })),
  today_appointments: [], pipeline_value: 35_000_000_000,
  weekly_kpis: { calls: 45, meetings: 8, surveys: 5, new_leads: 12 },
  ai_suggestions: [],
};

// ─── Quotations (15+) ─────────────────────────────────────
export const DEMO_QUOTATIONS: Quotation[] = DEMO_PROJECTS.slice(0, 15).map((proj, i) => ({
  id: `demo-q-${String(i + 1).padStart(3, '0')}`,
  code: `BG-${proj.code}`, type: 'design', title: `Báo giá ${proj.name}`,
  status: i < 10 ? 'approved' : 'draft',
  total_amount: Math.round((proj.total_value || 0) * 0.3),
  tax_amount: Math.round((proj.total_value || 0) * 0.03),
  revision: 1,
  items: { line_items: [] },
  project_id: proj.id, lead_id: proj.lead_id,
  created_at: proj.created_at, updated_at: proj.updated_at,
}));

// ─── Materials ─────────────────────────────────────────────
export const DEMO_MATERIALS: Material[] = [
  { id: 'mat-1', code: 'GOC-001', name: 'Gỗ Óc Chó', category: 'wood', unit: 'm2', unit_price: 2_500_000, quantity_in_stock: 150, min_stock: 30, supplier: 'Nội thất Hòa Phát', created_at: '2026-01-01', updated_at: '2026-07-01' },
  { id: 'mat-2', code: 'GCM-001', name: 'Gỗ Công Nghiệp MFC', category: 'wood', unit: 'm2', unit_price: 450_000, quantity_in_stock: 500, min_stock: 100, supplier: 'An Cường', created_at: '2026-01-01', updated_at: '2026-07-01' },
  { id: 'mat-3', code: 'DA-001', name: 'Đá Marble', category: 'stone', unit: 'm2', unit_price: 3_500_000, quantity_in_stock: 80, min_stock: 20, supplier: 'Đá Hoa Cương Bình Dương', created_at: '2026-01-01', updated_at: '2026-07-01' },
  { id: 'mat-4', code: 'SN-001', name: 'Sơn Dulux', category: 'paint', unit: 'lon', unit_price: 850_000, quantity_in_stock: 200, min_stock: 50, supplier: 'Dulux Việt Nam', created_at: '2026-01-01', updated_at: '2026-07-01' },
  { id: 'mat-5', code: 'KC-001', name: 'Kính cường lực', category: 'glass', unit: 'm2', unit_price: 1_200_000, quantity_in_stock: 100, min_stock: 25, supplier: 'Kính Việt Nhật', created_at: '2026-01-01', updated_at: '2026-07-01' },
];

// ─── P&L Summary ──────────────────────────────────────────
export const DEMO_PNL_SUMMARY = {
  period: '2026-07', total_revenue: totalIncome, total_cost: totalExpense,
  net_profit: totalIncome - totalExpense,
  margin_pct: Math.round((totalIncome - totalExpense) / Math.max(totalIncome, 1) * 100),
  revenue_by_project: DEMO_PROJECTS.slice(0, 10).map(p => ({
    project_id: p.id, project_code: p.code, project_name: p.name,
    revenue: Math.round((p.total_value || 0) * 0.25), cost: Math.round((p.total_value || 0) * 0.15),
    profit: Math.round((p.total_value || 0) * 0.10),
    margin_pct: Math.round(10 / 25 * 100),
  })),
};

// ─── Salary Grades ─────────────────────────────────────────
export const DEMO_SALARY_GRADES: SalaryGrade[] = [
  { id: 'sg-1', grade_name: 'Nhân viên', base_salary: 8_000_000, bhxh_rate: 0.08, bhxh_company_rate: 0.175, bhyt_rate: 0.015, bhtn_rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01' },
  { id: 'sg-2', grade_name: 'Chuyên viên', base_salary: 12_000_000, bhxh_rate: 0.08, bhxh_company_rate: 0.175, bhyt_rate: 0.015, bhtn_rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01' },
  { id: 'sg-3', grade_name: 'Trưởng nhóm', base_salary: 18_000_000, bhxh_rate: 0.08, bhxh_company_rate: 0.175, bhyt_rate: 0.015, bhtn_rate: 0.01, effective_date: '2026-01-01', created_at: '2026-01-01' },
];

// ─── Fixed Costs ───────────────────────────────────────────
export const DEMO_FIXED_COSTS: FixedCost[] = [
  { id: 'fc-1', category: 'Thuê mặt bằng', amount: 45_000_000, month: '2026-07', notes: 'Văn phòng Thanh Đa View', created_at: '2026-07-01' },
  { id: 'fc-2', category: 'Internet & Điện', amount: 8_000_000, month: '2026-07', created_at: '2026-07-01' },
  { id: 'fc-3', category: 'Bảo hiểm', amount: 12_000_000, month: '2026-07', created_at: '2026-07-01' },
];

// ─── Variable Costs ────────────────────────────────────────
export const DEMO_VARIABLE_COSTS: VariableCost[] = [
  { id: 'vc-1', category: 'Hao hụt vật liệu', amount: 25_000_000, month: '2026-07', created_at: '2026-07-01' },
  { id: 'vc-2', category: 'Di chuyển công trình', amount: 15_000_000, month: '2026-07', created_at: '2026-07-01' },
];

// ─── Commission Structures ─────────────────────────────────
export const DEMO_COMMISSION_STRUCTURES: CommissionStructure[] = [
  { id: 'cs-1', department: 'SALES', commission_type: 'percentage', rate: 0.03, effective_date: '2026-01-01', created_at: '2026-01-01' },
  { id: 'cs-2', department: 'SALES', commission_type: 'percentage', rate: 0.02, effective_date: '2026-01-01', created_at: '2026-01-01' },
];

// ─── AI Suggestions ────────────────────────────────────────
export const DEMO_AI_SUGGESTIONS: AISuggestion[] = [
  { action: 'Gọi điện follow-up', reason: 'Khách chưa liên hệ 5 ngày', priority: 'high', message_template: 'Anh/chị ơi, em JAMA HOME muốn hỏi thăm...' },
  { action: 'Gửi báo giá mới', reason: 'Ngân sách thấp hơn đối thủ', priority: 'medium', message_template: 'Em có phương án tối ưu chi phí...' },
];
