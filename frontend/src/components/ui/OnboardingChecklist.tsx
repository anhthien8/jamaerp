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

// Training checklist items per role — actionable tasks
const TRAINING_CHECKLIST: Record<string, { id: string; icon: string; title: string; href: string }[]> = {
  data_entry: [
    { id: 'view_pipeline', icon: '🔄', title: 'Xem Pipeline leads', href: '/leads' },
    { id: 'create_lead', icon: '➕', title: 'Tạo lead mới', href: '/leads' },
    { id: 'use_quote', icon: '⚡', title: 'Dùng báo giá tức thì', href: '/quote-tool' },
    { id: 'view_project', icon: '📋', title: 'Xem tiến độ dự án', href: '/projects' },
    { id: 'check_reports', icon: '📊', title: 'Xem báo cáo cá nhân', href: '/reports' },
  ],
  supervisor: [
    { id: 'view_projects', icon: '📋', title: 'Xem danh sách dự án', href: '/projects' },
    { id: 'update_task', icon: '✅', title: 'Cập nhật trạng thái task', href: '/projects' },
    { id: 'check_inventory', icon: '📦', title: 'Kiểm tra kho vật tư', href: '/inventory' },
    { id: 'create_quotation', icon: '💬', title: 'Tạo báo giá', href: '/quotations' },
    { id: 'check_in', icon: '⏰', title: 'Chấm công ngày', href: '/attendance' },
  ],
  accountant: [
    { id: 'view_accounting', icon: '💰', title: 'Xem sổ kế toán', href: '/accounting' },
    { id: 'create_transaction', icon: '➕', title: 'Tạo giao dịch mới', href: '/accounting' },
    { id: 'view_pl', icon: '📊', title: 'Xem báo cáo P&L', href: '/pl' },
    { id: 'check_payroll', icon: '💵', title: 'Kiểm tra lương', href: '/hr' },
    { id: 'approve_transactions', icon: '✅', title: 'Duyệt giao dịch chờ', href: '/approvals' },
  ],
  admin: [
    { id: 'view_dashboard', icon: '📊', title: 'Xem dashboard tổng quan', href: '/' },
    { id: 'configure_ai', icon: '🧠', title: 'Cấu hình AI Model', href: '/settings' },
    { id: 'manage_users', icon: '👥', title: 'Quản lý người dùng', href: '/users' },
    { id: 'setup_automation', icon: '🤖', title: 'Cấu hình tự động hóa', href: '/settings' },
    { id: 'create_lead', icon: '🔄', title: 'Tạo lead đầu tiên', href: '/leads' },
  ],
  leader: [
    { id: 'view_pipeline', icon: '🔄', title: 'Xem pipeline team', href: '/leads' },
    { id: 'assign_lead', icon: '👤', title: 'Phân công lead cho team', href: '/leads' },
    { id: 'view_projects', icon: '📋', title: 'Theo dõi dự án team', href: '/projects' },
    { id: 'check_approvals', icon: '✅', title: 'Duyệt yêu cầu chờ', href: '/approvals' },
    { id: 'view_reports', icon: '📊', title: 'Xem báo cáo hiệu suất', href: '/reports' },
  ],
  executive: [
    { id: 'view_dashboard', icon: '📊', title: 'Xem tổng quan điều hành', href: '/' },
    { id: 'view_pl', icon: '📈', title: 'Xem báo cáo P&L', href: '/pl' },
    { id: 'check_projects', icon: '📋', title: 'Theo dõi dự án', href: '/projects' },
    { id: 'view_reports', icon: '📊', title: 'Xem phân tích kinh doanh', href: '/reports' },
    { id: 'review_feedback', icon: '💬', title: 'Xem feedback nhân sự', href: '/feedback' },
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

function getProgressKey(role: string) {
  return `jama_training_progress_${role}`;
}

export function isOnboarded(role: string): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(getOnboardKey(role)) === 'true';
}

export function clearOnboarding(role: string) {
  localStorage.removeItem(getOnboardKey(role));
  localStorage.removeItem(getProgressKey(role));
}

export function getTrainingProgress(role: string): string[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(getProgressKey(role)) || '[]');
  } catch { return []; }
}

