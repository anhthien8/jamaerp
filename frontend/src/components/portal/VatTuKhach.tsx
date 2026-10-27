'use client';

/**
 * Khách tự xem vật tư đã chọn + giá bán và bấm «Đồng ý» (27/10/2026).
 * Không có giá vốn/NCC — backend chỉ trả giá bán. Không JWT, gọi /portal/{token}/...
 */

import { useCallback, useEffect, useState } from 'react';

type Dong = {
  id: string; phong: string; hang_muc: string | null; ten: string | null; thay_the: string | null; ly_do_doi: string | null;
  so_luong: number; don_vi: string; gia_ban: number | null; thanh_tien: number | null;
  trang_thai: string; cho_khach_duyet: boolean; khach_dong_y_luc: string | null;
};

const VANG = '#C9A96E';
const tien = (n: number) => n.toLocaleString('vi-VN') + ' đ';

export default function VatTuKhach({ api, token, projectId }: { api: string; token: string; projectId: string }) {
  const [ds, setDs] = useState<Dong[]>([]);
  const [dang, setDang] = useState('');
  const [loi, setLoi] = useState('');

  const tai = useCallback(() => {
    fetch(`${api}/portal/${token}/projects/${projectId}/vat-tu`)
      .then(r => (r.ok ? r.json() : [])).then(setDs).catch(() => {});
  }, [api, token, projectId]);
  useEffect(() => { tai(); }, [tai]);

  const dongY = async (d: Dong) => {
    setDang(d.id); setLoi('');
    try {
      const r = await fetch(`${api}/portal/${token}/vat-tu/${d.id}/dong-y`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      if (!r.ok) throw new Error();
      tai();
    } catch { setLoi('Chưa gửi được, anh/chị thử lại giúp em.'); } finally { setDang(''); }
  };

  if (!ds.length) return null;
  const cho = ds.filter(d => d.cho_khach_duyet).length;
  return (
    <div className="rounded-2xl p-4 mt-4" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Vật tư đã chọn</h3>
        {cho > 0 && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: VANG, color: '#000' }}>{cho} mục chờ anh/chị đồng ý</span>}
      </div>
      <div className="space-y-2">
        {ds.map(d => (
          <div key={d.id} className="rounded-xl p-3 text-sm" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between gap-2">
              <div className="min-w-0">
                <div className="text-white truncate">{d.ten || d.hang_muc || 'Vật tư'}</div>
                <div className="text-xs text-gray-400">{d.phong}{d.hang_muc ? ` · ${d.hang_muc}` : ''} · {d.so_luong} {d.don_vi}</div>
                {d.thay_the && <div className="text-xs mt-1" style={{ color: VANG }}>Đề xuất thay bằng: {d.thay_the}{d.ly_do_doi ? ` (${d.ly_do_doi})` : ''}</div>}
              </div>
              <div className="text-right shrink-0">
                {d.thanh_tien != null && <div className="text-white">{tien(d.thanh_tien)}</div>}
                {d.gia_ban != null && <div className="text-xs text-gray-400">{tien(d.gia_ban)}/{d.don_vi}</div>}
              </div>
            </div>
            {d.cho_khach_duyet ? (
              <button disabled={dang === d.id} onClick={() => dongY(d)}
                className="mt-2 w-full text-xs py-2 rounded-full font-medium disabled:opacity-50" style={{ background: VANG, color: '#000' }}>
                {dang === d.id ? 'Đang gửi…' : d.thay_the ? 'Đồng ý mẫu thay thế' : 'Đồng ý giá này'}
              </button>
            ) : d.khach_dong_y_luc && <div className="mt-1 text-xs text-emerald-400">Anh/chị đã đồng ý {new Date(d.khach_dong_y_luc + 'Z').toLocaleDateString('vi-VN')}</div>}
          </div>
        ))}
      </div>
      {loi && <p className="text-xs text-red-400 mt-2">{loi}</p>}
    </div>
  );
}
