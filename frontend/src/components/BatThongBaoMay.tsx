'use client';

// Bật/tắt thông báo đẩy trên máy đang dùng (25/10/2026). Mọi thông báo chuông
// trong CRM (báo cáo công trình, giao việc, duyệt…) sẽ hiện lên điện thoại/máy
// tính kể cả khi không mở app. iPhone/iPad: phải «Thêm vào MH chính» trước.

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';

type TrangThai = 'dang-tai' | 'khong-ho-tro' | 'can-cai-ios' | 'chua-cau-hinh' | 'bi-chan' | 'tat' | 'bat';

function base64UrlToUint8Array(base64: string) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function laIOS() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function daCaiVaoManHinh() {
  return window.matchMedia('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

async function dangKySW() {
  return navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' });
}

export default function BatThongBaoMay({ gon = false }: { gon?: boolean }) {
  const [tt, setTt] = useState<TrangThai>('dang-tai');
  const [dangLam, setDangLam] = useState(false);
  const [loi, setLoi] = useState('');
  const [daThu, setDaThu] = useState(false);

  const kiemTra = useCallback(async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      setTt(laIOS() && !daCaiVaoManHinh() ? 'can-cai-ios' : 'khong-ho-tro');
      return;
    }
    try {
      const k = await api.pushPublicKey();
      if (!k.enabled || !k.public_key) { setTt('chua-cau-hinh'); return; }
    } catch {
      setTt('chua-cau-hinh');
      return;
    }
    if (Notification.permission === 'denied') { setTt('bi-chan'); return; }
    const reg = await navigator.serviceWorker.getRegistration('/');
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    if (sub) {
      // Gửi lại để máy luôn gắn đúng người đang đăng nhập
      api.pushSubscribe(sub.toJSON()).catch(() => {});
      setTt('bat');
    } else {
      setTt('tat');
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(kiemTra, 0);
    return () => clearTimeout(id);
  }, [kiemTra]);

  const bat = async () => {
    setDangLam(true);
    setLoi('');
    try {
      const quyen = await Notification.requestPermission();
      if (quyen !== 'granted') {
        setTt(quyen === 'denied' ? 'bi-chan' : 'tat');
        return;
      }
      const { public_key } = await api.pushPublicKey();
      if (!public_key) { setTt('chua-cau-hinh'); return; }
      const reg = await dangKySW();
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array(public_key),
      });
      await api.pushSubscribe(sub.toJSON());
      setTt('bat');
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Không bật được thông báo');
    } finally {
      setDangLam(false);
    }
  };

  const tat = async () => {
    setDangLam(true);
    setLoi('');
    try {
      const reg = await navigator.serviceWorker.getRegistration('/');
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      if (sub) {
        await api.pushUnsubscribe(sub.endpoint).catch(() => {});
        await sub.unsubscribe();
      }
      setTt('tat');
    } finally {
      setDangLam(false);
    }
  };

  const thu = async () => {
    setLoi('');
    try {
      await api.pushTest();
      setDaThu(true);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Gửi thử lỗi');
    }
  };

  if (tt === 'dang-tai') return null;
  // Bản gọn (trong khung chuông): chỉ hiện khi còn việc để bấm
  if (gon && tt !== 'tat' && tt !== 'can-cai-ios') return null;

  const nutChinh = 'px-4 py-2 rounded-full text-sm font-medium transition-opacity disabled:opacity-50';

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
              <p style={{ color: 'var(--text-secondary)' }}>Nhận thông báo trên máy này kể cả khi không mở CRM.</p>
              <button onClick={bat} disabled={dangLam} className="mt-2 px-3 py-1.5 rounded-full font-medium disabled:opacity-50" style={{ background: 'var(--gold-400)', color: 'var(--surface-0)' }}>
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
        Báo cáo công trình mới, việc được giao, việc chờ duyệt… sẽ hiện lên điện thoại/máy tính kể cả khi không mở CRM.
        Mỗi máy (điện thoại, laptop) bật riêng một lần.
      </p>
      {tt === 'bat' && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm flex items-center gap-1.5" style={{ color: 'var(--success, #22c55e)' }}><LineIcon name="check" size={16} />Đã bật trên máy này</span>
          <button onClick={thu} className={nutChinh} style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>Gửi thử</button>
          <button onClick={tat} disabled={dangLam} className={nutChinh} style={{ color: 'var(--text-muted)' }}>Tắt</button>
          {daThu && <span className="text-xs w-full" style={{ color: 'var(--text-muted)' }}>Đã gửi — vài giây nữa thông báo sẽ hiện.</span>}
        </div>
      )}
      {tt === 'tat' && (
        <button onClick={bat} disabled={dangLam} className={nutChinh} style={{ background: 'var(--gold-400)', color: 'var(--surface-0)' }}>
          {dangLam ? 'Đang bật…' : 'Bật thông báo trên máy này'}
        </button>
      )}
      {tt === 'bi-chan' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Trình duyệt đang chặn thông báo của CRM. Bấm biểu tượng ổ khoá cạnh địa chỉ trang → Thông báo → Cho phép, rồi tải lại trang.
        </p>
      )}
      {tt === 'can-cai-ios' && (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          iPhone/iPad (iOS 16.4 trở lên): mở CRM bằng Safari → nút Chia sẻ → «Thêm vào MH chính», rồi mở JAMA từ màn hình chính và vào lại mục này.
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
