/**
 * API client — communicate with FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  params?: Record<string, string>;
}

/** Lỗi từ máy chủ, có kèm mã HTTP.
 *
 *  Trước 12/08/2026 mọi lỗi đều là Error trơn nên màn hình không phân biệt được
 *  "chưa được cấp quyền" (403) với "máy chủ đang lỗi" (500) — người dùng thấy chung
 *  một câu "Không thể tải dữ liệu" rồi tưởng hệ thống sập.
 */
export class ApiError extends Error {
  public data?: Record<string, unknown>;
  constructor(message: unknown, public status: number) {
    // Backend có thể trả detail dạng {message, ...} (VD lead trùng SĐT 409)
    const obj = message && typeof message === 'object' && !Array.isArray(message) ? message as Record<string, unknown> : undefined;
    super(obj ? String(obj.message ?? `HTTP ${status}`) : Array.isArray(message) ? `HTTP ${status}` : String(message));
    this.data = obj;
    this.name = 'ApiError';
  }
}

/** true nếu lỗi là do thiếu quyền (403), không phải sự cố hệ thống. */
export function laLoiThieuQuyen(e: unknown): boolean {
  return e instanceof ApiError && e.status === 403;
}

// Endpoint không cần đăng nhập — 401 ở đây nghĩa là "sai mật khẩu / sai mã",
// KHÔNG phải phiên hết hạn, nên tuyệt đối không được xóa phiên hay chuyển trang.
const ENDPOINT_CONG_KHAI = ['/auth/login', '/auth/telegram', '/auth/forgot-password', '/auth/reset-password'];

let daXuLyHetPhien = false;

/**
 * Token trong máy đã được thay bằng một token KHÁC (không phải bị xoá) kể từ lúc gửi request.
 *
 * Xảy ra khi máy này vừa nhận token mới qua X-Phien-Moi (gia hạn hằng ngày, đổi mật khẩu,
 * «Đăng xuất các thiết bị khác») trong lúc một request cũ — vd thông báo tự tải mỗi 60
 * giây — còn đang bay bằng token trước đó. Backend cắt phiên theo mốc thời gian nên
 * request cũ trả 401, nhưng máy này vẫn đăng nhập hợp lệ bằng token mới.
 */
function tokenDaDuocThay(tokenDaGui: string | null | undefined): boolean {
  if (typeof window === 'undefined' || !tokenDaGui) return false;
  const hienTai = localStorage.getItem('jama_token');
  return !!hienTai && hienTai !== tokenDaGui;
}

/**
 * Token hết hạn hoặc không hợp lệ (401) → xóa phiên chết, đưa về trang đăng nhập.
 *
 * Trước đây 401 chỉ bị ném ra như một lỗi thường: vỏ ứng dụng vẫn dựng lại từ
 * localStorage (còn tên, còn menu) trong khi mọi lời gọi đều hỏng, nên người dùng
 * chỉ thấy "Không thể tải dữ liệu. Vui lòng thử lại." ở mọi trang và bấm "Thử lại"
 * cũng vô ích vì vẫn gửi đúng cái token đã chết đó.
 *
 * `tokenDaGui` là token đã kèm theo request bị 401: nếu trong máy đã có token khác thì
 * 401 đó thuộc về token cũ — giữ nguyên phiên mới, không đá người dùng ra.
 */
function xuLyHetPhien(endpoint: string, tokenDaGui?: string | null) {
  if (typeof window === 'undefined') return;
  if (ENDPOINT_CONG_KHAI.some(p => endpoint.startsWith(p))) return;
  if (tokenDaDuocThay(tokenDaGui)) return;
  if (daXuLyHetPhien) return;
  daXuLyHetPhien = true;
  localStorage.removeItem('jama_token');
  localStorage.removeItem('jama_user');
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login?het_han=1';
  }
}

/** Đuôi query cho bộ lọc kỳ của Tổng quan. Backend nhận `tu`/`den` dạng
 *  YYYY-MM-DD theo giờ VN rồi tự quy đổi UTC. */
