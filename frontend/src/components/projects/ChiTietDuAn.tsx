'use client';

import { useXacNhan } from '@/components/ui/XacNhan';
import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import AnhDuAn from '@/components/projects/AnhDuAn';
import GuiLinkKhach from '@/components/projects/GuiLinkKhach';
import { api } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import Link from 'next/link';
import LineIcon from '@/components/ui/LineIcon';
import { statusConfig, STAGE_LABELS, taskStatusConfig, DEPT_LABELS, nhanTreHan, nhomDamNhan, tenNgan, canTakeTask, taskDeptOf } from './shared';
import type { Project, User, ProjectTask } from '@/lib/api';
import type { RolePermissions } from '@/lib/roles';

/** Modal chi tiết dự án. */
export default function ChiTietDuAn({
  setSelectedProject,
  selectedProject,
  handleProjectStageChange,
  permissions,
  openProjectForm,
  users,
  doiKhachRieng,
  handleKhachRieng,
  setTaskGroupMode,
  taskGroupMode,
  openMaterialRequest,
  openTaskForm,
  loadingTasks,
  tasks,
  groupedByDepartment,
  openTaskDetail,
  groupedTasks,
  handleTaskStatusChange,
  luuNhomDamNhan,
  duocGiaoViec,
  giaoCaNhom,
}: {
  setSelectedProject: Dispatch<SetStateAction<Project | null>>;
  selectedProject: Project;
  handleProjectStageChange: (newStage: string) => Promise<void>;
  permissions: RolePermissions;
  openProjectForm: (project?: Project | undefined) => void;
  users: User[];
  doiKhachRieng: boolean;
  handleKhachRieng: (giaTri: boolean) => Promise<void>;
  setTaskGroupMode: Dispatch<SetStateAction<"department" | "stage">>;
  taskGroupMode: "department" | "stage";
  openMaterialRequest: () => Promise<void>;
  openTaskForm: () => Promise<void>;
  loadingTasks: boolean;
  tasks: ProjectTask[];
  groupedByDepartment: { dept: string; label: string; color: string; tasks: ProjectTask[]; done: number; pct: number; waiting: boolean; minStage: number; }[];
  openTaskDetail: (task: ProjectTask) => Promise<void>;
  groupedTasks: { design: ProjectTask[]; quotation: ProjectTask[]; procurement: ProjectTask[]; construction: ProjectTask[]; acceptance: ProjectTask[]; };
  handleTaskStatusChange: (taskId: string, newStatus: string) => Promise<void>;
  luuNhomDamNhan: (taskId: string, ids: string[]) => Promise<void>;
  duocGiaoViec: (task: ProjectTask) => boolean;
  giaoCaNhom: (viec: ProjectTask[], uid: string) => Promise<void>;
}) {
  const xacNhan = useXacNhan();
  /** Ô «Giao cả nhóm» ở tiêu đề nhóm việc: chỉ đụng việc CHƯA có người nhận và
   *  chưa xong (giao đè sẽ thay cả nhóm đảm nhận), chỉ giao việc người được chọn
   *  thuộc đúng bộ phận. Không còn việc nào như vậy thì ẩn. */
  // Chặn bấm chồng khi vòng giao cả nhóm đang chạy (tránh báo trùng / giao đè).
  const [dangGiao, setDangGiao] = useState(false);
  const oGiaoCaNhom = (nhan: string, dsViec: ProjectTask[]) => {
    const trong = dsViec.filter(t => t.status !== 'done' && nhomDamNhan(t).length === 0 && duocGiaoViec(t));
    if (trong.length === 0) return null;
    const ungVien = users.filter(u => trong.some(t => canTakeTask(u, taskDeptOf(t))));
    if (ungVien.length === 0) return null;
    return (
      <label className="inline-flex items-center gap-1 min-w-0 text-[10px] font-medium normal-case text-[var(--text-muted)]" onClick={e => e.stopPropagation()}>
        <LineIcon name="users" size={12} color="currentColor" className="shrink-0" />
        <select
          className="min-w-0 max-w-[150px] text-[10px] px-1.5 py-1 rounded cursor-pointer border bg-transparent"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-secondary)' }}
          title="Giao tất cả việc chưa có người nhận trong nhóm này cho một người"
          value=""
          disabled={dangGiao}
          onChange={async e => {
            if (dangGiao) return;
            const u = ungVien.find(x => x.id === e.target.value);
            if (!u) return;
            const viec = trong.filter(t => canTakeTask(u, taskDeptOf(t)));
            if (await xacNhan(`Giao ${viec.length} việc chưa có người nhận ở «${nhan}» cho ${u.full_name}?
${u.full_name} sẽ nhận ${viec.length} thông báo.`)) {
              setDangGiao(true);
              void giaoCaNhom(viec, u.id).finally(() => setDangGiao(false));
            }
          }}
        >
          <option value="">Giao cả nhóm ({trong.length})…</option>
          {ungVien.map(u => (
            <option key={u.id} value={u.id} style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}>{u.full_name}</option>
          ))}
        </select>
      </label>
    );
  };

  // Nút «Bắt đầu» / «Xong» thay ô chọn trạng thái chữ 9px (24/11): một chạm, cao ≥ 36px. Việc đã xong
  // không có nút — cần mở lại thì vào chi tiết việc đổi trạng thái.
  const [dangDoi, setDangDoi] = useState('');
  const nutViec = (task: ProjectTask) => {
    if (task.status === 'done' || task.status === 'completed') return null;
    const chuaLam = task.status === 'not_started' || task.status === 'todo';
    return (
      <button
        type="button"
        disabled={dangDoi === task.id}
        className="shrink-0 min-h-[36px] px-3 rounded-full text-xs font-medium disabled:opacity-50"
        style={chuaLam ? { border: '1px solid var(--border-default)', color: 'var(--gold-400)' } : { background: 'var(--gold-400)', color: '#000' }}
        onClick={e => {
          e.stopPropagation();
          setDangDoi(task.id);
          void handleTaskStatusChange(task.id, chuaLam ? 'in_progress' : 'done').finally(() => setDangDoi(''));
        }}
      >
        {chuaLam ? 'Bắt đầu' : 'Xong'}
      </button>
    );
  };
  const nutNhanh = 'inline-flex items-center gap-1.5 shrink-0 min-h-[40px] px-3.5 rounded-full text-xs font-medium border border-[var(--border-default)] text-[var(--text-primary)] bg-[var(--surface-2)]';
  const chip = 'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" onClick={() => setSelectedProject(null)}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-2xl max-h-[82vh] overflow-y-auto rounded-2xl animate-in"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 border-b" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)' }}>
        <div className="flex items-center justify-between p-5 pb-3">
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
          {/* Hàng nút dính (24/11): bốn việc hay làm nhất ở công trình, cuộn tới đâu cũng một chạm. */}
          <div className="flex gap-2 px-5 pb-3 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
            {selectedProject.client_phone && (
              <a href={`tel:${selectedProject.client_phone}`} className={nutNhanh}><LineIcon name="phone" size={15} color="currentColor" />Gọi khách</a>
            )}
            {selectedProject.address && (
              <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(selectedProject.address)}`} target="_blank" rel="noopener noreferrer" className={nutNhanh}>
                <LineIcon name="pin" size={15} color="currentColor" />Chỉ đường
              </a>
            )}
            <button type="button" className={nutNhanh} onClick={() => {
              const o = document.getElementById('o-them-anh-du-an');
              o?.click();
              o?.parentElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }}>
              <LineIcon name="camera" size={15} color="currentColor" />Thêm ảnh
            </button>
            <Link href={`/vat-tu?project=${selectedProject.id}`} className={nutNhanh}><LineIcon name="package" size={15} color="currentColor" />Vật tư</Link>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* Pause Reason — hiển thị khi dự án tạm dừng */}
          {(selectedProject.stage === 'paused' || selectedProject.status === 'paused') && (
            <div className="p-3 rounded-xl" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
              <p className="text-xs font-semibold text-amber-400 mb-1"><LineIcon name="pause" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Lý do tạm dừng:</p>
              <p className="text-sm text-[var(--text-secondary)]">{(selectedProject as unknown as Record<string, string>).pause_reason || 'Không ghi rõ'}</p>
            </div>
          )}

          {/* Tóm tắt — một hàng chip (24/11: gộp 4 thẻ tóm tắt + 2 thẻ giá trị hợp đồng) */}
          <div className="flex flex-wrap gap-1.5">
            {[
              ['Tiến độ', `${selectedProject.progress}%`],
              ['Tổng giá trị', formatCurrency(selectedProject.total_value || (selectedProject.design_value || 0) + (selectedProject.construction_value || 0))],
              ['HĐ thiết kế', formatCurrency(selectedProject.design_value)],
              ['HĐ thi công', formatCurrency(selectedProject.construction_value)],
              ['Đã chi', formatCurrency(selectedProject.spent)],
              ['Loại', selectedProject.project_type === 'design_build' ? 'TK & Thi công' : selectedProject.project_type === 'design_only' ? 'Chỉ Thiết kế' : 'Chỉ Thi công'],
            ].map(([nhan, giaTri]) => (
              <span key={nhan} className={chip} style={{ background: 'var(--surface-2)' }}>
                <span className="text-[var(--text-muted)]">{nhan}</span>
                <b style={{ color: 'var(--gold-400)' }}>{giaTri}</b>
              </span>
            ))}
          </div>

          {/* Team Assignment — Phân công bộ phận */}
          <div className="glass-card p-4">
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3"><LineIcon name="users" size={16} className="inline-block align-[-2px] mr-1.5" />Phân công bộ phận</h3>
            <div className="flex flex-wrap gap-1.5">
              {[
                { label: 'PM / Giám sát', id: selectedProject.pm_id, color: '#8B5CF6', icon: 'clipboard' },
                { label: 'Thiết kế', id: selectedProject.designer_id, color: '#F59E0B', icon: 'palette' },
                { label: 'Báo giá – Thu mua', id: selectedProject.purchasing_id, color: '#10B981', icon: 'receipt' },
                { label: 'Kinh doanh', id: selectedProject.sales_id, color: '#3B82F6', icon: 'briefcase' },
              ].map(m => {
                const userName = m.id ? (users.find(u => u.id === m.id)?.full_name || '—') : '—';
                return (
                  <span key={m.label} className={`${chip} min-w-0`} style={{ background: 'var(--surface-2)' }}>
                    <LineIcon name={m.icon} size={14} color={m.color} className="shrink-0" />
                    <span className="text-[var(--text-muted)] shrink-0">{m.label}</span>
                    <b className="truncate" style={{ color: m.color }}>{userName}</b>
                  </span>
                );
              })}
            </div>
            {(doiKhachRieng || selectedProject.khach_rieng) && (
              <label className={cn('mt-3 flex items-start gap-2.5 p-2.5 rounded-lg min-h-[44px]', doiKhachRieng && 'cursor-pointer')}
                style={{ background: 'var(--surface-2)' }}>
                <input type="checkbox" className="mt-0.5 w-4 h-4 accent-[var(--gold-500)]"
                  checked={!!selectedProject.khach_rieng} disabled={!doiKhachRieng}
                  onChange={e => handleKhachRieng(e.target.checked)} />
                <span className="text-xs">
                  <span className="font-semibold text-[var(--text-primary)]">Khách riêng của sale</span>
                  <span className="block text-[var(--text-muted)]">Sale tự mang khách về → hoa hồng sale 2% thay vì 1% mỗi đợt thu tiền.{!doiKhachRieng && ' Chỉ TP Kinh doanh / Ban Giám đốc đổi được.'}</span>
                </span>
              </label>
            )}
          </div>

          {/* Client Info */}
          <div className="glass-card p-4">
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Thông tin khách hàng</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-[var(--text-secondary)]">
              <p><LineIcon name="user" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{selectedProject.client_name}</p>
              {selectedProject.client_phone && <p><LineIcon name="smartphone" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{selectedProject.client_phone}</p>}
              {selectedProject.address && <p className="md:col-span-2"><LineIcon name="pin" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{selectedProject.address}</p>}
            </div>
            <div className="mt-3">
              <GuiLinkKhach
                key={selectedProject.id}
                layLink={() => api.getPortalLinkDuAn(selectedProject.id)}
                phone={selectedProject.client_phone}
                nhan="Gửi tiến độ cho khách"
                choGoi
                soanTin={link => `Chào anh/chị ${selectedProject.client_name}, công trình ${selectedProject.name} đang ở giai đoạn ${STAGE_LABELS[selectedProject.stage] || selectedProject.stage}, tiến độ ${Math.round(selectedProject.progress || 0)}%. Anh/chị xem ảnh và tiến độ tại: ${link}`}
              />
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
                {over && <p className="text-xs mt-2" style={{ color: '#F87171' }}><LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Vượt ngân sách {formatCurrency(spent - budget)} — cần rà soát chi phí</p>}
                {warn && <p className="text-xs mt-2" style={{ color: '#FBBF24' }}>Sắp chạm ngân sách — theo dõi sát các khoản chi tiếp theo</p>}
              </div>
            );
          })() : null}

          {/* Ảnh công trình — Kho ảnh (Telegram «JAMA Công trình») */}
          <AnhDuAn projectId={selectedProject.id} />

          {/* Khách đã xác nhận nghiệm thu trên portal (27/10/2026) */}
          {selectedProject.stage_acceptances && Object.keys(selectedProject.stage_acceptances).length > 0 && (
            <div className="glass-card p-4">
              <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Khách đã nghiệm thu</h3>
              <div className="space-y-2 text-sm">
                {Object.entries(selectedProject.stage_acceptances).map(([gd, nt]) => (
                  <div key={gd} className="flex items-start gap-2">
                    <LineIcon name="check" size={16} />
                    <div className="min-w-0">
                      <div className="text-[var(--text-primary)]">{STAGE_LABELS[gd] || gd} · {new Date(nt.at).toLocaleDateString('vi-VN')}</div>
                      {nt.note && <div className="text-xs text-[var(--text-muted)]">{nt.note}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

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
                    <LineIcon name="package" size={16} className="inline-block align-[-2px] mr-1.5" />Yêu cầu vật tư
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
                      <div className="flex items-center gap-2 min-w-0">
                        {oGiaoCaNhom(group.label, group.tasks)}
                        <div className="w-16 sm:w-24 h-1 rounded-full bg-white/5 shrink-0">
                          <div className="h-full rounded-full" style={{ width: `${group.pct}%`, background: group.color }} />
                        </div>
                      </div>
                    </div>
                    <div className="space-y-1.5 pl-3">
                      {group.tasks.map(task => {
                        const ts = taskStatusConfig[task.status] || { label: task.status, color: '#6B7280', icon: 'pin' };
                        return (
                          <div
                            key={task.id}
                            className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-all hover:bg-white/5 bg-white/2"
                            onClick={() => openTaskDetail(task)}
                          >
                            <LineIcon name={ts.icon} size={16} color={ts.color} className="shrink-0" />
                            <span className="flex-1 min-w-0 text-sm text-[var(--text-primary)] truncate">{task.title}</span>
                            <span className={cn('shrink-0 text-[10px] px-1.5 py-0.5 rounded', task.status !== 'done' && 'hidden sm:inline')} style={{ background: `${ts.color}20`, color: ts.color }}>{ts.label}</span>
                            {nutViec(task)}
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
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <h4 className="text-xs font-bold text-[var(--gold-400)] uppercase flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-[var(--gold-500)]" />
                          {STAGE_LABELS[stageKey]} ({stageTasks.length})
                        </h4>
                        {oGiaoCaNhom(STAGE_LABELS[stageKey], stageTasks)}
                      </div>
                      <div className="space-y-1.5 pl-3">
                        {stageTasks.map(task => {
                          const ts = taskStatusConfig[task.status] || { label: task.status, color: '#6B7280', icon: 'pin' };
                          const dept = task.department ? DEPT_LABELS[task.department] : null;
                          return (
                            <div
                              key={task.id}
                              className="flex flex-wrap items-center gap-x-3 gap-y-1.5 p-2.5 rounded-lg cursor-pointer transition-all hover:bg-white/5 bg-white/2"
                              onClick={() => openTaskDetail(task)}
                            >
                              <LineIcon name={ts.icon} size={16} color={ts.color} className="shrink-0" />
                              <div className="flex-1 min-w-[45%] sm:min-w-0">
                                <p className="text-xs font-medium truncate text-white">{task.title}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  {dept && (
                                    <span className="text-[9px] px-1 py-0.2 rounded font-medium" style={{ background: `${dept.color}15`, color: dept.color }}>
                                      {dept.label}
                                    </span>
                                  )}
                                  {task.final_file_url && (
                                    <LineIcon name="link" size={11} className="shrink-0" />
                                  )}
                                </div>
                              </div>
                              {nutViec(task)}
                              {/* Nhãn trễ hạn / vượt SLA (13/10/2026) */}
                              {(() => {
                                const nhan = nhanTreHan(task);
                                return nhan ? (
                                  <span
                                    className="flex-shrink-0 text-[9px] px-1.5 py-0.5 rounded font-bold"
                                    style={{ background: nhan.bg, color: nhan.color }}
                                    title={task.due_date ? `Hạn ${new Date(task.due_date).toLocaleDateString('vi-VN')}` : 'Theo chuẩn nội bộ (SLA)'}
                                  >
                                    <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle" style={{ background: 'currentColor' }} />{nhan.text}
                                  </span>
                                ) : null;
                              })()}
                              {/* Nhóm người đảm nhận — NHIỀU người, tất cả ngang vai */}
                              {nhomDamNhan(task).map(uid => (
                                <span
                                  key={uid}
                                  className="flex-shrink-0 text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]"
                                  title={users.find(u => u.id === uid)?.full_name || ''}
                                >
                                  {tenNgan(users.find(u => u.id === uid)?.full_name)}
                                </span>
                              ))}
                              {/* Thêm người đảm nhận — luôn hiện, vì một đầu việc có thể
                                  nhiều người (trước 13/10 nút này biến mất ngay khi có
                                  người đầu tiên nên không ai thêm được người thứ hai). */}
                              <select
                                className="min-w-0 text-[9px] px-1.5 py-0.5 rounded font-medium cursor-pointer border"
                                style={{ background: 'rgba(16,185,129,0.1)', color: '#10B981', borderColor: 'rgba(16,185,129,0.3)' }}
                                title="Thêm người đảm nhận"
                                value=""
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  const uid = e.target.value;
                                  if (!uid) return;
                                  // Dùng chung đường lưu với ô trong chi tiết việc: cập nhật
                                  // đúng một đầu việc trong state, không `refreshData()` —
                                  // nạp lại cả dự án + việc + nhân sự chỉ để thêm một người
                                  // làm cả bảng nhấp nháy và chậm trên danh sách dài.
                                  luuNhomDamNhan(task.id, [...nhomDamNhan(task), uid]);
                                }}
                              >
                                <option value="">{nhomDamNhan(task).length ? '+ Thêm' : 'Đảm nhận'}</option>
                                {users
                                  .filter(u => canTakeTask(u, taskDeptOf(task)) && !nhomDamNhan(task).includes(u.id))
                                  .map(u => (
                                    <option key={u.id} value={u.id}>{u.full_name}</option>
                                  ))}
                              </select>
                              <svg className="flex-shrink-0" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
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
  );
}
