'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import type { Lead, Project } from '@/lib/api';

// ── Types ────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  group: 'action_required' | 'recent';
  title: string;
  description: string;
  icon: string;
  href: string;
  timestamp: string; // ISO date
  read: boolean;
  type: 'overdue_lead' | 'low_progress' | 'new_assignment' | 'stage_change' | 'pending_approval';
}

// ── localStorage helpers ─────────────────────────────────────────────

const STORAGE_KEY_UNREAD = 'jama_notifications_unread';
const STORAGE_KEY_READ_IDS = 'jama_notifications_read_ids';

function getReadIds(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY_READ_IDS);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function setReadIds(ids: Set<string>) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_READ_IDS, JSON.stringify([...ids]));
}

function storeUnreadCount(count: number) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_UNREAD, String(count));
}

// ── Notification generation (from existing demo data, no backend) ─────

const THRESHOLD_DAYS = 3;

function daysSince(isoDate: string | undefined): number {
  if (!isoDate) return Infinity;
  const diff = Date.now() - new Date(isoDate).getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

export function generateNotifications(leads: Lead[], projects: Project[], readIds: Set<string>): Notification[] {
  const now = new Date();
  const notifs: Notification[] = [];

  // Overdue leads (not contacted in 3+ days)
  for (const lead of leads) {
    const days = daysSince(lead.last_contacted_at);
    if (days >= THRESHOLD_DAYS) {
      const id = `overdue-${lead.id}`;
      notifs.push({
        id,
        group: 'action_required',
        title: `Lead quá hạn: ${lead.name}`,
        description: `Chưa liên hệ ${days} ngày — ${lead.phone}${lead.address ? ' · ' + lead.address : ''}`,
        icon: '⚠️',
        href: '/leads',
        timestamp: lead.last_contacted_at || lead.updated_at,
        read: readIds.has(id),
        type: 'overdue_lead',
      });
    }
  }

  // Projects with low progress (below 40% and active)
  for (const proj of projects) {
    if (proj.status === 'active' && proj.progress < 40) {
      const id = `lowprog-${proj.id}`;
      notifs.push({
        id,
        group: 'action_required',
        title: `Tiến độ thấp: ${proj.code}`,
        description: `${proj.name} — ${proj.progress}% hoàn thành`,
        icon: '🚧',
        href: '/projects',
        timestamp: proj.updated_at,
        read: readIds.has(id),
        type: 'low_progress',
      });
    }
  }

  // Recent: simulated new assignments (based on leads updated today or yesterday)
  for (const lead of leads) {
    if (daysSince(lead.updated_at) <= 1) {
      const id = `recent-${lead.id}`;
      notifs.push({
        id,
        group: 'recent',
        title: `Cập nhật: ${lead.name}`,
        description: `Pipeline ${lead.stage.replace(/_/g, ' ')} — ${lead.assigned_user_name || 'Chưa giao'}`,
        icon: '🔵',
        href: '/leads',
        timestamp: lead.updated_at,
        read: readIds.has(id),
        type: 'new_assignment',
      });
    }
  }

  // Sort: action_required first, then by timestamp desc
  notifs.sort((a, b) => {
    if (a.group !== b.group) return a.group === 'action_required' ? -1 : 1;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  return notifs;
}

// ── Main component ───────────────────────────────────────────────────

interface NotificationCenterProps {
  leads: Lead[];
  projects: Project[];
  /** Called when unread count changes so the bell badge can update. */
  onCountChange?: (count: number) => void;
}

export function useNotificationCount(leads: Lead[], projects: Project[]): number {
  const readIds = useMemo(() => getReadIds(), []);
  const notifs = useMemo(() => generateNotifications(leads, projects, readIds), [leads, projects, readIds]);
  return notifs.filter(n => !n.read).length;
}

export default function NotificationCenter({ leads, projects, onCountChange }: NotificationCenterProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [readIds, setReadIdsState] = useState<Set<string>>(new Set());
  const panelRef = useRef<HTMLDivElement>(null);

  // Load read IDs on mount
  useEffect(() => {
    setReadIdsState(getReadIds());
  }, []);

  const notifications = useMemo(
    () => generateNotifications(leads, projects, readIds),
    [leads, projects, readIds],
  );

  const unreadCount = useMemo(
    () => notifications.filter(n => !n.read).length,
    [notifications],
  );

  // Propagate unread count
  useEffect(() => {
    storeUnreadCount(unreadCount);
    onCountChange?.(unreadCount);
  }, [unreadCount, onCountChange]);

  const markAllRead = useCallback(() => {
    const allIds = new Set(readIds);
    for (const n of notifications) allIds.add(n.id);
    setReadIdsState(allIds);
    setReadIds(allIds);
  }, [readIds, notifications]);

  const handleNavigate = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  // Close on escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const actionNotifs = notifications.filter(n => n.group === 'action_required');
  const recentNotifs = notifications.filter(n => n.group === 'recent');

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h`;
    const diffDay = Math.floor(diffHr / 24);
    return `${diffDay}d`;
  };

  // ── Bell Button ──────────────────────────────────────────────────
  const bellButton = (
    <button
      onClick={() => setOpen(true)}
      className="relative p-2 rounded-xl transition-all hover:bg-white/5"
      style={{ color: 'var(--text-tertiary)' }}
      aria-label={`Thông báo${unreadCount > 0 ? `, ${unreadCount} chưa đọc` : ''}`}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold text-white px-1"
          style={{ background: '#EF4444', boxShadow: '0 0 0 2px var(--surface-1)' }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  );

  // ── Notification Item ────────────────────────────────────────────
  const renderNotification = (n: Notification) => (
    <button
      key={n.id}
      onClick={() => handleNavigate(n.href)}
      className="w-full flex items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
      style={{ borderBottom: '1px solid var(--border-subtle)' }}
    >
      <span className="text-lg flex-shrink-0 mt-0.5">{n.icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)] truncate">{n.title}</p>
        <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">{n.description}</p>
      </div>
      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        <span className="text-[10px] text-[var(--text-disabled)]">{formatTime(n.timestamp)}</span>
        {!n.read && (
          <span className="w-2 h-2 rounded-full" style={{ background: '#EF4444' }} />
        )}
      </div>
    </button>
  );

  const notifGroups = [
    { key: 'action_required', label: 'Cần xử lý', items: actionNotifs },
    { key: 'recent', label: 'Gần đây', items: recentNotifs },
  ].filter(g => g.items.length > 0);

  return (
    <>
      {/* Bell button — rendered inline */}
      {bellButton}

      {/* ── Mobile: Bottom Sheet ── */}
      {open && (
        <div className="fixed inset-0 z-[100] lg:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            ref={panelRef}
            className="absolute bottom-0 left-0 right-0 max-h-[85vh] rounded-t-2xl overflow-hidden animate-slideUp"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            {renderMobilePanel()}
          </div>
        </div>
      )}

      {/* ── Desktop: Slide-in Panel ── */}
      {open && (
        <div className="fixed inset-0 z-[100] hidden lg:block" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div
            ref={panelRef}
            className="absolute top-0 right-0 bottom-0 w-[400px] flex flex-col animate-slideRight"
            style={{ background: 'var(--surface-1)', borderLeft: '1px solid var(--border-default)', boxShadow: '-8px 0 32px rgba(0,0,0,0.3)' }}
            onClick={e => e.stopPropagation()}
          >
            {renderDesktopPanel()}
          </div>
        </div>
      )}

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        @keyframes slideRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        .animate-slideUp { animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
        .animate-slideRight { animation: slideRight 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
      `}</style>
    </>
  );

  function renderHeader() {
    return (
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Thong bao</h3>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-[11px] px-2.5 py-1 rounded-lg font-medium transition-colors"
              style={{ color: 'var(--gold-400)', background: 'rgba(201,169,110,0.08)' }}
            >
              Danh dau da doc
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
            style={{ color: 'var(--text-tertiary)' }}
            aria-label="Dong"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    );
  }

  function renderNotificationList() {
    if (notifGroups.length === 0) {
      return (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            <span className="text-3xl block mb-2">🔔</span>
            <p className="text-sm text-[var(--text-muted)]">Khong co thong bao nao</p>
          </div>
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto">
        {notifGroups.map(group => (
          <div key={group.key}>
            <p className="px-4 pt-3 pb-1 text-[10px] text-[var(--text-disabled)] uppercase tracking-wider font-semibold">
              {group.label} ({group.items.length})
            </p>
            {group.items.map(renderNotification)}
          </div>
        ))}
      </div>
    );
  }

  function renderFooter() {
    return (
      <div className="px-4 py-2.5 border-t flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
        <span className="text-[10px] text-[var(--text-disabled)]">
          {notifications.length} tong cong · {unreadCount} chua doc
        </span>
        <span className="text-[10px] text-[var(--text-disabled)]">
          Tu dong tao tu du lieu he thong
        </span>
      </div>
    );
  }

  function renderDesktopPanel() {
    return (
      <>
        {renderHeader()}
        {renderNotificationList()}
        {renderFooter()}
      </>
    );
  }

  function renderMobilePanel() {
    return (
      <>
        {/* Drag handle */}
        <div className="flex justify-center py-2">
          <div className="w-10 h-1 rounded-full" style={{ background: 'var(--border-default)' }} />
        </div>
        {renderHeader()}
        {renderNotificationList()}
        {renderFooter()}
      </>
    );
  }
}
