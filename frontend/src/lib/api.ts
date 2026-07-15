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

/** In-memory store for demo activities added during session */
const _demoActivitiesCache: Activity[] = [];
const _demoTaskActivitiesCache: TaskActivity[] = [];

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
async function resolveDemo<T>(endpoint: string, params?: Record<string, string>, options?: { method?: string; body?: unknown }): Promise<T> {
  const d = await getDemoData();
  // Normalize: strip query params
  const path = endpoint.split('?')[0].replace(/\/$/, '');
  const method = options?.method || 'GET';

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
  // ── Lead Activities (POST = create note, GET = list) ──
  if (path.match(/\/leads\/[^/]+\/activities$/)) {
    const leadId = path.split('/')[2];
    if (method === 'POST') {
      const body = options?.body as { type?: string; content?: string } || {};
      const userStored = typeof window !== 'undefined' ? localStorage.getItem('jama_user') : null;
      const currentUser = userStored ? JSON.parse(userStored) : d.DEMO_USERS[0];
      const newActivity: Activity = {
        id: `demo-act-${Date.now()}`,
        lead_id: leadId,
        user_id: currentUser.id,
        user_name: currentUser.full_name,
        type: body.type || 'note',
        content: body.content || '',
        created_at: new Date().toISOString(),
      };
      _demoActivitiesCache.push(newActivity);
      return newActivity as T;
    }
    // GET: merge static demo activities + cached ones
    const staticActs = d.DEMO_ACTIVITIES.filter(a => a.lead_id === leadId);
    const cachedActs = _demoActivitiesCache.filter(a => a.lead_id === leadId);
    return [...staticActs, ...cachedActs] as T;
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
    const taskId = path.split('/')[3];
    if (method === 'POST') {
      const body = options?.body as { content?: string; media_url?: string } || {};
      const userStored = typeof window !== 'undefined' ? localStorage.getItem('jama_user') : null;
      const currentUser = userStored ? JSON.parse(userStored) : d.DEMO_USERS[0];
      const newAct: TaskActivity = {
        id: `demo-tact-${Date.now()}`,
        task_id: taskId,
        user_id: currentUser.id,
        user_name: currentUser.full_name,
        content: body.content || '',
        media_url: body.media_url || undefined,
        created_at: new Date().toISOString(),
      };
      _demoTaskActivitiesCache.push(newAct);
      return newAct as T;
    }
    const cached = _demoTaskActivitiesCache.filter(a => a.task_id === taskId);
    return cached as T;
  }
  if (path.match(/^\/projects\/[^/]+\/tasks$/)) {
    const projectId = path.split('/')[2];
    return d.DEMO_TASKS.filter(t => t.project_id === projectId).sort((a, b) => a.order - b.order) as T;
  }
  // PUT /projects/tasks/{taskId}/status — demo mode status update
  if (path.match(/^\/projects\/tasks\/[^/]+\/status$/) && method === 'PUT') {
    const taskId = path.split('/')[3];
    const task = d.DEMO_TASKS.find(t => t.id === taskId);
    if (task) {
      task.status = (options?.body as Record<string, string>)?.status || task.status;
      return task as T;
    }
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
  if (path.match(/^\/customers\/[^/]+$/) && method === 'GET') {
    const custId = path.split('/')[2];
    const custList = d.DEMO_CUSTOMERS as unknown as Array<Record<string, unknown>>;
    const projList = d.DEMO_PROJECTS as unknown as Array<Record<string, unknown>>;
    const cust = custList.find(c => c.id === custId) || custList[0];
    // Enrich with linked projects
    const linkedProjects = projList.filter(p => p.lead_id === cust.lead_id || p.customer_id === cust.id);
    return { ...cust, projects: linkedProjects, project_count: linkedProjects.length } as T;
  }

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

  // ── Notifications (demo: NotificationCenter generates locally) ──
  if (path === '/notifications') return { items: [], unread_count: 0 } as T;
  if (path.match(/^\/notifications\/.+\/read$/) || path === '/notifications/read-all') {
    return { status: 'ok' } as T;
  }

  // ── HR Phase 1: Chấm công / Phê duyệt / Nghỉ phép / Lương ──
  if (path === '/projects/by-department') return { department: params?.dept || 'DESIGN', items: [] } as T;
  if (path === '/attendance/today') return { record: null } as T;
  if (path === '/attendance/me') {
    return {
      summary: { period: '2026-07', records: 20, work_days: 20, work_days_fraction: 20, total_hours: 160, ot_approved_hours: 4, needs_review: 0 },
      records: [
        { id: 'demo-att-1', user_id: 'demo-user', work_date: '2026-07-14', check_in: '2026-07-14 08:01', check_out: '2026-07-14 17:32', project_id: null, source: 'web', work_hours: 8, ot_hours: 1.5, ot_status: 'approved', needs_review: false, note: null },
        { id: 'demo-att-2', user_id: 'demo-user', work_date: '2026-07-13', check_in: '2026-07-13 07:58', check_out: '2026-07-13 17:05', project_id: null, source: 'telegram', work_hours: 8, ot_hours: 0, ot_status: 'none', needs_review: false, note: null },
      ],
    } as T;
  }
  if (path === '/attendance/team') return { period: '2026-07', items: [] } as T;
  if (path === '/attendance/ot/pending') return { items: [] } as T;
  if (path === '/approvals/pending-for-me') {
    return { items: [
      { id: 'demo-apr-1', type: 'leave', type_label: 'Nghỉ phép', ref_id: 'demo-leave-1', title: 'Phép năm 2 ngày (2026-07-20 → 2026-07-21) — Nguyễn Văn Sale', amount: null, requester_id: 'u-sales', requester_name: 'Nguyễn Văn Sale', step: 1, total_steps: 1, status: 'pending', reason: null, due_at: null, created_at: '2026-07-14 09:00', resolved_at: null, delegated: false },
    ], count: 1 } as T;
  }
  if (path === '/approvals/my-requests') return { items: [] } as T;
  if (path === '/approvals/handled') return { items: [] } as T;
  if (path === '/leaves/me') return { items: [] } as T;
  if (path === '/leaves/balance/me') return { year: 2026, annual_total: 12, annual_used: 3, annual_remaining: 9, sick_used: 0, unpaid_used: 0 } as T;
  if (path === '/leaves/calendar') return { month: params?.month || '2026-07', items: [] } as T;
  if (path === '/payroll/me') {
    return { items: [
      { id: 'demo-pay-1', period: '2026-06', base_salary: 12000000, work_days: 22, standard_days: 22, ot_hours: 4, ot_pay: 409000, commission_total: 6500000, bonus: 0, allowance: 0, gross_salary: 18909000, bhxh_employee: 1260000, taxable_income: 6649000, pit: 414900, advance_deduction: 0, deductions: 0, net_salary: 17234100, status: 'paid', notes: null, paid_at: '2026-07-05', payslip_sent_at: '2026-07-05' },
    ] } as T;
  }
  if (path === '/payroll/advances/me') return { items: [] } as T;
  if (path === '/payroll/settings') return { pit_personal_deduction: 11000000, pit_dependent_deduction: 4400000, bhxh_salary_cap: 46800000, payroll_standard_days: 22, ot_multiplier: 1.5 } as T;
  if (path === '/payroll') return { period: params?.period || '2026-07', items: [], total_net: 0, total_company_cost: 0, status: null } as T;

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
      try {
        return await resolveDemo<T>(endpoint, params, { method, body });
      } catch {
        if (method !== 'GET') {
          // POST/PUT in demo mode: simulate success with generated ID
          const fakeResponse = { ...(body as Record<string, unknown> || {}), id: `demo-${Date.now()}`, code: `DEMO-${Date.now()}`, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
          return fakeResponse as T;
        }
        // Fall through to real API for GET
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

  /** Dự án đang đến phòng bạn (Tổng quan designer/pm/purchasing) — spec 07 A3 */
  async getProjectsByDepartment(dept: 'DESIGN' | 'PURCHASING' | 'PM', limit = 5) {
    return this.request<{ department: string; items: (Project & { pending_tasks: number; days_left: number | null })[] }>(
      '/projects/by-department', { params: { dept, limit: String(limit) } }
    );
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

  async createTransaction(data: { type: string; category: string; description: string; amount: number; date: string; project_id?: string }) {
    return this.request<Transaction>('/accounting/transactions', { method: 'POST', body: data });
  }
  async updateTransaction(id: string, data: Record<string, unknown>) {
    return this.request<Transaction>(`/accounting/transactions/${id}`, { method: 'PUT', body: data });
  }
  async deleteTransaction(id: string) {
    return this.request<{ status: string }>(`/accounting/transactions/${id}`, { method: 'DELETE' });
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

  // === Resignation / Transfer ===
  async resignPreview(userId: string) {
    return this.request<{
      user_name: string;
      leads: Array<{ id: string; name: string; phone: string; stage: string }>;
      tasks: Array<{ id: string; title: string; project_name: string; status: string }>;
      lead_count: number;
      task_count: number;
    }>('/hr/resign-preview', { method: 'POST', body: { user_id: userId } });
  }

  async resignUser(data: { user_id: string; transfer_leads_to?: string; transfer_tasks_to?: string }) {
    return this.request<{
      transferred_leads: number;
      transferred_tasks: number;
      message: string;
    }>('/hr/resign', { method: 'POST', body: data });
  }

  async undoResign(userId: string) {
    return this.request<{ status: string; message: string }>(
      '/hr/undo-resign',
      { method: 'POST', body: { user_id: userId } }
    );
  }

  // === HR Phase 1: Chấm công ===
  async attendanceCheckin(data?: { project_id?: string; latitude?: number; longitude?: number }) {
    return this.request<{ record: AttendanceRecord; created: boolean; message: string }>(
      '/attendance/checkin', { method: 'POST', body: data || {} }
    );
  }
  async attendanceCheckout() {
    return this.request<{ record: AttendanceRecord; message: string }>('/attendance/checkout', { method: 'POST' });
  }
  async attendanceToday() {
    return this.request<{ record: AttendanceRecord | null }>('/attendance/today');
  }
  async myAttendance(period?: string) {
    return this.request<{ summary: AttendanceSummary; records: AttendanceRecord[] }>(
      '/attendance/me', { params: period ? { period } : undefined }
    );
  }
  async teamAttendance(period?: string, teamId?: string) {
    const params: Record<string, string> = {};
    if (period) params.period = period;
    if (teamId) params.team_id = teamId;
    return this.request<{ period: string; items: TeamAttendanceRow[] }>(
      '/attendance/team', { params: Object.keys(params).length ? params : undefined }
    );
  }
  async pendingOT() {
    return this.request<{ items: (AttendanceRecord & { full_name: string })[] }>('/attendance/ot/pending');
  }
  async approveOT(recordId: string) {
    return this.request<{ record: AttendanceRecord }>(`/attendance/${recordId}/ot-approve`, { method: 'POST' });
  }
  async rejectOT(recordId: string) {
    return this.request<{ record: AttendanceRecord }>(`/attendance/${recordId}/ot-reject`, { method: 'POST' });
  }

  // === HR Phase 1: Phê duyệt ===
  async approvalsPendingForMe() {
    return this.request<{ items: ApprovalItem[]; count: number }>('/approvals/pending-for-me');
  }
  async approvalsMyRequests() {
    return this.request<{ items: ApprovalItem[] }>('/approvals/my-requests');
  }
  async approvalsHandled() {
    return this.request<{ items: ApprovalItem[] }>('/approvals/handled');
  }
  async approveRequest(id: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/approve`, { method: 'POST' });
  }
  async rejectRequest(id: string, reason: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/reject`, { method: 'POST', body: { reason } });
  }
  async requestChanges(id: string, reason: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/request-changes`, { method: 'POST', body: { reason } });
  }
  async cancelRequest(id: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/cancel`, { method: 'POST' });
  }

  // === HR Phase 1: Nghỉ phép ===
  async createLeave(data: { leave_type: string; start_date: string; end_date: string; half_day?: boolean; reason: string }) {
    return this.request<{ leave: LeaveItem; approval_id: string }>('/leaves', { method: 'POST', body: data });
  }
  async myLeaves() {
    return this.request<{ items: LeaveItem[] }>('/leaves/me');
  }
  async myLeaveBalance(year?: number) {
    return this.request<LeaveBalanceInfo>('/leaves/balance/me', { params: year ? { year: String(year) } : undefined });
  }
  async leaveCalendar(month: string, teamId?: string) {
    const params: Record<string, string> = { month };
    if (teamId) params.team_id = teamId;
    return this.request<{ month: string; items: (LeaveItem & { full_name: string })[] }>('/leaves/calendar', { params });
  }

  // === HR Phase 1: Lương ===
  async myPayslips() {
    return this.request<{ items: PayrollRow[] }>('/payroll/me');
  }
  async payrollGenerate(period: string) {
    return this.request<{ period: string; created: number; total_net: number; missing_grade: number }>(
      `/payroll/generate?period=${period}`, { method: 'POST' }
    );
  }
  async payrollList(period: string) {
    return this.request<{ period: string; items: (PayrollRow & { full_name: string; role: string })[]; total_net: number; total_company_cost: number; status: string | null }>(
      '/payroll', { params: { period } }
    );
  }
  async payrollSubmit(period: string) {
    return this.request<{ period: string; rows: number; total_net: number; approval_id: string }>(
      `/payroll/${period}/submit`, { method: 'POST' }
    );
  }
  async payrollPay(period: string) {
    return this.request<{ period: string; paid_rows: number; sent: number; manual_delivery: string[] }>(
      `/payroll/${period}/pay`, { method: 'POST' }
    );
  }
  async payrollUpdateRow(rowId: string, data: { bonus?: number; allowance?: number; deductions?: number; notes?: string }) {
    return this.request<{ row: PayrollRow }>(`/payroll/rows/${rowId}`, { method: 'PATCH', body: data });
  }
  async createAdvance(data: { amount: number; reason: string }) {
    return this.request<{ advance: { id: string; amount: number; status: string }; approval_id: string }>(
      '/payroll/advance', { method: 'POST', body: data }
    );
  }
  async myAdvances() {
    return this.request<{ items: { id: string; amount: number; reason: string; status: string; period_deducted: string | null; created_at: string }[] }>('/payroll/advances/me');
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

  // === Notifications ===
  async getNotifications(unreadOnly = false) {
    return this.request<{ items: ServerNotification[]; unread_count: number }>(
      '/notifications', { params: unreadOnly ? { unread_only: 'true' } : undefined }
    );
  }
  async markNotificationRead(id: string) {
    return this.request<{ status: string }>(`/notifications/${id}/read`, { method: 'PUT' });
  }
  async markAllNotificationsRead() {
    return this.request<{ status: string }>('/notifications/read-all', { method: 'PUT' });
  }

  // === Automation (admin/executive) ===
  async getAutomationSettings() {
    return this.request<AutomationSettings>('/automation/settings');
  }
  async updateAutomationSettings(data: Partial<{
    followup_reminder_days: number;
    lead_recall_days: number;
    lead_recall_enabled: boolean;
    payment_reminder_days: number;
    bod_report_enabled: boolean;
    bod_report_hour: number;
    telegram_group_chat_id: string;
    group_briefing_enabled: boolean;
  }>) {
    return this.request<AutomationSettings>('/automation/settings', { method: 'PUT', body: data });
  }
  async runAutomation(job: 'followups' | 'recall' | 'payments' | 'all') {
    return this.request<Record<string, unknown>>(`/automation/run/${job}`, { method: 'POST' });
  }
  async sendBodReport(period: 'daily' | 'weekly' | 'monthly') {
    return this.request<Record<string, unknown>>(`/automation/run/bod-report/${period}`, { method: 'POST' });
  }
  async previewBodReport(period: 'daily' | 'weekly' | 'monthly') {
    return this.request<{ period: string; text: string; metrics: Record<string, number> }>(
      `/automation/bod-report/${period}/preview`
    );
  }
  async sendGroupBriefing() {
    return this.request<{ status: string; reason?: string }>('/automation/run/group-briefing', { method: 'POST' });
  }

  // === AI Settings (admin only) ===
  async getAISettings() {
    return this.request<AISettingsResponse>('/ai-settings');
  }
  async updateAISettings(data: Partial<{
    llm_model: string;
    llm_api_key: string;
    llm_fallback_model: string;
    llm_fallback_api_key: string;
  }>) {
    return this.request<AISettingsResponse>('/ai-settings', { method: 'PUT', body: data });
  }
  async testAIConnection() {
    return this.request<{ status: string; model?: string; reply?: string; detail?: string }>(
      '/ai-settings/test', { method: 'POST' }
    );
  }

  // === Backup (admin only) ===
  async getBackupSettings() {
    return this.request<BackupSettingsResponse>('/backup/settings');
  }
  async updateBackupSettings(data: Partial<{
    backup_enabled: boolean;
    backup_hour: number;
    backup_retention_days: number;
    backup_gdrive_enabled: boolean;
    gdrive_client_id: string;
    gdrive_client_secret: string;
  }>) {
    return this.request<BackupSettingsResponse>('/backup/settings', { method: 'PUT', body: data });
  }
  async runBackupNow() {
    return this.request<{ status: string; file?: string; size_mb?: number; gdrive_uploaded?: boolean; reason?: string }>(
      '/backup/run', { method: 'POST' }
    );
  }
  async getGdriveAuthUrl() {
    return this.request<{ auth_url: string }>('/backup/gdrive/auth-url');
  }
  async disconnectGdrive() {
    return this.request<{ status: string }>('/backup/gdrive/disconnect', { method: 'POST' });
  }

  // === Instant Quote (báo giá sơ bộ tức thì) ===
  async generateInstantQuote(data: {
    mode?: string; area_sqm?: number; property_type?: string; bedrooms?: number | null;
    budget?: number | null; raw_text?: string; floors?: number; scope?: string;
  }) {
    return this.request<InstantQuoteResult>('/instant-quote/generate', { method: 'POST', body: data });
  }
  async getPriceItems() {
    return this.request<PriceItemDTO[]>('/instant-quote/price-items');
  }
  async updatePriceItem(id: string, data: Partial<Omit<PriceItemDTO, 'id' | 'code' | 'updated_at'>>) {
    return this.request<{ status: string }>(`/instant-quote/price-items/${id}`, { method: 'PUT', body: data });
  }

  // ── KPI ──
  async getKpiMe(period?: string) {
    return this.request<{ period: string; score: number; metrics: { activity_rate: number; sla_compliance: number; first_touch_hours: number; signed_count: number; signed_value: number; stage_conversion: number; pipeline_value_weighted: number; recall_rate: number; lost_no_response_rate: number }; rank_in_team: number | null; rank_overall: number | null }>(
      '/kpi/me', { params: period ? { period } : undefined });
  }
  async getKpiTeam(period?: string) {
    return this.request<{ period: string; members: Array<{ user_id: string; name: string; score: number; metrics: { activity_rate: number; sla_compliance: number; first_touch_hours: number; signed_count: number; signed_value: number; stage_conversion: number; pipeline_value_weighted: number; recall_rate: number; lost_no_response_rate: number } }> }>(
      '/kpi/team', { params: period ? { period } : undefined });
  }
  async getKpiLeaderboard(period?: string) {
    return this.request<{ leaderboard: Array<{ rank: number; score: number; name: string | null; is_me: boolean }> }>(
      '/kpi/leaderboard', { params: period ? { period } : undefined });
  }

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
  resign_date?: string;
  resigned_by?: string;
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
  channel?: string;
  property_type?: string;
  area_sqm?: number;
  estimated_budget?: number;
  contact_status?: string;
  survey_date?: string;
  survey_photos?: string[];
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
  customer_id?: string;
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
  /** Tiến độ đầu việc theo giai đoạn (chỉ có ở API kanban) */
  stage_progress?: Record<string, { done: number; total: number }> | null;
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

/** Unified dashboard type — all fields optional since exec/personal have different shapes */
export type DashboardData = Partial<DashboardExecutive> & Partial<DashboardPersonal>;

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
  projects?: Array<{ id: string; code: string; name: string; status: string; stage: string; total_value?: number; spent?: number; progress: number; created_at: string }>;
  project_count?: number;
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

// === Notifications & Automation ===
export interface ServerNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface AutomationSettings {
  followup_reminder_days: string;
  lead_recall_days: string;
  lead_recall_enabled: string;
  payment_reminder_days: string;
  bod_report_enabled: string;
  bod_report_hour: string;
  telegram_group_chat_id: string;
  group_briefing_enabled: string;
}

// === Instant Quote ===
export interface QuoteLineItem {
  code: string; name: string; category: string; unit: string;
  qty: number; unit_price: number; total: number;
}

export interface QuoteTier {
  label: string; items: QuoteLineItem[]; total: number;
  range_low: number; range_high: number; per_sqm: number;
}

export interface RenovationCategory {
  label: string; total: number; count: number;
}

export interface MaterialOption {
  category: string;
  options: Array<{ name: string; price_delta: number; unit: string }>;
}

export interface InstantQuoteResult {
  mode?: string;
  area_sqm: number; property_type?: string; bedrooms?: number;
  floors?: number;
  tiers?: { basic: QuoteTier; standard: QuoteTier; premium: QuoteTier };
  suggested_tier?: 'basic' | 'standard' | 'premium';
  categories?: Record<string, Array<{ code: string; name: string; unit: string; qty: number; unit_price: number; total: number; note?: string }>>;
  category_totals?: Record<string, RenovationCategory>;
  total?: number;
  per_sqm?: number;
  range_low?: number;
  range_high?: number;
  material_options?: MaterialOption[];
  customer_budget: number | null;
  zalo_text: string;
  disclaimer: string;
  parsed: { name?: string; phone?: string } | null;
}

export interface PriceItemDTO {
  id: string; code: string; name: string; category: string; unit: string;
  price_basic: number; price_standard: number; price_premium: number;
  note: string | null; is_active: boolean; updated_at: string | null;
}

export interface BackupSettingsResponse {
  backup_enabled: string;
  backup_hour: string;
  backup_retention_days: string;
  backup_gdrive_enabled: string;
  max_retention_days: number;
  gdrive_connected: boolean;
  gdrive_account_email: string;
  gdrive_client_id_set: boolean;
  last_run: string;
  last_status: { status: string; file?: string; size_mb?: number; gdrive_uploaded?: boolean; reason?: string } | null;
  local_backup_count: number;
  local_backups: { name: string; size_bytes: number; created_at: string }[];
}

export interface AISettingsResponse {
  llm_model: string;
  llm_api_key_masked: string;
  llm_api_key_set: boolean;
  llm_fallback_model: string;
  llm_fallback_api_key_masked: string;
  llm_fallback_api_key_set: boolean;
  presets: { label: string; model: string }[];
}

// === Pagination ===
// === HR Phase 1 types ===
export interface AttendanceRecord {
  id: string;
  user_id: string;
  work_date: string;
  check_in: string | null;
  check_out: string | null;
  project_id: string | null;
  source: string;
  work_hours: number;
  ot_hours: number;
  ot_status: 'none' | 'pending' | 'approved' | 'rejected';
  needs_review: boolean;
  note: string | null;
}

export interface AttendanceSummary {
  period: string;
  records: number;
  work_days: number;
  work_days_fraction: number;
  total_hours: number;
  ot_approved_hours: number;
  needs_review: number;
}

export interface TeamAttendanceRow extends AttendanceSummary {
  user_id: string;
  full_name: string;
  role: string;
  team_id: string | null;
}

export interface ApprovalItem {
  id: string;
  type: string;
  type_label: string;
  ref_id: string;
  title: string;
  amount: number | null;
  requester_id: string;
  requester_name?: string;
  current_approver_id?: string | null;
  step: number;
  total_steps: number;
  status: 'pending' | 'approved' | 'rejected' | 'changes_requested' | 'cancelled';
  reason: string | null;
  due_at: string | null;
  created_at: string;
  resolved_at: string | null;
  delegated?: boolean;
}

export interface LeaveItem {
  id: string;
  user_id: string;
  leave_type: 'annual' | 'sick' | 'unpaid';
  leave_type_label: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: string;
  approval_id: string | null;
  created_at: string;
}

export interface LeaveBalanceInfo {
  year: number;
  annual_total: number;
  annual_used: number;
  annual_remaining: number;
  sick_used: number;
  unpaid_used: number;
}

export interface PayrollRow {
  id: string;
  user_id?: string;
  period: string;
  base_salary: number;
  work_days: number;
  standard_days: number;
  ot_hours: number;
  ot_pay: number;
  commission_total: number;
  bonus: number;
  allowance: number;
  gross_salary: number;
  bhxh_employee: number;
  bhxh_company?: number;
  taxable_income: number;
  pit: number;
  advance_deduction: number;
  deductions: number;
  net_salary: number;
  status: string;
  notes: string | null;
  paid_at: string | null;
  payslip_sent_at: string | null;
}

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

// Export singleton instance
export const api = new ApiClient(API_BASE);
