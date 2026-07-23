'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { getPermissions, UserRole } from '@/lib/roles';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Project, ProjectTask, ProjectKanban, TaskActivity, User, Material, Contract, Quotation, extractItems } from '@/lib/api';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { useToast } from '@/components/ui/Toast';
import AccessDenied from '@/components/ui/AccessDenied';
import MoneyInput from '@/components/ui/MoneyInput';

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'Đang thực hiện', color: '#10B981' },
  on_hold: { label: 'Tạm dừng', color: '#F59E0B' },
  completed: { label: 'Hoàn thành', color: '#3B82F6' },
  cancelled: { label: 'Hủy', color: '#EF4444' },
};

const STAGE_LABELS: Record<string, string> = {
  design: 'Thiết kế',
  quotation: 'Báo giá',
  procurement: 'Thu mua',
  construction: 'Thi công',
  acceptance: 'Nghiệm thu & Bàn giao',
  completed: 'Hoàn thành',
  paused: 'Tạm dừng',
};

const DEPT_LABELS: Record<string, { label: string; color: string }> = {
  design: { label: 'Thiết kế', color: '#8B5CF6' },
  quotation: { label: 'Báo giá', color: '#F59E0B' },
  procurement: { label: 'Thu mua', color: '#10B981' },
  construction: { label: 'Thi công', color: '#3B82F6' },
  accounting: { label: 'Kế toán', color: '#EC4899' },
  sales: { label: 'Kinh doanh', color: '#F97316' },
};

// ── Spec 07: thanh tiến độ 5 khối + badge hạn chót ──────────────────────────
const STAGE_ORDER = ['design', 'quotation', 'procurement', 'construction', 'acceptance', 'paused'] as const;
const STAGE_SHORT: Record<string, string> = {
  design: 'Thiết kế', quotation: 'Báo giá', procurement: 'Thu mua',
  construction: 'Thi công', acceptance: 'Nghiệm thu',
};

function daysLeft(target?: string | null): number | null {
  if (!target) return null;
  const end = new Date(target).getTime();
  if (Number.isNaN(end)) return null;
  return Math.ceil((end - Date.now()) / 86_400_000);
}

function DeadlineBadge({ project }: { project: Project }) {
  if (project.status === 'completed' || project.status === 'cancelled') return null;
  const d = daysLeft(project.target_end_date);
  if (d === null) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-medium" style={{ background: 'rgba(107,114,128,0.15)', color: '#9CA3AF' }}>Chưa đặt hạn</span>;
  }
  if (d < 0) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(248,113,113,0.18)', color: '#F87171' }}>🔴 Quá hạn {-d} ngày</span>;
  }
  if (d <= 14) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(251,146,60,0.18)', color: '#FB923C' }}>🟠 Còn {d} ngày</span>;
  }
  return <span className="text-[9px] px-1.5 py-0.5 rounded font-medium" style={{ background: 'rgba(107,114,128,0.12)', color: '#9CA3AF' }}>Còn {d} ngày</span>;
}

function StageBlocks({ project }: { project: Project }) {
  const progress = project.stage_progress;
  if (!progress) return null;
  return (
    <div className="flex gap-1 mb-2" aria-label="Tiến độ theo giai đoạn">
      {STAGE_ORDER.map(stage => {
        const cell = progress[stage];
        const total = cell?.total ?? 0;
        const done = cell?.done ?? 0;
        let bg = 'rgba(255,255,255,0.08)'; // chưa bắt đầu
        if (total > 0 && done >= total) bg = '#10B981';       // xong
        else if (done > 0 || project.stage === stage) bg = '#F59E0B'; // đang làm
        return (
          <div
            key={stage}
            className="h-1.5 flex-1 rounded-full"
            style={{ background: bg }}
            title={`${STAGE_SHORT[stage]}: ${done}/${total} việc`}
          />
        );
      })}
    </div>
  );
}

const taskStatusConfig: Record<string, { label: string; color: string; icon: string }> = {
  done: { label: 'Xong', color: '#10B981', icon: '✅' },
  in_progress: { label: 'Đang làm', color: '#F59E0B', icon: '🔄' },
  not_started: { label: 'Chưa bắt đầu', color: '#6B7280', icon: '⏳' },
  todo: { label: 'Chờ', color: '#6B7280', icon: '⏳' },
  completed: { label: 'Hoàn thành', color: '#3B82F6', icon: '✅' },
};

