'use client';

/**
 * Hiệu quả AI (26/10/2026) — AI hiện tại có giúp được ai không. Chỉ admin.
 *
 * Bốn chỉ số tính từ dữ liệu sẵn có (GET /ai/hieu-qua, xem backend/app/services/ai_eval.py).
 * Số "—" nghĩa là chưa đủ mẫu, không phải 0. Cách đọc số và bước tiếp:
 * docs/AI_EVOLUTION_PLAN.md mục 4.
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { api, AiHieuQua } from '@/lib/api';
import { STAGE_CONFIG } from '@/lib/utils';

const KY = [7, 30, 90];
const pt = (v: number | null) => (v === null ? '—' : `${v}%`);

export default function HieuQuaAiPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [ky, setKy] = useState(30);
  const [data, setData] = useState<AiHieuQua | null>(null);
  const [error, setError] = useState('');

  const laAdmin = user?.role === 'admin';

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    if (!laAdmin) router.push('/');
  }, [user, loading, laAdmin, router]);

  useEffect(() => {
    if (!laAdmin) return;
    api.aiHieuQua(ky).then(d => { setData(d); setError(''); }).catch(e => setError(e.message));
  }, [laAdmin, ky]);

  if (loading || !user || !laAdmin) return <Sidebar><div className="p-6"><div className="skeleton h-8 w-60 rounded-xl" /></div></Sidebar>;

  const the = data && [
    {
      nhan: 'Sale làm theo gợi ý',
      so: pt(data.goi_y.ti_le_lam),
      phu: `${data.goi_y.da_lam} làm · ${data.goi_y.bo_qua} bỏ qua · ${data.goi_y.chua_phan_hoi} chưa ai bấm`,
    },
    {
      nhan: 'Điểm lead có đúng không',
      so: `${pt(data.diem_lead.cao.ti_le_thang)} / ${pt(data.diem_lead.thap.ti_le_thang)}`,
      phu: `Tỷ lệ thắng: điểm ≥ 70 (${data.diem_lead.cao.da_chot} lead) / điểm < 40 (${data.diem_lead.thap.da_chot} lead)`,
    },
    {
      nhan: 'Lead đi tiếp trong 7 ngày',
      so: `${pt(data.di_tiep_7_ngay.sau_da_lam)} / ${pt(data.di_tiep_7_ngay.sau_bo_qua)}`,
      phu: 'Sau gợi ý «Đã làm» / sau gợi ý «Bỏ qua»',
    },
    {
      nhan: 'AI thật (không phải luật dự phòng)',
      so: pt(data.nguon.ti_le_llm),
      phu: `${data.nguon.llm} lần LLM · ${data.nguon.luat} lần luật`,
    },
  ];

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 space-y-5 max-w-6xl">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Hiệu quả AI</h1>
            <p className="text-xs text-[var(--text-muted)] mt-1">AI có đang giúp sale chốt khách không · «—» là chưa đủ số liệu</p>
          </div>
          <div className="flex gap-2">
            {KY.map(k => (
              <button
                key={k}
                onClick={() => setKy(k)}
                className="px-4 min-h-[44px] rounded-full text-sm font-medium"
                style={ky === k
                  ? { background: 'var(--text-primary)', color: 'var(--surface-1, #000)' }
                  : { background: 'var(--surface-2)', color: 'var(--text-secondary)' }}
              >
                {k} ngày
              </button>
            ))}
          </div>
        </header>

        {error && <p className="text-xs text-[#F87171] glass-card p-3">{error}</p>}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(the || []).map(t => (
            <div key={t.nhan} className="glass-card p-4">
              <p className="text-[11px] text-[var(--text-muted)]">{t.nhan}</p>
              <p className="text-2xl font-bold mt-1 text-[var(--text-primary)]">{t.so}</p>
              <p className="text-[11px] text-[var(--text-secondary)] mt-1">{t.phu}</p>
            </div>
          ))}
        </div>

        {data && (
          <section className="glass-card p-4 space-y-3">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">AI chấm sai — điểm cao mà mất, điểm thấp mà thắng</h2>
            {data.diem_lead.cham_sai.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">Chưa có lead nào bị chấm sai trong kỳ này.</p>
            ) : (
              <ul className="divide-y divide-white/5">
                {data.diem_lead.cham_sai.map(l => (
                  <li key={l.id} className="flex items-center justify-between py-2 text-sm">
                    <Link href={`/leads?lead=${l.id}`} className="text-[var(--text-primary)] hover:underline">{l.name}</Link>
                    <span className="text-xs text-[var(--text-secondary)]">
                      Điểm {Math.round(l.ai_score)} · {STAGE_CONFIG[l.stage]?.label || l.stage}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </Sidebar>
  );
}
