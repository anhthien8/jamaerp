'use client';

// «Việc của tôi» (27/10/2026; 13/11 thêm 4 ô đếm): đầu việc mình đảm nhận ở mọi dự án,
// đơn đang chờ mình duyệt (Phê duyệt + đơn vật tư vượt báo giá cho Leader Thu mua),
// và hàng đã đặt chờ Giám sát ra công trình xác nhận.

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';
import { api, ApprovalItem, DongVatTu, ViecCuaToi } from '@/lib/api';

type Nhom = 'qua_han' | 'hom_nay' | 'sap_toi' | 'khong_han';
type Loc = 'hom_nay' | 'qua_han' | 'cho_duyet' | 'dang_mo';

function ngay(s: string) { return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z'); }
function nhom(han: string | null): Nhom {
  if (!han) return 'khong_han';
  const d = ngay(han);
  const now = new Date();
  if (d < now) return 'qua_han';
  if (d.toDateString() === now.toDateString()) return 'hom_nay';
  return 'sap_toi';
}
const NHAN: Record<Nhom, string> = { qua_han: 'Quá hạn', hom_nay: 'Hôm nay', sap_toi: 'Sắp tới', khong_han: 'Chưa có hạn' };
const MAU: Record<Nhom, string> = { qua_han: 'var(--danger, #f87171)', hom_nay: 'var(--warning, #fbbf24)', sap_toi: 'var(--text-secondary)', khong_han: 'var(--text-muted)' };
const the = { background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' };

export default function ViecCuaToiPage() {
  const { toast } = useToast();
  const [ds, setDs] = useState<ViecCuaToi[] | null>(null);
  const [duyet, setDuyet] = useState<ApprovalItem[]>([]);
  const [vtDuyet, setVtDuyet] = useState<DongVatTu[]>([]);
  const [vtNhan, setVtNhan] = useState<DongVatTu[]>([]);
  const [loc, setLoc] = useState<Loc>('dang_mo');

  const tai = useCallback(async () => {
    const [viec, pd, vt] = await Promise.allSettled([api.viecCuaToi(), api.approvalsPendingForMe(), api.vatTuViecDatNhan()]);
    if (viec.status === 'fulfilled') setDs(viec.value);
    else { toast(viec.reason instanceof Error ? viec.reason.message : 'Không tải được', 'error'); setDs([]); }
    setDuyet(pd.status === 'fulfilled' ? pd.value.items : []);
    if (vt.status === 'fulfilled') {
      setVtDuyet(vt.value.la_leader_thu_mua ? vt.value.cho_duyet : []);
      const cuaToi = new Set(vt.value.nhan_cua_toi || []);
      setVtNhan(vt.value.cho_nhan.filter(d => cuaToi.has(d.id)));
    }
  }, [toast]);
  useEffect(() => { void Promise.resolve().then(() => tai()); }, [tai]);

  const doi = async (t: ViecCuaToi, status: string) => {
    try { await api.updateTaskStatus(t.id, status); toast(status === 'done' ? 'Đã xong việc' : 'Đã bắt đầu', 'success'); tai(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Không đổi được', 'error'); }
  };

  const viec = ds || [];
  const homNay = viec.filter(t => nhom(t.han) === 'hom_nay');
  const quaHan = viec.filter(t => nhom(t.han) === 'qua_han');
  const soChoDuyet = duyet.length + vtDuyet.length;
  const soDangMo = viec.length + vtNhan.length;

  const O: { k: Loc; nhan: string; so: number; icon: string; mau: string }[] = [
    { k: 'hom_nay', nhan: 'Đến hạn hôm nay', so: homNay.length, icon: 'calendar', mau: 'var(--warning, #fbbf24)' },
    { k: 'qua_han', nhan: 'Đã quá hạn', so: quaHan.length, icon: 'alarm', mau: 'var(--danger, #f87171)' },
    { k: 'cho_duyet', nhan: 'Đang chờ duyệt', so: soChoDuyet, icon: 'hourglass', mau: 'var(--gold-400)' },
    { k: 'dang_mo', nhan: 'Việc đang mở', so: soDangMo, icon: 'list', mau: 'var(--text-secondary)' },
  ];

  const theViec = (t: ViecCuaToi) => (
    <div key={t.id} className="rounded-2xl p-3 flex items-center gap-3" style={the}>
      <Link href={`/projects?id=${t.project_id}`} className="flex-1 min-w-0">
        <div className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{t.title}</div>
        <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
          {t.project_code} · {t.project_name}{t.han ? ` · hạn ${ngay(t.han).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}` : ''}
        </div>
      </Link>
      {t.status === 'not_started'
        ? <button className="text-xs px-3 py-1.5 rounded-full shrink-0" style={{ border: '1px solid var(--border-subtle)', color: 'var(--gold-400)' }} onClick={() => doi(t, 'in_progress')}>Bắt đầu</button>
        : <button className="text-xs px-3 py-1.5 rounded-full font-medium shrink-0" style={{ background: 'var(--gold-400)', color: '#000' }} onClick={() => doi(t, 'done')}>Xong</button>}
    </div>
  );

  const theLink = (key: string, href: string, tieuDe: string, phu: string, nut: string) => (
    <Link key={key} href={href} className="rounded-2xl p-3 flex items-center gap-3" style={the}>
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{tieuDe}</div>
        <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{phu}</div>
      </div>
      <span className="text-xs px-3 py-1.5 rounded-full shrink-0" style={{ border: '1px solid var(--border-subtle)', color: 'var(--gold-400)' }}>{nut}</span>
    </Link>
  );

  const khoi = (tieuDe: string, mau: string, so: number, noiDung: React.ReactNode) => so > 0 && (
    <section key={tieuDe}>
      <div className="text-sm font-semibold mb-2" style={{ color: mau }}>{tieuDe} · {so}</div>
      <div className="space-y-2">{noiDung}</div>
    </section>
  );

  const dsChoDuyet = (
    <>
      {khoi('Đơn chờ bạn duyệt', 'var(--gold-400)', duyet.length, duyet.map(a => theLink(a.id, '/approvals', a.title,
        `${a.type_label}${a.requester_name ? ` · ${a.requester_name}` : ''}${a.amount ? ` · ${a.amount.toLocaleString('vi-VN')}đ` : ''}`, 'Duyệt')))}
      {khoi('Đơn vật tư vượt báo giá', 'var(--gold-400)', vtDuyet.length, vtDuyet.map(d => theLink(d.id, '/vat-tu?tab=dat-nhan',
        `${d.ma || d.ma_tu_do || 'Vật tư'} · ${d.phong}`, `${d.project_code || ''} · ${d.ly_do_vuot || 'Vượt báo giá'}`, 'Duyệt')))}
    </>
  );
  const dsNhanHang = khoi('Hàng chờ bạn nhận tại công trình', 'var(--text-secondary)', vtNhan.length, vtNhan.map(d => theLink(d.id, '/vat-tu?tab=dat-nhan',
    `${d.ma || d.ma_tu_do || 'Vật tư'} · ${d.phong}`, `${d.project_code || ''} · đặt ${d.sl_dat ?? d.so_luong} ${d.don_vi}${d.trang_thai === 'giao_thieu' ? ' · đang giao thiếu' : ''}`, 'Nhận hàng')));

  return (
    <Sidebar>
      <div className="max-w-3xl mx-auto p-4 space-y-5">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Việc của tôi</h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {O.map(o => (
            <button key={o.k} onClick={() => setLoc(o.k)} className="rounded-2xl p-3 text-left transition-colors"
              style={{ background: 'var(--surface-1)', border: `1px solid ${loc === o.k ? o.mau : 'var(--border-subtle)'}` }}
              aria-pressed={loc === o.k}>
              <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                <LineIcon name={o.icon} size={14} color={o.mau} />{o.nhan}
              </div>
              <div className="text-2xl font-semibold mt-1" style={{ color: o.so > 0 ? o.mau : 'var(--text-muted)' }}>{ds === null ? '…' : o.so}</div>
            </button>
          ))}
        </div>

        {ds === null && <p style={{ color: 'var(--text-muted)' }}>Đang tải…</p>}

        {ds !== null && loc === 'hom_nay' && (homNay.length ? khoi('Đến hạn hôm nay', MAU.hom_nay, homNay.length, homNay.map(theViec))
          : <p style={{ color: 'var(--text-muted)' }}>Hôm nay không có việc đến hạn.</p>)}
        {ds !== null && loc === 'qua_han' && (quaHan.length ? khoi('Đã quá hạn', MAU.qua_han, quaHan.length, quaHan.map(theViec))
          : <p style={{ color: 'var(--text-muted)' }}>Không có việc quá hạn.</p>)}
        {ds !== null && loc === 'cho_duyet' && (soChoDuyet ? dsChoDuyet
          : <p style={{ color: 'var(--text-muted)' }}>Không có đơn nào đang chờ bạn duyệt.</p>)}
        {ds !== null && loc === 'dang_mo' && (soDangMo ? (
          <>
            {(['qua_han', 'hom_nay', 'sap_toi', 'khong_han'] as const).map(k => {
              const nhomDs = viec.filter(t => nhom(t.han) === k);
              return khoi(NHAN[k], MAU[k], nhomDs.length, nhomDs.map(theViec));
            })}
            {dsNhanHang}
          </>
        ) : <p style={{ color: 'var(--text-muted)' }}>Bạn không còn việc nào đang mở.</p>)}
      </div>
    </Sidebar>
  );
}
