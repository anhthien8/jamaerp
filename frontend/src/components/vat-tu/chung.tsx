'use client';

// Kiểu nút/ô nhập và mấy mảnh nhỏ dùng chung của màn Vật tư (trang /vat-tu + các khối tách file).

import { useEffect, useState } from 'react';
import { api, mediaUrl } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';

export const inp = 'w-full rounded-xl px-3 py-2 text-base sm:text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--gold-400)]';
export const btn = 'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium border transition-colors disabled:opacity-50';
export const btnGold = `${btn} bg-[var(--gold-400)] text-black border-transparent hover:opacity-90`;
export const btnGhost = `${btn} bg-transparent text-[var(--text-secondary)] border-[var(--border-default)] hover:text-[var(--text-primary)]`;
export const loi = (e: unknown, mac: string) => (e instanceof Error && e.message ? e.message : mac);
// Tiền viết đủ số: tin gửi ra ngoài và bảng giá (tien() làm tròn kiểu 1,2tr — chỉ hợp xem nhanh trong app)
export const tienDu = (v: number) => `${Math.round(v).toLocaleString('vi-VN')}đ`;
export type Bao = (loai: 'ok' | 'loi', text: string) => void;

// Hạng NCC (Supplier.hang) — null = chưa xếp
export const NHAN_HANG_NCC: Record<string, string> = { chinh: 'Chính', du_phong: 'Dự phòng', thu: 'Đang thử' };

export function AnhMau({ url, size = 40 }: { url?: string | null; size?: number }) {
  const src = url ? mediaUrl(url) : '';
  if (!src || !/^https?:/.test(src)) {
    return <div className="rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0" style={{ width: size, height: size }}><LineIcon name="package" size={16} /></div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" className="rounded-lg object-cover shrink-0" style={{ width: size, height: size }} loading="lazy" />;
}

// Gợi ý tên NCC có sẵn trong mục Nhà cung cấp (gõ tên mới thì tự tạo NCC khi lưu).
// Dùng: <NccGoiY /> rồi <input list="ds-ncc" />.
let nccCache: Promise<{ id: string; name: string }[]> | null = null;
export function NccGoiY() {
  const [ds, setDs] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => {
    nccCache ??= api.vatTuDsNcc().catch(() => { nccCache = null; return []; });
    nccCache.then(setDs);
  }, []);
  return <datalist id="ds-ncc">{ds.map(n => <option key={n.id} value={n.name} />)}</datalist>;
}
