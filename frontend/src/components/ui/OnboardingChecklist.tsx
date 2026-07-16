'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { UserRole } from '@/lib/roles';
import { startGuidedTour } from '@/components/ui/GuidedTour';

const ROLE_PRIMARY_PAGE: Record<string, { path: string; label: string }> = {
  data_entry: { path: '/leads', label: 'Quy trình CRM' },
  supervisor: { path: '/projects', label: 'Dự án' },
  accountant: { path: '/accounting', label: 'Kế toán' },
  admin: { path: '/', label: 'Tổng quan' },
  leader: { path: '/leads', label: 'Quy trình CRM' },
  executive: { path: '/', label: 'Tổng quan' },
};

interface RoleCard {
  icon: string;
  title: string;
  description: string;
  href: string;
}

const ROLE_CARDS: Record<string, RoleCard[]> = {
  data_entry: [
    { icon: '🔄', title: 'Quy trình CRM', description: 'Quản lý leads và theo dõi quy trình bán hàng', href: '/leads' },
    { icon: '📋', title: 'Báo cáo', description: 'Xem hiệu suất cá nhân và thống kê', href: '/reports' },
    { icon: '🤝', title: 'Dự án', description: 'Theo dõi tiến độ dự án đã ký', href: '/projects' },
  ],
  supervisor: [
    { icon: '📋', title: 'Dự án', description: 'Điều phối & thi công dự án (Thiết kế/Thu mua/Dự án)', href: '/projects' },
    { icon: '📦', title: 'Kho vật tư', description: 'Theo dõi vật tư và duyệt yêu cầu', href: '/inventory' },
    { icon: '💬', title: 'Báo giá', description: 'Tạo và quản lý báo giá', href: '/quotations' },
  ],
  accountant: [
    { icon: '💰', title: 'Kế toán', description: 'Quản lý thu chi và báo cáo tài chính', href: '/accounting' },
    { icon: '📊', title: 'P&L', description: 'Báo cáo lợi nhuận - lỗ', href: '/pl' },
    { icon: '👥', title: 'Nhân sự', description: 'Quản lý lương và nhân viên', href: '/hr' },
  ],
  admin: [
    { icon: '📊', title: 'Tổng quan', description: 'Tổng quan toàn hệ thống', href: '/' },
    { icon: '🔄', title: 'Quy trình CRM', description: 'Quản lý tất cả leads', href: '/leads' },
    { icon: '⚙️', title: 'Cài đặt', description: 'Quản trị hệ thống', href: '/settings' },
  ],
  leader: [
    { icon: '🔄', title: 'Quy trình CRM', description: 'Quản lý leads của team', href: '/leads' },
    { icon: '📋', title: 'Dự án', description: 'Theo dõi dự án team', href: '/projects' },
    { icon: '📊', title: 'Báo cáo', description: 'Báo cáo hiệu suất team', href: '/reports' },
  ],
  executive: [
    { icon: '📊', title: 'Tổng quan', description: 'Tổng quan điều hành', href: '/' },
    { icon: '📈', title: 'P&L', description: 'Báo cáo lợi nhuận', href: '/pl' },
    { icon: '📋', title: 'Báo cáo', description: 'Phân tích kinh doanh', href: '/reports' },
  ],
};

const SHORTCUTS = [
  { keys: 'Ctrl + K', description: 'Tìm kiếm nhanh' },
  { keys: 'Ctrl + Enter', description: 'Gửi ghi chú' },
  { keys: 'Esc', description: 'Đóng modal' },
];

function getOnboardKey(role: string) {
  return `jama_onboarded_${role}`;
}

export function isOnboarded(role: string): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(getOnboardKey(role)) === 'true';
}

export function clearOnboarding(role: string) {
  localStorage.removeItem(getOnboardKey(role));
}

interface OnboardingChecklistProps {
  forceOpen?: boolean;
  onComplete?: () => void;
}

