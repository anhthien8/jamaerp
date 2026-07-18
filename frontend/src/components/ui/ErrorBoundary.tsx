'use client';

import React, { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-[#0A0F1C]">
          <div className="max-w-md mx-4 text-center p-8 rounded-2xl" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4" style={{ background: 'rgba(239,68,68,0.15)' }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Có lỗi xảy ra</h2>
            <p className="text-sm text-gray-400 mb-3">
              Hệ thống gặp sự cố không mong muốn. Vui lòng tải lại trang.
            </p>
            {/* Chi tiết kỹ thuật — để chụp màn hình gửi đội dev là biết ngay lỗi gì */}
            {this.state.error && (
              <div className="mb-5 p-3 rounded-lg text-left overflow-auto max-h-40" style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <p className="text-[11px] font-mono break-all" style={{ color: '#F87171' }}>
                  {this.state.error.name}: {this.state.error.message}
                </p>
                {this.state.error.stack && (
                  <p className="text-[10px] font-mono mt-1 whitespace-pre-wrap break-all" style={{ color: 'rgba(255,255,255,0.45)' }}>
                    {this.state.error.stack.split('\n').slice(1, 4).join('\n')}
                  </p>
                )}
              </div>
            )}
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)', color: 'white' }}
            >
              Tải lại trang
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
