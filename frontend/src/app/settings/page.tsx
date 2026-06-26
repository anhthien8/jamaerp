'use client';

import { useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <h1 className="text-2xl font-bold mb-6">⚙️ Cài đặt</h1>

        <div className="max-w-2xl space-y-6">
          {/* Profile */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">Thông tin cá nhân</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#C9A96E] to-[#1A535C] flex items-center justify-center">
                  <span className="text-2xl font-bold text-white">{user.full_name?.charAt(0)}</span>
                </div>
                <div>
                  <p className="font-semibold text-lg">{user.full_name}</p>
                  <p className="text-sm text-[var(--text-secondary)]">{user.email}</p>
                  <p className="text-xs text-[var(--text-muted)] capitalize mt-0.5">
                    {user.role} · {user.department}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Telegram */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">🤖 Telegram Bot</h2>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">Telegram ID</span>
                <span className="text-sm font-mono">
                  {user.telegram_user_id || '— Chưa liên kết'}
                </span>
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Liên kết Telegram để nhận briefing hàng ngày và nhập lead qua bot.
              </p>
            </div>
          </div>

          {/* System */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">Hệ thống</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Phiên bản</span>
                <span className="font-mono">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Backend</span>
                <span className="font-mono">FastAPI</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">AI Model</span>
                <span className="font-mono">Groq / llama-3.3-70b</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Sidebar>
  );
}
