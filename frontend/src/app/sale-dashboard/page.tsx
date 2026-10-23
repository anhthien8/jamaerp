'use client';

/**
 * Bảng điều khiển Kinh doanh — bản thử nghiệm, CHỈ tài khoản admin (13/10/2026).
 *
 * Dựng theo dashboard mẫu chủ dự án gửi. Mọi số đều lấy từ dữ liệu thật qua
 * GET /dashboard/sales (một lần gọi cho cả màn, xem backend/app/api/sales_dashboard.py)
 * — không có số cứng, không có dữ liệu mẫu.
 *
 * Quy ước quan trọng khi đọc màn này:
 * • Mặc định kỳ = THÁNG NÀY (khác Tổng quan mặc định «Mọi lúc») vì toàn bộ mục
 *   tiêu ở đây là mục tiêu tháng.
 * • `muc_tieu` = mục tiêu của cả kỳ; `muc_tieu_tien_do` = mục tiêu tính theo số
 *   ngày ĐÃ trôi qua. Hai số này tách ra để phân biệt «mới đạt 21% vì mới ngày
 *   14» với «đang thật sự chậm».
 * • Mọi khối hiệu suất chỉ tính data ĐẠT TIÊU CHUẨN — chấm nhân viên bằng cả
 *   data tỉnh/số sai là chấm oan.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { api, SalesDashboard, SalesKpiCard, SalesPerson, SalesTargets } from '@/lib/api';
import { formatCurrency, SOURCE_LABELS } from '@/lib/utils';
import { DATE_PRESETS, nhanKy, resolveDateRange } from '@/lib/date-filter';

// Phải khớp `VAI_TRO_XEM` ở backend và `VAI_TRO_SALE_DASHBOARD` ở Sidebar.
const DUOC_XEM = ['admin'];

const NHAN_KPI: Record<SalesKpiCard['ma'], string> = {
  doanh_thu: 'Doanh thu thực tế',
  hd_thiet_ke: 'Deal thiết kế',
  hd_thi_cong: 'Deal thi công',
  khach_khao_sat: 'Tổng khách khảo sát',
  ty_le_lien_he: 'Tỷ lệ liên hệ thành công',
};

const MAU_RO: Record<string, string> = {
  dat_tieu_chuan: '#34D399',
  khach_tinh: '#FBBF24',
  ngan_sach_thap: '#A78BFA',
  khong_dat: '#F87171',
};

const MAU_MUC_DO: Record<string, { vien: string; nen: string; chu: string; nhan: string }> = {
  gap: { vien: 'rgba(248,113,113,0.35)', nen: 'rgba(248,113,113,0.08)', chu: '#F87171', nhan: 'Gấp' },
  canh_bao: { vien: 'rgba(251,191,36,0.35)', nen: 'rgba(251,191,36,0.08)', chu: '#FBBF24', nhan: 'Cảnh báo' },
  theo_doi: { vien: 'rgba(96,165,250,0.3)', nen: 'rgba(96,165,250,0.07)', chu: '#60A5FA', nhan: 'Theo dõi' },
};

const fmtSo = (n: number) => n.toLocaleString('vi-VN');

/** Giá trị KPI theo đơn vị — tiền thì gọn thành «tỷ/triệu», còn lại giữ số đếm. */
function giaTriKpi(k: SalesKpiCard): string {
  if (k.don_vi === 'vnd') return formatCurrency(k.thuc_te);
  if (k.don_vi === '%') return `${k.thuc_te}%`;
  return fmtSo(k.thuc_te);
}

function mucTieuKpi(k: SalesKpiCard): string {
  if (k.la_nguong) return `Mục tiêu: ≥ ${k.muc_tieu}%`;
  const mt = k.don_vi === 'vnd' ? formatCurrency(k.muc_tieu) : fmtSo(k.muc_tieu);
  return `/ ${mt}`;
}