export function markTrainingItem(role: string, itemId: string) {
  const progress = getTrainingProgress(role);
  if (!progress.includes(itemId)) {
    progress.push(itemId);
    localStorage.setItem(getProgressKey(role), JSON.stringify(progress));
  }
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
  const checklist = TRAINING_CHECKLIST[role] || TRAINING_CHECKLIST.data_entry;
  const completedItems = getTrainingProgress(role);

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
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg rounded-2xl overflow-hidden animate-in" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}>
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

        <div className="px-6 pb-4 min-h-[280px]">
          {/* Step 1: Welcome + role cards */}
          {step === 0 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Chào mừng bạn đến với JAMA HOME</h2>
              <p className="text-sm text-[var(--text-muted)] mb-4">Dưới đây là các trang quan trọng cho vai trò của bạn:</p>
              <div className="space-y-2.5">
                {cards.map(card => (
                  <Link key={card.href} href={card.href} onClick={() => close(true)}
                    className="flex items-center gap-3 p-3 rounded-xl transition-all hover:opacity-80 group"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <span className="text-xl flex-shrink-0">{card.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-white group-hover:text-[#C9A96E] transition-colors">{card.title}</p>
                      <p className="text-xs text-[var(--text-muted)] truncate">{card.description}</p>
                    </div>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-disabled)" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Training checklist */}
          {step === 1 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Checklist huấn luyện</h2>
              <p className="text-sm text-[var(--text-muted)] mb-1">Hoàn thành từng mục để nắm vững hệ thống:</p>
              {/* Progress bar */}
              <div className="flex items-center gap-2 mb-4">
                <div className="flex-1 h-2 rounded-full" style={{ background: 'var(--surface-3)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${(completedItems.length / checklist.length) * 100}%`, background: 'linear-gradient(90deg, #C9A96E, #B8935A)' }} />
                </div>
                <span className="text-[10px] font-mono" style={{ color: '#C9A96E' }}>{completedItems.length}/{checklist.length}</span>
              </div>
              <div className="space-y-2 max-h-[240px] overflow-y-auto">
                {checklist.map(item => {
                  const done = completedItems.includes(item.id);
                  return (
                    <Link key={item.id} href={item.href} onClick={() => { markTrainingItem(role, item.id); }}
                      className="flex items-center gap-3 p-3 rounded-xl transition-all hover:opacity-80 group"
                      style={{ background: done ? 'rgba(16,185,129,0.08)' : 'var(--surface-2)', border: `1px solid ${done ? 'rgba(16,185,129,0.2)' : 'var(--border-subtle)'}` }}>
                      <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ background: done ? '#10B981' : 'var(--surface-3)', border: `1px solid ${done ? '#10B981' : 'var(--border-subtle)'}` }}>
                        {done && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>}
                      </div>
                      <span className="text-xl flex-shrink-0">{item.icon}</span>
                      <span className={`text-sm ${done ? 'line-through text-[var(--text-muted)]' : 'text-white'}`}>{item.title}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 3: Keyboard shortcuts + start tour */}
          {step === 2 && (
            <div className="animate-in">
              <h2 className="text-lg font-bold text-white mb-1">Sẵn sàng bắt đầu!</h2>
              <p className="text-sm text-[var(--text-muted)] mb-3">Phím tắt hữu ích:</p>
              <div className="space-y-2 mb-4">
                {SHORTCUTS.map(sc => (
                  <div key={sc.keys} className="flex items-center justify-between p-2 rounded-lg" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <span className="text-xs text-[var(--text-secondary)]">{sc.description}</span>
                    <div className="flex items-center gap-1">
                      {sc.keys.split(' + ').map((k, i) => (
                        <span key={i}>
                          {i > 0 && <span className="text-[var(--text-disabled)] text-[10px] mx-0.5">+</span>}
                          <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold" style={{ background: 'var(--surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>{k}</kbd>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => { close(true); startGuidedTour(); }}
                className="w-full flex items-center gap-3 p-3 rounded-xl transition-all hover:opacity-90 group text-left"
                style={{ background: 'rgba(201,169,110,0.1)', border: '1px solid rgba(201,169,110,0.3)' }}>
                <span className="text-lg">🧭</span>
                <div className="flex-1">
                  <p className="text-sm font-bold text-[#C9A96E]">Bắt đầu hướng dẫn từng bước</p>
                  <p className="text-[10px] text-[var(--text-muted)]">Đi qua từng trang theo workflow của bạn</p>
                </div>
              </button>
              <div className="mt-3 flex items-center gap-2 cursor-pointer select-none" onClick={() => setDontShowAgain(!dontShowAgain)}>
                <div className="w-4 h-4 rounded flex items-center justify-center transition-all"
                  style={{ background: dontShowAgain ? '#C9A96E' : 'var(--surface-3)', border: `1px solid ${dontShowAgain ? '#C9A96E' : 'var(--border-subtle)'}` }}>
                  {dontShowAgain && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>}
                </div>
                <span className="text-xs text-[var(--text-muted)]">Không hiển thị lại</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 flex items-center justify-between">
          <button onClick={() => close(true)}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-80"
            style={{ background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
            Bỏ qua
          </button>
          <button onClick={next}
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95"
            style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)' }}>
            {step === 2 ? 'Hoàn thành' : 'Tiếp theo'}
          </button>
        </div>
      </div>
    </div>
  );
}
