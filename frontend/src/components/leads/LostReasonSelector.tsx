'use client';

import { useState } from 'react';
import LineIcon from '@/components/ui/LineIcon';

const LOST_REASONS = [
  'Ngân sách không phù hợp',
  'Đã chọn đối thủ',
  'Không phản hồi',
  'Thay đổi kế hoạch',
  'Lý do khác',
];

// Ô chọn lý do mất lead. Trạng thái mở do trang mẹ giữ để kéo thẻ vào cột "Mất"
// hoặc chọn "Mất" ở dropdown nhanh có thể bật sẵn ô này thay vì bắt user tự dò.
export default function LostReasonSelector({ isOpen, setIsOpen, onConfirm, onCancel }: {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [selectedReason, setSelectedReason] = useState('');
  const [customReason, setCustomReason] = useState('');

  const handleConfirm = () => {
    const reason = selectedReason === 'Lý do khác' ? customReason.trim() : selectedReason;
    if (!reason) return;
    onConfirm(reason);
    setIsOpen(false);
    setSelectedReason('');
    setCustomReason('');
  };

  return (
    <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
          style={{
            background: 'rgba(239,68,68,0.1)',
            color: '#EF4444',
            border: '1px solid rgba(239,68,68,0.3)',
          }}
        >
          <LineIcon name="xCircle" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Chuyển sang Mất lead
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-red-400">Chọn lý do mất lead:</p>
          <div className="flex flex-wrap gap-1.5">
            {LOST_REASONS.map(reason => (
              <button
                key={reason}
                onClick={() => setSelectedReason(reason)}
                className="px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all"
                style={{
                  background: selectedReason === reason ? 'rgba(239,68,68,0.25)' : 'var(--surface-2)',
                  color: selectedReason === reason ? '#EF4444' : 'var(--text-secondary)',
                  border: `1px solid ${selectedReason === reason ? 'rgba(239,68,68,0.4)' : 'var(--border-subtle)'}`,
                }}
              >
                {reason}
              </button>
            ))}
          </div>
          {selectedReason === 'Lý do khác' && (
            <input
              value={customReason}
              onChange={e => setCustomReason(e.target.value)}
              placeholder="Nhập lý do cụ thể..."
              className="w-full px-3 py-1.5 rounded-lg text-xs bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-red-400"
            />
          )}
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={!selectedReason || (selectedReason === 'Lý do khác' && !customReason.trim())}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 disabled:opacity-30 transition-all"
            >
              Xác nhận mất lead
            </button>
            <button
              onClick={() => { setIsOpen(false); setSelectedReason(''); setCustomReason(''); onCancel(); }}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
            >
              Hủy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
