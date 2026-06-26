'use client';

import { useState, useCallback, createContext, useContext, ReactNode } from 'react';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'info' | 'warning' | 'error';
}

interface ToastContextType {
  toast: (message: string, type?: Toast['type']) => void;
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

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, message, type }]);
    // Error toasts stay longer (4s) for readability
    const duration = type === 'error' ? 4000 : 3000;
    setTimeout(() => dismiss(id), duration);
  }, [dismiss]);

  const colors: Record<string, string> = {
    success: '#10B981',
    info: '#3B82F6',
    warning: '#F59E0B',
    error: '#EF4444',
  };

  const icons: Record<string, string> = {
    success: '✅',
    info: 'ℹ️',
    warning: '⚠️',
    error: '❌',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}

      {/* Toast container — accessible live region */}
      <div
        className="fixed top-4 right-4 z-[9999] space-y-2"
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
            <span aria-hidden="true">{icons[t.type]}</span>
            <span className="flex-1">{t.message}</span>
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
