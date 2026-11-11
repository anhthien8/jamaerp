'use client';

import type { Dispatch, RefObject, SetStateAction } from 'react';
import { mediaUrl } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import LineIcon from '@/components/ui/LineIcon';
import ChuCoLink from '@/components/ui/ChuCoLink';
import { taskStatusConfig, STAGE_LABELS, nhanTreHan, nhomDamNhan, canTakeTask, taskDeptOf, choOInputNgay } from './shared';
import type { ChangeEvent } from 'react';
import type { ProjectTask, User, TaskActivity } from '@/lib/api';

/** Modal chi tiết công việc (timeline ghi chú + file đính kèm). */
export default function ChiTietCongViec({
  setSelectedTask,
  selectedTask,
  handleTaskStatusChange,
  users,
  luuNhomDamNhan,
  luuHanChot,
  dangTaiFile,
  taiFileKetQua,
  taskFileUrl,
  setTaskFileUrl,
  handleTaskFileSave,
  handleFileUpload,
  newActivityContent,
  setNewActivityContent,
  fileRef,
  handleFileSelect,
  newActivityMedia,
  setNewActivityMedia,
  handleAddTaskActivity,
  loadingActivities,
  taskActivities,
}: {
  setSelectedTask: Dispatch<SetStateAction<ProjectTask | null>>;
  selectedTask: ProjectTask;
  handleTaskStatusChange: (taskId: string, newStatus: string) => Promise<void>;
  users: User[];
  luuNhomDamNhan: (taskId: string, ids: string[]) => Promise<void>;
  luuHanChot: (taskId: string, ngay: string) => Promise<void>;
  dangTaiFile: boolean;
  taiFileKetQua: (file: File) => Promise<void>;
  taskFileUrl: string;
  setTaskFileUrl: Dispatch<SetStateAction<string>>;
  handleTaskFileSave: () => Promise<void>;
  handleFileUpload: (e: ChangeEvent<HTMLInputElement, Element>) => Promise<void>;
  newActivityContent: string;
  setNewActivityContent: Dispatch<SetStateAction<string>>;
  fileRef: RefObject<HTMLInputElement | null>;
  handleFileSelect: (e: ChangeEvent<HTMLInputElement, Element>) => void;
  newActivityMedia: string[];
  setNewActivityMedia: Dispatch<SetStateAction<string[]>>;
  handleAddTaskActivity: () => Promise<void>;
  loadingActivities: boolean;
  taskActivities: TaskActivity[];
}) {
  return (
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
            <LineIcon name={(taskStatusConfig[selectedTask.status] || { icon: 'pin' }).icon} size={24} color={(taskStatusConfig[selectedTask.status] || { color: '#6B7280' }).color} className="shrink-0" />
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
                  {/* Giá trị phải là `not_started` — backend không có trạng thái
                      «todo», chọn sai thì ô này hiện lệch với trạng thái thật. */}
                  <option value="not_started">Chờ</option>
                  <option value="in_progress">Đang làm</option>
                  <option value="done">Hoàn thành</option>
                </select>
                {(() => {
                  const nhan = nhanTreHan(selectedTask);
                  return nhan ? (
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: nhan.bg, color: nhan.color }}>
                      <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle" style={{ background: 'currentColor' }} />{nhan.text}
                    </span>
                  ) : null;
                })()}
              </div>
            </div>
          </div>

          {/* Người đảm nhận — NHIỀU người, tất cả ngang vai (13/10/2026).
              Thêm ai là người đó nhận thông báo trong app + Telegram ngay. */}
          <div className="glass-card p-3.5 mb-4">
            <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2"><LineIcon name="user" size={16} className="inline-block align-[-2px] mr-1.5" />Người đảm nhận</h4>
            <div className="flex flex-wrap gap-1.5 items-center">
              {nhomDamNhan(selectedTask).map(uid => (
                <span
                  key={uid}
                  className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-lg"
                  style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
                >
                  {users.find(u => u.id === uid)?.full_name || 'Nhân sự đã nghỉ'}
                  <button
                    type="button"
                    title="Gỡ khỏi đầu việc"
                    className="text-[var(--text-muted)] hover:text-red-400"
                    onClick={() => luuNhomDamNhan(
                      selectedTask.id,
                      nhomDamNhan(selectedTask).filter(x => x !== uid),
                    )}
                  >
                    ✕
                  </button>
                </span>
              ))}
              {nhomDamNhan(selectedTask).length === 0 && (
                <span className="text-[10px] text-[var(--text-muted)]">Chưa có ai nhận việc này</span>
              )}
              <select
                value=""
                className="text-[10px] px-2 py-1 rounded-lg cursor-pointer border"
                style={{ background: 'rgba(16,185,129,0.1)', color: '#10B981', borderColor: 'rgba(16,185,129,0.3)' }}
                onChange={e => {
                  if (!e.target.value) return;
                  luuNhomDamNhan(selectedTask.id, [...nhomDamNhan(selectedTask), e.target.value]);
                }}
              >
                <option value="">+ Thêm người</option>
                {users
                  .filter(u => canTakeTask(u, taskDeptOf(selectedTask)) && !nhomDamNhan(selectedTask).includes(u.id))
                  .map(u => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
              </select>
            </div>
            {/* Hạn chốt (thoả thuận) vs hạn theo chuẩn nội bộ (SLA) */}
            <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
              <label className="text-[10px] text-[var(--text-muted)]">Hạn chốt</label>
              <input
                type="date"
                value={choOInputNgay(selectedTask.due_date)}
                onChange={e => luuHanChot(selectedTask.id, e.target.value)}
                className="text-[10px] px-2 py-1 rounded-lg text-white"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              />
              <span className="text-[10px] text-[var(--text-muted)]">
                {selectedTask.sla_due_at
                  ? `Chuẩn nội bộ (SLA): ${new Date(selectedTask.sla_due_at).toLocaleDateString('vi-VN')}`
                  : 'SLA chạy khi việc có người nhận hoặc chuyển «Đang làm»'}
              </span>
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
            <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2"><LineIcon name="layers" size={16} className="inline-block align-[-2px] mr-1.5" />File kết quả giai đoạn (Final File)</h4>
            <label
              className={`flex items-center justify-center gap-2 w-full py-2.5 mb-2 rounded-xl text-xs font-medium cursor-pointer transition-all bg-[var(--gold-500)] text-white hover:bg-[var(--gold-600)] ${dangTaiFile ? 'opacity-60 pointer-events-none' : ''}`}
            >
              {dangTaiFile ? 'Đang tải lên…' : <><LineIcon name="upload" size={14} color="currentColor" />Tải file lên (PDF, DWG, SKP, Excel… tối đa 50MB)</>}
              <input
                type="file"
                className="hidden"
                disabled={dangTaiFile}
                onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) taiFileKetQua(f); }}
              />
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="…hoặc dán link (Drive, file >50MB)"
                value={taskFileUrl}
                onChange={e => setTaskFileUrl(e.target.value)}
                className="flex-1 text-xs px-3 py-2 rounded-xl text-white"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              />
              <button
                onClick={handleTaskFileSave}
                className="text-xs px-3 rounded-xl font-medium border border-[var(--gold-500)] text-[var(--gold-400)] hover:bg-[var(--gold-500)]/10 transition-all"
              >
                Lưu link
              </button>
            </div>
            {selectedTask.final_file_url && (
              <div className="mt-2 text-xs flex items-center justify-between">
                <span className="text-[var(--text-muted)]">File hiện tại:</span>
                <a
                  href={mediaUrl(selectedTask.final_file_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--gold-400)] hover:underline truncate max-w-[70%]"
                >
                  <LineIcon name="link" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />
                  {selectedTask.final_file_url.startsWith('data:')
                    ? 'Xem ảnh đính kèm (Base64)'
                    : selectedTask.final_file_url.startsWith('/media/docs/')
                      ? `${decodeURIComponent(selectedTask.final_file_url.split('/').pop() || 'Tài liệu')}`
                      : selectedTask.final_file_url}
                </a>
              </div>
            )}
          </div>

          {/* File Upload Zone — ảnh vào ghi chú bên dưới, tài liệu thành file kết quả phía trên. */}
          <div className="mt-4 p-4 rounded-xl border-2 border-dashed" style={{ borderColor: 'var(--border-subtle)' }}>
            <p className="text-xs text-[var(--text-muted)] mb-2"><LineIcon name="link" size={14} className="inline-block align-[-2px] mr-1.5" />Chọn ảnh hoặc tài liệu</p>
            <input
              type="file"
              multiple
              onChange={handleFileUpload}
              disabled={dangTaiFile}
              className="w-full text-xs text-[var(--text-muted)]"
            />
            <p className="text-[10px] text-[var(--text-muted)] mt-2">
              Ảnh → vào ghi chú bên dưới. PDF/DWG/SKP/Excel → tự lưu làm file kết quả và gửi vào nhóm Telegram dự án.
            </p>
          </div>

          {/* Note and Media Attachment form */}
          <div className="glass-card p-3.5 mb-4">
            <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2"><LineIcon name="edit" size={14} className="inline-block align-[-2px] mr-1.5" />Thêm cập nhật ghi chú & hình ảnh</h4>
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
                    <LineIcon name="camera" size={16} className="inline-block align-[-2px] mr-1.5" />Đính kèm ảnh
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
                  disabled={!newActivityContent.trim() && newActivityMedia.length === 0}
                  className="text-xs px-3 py-1.5 rounded-xl font-medium bg-white text-black hover:opacity-90 disabled:opacity-50"
                >
                  Đăng cập nhật
                </button>
              </div>
            </div>
          </div>

          {/* History Timeline */}
          <div className="glass-card p-3.5 max-h-[22vh] overflow-y-auto">
            <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3"><LineIcon name="message" size={16} className="inline-block align-[-2px] mr-1.5" />Lịch sử cập nhật công việc</h4>
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
                    <p className="text-[11px] text-[var(--text-secondary)] whitespace-pre-wrap"><ChuCoLink text={act.content || ''} /></p>
                    {act.media_url && (
                      <div className="mt-1.5 max-w-[150px] rounded overflow-hidden border border-white/5">
                        <a href={mediaUrl(act.media_url)} target="_blank" rel="noopener noreferrer">
                          <img src={mediaUrl(act.media_url)} alt="Cập nhật" loading="lazy" className="max-h-24 object-cover" />
                        </a>
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
  );
}
