'use client';

/**
 * Điểm JAMA trong Hồ sơ 360° (23/10/2026) — chính chủ (khi Chế độ thưởng bật «Nhân viên tự xem
 * điểm») hoặc Admin/Kế toán. Số do backend tính (/che-do-thuong/nguoi/{id}); {hien:false} → ẩn.
 */

import { useEffect, useState } from 'react';
import { api, CdtDong } from '@/lib/api';
import { tien } from '@/lib/tien-gon';

const VANG = '#C9A96E';
const THANH_PHAN: [string, string][] = [['doanh_so', 'Doanh số'], ['chuyen_can', 'Chuyên cần'], ['phan_hoi', 'Phản hồi'], ['danh_gia', 'Đánh giá']];

type Diem = { hien: true; ky: string; quy: string } & CdtDong;

export default function DiemJama({ userId }: { userId: string }) {
  const [d, setD] = useState<Diem | null>(null);

  useEffect(() => {
    let huy = false;
    api.cdtNguoi(userId)
      .then(r => { if (!huy) setD(r.hien ? r : null); })
      .catch(() => { if (!huy) setD(null); });
    return () => { huy = true; };
  }, [userId]);

  if (!d) return null;
  const diem = d.diem;
  const mau = diem == null ? 'var(--text-muted)' : diem >= 90 ? VANG : diem >= 70 ? 'var(--success)' : diem >= 50 ? 'var(--warning)' : 'var(--danger)';

  return (
    <div className="glass-card rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Điểm JAMA · T{Number(d.ky.slice(5))}/{d.ky.slice(0, 4)}</p>
          <p className="font-mono font-bold text-3xl leading-tight" style={{ color: mau }}>{diem == null ? '—' : diem}</p>
          <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{diem == null ? 'Chưa đủ số liệu' : `Hệ số thưởng ×${d.he_so}`}</p>
        </div>
        <div className="text-right">
          <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Thưởng dự kiến kỳ này</p>
          <p className="font-mono font-bold text-lg" style={{ color: VANG }}>{tien(d.tong)}</p>
          {d.du_kien_cuoi_quy > 0 && <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>+{tien(d.du_kien_cuoi_quy)} chi cuối quý</p>}
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
        {THANH_PHAN.map(([ma, nhan]) => {
          const v = d.thanh_phan[ma];
          return (
            <div key={ma} className="rounded-lg p-2" style={{ background: 'var(--surface-2)' }}>
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{nhan}</p>
              <p className="font-mono text-sm">{v == null ? '—' : v}</p>
              <div className="h-1 rounded-full mt-1" style={{ background: 'rgba(255,255,255,.08)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, v ?? 0))}%`, background: VANG }} />
              </div>
            </div>
          );
        })}
      </div>
      {d.khoan.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {d.khoan.map((k, i) => (
            <li key={i} className="flex justify-between gap-3">
              <span style={{ color: 'var(--text-secondary)' }}>{k.nhan}{!k.chi_ky_nay && ' (chi cuối quý)'}</span>
              <span className="font-mono">{tien(k.so_tien)}</span>
            </li>
          ))}
        </ul>
      )}
      {d.ghi_chu.map((g, i) => <p key={i} className="text-[11px] mt-1" style={{ color: 'var(--warning)' }}>{g}</p>)}
      <p className="text-[10px] mt-2" style={{ color: 'var(--text-muted)' }}>Số dự kiến — chốt cuối kỳ, Kế toán duyệt rồi mới vào lương.</p>
    </div>
  );
}
