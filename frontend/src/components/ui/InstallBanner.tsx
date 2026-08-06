'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * InstallBanner — nhắc mobile user "Lưu ra màn hình chính" (yêu cầu 22/07).
 * - Android/Chrome: bắt sự kiện beforeinstallprompt → nút "Cài đặt" gọi prompt THẬT
 *   (một chạm, không phải mò menu ⋮). Fallback: hướng dẫn menu.
 * - iOS/Safari: không có API cài đặt → hướng dẫn Chia sẻ → Thêm vào MH chính.
 * - Ẩn khi đã chạy standalone (đã cài) hoặc đã bấm "Đã hiểu" (localStorage).
 */

// Sự kiện không có trong lib DOM chuẩn
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export default function InstallBanner() {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const deferredPrompt = useRef<BeforeInstallPromptEvent | null>(null);
  const [canNativeInstall, setCanNativeInstall] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    // Không hiện nếu đã cài (standalone) hoặc đã dismiss
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches
      || (navigator as unknown as { standalone?: boolean }).standalone === true;
    const wasDismissed = localStorage.getItem('jama_install_dismissed') === 'true';
    if (isStandalone || wasDismissed) return;

    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (!isMobile) return;

    const onBip = (e: Event) => {
      e.preventDefault();
      deferredPrompt.current = e as BeforeInstallPromptEvent;
      setCanNativeInstall(true);
    };
    window.addEventListener('beforeinstallprompt', onBip);

    const t = setTimeout(() => setVisible(true), 3000);
    return () => { clearTimeout(t); window.removeEventListener('beforeinstallprompt', onBip); };
  }, []);

  const dismiss = () => {
    setDismissed(true);
    setVisible(false);
    localStorage.setItem('jama_install_dismissed', 'true');
  };

  const nativeInstall = async () => {
    const ev = deferredPrompt.current;
    if (!ev) return;
    await ev.prompt();
    const choice = await ev.userChoice;
    if (choice.outcome === 'accepted') dismiss();
    deferredPrompt.current = null;
    setCanNativeInstall(false);
  };

  if (!visible || dismissed) return null;

  const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

  return (
    <div className="fixed bottom-16 left-0 right-0 z-[45] p-3 animate-in" style={{ background: 'linear-gradient(135deg, #1C1A15, #2A2620)', borderTop: '1px solid rgba(201,169,110,0.35)' }}>
      <div className="max-w-lg mx-auto flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icon-192.png" alt="JAMA HOME" className="w-10 h-10 rounded-xl flex-shrink-0" style={{ border: '1px solid rgba(201,169,110,0.3)' }} />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-white mb-0.5">📲 Lưu JAMA HOME ra màn hình chính</p>
          {isIOS ? (
            <p className="text-[10px] leading-relaxed" style={{ color: '#B8B0A0' }}>
              Bấm nút <span className="text-[#C9A96E] font-semibold">Chia sẻ ⬆️</span> (thanh dưới Safari) → kéo xuống chọn <span className="text-[#C9A96E] font-semibold">Thêm vào MH chính</span>
            </p>
          ) : canNativeInstall ? (
            <p className="text-[10px] leading-relaxed" style={{ color: '#B8B0A0' }}>
              Một chạm là có app trên màn hình — vào nhanh, chấm công nhanh
            </p>
          ) : (
            <p className="text-[10px] leading-relaxed" style={{ color: '#B8B0A0' }}>
              Bấm nút <span className="text-[#C9A96E] font-semibold">⋮ (3 chấm)</span> góc phải Chrome → <span className="text-[#C9A96E] font-semibold">Thêm vào Màn hình chính</span>
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5 flex-shrink-0">
          {!isIOS && canNativeInstall && (
            <button onClick={nativeInstall} className="text-[11px] font-bold px-3 py-1.5 rounded-lg text-white" style={{ background: 'linear-gradient(135deg, #C9A96E, #9A7542)' }}>
              Cài đặt
            </button>
          )}
          <button onClick={dismiss} className="text-[10px] px-3 py-1.5 rounded-lg" style={{ color: '#B8B0A0', background: 'rgba(255,255,255,0.06)' }}>
            Đã hiểu
          </button>
        </div>
      </div>
    </div>
  );
}
