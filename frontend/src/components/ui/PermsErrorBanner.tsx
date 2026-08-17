'use client';

import { useAuth } from '@/lib/auth';

/**
 * Banner «Không tải được quyền — thử lại» cho các trang gate theo quyền.
 * Hiện khi GET /users/permissions/me lỗi tạm (permsError) — lúc đó gate không
 * redirect (quyền đang hiện chỉ là bản cục bộ tạm, đá đi là đá oan); backend
 * vẫn tự chặn từng API nên không rò rỉ dữ liệu.
 */
export default function PermsErrorBanner({ className = '' }: { className?: string }) {
  const { permsError, retryPerms } = useAuth();
  if (!permsError) return null;
  return (
    <div
      className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl text-sm ${className}`}
      style={{ background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid rgba(251,191,36,0.25)' }}
    >
      <span>⚠️ Không tải được quyền từ máy chủ — trang đang chạy với quyền tạm, một số mục có thể thiếu.</span>
      <button
        onClick={retryPerms}
        className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
        style={{ background: 'rgba(251,191,36,0.15)', color: 'var(--warning)' }}
      >
        Thử lại
      </button>
    </div>
  );
}
