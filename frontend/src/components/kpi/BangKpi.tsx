'use client';

/**
 * Các khối dùng chung của trang KPI: bảng nhân viên (gom theo nhóm), phần giải
 * thích điểm của một người, và bảng «Cách tính điểm».
 *
 * Mọi nhãn/mốc lấy từ dữ liệu backend trả về (`thanh_phan`, `cong_thuc`) — không
 * chép tay công thức ở đây, để đổi mốc trong kpi_engine.py là màn hình đổi theo.
 */

import { Fragment, useMemo, useState } from 'react';
import Link from 'next/link';
import type { KpiCongThuc, KpiMetrics, KpiNhanVien, KpiThanhPhan, KpiViec } from '@/lib/api';
import { tien } from '@/lib/tien-gon';
import { STAGE_CONFIG, mauNhat } from '@/lib/utils';
import LineIcon from '@/components/ui/LineIcon';

export const so = (v: number | null | undefined, le = 1) =>
  v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: le });

export const mauDiem = (score: number, nguongDat = 80, nguongKem = 60) =>
  score >= nguongDat ? 'var(--success)' : score >= nguongKem ? 'var(--warning)' : 'var(--danger)';

const MAU_MUC: Record<string, string> = {
  do: 'var(--danger)', vang: 'var(--warning)', xanh: 'var(--success)', xam: 'var(--text-muted)',
};
export const mauMuc = (muc: string) => MAU_MUC[muc] || 'var(--text-muted)';

export function Delta({ v, donVi = '' }: { v: number | null | undefined; donVi?: string }) {
  if (v == null || v === 0) return null;
  return (
    <span className="text-xs font-medium whitespace-nowrap" style={{ color: v > 0 ? 'var(--success)' : 'var(--danger)' }}>
      {v > 0 ? '▲' : '▼'} {so(Math.abs(v))}{donVi}
    </span>
  );
}

const TRU_COT_MAC_DINH = [
  { ma: 'ket_qua', ten: 'Kết quả', trong_so: 50 },
  { ma: 'cham_khach', ten: 'Chăm khách', trong_so: 30 },
  { ma: 'chat_luong', ten: 'Chất lượng', trong_so: 20 },
];

