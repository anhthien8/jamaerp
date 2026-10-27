'use client';

// «Việc của tôi» (27/10/2026): mọi đầu việc mình đảm nhận ở mọi dự án, gom Quá hạn / Hôm nay / Sắp tới / Chưa có hạn.

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import { useToast } from '@/components/ui/Toast';
import { api, ViecCuaToi } from '@/lib/api';

function nhom(han: string | null): 'qua_han' | 'hom_nay' | 'sap_toi' | 'khong_han' {
  if (!han) return 'khong_han';
  const d = new Date(han.endsWith('Z') || han.includes('+') ? han : han + 'Z');
  const now = new Date();
  if (d < now) return 'qua_han';
  if (d.toDateString() === now.toDateString()) return 'hom_nay';
  return 'sap_toi';
}
const NHAN = { qua_han: 'Quá hạn', hom_nay: 'Hôm nay', sap_toi: 'Sắp tới', khong_han: 'Chưa có hạn' } as const;
const MAU = { qua_han: '#f87171', hom_nay: '#fbbf24', sap_toi: 'var(--text-secondary)', khong_han: 'var(--text-muted)' } as const;

export default function ViecCuaToiPage() {
  const { toast } = useToast();
  const [ds, setDs] = useState<ViecCuaToi[] | null>(null);
  const tai = useCallback(async () => {
    try { setDs(await api.viecCuaToi()); } catch (e) { toast(e instanceof Error ? e.message : 'Không tải được', 'error'); setDs([]); }
  }, [toast]);
  useEffect(() => { tai(); }, [tai]);

  const doi = async (t: ViecCuaToi, status: string) => {
    try { await api.updateTaskStatus(t.id, status); toast(status === 'done' ? 'Đã xong việc' : 'Đã bắt đầu', 'success'); tai(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Không đổi được', 'error'); }
  };

  return (
    <Sidebar>
      <div className="max-w-3xl mx-auto p-4 space-y-5">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Việc của tôi</h1>
        {ds === null && <p style={{ color: 'var(--text-muted)' }}>Đang tải…</p>}
        {ds?.length === 0 && <p style={{ color: 'var(--text-muted)' }}>Bạn không còn việc nào đang mở.</p>}
        {(['qua_han', 'hom_nay', 'sap_toi', 'khong_han'] as const).map(k => {
          const nhomDs = (ds || []).filter(t => nhom(t.han) === k);
          if (!nhomDs.length) return null;
          return (
            <section key={k}>
              <div className="text-sm font-semibold mb-2" style={{ color: MAU[k] }}>{NHAN[k]} · {nhomDs.length}</div>
              <div className="space-y-2">
                {nhomDs.map(t => (
                  <div key={t.id} className="rounded-2xl p-3 flex items-center gap-3" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
                    <Link href={`/projects?id=${t.project_id}`} className="flex-1 min-w-0">
                      <div className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{t.title}</div>
                      <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                        {t.project_code} · {t.project_name}{t.han ? ` · hạn ${new Date(t.han.endsWith('Z') ? t.han : t.han + 'Z').toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}` : ''}
                      </div>
                    </Link>
                    {t.status === 'not_started'
                      ? <button className="text-xs px-3 py-1.5 rounded-full shrink-0" style={{ border: '1px solid var(--border-subtle)', color: 'var(--gold-400)' }} onClick={() => doi(t, 'in_progress')}>Bắt đầu</button>
                      : <button className="text-xs px-3 py-1.5 rounded-full font-medium shrink-0" style={{ background: 'var(--gold-400)', color: '#000' }} onClick={() => doi(t, 'done')}>Xong</button>}
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </Sidebar>
  );
}
