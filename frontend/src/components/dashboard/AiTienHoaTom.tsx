'use client';

/**
 * Khối «AI Tiến Hoá» trên Tổng quan — chỉ admin (13/11/2026).
 *
 * Tóm tắt 12 tuần: tỷ lệ sale làm theo gợi ý 4 tuần gần nhất so với 4 tuần trước, đường nhỏ
 * theo tuần, vài con số vận hành và số bài học đang chờ duyệt. Chi tiết + duyệt bài học ở
 * /ai-tien-hoa. Lỗi tải thì ẩn khối, không làm vỡ Tổng quan.
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, type AiTienHoa } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import { ChenhLech, Sparkline, pct } from '@/components/ai-tien-hoa/BieuDo';

export default function AiTienHoaTom() {
  const [d, setD] = useState<AiTienHoa | null>(null);
  const [loi, setLoi] = useState(false);

  useEffect(() => {
    api.aiTienHoa(12).then(setD).catch(() => setLoi(true));
  }, []);

  if (loi) return null;
  if (!d) return <div className="card p-4 sm:p-6 h-[168px] skeleton" aria-hidden />;

  const t = d.tong;
  const nho = [
    { nhan: 'Lần AI chạy', gt: t.so_lan_chay.toLocaleString('vi-VN') },
    { nhan: 'Dùng lại bộ nhớ', gt: pct(t.ty_le_dung_lai) },
    { nhan: 'Do LLM trả lời', gt: pct(t.ty_le_llm) },
  ];

  return (
    <section className="card p-4 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-overline text-[var(--text-muted)]">
            <LineIcon name="brain" size={14} color="currentColor" />
            AI Tiến Hoá · 12 tuần
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">Sale làm theo gợi ý của Co-Pilot, 4 tuần gần nhất</p>
        </div>
        <Link href="/ai-tien-hoa"
          className="shrink-0 inline-flex items-center gap-1 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] min-h-[32px]">
          Xem chi tiết <LineIcon name="arrowRight" size={14} color="currentColor" />
        </Link>
      </div>

      <div className="flex items-end justify-between gap-4 mt-3">
        <div className="min-w-0">
          <div className="text-[32px] leading-none font-semibold text-[var(--text-primary)]">{pct(t.ty_le_lam_theo_4_tuan)}</div>
          <div className="mt-2"><ChenhLech v={t.chenh_lech} so_voi="4 tuần trước" /></div>
        </div>
        <Sparkline gt={d.theo_tuan.map(w => w.ty_le_lam_theo)} nhan="Tỷ lệ làm theo gợi ý 12 tuần" />
      </div>

      <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-[var(--border-subtle)]">
        {nho.map(m => (
          <div key={m.nhan} className="min-w-0">
            <div className="text-[11px] text-[var(--text-muted)] truncate">{m.nhan}</div>
            <div className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">{m.gt}</div>
          </div>
        ))}
      </div>

      {d.so_cho_duyet > 0 && (
        <Link href="/ai-tien-hoa#bai-hoc"
          className="mt-4 flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm bg-[var(--surface-2)] border border-[var(--border-default)] hover:border-[var(--border-strong)] min-h-[44px]">
          <LineIcon name="bulb" size={16} color="var(--warning)" />
          <span className="text-[var(--text-primary)]"><b className="font-semibold">{d.so_cho_duyet}</b> bài học AI rút ra đang chờ bạn duyệt</span>
          <LineIcon name="arrowRight" size={14} color="var(--text-muted)" className="ml-auto" />
        </Link>
      )}
    </section>
  );
}
