'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import LineIcon from './LineIcon';

/**
 * Ghi chú hướng dẫn dùng chung toàn app: icon «i» nhỏ, rê chuột (máy tính) hoặc chạm
 * (điện thoại/tablet) để hiện giải thích ngắn.
 *
 * - Không truyền children → vẽ icon «i».
 * - Truyền children → bọc phần tử đó (vd nút), rê lên nút là hiện ghi chú.
 *
 * Bong bóng vẽ qua portal + position fixed → không bị khung modal cuộn (overflow) cắt mất.
 */
export default function InfoTip({ text, children, size = 13, className = '' }: {
  text: ReactNode;
  children?: ReactNode;
  size?: number;
  className?: string;
}) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);

  const show = useCallback(() => {
    const r = triggerRef.current?.getBoundingClientRect();
    if (!r) return;
    const above = r.top > 120; // đủ chỗ phía trên thì hiện trên, không thì hiện dưới
    setPos({ x: r.left + r.width / 2, y: above ? r.top - 6 : r.bottom + 6, above });
  }, []);
  const hide = useCallback(() => setPos(null), []);

  // Cuộn/đổi cỡ màn hình → toạ độ cũ sai, đóng luôn cho gọn.
  useEffect(() => {
    if (!pos) return;
    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
    return () => {
      window.removeEventListener('scroll', hide, true);
      window.removeEventListener('resize', hide);
    };
  }, [pos, hide]);

  const bubble = pos && typeof document !== 'undefined' && createPortal(
    <div
      role="tooltip"
      className="fixed z-[9999] max-w-[260px] px-3 py-2 rounded-lg text-xs leading-relaxed pointer-events-none shadow-lg"
      style={{
        left: Math.min(Math.max(pos.x, 140), window.innerWidth - 140),
        top: pos.y,
        transform: `translate(-50%, ${pos.above ? '-100%' : '0'})`,
        background: 'var(--surface-3, #1f2937)',
        color: 'var(--text-primary, #fff)',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
      }}
    >
      {text}
    </div>,
    document.body,
  );

  const handlers = {
    onMouseEnter: show,
    onMouseLeave: hide,
    onFocus: show,
    onBlur: hide,
  };

  if (children) {
    // Bọc nút: bấm là chạy việc của nút → cất ghi chú ngay, kẻo trên cảm ứng nó nằm lại đè lên
    // màn kế tiếp. Người dùng điện thoại đọc ghi chú qua icon «i» (bản không children).
    return (
      <span ref={triggerRef} className={`inline-flex ${className}`} {...handlers} onClick={hide}>
        {children}
        {bubble}
      </span>
    );
  }

  return (
    <span
      ref={triggerRef}
      role="button"
      tabIndex={0}
      aria-label="Xem ghi chú"
      className={`inline-flex items-center justify-center cursor-help align-middle opacity-60 hover:opacity-100 focus:opacity-100 outline-none ${className}`}
      onClick={e => { e.stopPropagation(); if (pos) hide(); else show(); }}
      {...handlers}
    >
      <LineIcon name="info" size={size} color="currentColor" />
      {bubble}
    </span>
  );
}
