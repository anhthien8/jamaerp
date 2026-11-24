'use client';

import { useState, useCallback, createContext, useContext, ReactNode } from 'react';
import LineIcon from '@/components/ui/LineIcon';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'info' | 'warning' | 'error';
  /** Nút kèm theo, vd «Hoàn tác» cho thao tác 1 chạm. Bấm là chạy `lam` rồi cất toast. */
  hanhDong?: { nhan: string; lam: () => void };
}

interface ToastContextType {
  toast: (message: string, type?: Toast['type'], hanhDong?: Toast['hanhDong']) => void;
}

const ToastContext = createContext<ToastContextType>({
  toast: () => {},
});

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = useCallback((message: string, type: Toast['type'] = 'info', hanhDong?: Toast['hanhDong']) => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, message, type, hanhDong }]);
    // Error toasts stay longer (4s) for readability; có nút Hoàn tác thì 6s cho kịp bấm
    const duration = hanhDong ? 6000 : type === 'error' ? 4000 : 3000;
    setTimeout(() => dismiss(id), duration);
  }, [dismiss]);

  const colors: Record<string, string> = {
    success: '#10B981',
    info: '#3B82F6',
    warning: '#F59E0B',
    error: '#EF4444',
  };

  const icons: Record<string, string> = {
    success: 'check',
    info: 'info',
    warning: 'alert',
    error: 'xCircle',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}

      {/* Toast container — accessible live region */}
      <div
        className="fixed top-4 right-4 left-4 sm:left-auto z-[9999] space-y-2"
        role="status"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map(t => (
          <div
            key={t.id}
            className="px-4 py-3 rounded-xl shadow-lg backdrop-blur-md flex items-center gap-2 text-sm font-medium animate-in"
            style={{
              background: `linear-gradient(135deg, ${colors[t.type]}20, ${colors[t.type]}08)`,
              border: `1px solid ${colors[t.type]}30`,
              color: colors[t.type],
              minWidth: 280,
            }}
          >
            <LineIcon name={icons[t.type]} size={16} color="currentColor" />
            <span className="flex-1">{t.message}</span>
            {t.hanhDong && (
              <button
                onClick={() => { t.hanhDong?.lam(); dismiss(t.id); }}
                className="ml-1 px-3 min-h-[32px] rounded-lg text-xs font-bold underline underline-offset-2"
                style={{ color: colors[t.type] }}
              >
                {t.hanhDong.nhan}
              </button>
            )}
            {/* Dismiss button */}
            <button
              onClick={() => dismiss(t.id)}
              className="ml-2 w-5 h-5 rounded flex items-center justify-center opacity-60 hover:opacity-100 transition-opacity"
              style={{ color: colors[t.type] }}
              aria-label="Đóng thông báo"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
