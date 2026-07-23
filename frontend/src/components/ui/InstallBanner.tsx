'use client';

import { useState, useEffect } from 'react';

/**
 * InstallBanner — hiện hướng dẫn "Lưu ra màn hình chính" cho mobile users.
 * Chỉ hiện 1 lần, lưu localStorage để không lặp lại.
 */
export default function InstallBanner() {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    // Không hiện nếu đã dismiss hoặc đang ở standalone mode (đã cài)
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    const wasDismissed = localStorage.getItem('jama_install_dismissed') === 'true';
    if (isStandalone || wasDismissed) return;

    // Chỉ hiện trên mobile
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (!isMobile) return;

    const t = setTimeout(() => setVisible(true), 3000);
    return () => clearTimeout(t);
  }, []);

  const dismiss = () => {
    setDismissed(true);
    setVisible(false);
    localStorage.setItem('jama_install_dismissed', 'true');
  };

  if (!visible || dismissed) return null;

  const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
  const isAndroid = /Android/i.test(navigator.userAgent);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[90] p-3 animate-in" style={{ background: 'linear-gradient(135deg, #0D1526, #1A535C)', borderTop: '1px solid rgba(201,169,110,0.3)' }}>
      <div className="max-w-lg mx-auto flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)' }}>
          <span className="text-lg font-bold text-white">J</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-white mb-1">📲 Lưu JAMA ra màn hình chính</p>
          {isIOS ? (
            <p className="text-[10px]" style={{ color: '#9BA7B4' }}>
              Bấm nút <span className="text-[#C9A96E]">⬆️ Chia sẻ</span> → <span className="text-[#C9A96E]">Thêm vào Màn hình chính</span>
            </p>
          ) : (
            <p className="text-[10px]" style={{ color: '#9BA7B4' }}>
              Bấm nút <span className="text-[#C9A96E]">⋮ (3 chấm)</span> → <span className="text-[#C9A96E]">Thêm vào Màn hình chính</span>
            </p>
          )}
          <p className="text-[9px] mt-0.5" style={{ color: '#6B7683' }}>Truy cập nhanh, không cần mở trình duyệt</p>
        </div>
        <button onClick={dismiss} className="text-[10px] px-2 py-1 rounded-lg flex-shrink-0" style={{ color: '#9BA7B4', background: 'rgba(255,255,255,0.05)' }}>
          Đã hiểu
        </button>
      </div>
    </div>
  );
}