export default function ProjectsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

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

  // Project form modal state
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [projectForm, setProjectForm] = useState({
    name: '', client_name: '', client_phone: '', address: '',
    project_type: 'design_build', total_value: '', start_date: '', target_end_date: '',
    budget_total: '', handover_date: '', warranty_months: '12',
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

  // File upload state (designers)
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);

  // Material request state (PMs)
  const [showMaterialRequest, setShowMaterialRequest] = useState(false);
  const [materialRequestForm, setMaterialRequestForm] = useState({ material_id: '', quantity: '', note: '' });
  const [materialsList, setMaterialsList] = useState<Material[]>([]);
  const [savingMaterialRequest, setSavingMaterialRequest] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const kanbanScrollRef = useRef<HTMLDivElement>(null);
  const kanbanAutoScrolled = useRef(false);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setUploadedFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const params: Record<string, string> = {};
      if (filterStatus !== 'all') params.status = filterStatus;
      const data = extractItems(await api.getProjects(params));
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
    if (user) refreshData();
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
      const t = await api.getProjectTasks(project.id);
      setTasks(t);
    } catch {
      setTasks([]);
    } finally {
      setLoadingTasks(false);
    }
  };

  const openTaskDetail = async (task: ProjectTask) => {
    setSelectedTask(task);
    setTaskFileUrl(task.final_file_url || '');
    setUploadedFiles([]);
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
    if (!selectedTask || !newActivityContent.trim()) return;
    try {
      // Append uploaded file info to content
      let content = newActivityContent.trim();
      if (uploadedFiles.length > 0) {
        const fileInfo = uploadedFiles.map(f => `[File: ${f.name} (${(f.size / 1024).toFixed(0)} KB)]`).join(' ');
        content = `${content}\n\nĐính kèm: ${fileInfo}`;
      }
      // Use first photo as media_url (API supports single URL)
      const act = await api.createTaskActivity(selectedTask.id, content, newActivityMedia[0] || undefined);
      setTaskActivities(prev => [act, ...prev]);
      setNewActivityContent('');
      setNewActivityMedia([]);
      setUploadedFiles([]);
      toast('Thêm ghi chú thành công', 'success');
    } catch {
      toast('Lỗi khi thêm ghi chú', 'error');
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
    try {
      const updated = await api.updateProjectStage(selectedProject.id, newStage);
      setProjects(prev => prev.map(p => p.id === selectedProject.id ? updated : p));
      setSelectedProject(updated);
      refreshData();
      toast(`Đã chuyển dự án sang giai đoạn ${STAGE_LABELS[newStage]}`, 'success');
    } catch {
      toast('Lỗi khi cập nhật giai đoạn', 'error');
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
    const validFiles = Array.from(files).filter(f => {
      if (f.size > 5 * 1024 * 1024) { toast(`${f.name}: tối đa 5MB`, 'error'); return false; }
      return true;
    });
    let loaded = 0;
    const results: string[] = [];
    validFiles.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        results.push(reader.result as string);
        loaded++;
        if (loaded === validFiles.length) {
          setNewActivityMedia(prev => [...prev, ...results]);
          toast(`Đã chọn ${results.length} ảnh`, 'success');
        }
      };
      reader.readAsDataURL(file);
    });
    if (fileRef.current) fileRef.current.value = '';
  };

  // Open project form for create or edit
  const openProjectForm = (project?: Project) => {
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
      });
    } else {
      setEditingProject(null);
      setProjectForm({ name: '', client_name: '', client_phone: '', address: '', project_type: 'design_build', total_value: '', start_date: '', target_end_date: '', budget_total: '', handover_date: '', warranty_months: '12' });
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
    } catch {
      toast(editingProject ? 'Lỗi khi cập nhật dự án' : 'Lỗi khi tạo dự án', 'error');
    } finally {
      setSavingProject(false);
    }
  };

  // Open task creation form
  const openTaskForm = async () => {
    setTaskForm({ title: '', stage: selectedProject?.stage || 'design', department: 'design', assigned_to: '' });
    setShowTaskForm(true);
    try {
      const data = extractItems(await api.getUsers());
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

  if (loading || !user) return null;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <span className="text-4xl block mb-4">⚠️</span>
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); refreshData(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }


  const permissions = getPermissions(user.role as UserRole);
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
              📊 Kanban
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "flex-1 px-4 py-3 text-sm font-semibold transition-all text-center",
                viewMode === 'list' ? "bg-[var(--gold-500)] text-white" : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
              )}
            >
              📋 Danh sách
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
                        <span className="truncate max-w-[55%]">👤 {project.client_name}</span>
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
              <div key={col.stage} className="flex-shrink-0 w-[82vw] max-w-[20rem] sm:w-80 snap-start rounded-2xl p-3 flex flex-col" style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid var(--border-subtle)' }}>
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
                        <span className="truncate max-w-[55%]">👤 {proj.client_name}</span>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" onClick={() => setSelectedProject(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-2xl max-h-[82vh] overflow-y-auto rounded-2xl animate-in"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between p-5 border-b" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)' }}>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-[var(--text-muted)] font-mono">{selectedProject.code}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                    backgroundColor: `${(statusConfig[selectedProject.status] || { color: '#6B7280' }).color}20`,
                    color: (statusConfig[selectedProject.status] || { color: '#6B7280' }).color,
                  }}>
                    {statusConfig[selectedProject.status]?.label || selectedProject.status}
                  </span>

                  {/* Stage Dropdown */}
                  <div className="flex items-center gap-1 ml-2">
                    <span className="text-xs text-[var(--text-muted)]">Giai đoạn:</span>
                    <select
                      value={selectedProject.stage}
                      onChange={e => handleProjectStageChange(e.target.value)}
                      className="text-xs bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 text-[var(--text-primary)] cursor-pointer"
                    >
                      {Object.entries(STAGE_LABELS).map(([k, label]) => (
                        <option key={k} value={k}>{label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <h2 className="text-lg font-bold mt-1 text-white">{selectedProject.name}</h2>
              </div>
              <div className="flex items-center gap-2">
                {permissions?.canCreateProjects && (
                  <button
                    onClick={() => openProjectForm(selectedProject)}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-white/10 border border-[var(--border-subtle)] transition-all"
                  >
                    Chỉnh sửa
                  </button>
                )}
                <button onClick={() => setSelectedProject(null)} className="p-2 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
              </div>
            </div>

            <div className="p-5 space-y-5">
              {/* Pause Reason — hiển thị khi dự án tạm dừng */}
              {selectedProject.stage === 'paused' && (
                <div className="p-3 rounded-xl" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
                  <p className="text-xs font-semibold text-amber-400 mb-1">⏸️ Lý do tạm dừng:</p>
                  <p className="text-sm text-[var(--text-secondary)]">{(selectedProject as unknown as Record<string, string>).pause_reason || 'Không ghi rõ'}</p>
                </div>
              )}

              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Tiến độ', value: `${selectedProject.progress}%` },
                  { label: 'Tổng giá trị', value: formatCurrency(selectedProject.total_value || (selectedProject.design_value || 0) + (selectedProject.construction_value || 0)) },
                  { label: 'Đã chi', value: formatCurrency(selectedProject.spent) },
                  { label: 'Loại', value: selectedProject.project_type === 'design_build' ? 'TK & Thi công' : selectedProject.project_type === 'design_only' ? 'Chỉ Thiết kế' : 'Chỉ Thi công' },
                ].map((card, i) => (
                  <div key={i} className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">{card.label}</p>
                    <p className="text-sm font-semibold mt-1 text-[#C9A96E]">{card.value}</p>
                  </div>
                ))}
              </div>

              {/* Team Assignment — Phân công bộ phận */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">👥 Phân công bộ phận</h3>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: 'PM', id: selectedProject.pm_id, color: '#8B5CF6', icon: '📋' },
                    { label: 'Thiết kế', id: selectedProject.designer_id, color: '#F59E0B', icon: '🎨' },
                    { label: 'Kinh doanh', id: selectedProject.sales_id, color: '#3B82F6', icon: '💼' },
                  ].map(m => {
                    const userName = m.id ? (users.find(u => u.id === m.id)?.full_name || '—') : '—';
                    return (
                      <div key={m.label} className="p-2 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                        <p className="text-lg mb-1">{m.icon}</p>
                        <p className="text-[10px] font-medium text-[var(--text-muted)]">{m.label}</p>
                        <p className="text-xs font-semibold truncate" style={{ color: m.color }}>{userName}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Client Info */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Thông tin khách hàng</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-[var(--text-secondary)]">
                  <p>👤 {selectedProject.client_name}</p>
                  {selectedProject.client_phone && <p>📱 {selectedProject.client_phone}</p>}
                  {selectedProject.address && <p className="md:col-span-2">📍 {selectedProject.address}</p>}
                </div>
              </div>

              {/* Contract Values */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Giá trị hợp đồng</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">HĐ Thiết kế</p>
                    <p className="text-sm font-semibold mt-1 text-white">{formatCurrency(selectedProject.design_value)}</p>
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">HĐ Thi công</p>
                    <p className="text-sm font-semibold mt-1 text-white">{formatCurrency(selectedProject.construction_value)}</p>
                  </div>
                </div>
              </div>

              {/* Ngân sách vs Thực chi — cảnh báo vượt ngân sách sớm */}
              {selectedProject.budget_total ? (() => {
                const budget = selectedProject.budget_total || 0;
                const spent = selectedProject.spent || 0;
                const pct = budget > 0 ? Math.round((spent / budget) * 100) : 0;
                const over = pct > 100;
                const warn = pct >= 80 && !over;
                const barColor = over ? '#F87171' : warn ? '#FBBF24' : '#34D399';
                return (
                  <div className="glass-card p-4">
                    <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Ngân sách vs thực chi</h3>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-[var(--text-secondary)]">Đã chi {formatCurrency(spent)} / {formatCurrency(budget)}</span>
                      <span className="font-bold" style={{ color: barColor }}>{pct}%</span>
                    </div>
                    <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
                      <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, pct)}%`, background: barColor }} />
                    </div>
                    {over && <p className="text-xs mt-2" style={{ color: '#F87171' }}>⚠ Vượt ngân sách {formatCurrency(spent - budget)} — cần rà soát chi phí</p>}
                    {warn && <p className="text-xs mt-2" style={{ color: '#FBBF24' }}>Sắp chạm ngân sách — theo dõi sát các khoản chi tiếp theo</p>}
                  </div>
                );
              })() : null}

              {/* Bàn giao & bảo hành */}
              {selectedProject.handover_date && (
                <div className="glass-card p-4">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Bàn giao &amp; bảo hành</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-[var(--text-muted)]">Ngày bàn giao</p>
                      <p className="font-semibold text-white mt-0.5">{new Date(selectedProject.handover_date).toLocaleDateString('vi-VN')}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-muted)]">Hết bảo hành ({selectedProject.warranty_months ?? 12} tháng)</p>
                      <p className="font-semibold text-white mt-0.5">
                        {(() => {
                          const d = new Date(selectedProject.handover_date);
                          d.setMonth(d.getMonth() + (selectedProject.warranty_months ?? 12));
                          return d.toLocaleDateString('vi-VN');
                        })()}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Tasks - Grouped by Operational Stage */}
              <div className="glass-card p-4">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                      Đầu việc
                    </h3>
                    <div className="flex rounded-lg overflow-hidden border border-[var(--border-subtle)]">
                      <button
                        onClick={() => setTaskGroupMode('stage')}
                        className={cn('px-2 py-0.5 text-[10px] font-semibold transition-all',
                          taskGroupMode === 'stage' ? 'bg-[var(--gold-500)] text-white' : 'text-[var(--text-muted)] hover:text-white')}
                      >Theo giai đoạn</button>
                      <button
                        onClick={() => setTaskGroupMode('department')}
                        className={cn('px-2 py-0.5 text-[10px] font-semibold transition-all',
                          taskGroupMode === 'department' ? 'bg-[var(--gold-500)] text-white' : 'text-[var(--text-muted)] hover:text-white')}
                      >Theo phòng ban</button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {permissions?.canCreateProjects && (
                      <button
                        onClick={openMaterialRequest}
                        className="text-xs px-3 py-1 rounded-lg font-medium bg-[#10B981] text-white hover:bg-[#059669] transition-all"
                      >
                        📦 Yêu cầu vật tư
                      </button>
                    )}
                    {permissions?.canCreateTasks && (
                      <button
                        onClick={openTaskForm}
                        className="text-xs px-3 py-1 rounded-lg font-medium bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] transition-all"
                      >
                        + Thêm công việc
                      </button>
                    )}
                  </div>
                </div>
                {loadingTasks ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Đang tải...</p>
                ) : tasks.length === 0 ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Chưa có công việc</p>
                ) : taskGroupMode === 'department' ? (
                  <div className="space-y-4">
                    {groupedByDepartment.map(group => (
                      <div
                        key={group.dept}
                        className={cn('border-b border-white/5 pb-3 last:border-0 last:pb-0 rounded-lg transition-opacity', group.waiting && 'opacity-45')}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-xs font-bold uppercase flex items-center gap-1.5" style={{ color: group.color }}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: group.color }} />
                            {group.label} ({group.done}/{group.tasks.length})
                            {group.waiting && (
                              <span className="text-[9px] font-medium normal-case px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                                Chờ giai đoạn trước
                              </span>
                            )}
                          </h4>
                          <div className="w-24 h-1 rounded-full bg-white/5">
                            <div className="h-full rounded-full" style={{ width: `${group.pct}%`, background: group.color }} />
                          </div>
                        </div>
                        <div className="space-y-1.5 pl-3">
                          {group.tasks.map(task => {
                            const ts = taskStatusConfig[task.status] || { label: task.status, color: '#6B7280', icon: '📌' };
                            return (
                              <div
                                key={task.id}
                                className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-all hover:bg-white/5 bg-white/2"
                                onClick={() => openTaskDetail(task)}
                              >
                                <span className="text-sm">{ts.icon}</span>
                                <span className="flex-1 text-sm text-[var(--text-primary)] truncate">{task.title}</span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${ts.color}20`, color: ts.color }}>{ts.label}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(groupedTasks).map(([stageKey, stageTasks]) => {
                      if (stageTasks.length === 0) return null;
                      return (
                        <div key={stageKey} className="border-b border-white/5 pb-3 last:border-0 last:pb-0">
                          <h4 className="text-xs font-bold text-[var(--gold-400)] uppercase mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--gold-500)]" />
                            {STAGE_LABELS[stageKey]} ({stageTasks.length})
                          </h4>
                          <div className="space-y-1.5 pl-3">
                            {stageTasks.map(task => {
                              const ts = taskStatusConfig[task.status] || { label: task.status, color: '#6B7280', icon: '📌' };
                              const dept = task.department ? DEPT_LABELS[task.department] : null;
                              return (
                                <div
                                  key={task.id}
                                  className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-all hover:bg-white/5 bg-white/2"
                                  onClick={() => openTaskDetail(task)}
                                >
                                  <span className="text-sm">{ts.icon}</span>
                                  <div className="flex-1 min-w-0">
                                    <p className="text-xs font-medium truncate text-white">{task.title}</p>
                                    <div className="flex items-center gap-2 mt-0.5">
                                      {dept && (
                                        <span className="text-[9px] px-1 py-0.2 rounded font-medium" style={{ background: `${dept.color}15`, color: dept.color }}>
                                          {dept.label}
                                        </span>
                                      )}
                                      {task.final_file_url && (
                                        <span className="text-[9px] text-[var(--gold-400)]">📎</span>
                                      )}
                                    </div>
                                  </div>
                                  {/* Inline status dropdown */}
                                  <select
                                    className="text-[9px] px-1 py-0.5 rounded font-medium bg-transparent border border-white/10 cursor-pointer max-w-[90px]"
                                    style={{ color: ts.color }}
                                    value={task.status}
                                    onClick={(e) => e.stopPropagation()}
                                    onChange={(e) => {
                                      e.stopPropagation();
                                      handleTaskStatusChange(task.id, e.target.value);
                                    }}
                                  >
                                    {['not_started', 'in_progress', 'done'].map(s => (
                                      <option key={s} value={s} style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}>
                                        {taskStatusConfig[s]?.label || s}
                                      </option>
                                    ))}
                                  </select>
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pause Reason Modal */}
      {showPauseReason && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={() => setShowPauseReason(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl p-5" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-1">⏸️ Tạm dừng dự án</h3>
            <p className="text-xs text-[var(--text-muted)] mb-3">Nhập lý do tạm dừng để lần sau quay lại biết context:</p>
            <textarea
              value={pauseReason}
              onChange={e => setPauseReason(e.target.value)}
              placeholder="VD: Đang xin phép, khách đi du lịch, chờ vật liệu..."
              rows={3}
              className="w-full text-xs px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white resize-none outline-none focus:border-[#C9A96E]"
              autoFocus
            />
            <div className="flex gap-2 mt-3 justify-end">
              <button onClick={() => setShowPauseReason(false)}
                className="px-3 py-1.5 rounded-xl text-xs bg-white/5 text-[var(--text-muted)]">Hủy</button>
              <button onClick={confirmPause}
                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-amber-500/20 text-amber-400 hover:bg-amber-500/30">
                Xác nhận tạm dừng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Task Detail Modal (with Note timeline + File attachments) ── */}
      {selectedTask && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 pt-[8vh]" onClick={() => setSelectedTask(null)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-2xl animate-in"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6">
              <button onClick={() => setSelectedTask(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>

              {/* Header */}
              <div className="flex items-center gap-3 mb-4">
                <span className="text-2xl">{(taskStatusConfig[selectedTask.status] || { icon: '📌' }).icon}</span>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-bold text-white truncate">{selectedTask.title}</h3>
                  <div className="flex flex-wrap gap-2 mt-1">
                    <span className="text-[9px] px-1.5 py-0.2 rounded font-medium bg-[var(--surface-3)] text-[var(--text-muted)]">
                      {STAGE_LABELS[selectedTask.stage]}
                    </span>
                    <select
                      value={selectedTask.status}
                      onChange={e => handleTaskStatusChange(selectedTask.id, e.target.value)}
                      className="text-[10px] bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded px-1 text-[var(--text-primary)] cursor-pointer"
                    >
                      <option value="todo">Chờ</option>
                      <option value="in_progress">Đang làm</option>
                      <option value="done">Hoàn thành</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Description */}
              {selectedTask.description && (
                <div className="rounded-xl p-3.5 mb-4 text-xs text-[var(--text-secondary)]" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-[10px] text-[var(--text-muted)] mb-1 uppercase font-semibold tracking-wider">Mô tả công việc</p>
                  <p className="whitespace-pre-wrap">{selectedTask.description}</p>
                </div>
              )}

              {/* Final Result File (Upload or Paste Link) */}
              <div className="glass-card p-3.5 mb-4">
                <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">📁 File kết quả giai đoạn (Final File)</h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Nhập link file chốt (ví dụ: link Drive, link PDF bản vẽ...)"
                    value={taskFileUrl}
                    onChange={e => setTaskFileUrl(e.target.value)}
                    className="flex-1 text-xs px-3 py-2 rounded-xl text-white"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                  />
                  <button
                    onClick={handleTaskFileSave}
                    className="text-xs px-3 rounded-xl font-medium bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] transition-all"
                  >
                    Lưu File
                  </button>
                </div>
                {selectedTask.final_file_url && (
                  <div className="mt-2 text-xs flex items-center justify-between">
                    <span className="text-[var(--text-muted)]">File hiện tại:</span>
                    <a
                      href={selectedTask.final_file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[var(--gold-400)] hover:underline truncate max-w-[70%]"
                    >
                      {selectedTask.final_file_url.startsWith('data:') ? '📎 Xem ảnh đính kèm (Base64)' : selectedTask.final_file_url}
                    </a>
                  </div>
                )}
              </div>

              {/* File Upload Zone */}
              <div className="mt-4 p-4 rounded-xl border-2 border-dashed" style={{ borderColor: 'var(--border-subtle)' }}>
                <p className="text-xs text-[var(--text-muted)] mb-2">📎 Upload file thiết kế / tài liệu</p>
                <input
                  type="file"
                  multiple
                  accept="image/*,.pdf,.doc,.docx,.dwg,.skp"
                  onChange={handleFileUpload}
                  className="w-full text-xs text-[var(--text-muted)]"
                />
                {uploadedFiles.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {uploadedFiles.map((f, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        <span>📄</span>
                        <span>{f.name}</span>
                        <span className="text-[var(--text-muted)]">({(f.size / 1024).toFixed(0)} KB)</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Note and Media Attachment form */}
              <div className="glass-card p-3.5 mb-4">
                <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">✍️ Thêm cập nhật ghi chú & hình ảnh</h4>
                <div className="space-y-2">
                  <textarea
                    placeholder="Nhập thông tin cập nhật công việc..."
                    value={newActivityContent}
                    onChange={e => setNewActivityContent(e.target.value)}
                    rows={2}
                    className="w-full text-xs px-3 py-2 rounded-xl text-white resize-none"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                  />
                  <div className="flex justify-between items-center">
                    {/* Media attach buttons */}
                    <div className="flex gap-2 items-center">
                      <input ref={fileRef} type="file" accept="image/*" multiple className="hidden" onChange={handleFileSelect} />
                      <button
                        onClick={() => fileRef.current?.click()}
                        type="button"
                        className="text-[10px] px-2.5 py-1 rounded bg-white/5 border border-white/10 text-white hover:bg-white/10 relative"
                      >
                        📷 Đính kèm ảnh
                        {newActivityMedia.length > 0 && (
                          <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center bg-[#C9A96E] text-black">
                            {newActivityMedia.length}
                          </span>
                        )}
                      </button>
                      {newActivityMedia.length > 0 && (
                        <button
                          onClick={() => setNewActivityMedia([])}
                          type="button"
                          className="text-[10px] px-1.5 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20"
                        >
                          Xóa ({newActivityMedia.length})
                        </button>
                      )}
                    </div>
                    {/* Photo thumbnails preview */}
                    {newActivityMedia.length > 0 && (
                      <div className="flex gap-1.5 mt-2 flex-wrap">
                        {newActivityMedia.map((src, i) => (
                          <div key={i} className="relative group">
                            <img src={src} alt={`Ảnh ${i+1}`} className="w-12 h-12 rounded-lg object-cover border border-white/10" />
                            <button
                              onClick={() => setNewActivityMedia(prev => prev.filter((_, idx) => idx !== i))}
                              className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[8px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={handleAddTaskActivity}
                      disabled={!newActivityContent.trim()}
                      className="text-xs px-3 py-1.5 rounded-xl font-medium bg-white text-black hover:opacity-90 disabled:opacity-50"
                    >
                      Đăng cập nhật
                    </button>
                  </div>
                </div>
              </div>

              {/* History Timeline */}
              <div className="glass-card p-3.5 max-h-[22vh] overflow-y-auto">
                <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">💬 Lịch sử cập nhật công việc</h4>
                {loadingActivities ? (
                  <p className="text-[10px] text-center text-[var(--text-disabled)]">Đang tải...</p>
                ) : taskActivities.length === 0 ? (
                  <p className="text-[10px] text-center text-[var(--text-disabled)]">Chưa có cập nhật nào</p>
                ) : (
                  <div className="space-y-3.5">
                    {taskActivities.map(act => (
                      <div key={act.id} className="border-l border-white/10 pl-3 relative ml-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--gold-500)] absolute -left-[4px] top-1" />
                        <div className="flex justify-between items-center text-[9px] text-[var(--text-disabled)] mb-0.5">
                          <span className="font-semibold text-white">{act.user_name || 'Nhân viên'}</span>
                          <span>{formatDate(act.created_at)}</span>
                        </div>
                        <p className="text-[11px] text-[var(--text-secondary)] whitespace-pre-wrap">{act.content}</p>
                        {act.media_url && (
                          <div className="mt-1.5 max-w-[150px] rounded overflow-hidden border border-white/5">
                            <img src={act.media_url} alt="Cập nhật" className="max-h-24 object-cover" />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Project Create/Edit Form Modal ── */}
      {showProjectForm && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={() => setShowProjectForm(false)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl animate-in p-6"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">{editingProject ? 'Chỉnh sửa dự án' : 'Tạo dự án mới'}</h2>
              <button onClick={() => setShowProjectForm(false)} className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Tên dự án *</label>
                <input
                  type="text" value={projectForm.name}
                  onChange={e => setProjectForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Nhập tên dự án"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Tên khách hàng *</label>
                <input
                  type="text" value={projectForm.client_name}
                  onChange={e => setProjectForm(f => ({ ...f, client_name: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Nhập tên khách hàng"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Số điện thoại</label>
                  <input
                    type="text" value={projectForm.client_phone}
                    onChange={e => setProjectForm(f => ({ ...f, client_phone: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                    placeholder="SĐT khách hàng"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Loại dự án</label>
                  <select
                    value={projectForm.project_type}
                    onChange={e => setProjectForm(f => ({ ...f, project_type: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  >
                    <option value="design_build">Thiết kế & Thi công</option>
                    <option value="design_only">Chỉ Thiết kế</option>
                    <option value="construction_only">Chỉ Thi công</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Địa chỉ</label>
                <input
                  type="text" value={projectForm.address}
                  onChange={e => setProjectForm(f => ({ ...f, address: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Địa chỉ công trình"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Tổng giá trị (nghìn đồng)</label>
                <MoneyInput
                  valueDong={projectForm.total_value}
                  onChangeDong={v => setProjectForm(f => ({ ...f, total_value: v }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ngày bắt đầu</label>
                  <input
                    type="date" value={projectForm.start_date}
                    onChange={e => setProjectForm(f => ({ ...f, start_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ngày dự kiến hoàn thành</label>
                  <input
                    type="date" value={projectForm.target_end_date}
                    onChange={e => setProjectForm(f => ({ ...f, target_end_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ngân sách kế hoạch (nghìn đồng) — để cảnh báo khi chi vượt</label>
                <MoneyInput
                  valueDong={projectForm.budget_total}
                  onChangeDong={v => setProjectForm(f => ({ ...f, budget_total: v }))}
                  placeholder="Bỏ trống nếu chưa lập ngân sách"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ngày bàn giao</label>
                  <input
                    type="date" value={projectForm.handover_date}
                    onChange={e => setProjectForm(f => ({ ...f, handover_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Bảo hành (tháng)</label>
                  <input
                    type="number" min={0} max={120} value={projectForm.warranty_months}
                    onChange={e => setProjectForm(f => ({ ...f, warranty_months: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowProjectForm(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-white/10 border border-[var(--border-subtle)]"
                >
                  Hủy
                </button>
                <button
                  onClick={handleSaveProject}
                  disabled={savingProject || !projectForm.name.trim() || !projectForm.client_name.trim()}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] disabled:opacity-50 transition-all"
                >
                  {savingProject ? 'Đang lưu...' : editingProject ? 'Cập nhật' : 'Tạo dự án'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Task Create Form Modal ── */}
      {showTaskForm && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={() => setShowTaskForm(false)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-md rounded-2xl animate-in p-6"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Thêm công việc mới</h2>
              <button onClick={() => setShowTaskForm(false)} className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Tiêu đề *</label>
                <input
                  type="text" value={taskForm.title}
                  onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Nhập tên công việc"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Giai đoạn</label>
                  <select
                    value={taskForm.stage}
                    onChange={e => setTaskForm(f => ({ ...f, stage: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  >
                    {Object.entries(STAGE_LABELS).filter(([k]) => k !== 'completed').map(([k, label]) => (
                      <option key={k} value={k}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Phòng ban</label>
                  <select
                    value={taskForm.department}
                    onChange={e => setTaskForm(f => ({ ...f, department: e.target.value, assigned_to: '' }))}
                    className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                  >
                    {Object.entries(DEPT_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Người phụ trách</label>
                <select
                  value={taskForm.assigned_to}
                  onChange={e => setTaskForm(f => ({ ...f, assigned_to: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                >
                  <option value="">-- Chọn người --</option>
                  {users
                    .filter(u => !taskForm.department || u.department === taskForm.department || u.role === 'admin' || u.role === 'supervisor')
                    .map(u => (
                      <option key={u.id} value={u.id}>{u.full_name || u.email}{u.department ? ` (${u.department})` : ''}</option>
                    ))
                  }
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowTaskForm(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-white/10 border border-[var(--border-subtle)]"
                >
                  Hủy
                </button>
                <button
                  onClick={handleSaveTask}
                  disabled={savingTask || !taskForm.title.trim()}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] disabled:opacity-50 transition-all"
                >
                  {savingTask ? 'Đang lưu...' : 'Thêm công việc'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Material Request Modal ── */}
      {showMaterialRequest && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={() => setShowMaterialRequest(false)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-md rounded-2xl animate-in p-6"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">📦 Yêu cầu vật tư</h2>
              <button onClick={() => setShowMaterialRequest(false)} className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Vật tư *</label>
                <select
                  value={materialRequestForm.material_id}
                  onChange={e => setMaterialRequestForm(f => ({ ...f, material_id: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                >
                  <option value="">-- Chọn vật tư --</option>
                  {materialsList.map(m => (
                    <option key={m.id} value={m.id}>{m.name} ({m.unit} - tồn: {m.quantity_in_stock})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Số lượng *</label>
                <input
                  type="number"
                  min="1"
                  value={materialRequestForm.quantity}
                  onChange={e => setMaterialRequestForm(f => ({ ...f, quantity: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Nhập số lượng"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ghi chú</label>
                <textarea
                  value={materialRequestForm.note}
                  onChange={e => setMaterialRequestForm(f => ({ ...f, note: e.target.value }))}
                  rows={2}
                  className="w-full px-3 py-2 rounded-xl text-sm text-white resize-none bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
                  placeholder="Ghi chú (không bắt buộc)"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowMaterialRequest(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-white/10 border border-[var(--border-subtle)]"
                >
                  Hủy
                </button>
                <button
                  onClick={handleSubmitMaterialRequest}
                  disabled={savingMaterialRequest || !materialRequestForm.material_id || !materialRequestForm.quantity}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-[#10B981] text-white hover:bg-[#059669] disabled:opacity-50 transition-all"
                >
                  {savingMaterialRequest ? 'Đang gửi...' : 'Gửi yêu cầu'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Sidebar>
  );
}