/** Thanh 0–100 có màu theo ngưỡng. */
function Thanh({ diem }: { diem: number }) {
  return (
    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, diem))}%`, background: mauDiem(diem) }} />
    </div>
  );
}

/** «Thực tế so với mốc» của một thành phần, viết bằng lời. */
function soVoiMoc(tp: KpiThanhPhan): string {
  if (tp.gia_tri == null) return '';
  switch (tp.ma) {
    case 'doanh_so': return `${tien(tp.gia_tri)} / mục tiêu ${tien(tp.moc || 0)}`;
    case 'deal': return `${so(tp.gia_tri)} / mục tiêu ${so(tp.moc)} deal`;
    case 'cham_dung_han': return `${so(tp.gia_tri)}% · mốc đạt ≥ ${so(tp.moc)}%`;
    case 'phan_hoi': return `${so(tp.gia_tri)} giờ làm việc · mốc đạt ≤ ${so(tp.moc)} giờ`;
    case 'tien_buoc': return `${so(tp.gia_tri)}% · mốc đạt ≥ ${so(tp.moc)}%`;
    case 'mat_khach': return `${so(tp.gia_tri)}% · mốc đạt ≤ ${so(tp.moc)}%`;
    default: return so(tp.gia_tri);
  }
}

/** Vì sao người này được số điểm đó: 3 trụ cột, từng thành phần so với mốc. */
export function ChiTietDiem({ m, congThuc }: { m: KpiMetrics; congThuc?: KpiCongThuc }) {
  const thanhPhan = m.thanh_phan || [];
  if (!thanhPhan.length) {
    return <p className="text-sm text-[var(--text-muted)]">Kỳ này chưa có bảng chấm chi tiết.</p>;
  }
  const truCot = congThuc?.tru_cot || TRU_COT_MAC_DINH;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {truCot.map(tru => {
          const diemTru = m.tru_cot?.[tru.ma];
          return (
            <div key={tru.ma} className="rounded-xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-baseline justify-between mb-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
                  {tru.ten} <span className="text-[var(--text-muted)] normal-case">· {tru.trong_so}% điểm</span>
                </p>
                <span className="text-base font-bold" style={{ color: diemTru == null ? 'var(--text-muted)' : mauDiem(diemTru) }}>
                  {diemTru == null ? '—' : so(diemTru)}
                </span>
              </div>
              <div className="space-y-3">
                {thanhPhan.filter(tp => tp.tru === tru.ma).map(tp => (
                  <div key={tp.ma}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm text-[var(--text-primary)]">{tp.ten}</span>
                      <span className="text-sm font-semibold shrink-0" style={{ color: tp.diem == null ? 'var(--text-muted)' : mauDiem(tp.diem) }}>
                        {tp.diem == null ? 'Chưa chấm' : so(tp.diem)}
                      </span>
                    </div>
                    {tp.diem != null && <div className="my-1.5"><Thanh diem={tp.diem} /></div>}
                    <p className="text-xs text-[var(--text-muted)]">
                      {tp.diem == null ? tp.ly_do : soVoiMoc(tp)}
                      <span className="opacity-70"> · trọng số {tp.trong_so}%</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-[var(--text-muted)] leading-relaxed">
        Đang giữ {so(m.lead_dang_giu)} lead ({so(m.lead_tre_cham)} quá hạn chăm) · Nhận trong kỳ {so(m.lead_nhan)} lead ·
        Dự báo từ lead đang mở {tien(m.du_bao || 0)} · {so(m.hoat_dong)} hoạt động ghi trên ERP (chỉ để tham khảo, không tính điểm)
        {m.do_phu != null && m.do_phu < 100 && (
          <> · Điểm tính trên {m.do_phu}% trọng số có đủ dữ liệu, phần còn lại chưa đủ mẫu nên không chấm.</>
        )}
      </p>
    </div>
  );
}

const SO_LEAD_HIEN_SAN = 5;

/**
 * «Việc nên làm tiếp» của chính người đang xem. Điểm chỉ nói đang ở đâu; khối này
 * nói làm gì để lên — mỗi việc kèm đúng các lead cần đụng tới, bấm là gọi/mở được.
 * Nội dung do backend dựng (kpi_engine._viec_tiep) từ cùng số liệu với điểm.
 */
export function ViecNenLam({ ds, diem, nguongDat = 80 }: { ds: KpiViec[]; diem: number; nguongDat?: number }) {
  const [moRong, setMoRong] = useState<Record<string, boolean>>({});

  if (!ds.length) {
    return (
      <div className="glass-card p-5 flex items-start gap-3">
        <span className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ background: mauNhat('var(--success)', 18) }}>
          <LineIcon name="check" size={16} color="var(--success)" />
        </span>
        <div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">Không có việc tồn</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
            Lead của bạn đều đang trong hạn chăm và bạn đang kịp mốc hôm nay. Giữ nhịp này.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-baseline justify-between gap-x-3 gap-y-1 flex-wrap">
        <p className="text-sm font-semibold text-[var(--text-primary)]">Việc nên làm tiếp</p>
        {diem < nguongDat && ds[0].ma !== 'chua_co_lead' && (
          <span className="text-xs text-[var(--text-muted)]">Còn {so(nguongDat - diem)} điểm nữa là tới mốc đạt {nguongDat}</span>
        )}
      </div>
      <p className="text-xs text-[var(--text-muted)] mt-1 mb-4">Xếp theo độ gấp. Làm xong, tải lại trang là điểm cập nhật.</p>
      <ol className="space-y-5">
        {ds.map((v, i) => {
          const mau = mauMuc(v.muc);
          const mo = !!moRong[v.ma];
          const hien = mo ? v.lead : v.lead.slice(0, SO_LEAD_HIEN_SAN);
          return (
            <li key={v.ma} className="flex gap-3">
              <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5"
                style={{ background: mauNhat(mau, 18), color: mau }}>{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-x-2 gap-y-0.5 flex-wrap">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{v.tieu_de}</p>
                  {v.diem_them != null && (
                    <span className="text-xs font-medium whitespace-nowrap" style={{ color: 'var(--success)' }}>
                      có thể thêm khoảng +{so(v.diem_them)} điểm
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{v.ly_do}</p>
                {hien.length > 0 && (
                  <ul className="mt-2.5 rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
                    {hien.map((l, j) => (
                      <li key={l.id} className="flex items-center gap-2 pl-3 pr-2 py-2"
                        style={{ background: 'var(--surface-2)', borderTop: j ? '1px solid var(--border-subtle)' : undefined }}>
                        <Link href={`/leads?id=${l.id}`} className="min-w-0 flex-1 py-0.5" title="Mở thẻ lead">
                          <span className="block text-sm text-[var(--text-primary)] truncate">{l.ten}</span>
                          <span className="block text-xs text-[var(--text-muted)] leading-snug">
                            {STAGE_CONFIG[l.stage]?.label || l.stage}{l.ghi_chu ? ` · ${l.ghi_chu}` : ''}
                          </span>
                        </Link>
                        {l.sdt && (
                          <a href={`tel:${l.sdt.replace(/[^\d+]/g, '')}`} aria-label={`Gọi ${l.ten}`}
                            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full text-xs font-medium shrink-0"
                            style={{ border: '1px solid var(--gold-500)', color: 'var(--gold-500)' }}>
                            <LineIcon name="phone" size={13} color="currentColor" />Gọi
                          </a>
                        )}
                        <Link href={`/leads?id=${l.id}`} aria-label={`Mở thẻ lead ${l.ten}`}
                          className="hidden sm:inline-flex items-center h-9 px-3 rounded-full text-xs font-medium shrink-0 text-[var(--text-secondary)]"
                          style={{ border: '1px solid var(--border-subtle)' }}>
                          Mở
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                {v.lead.length > SO_LEAD_HIEN_SAN && (
                  <button type="button" onClick={() => setMoRong(m => ({ ...m, [v.ma]: !mo }))}
                    className="mt-2 text-xs font-medium text-[var(--gold-500)] py-1">
                    {mo ? 'Thu gọn' : `Xem thêm ${v.lead.length - SO_LEAD_HIEN_SAN} lead`}
                  </button>
                )}
                {mo && v.tong_lead > v.lead.length && (
                  <p className="text-xs text-[var(--text-muted)] mt-1">Còn {v.tong_lead - v.lead.length} lead nữa, xem ở trang Lead.</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

type CotSapXep = 'score' | 'doanh_so' | 'deal_thang' | 'lead_dang_giu' | 'lead_tre_cham';
const giaTriCot = (h: KpiNhanVien, cot: CotSapXep) => (cot === 'score' ? h.score : h.metrics[cot] || 0);

function tomTatNhom(ds: KpiNhanVien[]) {
  const coSo = ds.filter(h => !h.metrics.chua_du_lieu);
  return {
    diemTb: coSo.length ? coSo.reduce((a, h) => a + h.score, 0) / coSo.length : null,
    doanhSo: ds.reduce((a, h) => a + (h.metrics.doanh_so || 0), 0),
    deal: ds.reduce((a, h) => a + (h.metrics.deal_thang || 0), 0),
    treCham: ds.reduce((a, h) => a + (h.metrics.lead_tre_cham || 0), 0),
    truongNhom: ds.find(h => h.la_truong_nhom)?.name || null,
  };
}

/**
 * Bảng KPI từng người. `gomTheoNhom`: chèn dòng tiêu đề cho mỗi nhóm (tên nhóm,
 * trưởng nhóm, số tổng của nhóm) — không có nó thì cả công ty chỉ là một dãy tên.
 */
export function BangNhanVien({ ds, congThuc, gomTheoNhom = true }: {
  ds: KpiNhanVien[]; congThuc?: KpiCongThuc; gomTheoNhom?: boolean;
}) {
  const [mo, setMo] = useState<string | null>(null);
  const [cot, setCot] = useState<CotSapXep>('score');
  const [giam, setGiam] = useState(true);

  const nhom = useMemo(() => {
    const xep = (a: KpiNhanVien, b: KpiNhanVien) => {
      // Người chưa có dữ liệu luôn ở cuối: 0 điểm của họ là «trống», không phải «kém».
      const trong = Number(!!a.metrics.chua_du_lieu) - Number(!!b.metrics.chua_du_lieu);
      return trong || (giaTriCot(b, cot) - giaTriCot(a, cot)) * (giam ? 1 : -1);
    };
    if (!gomTheoNhom) return [{ khoa: 'tat-ca', ten: null as string | null, ds: [...ds].sort(xep) }];
    const theo = new Map<string, KpiNhanVien[]>();
    ds.forEach(h => {
      const k = h.team_id || '';
      theo.set(k, [...(theo.get(k) || []), h]);
    });
    return [...theo.entries()]
      .map(([k, list]) => ({ khoa: k || 'chua-xep', ten: list[0].ten_nhom || 'Chưa xếp nhóm', ds: list.sort(xep) }))
      // Nhóm doanh số cao đứng trước; «Chưa xếp nhóm» luôn ở cuối
      .sort((a, b) => Number(a.khoa === 'chua-xep') - Number(b.khoa === 'chua-xep')
        || tomTatNhom(b.ds).doanhSo - tomTatNhom(a.ds).doanhSo);
  }, [ds, cot, giam, gomTheoNhom]);

  if (!ds.length) {
    return <div className="glass-card p-8 text-center text-sm text-[var(--text-muted)]">Chưa có dữ liệu KPI kỳ này</div>;
  }

  const doiCot = (c: CotSapXep) => { if (c === cot) setGiam(!giam); else { setCot(c); setGiam(true); } };
  const th = (c: CotSapXep, nhan: string) => (
    <th className="px-3 py-3 text-right font-medium text-[var(--text-muted)] whitespace-nowrap">
      <button type="button" onClick={() => doiCot(c)} className="inline-flex items-center gap-1 hover:text-[var(--text-primary)]">
        {nhan}<span className="text-[10px] w-2">{cot === c ? (giam ? '▼' : '▲') : ''}</span>
      </button>
    </th>
  );

  return (
    <div className="glass-card overflow-x-auto">
      <table className="w-full text-sm min-w-[920px]">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <th className="px-4 py-3 text-left font-medium text-[var(--text-muted)] min-w-[280px]">Nhân viên</th>
            {th('score', 'Điểm')}
            {TRU_COT_MAC_DINH.map(t => (
              <th key={t.ma} className="px-2 py-3 text-right font-medium text-[var(--text-muted)] whitespace-nowrap" title={`${t.trong_so}% tổng điểm`}>{t.ten}</th>
            ))}
            {th('doanh_so', 'Doanh số')}
            {th('deal_thang', 'Deal')}
            {th('lead_dang_giu', 'Lead giữ')}
            {th('lead_tre_cham', 'Trễ chăm')}
          </tr>
        </thead>
        <tbody>
          {nhom.map(g => {
            const tt = tomTatNhom(g.ds);
            return (
              <Fragment key={g.khoa}>
                {g.ten != null && (
                  <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border-subtle)' }}>
                    <td className="px-4 py-2.5">
                      <span className="font-semibold text-[var(--gold-500)]">{g.ten}</span>
                      <span className="text-xs text-[var(--text-muted)]">
                        {' '}· {g.ds.length} người{tt.truongNhom ? ` · Trưởng nhóm: ${tt.truongNhom}` : ''}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold" style={{ color: tt.diemTb == null ? 'var(--text-muted)' : mauDiem(tt.diemTb) }}>
                      {tt.diemTb == null ? '—' : `TB ${so(tt.diemTb)}`}
                    </td>
                    <td colSpan={3} />
                    <td className="px-3 py-2.5 text-right font-semibold text-[var(--text-primary)] whitespace-nowrap">{tien(tt.doanhSo)}</td>
                    <td className="px-3 py-2.5 text-right font-semibold text-[var(--text-primary)]">{so(tt.deal)}</td>
                    <td />
                    <td className="px-3 py-2.5 text-right font-semibold" style={{ color: tt.treCham ? 'var(--warning)' : 'var(--text-muted)' }}>{so(tt.treCham)}</td>
                  </tr>
                )}
                {g.ds.map(h => {
                  const m = h.metrics;
                  const trong = !!m.chua_du_lieu;
                  const dangMo = mo === h.user_id;
                  return (
                    <Fragment key={h.user_id}>
                      <tr
                        onClick={() => setMo(dangMo ? null : h.user_id)}
                        className="cursor-pointer hover:bg-white/5"
                        style={{ borderBottom: '1px solid var(--border-subtle)' }}
                      >
                        <td className="px-4 py-3">
                          <button type="button" aria-expanded={dangMo} className="flex items-center gap-2 text-left">
                            <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0 transition-transform" style={{ transform: dangMo ? 'rotate(90deg)' : 'none' }}>
                              <path d="M3 1l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            <span className="font-medium text-[var(--text-primary)]">{h.name}</span>
                            {h.la_truong_nhom && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}>Trưởng nhóm</span>
                            )}
                          </button>
                          {h.canh_bao.length > 0 && (
                            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 pl-[18px]">
                              {h.canh_bao.map(c => (
                                <span key={c.ma} className="text-xs" style={{ color: mauMuc(c.muc) }}>{c.noi_dung}</span>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3 text-right whitespace-nowrap">
                          {trong ? <span className="text-[var(--text-muted)]">—</span> : (
                            <>
                              <span className="text-base font-bold" style={{ color: mauDiem(h.score) }}>{so(h.score)}</span>
                              <span className="block"><Delta v={h.delta} /></span>
                            </>
                          )}
                        </td>
                        {TRU_COT_MAC_DINH.map(t => {
                          const d = trong ? null : m.tru_cot?.[t.ma];
                          return (
                            <td key={t.ma} className="px-2 py-3 text-right" style={{ color: d == null ? 'var(--text-muted)' : mauDiem(d) }}>
                              {d == null ? '—' : so(d, 0)}
                            </td>
                          );
                        })}
                        <td className="px-3 py-3 text-right whitespace-nowrap">
                          <span className="text-[var(--text-primary)]">{tien(m.doanh_so || 0)}</span>
                          {m.dat_muc_tieu_pct != null && (
                            <span className="block text-xs text-[var(--text-muted)]">{so(m.dat_muc_tieu_pct, 0)}% mục tiêu</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-right">{so(m.deal_thang)}</td>
                        <td className="px-3 py-3 text-right" style={{ color: (m.lead_dang_giu || 0) > (congThuc?.moc.lead_qua_tai ?? 25) ? 'var(--danger)' : undefined }}>
                          {so(m.lead_dang_giu)}
                        </td>
                        <td className="px-3 py-3 text-right" style={{ color: m.lead_tre_cham ? 'var(--warning)' : 'var(--text-muted)' }}>
                          {so(m.lead_tre_cham)}
                        </td>
                      </tr>
                      {dangMo && (
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td colSpan={9} className="px-4 py-4"><ChiTietDiem m={m} congThuc={congThuc} /></td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Công thức đang chạy, đọc từ backend — để ai cũng kiểm lại được điểm của mình. */
export function CachTinhDiem({ congThuc }: { congThuc?: KpiCongThuc }) {
  if (!congThuc) return null;
  const k = congThuc.moc;
  // «Tiếp nhận mới 3 ngày, Đang tư vấn 7 ngày…» — cùng bảng với nhãn «Quá hạn» ở trang Lead
  const hanCham = Object.entries(congThuc.han_cham || {})
    .map(([buoc, ngay]) => `${STAGE_CONFIG[buoc]?.label || buoc} ${ngay} ngày`).join(', ');
  const giaiThich: Record<string, string> = {
    doanh_so: 'Giá trị dự án thắng deal trong kỳ so với mục tiêu đầu người. Kỳ đang chạy thì mục tiêu chia theo số ngày đã qua.',
    deal: 'Số deal thắng trong kỳ so với mục tiêu deal đầu người, cũng chia theo số ngày đã qua.',
    cham_dung_han: `Tỷ lệ lead đang giữ còn trong hạn chăm${hanCham ? ` của bước nó đang đứng (${hanCham})` : ` ${k.so_ngay_cham} ngày`}, hoặc mới nhận, hoặc đã có lịch khảo sát phía trước. Hạn này trùng với nhãn «Quá hạn» ở trang Lead. Đạt ${k.cham_dung_han_dat}% trở lên là 100 điểm.`,
    phan_hoi: `Trung vị thời gian từ lúc được giao lead tới lần chăm đầu tiên, chỉ đếm giờ làm việc (T2–T7, ${k.gio_mo}h–${k.gio_dong}h). Trong ${k.phan_hoi_tot_gio} giờ là 100 điểm, từ ${k.phan_hoi_kem_gio} giờ là 0.`,
    tien_buoc: `Tỷ lệ lead nhận trong kỳ đã tiến tới «Đang tư vấn» trở lên. Đạt ${k.tien_buoc_dat}% là 100 điểm.`,
    mat_khach: `Tỷ lệ lead nhận trong kỳ bị mất. Từ ${k.mat_khach_tot}% trở xuống là 100 điểm, từ ${k.mat_khach_kem}% là 0.`,
  };
  return (
    <details className="glass-card p-5">
      <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">Cách tính điểm KPI</summary>
      <div className="mt-4 space-y-4 text-sm">
        {congThuc.tru_cot.map(tru => (
          <div key={tru.ma}>
            <p className="font-semibold text-[var(--text-secondary)] mb-1.5">{tru.ten} — {tru.trong_so}% tổng điểm</p>
            <ul className="space-y-1.5">
              {congThuc.thanh_phan.filter(tp => tp.tru === tru.ma).map(tp => (
                <li key={tp.ma} className="text-[var(--text-secondary)] leading-relaxed">
                  <span className="text-[var(--text-primary)]">{tp.ten} ({tp.trong_so}%).</span> {giaiThich[tp.ma]}
                </li>
              ))}
            </ul>
          </div>
        ))}
        <p className="text-[var(--text-muted)] leading-relaxed">
          Thành phần chưa đủ mẫu (nhận dưới {k.mau_toi_thieu} lead) không được chấm; trọng số của nó dồn sang các phần còn lại.
          Người không có lead và deal nào trong kỳ được ghi «chưa có dữ liệu», không tính vào điểm trung bình.
          Từ {k.nguong_dat} điểm là đạt, dưới {k.nguong_can_kem} là cần kèm. Số hoạt động ghi trên ERP chỉ hiển thị, không tính điểm.
        </p>
      </div>
    </details>
  );
}
