'use client';

// Ngày NCC hẹn giao khi đặt hàng (22/11/2026) — bắt buộc, để đo NCC giao trễ. Chọn bằng một chạm;
// KHÔNG chọn sẵn ngày nào: người đặt phải hỏi NCC rồi mới bấm. Ngày tính theo giờ Việt Nam
// (server so với vn_today, hôm nay vẫn hợp lệ).

import { useState } from 'react';
import { ngayVN } from '@/lib/du-lieu-chung';
import { btn, inp } from './chung';

const NHANH = [{ n: 1, nhan: 'Mai' }, { n: 3, nhan: '3 ngày' }, { n: 7, nhan: '1 tuần' }, { n: 14, nhan: '2 tuần' }];

/** 'YYYY-MM-DD' → 'dd/MM' — cắt chuỗi, không qua Date để khỏi lệch ngày theo múi giờ máy. */
export const ngayNgan = (s?: string | null) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');

/** `value` là 'YYYY-MM-DD' hoặc '' (chưa chọn / ngày không hợp lệ). Nút đặt hàng của nơi gọi phải khoá khi value rỗng. */
export default function ChonNgayHen({ value, onChange, disabled }: { value: string; onChange: (ngay: string) => void; disabled?: boolean }) {
  const [tuChon, setTuChon] = useState(false);
  const [tay, setTay] = useState(''); // ngày đang chọn ở ô «Chọn ngày» — chỉ báo lên nơi gọi khi không trước hôm nay
  // Mốc ngày chốt một lần lúc mở khung (Date.now() không được gọi lúc render): [hôm nay, mai, +3, +7, +14]
  const [moc] = useState(() => [0, ...NHANH.map(x => x.n)].map(n => ngayVN(new Date(Date.now() + n * 86_400_000))));
  const kieu = (bat: boolean) => `${btn} text-xs ${bat ? 'bg-[var(--surface-3)] text-[var(--text-primary)] border-[var(--gold-400)]' : 'text-[var(--text-secondary)] border-[var(--border-subtle)]'}`;
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-[var(--text-muted)]">NCC hẹn giao</span>
        {NHANH.map((x, i) => (
          <button key={x.n} type="button" disabled={disabled} className={kieu(!tuChon && value === moc[i + 1])}
            onClick={() => { setTuChon(false); onChange(moc[i + 1]); }}>{x.nhan}</button>
        ))}
        <button type="button" disabled={disabled} className={kieu(tuChon)}
          onClick={() => { if (!tuChon) { setTuChon(true); setTay(''); onChange(''); } }}>Chọn ngày</button>
        {value && <span className="text-xs text-emerald-400">Hẹn giao {ngayNgan(value)}</span>}
      </div>
      {tuChon && (
        // iOS Safari không chặn ngày nhỏ hơn `min` trong bảng chọn → tự so chuỗi YYYY-MM-DD với hôm nay
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" className={`${inp} w-auto`} aria-label="Ngày NCC hẹn giao" min={moc[0]} value={tay} disabled={disabled}
            onChange={e => { const v = e.target.value; setTay(v); onChange(v >= moc[0] ? v : ''); }} />
          {tay && tay < moc[0] && <span className="text-xs text-amber-300">Ngày hẹn giao không được trước hôm nay</span>}
        </div>
      )}
    </div>
  );
}
