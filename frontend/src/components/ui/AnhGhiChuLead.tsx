'use client';

/**
 * Ảnh đính kèm ghi chú lead (23/10/2026) — thay ô dán link Google Drive.
 * Ảnh nằm sau JWT (lead chỉ KD + BGĐ xem) nên <img src> không trỏ thẳng được:
 * fetch kèm token → blob URL, cache theo id cho cả phiên để mở lại modal không tải lại.
 */
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

const blobCache = new Map<string, Promise<string>>();

/** Dòng trong Activity.content trỏ tới ảnh: «🖼 anh:<id>» */
export const DONG_ANH = /^🖼 anh:([\w-]+)$/;

function layAnh(leadId: string, anhId: string): Promise<string> {
  let p = blobCache.get(anhId);
  if (!p) {
    p = api.getLeadImageUrl(leadId, anhId);
    p.catch(() => blobCache.delete(anhId)); // lỗi mạng → lần sau thử lại
    blobCache.set(anhId, p);
  }
  return p;
}

export function AnhLead({ leadId, anhId }: { leadId: string; anhId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loi, setLoi] = useState(false);
  const [phongTo, setPhongTo] = useState(false);

  useEffect(() => {
    let huy = false;
    layAnh(leadId, anhId).then(u => { if (!huy) setSrc(u); }).catch(() => { if (!huy) setLoi(true); });
    return () => { huy = true; };
  }, [leadId, anhId]);

  useEffect(() => {
    if (!phongTo) return;
    const dong = (e: KeyboardEvent) => { if (e.key === 'Escape') setPhongTo(false); };
    window.addEventListener('keydown', dong);
    return () => window.removeEventListener('keydown', dong);
  }, [phongTo]);

  if (loi) {
    return <div className="w-20 h-20 rounded-lg flex items-center justify-center text-[10px] text-[var(--text-muted)] bg-white/5 border border-white/10">Lỗi tải ảnh</div>;
  }
  return (
    <>
      <button
        type="button"
        onClick={() => src && setPhongTo(true)}
        className="w-20 h-20 rounded-lg overflow-hidden bg-white/5 border border-white/10 hover:border-[#C9A96E] transition-all"
        aria-label="Xem ảnh lớn"
      >
        {src
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={src} alt="Ảnh ghi chú" className="w-full h-full object-cover" loading="lazy" />
          : <span className="block w-full h-full animate-pulse" />}
      </button>
      {phongTo && src && (
        <div
          className="fixed inset-0 z-[100] bg-black/85 flex items-center justify-center p-4"
          onClick={() => setPhongTo(false)}
          role="dialog"
          aria-label="Ảnh ghi chú"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="Ảnh ghi chú" className="max-w-full max-h-full rounded-lg object-contain" />
          <button
            type="button"
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 text-white text-xl"
            aria-label="Đóng"
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}
