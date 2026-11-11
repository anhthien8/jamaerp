'use client';

import type { Dispatch, SetStateAction } from 'react';
import LineIcon from '@/components/ui/LineIcon';

/** Modal nhập lý do tạm dừng dự án. */
export default function LyDoTamDung({
  setShowPauseReason,
  pauseReason,
  setPauseReason,
  confirmPause,
}: {
  setShowPauseReason: Dispatch<SetStateAction<boolean>>;
  pauseReason: string;
  setPauseReason: Dispatch<SetStateAction<string>>;
  confirmPause: () => Promise<void>;
}) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={() => setShowPauseReason(false)}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-md rounded-2xl p-5" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-bold text-[var(--text-primary)] mb-1"><LineIcon name="pause" size={16} className="inline-block align-[-2px] mr-1.5" />Tạm dừng dự án</h3>
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
  );
}
