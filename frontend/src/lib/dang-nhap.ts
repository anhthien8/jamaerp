/**
 * Giữ trang đang mở qua bước đăng nhập (21/11/2026).
 *
 * Link trong tin nhắc (Telegram «Mở danh sách đối chiếu» → /doi-chieu?phong=OPS, «Hướng dẫn
 * 1 phút» → /cai-app, thông báo máy) hay mở ở trình duyệt CHƯA đăng nhập: trình duyệt trong
 * Telegram/Zalo, tab Safari mới, app vừa hết phiên. Token nằm trong localStorage của từng
 * trình duyệt nên ở đó chưa có phiên. Trước đây trang đá về `/login` trơn và đăng nhập xong
 * luôn về Tổng quan → trưởng phòng không tới được trang đối chiếu / hướng dẫn cài app.
 *
 * Nay: trang đá về `/login?next=<đường dẫn đang mở>`; đăng nhập xong đi tiếp tới `next`
 * (chỉ nhận đường dẫn nội bộ — xem diemDenSauDangNhap).
 */

/** Đường tới trang đăng nhập, kèm `next` = trang đang mở (bỏ qua khi đang ở «/» hoặc /login). */
export function duongDangNhap(hetHan = false): string {
  const p = new URLSearchParams();
  if (hetHan) p.set('het_han', '1');
  if (typeof window !== 'undefined') {
    const { pathname, search } = window.location;
    if (pathname !== '/' && !pathname.startsWith('/login')) p.set('next', pathname + search);
  }
  const q = p.toString();
  return q ? `/login?${q}` : '/login';
}

/**
 * Trang đi tới sau khi đăng nhập. Chỉ nhận đường dẫn nội bộ bắt đầu bằng «/» — chặn
 * «//web-la.com», «/\web-la.com» (trình duyệt hiểu như «//») và mọi địa chỉ khác nguồn,
 * để link `?next=` không thành lối chuyển hướng sang trang lạ. Không hợp lệ → «/».
 */
export function diemDenSauDangNhap(next: string | null | undefined): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/';
  if (typeof window === 'undefined') return '/';
  try {
    const u = new URL(next, window.location.origin);
    if (u.origin !== window.location.origin || u.pathname.startsWith('/login')) return '/';
    return u.pathname + u.search + u.hash;
  } catch {
    return '/';
  }
}
