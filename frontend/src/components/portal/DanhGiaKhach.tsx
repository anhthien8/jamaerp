'use client';

/**
 * Khách chấm sao trên trang tiến độ (23/10/2026) — chương trình «Khách hàng đánh giá»
 * trong Chế độ thưởng. Chỉ hiện khi chương trình bật và có mốc đã MỞ (ký HĐ thiết kế,
 * chốt bản vẽ, bàn giao, sau 3 tháng). Mỗi mốc chấm 1 lần; khen tên người trong đội dự án.
 * Gọi thẳng /portal/{token}/... (không JWT) như các khối khác của portal.
 */

import { useEffect, useState } from 'react';
import LineIcon from '@/components/ui/LineIcon';

type Moc = { ma: string; ten: string; mo: boolean; da_cham: { so_sao: number; nhan_xet: string | null; luc: string | null } | null };
type DuLieu = { bat: boolean; moc: Moc[]; doi_ngu: { id: string; ten: string; vai: string }[] };

const VANG = '#C9A96E';
const NHAN_SAO = ['', 'Rất chưa hài lòng', 'Chưa hài lòng', 'Tạm ổn', 'Hài lòng', 'Rất hài lòng'];

export default function DanhGiaKhach({ api, token, projectId }: { api: string; token: string; projectId: string }) {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [sao, setSao] = useState(0);
  const [nhanXet, setNhanXet] = useState('');
  const [khen, setKhen] = useState('');
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState('');
  const [camOn, setCamOn] = useState(false);

  useEffect(() => {
    let huy = false;
    fetch(`${api}/portal/${token}/projects/${projectId}/danh-gia`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (!huy) setDl(d); })
      .catch(() => {});
    return () => { huy = true; };
  }, [api, token, projectId]);

  if (!dl || !dl.bat) return null;
  const choCham = dl.moc.find(m => m.mo && !m.da_cham);
  const daCham = dl.moc.filter(m => m.da_cham);
  if (!choCham && daCham.length === 0 && !camOn) return null;

  const gui = async () => {
    if (!choCham || !sao) return;
    setDangGui(true); setLoi('');
    try {
      const res = await fetch(`${api}/portal/${token}/projects/${projectId}/danh-gia`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ moc: choCham.ma, so_sao: sao, nhan_xet: nhanXet.trim(), khen_user_id: khen || null }),
      });
      if (!res.ok) throw new Error();
      setDl(d => d && { ...d, moc: d.moc.map(m => m.ma === choCham.ma ? { ...m, da_cham: { so_sao: sao, nhan_xet: nhanXet.trim() || null, luc: new Date().toISOString() } } : m) });
      setSao(0); setNhanXet(''); setKhen(''); setCamOn(true);
    } catch {
      setLoi('Chưa gửi được — vui lòng thử lại hoặc gọi JAMA HOME: 070.56.23456');
    } finally { setDangGui(false); }
  };

  return (
    <div className="p-4 rounded-xl" style={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.08)' }}>
      <h3 className="text-xs font-semibold mb-2" style={{ color: '#9BA7B4' }}><LineIcon name="star" size={14} color={VANG} className="inline-block align-[-2px] mr-1.5" />Đánh giá của bạn</h3>

      {daCham.length > 0 && (
        <div className="space-y-1 mb-3">
          {daCham.map(m => (
            <div key={m.ma} className="flex items-center justify-between gap-2 text-xs">
              <span className="text-white">{m.ten}</span>
              <span style={{ color: VANG }}>{'★'.repeat(m.da_cham!.so_sao)}<span style={{ color: '#3a3f47' }}>{'★'.repeat(5 - m.da_cham!.so_sao)}</span></span>
            </div>
          ))}
        </div>
      )}

      {camOn && !choCham && <p className="text-[11px]" style={{ color: '#10B981' }}>Cảm ơn bạn đã đánh giá — JAMA HOME ghi nhận và gửi tới đội dự án.</p>}

      {choCham && (
        <div className="space-y-2.5">
          <p className="text-[11px]" style={{ color: '#9BA7B4' }}>
            Bạn thấy JAMA làm thế nào ở mốc <span className="text-white">{choCham.ten}</span>?
          </p>
          <div className="flex items-center justify-center gap-2" role="radiogroup" aria-label="Số sao">
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} type="button" role="radio" aria-checked={sao === n} aria-label={`${n} sao`} onClick={() => setSao(n)}
                className="text-3xl leading-none w-11 h-11 transition-transform active:scale-90"
                style={{ color: n <= sao ? VANG : '#3a3f47' }}>★</button>
            ))}
          </div>
          {sao > 0 && <p className="text-center text-[11px]" style={{ color: VANG }}>{NHAN_SAO[sao]}</p>}
          {sao > 0 && (
            <>
              <textarea value={nhanXet} onChange={e => setNhanXet(e.target.value)} rows={2} maxLength={1000}
                placeholder={sao <= 2 ? 'Điều gì khiến bạn chưa hài lòng? Trưởng phòng sẽ gọi lại bạn.' : 'Cảm nhận của bạn (không bắt buộc)'}
                className="w-full px-3 py-2 rounded-lg text-base sm:text-xs"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }} />
              {sao >= 4 && dl.doi_ngu.length > 0 && (
                <div>
                  <p className="text-[11px] mb-1.5" style={{ color: '#9BA7B4' }}>Muốn khen riêng ai không?</p>
                  <div className="flex flex-wrap gap-1.5">
                    {dl.doi_ngu.map(p => (
                      <button key={p.id} type="button" onClick={() => setKhen(k => (k === p.id ? '' : p.id))}
                        className="px-3 py-1.5 rounded-full text-[11px]"
                        style={khen === p.id
                          ? { background: VANG, color: '#0D1117', fontWeight: 600 }
                          : { border: '1px solid rgba(255,255,255,0.15)', color: '#E6EDF3' }}>
                        {p.ten}{p.vai ? ` · ${p.vai}` : ''}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <button onClick={gui} disabled={dangGui}
                className="w-full py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)', color: 'white' }}>
                {dangGui ? 'Đang gửi...' : 'Gửi đánh giá'}
              </button>
            </>
          )}
          {loi && <p className="text-[11px]" style={{ color: '#F87171' }}>{loi}</p>}
        </div>
      )}
    </div>
  );
}
