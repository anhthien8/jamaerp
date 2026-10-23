'use client';

import { useState, useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';

/**
 * InstallBanner — thanh dưới «Lưu JAMA HOME ra màn hình chính» (22/07, làm lại 23/10/2026).
 * - Bấm cả thanh là cài: Android/Samsung (Chrome, Samsung Internet) gọi hộp cài THẬT qua
 *   beforeinstallprompt; iOS/iPadOS không có API → mở bảng hướng dẫn 3 bước có hình nút.
 * - Trang đăng nhập: hiện NGAY, sát đáy (không có thanh menu dưới), kể cả khi trước đó
 *   đã bấm «Để sau» ở trong app — đây là lúc người mới mở web lần đầu.
 * - Trong app: «Để sau» ẩn 7 ngày (bản cũ ẩn vĩnh viễn nên nhân viên lỡ bấm là mất luôn).
 * - Ẩn hẳn khi đang chạy dạng app (standalone) hoặc trên máy tính.
 */

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const KEY_HOAN = 'jama_install_snooze_until';
const KEY_AN_PHIEN = 'jama_install_an_phien';
const BAY_NGAY = 7 * 24 * 60 * 60 * 1000;

function laIOS(): boolean {
  const ua = navigator.userAgent;
  // iPadOS 13+ tự xưng «Macintosh» — nhận ra bằng màn cảm ứng.
  return /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
}

export default function InstallBanner() {
  const pathname = usePathname();
  const laTrangLogin = pathname === '/login';
  const [sanSang, setSanSang] = useState(false); // đủ điều kiện hiện (mobile, chưa cài)
  const [hoan, setHoan] = useState(false);
  const [anPhienNay, setAnPhienNay] = useState(false);
  const [moHuongDan, setMoHuongDan] = useState(false);
  const [ios, setIos] = useState(false);
  const deferredPrompt = useRef<BeforeInstallPromptEvent | null>(null);
  const [coHopCai, setCoHopCai] = useState(false);

  useEffect(() => {
    const daCai = window.matchMedia('(display-mode: standalone)').matches
      || (navigator as unknown as { standalone?: boolean }).standalone === true;
    if (daCai) return;
    const iosMay = laIOS();
    const mobile = iosMay || /Android|Mobi/i.test(navigator.userAgent);
    if (!mobile) return;

    const onBip = (e: Event) => {
      e.preventDefault();
      deferredPrompt.current = e as BeforeInstallPromptEvent;
      setCoHopCai(true);
    };
    const onInstalled = () => setSanSang(false);
    window.addEventListener('beforeinstallprompt', onBip);
    window.addEventListener('appinstalled', onInstalled);
    void Promise.resolve().then(() => {
      setIos(iosMay);
      setHoan(Number(localStorage.getItem(KEY_HOAN) || 0) > Date.now());
      setAnPhienNay(sessionStorage.getItem(KEY_AN_PHIEN) === '1');
      setSanSang(true);
    });
    return () => {
      window.removeEventListener('beforeinstallprompt', onBip);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const deSau = () => {
    setHoan(true);
    setAnPhienNay(true);
    localStorage.setItem(KEY_HOAN, String(Date.now() + BAY_NGAY));
    sessionStorage.setItem(KEY_AN_PHIEN, '1');
  };

  const cai = async () => {
    const ev = deferredPrompt.current;
    if (ev) {
      await ev.prompt();
      const kq = await ev.userChoice;
      deferredPrompt.current = null;
      setCoHopCai(false);
      if (kq.outcome === 'accepted') setSanSang(false);
      return;
    }
    setMoHuongDan(true); // iOS, hoặc trình duyệt chưa cho hộp cài → hướng dẫn tay
  };

  if (!sanSang) return null;
  // Trang đăng nhập bỏ qua «Để sau» 7 ngày, chỉ ẩn khi vừa bấm ✕ trong phiên này.
  if (laTrangLogin ? anPhienNay : hoan) return null;

  return (
    <>
      <div
        className={`fixed left-0 right-0 z-[45] px-3 pt-3 animate-in ${laTrangLogin ? 'bottom-0' : 'bottom-16'}`}
        style={{
          paddingBottom: laTrangLogin ? 'calc(12px + env(safe-area-inset-bottom))' : 12,
          background: '#14161C',
          borderTop: '1px solid rgba(201,169,110,0.35)',
        }}
      >
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={cai}
            className="flex-1 min-w-0 flex items-center gap-3 text-left"
            aria-label="Lưu JAMA HOME thành app trên màn hình chính"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon-192.png" alt="" className="w-11 h-11 rounded-xl flex-shrink-0" style={{ border: '1px solid rgba(201,169,110,0.3)' }} />
            <span className="flex-1 min-w-0">
              <span className="block text-[13px] font-semibold text-white">Cài JAMA HOME lên điện thoại</span>
              <span className="block text-[11px] leading-snug" style={{ color: '#B8B0A0' }}>
                Có icon ngoài màn hình chính, mở nhanh như app
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={cai}
            className="flex-shrink-0 text-[13px] font-semibold px-4 rounded-full"
            style={{ background: '#C9A96E', color: '#0B0D11', minHeight: 36 }}
          >
            {coHopCai ? 'Cài đặt' : 'Thêm'}
          </button>
          <button
            type="button"
            onClick={deSau}
            className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center"
            style={{ color: '#B8B0A0', border: '1px solid rgba(255,255,255,0.12)' }}
            aria-label="Để sau"
          >
            ✕
          </button>
        </div>
      </div>

      {moHuongDan && (
        <div className="fixed inset-0 z-[110] flex items-end justify-center" onClick={() => setMoHuongDan(false)}>
          <div className="absolute inset-0 bg-black/60" />
          <div
            className="relative w-full max-w-lg rounded-t-3xl p-5 animate-slideUpSheet"
            style={{ background: '#14161C', borderTop: '1px solid rgba(201,169,110,0.35)', paddingBottom: 'calc(20px + env(safe-area-inset-bottom))' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 rounded-full mx-auto mb-4" style={{ background: 'rgba(255,255,255,0.2)' }} />
            <p className="text-base font-semibold text-white mb-4">Thêm JAMA HOME ra màn hình chính</p>
            <ol className="space-y-3 text-sm" style={{ color: '#D8D2C4' }}>
              {ios ? (
                <>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>1</span>
                    <span>Bấm nút <b className="text-white">Chia sẻ</b>{' '}
                      <svg className="inline -mt-1" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4DA3FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>
                      {' '}ở thanh dưới (iPhone) hoặc góc trên (iPad) của Safari</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>2</span>
                    <span>Kéo xuống, chọn <b className="text-white">Thêm vào MH chính</b> ⊞</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>3</span>
                    <span>Bấm <b className="text-white">Thêm</b> ở góc phải — icon JAMA HOME hiện ngoài màn hình</span>
                  </li>
                  <li className="text-xs pt-1" style={{ color: '#8E8778' }}>Đang mở bằng Zalo/Chrome? Chọn «Mở bằng Safari» trước rồi làm như trên.</li>
                </>
              ) : (
                <>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>1</span>
                    <span>Bấm nút <b className="text-white">⋮</b> (Chrome) hoặc <b className="text-white">≡</b> (Samsung Internet) ở góc màn hình</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>2</span>
                    <span>Chọn <b className="text-white">Thêm vào màn hình chính</b> / <b className="text-white">Cài đặt ứng dụng</b></span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>3</span>
                    <span>Bấm <b className="text-white">Thêm</b> — icon JAMA HOME hiện ngoài màn hình</span>
                  </li>
                </>
              )}
            </ol>
            <button
              type="button"
              onClick={() => setMoHuongDan(false)}
              className="w-full mt-5 rounded-full text-sm font-semibold"
              style={{ background: '#C9A96E', color: '#0B0D11', minHeight: 44 }}
            >
              Đã hiểu
            </button>
          </div>
        </div>
      )}
      <style>{`
        @keyframes slideUpSheet { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .animate-slideUpSheet { animation: slideUpSheet 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
      `}</style>
    </>
  );
}
