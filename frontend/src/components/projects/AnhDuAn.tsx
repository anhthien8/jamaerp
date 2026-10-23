'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, MediaFile, mediaUrl } from '@/lib/api';
import { nenAnh } from '@/lib/anh';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';

const NHAN_LOAI: Record<string, string> = {
  tien_do: 'Tiến độ', su_co: 'Sự cố', vat_tu: 'Vật tư', cham_cong: 'Chấm công', khac: 'Khác',
};

/**
 * Khối «Ảnh dự án» trong chi tiết dự án (23/10/2026). Ảnh nằm ở Kho ảnh
 * (nhóm Telegram «JAMA Công trình», mỗi dự án 1 topic). Công tắc «Khách thấy»
 * quyết định ảnh có lên trang tiến độ của khách (/portal) hay không.
 */
export default function AnhDuAn({ projectId }: { projectId: string }) {
  const { toast } = useToast();
  const [items, setItems] = useState<MediaFile[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState('');
  const [xem, setXem] = useState<MediaFile | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const res = await api.listMedia(projectId, p);
      setItems(prev => (p === 1 ? res.items : [...prev, ...res.items]));
      setTotal(res.total);
      setPage(p);
    } catch {
      // Chế độ Tập luyện / chưa có quyền: khối ảnh trống, không chặn chi tiết dự án
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(1); }, [load]);

  const upload = async (files: File[]) => {
    let ok = 0;
    for (let i = 0; i < files.length; i++) {
      setUploading(`${i + 1}/${files.length}`);
      try {
        const blob = await nenAnh(files[i]);
        if (!blob) { toast(`${files[i].name}: không đọc được ảnh`, 'error'); continue; }
        const m = await api.uploadMedia(blob, { projectId, kind: 'tien_do' });
        if (!m.deduped) ok++;
      } catch (e) {
        toast(e instanceof Error ? e.message : 'Tải ảnh thất bại', 'error');
        break;
      }
    }
    setUploading('');
    if (ok > 0) toast(`Đã lưu ${ok} ảnh vào Kho ảnh`, 'success');
    load(1);
  };

  const doiChiaSe = async (m: MediaFile) => {
    try {
      const u = await api.patchMedia(m.id, { shared_with_customer: !m.shared_with_customer });
      setItems(prev => prev.map(x => (x.id === m.id ? { ...x, ...u } : x)));
      if (xem?.id === m.id) setXem({ ...m, ...u });
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không đổi được', 'error');
    }
  };

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
          <LineIcon name="camera" size={16} className="inline-block align-[-2px] mr-1.5" />Ảnh dự án {total > 0 && <span className="normal-case">({total})</span>}
        </h3>
        <input
          ref={fileRef} type="file" accept="image/*" multiple className="hidden"
          onChange={e => { const f = Array.from(e.target.files || []); e.target.value = ''; if (f.length) upload(f); }}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={!!uploading}
          className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white hover:bg-white/10 disabled:opacity-50"
        >
          {uploading ? `Đang tải ${uploading}…` : '＋ Thêm ảnh'}
        </button>
      </div>

      {loading && items.length === 0 ? (
        <p className="text-xs text-[var(--text-disabled)]">Đang tải…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">
          Chưa có ảnh. Chụp ở công trình rồi bấm «Thêm ảnh», hoặc thả ảnh vào topic dự án trong nhóm Telegram «JAMA Công trình».
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {items.map(m => (
              <div key={m.id} className="relative group">
                <button type="button" onClick={() => setXem(m)} className="block w-full aspect-square rounded-lg overflow-hidden border border-white/10">
                  <img src={mediaUrl(m.url)} alt={m.caption || 'Ảnh công trình'} loading="lazy" className="w-full h-full object-cover" />
                </button>
                <button
                  type="button"
                  onClick={() => doiChiaSe(m)}
                  title={m.shared_with_customer ? 'Khách đang thấy ảnh này — bấm để ẩn' : 'Khách chưa thấy — bấm để chia sẻ'}
                  className={`absolute bottom-1 left-1 text-[10px] px-1.5 py-0.5 rounded ${m.shared_with_customer ? 'bg-emerald-500/90 text-black' : 'bg-black/70 text-white/70'}`}
                >
                  <LineIcon name={m.shared_with_customer ? 'eye' : 'lock'} size={10} color="currentColor" className="inline-block align-[-1px] mr-0.5" />{m.shared_with_customer ? 'Khách thấy' : 'Nội bộ'}
                </button>
                {m.kind !== 'tien_do' && (
                  <span className="absolute top-1 left-1 text-[9px] px-1 rounded bg-black/70 text-amber-300">{NHAN_LOAI[m.kind] || m.kind}</span>
                )}
              </div>
            ))}
          </div>
          {items.length < total && (
            <button type="button" onClick={() => load(page + 1)} disabled={loading} className="mt-3 text-xs text-[var(--gold-400)] hover:underline">
              {loading ? 'Đang tải…' : `Xem thêm (${total - items.length})`}
            </button>
          )}
        </>
      )}

      {xem && (
        <div className="fixed inset-0 z-[60] bg-black/90 flex flex-col items-center justify-center p-4" onClick={() => setXem(null)}>
          <img src={mediaUrl(xem.url)} alt={xem.caption || 'Ảnh công trình'} className="max-h-[80vh] max-w-full object-contain rounded" />
          <div className="mt-3 text-center text-xs text-white/80 space-y-1" onClick={e => e.stopPropagation()}>
            {xem.caption && <p>{xem.caption}</p>}
            <p>{xem.user_name || 'Nhân viên'} · {xem.created_at ? new Date(xem.created_at + (xem.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : ''}</p>
            <button type="button" onClick={() => doiChiaSe(xem)} className="px-3 py-1 rounded bg-white/10 hover:bg-white/20">
              <LineIcon name={xem.shared_with_customer ? 'eye' : 'lock'} size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />{xem.shared_with_customer ? 'Khách thấy — bấm để ẩn' : 'Nội bộ — bấm để khách thấy'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
