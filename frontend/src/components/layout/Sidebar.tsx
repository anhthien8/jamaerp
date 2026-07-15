'use client';

import { useState, useEffect, useMemo, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import SearchModal from '@/components/ui/SearchModal';
import NotificationCenter from '@/components/ui/NotificationCenter';
import OnboardingChecklist from '@/components/ui/OnboardingChecklist';
import GuidedTour from '@/components/ui/GuidedTour';
import { getPermissions, getRoleLabel, UserRole } from '@/lib/roles';

// ── SVG Icons (reusable) ──────────────────────────────────────────────
const Icon = {
  dashboard: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>,
  pipeline: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>,
  projects: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7-6H4a2 2 0 0 0-2 2v16z" /><path d="M14 2v6h6" /></svg>,
  customers: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>,
  contracts: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>,
  quotations: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5H2v7l6.29 6.29c.94.94 2.48.94 3.42 0l4.58-4.58c.94-.94.94-2.48 0-3.42L9 5z" /><circle cx="6" cy="9" r="1" /></svg>,
  inventory: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg>,
  accounting: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1v22" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>,
  hr: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></svg>,
  pnl: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>,
  finance: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" /></svg>,
  reports: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" /></svg>,
  settings: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>,
  more: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></svg>,
  attendance: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>,
  approvals: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>,
  kpi: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" /><line x1="4" y1="20" x2="20" y2="20" /></svg>,
};

// ── All nav items (flat list) ────────────────────────────────────────
const ALL_ITEMS = [
  { href: '/', label: 'Tổng quan', icon: Icon.dashboard },
  { href: '/attendance', label: 'Chấm công', icon: Icon.attendance },
  { href: '/approvals', label: 'Phê duyệt', icon: Icon.approvals },
  { href: '/leads', label: 'Quy trình', icon: Icon.pipeline, perm: 'canViewLeads' },
  { href: '/quote-tool', label: 'Báo giá tức thì', icon: Icon.quotations, perm: 'canViewLeads' },
  { href: '/projects', label: 'Dự án', icon: Icon.projects, perm: 'canViewProjects' },
  { href: '/customers', label: 'Khách hàng', icon: Icon.customers },
  { href: '/contracts', label: 'Hợp đồng', icon: Icon.contracts, perm: 'canViewContracts' },
  { href: '/quotations', label: 'Báo giá', icon: Icon.quotations, perm: 'canViewQuotations' },
  { href: '/inventory', label: 'Kho vật tư', icon: Icon.inventory, perm: 'canViewInventory' },
  { href: '/accounting', label: 'Kế toán', icon: Icon.accounting, perm: 'canViewAccounting' },
  { href: '/hr', label: 'Nhân sự', icon: Icon.hr, perm: 'canViewHR' },
  { href: '/kpi', label: 'KPI', icon: Icon.kpi },
  { href: '/pl', label: 'P&L', icon: Icon.pnl, perm: 'canViewPnL' },
  { href: '/finance', label: 'Tài chính', icon: Icon.finance, perm: 'canViewAccounting' },
  { href: '/reports', label: 'Báo cáo', icon: Icon.reports, perm: 'canViewReports' },
  { href: '/feedback', label: 'Feedback', icon: Icon.reports, perm: 'canViewReports' },
  { href: '/settings', label: 'Cài đặt', icon: Icon.settings },
];

// ── Role → essential items (KISS: only show what matters most) ───────
const ROLE_ESSENTIALS: Record<string, string[]> = {
  admin:      ['/', '/approvals', '/leads', '/projects', '/contracts', '/accounting', '/feedback'],
  executive:  ['/', '/projects', '/pl', '/reports'],
  leader:     ['/', '/approvals', '/leads', '/quote-tool', '/projects', '/reports'],
  data_entry: ['/', '/attendance', '/leads', '/quote-tool', '/projects', '/contracts'],
  designer:   ['/', '/attendance', '/projects', '/quotations'],
  pm:         ['/', '/attendance', '/approvals', '/projects', '/inventory', '/contracts'],
  accountant: ['/', '/approvals', '/attendance', '/accounting', '/pl', '/finance'],
  purchasing: ['/', '/attendance', '/projects', '/inventory'],
};

export default function Sidebar({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout, isDemo, mode, setMode } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  // Track desktop breakpoint (1024px = lg) — SSR-safe
  const isDesktop = useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia('(min-width: 1024px)');
      mq.addEventListener('change', cb);
      return () => mq.removeEventListener('change', cb);
    },
    () => window.matchMedia('(min-width: 1024px)').matches,
    () => false, // SSR fallback
  );

  // Global keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => {
    void Promise.resolve().then(() => setMobileOpen(false));
  }, [pathname]);

  // KISS: Split nav into essential items (always visible) + extra items (expandable)
  const perms = user ? getPermissions(user.role as UserRole) : null;
  const [showMore, setShowMore] = useState(false);

  const { essentialItems, extraItems } = useMemo(() => {
    if (!perms) return { essentialItems: [], extraItems: [] };
    const allowed = ALL_ITEMS.filter(item => {
      if (!item.perm) return true;
      return (perms as unknown as Record<string, unknown>)[item.perm] === true;
    });
    const essentialHrefs = ROLE_ESSENTIALS[user?.role || 'admin'] || ROLE_ESSENTIALS.admin;
    const essential = allowed.filter(item => essentialHrefs.includes(item.href));
    const extra = allowed.filter(item => !essentialHrefs.includes(item.href));
    return { essentialItems: essential, extraItems: extra };
  }, [perms, user?.role]);

  if (!user) return <>{children}</>;
  const sidebarContent = (
    <>
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 h-16 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
          <span className="text-sm font-bold text-white tracking-tight">J</span>
        </div>
        <div className="animate-fade">
          <span className="text-base font-bold gold-gradient tracking-tight">JAMA</span>
          <span className="text-base font-light text-[var(--text-secondary)] ml-1">HOME</span>
        </div>
      </div>

      {/* Search button */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={() => setSearchOpen(true)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm transition-all"
          style={{ background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <span className="flex-1 text-left text-xs">Tìm kiếm...</span>
          <kbd className="text-[10px] font-mono px-1 py-0.5 rounded" style={{ background: 'var(--surface-3)', color: 'var(--text-disabled)' }}>
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {/* Essential items — always visible */}
        {essentialItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? 'page' : undefined}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 relative"
              style={{
                background: isActive ? 'rgba(201,169,110,0.1)' : 'transparent',
                color: isActive ? 'var(--gold-400)' : 'var(--text-tertiary)',
              }}
              onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text-primary)'; } }}
              onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-tertiary)'; } }}
            >
              {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full" style={{ background: 'var(--gold-500)' }} />}
              <span className="flex-shrink-0">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}

        {/* "Xem thêm" toggle — only when there are extra items */}
        {extraItems.length > 0 && (
          <>
            <button
              onClick={() => setShowMore(!showMore)}
              className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm w-full transition-all duration-200"
              style={{ color: 'var(--text-disabled)' }}
            >
              <span className="flex-shrink-0 transition-transform duration-200" style={{ transform: showMore ? 'rotate(90deg)' : 'rotate(0deg)' }}>{Icon.more}</span>
              <span className="font-medium">{showMore ? 'Thu gọn' : 'Xem thêm'}</span>
              {!showMore && <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-disabled)' }}>{extraItems.length}</span>}
            </button>

            {/* Extra items — expandable */}
            {showMore && extraItems.map((item) => {
              const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-200 relative"
                  style={{
                    background: isActive ? 'rgba(201,169,110,0.1)' : 'transparent',
                    color: isActive ? 'var(--gold-400)' : 'var(--text-disabled)',
                  }}
                  onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text-secondary)'; } }}
                  onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-disabled)'; } }}
                >
                  {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full" style={{ background: 'var(--gold-500)' }} />}
                  <span className="flex-shrink-0">{item.icon}</span>
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* Mode Toggle Badge */}
      <div className="px-3 mb-3">
        <button
          onClick={() => setMode(mode === 'demo' ? 'work' : 'demo')}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-[0.6875rem] font-semibold transition-all duration-200 cursor-pointer select-none"
          style={{
            background: mode === 'demo' ? 'rgba(251,191,36,0.1)' : 'rgba(74,222,128,0.08)',
            border: `1px solid ${mode === 'demo' ? 'rgba(251,191,36,0.25)' : 'rgba(74,222,128,0.2)'}`,
            color: mode === 'demo' ? '#FBBF24' : '#4ADE80',
          }}
          title={mode === 'demo' ? 'Chuyển sang Chế độ Làm việc' : 'Chuyển sang Chế độ Tập luyện'}
        >
          <span className="text-sm">{mode === 'demo' ? '\u{1F3AF}' : '\u{1F4BC}'}</span>
          <span>{mode === 'demo' ? 'TẬP LUYỆN' : 'LÀM VIỆC'}</span>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      {/* User */}
      <div className="px-3 py-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))' }}
          >
            <span className="text-xs font-semibold text-white">
              {user.full_name?.split(' ').pop()?.charAt(0) || 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[0.8125rem] font-medium text-[var(--text-primary)] truncate">{user.full_name}</p>
            <p className="text-[0.6875rem] text-[var(--text-disabled)]">{getRoleLabel(user.role as UserRole)}</p>
          </div>
          <button
            onClick={logout}
            className="p-1.5 rounded-lg transition-colors hover:bg-[rgba(248,113,113,0.1)]"
            title="Đăng xuất"
            aria-label="Đăng xuất"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
        <p className="text-center text-[10px] mt-2 select-none" style={{ color: 'var(--text-disabled)', opacity: 0.8 }} title="Người phát triển hệ thống">
          Dev bởi Dương Anh Thiện
        </p>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen">
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-4 left-4 z-50 p-2 rounded-xl lg:hidden"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
        aria-label="Mở menu"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-primary)" strokeWidth="2" strokeLinecap="round">
          <path d="M3 12h18M3 6h18M3 18h18" />
        </svg>
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        </div>
      )}

      {/* Desktop sidebar */}
      <aside
        style={{
          width: 256,
          transition: 'width 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        className="fixed top-0 left-0 h-full z-40 hidden lg:flex flex-col border-r bg-[var(--surface-1)]"
        role="navigation"
        aria-label="Main navigation"
      >
        {sidebarContent}

        {/* Sidebar always expanded — no collapse toggle */}
      </aside>

      {/* Mobile sidebar */}
      <aside
        style={{
          transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        className="fixed top-0 left-0 w-64 h-full z-50 flex flex-col border-r bg-[var(--surface-1)] lg:hidden"
      >
        {sidebarContent}
      </aside>

      {/* Single main — children rendered ONCE */}
      <main
        className="flex-1 min-h-screen pt-14 lg:pt-0"
        style={{
          marginLeft: isDesktop ? 256 : 0,
          transition: 'margin-left 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Mode Banner */}
        {mode === 'demo' ? (
          <div className="mx-4 mt-4 px-4 py-2.5 rounded-xl flex items-center justify-between" style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)' }}>
            <div className="flex items-center gap-2">
              <span>🎯</span>
              <span className="text-xs font-semibold" style={{ color: '#FBBF24' }}>CHẾ ĐỘ TẬP LUYỆN</span>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>— Dữ liệu mẫu, dùng để demo cho nhân sự</span>
            </div>
            <button onClick={() => setMode('work')} className="text-[10px] px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors font-medium">
              Chuyển sang Work →
            </button>
          </div>
        ) : (
          <div className="mx-4 mt-4 px-4 py-2.5 rounded-xl flex items-center justify-between" style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.15)' }}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-emerald-400">CHẾ ĐỘ LÀM VIỆC</span>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>— Dữ liệu thật từ hệ thống</span>
            </div>
            <button onClick={() => setMode('demo')} className="text-[10px] px-2 py-1 rounded-lg bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors font-medium">
              ← Demo
            </button>
          </div>
        )}
        {children}
      </main>

      {/* Global Search Modal */}
      <SearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />

      {/* Notification Center */}
      <NotificationCenter />

      {/* Onboarding Checklist (first login) */}
      <OnboardingChecklist />
      <GuidedTour />
    </div>
  );
}