function _duoiKy(ky?: { from: string; to: string } | null): string {
  if (!ky) return '';
  const p = new URLSearchParams();
  if (ky.from) p.set('tu', ky.from);
  if (ky.to) p.set('den', ky.to);
  const q = p.toString();
  return q ? `?${q}` : '';
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

    let url = `${this.baseUrl}${endpoint}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const guiDi = (t: string | null) => fetch(url, {
      method,
      headers: this.headers(t ?? undefined),
      body: body ? JSON.stringify(body) : undefined,
    });

    let tokenDaGui = token || this.getToken();
    let res = await guiDi(tokenDaGui);

    // 401 vì token cũ vừa bị thay trong lúc request đang bay (gia hạn, đổi mật khẩu,
    // «Đăng xuất các thiết bị khác») → gửi lại đúng 1 lần bằng token mới. An toàn vì
    // 401 của phiên bị chặn ở get_current_user, trước khi handler kịp ghi gì. Endpoint
    // công khai (đăng nhập…) thì 401 là sai mật khẩu → không gửi lại.
    if (
      res.status === 401 && !token && tokenDaDuocThay(tokenDaGui)
      && !ENDPOINT_CONG_KHAI.some(p => endpoint.startsWith(p))
    ) {
      tokenDaGui = this.getToken();
      res = await guiDi(tokenDaGui);
    }

    // Phiên trượt (13/08/2026, nới 13/11/2026): token đã dùng quá 24 tiếng (đời 7 ngày)
    // thì backend kèm token mới trong header X-Phien-Moi — lưu đè để phiên tự dài ra.
    // Chỉ lưu khi đang dùng token phiên (không phải token truyền tay qua options).
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && !token && typeof window !== 'undefined') {
      localStorage.setItem('jama_token', tokenMoi);
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      if (res.status === 401) xuLyHetPhien(endpoint, tokenDaGui);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
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

  /**
   * Sửa thông tin lead. KHÔNG đổi được stage/lost_reason qua đây — dùng
   * changeStage(). Backend nay trả 422 nếu gửi field lạ; kiểu dữ liệu dưới đây
   * chặn sớm ngay từ lúc biên dịch.
   */
  /** Khảo sát trong tháng theo NVKD — GET /leads/khao-sat/thong-ke (10/11/2026). */
  async getThongKeKhaoSat(thang: string) {
    return this.request<ThongKeKhaoSat>('/leads/khao-sat/thong-ke', { params: { thang } });
  }

  /** Xoá người đã nghỉ khỏi danh sách nhân sự (ẩn, giữ lịch sử) — 10/11/2026. */
  async xoaNhanSuDaNghi(userId: string) {
    return this.request<{ status: string; message: string }>(`/hr/resigned/${userId}`, { method: 'DELETE' });
  }

  async updateLead(id: string, data: Omit<Partial<Lead>, 'stage' | 'lost_reason'>) {
    return this.request<Lead>(`/leads/${id}`, { method: 'PUT', body: data });
  }

  /**
   * Đổi giai đoạn lead — CỬA DUY NHẤT cho mọi chuyển stage, kể cả sang "Mất".
   * Đừng đổi stage qua updateLead(): PUT /leads/{id} không nhận stage/lost_reason
   * và Pydantic bỏ qua field lạ, nên nó trả 200 mà lead nằm y nguyên chỗ cũ.
   */
  async changeStage(id: string, newStage: string, opts?: { designContractValue?: number; note?: string; lostReason?: string; projectName?: string; projectBudget?: number; designSignedDate?: string }) {
    return this.request<Lead>(`/leads/${id}/stage`, {
      method: 'PUT',
      body: {
        new_stage: newStage,
        design_contract_value: opts?.designContractValue,
        project_name: opts?.projectName,
        project_budget: opts?.projectBudget,
        design_signed_date: opts?.designSignedDate,
        note: opts?.note,
        lost_reason: opts?.lostReason,
      },
    });
  }

  async assignLead(id: string, userId: string, note?: string) {
    return this.request<Lead>(`/leads/${id}/assign`, {
      method: 'POST',
      body: { user_id: userId, note },
    });
  }

  /** Giao hàng loạt — backend tự bỏ qua lead ngoài phạm vi (trả về skipped). */
  async bulkAssignLeads(leadIds: string[], userId: string) {
    return this.request<{ updated: number; skipped: number }>('/leads/bulk/assign', {
      method: 'POST',
      body: { lead_ids: leadIds, user_id: userId },
    });
  }

  /** Đổi giai đoạn hàng loạt. Backend chặn signed_design (side-effect phải chuyển từng lead). */
  async bulkChangeStage(leadIds: string[], newStage: string, lostReason?: string) {
    return this.request<{ updated: number; skipped: number }>('/leads/bulk/stage', {
      method: 'POST',
      body: { lead_ids: leadIds, new_stage: newStage, lost_reason: lostReason },
    });
  }

  async getActivities(leadId: string): Promise<Activity[]> {
    // Backend trả object phân trang {items,...} → chuẩn hoá về mảng.
    // Lấy tối đa backend cho phép (200): khối lognote CSKH trong thẻ chi tiết đọc từ
    // mảng này, mặc định 50 thì lead bận rộn sẽ KHUẤT mất đánh giá cũ (QC 05/09).
    const res = await this.request<Activity[] | { items: Activity[] }>(`/leads/${leadId}/activities`, { params: { page_size: '200' } });
    return Array.isArray(res) ? res : (res?.items ?? []);
  }

  /** Ảnh đính kèm ghi chú lead — data-URL JPG đã nén; trả id để chèn «🖼 anh:<id>» vào ghi chú */
  async uploadLeadImage(leadId: string, dataUrl: string) {
    return this.request<{ id: string; width: number; height: number; size_bytes: number }>(
      `/leads/${leadId}/attachments`, { method: 'POST', body: { data_base64: dataUrl } }
    );
  }
  /** Ảnh lead nằm sau JWT → fetch kèm token rồi trả blob URL cho <img> */
  async getLeadImageUrl(leadId: string, anhId: string): Promise<string> {
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/leads/${leadId}/attachments/${anhId}`, {
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
    if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
    return URL.createObjectURL(await res.blob());
  }
  async createActivity(leadId: string, data: { type: string; content: string }) {
    return this.request<Activity>(`/leads/${leadId}/activities`, {
      method: 'POST',
      body: data,
    });
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

  async createTask(projectId: string, data: { title: string; stage: string; department?: string; assigned_to?: string; assignee_ids?: string[]; due_date?: string }) {
    return this.request<ProjectTask>(`/projects/${projectId}/tasks`, { method: 'POST', body: data });
  }

  async getProjectKanban() {
    return this.request<ProjectKanban[]>('/projects/pipeline/kanban');
  }

  async updateProjectStage(projectId: string, stage: string, force = false) {
    return this.request<Project>(`/projects/${projectId}/stage`, { method: 'PUT', body: force ? { stage, force } : { stage } });
  }

  async getTaskActivities(taskId: string) {
    return this.request<TaskActivity[]>(`/projects/tasks/${taskId}/activities`);
  }

  async createTaskActivity(taskId: string, content: string, mediaUrl?: string, kind?: ActivityKind) {
    return this.request<TaskActivity>(`/projects/tasks/${taskId}/activities`, {
      method: 'POST',
      body: { content, media_url: mediaUrl, kind },
    });
  }

  // ── Kho ảnh công trình (23/10/2026) ─────────────────────────────────────
  // Ảnh nằm ở nhóm Telegram «JAMA Công trình», DB chỉ giữ metadata; link
  // `/media/{id}/{sig}.jpg` đã ký nên <img> mở được không cần header.

  /** Tải 1 ảnh lên Kho ảnh. Multipart nên không đi qua request() (header JSON). */

  /** Nhiều ảnh một lượt → nhóm Kho ảnh Telegram nhận thành MỘT album thay vì N tin. */
  async uploadMediaBatch(files: Blob[], opts: { projectId: string; kind?: ActivityKind; caption?: string }) {
    const fd = new FormData();
    files.forEach((f, i) => fd.append('files', f, `anh${i}.jpg`));
    fd.append('project_id', opts.projectId);
    if (opts.kind) fd.append('kind', opts.kind);
    if (opts.caption) fd.append('caption', opts.caption);
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/media/upload-batch`, {
      method: 'POST',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: fd,
    });
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && typeof window !== 'undefined') localStorage.setItem('jama_token', tokenMoi);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Tải ảnh thất bại' }));
      if (res.status === 401) xuLyHetPhien('/media/upload-batch', t);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
    }
    return res.json() as Promise<{ items: (MediaFile & { deduped: boolean })[]; deduped_count: number }>;
  }

  // ── Thư viện mẫu hợp đồng / biên bản (25/10/2026) ──
  async getContractTemplates(includeHidden = false) {
    return this.request<{ items: ContractTemplate[]; can_manage: boolean }>(
      '/contract-templates', includeHidden ? { params: { include_hidden: '1' } } : {}
    );
  }
  async uploadContractTemplates(files: File[]) {
    const fd = new FormData();
    files.forEach(f => fd.append('files', f, f.name));
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/contract-templates`, {
      method: 'POST',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: fd,
    });
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && typeof window !== 'undefined') localStorage.setItem('jama_token', tokenMoi);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Tải mẫu lên thất bại' }));
      if (res.status === 401) xuLyHetPhien('/contract-templates', t);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
    }
    return res.json() as Promise<{ items: ContractTemplate[]; created: number; replaced: number }>;
  }
  async updateContractTemplate(id: string, data: Partial<Pick<ContractTemplate, 'name' | 'category' | 'is_active'>> & { contract_kind?: string }) {
    return this.request<ContractTemplate>(`/contract-templates/${id}`, { method: 'PATCH', body: data });
  }
  /** Mẫu nằm sau JWT → fetch kèm token rồi bấm tải bằng blob URL */
  async downloadContractTemplate(m: ContractTemplate) {
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/contract-templates/${m.id}/download`, {
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
    if (!res.ok) {
      if (res.status === 401) xuLyHetPhien('/contract-templates', t);
      throw new ApiError(`HTTP ${res.status}`, res.status);
    }
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = m.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }

  // ── Tệp hợp đồng đã ký (26/10/2026) ──
  async listContractFiles(contractId: string) {
    return this.request<{ items: ContractFile[] }>(`/contracts/${contractId}/files`);
  }
  async uploadContractFiles(contractId: string, files: File[]) {
    const fd = new FormData();
    files.forEach(f => fd.append('files', f, f.name));
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/contracts/${contractId}/files`, {
      method: 'POST',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: fd,
    });
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && typeof window !== 'undefined') localStorage.setItem('jama_token', tokenMoi);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Tải tệp lên thất bại' }));
      if (res.status === 401) xuLyHetPhien('/contracts', t);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
    }
    return res.json() as Promise<{ items: ContractFile[] }>;
  }
  /** Xem (PDF/ảnh mở tab mới) hoặc tải tệp HĐ — tệp nằm sau JWT nên đi qua blob URL */
  async openContractFile(contractId: string, f: ContractFile, xem: boolean) {
    const moTab = xem && (f.mime.includes('pdf') || f.mime.startsWith('image/'));
    const tab = moTab ? window.open('', '_blank') : null;
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/contracts/${contractId}/files/${f.id}/download?inline=${moTab}`, {
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
    if (!res.ok) {
      tab?.close();
      if (res.status === 401) xuLyHetPhien('/contracts', t);
      throw new ApiError(`HTTP ${res.status}`, res.status);
    }
    const url = URL.createObjectURL(new Blob([await res.blob()], { type: f.mime }));
    if (tab) {
      tab.location.href = url;
    } else {
      const a = document.createElement('a');
      a.href = url;
      a.download = f.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  async removeContractFile(contractId: string, fileId: string) {
    return this.request<{ ok: boolean }>(`/contracts/${contractId}/files/${fileId}`, { method: 'DELETE' });
  }

  /** Nhập danh sách nhân sự (Excel HCNS) → Hồ sơ 360°. apply=false chỉ xem trước. */
  async importEmployeesExcel(file: File, apply: boolean) {
    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('apply', apply ? 'true' : 'false');
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/hr/employees/import-excel`, {
      method: 'POST',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: fd,
    });
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && typeof window !== 'undefined') localStorage.setItem('jama_token', tokenMoi);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Nhập file thất bại' }));
      if (res.status === 401) xuLyHetPhien('/hr/employees/import-excel', t);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
    }
    return res.json() as Promise<KetQuaNhapNhanSu>;
  }

  async listMedia(projectId: string, page = 1) {
    return this.request<{ items: MediaFile[]; total: number; page: number }>('/media', {
      params: { project_id: projectId, page: String(page) },
    });
  }

  async patchMedia(id: string, data: { shared_with_customer?: boolean; caption?: string }) {
    return this.request<MediaFile>(`/media/${id}`, { method: 'PATCH', body: data });
  }

  async getMediaStatus() {
    return this.request<MediaStatus>('/media/status');
  }

  async testMedia() {
    return this.request<{ chat_id: string; message_id: number }>('/media/test', { method: 'POST', body: {} });
  }

  async retryMediaMirror() {
    return this.request<{ requeued: number }>('/media/mirror/retry', { method: 'POST', body: {} });
  }

  /** Tải file kết quả giai đoạn (PDF/DWG/SKP… ≤50MB) — bot đăng vào topic dự án, trả task đã gắn file */
  async uploadTaskFile(taskId: string, file: File) {
    if (file.size > 50 * 1024 * 1024) {
      throw new Error(`File ${Math.round(file.size / 1048576)}MB vượt 50MB — nén lại hoặc dán link Drive.`);
    }
    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('task_id', taskId);
    const t = this.getToken();
    const res = await fetch(`${this.baseUrl}/media/task-file`, {
      method: 'POST',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: fd,
    });
    const tokenMoi = res.headers.get('X-Phien-Moi');
    if (tokenMoi && typeof window !== 'undefined') localStorage.setItem('jama_token', tokenMoi);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Tải file thất bại' }));
      if (res.status === 401) xuLyHetPhien('/media/task-file', t);
      throw new ApiError(error.detail || `HTTP ${res.status}`, res.status);
    }
    return res.json() as Promise<ProjectTask>;
  }

  async updateTaskFinalFile(taskId: string, finalFileUrl: string | null) {
    return this.request<ProjectTask>(`/projects/tasks/${taskId}/final-file`, {
      method: 'PUT',
      body: { final_file_url: finalFileUrl },
    });
  }

  async viecCuaToi() {
    return this.request<ViecCuaToi[]>('/projects/tasks/mine');
  }

  async updateTaskStatus(taskId: string, status: string) {
    return this.request<ProjectTask>(`/projects/tasks/${taskId}/status`, {
      method: 'PUT',
      body: { status },
    });
  }

  /** Đặt lại TOÀN BỘ nhóm đảm nhận. Mảng rỗng = gỡ hết người. */
  async setTaskAssignees(projectId: string, taskId: string, userIds: string[]) {
    return this.request<ProjectTask>(`/projects/${projectId}/tasks/${taskId}/assign`, {
      method: 'PUT',
      body: { assignee_ids: userIds },
    });
  }

  /** Đặt / bỏ hạn thoả thuận của đầu việc (mốc nhắc «quá hạn»). */
  async setTaskDueDate(projectId: string, taskId: string, dueDate: string | null) {
    return this.request<ProjectTask>(`/projects/${projectId}/tasks/${taskId}/due-date`, {
      method: 'PUT',
      body: { due_date: dueDate },
    });
  }

  // Accounting
  async getTransactions(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Transaction>>('/accounting/transactions', { params });
  }

  async createTransaction(data: { type: string; category: string; description: string; amount: number; date: string; project_id?: string; user_id?: string }) {
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
  /** `ky` = khoảng ngày theo giờ VN (YYYY-MM-DD). Bỏ trống = toàn bộ lịch sử. */
  async getExecutiveDashboard(ky?: { from: string; to: string } | null) {
    return this.request<DashboardExecutive>(`/dashboard/executive${_duoiKy(ky)}`);
  }

  async getPersonalDashboard(ky?: { from: string; to: string } | null) {
    return this.request<DashboardPersonal>(`/dashboard/personal${_duoiKy(ky)}`);
  }

  // Bảng điều khiển Kinh doanh (13/10/2026) — một lần gọi trả cả màn hình.
  // Bỏ trống `ky` thì BACKEND tự lấy tháng này (khác Tổng quan mặc định «toàn
  // bộ»): mọi mục tiêu ở màn này là mục tiêu tháng.
  async getSalesDashboard(ky?: { from: string; to: string } | null, teamId?: string | null) {
    const duoi = _duoiKy(ky);
    const them = teamId ? `${duoi ? '&' : '?'}team_id=${encodeURIComponent(teamId)}` : '';
    return this.request<SalesDashboard>(`/dashboard/sales${duoi}${them}`);
  }

  async saveSalesTargets(payload: SalesTargets) {
    return this.request<SalesTargets>('/dashboard/sales/muc-tieu', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async suggestAction(leadId: string) {
    return this.request<AISuggestion>('/ai/suggest-action', {
      method: 'POST',
      params: { lead_id: leadId },
    });
  }

  async getSuggestionHistory(leadId: string) {
    return this.request<{ items: AISuggestionHistory[]; total: number }>(
      `/ai/suggestions/${leadId}`
    );
  }

  async markSuggestionOutcome(runId: string, outcome: 'done' | 'skipped', note?: string) {
    return this.request<AISuggestionHistory>(`/ai/suggestions/${runId}/outcome`, {
      method: 'POST',
      body: { outcome, note },
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
  async docCccd(data_base64: string) {
    return this.request<{ name?: string | null; national_id?: string | null; birthday?: string | null; gender?: string | null; address?: string | null }>('/customers/doc-cccd', { method: 'POST', body: { data_base64 } });
  }

  async generatePortalLink(customerId: string) {
    return this.request<{ portal_token: string; portal_url: string }>(`/customers/${customerId}/generate-portal-link`, { method: 'POST' });
  }

  // === ERP: Contracts ===
  async getContracts(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Contract>>('/contracts', { params });
  }
  async createContract(data: Partial<Contract>) {
    return this.request<Contract>('/contracts', { method: 'POST', body: data });
  }
  async updateContract(id: string, data: Partial<Contract>) {
    return this.request<Contract>(`/contracts/${id}`, { method: 'PUT', body: data });
  }
  async updatePayment(contractId: string, installmentIdx: number, proofImage?: string, partialAmount?: number) {
    const body: Record<string, unknown> = {};
    if (proofImage) body.evidence_url = proofImage;
    if (partialAmount && partialAmount > 0) { body.status = 'partial'; body.amount = partialAmount; }
    return this.request<Contract>(`/contracts/${contractId}/payments/${installmentIdx}`, {
      method: 'PUT',
      body: Object.keys(body).length ? body : undefined,
    });
  }
  /** Bỏ «đã thu» (ghi nhầm): đợt về chờ thu, giao dịch thu + hoa hồng chưa trả tự gỡ */
  async boDaThu(contractId: string, installmentIdx: number) {
    return this.request<Contract>(`/contracts/${contractId}/payments/${installmentIdx}`, { method: 'PUT', body: { status: 'pending' } });
  }
  /** Sửa lịch thu: số đợt, %, hạn thu (tổng % = 100; đợt đã thu giữ nguyên trạng thái) */
  async updateLichThu(contractId: string, dot: Array<{ name: string; percentage: number; due_date?: string | null; milestone?: string }>) {
    return this.request<Contract>(`/contracts/${contractId}/lich-thu`, { method: 'PUT', body: { dot } });
  }

  /** Phụ lục phát sinh (+) / giảm trừ (−): HĐ con, giá trị dự án tự cộng */
  async taoPhuLuc(contractId: string, data: { title: string; total_value: number; notes?: string }) {
    return this.request<Contract>(`/contracts/${contractId}/phu-luc`, { method: 'POST', body: data });
  }

  // === ERP: Quotations ===
  async getQuotations(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Quotation>>('/quotations', { params });
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
  async useMaterial(data: { material_id: string; project_id: string; quantity: number; note?: string }) {
    return this.request<unknown>('/inventory/use', { method: 'POST', body: { ...data, notes: data.note, note: undefined } });
  }
  async getLowStock() {
    return this.request<Material[]>('/inventory/low-stock');
  }

  // === ERP: Suppliers & Price Board ===
  async getSuppliers(params?: Record<string, string>) {
    return this.request<PaginatedResponse<Supplier>>('/suppliers', { params });
  }
  async createSupplier(data: Partial<Supplier>) {
    return this.request<Supplier>('/suppliers', { method: 'POST', body: data });
  }
  async updateSupplier(id: string, data: Partial<Supplier>) {
    return this.request<Supplier>(`/suppliers/${id}`, { method: 'PUT', body: data });
  }
  async getSupplierQuotes(supplierId: string) {
    // Backend trả {items, total} chứ không phải mảng thuần — trước 15/08/2026 FE
    // ép kiểu mảng rồi Array.isArray → luôn "Chưa có báo giá" dù DB có dữ liệu.
    const res = await this.request<{ items?: SupplierQuote[] } | SupplierQuote[]>(`/suppliers/${supplierId}/quotes`);
    return Array.isArray(res) ? res : (res.items ?? []);
  }
  async addSupplierQuote(supplierId: string, data: Partial<SupplierQuote>) {
    return this.request<SupplierQuote>(`/suppliers/${supplierId}/quotes`, { method: 'POST', body: data });
  }
  /** So sánh giá 1 vật tư giữa các NCC.
   *
   * Backend là POST /suppliers/compare, nhận {materials: [...]} và trả
   * {comparisons: [{material_name, best_price, quotes:[...]}]}. Trước 12/08/2026 hàm này
   * gọi GET kèm query → luôn 405, nút "So sánh" trong trang NCC không bao giờ chạy.
   * Phần rẻ nhất / trung bình / xu hướng do FE tự tính từ danh sách báo giá.
   * (params giữ lại để trình giải lập Chế độ Tập luyện vẫn nhận ra đường dẫn.)
   */
  async comparePrices(materialName: string): Promise<PriceComparison> {
    const res = await this.request<{ comparisons?: RawComparison[] }>('/suppliers/compare', {
      method: 'POST',
      body: { materials: [materialName] },
      params: { material_name: materialName },
    });
    // Trình giải lập Chế độ Tập luyện trả thẳng shape cũ — nhận cả hai.
    if (res && !('comparisons' in res)) return res as unknown as PriceComparison;
    const raw = res?.comparisons?.[0];
    const quotes = raw?.quotes ?? [];
    const prices = quotes.map(q => q.unit_price);
    const cheapest = prices.length ? Math.min(...prices) : 0;
    const avg = prices.length ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length) : 0;
    return {
      material_name: raw?.material_name || materialName,
      unit: quotes[0]?.unit || '',
      cheapest_price: cheapest,
      avg_price: avg,
      quotes: quotes.map(q => ({
        supplier_id: q.supplier_id,
        supplier_name: q.supplier_name,
        unit_price: q.unit_price,
        min_quantity: q.min_quantity ?? undefined,
        lead_time_days: q.lead_time_days ?? undefined,
        quote_date: q.quote_date,
        is_cheapest: q.unit_price === cheapest,
        // Backend chưa trả xu hướng giá — để 'stable' thay vì bịa mũi tên tăng/giảm.
        price_trend: 'stable' as const,
      })),
    };
  }

  // === ERP: Users (HR) ===
  async getUsers(params?: Record<string, string>) {
    return this.request<PaginatedResponse<User>>('/users', { params });
  }
  /**
   * Ứng viên nhận lead cho dropdown «Giao data» — GET /users/assignable.
   * Backend tự cắt phạm vi: admin/điều phối KD thấy toàn lực lượng KD;
   * trưởng nhóm (leader/sale_leader) chỉ thấy người nhóm mình + chính mình.
   * Không đòi quyền Nhân sự (khác GET /users) — chỉ trả tên/vai trò/nhóm.
   */
  async getAssignableSales(): Promise<User[]> {
    const items = await this.request<User[]>('/users/assignable');
    return (Array.isArray(items) ? items : [])
      .sort((a, b) => a.full_name.localeCompare(b.full_name, 'vi'));
  }
  /**
   * Người nhận việc dự án cho dropdown «Đảm nhận» — GET /users/task-assignable.
   * Khác GET /users (gate quyền Nhân sự + trưởng nhóm bị cắt về nhóm mình):
   * endpoint này gate theo Xem Dự án/Tạo Công việc và trả đủ nhân sự đang làm
   * việc, nhưng chỉ danh tính tối thiểu (tên/vai trò/bộ phận) — không SĐT/lương.
   */
  async getTaskAssignableUsers(): Promise<User[]> {
    const items = await this.request<User[]>('/users/task-assignable');
    return Array.isArray(items) ? items : [];
  }
  async getTeams() {
    return this.request<Team[]>('/users/teams');
  }
  async createTeam(data: { name: string; code: string; department?: string; leader_id?: string | null }) {
    return this.request<Team>('/users/teams', { method: 'POST', body: data });
  }
  async updateTeam(id: string, data: { name?: string; department?: string; leader_id?: string | null }) {
    return this.request<Team>(`/users/teams/${id}`, { method: 'PUT', body: data });
  }
  /** Danh sách ĐẦY ĐỦ thành viên của đội sau khi lưu — trưởng nhóm luôn được backend giữ lại */
  async setTeamMembers(id: string, userIds: string[]) {
    return this.request<{ team_id: string; member_count: number; added: number; removed: number }>(
      `/users/teams/${id}/members`, { method: 'PUT', body: { user_ids: userIds } }
    );
  }
  /** Giải tán đội — thành viên về «chưa xếp đội», lead chỉ mất nhãn đội. FE phải confirm trước. */
  async deleteTeam(id: string) {
    return this.request<{ message: string; members_cleared: number; leads_cleared: number }>(
      `/users/teams/${id}`, { method: 'DELETE' }
    );
  }
  /** Người Telegram bot đã gặp (nhóm/riêng) chưa gán tài khoản, kèm gợi ý nhân viên khớp tên — cần «Quản lý Users» */
  /** Ai đang không nhận được tin bot (13/11/2026): bị Telegram từ chối + chưa gán Telegram */
  async telegramKhongNhan() {
    return this.request<{
      bi_tu_choi: { id: string; full_name: string; department: string | null; telegram_user_id: number; ly_do: string; luc: string }[];
      chua_gan: { id: string; full_name: string; department: string | null }[];
    }>('/users/telegram-khong-nhan');
  }
  async getTelegramContacts() {
    return this.request<TelegramContact[]>('/users/telegram-contacts', { params: { unlinked: 'true' } });
  }
  /** Gán Telegram ID cho nhân viên — trùng người khác → 400 */
  async linkTelegram(userId: string, tgUserId: number) {
    return this.request<{ id: string; full_name: string; telegram_user_id: number }>(
      `/users/${userId}/link-telegram`, { method: 'POST', body: { tg_user_id: tgUserId } }
    );
  }
  async createUser(data: Partial<User> & { password: string }) {
    return this.request<User>('/users', { method: 'POST', body: data });
  }
  async updateUser(id: string, data: Partial<Omit<User, 'team_id'>> & { team_id?: string | null }) {
    // team_id chấp nhận null tường minh = gỡ khỏi đội (backend exclude_unset — undefined sẽ bị JSON bỏ qua)
    return this.request<User>(`/users/${id}`, { method: 'PUT', body: data });
  }

  async doiHoTen(id: string, full_name: string) {
    // Chỉ Ban Giám đốc + Kế toán/Nhân sự — đổi ngay trên Hồ sơ 360°
    return this.request<{ id: string; full_name: string }>(`/users/${id}/full-name`, { method: 'PUT', body: { full_name } });
  }

  // === Per-user permission overrides (admin only) ===
  async getUserPermissions(userId: string) {
    return this.request<{ user_id: string; role: string; custom_permissions: Record<string, boolean> | null; combined_permissions: Record<string, boolean> }>(
      `/users/${userId}/permissions`
    );
  }
  async setUserPermissions(userId: string, permissions: Record<string, boolean>) {
    return this.request<{ user_id: string; custom_permissions: Record<string, boolean> | null; message: string }>(
      `/users/${userId}/permissions`, { method: 'PUT', body: { permissions } }
    );
  }

  // === Custom roles (stored in system_settings) ===
  async getCustomRoles() {
    return this.request<{ roles: Array<{ role_key: string; role_name: string; department: string; permissions: Record<string, boolean> }> }>('/users/roles/custom');
  }
  async createCustomRole(data: { role_key: string; role_name: string; department: string; permissions: Record<string, boolean> }) {
    return this.request<{ role: { role_key: string; role_name: string; department: string; permissions: Record<string, boolean> }; message: string }>('/users/roles', { method: 'POST', body: data });
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
  async myAttendance(period?: string, userId?: string) {
    const params: Record<string, string> = {};
    if (period) params.period = period;
    if (userId) params.user_id = userId;
    return this.request<{ summary: AttendanceSummary; records: AttendanceRecord[] }>(
      '/attendance/me', { params: Object.keys(params).length ? params : undefined }
    );
  }
  /** Sửa ca quên chấm — bắt buộc lý do (quản lý team / admin) */
  async editAttendance(recordId: string, body: { check_in?: string; check_out?: string; work_hours?: number; note: string }) {
    return this.request<{ record: AttendanceRecord }>(`/attendance/${recordId}`, { method: 'PATCH', body });
  }
  async ngayLe(nam?: number) {
    return this.request<{ nam: number; mac_dinh: string[]; them: string[]; tat_ca: string[] }>('/attendance/ngay-le', { params: nam ? { nam: String(nam) } : undefined });
  }
  async luuNgayLe(ngay: string[]) {
    return this.request<{ them: string[] }>('/attendance/ngay-le', { method: 'PUT', body: { ngay } });
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

  // === Chấm công văn phòng + máy chấm công (09/09) ===
  async getOfficeConfig() {
    return this.request<{
      office: {
        networks: string[]; lat: number | null; lng: number | null; radius_m: number;
        require_gps?: boolean; field_departments?: string[];
      };
      device: { enabled: boolean; api_key_masked: string | null; webhook_path: string };
    }>('/attendance/office-config');
  }
  async updateOfficeConfig(data: {
    networks: string[]; lat?: number | null; lng?: number | null; radius_m?: number;
    require_gps?: boolean; field_departments?: string[];
  }) {
    return this.request<{ office: unknown }>('/attendance/office-config', { method: 'PUT', body: data });
  }
  async rotateDeviceKey() {
    return this.request<{ api_key: string; enabled: boolean }>('/attendance/device-key/rotate', { method: 'POST' });
  }
  async toggleDevice(enabled: boolean) {
    return this.request<{ enabled: boolean }>('/attendance/device-config', { method: 'PUT', body: { enabled } });
  }

  // === Hồ sơ nhân viên 360° (09/09) ===
  async getEmployeeProfile(userId: string) {
    return this.request<{
      user: { id: string; full_name: string; email: string; phone: string | null; role: string; department: string | null; team_id: string | null; is_active: boolean; resign_date: string | null; avatar_url?: string | null };
      profile: EmployeeProfileData;
      documents: EmployeeDocumentMeta[];
      can_edit: boolean;
    }>(`/hr/employees/${userId}/profile`);
  }
  async updateEmployeeProfile(userId: string, data: EmployeeProfileData) {
    return this.request<{ profile: EmployeeProfileData }>(`/hr/employees/${userId}/profile`, { method: 'PUT', body: data });
  }
  async uploadEmployeeDocument(userId: string, data: { doc_type: string; filename: string; mime: string; data_base64: string }) {
    return this.request<{ id: string }>(`/hr/employees/${userId}/documents`, { method: 'POST', body: data });
  }
  async getEmployeeDocument(userId: string, docId: string) {
    return this.request<{ id: string; mime: string; filename: string; data_base64: string }>(`/hr/employees/${userId}/documents/${docId}`);
  }
  /** Ảnh đại diện: chính chủ hoặc admin/kế toán. Server tự cắt vuông 320px. */
  async uploadAvatar(userId: string, dataBase64: string) {
    return this.request<{ avatar_url: string | null }>(`/hr/employees/${userId}/avatar`, {
      method: 'PUT', body: { data_base64: dataBase64 },
    });
  }
  async deleteAvatar(userId: string) {
    return this.request<{ avatar_url: string | null }>(`/hr/employees/${userId}/avatar`, { method: 'DELETE' });
  }
  async deleteEmployeeDocument(userId: string, docId: string) {
    return this.request<{ deleted: boolean }>(`/hr/employees/${userId}/documents/${docId}`, { method: 'DELETE' });
  }
  async getEmployeeFinance(userId: string) {
    return this.request<EmployeeFinanceData>(`/hr/employees/${userId}/finance`);
  }
  async getEmployeeAttendance(userId: string, period?: string) {
    return this.request<{ summary: AttendanceSummary; records: AttendanceRecord[] }>(
      `/hr/employees/${userId}/attendance`, { params: period ? { period } : undefined }
    );
  }
  async getEmployeeLeaves(userId: string) {
    return this.request<{
      balance: { year: number; annual_total: number; annual_used: number; sick_used: number; unpaid_used: number };
      requests: { id: string; leave_type: string; start_date: string; end_date: string; days: number; reason: string; status: string; created_at: string }[];
    }>(`/hr/employees/${userId}/leaves`);
  }
  async getEmployeeHandovers(userId: string) {
    return this.request<{ given: HandoverItem[]; received: HandoverItem[] }>(`/hr/employees/${userId}/handovers`);
  }
  async getEmployeeAudit(userId: string) {
    return this.request<{ items: { id: string; action: string; actor_name: string | null; note: string | null; created_at: string }[] }>(`/hr/employees/${userId}/audit`);
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
  async resubmitRequest(id: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/resubmit`, { method: 'POST' });
  }
  async cancelRequest(id: string) {
    return this.request<{ request: ApprovalItem }>(`/approvals/${id}/cancel`, { method: 'POST' });
  }

  // === HR Phase 1: Nghỉ phép ===
  async createLeave(data: { leave_type: string; start_date: string; end_date: string; half_day?: boolean; reason: string }) {
    return this.request<{ leave: LeaveItem; approval_id: string }>('/leaves', { method: 'POST', body: data });
  }
  async huyDonNghi(id: string) {
    return this.request<{ leave: LeaveItem }>(`/leaves/${id}/huy`, { method: 'POST' });
  }
  async myLeaves() {
    return this.request<{ items: LeaveItem[] }>('/leaves/me');
  }
  async myLeaveBalance(year?: number) {
    return this.request<LeaveBalanceInfo>('/leaves/balance/me', { params: year ? { year: String(year) } : undefined });
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

  // === Tự đổi/đặt lại mật khẩu ===
  async changePassword(oldPassword: string, newPassword: string) {
    return this.request<{ status: string; message: string }>('/auth/change-password', {
      method: 'POST', body: { old_password: oldPassword, new_password: newPassword },
    });
  }
  // Đăng xuất mọi máy khác; máy đang dùng nhận token mới qua X-Phien-Moi (request() tự lưu)
  async logoutOtherDevices() {
    return this.request<{ status: string; message: string }>('/auth/logout-all', { method: 'POST' });
  }
  async forgotPassword(email: string) {
    return this.request<{ status: string; message: string }>('/auth/forgot-password', {
      method: 'POST', body: { email },
    });
  }
  async resetPassword(email: string, code: string, newPassword: string) {
    return this.request<{ status: string; message: string }>('/auth/reset-password', {
      method: 'POST', body: { email, code, new_password: newPassword },
    });
  }

  // === Phải thu theo hợp đồng (BOD/kế toán) ===
  async getReceivables() {
    return this.request<ReceivablesResponse>('/pl/receivables');
  }

  // === Zalo Listener (admin) — spec 09 ===
  async zaloSession() {
    return this.request<ZaloSessionInfo>('/zalo/session');
  }
  async zaloLogin() {
    return this.request<{ status: string; message: string }>('/zalo/session/login', { method: 'POST' });
  }
  async zaloLogout() {
    return this.request<{ status: string }>('/zalo/session/logout', { method: 'POST' });
  }
  async zaloGroups() {
    return this.request<{ items: ZaloGroupInfo[] }>('/zalo/groups');
  }
  async zaloUpdateGroup(id: string, patch: { kind?: string; assigned_user_id?: string | null; monitoring?: boolean; consent_ref?: string; department?: string }) {
    return this.request<{ id: string; monitoring: boolean; kind: string; department: string | null }>(`/zalo/groups/${id}`, { method: 'PATCH', body: patch });
  }
  async zaloSignals(status = 'new', filters: { type?: string; department?: string } = {}) {
    const params: Record<string, string> = { status };
    if (filters.type) params.type = filters.type;
    if (filters.department) params.department = filters.department;
    return this.request<{ items: ZaloSignalInfo[] }>('/zalo/signals', { params });
  }
  async zaloOverview() {
    return this.request<ZaloOverview>('/zalo/overview');
  }
  async zaloDigests(day?: string) {
    return this.request<ZaloDigestList>('/zalo/digests', { params: day ? { day } : undefined });
  }
  async zaloRunDigest(send = false) {
    return this.request<{ day: string; groups: number; sent: number }>('/zalo/digests/run', { method: 'POST', params: { send: String(send) } });
  }
  async zaloActSignal(id: string, action: 'actioned' | 'dismissed') {
    return this.request<{ id: string; status: string }>(`/zalo/signals/${id}/action`, { method: 'POST', body: { action } });
  }

  // === Chế độ thưởng + Hũ doanh số (23/10/2026) ===
  async cdtCauHinh(ky?: string) {
    return this.request<CdtCauHinhResp>('/che-do-thuong', { params: ky ? { ky } : undefined });
  }
  async cdtLuu(cau_hinh: CdtCauHinh) {
    return this.request<{ cau_hinh: CdtCauHinh; hieu_luc_tu: string }>('/che-do-thuong', { method: 'PUT', body: { cau_hinh } });
  }
  async cdtXemThu(ky: string) {
    return this.request<CdtBang>('/che-do-thuong/xem-thu', { params: { ky } });
  }
  async cdtChot(ky: string) {
    return this.request<{ luc: string; so_nguoi: number; tong: number; ky_luong: string; approval_id: string | null }>('/che-do-thuong/chot', { method: 'POST', params: { ky } });
  }
  async cdtLoaiTru(ky: string) {
    return this.request<{ ky: string; user_ids: string[]; ly_do: Record<string, string> }>('/che-do-thuong/loai-tru', { params: { ky } });
  }
  async cdtLuuLoaiTru(ky: string, user_ids: string[], ly_do: Record<string, string> = {}) {
    return this.request<{ ky: string; user_ids: string[] }>('/che-do-thuong/loai-tru', { method: 'PUT', params: { ky }, body: { user_ids, ly_do } });
  }
  async cdtHu() {
    return this.request<CdtHu>('/che-do-thuong/hu');
  }
  async cdtNguoi(userId: string, ky?: string) {
    return this.request<{ hien: false } | ({ hien: true; ky: string; quy: string } & CdtDong)>(`/che-do-thuong/nguoi/${userId}`, { params: ky ? { ky } : undefined });
  }

  // AI Tiến Hoá (13/11/2026) — chỉ admin
  async aiTienHoa(so_tuan = 12) {
    return this.request<AiTienHoa>('/ai/tien-hoa', { params: { so_tuan: String(so_tuan) } });
  }
  async aiTienHoaQuyet(code: string, huong: AiHuong | null, quyet_dinh: 'duyet' | 'tu_choi' | 'go') {
    return this.request<{ ok: boolean; bai_hoc: unknown }>('/ai/tien-hoa/bai-hoc', { method: 'POST', body: { code, huong, quyet_dinh } });
  }

  async getPnLProjects() {
    return this.request<PnLProject[]>('/pl/projects');
  }

  // Finance Module
  async getSalaryGrades() { return this.request<SalaryGrade[]>('/salary-grades'); }
  async importMaterials(rows: Array<Record<string, unknown>>) {
    return this.request<{ created: number; updated: number; errors: string[]; total: number }>('/inventory/import', { method: 'POST', body: { rows } });
  }
  async updateCommissionStatus(id: string, status: string) {
    return this.request<{ id: string; status: string }>(`/accounting/commissions/${id}`, { method: 'PUT', body: { status } });
  }

  async getFixedCosts(month?: string) { return this.request<FixedCost[]>('/fixed-costs', { params: month ? { month } : undefined }); }

  async getVariableCosts(month?: string) { return this.request<VariableCost[]>('/variable-costs', { params: month ? { month } : undefined }); }

  async getCommissionStructures() { return this.request<CommissionStructure[]>('/commission-structures'); }

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

  // === Web Push (thông báo ra điện thoại/máy tính) ===
  async pushPublicKey() {
    return this.request<{ enabled: boolean; public_key: string | null }>('/push/public-key');
  }
  async pushSubscribe(sub: PushSubscriptionJSON) {
    return this.request<{ ok: boolean }>('/push/subscribe', {
      method: 'POST',
      body: { endpoint: sub.endpoint, keys: sub.keys, user_agent: navigator.userAgent.slice(0, 255) },
    });
  }
  async pushUnsubscribe(endpoint: string) {
    return this.request<{ ok: boolean }>('/push/unsubscribe', { method: 'POST', body: { endpoint } });
  }
  async pushTest() {
    // 25/10/2026: trả kết quả thật từng máy (devices, sent, codes, reason) để Cài đặt báo lỗi đúng chỗ
    return this.request<{ ok: boolean; devices: number; sent: number; codes: number[]; reason?: string }>('/push/test', { method: 'POST' });
  }

  // ── Vật tư Đợt 1 (25/10/2026): danh mục mẫu · phiếu chọn theo dự án · hỏi giá NCC ──
  // Giá vốn/NCC/lãi chỉ có trong JSON khi backend cho vai đó xem (thay_gia_von).
  async vatTuTongQuan() {
    return this.request<VatTuTongQuan>('/vat-tu/tong-quan');
  }
  async vatTuMau(params?: Record<string, string>) {
    return this.request<{ items: MauVatTu[]; total: number; thay_gia_von: boolean }>('/vat-tu/mau', { params });
  }
  async vatTuNhom() {
    return this.request<{ nhom: string; so_mau: number; phan_tram_lai: number | null }[]>('/vat-tu/nhom');
  }
  async vatTuTaoMau(body: Partial<MauVatTu>) {
    return this.request<MauVatTu>('/vat-tu/mau', { method: 'POST', body });
  }
  async vatTuSuaMau(id: string, body: Partial<MauVatTu>) {
    return this.request<MauVatTu>(`/vat-tu/mau/${id}`, { method: 'PUT', body });
  }
  /** Tải ảnh mẫu từ máy (JPG base64 đã nén) → anh_url ký HMAC để gắn vào mẫu. Thu mua. */
  async vatTuTaiAnh(data_base64: string) {
    return this.request<{ id: string; anh_url: string; size_bytes: number }>('/vat-tu/anh', { method: 'POST', body: { data_base64 } });
  }
  async vatTuImportSheet(url: string, ghiDe = false) {
    return this.request<{ doc_duoc: number; them: number; sua: number; ncc_moi?: number }>('/vat-tu/mau/import-sheet', { method: 'POST', body: { url, ghi_de: ghiDe } });
  }
  async vatTuCaiGia() {
    return this.request<{ nhom: string; phan_tram_lai: number }[]>('/vat-tu/cai-gia');
  }
  async vatTuLuuCaiGia(body: { nhom: string; phan_tram_lai: number }[]) {
    return this.request<{ ok: boolean }>('/vat-tu/cai-gia', { method: 'PUT', body });
  }
  async vatTuPhieu(projectId: string) {
    return this.request<PhieuVatTu>(`/vat-tu/du-an/${projectId}/dong`);
  }
  async vatTuThemDong(projectId: string, body: Partial<DongVatTu>) {
    return this.request<DongVatTu>(`/vat-tu/du-an/${projectId}/dong`, { method: 'POST', body });
  }
  async vatTuSuaDong(id: string, body: Partial<DongVatTu>) {
    return this.request<DongVatTu>(`/vat-tu/dong/${id}`, { method: 'PATCH', body });
  }
  async vatTuXoaDong(id: string) {
    return this.request<void>(`/vat-tu/dong/${id}`, { method: 'DELETE' });
  }
  async vatTuKhachDongY(id: string, ghiChu?: string) {
    return this.request<DongVatTu>(`/vat-tu/dong/${id}/khach-dong-y`, { method: 'POST', body: { ghi_chu: ghiChu || null } });
  }
  /** Thu mua đặt hàng: trong báo giá → «Đã đặt», vượt khối lượng/đơn giá/ngân sách → chờ Leader duyệt (13/11/2026). */
  async vatTuDatHang(id: string, body: { so_luong?: number | null; don_gia?: number | null }) {
    return this.request<DongVatTu>(`/vat-tu/dong/${id}/dat-hang`, { method: 'POST', body });
  }
  async vatTuDuyetDat(id: string, dongY: boolean, lyDo?: string) {
    return this.request<DongVatTu>(`/vat-tu/dong/${id}/duyet-dat`, { method: 'POST', body: { dong_y: dongY, ly_do: lyDo || null } });
  }
  /** Giám sát xác nhận hàng về đủ/thiếu — anh_ids lấy từ uploadMediaBatch, tối thiểu 2 ảnh. */
  async vatTuNhanHang(id: string, body: { ket_qua: 'du' | 'thieu'; so_luong_nhan?: number | null; ghi_chu?: string; anh_ids: string[] }) {
    return this.request<DongVatTu>(`/vat-tu/dong/${id}/nhan-hang`, { method: 'POST', body });
  }
  async vatTuViecDatNhan() {
    return this.request<{ cho_duyet: DongVatTu[]; cho_nhan: DongVatTu[]; la_leader_thu_mua: boolean; so_anh_toi_thieu: number; nhan_cua_toi?: string[] }>('/vat-tu/viec-dat-nhan');
  }
  async vatTuCanHoiGia(trangThai?: string) {
    return this.request<{ items: DongVatTu[] }>('/vat-tu/can-hoi-gia', { params: trangThai ? { trang_thai: trangThai } : undefined });
  }
  async vatTuThemBaoGia(dongId: string, body: { supplier_id?: string | null; ncc_ten?: string; gia: number; con_hang?: boolean; ngay_giao?: string; ghi_chu?: string }) {
    return this.request<DongVatTu>(`/vat-tu/dong/${dongId}/bao-gia`, { method: 'POST', body });
  }
  async vatTuXoaBaoGia(id: string) {
    return this.request<void>(`/vat-tu/bao-gia/${id}`, { method: 'DELETE' });
  }
  async vatTuChot(dongId: string, body: { bao_gia_id?: string; gia_von?: number; supplier_id?: string | null; ncc_ten?: string }) {
    return this.request<DongVatTu>(`/vat-tu/dong/${dongId}/chot`, { method: 'POST', body });
  }
  async vatTuTimShopee(mauId: string, q?: string) {
    return this.request<{ tu_khoa: string; items: ShopeeSanPham[] }>(`/vat-tu/mau/${mauId}/shopee`, { params: q ? { q } : undefined });
  }
  async vatTuChonShopee(mauId: string, sp: { item_id: string; ten?: string; gia?: number | null; link_aff?: string | null }) {
    return this.request<MauVatTu>(`/vat-tu/mau/${mauId}/shopee`, { method: 'PUT', body: sp });
  }
  async vatTuBoShopee(mauId: string) {
    return this.request<MauVatTu>(`/vat-tu/mau/${mauId}/shopee`, { method: 'DELETE' });
  }
  async vatTuLinkAff(mauId: string, url: string) {
    return this.request<MauVatTu>(`/vat-tu/mau/${mauId}/shopee/link`, { method: 'POST', body: { url } });
  }
  async vatTuCanThuongLuong() {
    return this.request<{ items: CanThuongLuong[] }>('/vat-tu/can-thuong-luong');
  }
  async vatTuDsNcc() {
    return this.request<{ id: string; name: string; chiet_khau_pct: number }[]>('/vat-tu/ncc');
  }
  async traMaSoThue(mst: string) {
    return this.request<{ ma_so_thue: string; ten_cong_ty?: string | null; ten_ngan?: string | null; dia_chi?: string | null; trang_thai?: string | null }>(`/suppliers/tra-mst/${encodeURIComponent(mst.trim())}`);
  }
  async vatTuGoiYNcc(mauId: string) {
    return this.request<{ gia_shopee?: number | null; link_shopee_aff?: string | null; items: GoiYNcc[]; goi_y: GoiYNcc | null }>(`/vat-tu/mau/${mauId}/goi-y-ncc`);
  }
  async shopeeCaiDat() {
    return this.request<{ app_id: string; secret_masked: string; secret_set: boolean; san_sang: boolean }>('/shopee-settings');
  }
  async shopeeLuuCaiDat(body: { app_id?: string; secret?: string }) {
    return this.request<{ app_id: string; secret_masked: string; secret_set: boolean; san_sang: boolean }>('/shopee-settings', { method: 'PUT', body });
  }
  async shopeeThu() {
    return this.request<{ ok: boolean; so_ket_qua: number; vi_du: ShopeeSanPham[] }>('/shopee-settings/thu', { method: 'POST' });
  }

  // === Automation (admin/executive) ===
  async getAutomationSettings() {
    return this.request<AutomationSettings>('/automation/settings');
  }
  async updateAutomationSettings(data: Partial<{
    followup_reminder_days: number;
    lead_recall_days: number;
    lead_recall_enabled: boolean;
    zalo_digest_enabled: boolean;
    zalo_digest_hour: number;
    zalo_unanswered_hours: number;
    payment_reminder_days: number;
    bod_report_enabled: boolean;
    bod_report_hour: number;
    telegram_group_chat_id: string;
    storage_telegram_chat_id: string;
    group_briefing_enabled: boolean;
  }>) {
    return this.request<AutomationSettings>('/automation/settings', { method: 'PUT', body: data });
  }
  // SLA đầu việc (13/10/2026) — số ngày chuẩn cho từng đầu việc, sửa trong Cài đặt
  async getTaskSla() {
    return this.request<TaskSlaConfig>('/automation/task-sla');
  }
  async updateTaskSla(data: Partial<{
    dau_viec: Record<string, number>;
    phong_ban: Record<string, number>;
    leo_thang_ngay: number;
    bat: boolean;
  }>) {
    return this.request<TaskSlaConfig>('/automation/task-sla', { method: 'PUT', body: data });
  }
  async runTaskAlerts() {
    return this.request<{ task_overdue: number; task_sla_breach: number }>(
      '/automation/run/task-alerts', { method: 'POST' }
    );
  }

  async runAutomation(job: 'followups' | 'recall' | 'payments' | 'all') {
    return this.request<Record<string, unknown>>(`/automation/run/${job}`, { method: 'POST' });
  }
  async sendBodReport(period: 'daily' | 'weekly' | 'monthly') {
    return this.request<Record<string, unknown>>(`/automation/run/bod-report/${period}`, { method: 'POST' });
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
    fallbacks: { model: string; api_key?: string }[];
  }>) {
    return this.request<AISettingsResponse>('/ai-settings', { method: 'PUT', body: data });
  }
  async testAIConnection() {
    return this.request<{ status: string; model?: string; reply?: string; detail?: string;
      ket_qua?: { model: string; status: string; key_masked: string; reply?: string; detail?: string }[] }>(
      '/ai-settings/test', { method: 'POST' }
    );
  }

  // === Khóa AI cá nhân (mọi vai trò) — có key riêng thì AI ưu tiên dùng trước key hệ thống ===
  async getMyLlmKey() {
    return this.request<{ set: boolean; masked: string }>('/ai-settings/my-key');
  }
  async updateMyLlmKey(apiKey: string) {
    return this.request<{ set: boolean; masked: string }>(
      '/ai-settings/my-key', { method: 'PUT', body: { api_key: apiKey } }
    );
  }
  async testMyLlmKey() {
    return this.request<{ status: string; model?: string; reply?: string; detail?: string }>(
      '/ai-settings/my-key/test', { method: 'POST' }
    );
  }

  // === Sao lưu (chỉ admin) — backup toàn bộ dữ liệu, gửi file vào nhóm Telegram ===
  async getBackupSettings() {
    return this.request<BackupSettingsResponse>('/backup/settings');
  }
  async updateBackupSettings(data: Partial<{
    enabled: boolean;
    hour: number;             // 0-23 (giờ VN)
    retention_days: number;   // 1-180 (số ngày giữ bản local)
    telegram_chat_id: string; // "" để gỡ nhóm nhận backup
  }>) {
    return this.request<BackupSettingsResponse>('/backup/settings', { method: 'PUT', body: data });
  }
  async runBackupNow() {
    // Kết quả THẬT: thành công kèm dung lượng/thời gian, hoặc lỗi kèm lý do tiếng Việt.
    return this.request<
      | { status: 'success'; size_mb: number; duration_s: number; file_name: string; sent_telegram: boolean }
      | { status: 'error'; reason: string }
    >('/backup/run', { method: 'POST' });
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

  // ── Feedback ──
  async getFeedback(params?: Record<string, string>) {
    return this.request<PaginatedResponse<FeedbackItem>>('/feedback', { params });
  }
  async updateFeedback(id: string, data: { status?: string; admin_reply?: string }) {
    return this.request<FeedbackItem>(`/feedback/${id}`, { method: 'PUT', body: data });
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
  /** Ảnh đại diện — đường dẫn ký HMAC tương đối (/media/avatar/...); dùng qua mediaUrl() */
  avatar_url?: string | null;
  email: string;
  phone?: string;
  role: string;
  department: string;
  team_id?: string;
  telegram_user_id?: number;
  is_active: boolean;
  /** Cấu hình lương — admin/kế toán gán để payroll tính được (không gán = lương 0đ) */
  salary_grade_id?: string | null;
  dependents_count?: number;
  resign_date?: string;
  resigned_by?: string;
  /** Per-user permission overrides — null = use role defaults only */
  custom_permissions?: Record<string, boolean> | null;
  created_at: string;
}

export interface TelegramContact {
  tg_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  chat_title: string | null;
  last_seen_at: string | null;
  linked_user_id: string | null;
  linked_user_name: string | null;
  suggested_user_id: string | null;
  suggested_user_name: string | null;
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
  survey_date?: string | null;
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
  ngan_sach_khoang?: string | null;
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

// ── Vật tư (25/10/2026) ──
export interface MauVatTu {
  id: string; ma: string; ten?: string | null; hang?: string | null; nhom: string; be_mat?: string | null;
  don_vi: string; anh_url?: string | null; link_shopee?: string | null; ghi_chu?: string | null; tinh_trang?: string | null; is_active: boolean;
  // chỉ có khi được xem giá vốn
  gia_tham_khao?: number | null; gia_von_gan_nhat?: number | null; gia_von_cap_nhat_luc?: string | null;
  ncc_gan_nhat_ten?: string | null; gia_ban_co_dinh?: number | null;
  /** Giá khung quá 60 ngày chưa hỏi lại NCC */
  gia_cu?: boolean;
  // giá thị trường Shopee (mọi vai thấy) — 26/10/2026
  shopee_item_id?: string | null; shopee_ten?: string | null; link_shopee_aff?: string | null;
  gia_shopee?: number | null; gia_shopee_luc?: string | null;
}
export interface ShopeeSanPham {
  item_id: string; ten: string; gia: number | null; gia_max?: number | null; da_ban: number; sao?: number | null;
  shop?: string | null; anh?: string | null; link?: string | null; link_aff?: string | null; hoa_hong_pct: number;
}
export interface CanThuongLuong {
  bao_gia_id: string; dong_id: string; ncc_ten: string; supplier_id?: string | null; gia_ncc: number;
  gia_shopee: number; chenh: number; chenh_pct: number; mau_id: string; ma: string; hang?: string | null;
  don_vi: string; link_shopee_aff?: string | null; project_code?: string | null; duoc_chon: boolean; created_at?: string;
}
export interface GoiYNcc {
  supplier_id?: string | null; ncc_ten: string; gia: number; chiet_khau_pct: number; gia_sau_ck: number;
  da_mua: number; con_hang: boolean; bao_gia_luc?: string; cao_hon_shopee: boolean;
}
export interface BaoGiaVatTu {
  id: string; supplier_id?: string | null; ncc_ten: string; gia: number; con_hang: boolean;
  ngay_giao?: string | null; ghi_chu?: string | null; duoc_chon: boolean; created_at?: string;
  cao_hon_shopee?: boolean;
}
export type TrangThaiDongVatTu = 'khach_chon' | 'hoi_ncc' | 'het_hang' | 'cho_khach_duyet_lai' | 'da_chot_gia' | 'cho_duyet_dat' | 'da_dat' | 'giao_thieu' | 'da_giao' | 'huy';
export interface DongVatTu {
  id: string; project_id: string; phong: string; hang_muc?: string | null; mau_id?: string | null;
  ma?: string | null; hang?: string | null; nhom?: string | null; anh_url?: string | null; ma_tu_do?: string | null;
  so_luong: number; don_vi: string; trang_thai: TrangThaiDongVatTu; trang_thai_nhan: string; can_ngay?: string | null;
  mau_thay_the_id?: string | null; ma_thay_the?: string | null; ly_do_doi?: string | null;
  gia_ban?: number | null; thanh_tien?: number | null; chot_luc?: string | null;
  khach_dong_y_luc?: string | null; khach_ghi_chu?: string | null; ghi_chu?: string | null; thu_tu: number;
  created_at?: string; updated_at?: string; so_bao_gia: number;
  gia_shopee?: number | null; link_shopee_aff?: string | null;
  project_code?: string; project_name?: string; client_name?: string;
  // Đặt hàng – duyệt – nhận hàng (13/11/2026)
  sl_dat?: number | null; dat_luc?: string | null; dat_boi_ten?: string | null; ly_do_vuot?: string | null;
  duyet_dat_luc?: string | null; duyet_dat_boi_ten?: string | null; tu_choi_dat_ly_do?: string | null;
  nhan_ket_qua?: 'du' | 'thieu' | null; sl_nhan?: number | null; nhan_luc?: string | null; nhan_boi_ten?: string | null;
  nhan_ghi_chu?: string | null; nhan_anh?: { id: string; url: string }[];
  // chỉ có khi được xem giá vốn
  gia_dat?: number | null; gia_cu?: boolean;
  gia_von?: number | null; ncc_id?: string | null; ncc_ten?: string | null; phan_tram_ap_dung?: number | null;
  lai?: number | null; bao_gia?: BaoGiaVatTu[]; gia_von_gan_nhat?: number | null; gia_tham_khao?: number | null;
}
export interface PhieuVatTu {
  items: DongVatTu[]; tong_gia_ban: number; tong_lai?: number; thay_gia_von: boolean; co_the_chot: boolean;
}
export interface VatTuTongQuan {
  so_mau: number; theo_trang_thai: Record<string, number>; thay_gia_von: boolean; la_thu_mua: boolean;
  la_leader_thu_mua?: boolean; la_giam_sat?: boolean; so_anh_toi_thieu?: number; so_ngay_gia_cu?: number;
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
  /** PIC Báo giá – Thu mua (phòng PURCHASING), thêm 05/09/2026 */
  purchasing_id?: string;
  /** Khách riêng của sale → hoa hồng sale 2% thay 1% (JD, 24/10/2026) */
  khach_rieng?: boolean;
  start_date?: string;
  target_end_date?: string;
  budget_total?: number | null;
  handover_date?: string | null;
  warranty_months?: number;
  stage_acceptances?: Record<string, { at: string; note?: string; by?: string }> | null;
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
  /** BẢN SAO của một người trong nhóm — nhóm thật là `assignee_ids` (13/10/2026). */
  assigned_to?: string;
  /** Nhóm người đảm nhận, TẤT CẢ NGANG VAI (không chính/phụ). */
  assignee_ids?: string[];
  order: number;
  /** Hạn thoả thuận — trễ mốc này là «quá hạn». */
  due_date?: string;
  /** Mốc bắt đầu làm; đồng hồ SLA chạy từ đây. */
  started_at?: string;
  /** Hạn theo chuẩn nội bộ — trễ mốc này là «vi phạm SLA». */
  sla_due_at?: string;
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
  kind?: ActivityKind | null;
  created_at: string;
}

export type ActivityKind = 'tien_do' | 'su_co' | 'vat_tu' | 'cham_cong' | 'khac';

export interface MediaFile {
  id: string;
  url: string;
  width: number | null;
  height: number | null;
  caption: string | null;
  kind: ActivityKind;
  shared_with_customer: boolean;
  project_id: string | null;
  uploaded_by: string | null;
  user_name: string | null;
  mirror_status: string;
  created_at: string | null;
}

export interface MediaStatus {
  storage_chat_configured: boolean;
  drive_configured: boolean;
  total: number;
  pending: number;
  done: number;
  error: number;
  last_error: string | null;
}

/** Link ảnh từ backend: Kho ảnh trả đường dẫn tương đối `/media/...` → ghép
 *  API_BASE. Ảnh cũ (data-URL, http) giữ nguyên. */
export function mediaUrl(u?: string | null): string {
  if (!u) return '';
  if (u.startsWith('/media/')) return `${API_BASE}${u}`;
  return u;
}

export interface Transaction {
  id: string;
  code: string;
  type: string;
  category: string;
  description: string;
  amount: number;
  project_id?: string;
  /** Nhân viên liên quan — dùng cho giao dịch Lương/Hoa hồng gắn với một người cụ thể */
  related_user_id?: string | null;
  related_user_name?: string | null;
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
  period?: string | null;
  contract_id?: string | null;
  installment_idx?: number | null;
  note?: string | null;
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
  /** Việc quá hạn toàn công ty (task quá due_date chưa xong) — backend trả từ 13/08/2026 */
  overdue_tasks?: number;
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
  /** Hoa hồng đã duyệt kỳ gần nhất của chính user (backend chưa trả thì FE hiện —) */
  commission_month?: number;
  /** Lead/việc quá hạn phạm vi chính chủ — backend trả từ 13/08/2026 */
  overdue_leads?: number;
  overdue_tasks?: number;
}

/** Unified dashboard type — all fields optional since exec/personal have different shapes */
export type DashboardData = Partial<DashboardExecutive> & Partial<DashboardPersonal>;

// ── Bảng điều khiển Kinh doanh (13/10/2026) ─────────────────────────────────
// Khớp payload của GET /dashboard/sales. Tên trường để nguyên tiếng Việt như
// backend trả — đổi tên ở FE là mở đường cho lệch âm thầm khi backend sửa.

export interface SalesTargets {
  doanh_thu_thang: number;
  hd_thiet_ke_thang: number;
  hd_thi_cong_thang: number;
  khach_khao_sat_thang: number;
  ty_le_lien_he_toi_thieu: number;
  khu_vuc_trong_tam: string[];
  theo_nhom: Record<string, Record<string, number>>;
}

export interface SalesKpiCard {
  ma: 'doanh_thu' | 'hd_thiet_ke' | 'hd_thi_cong' | 'khach_khao_sat' | 'ty_le_lien_he';
  thuc_te: number;
  muc_tieu: number;
  muc_tieu_thang: number;
  /** Mục tiêu đã chia theo số ngày ĐÃ TRÔI QUA — phân biệt «mới ngày 14» với «đang chậm» */
  muc_tieu_tien_do: number;
  phan_tram: number;
  ky_truoc: number;
  delta_pct: number | null;
  dat_tien_do: boolean | null;
  don_vi: 'vnd' | 'hop_dong' | 'khach' | '%';
  /** Ngưỡng sàn (tỷ lệ liên hệ) — không chia theo ngày, không nhân theo tháng */
  la_nguong?: boolean;
}

export interface SalesFunnelStep {
  ma: string;
  nhan: string;
  so_luong: number;
  phan_tram_goc: number;
  phan_tram_buoc_truoc: number | null;
}

export interface SalesTeamRow {
  team_id: string | null;
  nhom: string;
  data_nhan: number;
  dat_tieu_chuan: number;
  pct_dat: number;
  khach_tinh: number;
  ngan_sach_thap: number;
  khong_dat: number;
  lien_he: number;
  khao_sat: number;
  bao_gia: number;
  ky_hd: number;
  doanh_so: number;
  muc_tieu: number;
  pct_muc_tieu: number | null;
}

export interface SalesPerson {
  user_id: string;
  ten: string;
  nhom: string;
  data: number;
  lien_he: number;
  khao_sat: number;
  bao_gia: number;
  ky_hd: number;
  doanh_so: number;
  pct_khao_sat: number;
  pct_bao_gia: number;
  pct_ky: number;
  pct_muc_tieu: number;
  ngay_cho_tb: number;
  ton_qua_han: number;
  van_de?: Array<{ ma: string; nhan: string; muc_do: 'gap' | 'canh_bao' }>;
  van_de_chinh?: string;
}

export interface SalesDashboard {
  ky: {
    tu: string; den: string; so_ngay: number | null;
    ky_truoc_tu: string | null; ky_truoc_den: string | null; he_so_thang: number;
  };
  team_id: string | null;
  danh_sach_nhom: Array<{ id: string; ten: string }>;
  cap_nhat_luc: string;
  muc_tieu: SalesTargets;
  kpi: SalesKpiCard[];
  chu_ky_6_thang: {
    tong: number; trung_binh: number; delta_pct: number | null;
    cao_nhat: { nhan: string; thuc_te: number } | null;
    thap_nhat: { nhan: string; thuc_te: number } | null;
  };
  doanh_so_theo_thang: Array<{ thang: string; nhan: string; thuc_te: number; muc_tieu: number }>;
  chat_luong_data: {
    tong: number; delta_pct: number | null;
    ro: Array<{ ma: string; nhan: string; so_luong: number; phan_tram: number }>;
  };
  hieu_suat_nhom: SalesTeamRow[];
  pheu: SalesFunnelStep[];
  top_nhan_vien: SalesPerson[];
  can_ho_tro: SalesPerson[];
  canh_bao: Array<{
    ma: string; tieu_de: string; so_luong: number;
    nhan_hanh_dong: string; muc_do: 'gap' | 'canh_bao' | 'theo_doi';
    metric: string | null;
  }>;
  // 6 khối đề xuất thêm
  toc_do_pipeline: Array<{ stage: string; nhan: string; so_luong: number; tuoi_tb: number; tuoi_max: number }>;
  ton_kho_lead: Array<{ nhan: string; so_luong: number; phan_tram: number; gia_tri: number }>;
  theo_nguon: Array<{
    nguon: string; tong: number; dat_chuan: number; khao_sat: number; ky_hd: number;
    gia_tri: number; pct_dat_chuan: number; pct_ky: number;
  }>;
  du_bao: {
    gia_tri_pipeline: number; du_bao_co_trong_so: number; con_thieu: number;
    theo_buoc: Array<{ stage: string; nhan: string; so_luong: number; gia_tri: number; xac_suat: number; du_bao: number }>;
  };
  ly_do_mat: Array<{ ly_do: string; so_luong: number; phan_tram: number }>;
  theo_ngan_sach: Array<{
    muc: string; nhan: string; tong: number; phan_tram: number;
    ky_hd: number; pct_ky: number; gia_tri: number;
  }>;
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
  /** Mã bản ghi trong bộ nhớ AI — gửi kèm khi bấm "Đã làm" / "Bỏ qua" */
  run_id?: string | null;
  /** 'llm' = do AI viết, 'rule' = do bộ luật sinh */
  source?: string;
  lich_su?: AISuggestionHistory[];
}

export interface AISuggestionHistory {
  run_id: string;
  action?: string;
  reason?: string;
  priority?: string;
  source: string;
  outcome?: string | null; // done | skipped | null
  outcome_note?: string | null;
  outcome_at?: string | null;
  created_at?: string | null;
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
  birthday?: string | null;
  national_id?: string | null;
  doanh_thu?: number;
  so_hop_dong?: number;
  so_du_an?: number;
  sinh_nhat_con_ngay?: number | null;
}

export type NhomMau = 'hop_dong' | 'bien_ban' | 'thanh_toan' | 'phu_luc' | 'khac';
export interface ContractFile {
  id: string;
  filename: string;
  mime: string;
  size_bytes: number;
  uploaded_by?: string | null;
  uploaded_by_name?: string | null;
  created_at?: string | null;
}

export interface ContractTemplate {
  id: string;
  name: string;
  category: NhomMau;
  contract_kind?: 'thiet_ke' | 'thi_cong' | null;
  filename: string;
  mime: string;
  size_bytes: number;
  version: number;
  is_active: boolean;
  updated_by_name?: string | null;
  updated_at?: string | null;
}

export interface Contract {
  id: string;
  code: string;
  project_id: string;
  quotation_id?: string;
  title: string;
  /** thiet_ke | thi_cong — quyết định hoa hồng thiết kế (JD). Trống = đoán theo tiêu đề */
  contract_kind?: 'thiet_ke' | 'thi_cong' | null;
  /** Phụ lục: id HĐ gốc */
  parent_contract_id?: string | null;
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
      due_date?: string;
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
  leader_id?: string | null;
  /** GET /users/teams trả kèm 2 trường này để UI vẽ thẳng, khỏi join tay */
  leader_name?: string | null;
  member_count?: number;
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
  // Backend schemas/pl.py trả total_cost/margin (page P&L map fallback cả 2 tên)
  // + start_date ISO nullable từ 05/09/2026 — dự án chưa nhập ngày là null.
  total_cost?: number;
  margin?: number;
  start_date?: string | null;
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
  budget_total?: number | null;
}

export interface ReceivableInstallment {
  name: string;
  percentage: number;
  amount: number;
  milestone?: string | null;
}

export interface ReceivableContract {
  contract_id: string;
  contract_code: string;
  project_code: string;
  project_name: string;
  signed_date?: string | null;
  total_value: number;
  pending_amount: number;
  pending_installments: ReceivableInstallment[];
}

export interface ReceivablesResponse {
  total_receivable: number;
  contract_count: number;
  contracts: ReceivableContract[];
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
  storage_telegram_chat_id?: string;
  group_briefing_enabled: string;
  zalo_digest_enabled?: string;
  zalo_digest_hour?: string;
  zalo_unanswered_hours?: string;
}

/** Cấu hình SLA đầu việc — `dau_viec`/`phong_ban` là bản HIỆU LỰC (mặc định đã
 *  trộn với phần admin sửa); `mac_dinh_*` để UI biết chỗ nào đang khác mặc định. */
export interface TaskSlaConfig {
  dau_viec: Record<string, number>;
  phong_ban: Record<string, number>;
  leo_thang_ngay: number;
  bat: boolean;
  mac_dinh_dau_viec: Record<string, number>;
  mac_dinh_phong_ban: Record<string, number>;
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
  enabled: boolean;
  hour: number;                 // giờ sao lưu hằng ngày (0-23, giờ VN)
  retention_days: number;       // số ngày giữ bản local
  telegram_chat_id: string;     // Chat ID nhóm Telegram nhận backup ("" nếu chưa đặt)
  telegram_configured: boolean; // đã đặt chat_id VÀ có TELEGRAM_BOT_TOKEN
  last_run_at: string | null;   // ISO giờ VN, null nếu chưa từng chạy
  last_status: 'success' | 'error' | 'never';
  last_detail: string;          // mô tả kết quả lần gần nhất
  last_size_mb: number | null;  // dung lượng bản backup gần nhất
}

export interface AISettingsResponse {
  llm_model: string;
  llm_api_key_masked: string;
  llm_api_key_set: boolean;
  llm_fallback_model: string;
  llm_fallback_api_key_masked: string;
  llm_fallback_api_key_set: boolean;
  fallbacks?: { model: string; api_key_masked: string; api_key_set: boolean }[];
  max_fallbacks?: number;
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
  // Đối chiếu văn phòng lúc check-in (09/09): null = không có gì để so
  ip_ok?: boolean | null;
  gps_ok?: boolean | null;
  work_hours: number;
  ot_hours: number;
  ot_status: 'none' | 'pending' | 'approved' | 'rejected';
  // Ai chốt OT + lúc nào (giờ UTC — FE tự +7 khi hiển thị)
  ot_decided_by_name?: string | null;
  ot_decided_at?: string | null;
  needs_review: boolean;
  note: string | null;
}

// === Hồ sơ nhân viên 360° (09/09/2026) ===
export interface EmployeeProfileData {
  national_id?: string | null;
  national_id_issued_date?: string | null;
  national_id_issued_place?: string | null;
  date_of_birth?: string | null;
  address?: string | null;
  emergency_contact?: string | null;
  bank_account?: string | null;
  bank_name?: string | null;
  social_insurance_no?: string | null;
  hire_date?: string | null;
  contract_type?: string | null;
  contract_signed_date?: string | null;
  contract_end_date?: string | null;
  note?: string | null;
  // Lương & BHXH từng người (24/10/2026) — bảng lương ưu tiên các ô này hơn bậc lương
  tax_code?: string | null;
  insurance_start_date?: string | null;
  contract_salary?: number | null;
  insurance_salary?: number | null;
  allowance_monthly?: number | null;
}

export interface KetQuaNhapNhanSu {
  tong_dong: number;
  khop: Array<{ user_id: string; ten: string; phong_ban: string | null; o_thay_doi: string[]; co_luong: boolean }>;
  khong_khop: Array<{ ten: string; phong_ban: string | null }>;
  trung_ten: Array<{ ten: string; so_tai_khoan: number }>;
  se_cap_nhat: number;
  da_ap_dung: boolean;
}

export interface EmployeeDocumentMeta {
  id: string;
  doc_type: string;
  filename: string;
  mime: string;
  size_bytes: number;
  uploaded_by_name: string | null;
  created_at: string;
}

export interface EmployeeFinanceData {
  payrolls: {
    id: string; period: string; status: string; base_salary: number;
    commission_total: number; bonus: number; allowance: number; ot_pay: number;
    work_days: number; gross: number; net: number; advance_deduction: number;
    paid_at: string | null;
  }[];
  commissions: {
    id: string; type: string; amount: number; status: string; milestone: string;
    period: string | null; project_id: string | null; created_at: string;
  }[];
  advances: {
    id: string; amount: number; reason: string; status: string;
    period_deducted: string | null; created_at: string;
  }[];
  transactions: {
    id: string; type: string; category: string; amount: number;
    description: string; transaction_date: string; status: string;
  }[];
  totals: { net_paid: number; commission_paid: number; commission_pending: number; advance_open: number };
}

export interface HandoverItem {
  id: string; entity_type: string; entity_id: string; entity_name: string;
  reason: string; from_user_name: string; to_user_name: string;
  actor_name: string | null; created_at: string;
}

export interface AttendanceSummary {
  period: string;
  records: number;
  work_days: number;
  work_days_fraction: number;
  total_hours: number;
  ot_approved_hours: number;
  needs_review: number;
  /** Công chuẩn tháng — chỉ có ở /attendance/me (22/10/2026) */
  standard_days?: number;
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

// === Zalo Listener types (spec 09) ===
export interface ZaloSessionInfo {
  status: 'logged_out' | 'awaiting_qr' | 'qr_ready' | 'logged_in' | 'error';
  qr_image: string | null;
  account_name: string | null;
  error_msg: string | null;
  ingest_online: boolean;
  last_seen: string | null;
}

export interface ZaloGroupInfo {
  id: string;
  zalo_group_id: string;
  name: string;
  kind: 'internal' | 'customer';
  assigned_user_id: string | null;
  monitoring: boolean;
  consent_ref: string | null;
  new_signals: number;
  department: string | null;
  member_count: number | null;
  last_message_at: string | null;
}

export interface ZaloOverview {
  scope: 'tat_ca' | 'phong';
  department: string | null;
  new_by_type: Record<string, number>;
  groups_monitored: number;
  listener_status: string;
}

export interface ZaloDigestItem {
  group_id: string;
  group_name: string;
  kind: 'internal' | 'customer';
  department: string | null;
  msg_count: number;
  summary: string;
  by_llm: boolean;
}

export interface ZaloDigestList {
  day: string | null;
  days: string[];
  items: ZaloDigestItem[];
}

export interface ZaloSignalInfo {
  id: string;
  type: 'lead_candidate' | 'commitment' | 'quote_request' | 'unanswered' | 'deal_risk' | 'faq';
  summary: string;
  status: 'new' | 'actioned' | 'dismissed';
  group_name: string;
  group_department?: string | null;
  group_kind?: 'internal' | 'customer';
  assigned_user_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

// === Supplier & Price Board types ===
export interface Supplier {
  id: string;
  name: string;
  /** Tên người liên hệ. Backend gọi là contact_name; FE từng gửi contact_person nên
   *  Pydantic lặng lẽ bỏ trường này khi tạo NCC (nhập xong là mất). Sửa 12/08/2026. */
  contact_name?: string;
  phone?: string;
  zalo?: string;
  email?: string;
  address?: string;
  region?: string;
  rating?: number;
  category: string; // wood | stone | metal | paint | electrical | plumbing | furniture | glass | general
  notes?: string;
  is_active: boolean;
  /** % chiết khấu NCC dành cho JAMA — dùng xếp gợi ý NCC (26/10/2026) */
  chiet_khau_pct?: number;
  /** Mã số thuế + tên pháp lý (tra từ Cục Thuế) — 26/10/2026 */
  ma_so_thue?: string | null;
  ten_cong_ty?: string | null;
  quote_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SupplierQuote {
  id: string;
  supplier_id: string;
  supplier_name?: string;
  material_name: string;
  material_category?: string;
  unit: string;
  unit_price: number;
  min_quantity?: number;
  lead_time_days?: number;
  notes?: string;
  /** Ngày báo giá. Bảng supplier_quotes KHÔNG có valid_from/valid_until —
   *  FE cũ hiện "HL đến ..." từ trường không tồn tại nên không bao giờ ra chữ. */
  quote_date: string;
}

/** Đúng shape thô backend trả về ở POST /suppliers/compare (trước khi FE tính thêm). */
export interface RawComparison {
  material_name: string;
  quote_count: number;
  best_supplier_id: string | null;
  best_supplier_name: string | null;
  best_price: number | null;
  quotes: Array<{
    supplier_id: string;
    supplier_name: string;
    unit_price: number;
    unit: string;
    min_quantity?: number | null;
    lead_time_days?: number | null;
    quote_date: string;
  }>;
}

export interface PriceComparison {
  material_name: string;
  unit: string;
  quotes: Array<{
    supplier_id: string;
    supplier_name: string;
    unit_price: number;
    min_quantity?: number;
    lead_time_days?: number;
    quote_date?: string;
    is_cheapest: boolean;
    price_trend: 'up' | 'down' | 'stable';
  }>;
  cheapest_price: number;
  avg_price: number;
}

// === Feedback types ===
export interface FeedbackItem {
  id: string;
  user_name: string | null;
  category: string;
  content: string;
  status: string;
  admin_reply: string | null;
  created_at: string;
}

// === Chế độ thưởng (23/10/2026) ===
export type CdtChuKy = 'thang' | 'quy';
export interface CdtMoc { doanh_so: number; quy: number; nhan: string; dat?: boolean }
export interface CdtCauHinh {
  quy_tran_thang: number;
  tu_dong_chot: boolean;
  chuong_trinh: {
    hu_doanh_so: { bat: boolean; chu_ky: CdtChuKy; moc: CdtMoc[]; cong_don: boolean; pham_vi: string; cach_chia: string; phong_nhan: string[]; bao_telegram: boolean; ai_thay_hu: string };
    chuyen_can: { bat: boolean; chu_ky: CdtChuKy; gio_vao_ca: string; tre_phut: number; tru_tre: number; tru_quen_ra: number; tru_nghi_khong_phep: number; thuong_du_cong: number };
    phan_hoi: { bat: boolean; chu_ky: CdtChuKy; phong: string[]; gio_goi: number; muc_tieu_goi: number; phut_zalo: number; muc_tieu_zalo: number; tru_qua_24h: number; thuong: number };
    danh_gia: { bat: boolean; chu_ky: CdtChuKy; thoi_diem: string[]; nguong_sao: number; thuong_du_an: number; thuong_khen: number };
    ngoi_sao: { bat: boolean; chu_ky: CdtChuKy; giai: number[] };
  };
  diem_jama: { trong_so: Record<string, Record<string, number>>; he_so: { tu: number; he_so: number }[] };
  dieu_kien: { con_lam_viec: boolean; thu_viec_pct: number; ky_luat_khong_nhan: boolean; nv_xem_diem: boolean };
}
export interface CdtCauHinhResp {
  ky: string; cau_hinh: CdtCauHinh; hieu_luc_tu: string | null; phien_ban: string[];
  lich_su: { luc: string; boi: string; hieu_luc_tu: string }[]; lan_luu_sau_ap_tu: string; mac_dinh: CdtCauHinh;
}
export interface CdtKhoan { ma: string; nhan: string; so_tien: number; chi_ky_nay: boolean }
export interface CdtDong {
  user_id: string; ten: string; phong: string | null; nhom: string | null; doanh_so: number;
  diem: number | null; he_so: number; thanh_phan: Record<string, number | null>;
  chi_tiet: Record<string, Record<string, unknown> | null>;
  khoan: CdtKhoan[]; tong: number; du_kien_cuoi_quy: number; ghi_chu: string[];
}
export interface CdtBang {
  ky: string; quy: string; cuoi_quy: boolean; hieu_luc_tu: string | null;
  chuong_trinh_bat: number; tong_chuong_trinh: number; tong_chi: number; quy_tran: number; vuot_tran: boolean;
  so_nguoi: number; so_nguoi_nhan: number;
  hu: { doanh_so: number; moc: CdtMoc[]; so_moc_dat: number; quy_mo: number; moc_tiep: CdtMoc | null; con_thieu: number } | null;
  du_an_danh_gia: { project_id: string; code: string; name: string; sao_tb: number; so_luot: number; khieu_nai: boolean; dat: boolean }[];
  ngoi_sao: { hang: number; user_id: string; ten: string; diem: number; giai: number }[];
  da_chot: { luc: string; boi: string; so_nguoi: number; tong: number; ky_luong: string; approval_id: string | null } | null;
  nguoi: CdtDong[];
}
export type CdtHu = { hien: false } | {
  hien: true; ky: string; nhan_ky: string; chu_ky: CdtChuKy; cong_don: boolean; doanh_so: number;
  moc: CdtMoc[]; so_moc_dat: number; quy_mo: number; quy_toi_da: number; moc_tiep: CdtMoc | null; con_thieu: number;
  ngay_da_qua: number; so_ngay: number;
  ca_nhan: { user_id: string; ten: string; doanh_so: number }[];
  doi: { team_id: string; ten: string; doanh_so: number }[];
};

// AI Tiến Hoá — tỷ lệ là số 0..1, null khi chưa có mẫu
export type AiHuong = 'uu_tien' | 'ha';
export interface AiTienHoaTuan {
  tuan: string; nhan: string; chay: number; llm: number; rule: number; dung_lai: number;
  lam: number; bo_qua: number; ty_le_lam_theo: number | null;
}
export interface AiBaiHoc {
  code: string; nhan: string; huong: AiHuong; trang_thai: 'cho_duyet' | 'dang_ap_dung' | 'da_bo_qua';
  de_xuat_moi: AiHuong | null; lam: number; bo_qua: number; noi_dung: string;
  quyet_boi: string | null; quyet_luc: string | null;
}
export interface AiTienHoa {
  so_tuan: number; tu_ngay: string;
  tong: {
    so_lan_chay: number; dung_lai: number; ty_le_dung_lai: number | null;
    llm: number; rule: number; ty_le_llm: number | null;
    so_goi_y: number; lam: number; bo_qua: number; ty_le_phan_hoi: number | null; ty_le_lam_theo: number | null;
    ty_le_lam_theo_4_tuan: number | null; ty_le_lam_theo_4_tuan_truoc: number | null; chenh_lech: number | null;
    ap_bai_hoc: { so_goi_y: number; lam: number; bo_qua: number; ty_le_lam_theo: number | null };
  };
  theo_tuan: AiTienHoaTuan[];
  theo_agent: { agent: string; ten: string; chay: number; llm: number; rule: number; dung_lai: number }[];
  model: { dang_bat: boolean; chinh: string | null; du_phong: string[]; da_tra_loi: { model: string; so_lan: number }[] };
  theo_loai: { code: string; nhan: string; lam: number; bo_qua: number; chua_phan_hoi: number; ty_le_lam: number | null; ty_le_bo_qua: number | null }[];
  bai_hoc: AiBaiHoc[];
  so_cho_duyet: number;
  nguong: { mau_toi_thieu: number; bo_qua: number; lam: number };
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

/** Tải HẾT các trang của một danh sách phân trang.
 *
 * Các trang Leads / Dự án / Khách hàng gọi API đúng một lần rồi lọc-sắp xếp phía trình
 * duyệt. Backend mặc định trả 50 bản ghi/trang, nên khi công ty vượt 50 lead thì phần dư
 * biến mất KHÔNG một lời báo, và mọi bộ lọc chỉ chạy trên 50 cái đầu — số liệu sai mà
 * nhìn vẫn bình thường. Hàm này lấy đủ mọi trang (200 bản/lượt, trần của backend).
 *
 * Có chốt chặn 50 trang (~10.000 bản ghi) để một API lỗi không kéo trình duyệt gọi vô tận.
 */
export async function fetchAllPages<T>(
  fetchPage: (params: Record<string, string>) => Promise<T[] | PaginatedResponse<T>>,
  params: Record<string, string> = {},
  pageSize = 200,
): Promise<T[]> {
  const first = await fetchPage({ ...params, page: '1', page_size: String(pageSize) });
  if (Array.isArray(first)) return first;
  const items = [...(first.items ?? [])];
  const totalPages = Math.min(first.total_pages ?? 1, 50);
  for (let p = 2; p <= totalPages; p++) {
    const next = await fetchPage({ ...params, page: String(p), page_size: String(pageSize) });
    items.push(...extractItems(next));
  }
  // Dữ liệu đổi giữa hai lần gọi trang (ai đó vừa sửa 1 dòng) → dòng trượt sang
  // trang sau và bị tải 2 lần — kanban Lead của TP Kinh doanh hiện thẻ trùng (13/11).
  const daCo = new Set<unknown>();
  return items.filter(it => {
    const id = (it as { id?: unknown }).id;
    if (id == null) return true;
    if (daCo.has(id)) return false;
    daCo.add(id);
    return true;
  });
}

// Export singleton instance
export const api = new ApiClient(API_BASE);

export interface ViecCuaToi {
  id: string; title: string; status: string; stage: string;
  project_id: string; project_code: string; project_name: string; han: string | null;
}

export interface ThongKeKhaoSat {
  thang: string;
  tong: number;
  da_ky: number;
  ty_le: number;
  theo_nguoi: { user_id: string | null; ten: string; khao_sat: number; da_ky: number; ty_le: number }[];
}
