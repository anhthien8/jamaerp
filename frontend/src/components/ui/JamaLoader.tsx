/** Màn chờ logo JAMA — dùng cho app/loading.tsx và lớp phủ khi bấm chuyển trang.
 *  Hiện trễ 150ms (class .jama-loader trong globals.css) để trang mở nhanh không nháy. */
export default function JamaLoader({ label = 'Đang mở trang…' }: { label?: string }) {
  return (
    <div className="jama-loader flex flex-col items-center justify-center gap-4 min-h-[60vh]" role="status" aria-live="polite">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/jama-logo.png" alt="JAMA HOME" className="jama-loader__logo h-12 w-auto" />
      <div className="jama-loader__vach" />
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
    </div>
  );
}