function Thanh({ pct, mau, cao = 6 }: { pct: number; mau: string; cao?: number }) {
  return (
    <div className="rounded-full overflow-hidden w-full" style={{ height: cao, background: 'var(--surface-3)' }}>
      <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(Math.max(pct, 0), 100)}%`, background: mau }} />
    </div>
  );
}

function Khoi({ tieuDe, phu, children, className }: {
  tieuDe: string; phu?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`glass-card p-5 ${className || ''}`}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{tieuDe}</h2>
        {phu && <p className="text-[11px] text-[var(--text-muted)] mt-0.5">{phu}</p>}
      </div>
      {children}
    </section>
  );
}

function Trong({ chu }: { chu: string }) {
  return <p className="text-xs text-[var(--text-muted)] py-6 text-center">{chu}</p>;
}

/** Mũi tên so với kỳ trước. null = kỳ trước bằng 0 nên không chia được. */
function Delta({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-[11px] text-[var(--text-disabled)]">kỳ trước chưa có số</span>;
  const tang = pct >= 0;
  return (
    <span className="text-[11px] font-semibold" style={{ color: tang ? '#34D399' : '#F87171' }}>
      {tang ? '▲' : '▼'} {Math.abs(pct)}% so với kỳ trước
    </span>
  );
}

export default function SaleDashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<SalesDashboard | null>(null);
  const [error, setError] = useState('');

  // Mặc định «Tháng này»: mọi mục tiêu ở màn này là mục tiêu tháng, để «Mọi lúc»
  // thì % hoàn thành so với mục tiêu tháng là con số vô nghĩa.
  const [datePreset, setDatePreset] = useState('this_month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [teamId, setTeamId] = useState('');
  const ky = resolveDateRange(datePreset, dateFrom, dateTo);
  const kyKey = ky ? `${ky.from}_${ky.to}` : 'all';
  const tenKy = nhanKy(datePreset, dateFrom, dateTo);
  const [lanTai, setLanTai] = useState(0);
  const [khoaDaTai, setKhoaDaTai] = useState<string | null>(null);
  const khoaHienTai = `${kyKey}|${teamId}|${lanTai}`;
  const dangTai = khoaDaTai !== null && khoaDaTai !== khoaHienTai;

  const taiLai = useCallback(() => setLanTai(n => n + 1), []);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    // Backend chặn cứng ở admin; chặn thêm ở đây để người khác không rơi vào
    // trang trắng kèm 403 mà không hiểu vì sao.
    if (!DUOC_XEM.includes(user.role)) router.push('/');
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !DUOC_XEM.includes(user.role)) return;
    api.getSalesDashboard(ky, teamId || null)
      .then(d => { setData(d); setError(''); })
      .catch(e => setError(e.message))
      .finally(() => setKhoaDaTai(khoaHienTai));
    // Phụ thuộc `kyKey` (chuỗi) chứ KHÔNG phải object `ky` — `resolveDateRange`
    // trả object mới mỗi lần render nên để `ky` vào đây là gọi API vô hạn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, kyKey, teamId, lanTai]);

  if (loading || (!data && !error)) return (
    <Sidebar>
      <div className="p-6 space-y-6">
        <div className="skeleton h-8 w-72 rounded-xl" />
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="glass-card p-5">
              <div className="skeleton h-3 w-28 mb-3 rounded" />
              <div className="skeleton h-7 w-24 mb-2 rounded" />
              <div className="skeleton h-2 w-full rounded" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => <div key={i} className="glass-card p-6"><div className="skeleton h-48 w-full rounded-xl" /></div>)}
        </div>
      </div>
    </Sidebar>
  );

  if (!user || !DUOC_XEM.includes(user.role)) return null;

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        {/* ── Đầu trang ─────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              Bảng điều khiển <span className="gold-gradient">Kinh doanh</span>
            </h1>
            <p className="text-[var(--text-secondary)] text-sm mt-1">
              Hiệu suất phòng kinh doanh theo kỳ — doanh số, chất lượng data, phễu bán hàng và việc cần làm.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Lọc số liệu theo kỳ"
              value={datePreset}
              onChange={e => setDatePreset(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] border border-[var(--border-subtle)] outline-none cursor-pointer"
              style={{ color: 'var(--gold-500)', borderColor: 'rgba(201,169,110,0.5)' }}
            >
              {DATE_PRESETS.filter(p => p.value !== 'all').map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
            {datePreset === 'custom' && (
              <>
                <input type="date" aria-label="Từ ngày" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                  className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none" />
                <span className="text-xs text-[var(--text-muted)]">→</span>
                <input type="date" aria-label="Đến ngày" value={dateTo} onChange={e => setDateTo(e.target.value)}
                  className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none" />
              </>
            )}
            <select
              aria-label="Lọc theo nhóm kinh doanh"
              value={teamId}
              onChange={e => setTeamId(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none cursor-pointer"
            >
              <option value="">Tất cả nhóm</option>
              {(data?.danh_sach_nhom || []).map(n => <option key={n.id} value={n.id}>{n.ten}</option>)}
            </select>
            <button type="button" onClick={taiLai}
              className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
              Làm mới
            </button>
            {dangTai && <span className="text-xs text-[var(--text-muted)] animate-pulse">đang tải…</span>}
          </div>
        </div>

        {/* Bản thử nghiệm — nói thẳng để không ai tưởng đây là màn đã chốt */}
        <div className="px-3 py-2 rounded-xl text-xs flex flex-wrap items-center gap-2"
          style={{ background: 'rgba(201,169,110,0.07)', border: '1px solid rgba(201,169,110,0.25)', color: 'var(--text-secondary)' }}>
          <span className="font-semibold" style={{ color: 'var(--gold-500)' }}>BẢN THỬ NGHIỆM</span>
          <span>— chỉ tài khoản quản trị xem được, chưa mở cho Ban giám đốc và phòng kinh doanh.</span>
          {data && (
            <span className="ml-auto text-[var(--text-muted)]">
              Kỳ: {tenKy || `${data.ky.tu} → ${data.ky.den}`}
              {' · '}Cập nhật: {new Date(data.cap_nhat_luc).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>

        {error && (
          <div className="px-4 py-3 rounded-xl text-sm" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)', color: '#F87171' }}>
            {error}
          </div>
        )}

        {data && (
          <>
            {/* ── 5 thẻ KPI ─────────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
              {data.kpi.map(k => {
                const dat = k.dat_tien_do;
                const mau = dat === null ? 'var(--gold-500)' : dat ? '#34D399' : '#FBBF24';
                return (
                  <div key={k.ma} className="glass-card p-5">
                    <p className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">{NHAN_KPI[k.ma]}</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-xl font-bold text-[var(--text-primary)]">{giaTriKpi(k)}</span>
                      <span className="text-xs text-[var(--text-muted)]">{mucTieuKpi(k)}</span>
                    </div>
                    <div className="mt-3"><Thanh pct={k.phan_tram} mau={mau} /></div>
                    <div className="flex items-center justify-between mt-2 gap-2">
                      <Delta pct={k.delta_pct} />
                      <span className="text-[11px] font-semibold" style={{ color: mau }}>{k.phan_tram}%</span>
                    </div>
                    {/* Mục tiêu tới hôm nay: tránh đọc «mới 21%» thành «đang thất bại» */}
                    {!k.la_nguong && (
                      <p className="text-[10px] text-[var(--text-disabled)] mt-1">
                        Mục tiêu tới hôm nay: {k.don_vi === 'vnd' ? formatCurrency(k.muc_tieu_tien_do) : fmtSo(k.muc_tieu_tien_do)}
                        {dat !== null && (dat ? ' · đúng tiến độ' : ' · đang chậm')}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* ── Chu kỳ 6 tháng + Doanh số theo tháng ──────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Khoi tieuDe="Tổng doanh thu chu kỳ (6 tháng gần nhất)" phu="Tính trên giá trị dự án thắng deal, không phụ thuộc bộ lọc kỳ">
                <p className="text-2xl font-bold gold-gradient">{formatCurrency(data.chu_ky_6_thang.tong)}</p>
                <div className="mt-1"><Delta pct={data.chu_ky_6_thang.delta_pct} /></div>
                <dl className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <dt className="text-[var(--text-muted)]">Trung bình/tháng</dt>
                    <dd className="font-semibold text-[var(--text-primary)]">{formatCurrency(data.chu_ky_6_thang.trung_binh)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[var(--text-muted)]">Cao nhất</dt>
                    <dd className="font-semibold" style={{ color: '#34D399' }}>
                      {data.chu_ky_6_thang.cao_nhat
                        ? `${formatCurrency(data.chu_ky_6_thang.cao_nhat.thuc_te)} (${data.chu_ky_6_thang.cao_nhat.nhan})`
                        : '—'}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[var(--text-muted)]">Thấp nhất</dt>
                    <dd className="font-semibold" style={{ color: '#FBBF24' }}>
                      {data.chu_ky_6_thang.thap_nhat
                        ? `${formatCurrency(data.chu_ky_6_thang.thap_nhat.thuc_te)} (${data.chu_ky_6_thang.thap_nhat.nhan})`
                        : '—'}
                    </dd>
                  </div>
                </dl>
              </Khoi>

              <Khoi tieuDe="Doanh số theo tháng (6 tháng gần nhất)" phu="Cột = thực tế · vạch nét đứt = mục tiêu tháng" className="lg:col-span-2">
                {(() => {
                  const dinh = Math.max(
                    1,
                    ...data.doanh_so_theo_thang.map(m => Math.max(m.thuc_te, m.muc_tieu)),
                  );
                  return (
                    <>
                      <div className="flex items-end justify-between gap-2 sm:gap-4" style={{ height: 180 }}>
                        {data.doanh_so_theo_thang.map(m => {
                          const dat = m.thuc_te >= m.muc_tieu;
                          return (
                            <div key={m.thang} className="flex-1 flex flex-col items-center h-full">
                              <div className="relative w-full flex-1">
                                <div
                                  className="absolute bottom-0 left-1/4 right-1/4 rounded-t-md transition-all"
                                  style={{
                                    height: `${(m.thuc_te / dinh) * 100}%`,
                                    background: dat
                                      ? 'linear-gradient(180deg, #34D399, rgba(52,211,153,0.35))'
                                      : 'linear-gradient(180deg, var(--gold-500), rgba(201,169,110,0.3))',
                                  }}
                                  title={`${m.nhan}: ${formatCurrency(m.thuc_te)} / mục tiêu ${formatCurrency(m.muc_tieu)}`}
                                />
                                <div
                                  className="absolute left-0 right-0"
                                  style={{ bottom: `${(m.muc_tieu / dinh) * 100}%`, borderTop: '1px dashed rgba(248,113,113,0.75)' }}
                                />
                              </div>
                              <span className="text-[10px] text-[var(--text-muted)] mt-2">{m.nhan}</span>
                              <span className="text-[10px] font-semibold text-[var(--text-tertiary)]">{formatCurrency(m.thuc_te)}</span>
                            </div>
                          );
                        })}
                      </div>
                      <p className="text-[10px] text-[var(--text-disabled)] mt-3">
                        Mục tiêu tháng hiện tại: {formatCurrency(data.muc_tieu.doanh_thu_thang)} — sửa ở khối «Thiết lập mục tiêu» cuối trang.
                      </p>
                    </>
                  );
                })()}
              </Khoi>
            </div>

            {/* ── Chất lượng data + Phễu ────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Khoi
                tieuDe="Chất lượng dữ liệu Marketing"
                phu="Phân loại loại trừ nhau: không đạt → khách tỉnh → ngân sách thấp → đạt tiêu chuẩn"
              >
                <div className="flex items-baseline gap-3">
                  <span className="text-2xl font-bold text-[var(--text-primary)]">{fmtSo(data.chat_luong_data.tong)}</span>
                  <span className="text-xs text-[var(--text-muted)]">data nhận trong kỳ</span>
                  <span className="ml-auto"><Delta pct={data.chat_luong_data.delta_pct} /></span>
                </div>
                {/* Một dải ngang chia 4 phần — thấy ngay tỷ trọng data rác */}
                <div className="flex rounded-full overflow-hidden mt-4" style={{ height: 10, background: 'var(--surface-3)' }}>
                  {data.chat_luong_data.ro.map(r => (
                    <div key={r.ma} style={{ width: `${r.phan_tram}%`, background: MAU_RO[r.ma] }} title={`${r.nhan}: ${r.so_luong}`} />
                  ))}
                </div>
                <ul className="mt-4 space-y-2">
                  {data.chat_luong_data.ro.map(r => (
                    <li key={r.ma} className="flex items-center gap-2 text-xs">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: MAU_RO[r.ma] }} />
                      <span className="text-[var(--text-secondary)]">{r.nhan}</span>
                      <span className="ml-auto font-semibold text-[var(--text-primary)]">{fmtSo(r.so_luong)}</span>
                      <span className="text-[var(--text-muted)] w-12 text-right">{r.phan_tram}%</span>
                    </li>
                  ))}
                </ul>
              </Khoi>

              <Khoi tieuDe="Phễu bán hàng — toàn phòng kinh doanh" phu="Chỉ tính data đạt tiêu chuẩn · % bên phải = so với bước liền trước">
                {data.pheu[0]?.so_luong === 0 ? <Trong chu="Kỳ này chưa có data đạt tiêu chuẩn." /> : (
                  <ul className="space-y-2">
                    {data.pheu.map((b, i) => (
                      <li key={b.ma}>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-[var(--text-secondary)]">{b.nhan}</span>
                          <span className="flex items-center gap-2">
                            <span className="font-semibold text-[var(--text-primary)]">{fmtSo(b.so_luong)}</span>
                            <span className="text-[var(--text-muted)]">{b.phan_tram_goc}%</span>
                            {b.phan_tram_buoc_truoc !== null && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded"
                                style={{
                                  background: b.phan_tram_buoc_truoc >= 50 ? 'rgba(52,211,153,0.12)' : 'rgba(251,191,36,0.12)',
                                  color: b.phan_tram_buoc_truoc >= 50 ? '#34D399' : '#FBBF24',
                                }}>
                                ↓ {b.phan_tram_buoc_truoc}%
                              </span>
                            )}
                          </span>
                        </div>
                        <Thanh pct={b.phan_tram_goc} mau={`hsl(${38 + i * 4} 55% ${62 - i * 4}%)`} cao={8} />
                      </li>
                    ))}
                  </ul>
                )}
              </Khoi>
            </div>

            {/* ── Hiệu suất theo nhóm ───────────────────────────────── */}
            <Khoi tieuDe="Hiệu suất theo nhóm" phu="Các cột liên hệ → ký HĐ chỉ tính data đạt tiêu chuẩn">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                      <th className="text-left py-2 pr-3">Nhóm</th>
                      <th className="text-right py-2 px-2">Data nhận</th>
                      <th className="text-right py-2 px-2">Đạt chuẩn</th>
                      <th className="text-right py-2 px-2">Khách tỉnh</th>
                      <th className="text-right py-2 px-2">NS thấp</th>
                      <th className="text-right py-2 px-2">Không đạt</th>
                      <th className="text-right py-2 px-2">Liên hệ</th>
                      <th className="text-right py-2 px-2">Khảo sát</th>
                      <th className="text-right py-2 px-2">Báo giá</th>
                      <th className="text-right py-2 px-2">Ký HĐ</th>
                      <th className="text-right py-2 px-2">Doanh số</th>
                      <th className="text-right py-2 pl-2 w-28">% Mục tiêu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.hieu_suat_nhom.map(r => (
                      <tr key={r.team_id || 'chua-nhom'} className="border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                        <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">{r.nhom}</td>
                        <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(r.data_nhan)}</td>
                        <td className="text-right px-2" style={{ color: '#34D399' }}>{fmtSo(r.dat_tieu_chuan)} <span className="text-[10px] text-[var(--text-muted)]">{r.pct_dat}%</span></td>
                        <td className="text-right px-2 text-[var(--text-tertiary)]">{fmtSo(r.khach_tinh)}</td>
                        <td className="text-right px-2 text-[var(--text-tertiary)]">{fmtSo(r.ngan_sach_thap)}</td>
                        <td className="text-right px-2 text-[var(--text-tertiary)]">{fmtSo(r.khong_dat)}</td>
                        <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(r.lien_he)}</td>
                        <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(r.khao_sat)}</td>
                        <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(r.bao_gia)}</td>
                        <td className="text-right px-2 font-semibold text-[var(--text-primary)]">{fmtSo(r.ky_hd)}</td>
                        <td className="text-right px-2 font-semibold text-[var(--text-primary)]">{formatCurrency(r.doanh_so)}</td>
                        <td className="text-right pl-2">
                          {r.pct_muc_tieu === null ? (
                            <span className="text-[10px] text-[var(--text-disabled)]">chưa đặt mục tiêu</span>
                          ) : (
                            <div className="flex items-center gap-2 justify-end">
                              <div className="w-14"><Thanh pct={r.pct_muc_tieu} mau={r.pct_muc_tieu >= 100 ? '#34D399' : 'var(--gold-500)'} cao={5} /></div>
                              <span className="text-[10px] text-[var(--text-secondary)] w-9 text-right">{r.pct_muc_tieu}%</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.hieu_suat_nhom.length === 0 && <Trong chu="Chưa có nhóm kinh doanh nào." />}
            </Khoi>

            {/* ── Top nhân viên + Cần hỗ trợ ────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Khoi tieuDe="Nhân viên hiệu suất cao" phu="Xếp theo giá trị dự án thắng deal trong kỳ">
                {data.top_nhan_vien.length === 0 ? <Trong chu="Kỳ này chưa có nhân viên nào có số." /> : (
                  <ul className="space-y-3">
                    {data.top_nhan_vien.map((p, i) => (
                      <li key={p.user_id} className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                          style={{
                            background: i < 3 ? 'rgba(201,169,110,0.15)' : 'var(--surface-3)',
                            color: i < 3 ? '#C9A96E' : 'var(--text-muted)',
                          }}>{i + 1}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-[var(--text-primary)] truncate">{p.ten}</p>
                          <p className="text-[10px] text-[var(--text-muted)]">{p.nhom} · {p.ky_hd} HĐ · {p.data} data</p>
                        </div>
                        <div className="w-20 flex-shrink-0">
                          <Thanh pct={p.pct_muc_tieu} mau={p.pct_muc_tieu >= 100 ? '#34D399' : 'var(--gold-500)'} cao={5} />
                          <p className="text-[10px] text-right mt-1 text-[var(--text-muted)]">{p.pct_muc_tieu}%</p>
                        </div>
                        <span className="text-xs font-semibold text-[var(--text-primary)] w-20 text-right flex-shrink-0">{formatCurrency(p.doanh_so)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Khoi>

              <Khoi tieuDe="Nhân viên cần hỗ trợ" phu="Chỉ xét người nhận ≥ 5 data đạt chuẩn — ít hơn thì chưa đủ căn cứ kết luận">
                {data.can_ho_tro.length === 0 ? <Trong chu="Không ai vướng tiêu chí cần hỗ trợ trong kỳ này." /> : (
                  <ul className="space-y-3">
                    {data.can_ho_tro.map((p: SalesPerson) => (
                      <li key={p.user_id} className="flex items-start gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-[var(--text-primary)] truncate">{p.ten}</p>
                          <p className="text-[10px] text-[var(--text-muted)] mb-1">{p.nhom} · {p.data} data · chờ TB {p.ngay_cho_tb} ngày</p>
                          <div className="flex flex-wrap gap-1">
                            {(p.van_de || []).map(v => (
                              <span key={v.ma} className="text-[10px] px-1.5 py-0.5 rounded"
                                style={{
                                  background: MAU_MUC_DO[v.muc_do].nen,
                                  border: `1px solid ${MAU_MUC_DO[v.muc_do].vien}`,
                                  color: MAU_MUC_DO[v.muc_do].chu,
                                }}>{v.nhan}</span>
                            ))}
                          </div>
                        </div>
                        <span className="text-xs font-semibold text-[var(--text-tertiary)] w-20 text-right flex-shrink-0">{formatCurrency(p.doanh_so)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Khoi>
            </div>

            {/* ── Cảnh báo & việc cần làm ───────────────────────────── */}
            <Khoi
              tieuDe={`Cảnh báo & việc cần làm (${data.canh_bao.length})`}
              phu="Sắp theo mức độ: gấp → cảnh báo → theo dõi"
            >
              {data.canh_bao.length === 0 ? <Trong chu="Không có cảnh báo nào — kỳ này sạch." /> : (
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {data.canh_bao.map(c => {
                    const m = MAU_MUC_DO[c.muc_do];
                    return (
                      <li key={c.ma} className="px-3 py-2.5 rounded-xl flex items-center gap-3"
                        style={{ background: m.nen, border: `1px solid ${m.vien}` }}>
                        <span className="text-base font-bold flex-shrink-0" style={{ color: m.chu }}>{fmtSo(c.so_luong)}</span>
                        <span className="text-xs text-[var(--text-secondary)] flex-1 min-w-0">{c.tieu_de}</span>
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0"
                          style={{ color: m.chu, background: 'var(--surface-2)' }}>{c.nhan_hanh_dong}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Khoi>

            {/* ══ 6 khối ĐỀ XUẤT THÊM ══════════════════════════════════
                Không có trong dashboard mẫu. Dựng được vì dữ liệu đã nằm
                sẵn trong CSDL mà chưa màn hình nào đọc tới. */}
            <div className="flex items-center gap-3 pt-2">
              <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: 'var(--gold-500)' }}>Đề xuất thêm</span>
              <div className="flex-1 h-px" style={{ background: 'var(--border-subtle)' }} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* (1) Tốc độ pipeline */}
              <Khoi
                tieuDe="Lead đang ứ ở bước nào"
                phu="Tuổi trung bình của lead ĐANG ĐỨNG ở mỗi bước (hệ thống chưa lưu lịch sử chuyển bước nên không tính được thời gian nằm từng bước)"
              >
                <ul className="space-y-2">
                  {data.toc_do_pipeline.map(b => (
                    <li key={b.stage} className="flex items-center gap-3 text-xs">
                      <span className="text-[var(--text-secondary)] w-32 flex-shrink-0 truncate">{b.nhan}</span>
                      <span className="text-[var(--text-muted)] w-10 text-right">{fmtSo(b.so_luong)}</span>
                      <div className="flex-1"><Thanh pct={Math.min(b.tuoi_tb / 60 * 100, 100)} mau={b.tuoi_tb >= 30 ? '#F87171' : b.tuoi_tb >= 14 ? '#FBBF24' : '#34D399'} cao={5} /></div>
                      <span className="text-[var(--text-secondary)] w-24 text-right">TB {b.tuoi_tb}d · max {b.tuoi_max}d</span>
                    </li>
                  ))}
                </ul>
              </Khoi>

              {/* (2) Tồn kho lead theo tuổi */}
              <Khoi tieuDe="Tồn kho lead theo tuổi" phu="Chỉ lead đang mở — nhìn ra khối data đang nguội dần">
                <ul className="space-y-2.5">
                  {data.ton_kho_lead.map((r, i) => (
                    <li key={r.nhan} className="flex items-center gap-3 text-xs">
                      <span className="text-[var(--text-secondary)] w-24 flex-shrink-0">{r.nhan}</span>
                      <div className="flex-1"><Thanh pct={r.phan_tram} mau={['#34D399', '#FBBF24', '#F97316', '#F87171'][i] || 'var(--gold-500)'} cao={6} /></div>
                      <span className="font-semibold text-[var(--text-primary)] w-10 text-right">{fmtSo(r.so_luong)}</span>
                      <span className="text-[var(--text-muted)] w-20 text-right">{formatCurrency(r.gia_tri)}</span>
                    </li>
                  ))}
                </ul>
              </Khoi>

              {/* (3) Chuyển đổi theo nguồn */}
              <Khoi tieuDe="Chuyển đổi theo nguồn data" phu="Biết nguồn nào đáng tiêu thêm tiền marketing">
                {data.theo_nguon.length === 0 ? <Trong chu="Kỳ này chưa có data nào." /> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                          <th className="text-left py-2">Nguồn</th>
                          <th className="text-right py-2 px-2">Tổng</th>
                          <th className="text-right py-2 px-2">Đạt chuẩn</th>
                          <th className="text-right py-2 px-2">Khảo sát</th>
                          <th className="text-right py-2 px-2">Ký HĐ</th>
                          <th className="text-right py-2 pl-2">Giá trị</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.theo_nguon.map(n => (
                          <tr key={n.nguon} className="border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                            <td className="py-2 text-[var(--text-primary)]">{SOURCE_LABELS[n.nguon] || (n.nguon === 'khong_ro' ? 'Chưa ghi nguồn' : n.nguon)}</td>
                            <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(n.tong)}</td>
                            <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(n.dat_chuan)} <span className="text-[10px] text-[var(--text-muted)]">{n.pct_dat_chuan}%</span></td>
                            <td className="text-right px-2 text-[var(--text-secondary)]">{fmtSo(n.khao_sat)}</td>
                            <td className="text-right px-2 font-semibold text-[var(--text-primary)]">{fmtSo(n.ky_hd)} <span className="text-[10px] text-[var(--text-muted)]">{n.pct_ky}%</span></td>
                            <td className="text-right pl-2 text-[var(--text-secondary)]">{formatCurrency(n.gia_tri)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Khoi>

              {/* (4) Dự báo có trọng số */}
              <Khoi tieuDe="Dự báo doanh số có trọng số" phu="Pipeline đang mở × xác suất thắng của từng bước">
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div>
                    <p className="text-[10px] uppercase text-[var(--text-muted)]">Pipeline mở</p>
                    <p className="text-sm font-bold text-[var(--text-primary)] mt-1">{formatCurrency(data.du_bao.gia_tri_pipeline)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-[var(--text-muted)]">Dự báo</p>
                    <p className="text-sm font-bold gold-gradient mt-1">{formatCurrency(data.du_bao.du_bao_co_trong_so)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-[var(--text-muted)]">Còn thiếu so mục tiêu</p>
                    <p className="text-sm font-bold mt-1" style={{ color: data.du_bao.con_thieu > 0 ? '#F87171' : '#34D399' }}>
                      {data.du_bao.con_thieu > 0 ? formatCurrency(data.du_bao.con_thieu) : 'Đã đạt'}
                    </p>
                  </div>
                </div>
                <ul className="space-y-2">
                  {data.du_bao.theo_buoc.map(b => (
                    <li key={b.stage} className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--text-secondary)] w-28 flex-shrink-0 truncate">{b.nhan}</span>
                      <span className="text-[var(--text-muted)] w-8 text-right">{fmtSo(b.so_luong)}</span>
                      <span className="text-[10px] text-[var(--text-disabled)] w-10 text-right">×{Math.round(b.xac_suat * 100)}%</span>
                      <div className="flex-1"><Thanh pct={data.du_bao.du_bao_co_trong_so ? b.du_bao / data.du_bao.du_bao_co_trong_so * 100 : 0} mau="var(--gold-500)" cao={5} /></div>
                      <span className="text-[var(--text-secondary)] w-20 text-right">{formatCurrency(b.du_bao)}</span>
                    </li>
                  ))}
                </ul>
              </Khoi>

              {/* (5) Lý do mất lead */}
              <Khoi tieuDe="Lý do mất lead" phu="Cột lý do mất đã lưu từ 27/08/2026 mà trước nay chưa màn hình nào đọc">
                {data.ly_do_mat.length === 0 ? <Trong chu="Kỳ này không có lead nào bị đánh dấu mất." /> : (
                  <ul className="space-y-2.5">
                    {data.ly_do_mat.map(r => (
                      <li key={r.ly_do} className="flex items-center gap-3 text-xs">
                        <span className="text-[var(--text-secondary)] flex-1 min-w-0 truncate" title={r.ly_do}>{r.ly_do}</span>
                        <div className="w-28"><Thanh pct={r.phan_tram} mau="#F87171" cao={5} /></div>
                        <span className="font-semibold text-[var(--text-primary)] w-8 text-right">{fmtSo(r.so_luong)}</span>
                        <span className="text-[var(--text-muted)] w-10 text-right">{r.phan_tram}%</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Khoi>

              {/* (6) Phân khúc theo ngân sách */}
              <Khoi tieuDe="Phân khúc theo mức ngân sách" phu="Ô ngân sách thêm 22/09/2026, tới nay chưa khối nào dùng để phân tích">
                <ul className="space-y-2.5">
                  {data.theo_ngan_sach.map(r => (
                    <li key={r.muc} className="flex items-center gap-3 text-xs">
                      <span className="text-[var(--text-secondary)] w-32 flex-shrink-0">{r.nhan}</span>
                      <div className="flex-1"><Thanh pct={r.phan_tram} mau={r.muc === 'tren_500' ? '#34D399' : r.muc === 'khong_ro' ? '#627D98' : 'var(--gold-500)'} cao={6} /></div>
                      <span className="font-semibold text-[var(--text-primary)] w-10 text-right">{fmtSo(r.tong)}</span>
                      <span className="text-[var(--text-muted)] w-24 text-right">{r.ky_hd} ký · {r.pct_ky}%</span>
                    </li>
                  ))}
                </ul>
              </Khoi>
            </div>

            {/* ── Thiết lập mục tiêu ────────────────────────────────── */}
            <ThietLapMucTieu
              banDau={data.muc_tieu}
              nhom={data.danh_sach_nhom}
              xongThi={taiLai}
            />
          </>
        )}
      </div>
    </Sidebar>
  );
}

/** Một ô số của form mục tiêu. Để NGOÀI component cha: định nghĩa trong thân
 *  render là tạo component mới mỗi lần gõ ⇒ React remount input, mất con trỏ. */
function OSo({ nhan, giaTri, doi, buoc = 1, hau }: {
  nhan: string; giaTri: number; doi: (v: number) => void; buoc?: number; hau?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] text-[var(--text-muted)]">{nhan}</span>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="number" min={0} step={buoc} value={String(giaTri ?? 0)}
          onChange={e => doi(Number(e.target.value) || 0)}
          className="w-full text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-primary)] border border-[var(--border-subtle)] outline-none"
        />
        {hau && <span className="text-[10px] text-[var(--text-muted)] flex-shrink-0">{hau}</span>}
      </div>
    </label>
  );
}

/**
 * Khối «Thiết lập mục tiêu» — ghi vào SystemSetting qua PUT /dashboard/sales/muc-tieu.
 *
 * PUT ghi ĐÈ toàn bộ bản mục tiêu, nên form phải gửi lại cả những trường nó
 * không hiển thị; thiếu một trường là xóa trắng trường đó.
 */
function ThietLapMucTieu({ banDau, nhom, xongThi }: {
  banDau: SalesTargets;
  nhom: Array<{ id: string; ten: string }>;
  xongThi: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [form, setForm] = useState<SalesTargets>(banDau);
  const [khuVuc, setKhuVuc] = useState((banDau.khu_vuc_trong_tam || []).join(', '));
  const [dangLuu, setDangLuu] = useState(false);
  const [thongBao, setThongBao] = useState('');
  const [loi, setLoi] = useState('');

  const doi = (k: keyof SalesTargets, v: number) => setForm(f => ({ ...f, [k]: v }));
  const doiNhom = (id: string, v: number) =>
    setForm(f => ({ ...f, theo_nhom: { ...(f.theo_nhom || {}), [id]: { ...(f.theo_nhom?.[id] || {}), doanh_thu_thang: v } } }));

  const luu = async () => {
    setDangLuu(true); setLoi(''); setThongBao('');
    try {
      await api.saveSalesTargets({
        ...form,
        khu_vuc_trong_tam: khuVuc.split(',').map(s => s.trim()).filter(Boolean),
      });
      setThongBao('Đã lưu mục tiêu. Số liệu phía trên đang tải lại.');
      xongThi();
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Lưu mục tiêu thất bại');
    } finally {
      setDangLuu(false);
    }
  };

  return (
    <section className="glass-card p-5">
      <button type="button" onClick={() => setMo(!mo)} className="w-full flex items-center gap-3 text-left">
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Thiết lập mục tiêu</h2>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            Mục tiêu THÁNG — hệ thống tự chia theo số ngày của kỳ đang xem. Hiện tại: {formatCurrency(banDau.doanh_thu_thang)}/tháng.
          </p>
        </div>
        <span className="text-xs text-[var(--text-muted)]">{mo ? 'Thu gọn ▲' : 'Mở ▼'}</span>
      </button>

      {mo && (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <OSo nhan="Doanh thu / tháng" giaTri={form.doanh_thu_thang} doi={v => doi('doanh_thu_thang', v)} buoc={100_000_000} hau="đ" />
            <OSo nhan="Deal thiết kế" giaTri={form.hd_thiet_ke_thang} doi={v => doi('hd_thiet_ke_thang', v)} hau="deal" />
            <OSo nhan="Deal thi công" giaTri={form.hd_thi_cong_thang} doi={v => doi('hd_thi_cong_thang', v)} hau="deal" />
            <OSo nhan="Khách khảo sát" giaTri={form.khach_khao_sat_thang} doi={v => doi('khach_khao_sat_thang', v)} hau="khách" />
            <OSo nhan="Tỷ lệ liên hệ tối thiểu" giaTri={form.ty_le_lien_he_toi_thieu} doi={v => doi('ty_le_lien_he_toi_thieu', v)} hau="%" />
          </div>

          <label className="block">
            <span className="text-[11px] text-[var(--text-muted)]">
              Khu vực trọng tâm — lead ngoài danh sách này bị xếp «khách tỉnh» (cách nhau bằng dấu phẩy)
            </span>
            <input
              value={khuVuc} onChange={e => setKhuVuc(e.target.value)}
              className="w-full mt-1 text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-primary)] border border-[var(--border-subtle)] outline-none"
              placeholder="TP. Hồ Chí Minh, Bình Dương"
            />
          </label>

          {nhom.length > 0 && (
            <div>
              <p className="text-[11px] text-[var(--text-muted)] mb-2">
                Doanh thu/tháng theo nhóm — bỏ trống thì cột «% Mục tiêu» của nhóm đó để trống, không suy ra từ mục tiêu phòng.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {nhom.map(n => (
                  <label key={n.id} className="block">
                    <span className="text-[11px] text-[var(--text-secondary)]">{n.ten}</span>
                    <input
                      type="number" min={0} step={100_000_000}
                      value={String(form.theo_nhom?.[n.id]?.doanh_thu_thang ?? 0)}
                      onChange={e => doiNhom(n.id, Number(e.target.value) || 0)}
                      className="w-full mt-1 text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-primary)] border border-[var(--border-subtle)] outline-none"
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button" onClick={luu} disabled={dangLuu}
              className="text-xs font-semibold px-4 py-2 rounded-xl transition-all disabled:opacity-50"
              style={{ background: 'rgba(201,169,110,0.15)', border: '1px solid rgba(201,169,110,0.4)', color: 'var(--gold-500)' }}
            >
              {dangLuu ? 'Đang lưu…' : 'Lưu mục tiêu'}
            </button>
            <button
              type="button" onClick={() => { setForm(banDau); setKhuVuc((banDau.khu_vuc_trong_tam || []).join(', ')); setThongBao(''); setLoi(''); }}
              className="text-xs px-3 py-2 rounded-xl border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              Hoàn lại
            </button>
            {thongBao && <span className="text-xs" style={{ color: '#34D399' }}>{thongBao}</span>}
            {loi && <span className="text-xs" style={{ color: '#F87171' }}>{loi}</span>}
          </div>
        </div>
      )}
    </section>
  );
}
