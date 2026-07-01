/**
 * API client — communicate with FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/** Check if running in demo mode */
function isDemoMode(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem('jama_demo') === 'true';
}

/** Lazy-load demo data (only in browser) */
let _demoData: typeof import('./demo-data') | null = null;
async function getDemoData() {
  if (!_demoData) {
    _demoData = await import('./demo-data');
  }
  return _demoData;
}

/** Wrap an array in a PaginatedResponse shape for demo mode. */
function toPaginated<T>(items: T[], params?: Record<string, string>): PaginatedResponse<T> {
  const page = parseInt(params?.page || '1', 10);
  const pageSize = parseInt(params?.page_size || '50', 10);
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
  };
}

/** Map API endpoints to demo data resolvers */
async function resolveDemo<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
  const d = await getDemoData();
  // Normalize: strip query params
  const path = endpoint.split('?')[0].replace(/\/$/, '');

  // ── Auth ──
  if (path === '/auth/me') {
    const stored = typeof window !== 'undefined' ? localStorage.getItem('jama_user') : null;
    return (stored ? JSON.parse(stored) : d.DEMO_USERS[0]) as T;
  }

  // ── Leads ──
  if (path === '/leads' && !path.includes('/pipeline')) {
    let leads = [...d.DEMO_LEADS];
    if (params) {
      if (params.source && params.source !== 'all') leads = leads.filter(l => l.source === params.source);
      if (params.priority && params.priority !== 'all') leads = leads.filter(l => l.priority === params.priority);
    }
    return toPaginated(leads, params) as T;
  }
  if (path.match(/\/leads\/[^/]+\/activities$/)) {
    const leadId = path.split('/')[2];
    return d.DEMO_ACTIVITIES.filter(a => a.lead_id === leadId) as T;
  }
  if (path.includes('/pipeline/stats')) return d.DEMO_PIPELINE_STATS as T;
  if (path.startsWith('/leads') && path.includes('/pipeline/kanban')) return d.DEMO_PIPELINE_KANBAN as T;

  // ── Projects ──
  if (path === '/projects' && !path.includes('/pipeline') && !path.includes('/tasks')) {
    let projects = [...d.DEMO_PROJECTS];
    if (params?.status && params.status !== 'all') projects = projects.filter(p => p.status === params.status);
    return toPaginated(projects, params) as T;
  }
  if (path.match(/^\/projects\/pipeline\/kanban$/)) {
    const stages = ['design', 'quotation', 'procurement', 'construction', 'acceptance', 'completed'];
    const kanban = stages.map(stage => ({
      stage,
      stage_label: stage.charAt(0).toUpperCase() + stage.slice(1),
      projects: d.DEMO_PROJECTS.filter(p => p.stage === stage),
      count: d.DEMO_PROJECTS.filter(p => p.stage === stage).length,
    }));
    return kanban as T;
  }
  if (path.match(/^\/projects\/tasks\/[^/]+\/activities$/)) {
    return [] as T; // No demo activities for tasks
  }
  if (path.match(/^\/projects\/[^/]+\/tasks$/)) {
    const projectId = path.split('/')[2];
    return d.DEMO_TASKS.filter(t => t.project_id === projectId) as T;
  }
  if (path.match(/^\/projects\/[^/]+$/)) {
    const projectId = path.split('/')[2];
    return (d.DEMO_PROJECTS.find(p => p.id === projectId) || d.DEMO_PROJECTS[0]) as T;
  }

  // ── Dashboard ──
  if (path === '/dashboard/executive') return d.DEMO_DASHBOARD_EXECUTIVE as T;
  if (path === '/dashboard/personal') return d.DEMO_DASHBOARD_PERSONAL as T;

  // ── Accounting ──
  if (path === '/accounting/summary') return d.DEMO_ACCOUNTING_SUMMARY as T;
  if (path === '/accounting/transactions') return toPaginated(d.DEMO_TRANSACTIONS, params) as T;
  if (path === '/accounting/commissions') return toPaginated(d.DEMO_COMMISSIONS, params) as T;
  if (path === '/accounting/payroll') return toPaginated(d.DEMO_PAYROLL, params) as T;

  // ── Customers ──
  if (path === '/customers') return toPaginated(d.DEMO_CUSTOMERS, params) as T;

  // ── Contracts ──
  if (path === '/contracts') return toPaginated(d.DEMO_CONTRACTS, params) as T;

  // ── Quotations ──
  if (path === '/quotations') return toPaginated(d.DEMO_QUOTATIONS, params) as T;

  // ── Inventory ──
  if (path === '/inventory') return toPaginated(d.DEMO_MATERIALS, params) as T;
  if (path === '/inventory/low-stock') return toPaginated(d.DEMO_MATERIALS.filter(m => m.quantity_in_stock <= m.min_stock), params) as T;

  // ── Users / Teams ──
  if (path === '/users') return toPaginated(d.DEMO_USERS, params) as T;
  if (path === '/users/teams') return d.DEMO_TEAMS as T;

  // ── P&L ──
  if (path === '/pl/summary') return d.DEMO_PNL_SUMMARY as T;
  if (path === '/pl/projects') return (d.DEMO_PNL_SUMMARY.revenue_by_project || []) as T;
  if (path.match(/^\/pl\/projects\/[^/]+$/)) {
    const projectId = path.split('/')[3];
    const proj = (d.DEMO_PNL_SUMMARY.revenue_by_project || []).find((p: Record<string, unknown>) => p.project_id === projectId || p.project_code === projectId);
    return (proj || (d.DEMO_PNL_SUMMARY.revenue_by_project || [])[0]) as T;
  }

  // ── AI ──
  if (path === '/ai/parse-lead') return { name: '', phone: '', confidence: 0.95, raw_text: '' } as T;
  if (path === '/ai/suggest-action') return d.DEMO_AI_SUGGESTIONS[0] as T;

  // Fallback: throw so caller shows error
  throw new Error(`Demo mode: no data for ${path}`);
}


interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  params?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('jama_token');
  }

  private headers(token?: string): Record<string, string> {
    const t = token || this.getToken();
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (t) h['Authorization'] = `Bearer ${t}`;
    return h;
  }

  async request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
    const { method = 'GET', body, token, params } = options;

    // Demo mode: return mock data without hitting the API
    if (isDemoMode()) {
      if (method === 'GET') {
        try {
          return await resolveDemo<T>(endpoint, params);
        } catch {
          // Fall through to real API
        }
      } else {
        // POST/PUT in demo mode: simulate success
        try {
          return await resolveDemo<T>(endpoint, params);
        } catch {
          // POST/PUT in demo mode: simulate success with generated ID
          const fakeResponse = { ...(body as Record<string, unknown> || {}), id: `demo-${Date.now()}`, code: `DEMO-${Date.now()}`, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
          return fakeResponse as T;
        }
      }
    }

    let url = `${this.baseUrl}${endpoint}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const res = await fetch(url, {
      method,
      headers: this.headers(token),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  // Auth
  async login(email: string, password: string) {
    const data = await this.request<{
      access_token: string;
      user: User;
    }>('/auth/login', { method: 'POST', body: { email, password } });
    
    if (typeof window !== 'undefined') {
      localStorage.setItem('jama_token', data.access_token);
      localStorage.setItem('jama_user', JSON.stringify(data.user));
    }
    return data;
  }

  async me() {
    return this.request<User>('/auth/me');
  }

  // Leads
  async getLeads(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Lead>>('/leads', { params });
  }

  async getLead(id: string) {
    return this.request<Lead>(`/leads/${id}`);
  }

  async createLead(data: Partial<Lead>) {
    return this.request<Lead>('/leads', { method: 'POST', body: data });
  }

  async updateLead(id: string, data: Partial<Lead>) {
    return this.request<Lead>(`/leads/${id}`, { method: 'PUT', body: data });
  }

  async changeStage(id: string, newStage: string, designContractValue?: number, note?: string) {
    return this.request<Lead>(`/leads/${id}/stage`, {
      method: 'PUT',
      body: { new_stage: newStage, design_contract_value: designContractValue, note },
    });
  }

  async assignLead(id: string, userId: string, note?: string) {
    return this.request<Lead>(`/leads/${id}/assign`, {
      method: 'POST',
      body: { user_id: userId, note },
    });
  }

  async getActivities(leadId: string) {
    return this.request<Activity[]>(`/leads/${leadId}/activities`);
  }

  async createActivity(leadId: string, data: { type: string; content: string }) {
    return this.request<Activity>(`/leads/${leadId}/activities`, {
      method: 'POST',
      body: data,
    });
  }

  // Pipeline
  async getPipelineStats() {
    return this.request<PipelineStats>('/leads/pipeline/stats');
  }

  async getPipelineKanban() {
    return this.request<PipelineKanban[]>('/leads/pipeline/kanban');
  }

  // Projects
  async getProjects(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Project>>('/projects', { params });
  }

  async getProject(id: string) {
    return this.request<Project>(`/projects/${id}`);
  }

  async createProject(data: Partial<Project>) {
    return this.request<Project>('/projects', { method: 'POST', body: data });
  }

  async updateProject(id: string, data: Partial<Project>) {
    return this.request<Project>(`/projects/${id}`, { method: 'PUT', body: data });
  }

  async getProjectTasks(projectId: string) {
    return this.request<ProjectTask[]>(`/projects/${projectId}/tasks`);
  }

  async createTask(projectId: string, data: { title: string; stage: string; department?: string; assigned_to?: string }) {
    return this.request<ProjectTask>(`/projects/${projectId}/tasks`, { method: 'POST', body: data });
  }

  async getProjectKanban() {
    return this.request<ProjectKanban[]>('/projects/pipeline/kanban');
  }

  async updateProjectStage(projectId: string, stage: string) {
    return this.request<Project>(`/projects/${projectId}/stage`, { method: 'PUT', body: { stage } });
  }

  async getTaskActivities(taskId: string) {
    return this.request<TaskActivity[]>(`/projects/tasks/${taskId}/activities`);
  }

  async createTaskActivity(taskId: string, content: string, mediaUrl?: string) {
    return this.request<TaskActivity>(`/projects/tasks/${taskId}/activities`, {
      method: 'POST',
      body: { content, media_url: mediaUrl },
    });
  }

  async updateTaskFinalFile(taskId: string, finalFileUrl: string | null) {
    return this.request<ProjectTask>(`/projects/tasks/${taskId}/final-file`, {
      method: 'PUT',
      body: { final_file_url: finalFileUrl },
    });
  }

  async updateTaskStatus(taskId: string, status: string) {
    return this.request<ProjectTask>(`/projects/tasks/${taskId}/status`, {
      method: 'PUT',
      body: { status },
    });
  }

  // Accounting
  async getTransactions(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Transaction>>('/accounting/transactions', { params });
  }

  async getAccountingSummary() {
    return this.request<AccountingSummary>('/accounting/summary');
  }

  async getCommissions(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Commission>>('/accounting/commissions', { params });
  }

  async getPayroll(params?: Record<string, string>) {
    return this.request<PaginatedResponse<PayrollEntry>>('/accounting/payroll', { params });
  }

  // Dashboard
  async getExecutiveDashboard() {
    return this.request<DashboardExecutive>('/dashboard/executive');
  }

  async getPersonalDashboard() {
    return this.request<DashboardPersonal>('/dashboard/personal');
  }

  // AI
  async parseLead(text: string) {
    return this.request<LeadParseResult>('/ai/parse-lead', {
      method: 'POST',
      body: { text },
    });
  }

  async suggestAction(leadId: string) {
    return this.request<AISuggestion>('/ai/suggest-action', {
      method: 'POST',
      params: { lead_id: leadId },
    });
  }

  // === ERP: Customers ===
  async getCustomers(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Customer>>('/customers', { params });
  }
  async getCustomer(id: string) {
    return this.request<Customer>(`/customers/${id}`);
  }
  async createCustomer(data: Partial<Customer>) {
    return this.request<Customer>('/customers', { method: 'POST', body: data });
  }
  async updateCustomer(id: string, data: Partial<Customer>) {
    return this.request<Customer>(`/customers/${id}`, { method: 'PUT', body: data });
  }

  // === ERP: Contracts ===
  async getContracts(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Contract>>('/contracts', { params });
  }
  async getContract(id: string) {
    return this.request<Contract>(`/contracts/${id}`);
  }
  async createContract(data: Partial<Contract>) {
    return this.request<Contract>('/contracts', { method: 'POST', body: data });
  }
  async updateContract(id: string, data: Partial<Contract>) {
    return this.request<Contract>(`/contracts/${id}`, { method: 'PUT', body: data });
  }
  async updatePayment(contractId: string, installmentIdx: number, proofImage?: string) {
    return this.request<Contract>(`/contracts/${contractId}/payments/${installmentIdx}`, {
      method: 'PUT',
      body: proofImage ? { evidence_url: proofImage } : undefined,
    });
  }

  // === ERP: Quotations ===
  async getQuotations(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Quotation>>('/quotations', { params });
  }
  async getQuotation(id: string) {
    return this.request<Quotation>(`/quotations/${id}`);
  }
  async createQuotation(data: Partial<Quotation>) {
    return this.request<Quotation>('/quotations', { method: 'POST', body: data });
  }
  async updateQuotation(id: string, data: Partial<Quotation>) {
    return this.request<Quotation>(`/quotations/${id}`, { method: 'PUT', body: data });
  }
  async approveQuotation(id: string) {
    return this.request<Quotation>(`/quotations/${id}/approve`, { method: 'POST' });
  }

  // === ERP: Inventory ===
  async getMaterials(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Material>>('/inventory', { params });
  }
  async getMaterial(id: string) {
    return this.request<Material>(`/inventory/${id}`);
  }
  async createMaterial(data: Partial<Material>) {
    return this.request<Material>('/inventory', { method: 'POST', body: data });
  }
  async updateMaterial(id: string, data: Partial<Material>) {
    return this.request<Material>(`/inventory/${id}`, { method: 'PUT', body: data });
  }
  async adjustStock(id: string, delta: number, reason?: string) {
    return this.request<Material>(`/inventory/${id}/adjust-stock`, { method: 'POST', body: { quantity: delta, reason } });
  }
  async useMaterial(data: { material_id: string; project_id: string; quantity: number; note?: string }) {
    return this.request<unknown>('/inventory/use', { method: 'POST', body: { ...data, notes: data.note, note: undefined } });
  }
  async getLowStock() {
    return this.request<Material[]>('/inventory/low-stock');
  }
  async getMaterialUsages(materialId: string) {
    return this.request<MaterialUsage[]>(`/inventory/${materialId}/usages`);
  }

  // === ERP: Users (HR) ===
  async getUsers(params?: Record<string, string>) {
    return this.request<PaginatedResponse<User>>('/users', { params });
  }
  async getTeams() {
    return this.request<Team[]>('/users/teams');
  }
  async createUser(data: Partial<User> & { password: string }) {
    return this.request<User>('/users', { method: 'POST', body: data });
  }
  async updateUser(id: string, data: Partial<User>) {
    return this.request<User>(`/users/${id}`, { method: 'PUT', body: data });
  }

  // === ERP: P&L (C-level only) ===
  async getPnLSummary() {
    return this.request<PnLSummary>('/pl/summary');
  }
  async getPnLProjects() {
    return this.request<PnLProject[]>('/pl/projects');
  }
  async getPnLProject(projectId: string) {
    return this.request<PnLProjectDetail>(`/pl/projects/${projectId}`);
  }

  // Finance Module
  async getSalaryGrades() { return this.request<SalaryGrade[]>('/salary-grades'); }
  async createSalaryGrade(data: Partial<SalaryGrade>) { return this.request<SalaryGrade>('/salary-grades', { method: 'POST', body: data }); }
  async updateSalaryGrade(id: string, data: Partial<SalaryGrade>) { return this.request<SalaryGrade>(`/salary-grades/${id}`, { method: 'PUT', body: data }); }
  async deleteSalaryGrade(id: string) { return this.request<unknown>(`/salary-grades/${id}`, { method: 'DELETE' }); }

  async getFixedCosts(month?: string) { return this.request<FixedCost[]>('/fixed-costs', { params: month ? { month } : undefined }); }
  async createFixedCost(data: Partial<FixedCost>) { return this.request<FixedCost>('/fixed-costs', { method: 'POST', body: data }); }
  async updateFixedCost(id: string, data: Partial<FixedCost>) { return this.request<FixedCost>(`/fixed-costs/${id}`, { method: 'PUT', body: data }); }
  async deleteFixedCost(id: string) { return this.request<unknown>(`/fixed-costs/${id}`, { method: 'DELETE' }); }

  async getVariableCosts(month?: string) { return this.request<VariableCost[]>('/variable-costs', { params: month ? { month } : undefined }); }
  async createVariableCost(data: Partial<VariableCost>) { return this.request<VariableCost>('/variable-costs', { method: 'POST', body: data }); }
  async updateVariableCost(id: string, data: Partial<VariableCost>) { return this.request<VariableCost>(`/variable-costs/${id}`, { method: 'PUT', body: data }); }
  async deleteVariableCost(id: string) { return this.request<unknown>(`/variable-costs/${id}`, { method: 'DELETE' }); }

  async getCommissionStructures() { return this.request<CommissionStructure[]>('/commission-structures'); }
  async createCommissionStructure(data: Partial<CommissionStructure>) { return this.request<CommissionStructure>('/commission-structures', { method: 'POST', body: data }); }
  async updateCommissionStructure(id: string, data: Partial<CommissionStructure>) { return this.request<CommissionStructure>(`/commission-structures/${id}`, { method: 'PUT', body: data }); }
  async deleteCommissionStructure(id: string) { return this.request<unknown>(`/commission-structures/${id}`, { method: 'DELETE' }); }

  logout() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('jama_token');
      localStorage.removeItem('jama_user');
    }
  }
}

// Types
export interface User {
  id: string;
  full_name: string;
  email: string;
  phone?: string;
  role: string;
  department: string;
  team_id?: string;
  telegram_user_id?: number;
  is_active: boolean;
  created_at: string;
}

export interface Lead {
  id: string;
  name: string;
  phone: string;
  email?: string;
  contact_person?: string;
  address?: string;
  needs?: string;
  source?: string;
  property_type?: string;
  area_sqm?: number;
  estimated_budget?: number;
  stage: string;
  priority: string;
  assigned_to?: string;
  team_id?: string;
  ai_score?: number;
  ai_notes?: string;
  design_contract_value?: number;
  erp_lead_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  last_contacted_at?: string;
  assigned_user_name?: string;
  team_name?: string;
  activity_count?: number;
  property_class?: 'luxury' | 'mid_range' | 'budget';
  price_per_sqm?: number;
  region?: string;
  segment?: string;
  plan_type?: 'online' | 'offline' | 'survey' | 'none';
  tags?: string[];
  deal_value?: number;
  lost_reason?: string;
}

export interface Activity {
  id: string;
  lead_id: string;
  user_id: string;
  type: string;
  content: string;
  telegram_message_id?: number;
  created_at: string;
  user_name?: string;
}

export interface Project {
  id: string;
  code: string;
  name: string;
  lead_id?: string;
  client_name: string;
  client_phone?: string;
  address?: string;
  project_type: string;
  status: string;
  stage: string;
  design_value?: number;
  construction_value?: number;
  total_value?: number;
  spent: number;
  progress: number;
  pm_id?: string;
  designer_id?: string;
  sales_id?: string;
  start_date?: string;
  target_end_date?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectTask {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  status: string; // not_started | in_progress | done
  stage: string;
  department?: string; // design | quotation | procurement | construction | accounting | sales
  final_file_url?: string;
  assigned_to?: string;
  order: number;
  due_date?: string;
  completed_at?: string;
  created_at: string;
}

export interface ProjectKanban {
  stage: string;
  stage_label: string;
  projects: Project[];
  count: number;
}

export interface TaskActivity {
  id: string;
  task_id: string;
  user_id: string;
  user_name?: string;
  content: string;
  media_url?: string;
  created_at: string;
}

export interface Transaction {
  id: string;
  code: string;
  type: string;
  category: string;
  description: string;
  amount: number;
  project_id?: string;
  status: string;
  date: string;
  created_at: string;
}

export interface AccountingSummary {
  total_income: number;
  total_expense: number;
  net: number;
  by_category: Array<{
    category: string;
    type: string;
    total: number;
    count: number;
  }>;
}

export interface Commission {
  id: string;
  user_id: string;
  user_name?: string;
  project_id?: string;
  type: string;
  rate: number;
  base_amount: number;
  commission_amount: number;
  milestone: string;
  status: string;
  period?: string;
}

export interface PayrollEntry {
  id: string;
  user_id: string;
  user_name?: string;
  period: string;
  base_salary: number;
  commission_total: number;
  bonus: number;
  deductions: number;
  net_salary: number;
  status: string;
}

export interface PipelineStats {
  total_leads: number;
  by_stage: Record<string, number>;
  conversion_rate: number;
  pipeline_value: number;
  sla_compliance: number;
  overdue_count: number;
  today_count: number;
  unassigned_count: number;
}

export interface PipelineKanban {
  stage: string;
  stage_label: string;
  leads: Lead[];
  count: number;
}

export interface DashboardExecutive {
  total_leads: number;
  total_leads_month: number;
  conversion_rate: number;
  pipeline_value: number;
  total_contracts: number;
  total_contract_value: number;
  active_projects: number;
  avg_project_progress: number;
  sla_compliance: number;
  overdue_leads: number;
  team_performance: Array<{
    team: string;
    total_leads: number;
    signed: number;
    conversion: number;
  }>;
  stage_funnel: Record<string, number>;
  monthly_trend: Array<Record<string, unknown>>;
  financial_summary?: {
    total_revenue_ytd: number;
    total_cost_ytd: number;
    net_profit_ytd: number;
    roi: number;
    yoy_growth: number;
    avg_project_margin: number;
    cash_flow: number;
    outstanding_receivable: number;
  };
  forecast?: {
    q3_2026: number;
    q4_2026: number;
    full_year_2026: number;
    full_year_2025: number;
  };
  growth_metrics?: {
    lead_growth_rate: number;
    conversion_improvement: number;
    avg_deal_size: number;
    customer_acquisition_cost: number;
    customer_lifetime_value: number;
    pipeline_velocity: number;
  };
  risk_hedging?: {
    concentration_risk: string;
    top_client_pct: number;
    pipeline_coverage: number;
    cash_reserve_months: number;
    overdue_receivable_pct: number;
  };
}

export interface DashboardPersonal {
  user_name: string;
  total_active_leads: number;
  by_stage: Record<string, number>;
  overdue_followup: Array<Record<string, unknown>>;
  today_appointments: Array<Record<string, unknown>>;
  weekly_kpis: Record<string, unknown>;
  pipeline_value: number;
  ai_suggestions: Array<Record<string, unknown>>;
}

export interface LeadParseResult {
  name?: string;
  phone?: string;
  contact_person?: string;
  address?: string;
  needs?: string;
  source?: string;
  property_type?: string;
  area_sqm?: number;
  estimated_budget?: number;
  confidence: number;
  raw_text: string;
}

export interface AISuggestion {
  action: string;
  reason: string;
  priority: string;
  message_template?: string;
}

// === ERP Types ===

export interface Customer {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  address?: string;
  type: string; // individual | company
  tax_code?: string;
  company_name?: string;
  lead_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Contract {
  id: string;
  code: string;
  project_id: string;
  quotation_id?: string;
  title: string;
  status: string; // draft | approved | sent | signed | completed | cancelled
  total_value?: number;
  payment_terms?: {
    installments: Array<{
      name: string;
      percentage: number;
      milestone: string;
      status: string;
      paid_date?: string;
      amount?: number;
      proof_image?: string;
    }>;
  };
  signed_date?: string;
  working_days?: number;
  start_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Quotation {
  id: string;
  code: string;
  type: string; // design | construction
  project_id?: string;
  lead_id?: string;
  title: string;
  status: string; // draft | approved | sent | rejected | expired
  total_amount?: number;
  tax_amount?: number;
  valid_until?: string;
  items?: unknown;
  revision: number;
  notes?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface Material {
  id: string;
  code: string;
  name: string;
  category: string;
  unit: string;
  unit_price: number;
  quantity_in_stock: number;
  min_stock: number;
  supplier?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface MaterialUsage {
  id: string;
  material_id: string;
  project_id: string;
  quantity: number;
  note?: string;
  used_by?: string;
  created_at: string;
  material_name?: string;
  project_name?: string;
}

export interface Team {
  id: string;
  name: string;
  code: string;
  department: string;
  leader_id?: string;
  created_at: string;
}

// === P&L Types ===
export interface PnLSummary {
  total_revenue: number;
  total_costs: number;
  net_profit: number;
  margin_pct: number;
  revenue_by_project: PnLProject[];
}

export interface PnLProject {
  project_id: string;
  project_code: string;
  project_name: string;
  revenue: number;
  costs: number;
  profit: number;
  margin_pct: number;
  status: string;
}

export interface PnLProjectDetail {
  project_id: string;
  project_code: string;
  project_name: string;
  revenue: number;
  costs: number;
  profit: number;
  margin_pct: number;
  cost_breakdown: {
    materials: number;
    labor: number;
    other: number;
  };
  revenue_breakdown: {
    design: number;
    construction: number;
  };
}

// === Finance Module Types ===
export interface SalaryGrade {
  id: string;
  grade_name: string;
  base_salary: number;
  bhxh_rate: number;
  bhxh_company_rate: number;
  bhyt_rate: number;
  bhtn_rate: number;
  effective_date: string;
  created_at: string;
}

export interface FixedCost {
  id: string;
  category: string;
  amount: number;
  month: string;
  notes?: string;
  created_at: string;
}

export interface VariableCost {
  id: string;
  category: string;
  amount: number;
  project_id?: string;
  month: string;
  notes?: string;
  created_at: string;
}

export interface CommissionStructure {
  id: string;
  department: string;
  commission_type: string;
  rate: number;
  effective_date: string;
  created_at: string;
}

// === Pagination ===
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Extract items from either a PaginatedResponse or a plain array (backward compat). */
export function extractItems<T>(response: T[] | PaginatedResponse<T>): T[] {
  if (Array.isArray(response)) return response;
  return (response as PaginatedResponse<T>).items ?? [];
}

// Export singleton
export const api = new ApiClient(API_BASE);
