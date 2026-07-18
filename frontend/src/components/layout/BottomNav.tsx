'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getPermissions, UserRole } from '@/lib/roles';
import LineIcon from '@/components/ui/LineIcon';

/**
 * Thanh điều hướng dưới cho mobile (sales/giám sát dùng điện thoại là chính).
 * Tối đa 5 mục theo quyền — đưa thao tác hay dùng nhất vào tầm ngón cái.
 * Chỉ hiện < lg (desktop đã có sidebar).
 */
export default function BottomNav({ role }: { role: string }) {
  const pathname = usePathname();
  const perms = getPermissions(role as UserRole);

  const items: { href: string; label: string; icon: string }[] = [
    { href: '/', label: 'Tổng quan', icon: 'home' },
  ];
  if (perms.canViewLeads) items.push({ href: '/leads', label: 'Quy trình', icon: 'kanban' });
  if (perms.canViewProjects) items.push({ href: '/projects', label: 'Dự án', icon: 'building' });
  if (perms.canViewAttendance) items.push({ href: '/attendance', label: 'Chấm công', icon: 'clock' });
  if (perms.canViewApprovals) items.push({ href: '/approvals', label: 'Phê duyệt', icon: 'check' });
  const visible = items.slice(0, 5);

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 lg:hidden flex items-stretch border-t"
      style={{
        background: 'var(--surface-1)',
        borderColor: 'var(--border-subtle)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      aria-label="Điều hướng nhanh"
    >
      {visible.map(item => {
        const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 min-h-[52px]"
            style={{ color: active ? 'var(--gold-400)' : 'var(--text-muted)' }}
            aria-current={active ? 'page' : undefined}
          >
            <LineIcon name={item.icon} size={20} color={active ? 'var(--gold-400)' : 'var(--text-muted)'} />
            <span className="text-[10px] font-medium leading-none">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
