'use client';

/**
 * Nhắc bật thông báo khi ĐÃ cài app (21/11/2026).
 *
 * Đo prod 21/11: 63 người đang làm, chỉ 2 người bật thông báo máy — nhiều người đã cài
 * JAMA HOME ra màn hình chính nhưng chưa từng bấm «Bật thông báo» (nút nằm sâu trong
 * Cài đặt / khung chuông). Banner nhỏ này hiện ngay đầu trang khi:
 *   • đang chạy dạng app (mở từ màn hình chính),
 *   • trình duyệt hỗ trợ thông báo đẩy và máy chủ đã bật VAPID,
 *   • máy chưa từng được hỏi quyền (Notification.permission === 'default') và chưa có đăng ký.
 * «Để sau» ẩn 7 ngày. Nằm trong dòng nội dung (không `fixed`) nên không bao giờ đè
 * thanh nút dính đáy như ở /doi-chieu. Không hiện ở /login (AppShell không vẽ ở đó).
 * Logic bật dùng chung lib/thong-bao-may.ts — không chép lại.
 */

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';
import { dangChayDangApp } from '@/lib/cai-app';
import { hoTroThongBaoDay, useThongBaoMay } from '@/lib/thong-bao-may';

const KEY_HOAN = 'jama_nhac_bat_tb_hoan';
const BAY_NGAY = 7 * 24 * 60 * 60 * 1000;

export default function NhacBatThongBao() {
  const pathname = usePathname();
  const [duDieuKien, setDuDieuKien] = useState(false);

  useEffect(() => {
    void Promise.resolve().then(() => {
      if (!dangChayDangApp() || !hoTroThongBaoDay()) return;
      if (Notification.permission !== 'default') return;
      if (Number(localStorage.getItem(KEY_HOAN) || 0) > Date.now()) return;
      setDuDieuKien(true);
    });
  }, []);

  // Trang /cai-app đã có khối bật thông báo đầy đủ.
  if (!duDieuKien || pathname === '/cai-app') return null;
  return <NoiDung onAn={() => setDuDieuKien(false)} />;
}

function NoiDung({ onAn }: { onAn: () => void }) {
  const { tt, dangLam, loi, bat } = useThongBaoMay();
  const { toast } = useToast();

  const deSau = () => {
    try { localStorage.setItem(KEY_HOAN, String(Date.now() + BAY_NGAY)); } catch { /* chế độ ẩn danh */ }
    onAn();
  };

  const batNgay = async () => {
    const t = await bat();
    if (t === 'bat') {
      toast('Đã bật thông báo trên máy này', 'success');
      onAn();
    }
  };

  // Chỉ hiện khi còn việc để bấm: máy chủ chưa bật / đã có đăng ký → im lặng.
  if (tt !== 'tat' && tt !== 'bi-chan') return null;

  return (
    <div
      className="mx-4 mt-3 px-3 py-2.5 rounded-2xl flex flex-wrap items-center gap-x-3 gap-y-2"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
      role="region"
      aria-label="Bật thông báo trên máy này"
    >
      <span className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'var(--surface-3)' }}>
        <LineIcon name="bell" size={18} />
      </span>
      <div className="flex-1 min-w-[180px]">
        {tt === 'bi-chan' ? (
          <>
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Máy đang chặn thông báo của JAMA HOME</p>
            <p className="text-[11px] leading-snug text-[var(--text-muted)]">
              Mở Cài đặt của điện thoại → Thông báo → JAMA HOME → Cho phép, rồi mở lại app.
            </p>
          </>
        ) : (
          <>
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Bật thông báo để không lỡ việc được giao</p>
            <p className="text-[11px] leading-snug text-[var(--text-muted)]">
              Việc mới, nhắc hạn, tin của Ban giám đốc hiện lên máy này kể cả khi không mở app.
            </p>
          </>
        )}
        {loi && <p className="text-[11px] mt-1" style={{ color: 'var(--warning)' }}>{loi}</p>}
      </div>
      <div className="flex items-center gap-2 ml-auto">
        {tt === 'tat' && (
          <button
            type="button"
            onClick={() => void batNgay()}
            disabled={dangLam}
            className="min-h-[44px] px-4 rounded-full text-xs font-semibold disabled:opacity-50"
            style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}
          >
            {dangLam ? 'Đang bật…' : 'Bật thông báo'}
          </button>
        )}
        <button
          type="button"
          onClick={deSau}
          className="min-h-[44px] px-3 rounded-full text-xs font-medium"
          style={{ color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
        >
          {tt === 'bi-chan' ? 'Đóng' : 'Để sau'}
        </button>
      </div>
    </div>
  );
}