export default function OnboardingChecklist({ forceOpen = false, onComplete }: OnboardingChecklistProps) {
  const { user } = useAuth();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(true);

  const role = (user?.role || 'data_entry') as string;
  const primaryPage = ROLE_PRIMARY_PAGE[role] || ROLE_PRIMARY_PAGE.data_entry;
  const cards = ROLE_CARDS[role] || ROLE_CARDS.data_entry;

  useEffect(() => {
    if (forceOpen) {
      setVisible(true);
      setStep(0);
      return;
    }
    if (!user) return;
    if (!isOnboarded(user.role)) {
      const t = setTimeout(() => setVisible(true), 600);
      return () => clearTimeout(t);
    }
  }, [user, forceOpen]);

  const close = (markComplete = true) => {
    if (markComplete && dontShowAgain) {
      localStorage.setItem(getOnboardKey(role), 'true');
    }
    setVisible(false);
    setStep(0);
    onComplete?.();
  };

  const next = () => {
    if (step < 2) setStep(step + 1);
    else close(true);
  };

  if (!visible || !user) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg rounded-2xl overflow-hidden animate-in"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                <span className="text-sm font-bold text-white">J</span>
              </div>
              <span className="text-xs font-semibold text-[var(--text-muted)]">JAMA HOME</span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>
              {step + 1} / 3
            </span>
          </div>
        </div>

        {/* Step Content */}
        <div className="px-6 pb-4 min-h-[280px]">
          {/* Step 1: Welcome + role cards */}
          {step === 0 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Chào mừng bạn đến với JAMA HOME</h2>
              <p className="text-sm text-[var(--text-muted)] mb-4">Dưới đây là các trang quan trọng cho vai trò của bạn:</p>
              <div className="space-y-2.5">
                {cards.map(card => (
                  <Link
                    key={card.href}
                    href={card.href}
                    onClick={() => close(true)}
                    className="flex items-center gap-3 p-3 rounded-xl transition-all hover:opacity-80 group"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                  >
                    <span className="text-xl flex-shrink-0">{card.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-white group-hover:text-[#C9A96E] transition-colors">{card.title}</p>
                      <p className="text-xs text-[var(--text-muted)] truncate">{card.description}</p>
                    </div>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-disabled)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Keyboard shortcuts */}
          {step === 1 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Các phím tắt hữu ích</h2>
              <p className="text-sm text-[var(--text-muted)] mb-4">Sử dụng phím tắt để thao tác nhanh hơn:</p>
              <div className="space-y-3">
                {SHORTCUTS.map(sc => (
                  <div key={sc.keys} className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <span className="text-sm text-[var(--text-secondary)]">{sc.description}</span>
                    <div className="flex items-center gap-1">
                      {sc.keys.split(' + ').map((k, i) => (
                        <span key={i}>
                          {i > 0 && <span className="text-[var(--text-disabled)] text-xs mx-0.5">+</span>}
                          <kbd className="px-2 py-1 rounded-lg text-xs font-mono font-semibold" style={{ background: 'var(--surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>
                            {k}
                          </kbd>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 p-3 rounded-xl text-xs text-[var(--text-muted)]" style={{ background: 'rgba(201,169,110,0.06)', border: '1px solid rgba(201,169,110,0.15)' }}>
                <span className="text-[#C9A96E] font-semibold">Mẹo:</span> Nhấn{' '}
                <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono mx-0.5" style={{ background: 'var(--surface-3)', border: '1px solid var(--border-subtle)' }}>Ctrl+K</kbd>
                {' '}bất cứ lúc nào để tìm kiếm lead, dự án, hay khách hàng.
              </div>
            </div>
          )}

          {/* Step 3: Bắt đầu tour theo vai trò */}
          {step === 2 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Sẵn sàng bắt đầu!</h2>
              <p className="text-sm text-[var(--text-muted)] mb-4">
                Khuyên dùng: đi theo <b className="text-[#C9A96E]">hướng dẫn từng bước</b> — hệ thống sẽ dẫn bạn qua đúng trình tự công việc của vai trò <b>{primaryPage.label === 'Tổng quan' ? 'quản lý' : 'của bạn'}</b>, từ đầu ca đến cuối ca.
              </p>
              <button
                onClick={() => { close(true); startGuidedTour(); }}
                className="w-full flex items-center gap-3 p-4 rounded-xl transition-all hover:opacity-90 group text-left"
                style={{ background: 'rgba(201,169,110,0.1)', border: '1px solid rgba(201,169,110,0.3)' }}
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                  <span className="text-lg">🧭</span>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-bold text-[#C9A96E] group-hover:text-white transition-colors">
                    Bắt đầu hướng dẫn từng bước
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">Đi qua từng trang theo đúng workflow công việc của bạn</p>
                </div>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C9A96E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
              <Link
                href={primaryPage.path}
                onClick={() => close(true)}
                className="mt-2 flex items-center justify-center p-2.5 rounded-xl text-xs transition-all hover:opacity-80"
                style={{ color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
              >
                Bỏ qua — vào thẳng {primaryPage.label}
              </Link>
              <div className="mt-4 flex items-center gap-2 cursor-pointer select-none" onClick={() => setDontShowAgain(!dontShowAgain)}>
                <div
                  className="w-4 h-4 rounded flex items-center justify-center transition-all"
                  style={{
                    background: dontShowAgain ? '#C9A96E' : 'var(--surface-3)',
                    border: `1px solid ${dontShowAgain ? '#C9A96E' : 'var(--border-subtle)'}`,
                  }}
                >
                  {dontShowAgain && (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </div>
                <span className="text-xs text-[var(--text-muted)]">Khong hien thi lai</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <div className="px-6 pb-6 flex items-center justify-between">
          <button
            onClick={() => close(true)}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-80"
            style={{ background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
          >
            Bo qua
          </button>
          <button
            onClick={next}
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95"
            style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)' }}
          >
            {step === 2 ? 'Hoan thanh' : 'Tiep theo'}
          </button>
        </div>
      </div>
    </div>
  );
}
