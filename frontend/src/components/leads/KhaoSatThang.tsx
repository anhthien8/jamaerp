'use client';

/** Khảo sát trong tháng theo NVKD (10/11/2026) — giám sát số khách đã khảo sát
 *  và bao nhiêu đã ký HĐ thiết kế. Backend tự cắt theo phạm vi xem lead. */
import { useEffect, useState } from 'react';
import { api, type ThongKeKhaoSat } from '@/lib/api';

function thangNay(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export default function KhaoSatThang() {
  const [thang, setThang] = useState(thangNay);
  const [data, setData] = useState<ThongKeKhaoSat | null>(null);
  const [loi, setLoi] = useState(false);

  useEffect(() => {
    let huy = false;
    api.getThongKeKhaoSat(thang)
      .then(d => { if (!huy) { setData(d); setLoi(false); } })
      .catch(() => { if (!huy) setLoi(true); });
    return () => { huy = true; };
  }, [thang]);

  return (
    <div className="glass-card p-4 mb-3">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Khảo sát theo tháng</h3>
        <input
          type="month"
          value={thang}
          onChange={e => e.target.value && setThang(e.target.value)}
          aria-label="Chọn tháng khảo sát"
          className="text-sm px-2 py-1 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
        />
        {data && (
          <span className="text-xs text-[var(--text-muted)] ml-auto">
            {data.tong} khách khảo sát · {data.da_ky} đã ký HĐ thiết kế · chuyển đổi {data.ty_le}%
          </span>
        )}
      </div>
      {loi ? (
        <p className="text-xs text-[var(--text-muted)]">Không tải được thống kê khảo sát</p>
      ) : !data ? (
        <p className="text-xs text-[var(--text-muted)]">Đang tải...</p>
      ) : data.theo_nguoi.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">Chưa có khách nào được ghi ngày khảo sát trong tháng này</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[var(--text-muted)] text-left">
                <th className="py-1.5 pr-3 font-medium">Nhân viên kinh doanh</th>
                <th className="py-1.5 px-3 font-medium text-right">Đã khảo sát</th>
                <th className="py-1.5 px-3 font-medium text-right">Đã ký HĐ</th>
                <th className="py-1.5 pl-3 font-medium text-right">Tỷ lệ</th>
              </tr>
            </thead>
            <tbody>
              {data.theo_nguoi.map(r => (
                <tr key={r.user_id ?? 'none'} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <td className="py-1.5 pr-3 text-[var(--text-primary)]">{r.ten}</td>
                  <td className="py-1.5 px-3 text-right tabular-nums">{r.khao_sat}</td>
                  <td className="py-1.5 px-3 text-right tabular-nums">{r.da_ky}</td>
                  <td className="py-1.5 pl-3 text-right tabular-nums text-[var(--gold-400)]">{r.ty_le}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
