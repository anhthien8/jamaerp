/**
 * Tô sáng tài khoản đang đăng nhập trong danh sách / sơ đồ nhân sự (24/10/2026):
 * nền vàng nhạt + nhãn «Bạn» để tự tìm thấy mình giữa nhiều người.
 */

export const NEN_CUA_TOI = 'color-mix(in srgb, var(--gold-500) 12%, var(--surface-2))';

export function BadgeBan() {
  return (
    <span
      className="ml-1.5 px-1.5 py-px rounded-full text-[10px] font-bold align-middle"
      style={{ background: 'var(--gold-500)', color: '#000' }}
    >
      Bạn
    </span>
  );
}
