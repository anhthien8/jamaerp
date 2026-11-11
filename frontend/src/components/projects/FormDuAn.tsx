'use client';

import type { Dispatch, SetStateAction } from 'react';
import { laTruongPhong } from '@/lib/roles';
import MoneyInput from '@/components/ui/MoneyInput';
import LineIcon from '@/components/ui/LineIcon';
import { laBanGiamDoc, PIC_CUA_BO_PHAN, canTakeTask } from './shared';
import type { Project, User } from '@/lib/api';

/** Modal tạo/sửa dự án. */
export default function FormDuAn({
  setShowProjectForm,
  editingProject,
  projectForm,
  setProjectForm,
  user,
  users,
  handleSaveProject,
  savingProject,
}: {
  setShowProjectForm: Dispatch<SetStateAction<boolean>>;
  editingProject: Project | null;
  projectForm: { name: string; client_name: string; client_phone: string; address: string; project_type: string; total_value: string; start_date: string; target_end_date: string; budget_total: string; handover_date: string; warranty_months: string; pm_id: string; designer_id: string; purchasing_id: string; sales_id: string; };
  setProjectForm: Dispatch<SetStateAction<{ name: string; client_name: string; client_phone: string; address: string; project_type: string; total_value: string; start_date: string; target_end_date: string; budget_total: string; handover_date: string; warranty_months: string; pm_id: string; designer_id: string; purchasing_id: string; sales_id: string; }>>;
  user: User | null;
  users: User[];
  handleSaveProject: () => Promise<void>;
  savingProject: boolean;
}) {
  return (
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
                type="text" inputMode="tel" value={projectForm.client_phone}
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

          {/* ── Phân công PIC 4 bộ phận (05/09/2026) ──────────────────────
              Trước đây form chỉ tạo dự án rồi để trống PM/Thiết kế/Thu mua,
              nên các bộ phận đó không lọc được «dự án của tôi». Mỗi ô lọc
              bằng canTakeTask — cùng luật với ô «Đảm nhận» ở đầu việc. */}
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)] block mb-2">
              Phân công phụ trách (PIC)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {([
                { key: 'pm_id', nhan: 'PM / Giám sát', icon: 'clipboard', dept: 'construction' },
                { key: 'designer_id', nhan: 'Thiết kế', icon: 'palette', dept: 'design' },
                { key: 'purchasing_id', nhan: 'Báo giá – Thu mua', icon: 'receipt', dept: 'quotation' },
                { key: 'sales_id', nhan: 'Kinh doanh', icon: 'briefcase', dept: 'sales' },
              ] as const).filter(o =>
                // Ban Giám Đốc điều phối chéo phòng → thấy cả 4 ô.
                // TRƯỞNG PHÒNG thấy đúng ô của bộ phận mình. Người khác không
                // thấy ô nào — backend cũng chỉ cho trưởng phòng gắn PIC, nên
                // hiện ô cho họ chỉ dẫn tới bấm rồi ăn 403 (chốt 22/09).
                laBanGiamDoc(user) ||
                (laTruongPhong(user) &&
                  PIC_CUA_BO_PHAN[(user?.department || '').toUpperCase()] === o.key)
              ).map(o => {
                const ungVien = users.filter(u => canTakeTask(u, o.dept));
                return (
                  <div key={o.key}>
                    <label className="text-[11px] text-[var(--text-muted)] block mb-1"><LineIcon name={o.icon} size={12} className="inline-block align-[-2px] mr-1" />{o.nhan}</label>
                    <select
                      value={projectForm[o.key]}
                      onChange={e => setProjectForm(f => ({ ...f, [o.key]: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
                    >
                      <option value="">— Chưa phân công —</option>
                      {ungVien.map(u => (
                        <option key={u.id} value={u.id}>{u.full_name || u.email}</option>
                      ))}
                    </select>
                    {ungVien.length === 0 && (
                      <p className="text-[10px] mt-1" style={{ color: '#F59E0B' }}>
                        Chưa có nhân sự nào thuộc bộ phận này — kiểm phòng ban trong Tài khoản.
                      </p>
                    )}
                  </div>
                );
              })}
              {!laBanGiamDoc(user) && !laTruongPhong(user) && (
                <p className="text-[11px] sm:col-span-2" style={{ color: '#F59E0B' }}>
                  Chỉ Trưởng phòng được phân công PIC cho bộ phận mình. Nhờ Trưởng phòng
                  Thiết kế / Giám sát / Báo giá–Thu mua / Kinh doanh gắn người giúp.
                </p>
              )}
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
  );
}
