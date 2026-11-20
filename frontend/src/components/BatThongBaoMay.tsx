'use client';

// Bật/tắt thông báo đẩy trên máy đang dùng (25/10/2026). Mọi thông báo chuông
// trong ERP (báo cáo công trình, giao việc, duyệt…) sẽ hiện lên điện thoại/máy
// tính kể cả khi không mở app. iPhone/iPad: phải «Thêm vào MH chính» trước.

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import { useThongBaoMay } from '@/lib/thong-bao-may';
import { dangChayDangApp } from '@/lib/cai-app';

// 21/11/2026: logic đăng ký / huỷ / đọc trạng thái tách sang lib/thong-bao-may.ts (dùng chung
// với banner «Bật thông báo» trong app và trang /cai-app) — ở đây chỉ còn giao diện.

export default function BatThongBaoMay({ gon = false }: { gon?: boolean }) {
  const pathname = usePathname();
  const { tt, dangLam, loi, setLoi, bat, tat } = useThongBaoMay();
  const [daThu, setDaThu] = useState(false);
  const [ketQuaThu, setKetQuaThu] = useState('');

  // 25/10/2026: máy chủ đẩy NGAY và trả kết quả thật — không còn «đã gửi» mà không thấy gì
  const thu = async () => {
    setLoi(''); setDaThu(false);
    try {
      const r = await api.pushTest();
      if (r.ok) { setDaThu(true); setKetQuaThu(`Đã gửi tới ${r.sent}/${r.devices} máy — thông báo hiện trong vài giây.`); return; }
      const ma = (r.codes || []).filter(c => !(c >= 200 && c < 300));
      let ly = r.reason || '';
      if (!ly) {
        if (ma.some(c => c === 401 || c === 403)) ly = 'Trình duyệt từ chối khoá VAPID của máy chủ (401/403). Bấm Tắt rồi Bật lại để đăng ký lại; nếu vẫn lỗi, báo Admin kiểm tra khoá VAPID trên máy chủ.';
        else if (ma.some(c => c === 404 || c === 410)) ly = 'Đăng ký trên máy này đã hết hạn (410) — bấm Tắt rồi Bật lại.';
        else if (ma.some(c => c === 0)) ly = 'Máy chủ không nối được tới dịch vụ đẩy của trình duyệt (mạng). Thử lại sau.';
        else if (ma.some(c => c === 413)) ly = 'Nội dung thông báo quá dài (413).';
        else ly = `Không gửi được (mã ${ma.join(', ') || '?'}).`;
      }
      setLoi(ly);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Gửi thử lỗi');
    }
  };

  if (tt === 'dang-tai') return null;
  // Bản gọn (trong khung chuông): chỉ hiện khi còn việc để bấm
  if (gon && tt !== 'tat' && tt !== 'can-cai-ios') return null;

  const nutChinh = 'min-h-[44px] px-4 py-2 rounded-full text-sm font-medium transition-opacity disabled:opacity-50';

  if (gon) {
    return (
      <div className="mx-3 my-2 p-3 rounded-xl text-xs flex items-start gap-2.5" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
        <LineIcon name="smartphone" size={16} />
        <div className="flex-1 min-w-0">
          {tt === 'can-cai-ios' ? (
            <p style={{ color: 'var(--text-secondary)' }}>
              Muốn nhận thông báo trên iPhone/iPad: bấm nút Chia sẻ → «Thêm vào MH chính», rồi mở JAMA từ màn hình chính.
            </p>
          ) : (
            <>
              <p style={{ color: 'var(--text-secondary)' }}>Nhận thông báo trên máy này kể cả khi không mở ERP.</p>
              <button onClick={bat} disabled={dangLam} className="mt-2 min-h-[44px] px-4 rounded-full font-medium disabled:opacity-50" style={{ background: 'var(--gold-400)', color: 'var(--surface-0)' }}>
                {dangLam ? 'Đang bật…' : 'Bật thông báo'}
              </button>
              {loi && <p className="mt-1" style={{ color: 'var(--danger, #ef4444)' }}>{loi}</p>}
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold mb-2 flex items-center gap-2"><LineIcon name="bell" />Thông báo trên máy này</h2>
      <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
        Báo cáo công trình mới, việc được giao, việc chờ duyệt… sẽ hiện lên điện thoại/máy tính kể cả khi không mở ERP.
        Mỗi máy (điện thoại, laptop) bật riêng một lần.
      </p>
      {tt === 'bat' && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm flex items-center gap-1.5" style={{ color: 'var(--success, #22c55e)' }}><LineIcon name="check" size={16} />Đã bật trên máy này</span>
          <button onClick={thu} className={nutChinh} style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>Gửi thử</button>
          <button onClick={tat} disabled={dangLam} className={nutChinh} style={{ color: 'var(--text-muted)' }}>Tắt</button>
          {daThu && <span className="text-xs w-full" style={{ color: 'var(--text-muted)' }}>{ketQuaThu}</span>}
        </div>
      )}
      {tt === 'tat' && (
        <button onClick={bat} disabled={dangLam} className={nutChinh} style={{ background: 'var(--gold-400)', color: 'var(--surface-0)' }}>
          {dangLam ? 'Đang bật…' : 'Bật thông báo trên máy này'}
        </button>
      )}
      {tt === 'bi-chan' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {dangChayDangApp()
            ? 'Máy đang chặn thông báo của JAMA HOME. Mở Cài đặt của điện thoại → Thông báo → JAMA HOME → Cho phép, rồi mở lại app.'
            : 'Trình duyệt đang chặn thông báo của ERP. Bấm biểu tượng ổ khoá cạnh địa chỉ trang → Thông báo → Cho phép, rồi tải lại trang.'}
        </p>
      )}
      {tt === 'can-cai-ios' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          iPhone/iPad (iOS 16.4 trở lên): mở ERP bằng Safari → nút Chia sẻ → «Thêm vào MH chính», rồi mở JAMA từ màn hình chính và vào lại mục này.
          {pathname !== '/cai-app' && (
            <>
              {' '}
              <Link href="/cai-app" className="underline" style={{ color: 'var(--gold-400)' }}>Xem hướng dẫn từng bước</Link>
            </>
          )}
        </p>
      )}
      {tt === 'khong-ho-tro' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Trình duyệt này chưa hỗ trợ thông báo đẩy. Dùng Chrome, Edge, Safari (macOS/iOS 16.4+) hoặc Samsung Internet.</p>
      )}
      {tt === 'chua-cau-hinh' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Máy chủ chưa bật thông báo đẩy — báo Admin.</p>
      )}
      {loi && <p className="text-sm mt-2" style={{ color: 'var(--danger, #ef4444)' }}>{loi}</p>}
    </div>
  );
}
