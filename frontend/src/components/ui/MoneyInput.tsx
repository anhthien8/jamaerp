'use client';

/**
 * Ô nhập tiền đơn vị NGHÌN ĐỒNG cho các giá trị lớn (dự án/hợp đồng tiền tỷ):
 * gõ 2500000 = 2,5 tỷ — ngắn hơn 3 số 0, khó gõ nhầm. Giá trị lưu/emit vẫn là
 * ĐỒNG (string, khớp state form hiện có); component tự nhân/chia 1000.
 * Preview dưới ô hiện giá trị đầy đủ + dạng tắt (tỷ/triệu) để người nhập tự soát.
 */

function shortVN(dong: number): string {
  if (dong >= 1_000_000_000) {
    const ty = dong / 1_000_000_000;
    return `${(Math.round(ty * 100) / 100).toLocaleString('vi-VN')} tỷ`;
  }
  if (dong >= 1_000_000) {
    const tr = dong / 1_000_000;
    return `${(Math.round(tr * 10) / 10).toLocaleString('vi-VN')} triệu`;
  }
  return `${dong.toLocaleString('vi-VN')} đ`;
}

interface MoneyInputProps {
  /** Giá trị hiện tại tính bằng ĐỒNG (string như form đang lưu, '' = trống) */
  valueDong: string;
  /** Emit giá trị mới tính bằng ĐỒNG (string) */
  onChangeDong: (dong: string) => void;
  placeholder?: string;
  className?: string;
  style?: React.CSSProperties;
}

export default function MoneyInput({ valueDong, onChangeDong, placeholder, className, style }: MoneyInputProps) {
  const dong = Number(valueDong) || 0;
  const nghin = valueDong === '' ? '' : String(Math.round(dong / 1000));

  return (
    <div>
      <div className="relative">
        <input
          type="number"
          min={0}
          value={nghin}
          onChange={e => {
            const v = e.target.value;
            onChangeDong(v === '' ? '' : String((Number(v) || 0) * 1000));
          }}
          placeholder={placeholder || 'VD: 2500000 = 2,5 tỷ'}
          className={className || 'w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)] pr-24'}
          style={style}
        />
        <span
          className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] pointer-events-none"
          style={{ color: 'var(--text-muted)' }}
        >
          nghìn đồng
        </span>
      </div>
      {dong > 0 && (
        <p className="text-[11px] mt-1" style={{ color: 'var(--gold-400)' }}>
          = {dong.toLocaleString('vi-VN')} đ ({shortVN(dong)})
        </p>
      )}
    </div>
  );
}
