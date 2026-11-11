'use client';

import type { Dispatch, SetStateAction } from 'react';
import LineIcon from '@/components/ui/LineIcon';
import { STAGE_CONFIG } from '@/lib/utils';
import type { User } from '@/lib/api';

/** Thanh hành động bulk — nổi dưới màn hình khi có lead được chọn ở view danh sách. */
export default function ThanhThaoTacHangLoat({
  selectedLeadIds,
  bulkAssignOpen,
  bulkStageOpen,
  loadAssignableUsers,
  setBulkAssignOpen,
  setBulkStageOpen,
  setSelectedLeadIds,
  bulkBusy,
  handleBulkAssign,
  loadingUsers,
  assignableUsers,
  bulkStageValue,
  setBulkStageValue,
  bulkLostReason,
  setBulkLostReason,
  runBulkStage,
}: {
  selectedLeadIds: Set<string>;
  bulkAssignOpen: boolean;
  bulkStageOpen: boolean;
  loadAssignableUsers: () => Promise<void>;
  setBulkAssignOpen: Dispatch<SetStateAction<boolean>>;
  setBulkStageOpen: Dispatch<SetStateAction<boolean>>;
  setSelectedLeadIds: Dispatch<SetStateAction<Set<string>>>;
  bulkBusy: boolean;
  handleBulkAssign: (userId: string) => Promise<void>;
  loadingUsers: boolean;
  assignableUsers: User[];
  bulkStageValue: string;
  setBulkStageValue: Dispatch<SetStateAction<string>>;
  bulkLostReason: string;
  setBulkLostReason: Dispatch<SetStateAction<string>>;
  runBulkStage: () => Promise<void>;
}) {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] flex items-center gap-3 px-4 py-3 rounded-2xl glass-card shadow-2xl" style={{ border: '1px solid var(--border-subtle)', background: 'var(--surface-1)' }}>
      <span className="text-xs font-semibold text-white whitespace-nowrap">{selectedLeadIds.size} lead đã chọn</span>
      {!bulkAssignOpen && !bulkStageOpen ? (
        <>
          <button
            onClick={() => { void loadAssignableUsers(); setBulkAssignOpen(true); }}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 transition-all whitespace-nowrap"
          >
            <LineIcon name="user" size={16} className="inline-block align-[-2px] mr-1.5" />Giao cho…
          </button>
          <button
            onClick={() => setBulkStageOpen(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] hover:bg-white/10 transition-all whitespace-nowrap"
          >
            <LineIcon name="refresh" size={16} className="inline-block align-[-2px] mr-1.5" />Đổi giai đoạn
          </button>
          <button
            onClick={() => setSelectedLeadIds(new Set())}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
          >
            Bỏ chọn
          </button>
        </>
      ) : bulkAssignOpen ? (
        <>
          <select
            autoFocus
            disabled={bulkBusy}
            defaultValue=""
            onChange={e => { if (e.target.value) void handleBulkAssign(e.target.value); }}
            className="text-xs px-2 py-1.5 rounded-lg cursor-pointer border outline-none"
            style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}
          >
            <option value="">{loadingUsers ? 'Đang tải…' : bulkBusy ? 'Đang giao…' : 'Chọn người phụ trách'}</option>
            {assignableUsers.map(u => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
          <button
            onClick={() => setBulkAssignOpen(false)}
            disabled={bulkBusy}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
          >
            Hủy
          </button>
        </>
      ) : (
        /* Bulk stage — dropdown + lý do «Mất» + nút chạy, 1 dòng gọn trong thanh nổi */
        <>
          <select
            autoFocus
            disabled={bulkBusy}
            value={bulkStageValue}
            onChange={e => setBulkStageValue(e.target.value)}
            aria-label="Chuyển các lead đã chọn sang giai đoạn"
            className="text-xs px-2 py-1.5 rounded-lg cursor-pointer border outline-none max-w-[180px]"
            style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}
          >
            <option value="">— Chọn giai đoạn —</option>
            {/* signed_design bị BE chặn (tự sinh KH+Dự án phải chạy từng lead),
                lost thì hiện ra nhưng bắt nhập lý do ngay bên cạnh. */}
            {['new', 'interested', 'survey_scheduled', 'potential', 'dormant', 'lost'].map(s => (
              <option key={s} value={s}>{STAGE_CONFIG[s]?.label || s}</option>
            ))}
          </select>
          {bulkStageValue === 'lost' && (
            <input
              value={bulkLostReason}
              onChange={e => setBulkLostReason(e.target.value)}
              placeholder="Lý do mất lead (bắt buộc)"
              className="text-xs px-2 py-1.5 rounded-lg border outline-none w-44"
              style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', borderColor: 'rgba(239,68,68,0.4)' }}
            />
          )}
          <button
            onClick={() => void runBulkStage()}
            disabled={bulkBusy || !bulkStageValue || (bulkStageValue === 'lost' && !bulkLostReason.trim())}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 disabled:opacity-40 transition-all whitespace-nowrap"
          >
            {bulkBusy ? 'Đang chuyển…' : 'Chuyển'}
          </button>
          <button
            onClick={() => { setBulkStageOpen(false); setBulkStageValue(''); setBulkLostReason(''); }}
            disabled={bulkBusy}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
          >
            Hủy
          </button>
        </>
      )}
    </div>
  );
}
