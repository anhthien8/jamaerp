'use client';

/**
 * Hũ doanh số trên Tổng quan (23/10/2026; dựng lại bố cục 24/11/2026): doanh số công ty leo qua
 * từng mốc, mỗi mốc mở thêm quỹ thưởng. Bố cục «bảng đua»: tiêu đề hạng của mình → đồng hồ cung
 * doanh số + thẻ từng mốc → hũ quỹ → đường đua xếp hạng (dòng của mình tô nổi, kèm câu «còn bao
 * nhiêu nữa là vượt người trên») → thẻ thưởng dự kiến của riêng mình.
 * Chỉ hiện khi Chế độ thưởng bật Hũ và người xem nằm trong «Ai thấy hũ» (backend quyết, trả
 * {hien:false} thì ẩn êm). Bảng xếp hạng chỉ có DOANH SỐ — tiền thưởng chỉ hiện của chính người xem.
 */

import { useEffect, useState } from 'react';
import { api, CdtHu, CdtKhoan } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { tien } from '@/lib/tien-gon';
import { CauThuc, DongHo, DuongDua, SO, TO, VANG } from './BangDua';

type CuaToi = { hien: false } | { hien: true; quy: string; diem: number | null; he_so: number; khoan: CdtKhoan[]; tong: number; du_kien_cuoi_quy: number };

