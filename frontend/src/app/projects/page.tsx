'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Project, ProjectTask, ProjectKanban, TaskActivity, extractItems } from '@/lib/api';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { useToast } from '@/components/ui/Toast';

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
};

const DEPT_LABELS: Record<string, { label: string; color: string }> = {
  design: { label: 'Thiết kế', color: '#8B5CF6' },
  quotation: { label: 'Báo giá', color: '#F59E0B' },
  procurement: { label: 'Thu mua', color: '#10B981' },
  construction: { label: 'Thi công', color: '#3B82F6' },
  accounting: { label: 'Kế toán', color: '#EC4899' },
  sales: { label: 'Kinh doanh', color: '#F97316' },
};

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
  const [viewMode, setViewMode] = useState<'list' | 'pipeline'>('pipeline');
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
  const [newActivityMedia, setNewActivityMedia] = useState('');
  const [taskFileUrl, setTaskFileUrl] = useState('');

  const fileRef = useRef<HTMLInputElement>(null);

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

  const handleAddTaskActivity = async () => {
    if (!selectedTask || !newActivityContent.trim()) return;
    try {
      const act = await api.createTaskActivity(selectedTask.id, newActivityContent, newActivityMedia || undefined);
      setTaskActivities(prev => [act, ...prev]);
      setNewActivityContent('');
      setNewActivityMedia('');
      toast('Thêm ghi chú thành công', 'success');
    } catch {
      toast('Lỗi khi thêm ghi chú', 'error');
    }
  };

  const handleProjectStageChange = async (newStage: string) => {
    if (!selectedProject) return;
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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast('File tối đa 5MB', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      setNewActivityMedia(result);
      toast('Đã đính kèm ảnh', 'success');
    };
    reader.readAsDataURL(file);
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

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Pipeline Dự án</h1>
            <p className="text-sm text-[var(--text-tertiary)] mt-1">
              Theo dõi và cập nhật tiến độ thi công công trình
            </p>
          </div>

          {/* View Toggle */}
          <div className="flex rounded-xl overflow-hidden border border-[var(--border-subtle)] p-0.5 bg-[var(--surface-2)] self-start sm:self-auto">
            <button
              onClick={() => setViewMode('pipeline')}
              className={cn(
                "px-4 py-1.5 text-xs font-semibold rounded-lg transition-all",
                viewMode === 'pipeline' ? "bg-[var(--gold-500)] text-white shadow-sm" : "text-[var(--text-muted)] hover:text-white"
              )}
            >
              📊 Pipeline Kanban
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "px-4 py-1.5 text-xs font-semibold rounded-lg transition-all",
                viewMode === 'list' ? "bg-[var(--gold-500)] text-white shadow-sm" : "text-[var(--text-muted)] hover:text-white"
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
                placeholder="Tim du an..."
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
                <span className="text-xs text-[var(--text-secondary)]">Cong viec cua toi</span>
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
                      if (!p.name.toLowerCase().includes(q) && !p.code.toLowerCase().includes(q) && !(p.client_name || '').toLowerCase().includes(q)) return false;
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
                placeholder="Tim du an..."
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
                <span className="text-xs text-[var(--text-secondary)]">Cong viec cua toi</span>
              </label>
            </div>
          <div className="flex gap-4 overflow-x-auto pb-4 min-w-0 min-h-[60vh] select-none animate-fade-in">
            {kanbanData.map(col => (
              <div key={col.stage} className="flex-shrink-0 w-80 rounded-2xl p-3 flex flex-col" style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid var(--border-subtle)' }}>
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
                        <span className="text-[9px] px-1.5 py-0.2 rounded font-medium" style={{
                          backgroundColor: proj.status === 'active' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                          color: proj.status === 'active' ? '#10B981' : '#F59E0B'
                        }}>
                          {proj.status === 'active' ? 'Chạy' : 'Tạm dừng'}
                        </span>
                      </div>
                      <h4 className="text-sm font-semibold text-white mb-3 truncate">{proj.name}</h4>

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
              <button onClick={() => setSelectedProject(null)} className="p-2 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
            </div>

            <div className="p-5 space-y-5">
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

              {/* Tasks - Grouped by Operational Stage */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-4">
                  Đầu việc theo giai đoạn vận hành
                </h3>
                {loadingTasks ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Đang tải...</p>
                ) : tasks.length === 0 ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Chưa có công việc</p>
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
                                  <span className="text-[9px] px-1.5 py-0.2 rounded font-medium" style={{ background: `${ts.color}15`, color: ts.color }}>
                                    {ts.label}
                                  </span>
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
                    <div className="flex gap-2">
                      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileSelect} />
                      <button
                        onClick={() => fileRef.current?.click()}
                        type="button"
                        className="text-[10px] px-2.5 py-1 rounded bg-white/5 border border-white/10 text-white hover:bg-white/10"
                      >
                        📷 {newActivityMedia ? 'Đã chọn ảnh' : 'Đính kèm ảnh'}
                      </button>
                      {newActivityMedia && (
                        <button
                          onClick={() => setNewActivityMedia('')}
                          type="button"
                          className="text-[10px] px-1.5 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20"
                        >
                          Xóa ảnh
                        </button>
                      )}
                    </div>
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
    </Sidebar>
  );
}
