'use client';

import type { Dispatch, SetStateAction } from 'react';
import { STAGE_LABELS, DEPT_LABELS, canTakeTask } from './shared';
import type { User } from '@/lib/api';

/** Modal tạo công việc. */
export default function FormCongViec({
  setShowTaskForm,
  taskForm,
  setTaskForm,
  users,
  handleSaveTask,
  savingTask,
}: {
  setShowTaskForm: Dispatch<SetStateAction<boolean>>;
  taskForm: { title: string; stage: string; department: string; assigned_to: string; };
  setTaskForm: Dispatch<SetStateAction<{ title: string; stage: string; department: string; assigned_to: string; }>>;
  users: User[];
  handleSaveTask: () => Promise<void>;
  savingTask: boolean;
}) {
  return (
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
                // Dùng chung canTakeTask với select «Đảm nhận» ở kanban.
                .filter(u => canTakeTask(u, taskForm.department))
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
  );
}