/** Hũ thủy tinh: mức vàng = quỹ đã mở / quỹ tối đa. */
function Hu({ pct }: { pct: number }) {
  const h = 104 * Math.max(0, Math.min(1, pct));
  return (
    <svg viewBox="0 0 120 150" className="w-20 sm:w-24 h-auto shrink-0" aria-hidden style={{ color: 'var(--text-primary)' }}>
      <defs>
        <clipPath id="hu-than"><path d="M28 30 Q20 34 20 48 V128 Q20 142 34 142 H86 Q100 142 100 128 V48 Q100 34 92 30 Z" /></clipPath>
        <linearGradient id="hu-vang" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F3D9A4" />
          <stop offset="1" stopColor="#A9824A" />
        </linearGradient>
      </defs>
      <g clipPath="url(#hu-than)">
        <rect x="0" y={142 - h} width="120" height={h} fill="url(#hu-vang)" style={{ transition: 'all 1.2s cubic-bezier(.2,.8,.2,1)' }} />
        {h > 6 && <path d={`M20 ${142 - h} q10 -4 20 0 t20 0 t20 0 t20 0 t20 0`} stroke="#FFF3D6" strokeOpacity=".6" strokeWidth="2" fill="none" />}
      </g>
      <path d="M28 30 Q20 34 20 48 V128 Q20 142 34 142 H86 Q100 142 100 128 V48 Q100 34 92 30" stroke="currentColor" strokeOpacity=".55" strokeWidth="3" fill="none" />
      <rect x="32" y="14" width="56" height="14" rx="4" fill="currentColor" fillOpacity=".1" stroke="currentColor" strokeOpacity=".55" strokeWidth="2" />
      <path d="M32 50 V118" stroke="currentColor" strokeOpacity=".18" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export default function HuDoanhSo() {
  const { user } = useAuth();
  const [hu, setHu] = useState<CdtHu | null>(null);
  const [cuaToi, setCuaToi] = useState<CuaToi | null>(null);
  const [xem, setXem] = useState<'ca_nhan' | 'doi'>('ca_nhan');

  useEffect(() => {
    api.cdtHu().then(setHu).catch(() => setHu({ hien: false }));
    api.request<CuaToi>('/che-do-thuong/cua-toi').then(setCuaToi).catch(() => setCuaToi({ hien: false }));
  }, []);

  if (!hu || !hu.hien) return null;

  const mocCuoi = hu.moc[hu.moc.length - 1]?.doanh_so || 1;
  const pctHu = hu.quy_toi_da > 0 ? hu.quy_mo / hu.quy_toi_da : 0;
  const conNgay = Math.max(0, hu.so_ngay - hu.ngay_da_qua);
  const mocKe = hu.moc.findIndex(m => !m.dat);

  const idToi = xem === 'ca_nhan' ? user?.id : user?.team_id;
  const bang = xem === 'ca_nhan'
    ? hu.ca_nhan.map(x => ({ id: x.user_id, ten: x.ten, doanh_so: x.doanh_so }))
    : hu.doi.map(x => ({ id: x.team_id, ten: x.ten, doanh_so: x.doanh_so }));
  const viTri = bang.findIndex(r => r.id === idToi);
  // Hiện 5 dòng đầu; mình nằm ngoài top 5 thì thêm dòng của mình ở cuối.
  const dongHien = bang.map((r, i) => ({ id: r.id, ten: r.ten, giaTri: r.doanh_so, hang: i + 1 })).filter((r, i) => i < 5 || r.id === idToi);

  // Hạng cá nhân cho tiêu đề (máy chủ chỉ trả 10 người đầu → đủ 10 thì không ghi «/tổng»).
  const hangToi = hu.ca_nhan.findIndex(x => x.user_id === user?.id) + 1;
  const dsToi = hangToi ? hu.ca_nhan[hangToi - 1].doanh_so : 0;

  // Câu thúc: còn bao nhiêu nữa là vượt người ngay trên, chia đều cho số ngày còn lại.
  let cauThuc: React.ReactNode = null;
  if (viTri > 0) {
    const thieu = bang[viTri - 1].doanh_so - bang[viTri].doanh_so;
    cauThuc = (
      <>Còn <b style={{ color: VANG }}>{tien(thieu)}</b> doanh số nữa là <b>vượt {bang[viTri - 1].ten}</b>
        {conNgay > 0 ? <> — khoảng {tien(thieu / conNgay)} mỗi ngày trong {conNgay} ngày còn lại.</> : '.'}</>
    );
  } else if (viTri === 0 && bang[1]) {
    cauThuc = <>{xem === 'ca_nhan' ? 'Bạn' : 'Nhóm bạn'} đang <b>dẫn đầu</b>, hơn {bang[1].ten} <b style={{ color: VANG }}>{tien(bang[0].doanh_so - bang[1].doanh_so)}</b>.</>;
  }

  const coThuong = cuaToi?.hien ? cuaToi : null;
  const khoanHien = coThuong ? coThuong.khoan.filter(k => k.so_tien > 0) : [];
  const dong = (v: number) => `${Math.round(v).toLocaleString('vi-VN')}đ`;

  return (
    <section className="space-y-3" aria-label="Hũ doanh số">
      {/* Tiêu đề: kỳ + hạng của mình */}
      <div>
        <div className="text-xs text-[var(--text-muted)]">Hũ thưởng {hu.nhan_ky} · còn <b className="text-[var(--text-primary)]">{conNgay} ngày</b></div>
        <h2 className={`${TO} text-[2rem] sm:text-[2.75rem] mt-1.5 text-[var(--text-primary)]`}>
          {hangToi ? <>Bạn · hạng {hangToi}{hu.ca_nhan.length < 10 ? `/${hu.ca_nhan.length}` : ''}</> : 'Hũ doanh số'}
        </h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Doanh số công ty: đồng hồ cung + thẻ từng mốc */}
        <div className="card p-4 sm:p-5">
          <div className="flex items-baseline justify-between gap-2 mb-2">
            <h3 className={`${TO} text-xl`}>Doanh số công ty</h3>
            <span className="text-xs text-[var(--text-muted)]">{hu.cong_don ? 'quỹ cộng dồn qua từng mốc' : 'tính theo mốc cao nhất'}</span>
          </div>
          <div className="flex flex-col items-center gap-3">
            <div className="w-full flex flex-col items-center">
              <DongHo giaTri={hu.doanh_so} tran={mocCuoi} hienThi={tien(hu.doanh_so)}
                vach={hu.moc.map(m => ({ giaTri: m.doanh_so, nhan: tien(m.doanh_so) }))}
                moTa={`Doanh số ${tien(hu.doanh_so)}, ${Math.round(Math.min(100, (hu.doanh_so / mocCuoi) * 100))}% tới mốc ${tien(mocCuoi)}`} />
              <div className="text-xs text-[var(--text-muted)] -mt-1">{Math.round(Math.min(100, (hu.doanh_so / mocCuoi) * 100))}% tới mốc {tien(mocCuoi)}</div>
            </div>
            <div className="w-full grid grid-cols-2 gap-2">
              {hu.moc.map((m, i) => {
                const mau = m.dat ? 'var(--success)' : i === mocKe ? 'var(--warning)' : 'var(--border-subtle)';
                return (
                  <div key={i} className="rounded-xl px-3 py-2" style={{ border: `1px solid ${mau}`, background: 'var(--surface-2)' }}>
                    <div className="text-[11px] text-[var(--text-muted)] truncate">Mốc {tien(m.doanh_so)} · mở {tien(m.quy)}</div>
                    <div className="text-sm font-bold" style={{ color: m.dat ? 'var(--success)' : i === mocKe ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {m.dat ? 'Đã đạt' : `còn thiếu ${tien(m.doanh_so - hu.doanh_so)}`}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Quỹ thưởng: hũ đầy dần + phần mình góp */}
        <div className="card p-4 sm:p-5 overflow-hidden relative">
          <div className="absolute -right-16 -top-16 w-56 h-56 rounded-full blur-3xl opacity-20 pointer-events-none" style={{ background: VANG }} />
          <h3 className={`${TO} text-xl mb-3`}>Quỹ thưởng đã mở</h3>
          <div className="flex items-center gap-4 sm:gap-6">
            <Hu pct={pctHu} />
            <div className="min-w-0 flex-1">
              <div className={`${SO} text-[2.25rem] sm:text-[2.75rem]`} style={{ color: VANG }}>{tien(hu.quy_mo)}</div>
              <div className="text-xs text-[var(--text-muted)] mt-1.5">tối đa {tien(hu.quy_toi_da)} · đạt {hu.so_moc_dat}/{hu.moc.length} mốc</div>
              <div className="mt-3 text-sm text-[var(--text-secondary)]">
                {hu.moc_tiep
                  ? <>Qua mốc «{hu.moc_tiep.nhan}» mở thêm <b style={{ color: VANG }}>{tien(hu.moc_tiep.quy)}</b>.</>
                  : <b style={{ color: VANG }}>Đã phá đảo mọi mốc!</b>}
              </div>
              {hangToi > 0 && hu.doanh_so > 0 && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-[var(--text-muted)]">
                    <span>Bạn góp <b className="text-[var(--text-primary)]">{Math.round((dsToi / hu.doanh_so) * 100)}%</b> doanh số</span>
                    <span className="font-mono">{tien(dsToi)}</span>
                  </div>
                  <div className="h-1.5 rounded-full mt-1" style={{ background: 'var(--surface-3)' }}>
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, (dsToi / hu.doanh_so) * 100)}%`, background: VANG }} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {(bang.length > 0 || hu.doi.length > 0 || coThuong) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Đường đua — chỉ doanh số, không ghi tiền thưởng của ai */}
          {(hu.ca_nhan.length > 0 || hu.doi.length > 0) && (
            <div className={`card p-4 sm:p-5 ${coThuong ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
              <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className={`${TO} text-xl`}>Đường đua</h3>
                {hu.doi.length > 0 && (
                  <div className="inline-flex rounded-full p-0.5 text-xs" style={{ background: 'var(--surface-2)' }}>
                    {([['ca_nhan', 'Cá nhân'], ['doi', 'Nhóm']] as const).map(([k, n]) => (
                      <button key={k} onClick={() => setXem(k)} aria-pressed={xem === k}
                        className="px-3 min-h-[36px] rounded-full font-medium"
                        style={xem === k ? { background: 'var(--text-primary)', color: 'var(--surface-0)' } : { color: 'var(--text-secondary)' }}>{n}</button>
                    ))}
                  </div>
                )}
              </div>
              <DuongDua ds={dongHien} tong={hu.doanh_so} dinhDang={tien} idToi={idToi} nhanTong="công ty" hauToToi={xem === 'ca_nhan' ? ' (bạn)' : ''} />
              {cauThuc && <CauThuc>{cauThuc}</CauThuc>}
            </div>
          )}

          {/* Thưởng dự kiến của riêng người xem */}
          {coThuong && (
            <div className="rounded-[var(--radius-card)] p-4 sm:p-5 lg:col-span-1" style={{ background: VANG, color: 'var(--surface-0)' }}>
              <div className="text-overline opacity-80">Thưởng dự kiến {hu.nhan_ky}</div>
              <div className={`${SO} text-[2.25rem] mt-2 break-words`}>{dong(coThuong.tong)}</div>
              <div className="text-xs opacity-80 mt-1.5">
                Tính theo số hôm nay{coThuong.du_kien_cuoi_quy > 0 ? <> · cuối {coThuong.quy} dự kiến thêm <b>{dong(coThuong.du_kien_cuoi_quy)}</b></> : ''}
              </div>
              {khoanHien.length > 0 && (
                <div className="rounded-xl px-3 py-1 mt-3" style={{ background: 'rgba(0,0,0,0.14)' }}>
                  {khoanHien.map(k => (
                    <div key={k.ma} className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
                      <span className="min-w-0 truncate opacity-85">{k.nhan}{k.chi_ky_nay ? '' : ' · cuối quý'}</span>
                      <b className="shrink-0">{dong(k.so_tien)}</b>
                    </div>
                  ))}
                </div>
              )}
              <div className="rounded-xl px-3 py-2.5 mt-3 text-sm font-medium" style={{ background: 'rgba(0,0,0,0.14)' }}>
                {coThuong.diem != null && <>Điểm JAMA <b>{Math.round(coThuong.diem)}</b> · hệ số ×{coThuong.he_so}. </>}
                {hu.moc_tiep
                  ? <>Công ty còn {tien(hu.con_thieu)} là qua mốc «{hu.moc_tiep.nhan}», hũ mở thêm {tien(hu.moc_tiep.quy)}.</>
                  : <>Hũ đã mở hết các mốc.</>}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
