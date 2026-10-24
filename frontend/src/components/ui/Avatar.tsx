'use client';

import { useState } from 'react';
import { api, mediaUrl } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';

/**
 * Ảnh đại diện nhân viên — có ảnh thì hiện ảnh (phủ kín khung), chưa có hoặc
 * ảnh lỗi thì hiện chữ cái đầu của TÊN (phần cuối họ tên, kiểu Việt).
 * Kích thước/bo góc/nền chữ do nơi gọi truyền qua className + style.
 */
export default function Avatar({
  name,
  url,
  className = 'w-9 h-9 rounded-xl text-sm',
  style,
  fallback = '?',
}: {
  name?: string | null;
  url?: string | null;
  className?: string;
  style?: React.CSSProperties;
  fallback?: string;
}) {
  const [loi, setLoi] = useState<string | null>(null);
  const src = url ? mediaUrl(url) : '';
  const coAnh = !!src && loi !== src;
  const chu = name?.trim().split(/\s+/).pop()?.charAt(0).toUpperCase() || fallback;
  return (
    <div
      className={`${className} relative overflow-hidden flex items-center justify-center font-bold flex-shrink-0 select-none`}
      style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))', color: 'white', ...style }}
    >
      {coAnh ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={name || 'Ảnh đại diện'}
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
          decoding="async"
          onError={() => setLoi(src)}
        />
      ) : chu}
    </div>
  );
}

/** Ảnh chọn từ máy → JPG vuông ≤480px (cắt giữa) dạng data-URL, nhẹ để gửi lên. */
export async function nenAnhDaiDien(file: File): Promise<string | null> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return null;
  const canh = Math.min(bitmap.width, bitmap.height);
  const dich = Math.min(480, canh);
  const canvas = document.createElement('canvas');
  canvas.width = dich;
  canvas.height = dich;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.fillStyle = '#ffffff'; // PNG trong suốt → nền trắng thay vì đen
  ctx.fillRect(0, 0, dich, dich);
  ctx.drawImage(bitmap, (bitmap.width - canh) / 2, (bitmap.height - canh) / 2, canh, canh, 0, 0, dich, dich);
  return canvas.toDataURL('image/jpeg', 0.85);
}

/**
 * Ảnh đại diện + nút máy ảnh để đổi ảnh. Backend cho phép chính chủ hoặc
 * admin/kế toán — nơi gọi chỉ render khi người xem có quyền.
 */
export function DoiAnhDaiDien({
  userId,
  name,
  url,
  onDoi,
  className = 'w-16 h-16 rounded-full text-2xl',
  style,
  choGo = false,
}: {
  userId: string;
  name?: string | null;
  url?: string | null;
  onDoi: (url: string | null) => void;
  className?: string;
  style?: React.CSSProperties;
  /** Hiện nút «Gỡ ảnh» bên dưới khi đang có ảnh */
  choGo?: boolean;
}) {
  const [dangTai, setDangTai] = useState(false);
  const [loi, setLoi] = useState('');

  const chon = async (file?: File | null) => {
    if (!file) return;
    setLoi('');
    setDangTai(true);
    try {
      const data = await nenAnhDaiDien(file);
      if (!data) throw new Error('Không đọc được ảnh — chọn ảnh JPG/PNG khác');
      const res = await api.uploadAvatar(userId, data);
      onDoi(res.avatar_url);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Đổi ảnh thất bại');
    } finally {
      setDangTai(false);
    }
  };

  const go = async () => {
    if (!confirm('Gỡ ảnh đại diện?')) return;
    setDangTai(true);
    try {
      await api.deleteAvatar(userId);
      onDoi(null);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Gỡ ảnh thất bại');
    } finally {
      setDangTai(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-1 flex-shrink-0">
      <label className="relative cursor-pointer group" title="Đổi ảnh đại diện" aria-label="Đổi ảnh đại diện">
        <Avatar name={name} url={url} className={className} style={style} />
        <span
          className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center shadow"
          style={{ background: 'var(--gold-500)', color: '#111', border: '2px solid var(--surface-1, #fff)' }}
        >
          {dangTai ? (
            <span className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
          ) : (
            <LineIcon name="camera" size={14} color="currentColor" />
          )}
        </span>
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          disabled={dangTai}
          onChange={(e) => { void chon(e.target.files?.[0]); e.target.value = ''; }}
        />
      </label>
      {choGo && url && !dangTai && (
        <button type="button" onClick={() => void go()} className="text-[11px] underline" style={{ color: 'var(--text-muted)' }}>
          Gỡ ảnh
        </button>
      )}
      {loi && <p className="text-[11px] max-w-[160px] text-center" style={{ color: 'var(--danger, #F87171)' }}>{loi}</p>}
    </div>
  );
}
