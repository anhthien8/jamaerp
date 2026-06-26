'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Project, ProjectTask } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/utils';

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'Đang thực hiện', color: '#10B981' },
  on_hold: { label: 'Tạm dừng', color: '#F59E0B' },
  completed: { label: 'Hoàn thành', color: '#3B82F6' },
  cancelled: { label: 'Hủy', color: '#EF4444' },
  design: { label: 'Thiết kế', color: '#8B5CF6' },
};

const taskStatusConfig: Record<string, { label: string; color: string; icon: string }> = {
  done: { label: 'Xong', color: '#10B981', icon: '✅' },
  in_progress: { label: 'Đang làm', color: '#F59E0B', icon: '🔄' },
  todo: { label: 'Chờ', color: '#6B7280', icon: '⏳' },
};

export default function ProjectsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [selectedTask, setSelectedTask] = useState<ProjectTask | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const params: Record<string, string> = {};
      if (filterStatus !== 'all') params.status = filterStatus;
      const data = await api.getProjects(params);
      setProjects(data);
    } catch (e) {
      console.warn('Projects API error:', e);
      setProjects([]);
    } finally {
      setLoadingProjects(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchProjects);
  }, [user, fetchProjects]);

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

  if (loading || !user) return null;

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

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Dự án</h1>
            <p className="text-sm text-[var(--text-tertiary)] mt-1">
              {projects.length} dự án · {activeCount} đang hoạt động
            </p>
          </div>
        </div>

        {/* Filter chips */}
        <div className="flex gap-2 flex-wrap mb-6">
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

        {/* Projects Grid */}
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => {
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
                      <p className="text-xs font-mono text-[var(--text-muted)]">{project.code}</p>
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
      </div>

      {/* ── Project Detail Modal ── */}
      {selectedProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" onClick={() => setSelectedProject(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-2xl max-h-[78vh] overflow-y-auto rounded-2xl animate-in"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between p-5 border-b" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)' }}>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-[var(--text-muted)] font-mono">{selectedProject.code}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                    backgroundColor: `${(statusConfig[selectedProject.status] || { color: '#6B7280' }).color}20`,
                    color: (statusConfig[selectedProject.status] || { color: '#6B7280' }).color,
                  }}>
                    {statusConfig[selectedProject.status]?.label || selectedProject.status}
                  </span>
                </div>
                <h2 className="text-lg font-bold mt-1">{selectedProject.name}</h2>
              </div>
              <button onClick={() => setSelectedProject(null)} className="p-2 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
            </div>

            <div className="p-5 space-y-5">
              {/* Time left bar */}
              {(() => {
                const tl = calcProjectTimeLeft(selectedProject);
                if (!tl) return null;
                return (
                  <div className="rounded-xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-[var(--text-muted)]">⏱ Thời gian thi công</span>
                      <span className="text-sm font-semibold" style={{
                        color: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                      }}>{tl.label}</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-[var(--surface-3)]">
                      <div className="h-full rounded-full transition-all" style={{
                        width: `${tl.pct}%`,
                        background: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                      }} />
                    </div>
                    <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1">
                      <span>Bắt đầu: {selectedProject.start_date ? new Date(selectedProject.start_date).toLocaleDateString('vi-VN') : '—'}</span>
                      <span>{tl.totalDays} ngày thi công</span>
                      <span>Kết thúc: {selectedProject.target_end_date ? new Date(selectedProject.target_end_date).toLocaleDateString('vi-VN') : '—'}</span>
                    </div>
                  </div>
                );
              })()}

              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Tiến độ', value: `${selectedProject.progress}%` },
                  { label: 'Tổng giá trị', value: formatCurrency(selectedProject.total_value || (selectedProject.design_value || 0) + (selectedProject.construction_value || 0)) },
                  { label: 'Đã chi', value: formatCurrency(selectedProject.spent) },
                  { label: 'Loại', value: selectedProject.project_type },
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
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
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
                    <p className="text-sm font-semibold mt-1">{formatCurrency(selectedProject.design_value)}</p>
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">HĐ Thi công</p>
                    <p className="text-sm font-semibold mt-1">{formatCurrency(selectedProject.construction_value)}</p>
                  </div>
                </div>
              </div>

              {/* Tasks — now clickable */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                  Danh sách công việc ({tasks.length})
                </h3>
                {loadingTasks ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Đang tải...</p>
                ) : tasks.length === 0 ? (
                  <p className="text-sm text-center text-[var(--text-muted)] py-4">Chưa có công việc</p>
                ) : (
                  <div className="space-y-2">
                    {tasks.map(task => {
                      const ts = taskStatusConfig[task.status] || { label: task.status, color: '#6B7280', icon: '📌' };
                      return (
                        <div
                          key={task.id}
                          className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all hover:scale-[1.005]"
                          style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                          onClick={() => setSelectedTask(task)}
                        >
                          <span className="text-lg">{ts.icon}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate text-[var(--text-primary)]">{task.title}</p>
                            {task.due_date && (
                              <p className="text-[10px] text-[var(--text-muted)]">Hạn: {formatDate(task.due_date)}</p>
                            )}
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded-lg font-medium" style={{ background: `${ts.color}20`, color: ts.color }}>
                            {ts.label}
                          </span>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Dates */}
              <div className="flex justify-between text-[10px] text-[var(--text-disabled)] pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <span>Bắt đầu: {formatDate(selectedProject.start_date)}</span>
                <span>Dự kiến: {formatDate(selectedProject.target_end_date)}</span>
                <span>Tạo: {formatDate(selectedProject.created_at)}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Task Detail Modal ── */}
      {selectedTask && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 pt-[8vh]" onClick={() => setSelectedTask(null)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg rounded-2xl animate-in"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6">
              <button onClick={() => setSelectedTask(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>

              <div className="flex items-center gap-3 mb-4">
                <span className="text-2xl">{(taskStatusConfig[selectedTask.status] || { icon: '📌' }).icon}</span>
                <div>
                  <h3 className="text-lg font-bold text-[var(--text-primary)]">{selectedTask.title}</h3>
                  <span className="text-xs px-2 py-0.5 rounded-lg font-medium" style={{
                    background: `${(taskStatusConfig[selectedTask.status] || { color: '#6B7280' }).color}20`,
                    color: (taskStatusConfig[selectedTask.status] || { color: '#6B7280' }).color,
                  }}>
                    {taskStatusConfig[selectedTask.status]?.label || selectedTask.status}
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                {selectedTask.description && (
                  <div className="rounded-xl p-4" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)] mb-1">Mô tả</p>
                    <p className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">{selectedTask.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Người thực hiện</p>
                    <p className="text-sm font-medium mt-1 text-[var(--text-primary)]">{selectedTask.assigned_to || 'Chưa giao'}</p>
                  </div>
                  <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Hạn hoàn thành</p>
                    <p className="text-sm font-medium mt-1 text-[var(--text-primary)]">{selectedTask.due_date ? formatDate(selectedTask.due_date) : '—'}</p>
                  </div>
                  <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Thứ tự</p>
                    <p className="text-sm font-medium mt-1 text-[var(--text-primary)]">#{selectedTask.order}</p>
                  </div>
                  <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Hoàn thành</p>
                    <p className="text-sm font-medium mt-1 text-[var(--text-primary)]">{selectedTask.completed_at ? formatDate(selectedTask.completed_at) : 'Chưa xong'}</p>
                  </div>
                </div>

                <p className="text-[10px] text-[var(--text-disabled)] text-right">Tạo: {formatDate(selectedTask.created_at)}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </Sidebar>
  );
}

