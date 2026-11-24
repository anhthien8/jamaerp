'use client';

/**
 * Nút «+» tạo nhanh trên điện thoại (24/11/2026) — góc trái trên thanh nút đáy, đối xứng với nút Trợ lý ở góc phải.
 * Một chạm mở danh sách việc hay tạo nhất theo quyền của người dùng:
 *  • «Lead mới» mở form ngay tại chỗ, không rời trang đang đứng.
 *  • «Dự án mới», «Giao dịch mới» sang trang đích với `?new=1` để form mở sẵn. Đang đứng ở chính trang đó thì ẩn mục
 *    này — trang đã có nút tạo của riêng nó.
 * Trước đó muốn tạo lead khi đang ở trang khác phải: menu → Quy trình → «Tạo lead».
 */

import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { canAssignLeads, type RolePermissions } from '@/lib/roles';
import LineIcon from '@/components/ui/LineIcon';
import CreateLeadModal from '@/components/ui/CreateLeadModal';

export default function TaoNhanh({ perms, user }: { perms: RolePermissions; user: { role?: string; department?: string } | null }) {
  const [mo, setMo] = useState(false);
  const [taoLead, setTaoLead] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const ghiSo = user?.role === 'admin' || user?.role === 'accountant'; // khớp cổng «+ Giao dịch mới» ở trang Kế toán
  const ds: { nhan: string; icon: string; lam: () => void }[] = [
    ...(perms.canViewLeads ? [
      { nhan: 'Lead mới', icon: 'user', lam: () => setTaoLead(true) },
      ...(pathname.startsWith('/quote-tool') ? [] : [{ nhan: 'Báo giá nhanh', icon: 'zap', lam: () => router.push('/quote-tool') }]),
    ] : []),
    ...(perms.canCreateProjects && !pathname.startsWith('/projects') ? [{ nhan: 'Dự án mới', icon: 'building', lam: () => router.push('/projects?new=1') }] : []),
    ...(ghiSo && !pathname.startsWith('/accounting') ? [{ nhan: 'Giao dịch mới', icon: 'wallet', lam: () => router.push('/accounting?tab=transactions&new=1') }] : []),
  ];
  if (ds.length === 0) return null;

  return (
    <>
      {mo && <div className="fixed inset-0 z-[45] lg:hidden" style={{ background: 'rgba(0,0,0,0.45)' }} onClick={() => setMo(false)} />}
      <div className="fixed left-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-[46] lg:hidden flex flex-col-reverse items-start gap-2">
        <button type="button" aria-label={mo ? 'Đóng tạo nhanh' : 'Tạo nhanh'} aria-expanded={mo} onClick={() => setMo(v => !v)}
          className="w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-transform active:scale-95"
          style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}>
          <LineIcon name={mo ? 'x' : 'plus'} size={22} color="currentColor" />
        </button>
        {mo && ds.map(a => (
          <button key={a.nhan} type="button" onClick={() => { setMo(false); a.lam(); }}
            className="min-h-[44px] pl-3 pr-4 rounded-full flex items-center gap-2 text-sm font-semibold shadow-lg"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
            <LineIcon name={a.icon} size={16} color="var(--gold-400)" />{a.nhan}
          </button>
        ))}
      </div>
      {taoLead && <CreateLeadModal isOpen onClose={() => setTaoLead(false)} canAssign={canAssignLeads(user)} />}
    </>
  );
}
