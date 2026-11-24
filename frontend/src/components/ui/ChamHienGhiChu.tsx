'use client';

/**
 * Ghi chú `title=` hiện được trên màn hình cảm ứng (24/11/2026).
 *
 * App còn ~80 chỗ giải thích bằng thuộc tính `title` — chỉ hiện khi rê chuột, nên trên điện thoại / tablet coi như
 * không có. Thay vì sửa từng chỗ, một bộ nghe chung: CHẠM vào phần tử có `title` (không phải nút, link, ô nhập — chạm
 * những thứ đó là để thao tác) thì hiện bong bóng ghi chú ngay dưới ngón tay trong vài giây. Chuột thì giữ cách cũ.
 */

import { useEffect, useState } from 'react';

export default function ChamHienGhiChu() {
  const [tip, setTip] = useState<{ text: string; x: number; y: number; tren: boolean } | null>(null);

  useEffect(() => {
    let hen: ReturnType<typeof setTimeout> | undefined;
    const onUp = (e: PointerEvent) => {
      if (e.pointerType === 'mouse') return;
      const dich = e.target instanceof Element ? e.target : null;
      const el = dich?.closest<HTMLElement>('[title]');
      const thaoTac = dich?.closest('button, a, input, select, textarea, label, [role="button"]');
      // Phần tử có title nằm TRONG một nút (hoặc chính nó là nút) → để yên cho thao tác.
      if (!el || !el.title.trim() || (thaoTac && (thaoTac === el || thaoTac.contains(el) || el.contains(thaoTac)))) { setTip(null); return; }
      const r = el.getBoundingClientRect();
      const tren = r.top > 110;
      setTip({ text: el.title, x: Math.min(Math.max(r.left + r.width / 2, 130), window.innerWidth - 130), y: tren ? r.top - 6 : r.bottom + 6, tren });
      clearTimeout(hen);
      hen = setTimeout(() => setTip(null), 4500);
    };
    const an = () => setTip(null);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('scroll', an, true);
    return () => { window.removeEventListener('pointerup', onUp); window.removeEventListener('scroll', an, true); clearTimeout(hen); };
  }, []);

  if (!tip) return null;
  return (
    <div role="tooltip" className="fixed z-[9998] w-max max-w-[250px] px-3 py-2 rounded-xl text-xs leading-snug shadow-xl pointer-events-none"
      style={{
        left: tip.x, top: tip.y, transform: `translate(-50%, ${tip.tren ? '-100%' : '0'})`,
        background: 'var(--surface-3)', border: '1px solid var(--border-default)', color: 'var(--text-primary)',
      }}>
      {tip.text}
    </div>
  );
}
