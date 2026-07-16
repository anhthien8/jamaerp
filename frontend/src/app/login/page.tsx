'use client';

import { useState, useEffect } from 'react';
import { useAuth, type AppMode } from '@/lib/auth';
import { useRouter } from 'next/navigation';

const DEMO_CREDENTIALS = [
  { email: 'admin@jamahome.vn', role: 'Admin' },
  { email: 'ceo@jamahome.vn', role: 'CEO' },
  { email: 'accountant@jamahome.vn', role: 'KT' },
  { email: 'leader@jamahome.vn', role: 'Leader' },
  { email: 'sales@jamahome.vn', role: 'Sales' },
  { email: 'supervisor@jamahome.vn', role: 'Giám sát' },
];

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedMode, setSelectedMode] = useState<AppMode>('work');
  const { login } = useAuth();
  const router = useRouter();

  // Read persisted mode after mount (avoids SSR localStorage error)
  useEffect(() => {
    const stored = localStorage.getItem('jama_mode');
    if (stored === 'demo' || stored === 'work') {
      setSelectedMode(stored);
    }
  }, []);

  const handleModeSwitch = (newMode: AppMode) => {
    setSelectedMode(newMode);
    localStorage.setItem('jama_mode', newMode);
    setError('');
    if (newMode === 'demo') {
      // Pre-fill admin email; password is shared demo123
      setEmail(DEMO_CREDENTIALS[0].email);
      setPassword('demo123');
    } else {
      // Work mode: clear fields and show clear instructions
      setEmail('');
      setPassword('');
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password, selectedMode);
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0A0F1C] via-[#111827] to-[#1A535C]/30" />
      <div className="absolute top-1/4 -left-1/4 w-96 h-96 bg-[#C9A96E]/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 -right-1/4 w-96 h-96 bg-[#1A535C]/20 rounded-full blur-3xl" />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md mx-4 animate-in">
        <div className="glass-card p-8">
          {/* Logo */}
          <div className="text-center mb-6">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://jamahome.vn/wp-content/uploads/2026/07/NEW-LOGO-JAMA-HOME-TACH-NEN-scaled.png"
              alt="JAMA HOME"
              className="h-16 w-auto mx-auto mb-3 object-contain"
              onError={(e) => {
                // Fallback nếu ảnh remote lỗi (offline/hotlink): hiện chữ
                const el = e.currentTarget;
                el.style.display = 'none';
                el.insertAdjacentHTML('afterend', '<h1 class="text-2xl font-bold gold-gradient">JAMA HOME</h1>');
              }}
            />
            <p className="text-[var(--text-secondary)] mt-1">Hệ thống Quản lý ERP</p>
          </div>

          {/* Mode Selector */}
          <div className="mb-6">
            <div
              className="flex rounded-xl p-1 gap-1"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)' }}
            >
              <button
                type="button"
                onClick={() => handleModeSwitch('demo')}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-sm font-medium transition-all duration-200"
                style={{
                  background: selectedMode === 'demo' ? 'rgba(251,191,36,0.15)' : 'transparent',
                  color: selectedMode === 'demo' ? '#FBBF24' : 'var(--text-muted)',
                  border: selectedMode === 'demo' ? '1px solid rgba(251,191,36,0.3)' : '1px solid transparent',
                }}
              >
                <span className="text-base">&#x1F3AF;</span>
                <span>Chế độ Tập luyện</span>
              </button>
              <button
                type="button"
                onClick={() => handleModeSwitch('work')}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-sm font-medium transition-all duration-200"
                style={{
                  background: selectedMode === 'work' ? 'rgba(74,222,128,0.12)' : 'transparent',
                  color: selectedMode === 'work' ? '#4ADE80' : 'var(--text-muted)',
                  border: selectedMode === 'work' ? '1px solid rgba(74,222,128,0.3)' : '1px solid transparent',
                }}
              >
                <span className="text-base">&#x1F4BC;</span>
                <span>Chế độ Làm việc</span>
              </button>
            </div>
            <p className="text-center text-[0.6875rem] mt-2" style={{ color: 'var(--text-disabled)' }}>
              {selectedMode === 'demo'
                ? 'Dùng để demo cho nhân sự — dữ liệu giả lập'
                : 'Kết nối đến hệ thống thực — dữ liệu thật'}
            </p>
          </div>

          {/* Work mode info */}
          {selectedMode === 'work' && (
            <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-xs text-center">
              Chế độ Làm việc — cần tài khoản thật từ admin. Nếu chưa có, quay lại <button type="button" onClick={() => handleModeSwitch('demo')} className="underline font-semibold">Chế độ Tập luyện</button> để demo.
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="login-email" className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
                Email
              </label>
              <input
                suppressHydrationWarning
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:border-[#C9A96E] focus:ring-1 focus:ring-[#C9A96E]/50 outline-none transition-all"
                placeholder={selectedMode === 'demo' ? 'admin@jamahome.vn' : 'email@jamahome.vn'}
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
                Mật khẩu
              </label>
              <input
                suppressHydrationWarning
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:border-[#C9A96E] focus:ring-1 focus:ring-[#C9A96E]/50 outline-none transition-all"
                placeholder="* * * * * * * *"
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white font-semibold hover:from-[#D4B97E] hover:to-[#C9A96E] disabled:opacity-50 transition-all duration-200 shadow-lg shadow-[#C9A96E]/20"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Đang đăng nhập...
                </span>
              ) : selectedMode === 'demo' ? (
                'Vào Demo'
              ) : (
                'Đăng nhập'
              )}
            </button>
          </form>

          {/* Demo Credentials — only visible in demo mode */}
          {selectedMode === 'demo' && (
            <details className="mt-5 rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)' }}>
              <summary className="cursor-pointer px-4 py-2.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors select-none flex items-center gap-2">
                <span>&#x1F511;</span> Tài khoản demo
              </summary>
              <div className="px-4 pb-3 pt-1 space-y-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {DEMO_CREDENTIALS.map(acc => (
                  <button
                    key={acc.email}
                    type="button"
                    className="w-full text-left px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors flex items-center justify-between group"
                    onClick={() => { setEmail(acc.email); setPassword('demo123'); }}
                  >
                    <span className="font-mono">{acc.email}</span>
                    <span className="opacity-0 group-hover:opacity-100 text-[#C9A96E] transition-opacity text-[10px] font-medium">
                      {acc.role} . Click de dien
                    </span>
                  </button>
                ))}
              </div>
            </details>
          )}

          {/* Footer */}
          <p className="text-center text-xs font-medium mt-6" style={{ color: 'var(--text-secondary)' }}>
            JAMA HOME <span style={{ opacity: 0.5 }}>|</span> Giải Pháp Thiết Kế Thi Công Nhà Ở Công Nghệ Toàn Diện
          </p>
          <p className="text-center text-[11px] mt-1.5" style={{ color: 'var(--text-muted)', opacity: 0.7 }}>
            Phát triển bởi <span className="gold-gradient font-medium">Dương Anh Thiện</span>
          </p>
        </div>
      </div>
    </div>
  );
}
