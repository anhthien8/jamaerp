'use client';

import dynamic from 'next/dynamic';
import { Suspense, useEffect, useState, useCallback, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { laTruongPhong } from '@/lib/roles';
import { useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, ApiError, Project, ProjectTask, ProjectKanban, TaskActivity, User, Material, Contract, Quotation, extractItems, fetchAllPages } from '@/lib/api';
import { nenAnh, blobThanhDataUrl } from '@/lib/anh';
import LyDoTamDung from '@/components/projects/LyDoTamDung';
import FormCongViec from '@/components/projects/FormCongViec';
import YeuCauVatTu from '@/components/projects/YeuCauVatTu';
import { formatCurrency, cn } from '@/lib/utils';
import { useToast } from '@/components/ui/Toast';
import AccessDenied from '@/components/ui/AccessDenied';
import LineIcon from '@/components/ui/LineIcon';
import { statusConfig, STAGE_LABELS, DEPT_LABELS, STAGE_ORDER, DeadlineBadge, StageBlocks } from '@/components/projects/shared';

const ChiTietDuAn = dynamic(() => import('@/components/projects/ChiTietDuAn'), { ssr: false });
const ChiTietCongViec = dynamic(() => import('@/components/projects/ChiTietCongViec'), { ssr: false });
const FormDuAn = dynamic(() => import('@/components/projects/FormDuAn'), { ssr: false });


function ProjectsPageInner() {
  const { user, loading, effectivePermissions } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  // Chỉ TP Kinh doanh + Ban Giám đốc đánh dấu «Khách riêng của sale» (backend gác lại)
  const doiKhachRieng = !!user && (user.role === 'admin' || user.role === 'executive'
    || (user.department === 'SALES' && laTruongPhong(user)));
  const handleKhachRieng = async (giaTri: boolean) => {
    if (!selectedProject) return;
    try {
      const updated = await api.updateProject(selectedProject.id, { khach_rieng: giaTri });
      setSelectedProject(updated);
      setProjects(prev => prev.map(p => (p.id === updated.id ? updated : p)));
      toast(giaTri ? 'Đã đánh dấu khách riêng — sale hưởng 2%' : 'Đã bỏ đánh dấu khách riêng', 'success');
    } catch (e) {
      toast((e as Error).message || 'Không đổi được', 'error');
    }
  };

  const [projects, setProjects] = useState<Project[]>([]);
  const [kanbanData, setKanbanData] = useState<ProjectKanban[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [viewMode, setViewMode] = useState<'list' | 'pipeline' | 'tasks'>('pipeline');
  const [taskGroupMode, setTaskGroupMode] = useState<'stage' | 'department'>('stage');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterQuarter, setFilterQuarter] = useState<string>('all');
  const [showMyTasks, setShowMyTasks] = useState(false);
  const [searchProject, setSearchProject] = useState('');

  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  const [selectedTask, setSelectedTask] = useState<ProjectTask | null>(null);
  const [taskActivities, setTaskActivities] = useState<TaskActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [newActivityContent, setNewActivityContent] = useState('');
  const [newActivityMedia, setNewActivityMedia] = useState<string[]>([]);
  const [taskFileUrl, setTaskFileUrl] = useState('');
  const [dangTaiFile, setDangTaiFile] = useState(false);

  // Project form modal state
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [projectForm, setProjectForm] = useState({
    name: '', client_name: '', client_phone: '', address: '',
    project_type: 'design_build', total_value: '', start_date: '', target_end_date: '',
    budget_total: '', handover_date: '', warranty_months: '12',
    // PIC 4 bộ phận — trước đây form KHÔNG cho chọn nên prod có 113 dự án mà
    // pm_id/designer_id đều rỗng (đo 05/09).
    pm_id: '', designer_id: '', purchasing_id: '', sales_id: '',
  });
  const [savingProject, setSavingProject] = useState(false);
  const [showPauseReason, setShowPauseReason] = useState(false);
  const [pauseReason, setPauseReason] = useState('');

  // Task form modal state
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: '', stage: 'design', department: 'design', assigned_to: '' });
  const [users, setUsers] = useState<User[]>([]);
  const [savingTask, setSavingTask] = useState(false);

  // Linked documents (Feature 2 - contract & quotation status)
  const [projectContracts, setProjectContracts] = useState<Contract[]>([]);
  const [projectQuotations, setProjectQuotations] = useState<Quotation[]>([]);
  const [loadingLinkedDocs, setLoadingLinkedDocs] = useState(false);

  // Material request state (PMs)
  const [showMaterialRequest, setShowMaterialRequest] = useState(false);
  const [materialRequestForm, setMaterialRequestForm] = useState({ material_id: '', quantity: '', note: '' });
  const [materialsList, setMaterialsList] = useState<Material[]>([]);
  const [savingMaterialRequest, setSavingMaterialRequest] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const kanbanScrollRef = useRef<HTMLDivElement>(null);
  const kanbanAutoScrolled = useRef(false);

  // Nén ảnh (≤1600px JPG) rồi xếp vào hàng chờ ghi chú. Bấm «Đăng cập nhật»
  // mới tải lên Kho ảnh. Trước 23/10/2026 ảnh đi base64 thẳng vào cột
  // media_url 500 ký tự → Postgres từ chối, ảnh không bao giờ lưu được.
  const addImagesToMedia = async (files: File[]) => {
    const results: string[] = [];
    for (const f of files) {
      if (f.size > 25 * 1024 * 1024) { toast(`${f.name}: ảnh quá lớn (tối đa 25MB)`, 'error'); continue; }
      const blob = await nenAnh(f);
      if (!blob) { toast(`${f.name}: không đọc được ảnh (HEIC? chụp lại ở chế độ JPG)`, 'error'); continue; }
      results.push(await blobThanhDataUrl(blob));
    }
    if (results.length === 0) return;
    setNewActivityMedia(prev => [...prev, ...results]);
    toast(`Đã chọn ${results.length} ảnh — bấm «Đăng cập nhật» để lưu`, 'success');
  };

  // 23/10/2026: tài liệu (PDF/DWG/SKP…) tải thẳng từ ERP — bot đăng vào topic dự án
  // trong nhóm Kho ảnh và gắn làm file kết quả. Trước đó nhân viên phải tự gửi
  // Telegram rồi dán link, chủ dự án thấy làm khó nhân viên.
  const taiFileKetQua = async (file: File) => {
    if (!selectedTask || dangTaiFile) return;
    setDangTaiFile(true);
    try {
      const updated = await api.uploadTaskFile(selectedTask.id, file);
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? updated : t));
      setSelectedTask(updated);
      setTaskFileUrl(updated.final_file_url || '');
      toast(`Đã tải «${file.name}» lên làm file kết quả`, 'success');
    } catch (e: unknown) {
      toast((e as Error).message || 'Tải file thất bại', 'error');
    }
    setDangTaiFile(false);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const all = Array.from(files);
    e.target.value = '';
    const images = all.filter(f => f.type.startsWith('image/'));
    const docs = all.filter(f => !f.type.startsWith('image/'));
    if (images.length > 0) addImagesToMedia(images);
    for (const d of docs) await taiFileKetQua(d);
  };

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const params: Record<string, string> = {};
      if (filterStatus !== 'all') params.status = filterStatus;
      // Lấy đủ mọi trang — lọc/sắp xếp chạy phía trình duyệt (xem fetchAllPages).
      const data = await fetchAllPages(p => api.getProjects(p), params);
      setProjects(data);
    } catch (e) {
      console.warn('Projects API error:', e);
      setError('Không thể tải dữ liệu dự án. Vui lòng thử lại.');
      setProjects([]);
    } finally {
      setLoadingProjects(false);
    }
  }, [filterStatus]);

  const fetchKanbanData = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const data = await api.getProjectKanban();
      setKanbanData(data);
    } catch (e) {
      console.warn('Kanban API error:', e);
      setError('Không thể tải dữ liệu kanban. Vui lòng thử lại.');
      setKanbanData([]);
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const refreshData = useCallback(() => {
    if (viewMode === 'pipeline') {
      void fetchKanbanData();
    } else {
      void fetchProjects();
    }
  }, [viewMode, fetchKanbanData, fetchProjects]);

  useEffect(() => {
    if (user) void Promise.resolve().then(() => refreshData());
  }, [user, refreshData]);

  // Kanban trên mobile: khi cột đầu ('Thiết kế') trống, người dùng tưởng không có dự án.
  // Tự cuộn ngang tới cột đầu tiên CÓ dự án (chỉ mobile < 768px).
  useEffect(() => {
    if (viewMode !== 'pipeline') { kanbanAutoScrolled.current = false; return; }
    if (kanbanAutoScrolled.current) return;
    if (typeof window === 'undefined' || window.innerWidth >= 768) return;
    if (kanbanData.length === 0) return;
    const firstWithProjects = kanbanData.findIndex(col => col.count > 0);
    if (firstWithProjects <= 0) { kanbanAutoScrolled.current = true; return; }
    const container = kanbanScrollRef.current;
    if (!container) return;
    const target = container.children[firstWithProjects] as HTMLElement | undefined;
    if (target) {
      container.scrollTo({ left: target.offsetLeft - container.offsetLeft, behavior: 'smooth' });
      kanbanAutoScrolled.current = true;
    }
  }, [viewMode, kanbanData]);

  const openProjectDetail = async (project: Project) => {
    setSelectedProject(project);
    setTasks([]);
    setLoadingTasks(true);
    try {
      const [t, u] = await Promise.all([
        api.getProjectTasks(project.id),
        // getUsers() là API Nhân sự — trưởng nhóm bị cắt về nhóm mình, vai trò
        // tùy chỉnh không có canViewHR dính 403 → tên người phụ trách chéo phòng
        // hiển thị trống. Dropdown «Đảm nhận» cần đủ nhân sự các phòng.
        users.length === 0 ? api.getTaskAssignableUsers() : Promise.resolve(users),
      ]);
      setTasks(t);
      if (u.length > 0 && users.length === 0) setUsers(u);
    } catch {
      setTasks([]);
    } finally {
      setLoadingTasks(false);
    }
  };

  // Mở thẳng chi tiết dự án từ link thông báo (/projects?id=…), rồi gỡ `id`
  // khỏi URL để bấm lại cùng thông báo vẫn mở được.
  const searchParams = useSearchParams();
  const urlProjectId = searchParams.get('id');
  useEffect(() => {
    if (!urlProjectId || loadingProjects) return;
    router.replace('/projects', { scroll: false });
    const coSan = projects.find(p => p.id === urlProjectId);
    if (coSan) { void Promise.resolve().then(() => openProjectDetail(coSan)); return; }
    api.getProject(urlProjectId)
      .then(p => openProjectDetail(p))
      .catch(() => toast('Không mở được dự án này (đã xoá hoặc ngoài phạm vi của bạn)', 'error'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlProjectId, loadingProjects]);

  const openTaskDetail = async (task: ProjectTask) => {
    setSelectedTask(task);
    setTaskFileUrl(task.final_file_url || '');
    setNewActivityMedia([]);
    setTaskActivities([]);
    setLoadingActivities(true);
    try {
      const acts = await api.getTaskActivities(task.id);
      setTaskActivities(acts);
    } catch {
      setTaskActivities([]);
    } finally {
      setLoadingActivities(false);
    }
  };

  const handleTaskStatusChange = async (taskId: string, newStatus: string) => {
    try {
      const updated = await api.updateTaskStatus(taskId, newStatus);
      setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
      setSelectedTask(updated);

      // Refresh project progress
      if (selectedProject) {
        const updatedProj = await api.getProject(selectedProject.id);
        setProjects(prev => prev.map(p => p.id === updatedProj.id ? updatedProj : p));
        setSelectedProject(updatedProj);
      }
      refreshData();
      toast('Cập nhật trạng thái công việc thành công', 'success');
    } catch {
      toast('Lỗi khi cập nhật trạng thái', 'error');
    }
  };

  // ── Người đảm nhận (nhiều người) + hạn chốt (13/10/2026) ───────────────────
  // Mỗi lần đổi nhóm, backend thông báo in-app + Telegram cho TỪNG người mới.
  const luuNhomDamNhan = async (taskId: string, ids: string[]) => {
    if (!selectedProject) return;
    try {
      const updated = await api.setTaskAssignees(selectedProject.id, taskId, ids);
      setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
      setSelectedTask(prev => prev && prev.id === taskId ? updated : prev);
      toast(ids.length ? 'Đã cập nhật người đảm nhận' : 'Đã gỡ hết người đảm nhận', 'success');
    } catch {
      toast('Lỗi khi cập nhật người đảm nhận', 'error');
    }
  };

  const luuHanChot = async (taskId: string, ngay: string) => {
    if (!selectedProject) return;
    try {
      // Ô <input type="date"> cho 'YYYY-MM-DD'; gửi cuối ngày để hạn tính hết ngày đó.
      const updated = await api.setTaskDueDate(
        selectedProject.id, taskId, ngay ? `${ngay}T17:00:00` : null
      );
      setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
      setSelectedTask(prev => prev && prev.id === taskId ? updated : prev);
      toast(ngay ? 'Đã đặt hạn chốt' : 'Đã bỏ hạn chốt', 'success');
    } catch {
      toast('Lỗi khi đặt hạn chốt', 'error');
    }
  };

  const handleTaskFileSave = async () => {
    if (!selectedTask) return;
    try {
      const updated = await api.updateTaskFinalFile(selectedTask.id, taskFileUrl || null);
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? updated : t));
      setSelectedTask(updated);
      toast('Lưu file kết quả thành công', 'success');
    } catch {
      toast('Lỗi khi lưu file kết quả', 'error');
    }
  };

  const openMaterialRequest = async () => {
    setMaterialRequestForm({ material_id: '', quantity: '', note: '' });
    setShowMaterialRequest(true);
    try {
      const data = extractItems(await api.getMaterials());
      setMaterialsList(data);
    } catch {
      setMaterialsList([]);
    }
  };

  const handleSubmitMaterialRequest = async () => {
    if (!selectedProject || !materialRequestForm.material_id || !materialRequestForm.quantity) return;
    setSavingMaterialRequest(true);
    try {
      await api.useMaterial({
        material_id: materialRequestForm.material_id,
        project_id: selectedProject.id,
        quantity: Number(materialRequestForm.quantity),
        note: materialRequestForm.note || undefined,
      });
      toast('Yêu cầu vật tư thành công', 'success');
      setShowMaterialRequest(false);
    } catch {
      toast('Lỗi khi gửi yêu cầu vật tư', 'error');
    } finally {
      setSavingMaterialRequest(false);
    }
  };

  const handleAddTaskActivity = async () => {
    // Cho phép gửi khi CHỈ còn ảnh (không nội dung) — là trường hợp thử lại
    // sau khi gửi được một phần: nội dung đã nằm trong ghi chú đầu rồi.
    if (!selectedTask || (!newActivityContent.trim() && newActivityMedia.length === 0)) return;
    const content = newActivityContent.trim();
    // Backend nhận 1 media_url mỗi ghi chú → gửi tuần tự MỖI ẢNH một ghi chú,
    // ghi chú đầu mang nội dung. Trước 13/08/2026 chỉ ảnh [0] được gửi,
    // các ảnh sau lặng lẽ biến mất dù UI đếm đủ.
    const media: (string | undefined)[] = newActivityMedia.length > 0 ? newActivityMedia : [undefined];
    const created: TaskActivity[] = [];
    try {
      // Tải TẤT CẢ ảnh trong một lượt → nhóm Kho ảnh Telegram nhận một album
      // (trước 24/10/2026 mỗi ảnh một tin, nhóm bị spam).
      let urls: (string | undefined)[] = media.map(() => undefined);
      if (media[0]) {
        if (media.length > 1) toast(`Đang tải ${media.length} ảnh…`, 'info');
        const blobs = await Promise.all(media.map(async m => (await fetch(m!)).blob()));
        const up = await api.uploadMediaBatch(blobs, {
          projectId: selectedTask.project_id, kind: 'tien_do', caption: content || undefined,
        });
        urls = up.items.map(x => x.url);
      }
      for (let i = 0; i < media.length; i++) {
        const caption = `📷 Ảnh ${i + 1}/${media.length}` + (content ? ' (kèm ghi chú trên)' : '');
        const body = i === 0 && content ? content : caption;
        const url = urls[i];
        created.push(await api.createTaskActivity(selectedTask.id, body, url, url ? 'tien_do' : undefined));
      }
      setTaskActivities(prev => [...created.slice().reverse(), ...prev]);
      setNewActivityContent('');
      setNewActivityMedia([]);
      toast(
        media[0]
          ? (content ? `Đã lưu ghi chú + ${media.length} ảnh` : `Đã lưu ${media.length} ảnh`)
          : 'Thêm ghi chú thành công',
        'success',
      );
    } catch (err) {
      if (created.length > 0) {
        // Gửi được một phần: hiện phần đã lưu, giữ lại các ảnh chưa gửi để thử lại.
        // Nội dung đã đăng cùng ghi chú đầu → PHẢI xóa, không thì bấm thử lại
        // sẽ đăng lặp nguyên văn ghi chú một lần nữa.
        setTaskActivities(prev => [...created.slice().reverse(), ...prev]);
        setNewActivityMedia(prev => prev.slice(created.length));
        setNewActivityContent('');
        toast(`Đã lưu ${created.length}/${media.length} — các ảnh còn lại chưa gửi được, bấm Đăng cập nhật để thử lại`, 'error');
      } else {
        toast(err instanceof Error && err.message ? err.message : 'Lỗi khi thêm ghi chú', 'error');
      }
    }
  };

  const handleProjectStageChange = async (newStage: string) => {
    if (!selectedProject) return;
    // Nếu chọn "Tạm dừng" → hỏi lý do
    if (newStage === 'paused') {
      setShowPauseReason(true);
      setPauseReason('');
      return;
    }
    const doi = async (force: boolean) => {
      const updated = await api.updateProjectStage(selectedProject.id, newStage, force);
      setProjects(prev => prev.map(p => p.id === selectedProject.id ? updated : p));
      setSelectedProject(updated);
      refreshData();
      toast(`Đã chuyển dự án sang giai đoạn ${STAGE_LABELS[newStage]}`, 'success');
    };
    try {
      await doi(false);
    } catch (e) {
      // Còn việc mở → hỏi «vẫn hoàn thành?» (audit 27/10)
      if (e instanceof ApiError && e.status === 409 && e.data?.code === 'con_viec_mo') {
        if (!confirm(`${e.message}

Vẫn đánh dấu hoàn thành? (sẽ nghiệm thu HĐ thi công + tính hoa hồng)`)) return;
        try { await doi(true); } catch (e2) { toast(e2 instanceof Error ? e2.message : 'Lỗi khi cập nhật giai đoạn', 'error'); }
        return;
      }
      toast(e instanceof Error && e.message ? e.message : 'Lỗi khi cập nhật giai đoạn', 'error');
    }
  };

  const confirmPause = async () => {
    if (!selectedProject) return;
    try {
      const updated = await api.request(`/projects/${selectedProject.id}/stage`, {
        method: 'PUT', body: { stage: 'paused', pause_reason: pauseReason.trim() || null },
      });
      const u = updated as Record<string, unknown>;
      setProjects(prev => prev.map(p => p.id === selectedProject.id ? { ...p, ...u } as Project : p));
      setSelectedProject(prev => prev ? { ...prev, ...u } as Project : null);
      refreshData();
      setShowPauseReason(false);
      toast(`Đã tạm dừng dự án. Lý do: ${pauseReason || 'Không ghi rõ'}`, 'success');
    } catch {
      toast('Lỗi khi tạm dừng dự án', 'error');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    addImagesToMedia(Array.from(files));
    if (fileRef.current) fileRef.current.value = '';
  };

  // Open project form for create or edit
  const openProjectForm = (project?: Project) => {
    // Nạp danh sách nhân sự cho 4 ô chọn PIC. Trước đây `users` chỉ được nạp khi
    // mở THẺ dự án / form Thêm công việc, nên mở form dự án từ danh sách thì cả
    // 4 dropdown rỗng trơn (bắt được lúc tự kiểm 05/09).
    if (users.length === 0) {
      api.getTaskAssignableUsers().then(setUsers).catch(() => {});
    }
    if (project) {
      setEditingProject(project);
      setProjectForm({
        name: project.name,
        client_name: project.client_name,
        client_phone: project.client_phone || '',
        address: project.address || '',
        project_type: project.project_type || 'design_build',
        total_value: project.total_value ? String(project.total_value) : '',
        start_date: project.start_date || '',
        target_end_date: project.target_end_date || '',
        budget_total: project.budget_total ? String(project.budget_total) : '',
        handover_date: project.handover_date ? project.handover_date.slice(0, 10) : '',
        warranty_months: String(project.warranty_months ?? 12),
        pm_id: project.pm_id || '',
        designer_id: project.designer_id || '',
        purchasing_id: project.purchasing_id || '',
        sales_id: project.sales_id || '',
      });
    } else {
      setEditingProject(null);
      setProjectForm({ name: '', client_name: '', client_phone: '', address: '', project_type: 'design_build', total_value: '', start_date: '', target_end_date: '', budget_total: '', handover_date: '', warranty_months: '12', pm_id: '', designer_id: '', purchasing_id: '', sales_id: '' });
    }
    setShowProjectForm(true);
  };

  const handleSaveProject = async () => {
    if (!projectForm.name.trim() || !projectForm.client_name.trim()) {
      toast('Tên dự án và tên khách hàng là bắt buộc', 'error');
      return;
    }
    setSavingProject(true);
    try {
      const payload: Partial<Project> = {
        name: projectForm.name.trim(),
        client_name: projectForm.client_name.trim(),
        client_phone: projectForm.client_phone.trim() || undefined,
        address: projectForm.address.trim() || undefined,
        project_type: projectForm.project_type,
        total_value: projectForm.total_value ? Number(projectForm.total_value) : undefined,
        start_date: projectForm.start_date || undefined,
        target_end_date: projectForm.target_end_date || undefined,
        budget_total: projectForm.budget_total ? Number(projectForm.budget_total) : undefined,
        handover_date: projectForm.handover_date || undefined,
        warranty_months: projectForm.warranty_months ? Number(projectForm.warranty_months) : undefined,
        // Gửi '' → undefined để bỏ trống PIC nghĩa là "chưa phân công", không phải chuỗi rỗng
        pm_id: projectForm.pm_id || undefined,
        designer_id: projectForm.designer_id || undefined,
        purchasing_id: projectForm.purchasing_id || undefined,
        sales_id: projectForm.sales_id || undefined,
      };
      if (editingProject) {
        const updated = await api.updateProject(editingProject.id, payload);
        setProjects(prev => prev.map(p => p.id === updated.id ? updated : p));
        if (selectedProject?.id === updated.id) setSelectedProject(updated);
        toast('Cập nhật dự án thành công', 'success');
      } else {
        const created = await api.createProject(payload);
        setProjects(prev => [created, ...prev]);
        toast('Tạo dự án mới thành công', 'success');
      }
      setShowProjectForm(false);
      refreshData();
    } catch (e: unknown) {
      // Trước 22/09 khối này là `catch {}` trống: nút «Tạo dự án mới» trả 422
      // «thiếu mã dự án» cho MỌI tài khoản mà người dùng chỉ thấy «Lỗi khi tạo
      // dự án» — không ai lần ra được nguyên nhân.
      const chiTiet = (e as Error)?.message?.trim();
      toast(
        chiTiet || (editingProject ? 'Lỗi khi cập nhật dự án' : 'Lỗi khi tạo dự án'),
        'error',
      );
    } finally {
      setSavingProject(false);
    }
  };

  // Open task creation form
  const openTaskForm = async () => {
    setTaskForm({ title: '', stage: selectedProject?.stage || 'design', department: 'design', assigned_to: '' });
    setShowTaskForm(true);
    try {
      const data = await api.getTaskAssignableUsers();
      setUsers(data);
    } catch {
      setUsers([]);
    }
  };

  const handleSaveTask = async () => {
    if (!selectedProject || !taskForm.title.trim()) return;
    setSavingTask(true);
    try {
      const newTask = await api.createTask(selectedProject.id, {
        title: taskForm.title.trim(),
        stage: taskForm.stage,
        department: taskForm.department || undefined,
        assigned_to: taskForm.assigned_to || undefined,
      });
      setTasks(prev => [...prev, newTask]);
      setShowTaskForm(false);
      toast('Thêm công việc thành công', 'success');
      refreshData();
    } catch {
      toast('Lỗi khi thêm công việc', 'error');
    } finally {
      setSavingTask(false);
    }
  };

  if (loading || !user) return <Sidebar><div className="p-6 space-y-4"><div className="skeleton h-8 w-48 rounded-xl" /><div className="grid grid-cols-4 gap-3">{[1,2,3,4].map(i => <div key={i} className="skeleton h-24 rounded-xl" />)}</div></div></Sidebar>;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <LineIcon name="alert" size={40} className="block mx-auto mb-4" />
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); refreshData(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }


  // effectivePermissions: gồm cả chức năng cấp riêng cho từng người (22/09),
  // nếu dùng getPermissions(role) trần thì cấp thêm quyền mà nút không hiện.
  const permissions = effectivePermissions;
  if (!permissions.canViewProjects) return <AccessDenied />;

  const activeCount = projects.filter(p => p.status === 'active').length;

  const calcProjectTimeLeft = (p: Project) => {
    if (!p.start_date || !p.target_end_date) return null;
    const start = new Date(p.start_date);
    const end = new Date(p.target_end_date);
    const now = new Date();
    const totalMs = end.getTime() - start.getTime();
    const elapsedMs = now.getTime() - start.getTime();
    const daysLeft = Math.max(0, Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
    const pct = Math.min(100, Math.max(0, (elapsedMs / totalMs) * 100));
    const totalDays = Math.ceil(totalMs / (1000 * 60 * 60 * 24));
    return { daysLeft, pct, totalDays, label: daysLeft > 0 ? `${daysLeft} ngày còn lại` : 'Quá hạn' };
  };

  // Group tasks for details modal
  const groupedTasks = {
    design: tasks.filter(t => t.stage === 'design'),
    quotation: tasks.filter(t => t.stage === 'quotation'),
    procurement: tasks.filter(t => t.stage === 'procurement'),
    construction: tasks.filter(t => t.stage === 'construction'),
    acceptance: tasks.filter(t => t.stage === 'acceptance'),
  };

  // Spec 07 A2 — nhóm theo PHÒNG BAN (mỗi phòng thấy ngay phần việc của mình)
  const groupedByDepartment = (() => {
    const groups: Record<string, typeof tasks> = {};
    for (const t of tasks) {
      const key = t.department || t.stage || 'khac';
      (groups[key] ||= []).push(t);
    }
    const stageIdx = (s: string) => {
      const i = (STAGE_ORDER as readonly string[]).indexOf(s);
      return i === -1 ? 99 : i;
    };
    const projStageIdx = selectedProject ? stageIdx(selectedProject.stage) : 0;
    return Object.entries(groups)
      .map(([dept, deptTasks]) => {
        const done = deptTasks.filter(t => t.status === 'done' || t.status === 'completed').length;
        const minStage = Math.min(...deptTasks.map(t => stageIdx(t.stage)));
        const started = deptTasks.some(t => t.status !== 'not_started' && t.status !== 'todo');
        return {
          dept,
          label: DEPT_LABELS[dept]?.label || STAGE_LABELS[dept] || 'Khác',
          color: DEPT_LABELS[dept]?.color || '#6B7280',
          tasks: deptTasks,
          done,
          pct: deptTasks.length ? Math.round((done / deptTasks.length) * 100) : 0,
          // Chưa tới lượt: chưa có việc nào bắt đầu VÀ giai đoạn dự án chưa chạm tới
          waiting: !started && minStage > projStageIdx,
          minStage,
        };
      })
      .sort((a, b) => a.minStage - b.minStage);
  })();

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 animate-in">
        {/* Header */}
        <div className="flex flex-col gap-4 mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Dự án</h1>
            {permissions?.canCreateProjects && (
              <button
                onClick={() => openProjectForm()}
                className="px-5 py-2.5 text-sm font-bold rounded-xl transition-all bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] shadow-lg shadow-[rgba(201,169,110,0.25)] min-h-[44px]"
              >
                + Dự án mới
              </button>
            )}
          </div>

          {/* View Toggle — prominent, full-width tabs */}
          <div className="flex rounded-xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--surface-2)]">
            <button
              onClick={() => setViewMode('pipeline')}
              className={cn(
                "flex-1 px-4 py-3 text-sm font-semibold transition-all text-center",
                viewMode === 'pipeline' ? "bg-[var(--gold-500)] text-white" : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
              )}
            >
              <LineIcon name="chart" size={16} className="inline-block align-[-2px] mr-1.5" />Kanban
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "flex-1 px-4 py-3 text-sm font-semibold transition-all text-center",
                viewMode === 'list' ? "bg-[var(--gold-500)] text-white" : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
              )}
            >
              <LineIcon name="clipboard" size={16} className="inline-block align-[-2px] mr-1.5" />Danh sách
            </button>
          </div>
        </div>

        {/* View Content */}
        {viewMode === 'list' ? (
          <>
            {/* Filter chips (Grid view only) */}
            <div className="flex gap-2 flex-wrap mb-4">
              {['all', ...Object.keys(statusConfig)].map((st) => (
                <button
                  key={st}
                  onClick={() => setFilterStatus(st)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: filterStatus === st ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
                    color: filterStatus === st ? 'var(--gold-400)' : 'var(--text-tertiary)',
                    border: `1px solid ${filterStatus === st ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                  }}
                >
                  {st === 'all' ? 'Tất cả' : statusConfig[st]?.label || st}
                </button>
              ))}
            </div>

            {/* Quarter filter */}
            <div className="flex gap-2 flex-wrap mb-6">
              <span className="text-xs text-[var(--text-muted)] self-center mr-1">Quý:</span>
              {[
                { key: 'all', label: 'Tất cả' },
                { key: 'Q1', label: 'Q1 (T1-T3)' },
                { key: 'Q2', label: 'Q2 (T4-T6)' },
                { key: 'Q3', label: 'Q3 (T7-T9)' },
                { key: 'Q4', label: 'Q4 (T10-T12)' },
              ].map(q => (
                <button
                  key={q.key}
                  onClick={() => setFilterQuarter(q.key)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: filterQuarter === q.key ? 'rgba(59,130,246,0.15)' : 'var(--surface-2)',
                    color: filterQuarter === q.key ? '#60A5FA' : 'var(--text-tertiary)',
                    border: `1px solid ${filterQuarter === q.key ? 'rgba(59,130,246,0.3)' : 'var(--border-subtle)'}`,
                  }}
                >
                  {q.label}
                </button>
              ))}
            </div>

            {/* Search + My Tasks filter row */}
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <input
                type="text"
                placeholder="Tìm dự án..."
                value={searchProject}
                onChange={e => setSearchProject(e.target.value)}
                className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none w-48"
              />
              {/* My Tasks toggle */}
              <label className="flex items-center gap-2 cursor-pointer self-center">
                <input
                  type="checkbox"
                  checked={showMyTasks}
                  onChange={e => setShowMyTasks(e.target.checked)}
                  className="rounded border-[var(--border-subtle)]"
                  style={{ accentColor: '#C9A96E' }}
                />
                <span className="text-xs text-[var(--text-secondary)]">Công việc của tôi</span>
              </label>
            </div>

            {loadingProjects ? (
              <div className="text-center py-20 text-[var(--text-muted)]">
                <div className="inline-block w-8 h-8 rounded-full border-2 border-[var(--gold-400)] border-t-transparent animate-spin" />
                <p className="text-sm mt-3">Đang tải dự án...</p>
              </div>
            ) : projects.length === 0 ? (
              <div className="text-center py-20 text-[var(--text-muted)]">
                <p>Chưa có dự án nào</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-fade-in">
                {projects
                  .filter(p => {
                    // Search filter
                    if (searchProject) {
                      const q = searchProject.toLowerCase();
                      if (!p.name.toLowerCase().includes(q) && !p.code.toLowerCase().includes(q) && !(p.client_name || '').toLowerCase().includes(q) && !(p.address || '').toLowerCase().includes(q) && !(p.project_type || '').toLowerCase().includes(q)) return false;
                    }
                    // My tasks filter (show only projects assigned to current user)
                    if (showMyTasks && user) {
                      if (p.pm_id !== user.id && p.designer_id !== user.id && p.sales_id !== user.id) return false;
                    }
                    if (filterQuarter === 'all') return true;
                    const month = new Date(p.created_at).getMonth() + 1;
                    if (filterQuarter === 'Q1') return month >= 1 && month <= 3;
                    if (filterQuarter === 'Q2') return month >= 4 && month <= 6;
                    if (filterQuarter === 'Q3') return month >= 7 && month <= 9;
                    if (filterQuarter === 'Q4') return month >= 10 && month <= 12;
                    return true;
                  })
                  .map((project) => {
                  const cfg = statusConfig[project.status] || { label: project.status, color: '#6B7280' };
                  const tl = calcProjectTimeLeft(project);
                  return (
                    <div
                      key={project.id}
                      className="rounded-2xl p-5 cursor-pointer transition-all hover:scale-[1.01]"
                      style={{
                        background: 'var(--surface-1)',
                        border: '1px solid var(--border-subtle)',
                      }}
                      onClick={() => openProjectDetail(project)}
                    >
                      {/* Project header */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 min-w-0 mr-2">
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-mono text-[var(--text-muted)]">{project.code}</span>
                            <span className="text-[9px] px-1 rounded bg-[var(--surface-3)] text-[var(--gold-400)]">{STAGE_LABELS[project.stage]}</span>
                          </div>
                          <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-0.5 truncate">{project.name}</h3>
                        </div>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0 font-medium" style={{
                          backgroundColor: `${cfg.color}20`,
                          color: cfg.color,
                        }}>
                          {cfg.label}
                        </span>
                      </div>

                      {/* Progress */}
                      <div className="mb-3">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[var(--text-muted)]">Tiến độ</span>
                          <span className="font-semibold text-[#C9A96E]">{project.progress}%</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/5">
                          <div className="h-full rounded-full transition-all" style={{
                            width: `${project.progress}%`,
                            background: `linear-gradient(90deg, #C9A96E, ${project.progress > 80 ? '#10B981' : '#C9A96E'})`,
                          }} />
                        </div>
                      </div>

                      {/* Time left bar */}
                      {tl && (
                        <div className="mb-3">
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-[var(--text-muted)]">Thời gian</span>
                            <span className="font-medium" style={{ color: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399' }}>
                              {tl.label}
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-white/5">
                            <div className="h-full rounded-full transition-all" style={{
                              width: `${tl.pct}%`,
                              background: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                            }} />
                          </div>
                        </div>
                      )}

                      {/* Client + values */}
                      <div className="flex justify-between items-end text-[10px] text-[var(--text-muted)] pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                        <span className="truncate max-w-[55%]"><LineIcon name="user" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{project.client_name}</span>
                        <span className="font-semibold text-[var(--text-secondary)]">{formatCurrency(project.total_value || (project.design_value || 0) + (project.construction_value || 0))}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          /* Kanban Board View */
          <>
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <input
                type="text"
                placeholder="Tìm dự án..."
                value={searchProject}
                onChange={e => setSearchProject(e.target.value)}
                className="px-3 py-1.5 rounded-xl text-xs bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none w-48"
              />
              <label className="flex items-center gap-2 cursor-pointer self-center">
                <input
                  type="checkbox"
                  checked={showMyTasks}
                  onChange={e => setShowMyTasks(e.target.checked)}
                  className="rounded border-[var(--border-subtle)]"
                  style={{ accentColor: '#C9A96E' }}
                />
                <span className="text-xs text-[var(--text-secondary)]">Công việc của tôi</span>
              </label>
            </div>
          <div ref={kanbanScrollRef} className="flex gap-4 overflow-x-auto pb-4 min-w-0 min-h-[60vh] select-none animate-fade-in">
            {kanbanData.map(col => (
              <div key={col.stage} className="flex-shrink-0 w-[82vw] max-w-[20rem] sm:w-80 snap-start rounded-2xl p-3 flex flex-col" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
                {/* Column Title */}
                <div className="flex items-center justify-between mb-4 px-1">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{
                      backgroundColor: col.stage === 'design' ? '#8B5CF6' :
                                      col.stage === 'quotation' ? '#3B82F6' :
                                      col.stage === 'procurement' ? '#F59E0B' :
                                      col.stage === 'construction' ? '#10B981' :
                                      col.stage === 'acceptance' ? '#06B6D4' : '#6B7280'
                    }} />
                    <span className="font-bold text-sm text-[var(--text-primary)]">{col.stage_label}</span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-white/5 text-[var(--text-muted)]">{col.count}</span>
                </div>

                {/* Column Cards */}
                <div className="flex-1 space-y-3 overflow-y-auto max-h-[55vh] pr-1">
                  {col.projects.filter(proj => {
                    // Search filter
                    if (searchProject) {
                      const q = searchProject.toLowerCase();
                      if (!proj.name.toLowerCase().includes(q) && !proj.code.toLowerCase().includes(q) && !(proj.client_name || '').toLowerCase().includes(q)) return false;
                    }
                    // My tasks filter
                    if (showMyTasks && user) {
                      if (proj.pm_id !== user.id && proj.designer_id !== user.id && proj.sales_id !== user.id) return false;
                    }
                    return true;
                  }).map(proj => (
                    <div
                      key={proj.id}
                      onClick={() => openProjectDetail(proj)}
                      className="rounded-xl p-4 cursor-pointer transition-all hover:bg-white/5"
                      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-[10px] font-mono text-[var(--text-muted)]">{proj.code}</span>
                        <DeadlineBadge project={proj} />
                      </div>
                      <h4 className="text-sm font-semibold text-white mb-2 truncate">{proj.name}</h4>

                      {/* Khung 5 giai đoạn — mọi phòng nhìn phát biết dự án đang ở đâu */}
                      <StageBlocks project={proj} />

                      {/* Progress bar */}
                      <div className="mb-3">
                        <div className="flex justify-between text-[10px] text-[var(--text-muted)] mb-1">
                          <span>Tiến độ</span>
                          <span className="font-semibold text-[var(--gold-400)]">{proj.progress}%</span>
                        </div>
                        <div className="h-1 rounded-full bg-white/5">
                          <div className="h-full rounded-full transition-all" style={{ width: `${proj.progress}%`, background: 'var(--gold-500)' }} />
                        </div>
                      </div>

                      {/* Client + Value */}
                      <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] pt-2 border-t border-white/5">
                        <span className="truncate max-w-[55%]"><LineIcon name="user" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{proj.client_name}</span>
                        <span className="font-semibold text-white">{formatCurrency(proj.total_value || (proj.design_value || 0) + (proj.construction_value || 0))}</span>
                      </div>
                    </div>
                  ))}
                  {col.count === 0 && (
                    <div className="text-center py-8 text-xs text-[var(--text-disabled)]">
                      Không có dự án
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          </>
        )}
      </div>

      {/* FAB "+ Dự án mới" — chỉ hiện trên mobile (desktop đã có nút ở header). Đẩy lên trên
          BottomNav (bottom-20) để không đè lên thanh điều hướng dưới. */}
      {permissions?.canCreateProjects && !selectedProject && (
        <button
          onClick={() => openProjectForm()}
          className="fixed bottom-20 right-6 z-40 lg:hidden flex items-center gap-2 px-5 py-3.5 rounded-full font-bold text-white shadow-2xl transition-transform active:scale-95 hover:scale-105"
          style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', boxShadow: '0 8px 24px rgba(201,169,110,0.4)' }}
          aria-label="Tạo dự án mới"
        >
          <span className="text-xl leading-none">＋</span>
          <span className="hidden sm:inline text-sm">Dự án mới</span>
        </button>
      )}

      {/* ── Project Detail Modal ── */}
      {selectedProject && (
        <ChiTietDuAn
          setSelectedProject={setSelectedProject}
          selectedProject={selectedProject}
          handleProjectStageChange={handleProjectStageChange}
          permissions={permissions}
          openProjectForm={openProjectForm}
          users={users}
          doiKhachRieng={doiKhachRieng}
          handleKhachRieng={handleKhachRieng}
          setTaskGroupMode={setTaskGroupMode}
          taskGroupMode={taskGroupMode}
          openMaterialRequest={openMaterialRequest}
          openTaskForm={openTaskForm}
          loadingTasks={loadingTasks}
          tasks={tasks}
          groupedByDepartment={groupedByDepartment}
          openTaskDetail={openTaskDetail}
          groupedTasks={groupedTasks}
          handleTaskStatusChange={handleTaskStatusChange}
          luuNhomDamNhan={luuNhomDamNhan}
        />
      )}

      {/* Pause Reason Modal */}
      {showPauseReason && (
        <LyDoTamDung
          setShowPauseReason={setShowPauseReason}
          pauseReason={pauseReason}
          setPauseReason={setPauseReason}
          confirmPause={confirmPause}
        />
      )}

      {/* ── Task Detail Modal (with Note timeline + File attachments) ── */}
      {selectedTask && (
        <ChiTietCongViec
          setSelectedTask={setSelectedTask}
          selectedTask={selectedTask}
          handleTaskStatusChange={handleTaskStatusChange}
          users={users}
          luuNhomDamNhan={luuNhomDamNhan}
          luuHanChot={luuHanChot}
          dangTaiFile={dangTaiFile}
          taiFileKetQua={taiFileKetQua}
          taskFileUrl={taskFileUrl}
          setTaskFileUrl={setTaskFileUrl}
          handleTaskFileSave={handleTaskFileSave}
          handleFileUpload={handleFileUpload}
          newActivityContent={newActivityContent}
          setNewActivityContent={setNewActivityContent}
          fileRef={fileRef}
          handleFileSelect={handleFileSelect}
          newActivityMedia={newActivityMedia}
          setNewActivityMedia={setNewActivityMedia}
          handleAddTaskActivity={handleAddTaskActivity}
          loadingActivities={loadingActivities}
          taskActivities={taskActivities}
        />
      )}

      {/* ── Project Create/Edit Form Modal ── */}
      {showProjectForm && (
        <FormDuAn
          setShowProjectForm={setShowProjectForm}
          editingProject={editingProject}
          projectForm={projectForm}
          setProjectForm={setProjectForm}
          user={user}
          users={users}
          handleSaveProject={handleSaveProject}
          savingProject={savingProject}
        />
      )}

      {/* ── Task Create Form Modal ── */}
      {showTaskForm && (
        <FormCongViec
          setShowTaskForm={setShowTaskForm}
          taskForm={taskForm}
          setTaskForm={setTaskForm}
          users={users}
          handleSaveTask={handleSaveTask}
          savingTask={savingTask}
        />
      )}

      {/* ── Material Request Modal ── */}
      {showMaterialRequest && (
        <YeuCauVatTu
          setShowMaterialRequest={setShowMaterialRequest}
          materialRequestForm={materialRequestForm}
          setMaterialRequestForm={setMaterialRequestForm}
          materialsList={materialsList}
          handleSubmitMaterialRequest={handleSubmitMaterialRequest}
          savingMaterialRequest={savingMaterialRequest}
        />
      )}
    </Sidebar>
  );
}

export default function ProjectsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><LineIcon name="hourglass" size={28} /></div>}>
      <ProjectsPageInner />
    </Suspense>
  );
}
