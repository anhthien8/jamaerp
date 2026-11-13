'use client';

import { useState, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { BRAND_NAME, BRAND_SLOGAN } from '@/lib/brand';
import LineIcon from '@/components/ui/LineIcon';

function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  // Quên mật khẩu — mã gửi qua Telegram đã liên kết
  const [forgotOpen, setForgotOpen] = useState(false);
  const [fpStep, setFpStep] = useState<'request' | 'reset'>('request');
  const [fpEmail, setFpEmail] = useState('');
  const [fpCode, setFpCode] = useState('');
  const [fpNewPass, setFpNewPass] = useState('');
  const [fpMsg, setFpMsg] = useState('');
  const [fpBusy, setFpBusy] = useState(false);

  const fpRequest = async () => {
    if (!fpEmail.trim()) { setFpMsg('Nhập email hoặc tên đăng nhập trước'); return; }
    setFpBusy(true); setFpMsg('');
    try {
      const r = await api.forgotPassword(fpEmail.trim());
      setFpMsg(r.message);
      setFpStep('reset');
    } catch (e) { setFpMsg(e instanceof Error ? e.message : 'Không gửi được mã'); }
    finally { setFpBusy(false); }
  };

  const fpReset = async () => {
    if (fpNewPass.length < 6) { setFpMsg('Mật khẩu mới cần ít nhất 6 ký tự'); return; }
    setFpBusy(true); setFpMsg('');
    try {
      const r = await api.resetPassword(fpEmail.trim(), fpCode.trim(), fpNewPass);
      setFpMsg(`✓ ${r.message}`);
      setForgotOpen(false); setFpStep('request'); setFpCode(''); setFpNewPass('');
      setEmail(fpEmail.trim()); setPassword('');
      setError('Đã đặt lại mật khẩu — đăng nhập bằng mật khẩu mới.');
    } catch (e) { setFpMsg(e instanceof Error ? e.message : 'Đặt lại thất bại'); }
    finally { setFpBusy(false); }
  };

  // Bị đá về đây do phiên hết hạn — nói rõ lý do thay vì để người dùng ngơ ngác
  const hetHan = useSearchParams().get('het_han') === '1';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
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
              className="h-24 sm:h-28 w-auto max-w-[280px] mx-auto mb-3 object-contain"
              onError={(e) => {
                // Fallback nếu ảnh remote lỗi (offline/hotlink): hiện chữ
                const el = e.currentTarget;
                el.style.display = 'none';
                el.insertAdjacentHTML('afterend', '<h1 class="text-3xl font-bold gold-gradient">JAMA HOME</h1>');
              }}
            />
            <p className="text-[var(--text-secondary)] mt-1">Hệ thống Quản lý ERP</p>
          </div>

          {/* Hướng dẫn đăng nhập */}
          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-xs text-center">
            Đăng nhập bằng tên ngắn (vd <span className="font-mono font-semibold">admin</span>) hoặc email đầy đủ.
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="login-email" className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
                Email hoặc tên đăng nhập
              </label>
              <input
                suppressHydrationWarning
                id="login-email"
                type="text"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:border-[#C9A96E] focus:ring-1 focus:ring-[#C9A96E]/50 outline-none transition-all"
                placeholder="admin (hoặc admin@jamahome.vn)"
                required
                autoComplete="username"
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

            {hetHan && !error && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-sm">
                Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.
              </div>
            )}

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
              ) : (
                'Đăng nhập'
              )}
            </button>
          </form>

          {/* Quên mật khẩu */}
          <div className="mt-4">
            {!forgotOpen ? (
              <button type="button" onClick={() => { setForgotOpen(true); setFpEmail(email); setFpMsg(''); }}
                className="text-xs text-[var(--text-muted)] hover:text-[#C9A96E] transition-colors underline">
                Quên mật khẩu?
              </button>
            ) : (
              <div className="p-4 rounded-xl space-y-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-[var(--text-secondary)]">Đặt lại mật khẩu</p>
                  <button type="button" onClick={() => { setForgotOpen(false); setFpStep('request'); setFpMsg(''); }} className="text-xs text-[var(--text-muted)] hover:text-white">✕</button>
                </div>
                {fpStep === 'request' ? (
                  <>
                    <p className="text-xs text-[var(--text-muted)]">Mã xác nhận sẽ gửi qua <b>Telegram</b> bạn đã liên kết trong Cài đặt. Chưa liên kết? Nhờ Admin đặt lại hộ.</p>
                    <input type="text" value={fpEmail} onChange={e => setFpEmail(e.target.value)} placeholder="Email hoặc tên đăng nhập"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:border-[#C9A96E]" />
                    <button type="button" onClick={fpRequest} disabled={fpBusy}
                      className="w-full py-2 rounded-lg bg-[#C9A96E] text-black text-sm font-semibold disabled:opacity-50">
                      {fpBusy ? 'Đang gửi...' : 'Gửi mã qua Telegram'}
                    </button>
                  </>
                ) : (
                  <>
                    <input type="text" inputMode="numeric" value={fpCode} onChange={e => setFpCode(e.target.value)} placeholder="Mã 6 số từ Telegram"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white font-mono focus:outline-none focus:border-[#C9A96E]" />
                    <input type="password" value={fpNewPass} onChange={e => setFpNewPass(e.target.value)} placeholder="Mật khẩu mới (≥ 6 ký tự)"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:border-[#C9A96E]" />
                    <div className="flex gap-2">
                      <button type="button" onClick={fpReset} disabled={fpBusy}
                        className="flex-1 py-2 rounded-lg bg-[#C9A96E] text-black text-sm font-semibold disabled:opacity-50">
                        {fpBusy ? 'Đang đặt lại...' : 'Đặt lại mật khẩu'}
                      </button>
                      <button type="button" onClick={() => setFpStep('request')} className="px-3 py-2 rounded-lg text-xs text-[var(--text-muted)] border border-white/10">Gửi lại mã</button>
                    </div>
                  </>
                )}
                {fpMsg && <p className="text-xs" style={{ color: fpMsg.startsWith('✓') ? '#34D399' : '#FBBF24' }}>{fpMsg}</p>}
              </div>
            )}
          </div>

          {/* Footer */}
          <p className="text-center text-xs font-medium mt-6" style={{ color: 'var(--text-secondary)' }}>
            {BRAND_NAME} <span style={{ opacity: 0.5 }}>·</span> {BRAND_SLOGAN}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><LineIcon name="hourglass" size={28} /></div>}>
      <LoginForm />
    </Suspense>
  );
}
