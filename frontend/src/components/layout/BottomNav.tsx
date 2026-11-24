'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { RolePermissions } from '@/lib/roles';
import LineIcon from '@/components/ui/LineIcon';

/**
 * Thanh điều hướng dưới cho mobile (sales/giám sát dùng điện thoại là chính).
 * Tối đa 5 mục — đưa thao tác hay dùng nhất vào tầm ngón cái. Chỉ hiện < lg (desktop đã có sidebar).
 *
 * 24/11/2026: xếp THEO VAI. Hai mục đầu ai cũng có (Tổng quan, Việc của tôi — đã gồm cả đơn chờ duyệt),
 * mục cuối là Chấm công, hai mục giữa là trang làm việc chính: `trangChinh` của vai đứng trước
 * (kế toán → Kế toán, ban quản trị → P&L, giám sát → Dự án…), rồi tới các trang còn lại theo quyền.
 * Trước đó thanh này cố định Quy trình / Dự án / Chấm công / Phê duyệt → kế toán không có lối tắt nào về việc của mình.
 */
const TRANG_CHINH: { href: string; label: string; icon: string; quyen: keyof RolePermissions }[] = [
  { href: '/leads', label: 'Quy trình', icon: 'kanban', quyen: 'canViewLeads' },
  { href: '/projects', label: 'Dự án', icon: 'building', quyen: 'canViewProjects' },
  { href: '/accounting', label: 'Kế toán', icon: 'wallet', quyen: 'canViewAccounting' },
  { href: '/pl', label: 'P&L', icon: 'chart', quyen: 'canViewPnL' },
];

export default function BottomNav({ perms, trangChinh }: { perms: RolePermissions; trangChinh?: string }) {
  // Nhận sẵn quyền HIỆU LỰC từ Sidebar (đã gồm quyền riêng của người này + chặn
  // cứng theo bộ phận) — trước đây tự tính lại từ role nên lệch với sidebar.
  const pathname = usePathname();

  const giua = TRANG_CHINH.filter(t => perms[t.quyen]).sort((a, b) => Number(b.href === trangChinh) - Number(a.href === trangChinh));
  const cuoi = perms.canViewAttendance ? [{ href: '/attendance', label: 'Chấm công', icon: 'clock' }] : [];
  const visible = [
    { href: '/', label: 'Tổng quan', icon: 'home' },
    { href: '/viec-cua-toi', label: 'Việc của tôi', icon: 'clipboard' },
    ...giua.slice(0, 3 - cuoi.length),
    ...cuoi,
  ];

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
            className="flex-1 min-w-0 flex flex-col items-center justify-center gap-0.5 py-2 min-h-[52px]"
            style={{ color: active ? 'var(--gold-400)' : 'var(--text-muted)' }}
            aria-current={active ? 'page' : undefined}
          >
            <LineIcon name={item.icon} size={20} color={active ? 'var(--gold-400)' : 'var(--text-muted)'} />
            <span className="text-[10px] font-medium leading-none truncate max-w-full px-0.5">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
