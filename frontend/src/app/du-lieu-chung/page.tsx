'use client';

/**
 * Dữ liệu chung — CRM phản ánh thực tế tới đâu (20/11/2026). CHỈ BGĐ (admin + executive).
 *
 * Một lần gọi GET /dashboard/du-lieu-chung trả cả màn (backend/app/api/du_lieu_chung.py).
 * Nguyên tắc đọc màn này:
 * • «Chưa cập nhật» = CRM chưa có dấu vết, KHÔNG có nghĩa phòng không làm.
 * • Chạy thử 60 ngày: chỉ đo, không đưa vào thưởng/phạt.
 * • `diem = null` (ít / không có hồ sơ) thì hiện nhãn, KHÔNG BAO GIỜ tự quy ra 0 hay 100.
 * • Lệch dữ liệu không trừ điểm; vắng dấu vết không bao giờ bị gọi là lệch.
 * • Màu chỉ qua biến theme, không dùng --danger.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/components/ui/Toast';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import LineIcon from '@/components/ui/LineIcon';
import { Khoi, Thanh, Trong } from '@/components/dashboard/KhoiDashboard';
import {
  api, ApiError,
  DuLieuChung, DuLieuChungHoSo, DuLieuChungLech, DuLieuChungPhong, DuLieuChungThe,
  LanNhac, NhacDuLieuChungBody, NhacDuLieuChungKetQua, PhongDuLieu, TrangThaiHoSo,
} from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import {
  GIAI_DOAN_PHAN_LOAI, NHAN_KET_QUA, NHAN_LECH, NHAN_MUC, NHAN_TRANG_THAI, PHONG_DU_LIEU,
  TEN_PHONG, THU_TU_TRANG_THAI, VAI_TRO_DU_LIEU_CHUNG,
  baoLau, gioPhut, laHomNay, linkHoSo, mauMuc, mauTrangThai, ngayThang,
  nhanDauVet, nhanGiaiDoan, tomTatNhac,
} from '@/lib/du-lieu-chung';

// Phải khớp VAI_TRO_BGD ở backend và mục /du-lieu-chung trong Sidebar.
const DUOC_XEM = VAI_TRO_DU_LIEU_CHUNG;
const MOI_TRANG = 20;

const NUT = 'inline-flex items-center justify-center gap-1.5 min-h-[44px] px-4 rounded-full text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const NUT_CHINH = `${NUT} bg-[var(--gold-500)] text-[var(--surface-0)] hover:bg-[var(--gold-400)]`;
const NUT_PHU = `${NUT} border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]`;

const fmtSo = (n: number) => n.toLocaleString('vi-VN');

function mauPct(pct: number): string {
  if (pct >= 80) return 'var(--success)';
  if (pct >= 50) return 'var(--gold-500)';
  return 'var(--warning)';
}

function nhanLanNhac(n: LanNhac): string {
  const khi = laHomNay(n.luc) ? gioPhut(n.luc) : `${ngayThang(n.luc)} ${gioPhut(n.luc)}`;
  return `Đã nhắc ${khi} · ${n.da_xem ? 'đã xem' : 'chưa xem'}`;
}

type ChoXacNhan = { id: string; ma: string; stage: string; message: string; soViec: number };

export default function DuLieuChungPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [data, setData] = useState<DuLieuChung | null>(null);
  const [error, setError] = useState('');
  const [lanTai, setLanTai] = useState(0);
  const [dangTai, setDangTai] = useState(false);
  const [dangGui, setDangGui] = useState<string | null>(null);

  // Mục 5 — lọc + phân trang
  const [locPhong, setLocPhong] = useState<'' | PhongDuLieu>('');
  const [locVanDe, setLocVanDe] = useState('');
  const [trang, setTrang] = useState(1);
  const [soLech, setSoLech] = useState(MOI_TRANG);
  // Mục 4 — lọc lệch theo mã quy tắc (L1–L5), bấm từ thẻ phòng
  const [locLech, setLocLech] = useState('');

  // Mục 6 — dữ liệu cũ
  const [moCu, setMoCu] = useState(false);
  const [soCu, setSoCu] = useState(MOI_TRANG);
  const [tamDungId, setTamDungId] = useState<string | null>(null);
  const [lyDoTamDung, setLyDoTamDung] = useState('');
  const [choXacNhan, setChoXacNhan] = useState<ChoXacNhan | null>(null);

  const laAdmin = user?.role === 'admin';

  const taiLai = useCallback(() => {
    setDangTai(true);
    setLanTai(n => n + 1);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    // Backend chặn cứng ở BGĐ; chặn thêm ở đây để người khác không rơi vào trang trắng + 403.
    if (!DUOC_XEM.includes(user.role)) router.push('/');
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !DUOC_XEM.includes(user.role)) return;
    let huy = false;
    api.getDuLieuChung()
      .then(d => { if (!huy) { setData(d); setError(''); } })
      .catch(e => { if (!huy) setError(e instanceof Error ? e.message : 'Không tải được dữ liệu'); })
      .finally(() => { if (!huy) setDangTai(false); });
    return () => { huy = true; };
  }, [user, lanTai]);

  // ── Hành động ────────────────────────────────────────────────────────
  const baoKetQua = useCallback((kq: NhacDuLieuChungKetQua) => {
    const { chu, kieu } = tomTatNhac(kq);
    toast(chu, kieu);
  }, [toast]);

  const baoLoiNhac = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 429) {
      toast('Người nhận đã đủ 2 tin hôm nay — mai nhắc tiếp.', 'warning');
      return;
    }
    toast(e instanceof Error && e.message ? e.message : 'Không gửi được tin nhắc', 'error');
  }, [toast]);

  const nhac = useCallback(async (body: NhacDuLieuChungBody, khoa: string) => {
    setDangGui(khoa);
    try {
      baoKetQua(await api.nhacDuLieuChung(body));
      taiLai();
    } catch (e) {
      baoLoiNhac(e);
    } finally {
      setDangGui(null);
    }
  }, [baoKetQua, baoLoiNhac, taiLai]);

  /** Lệch: nhắc CẢ HAI phía liên quan, mỗi phòng một lượt. */
  const hoiLaiLech = useCallback(async (r: DuLieuChungLech) => {
    if (r.phong_lien_quan.length === 0) { toast('Hồ sơ này chưa gắn phòng nào để hỏi', 'warning'); return; }
    const khoa = `lech:${r.ma}:${r.id}`;
    setDangGui(khoa);
    const gop: NhacDuLieuChungKetQua = { da_gui: [], bo_qua: [] };
    try {
      for (const phong of r.phong_lien_quan) {
        try {
          const kq = await api.nhacDuLieuChung({ phong, id: r.id, loai: r.loai });
          gop.da_gui.push(...kq.da_gui);
          gop.bo_qua.push(...kq.bo_qua);
        } catch (e) {
          if (e instanceof ApiError && e.status === 429) gop.bo_qua.push({ phong, ly_do: 'vuot_2_tin' });
          else throw e;
        }
      }
      baoKetQua(gop);
      taiLai();
    } catch (e) {
      baoLoiNhac(e);
    } finally {
      setDangGui(null);
    }
  }, [baoKetQua, baoLoiNhac, taiLai, toast]);

  /** Đổi giai đoạn qua PUT /projects/{id}/stage có sẵn — chỉ admin (backend chặn executive). */
  const doiGiaiDoan = useCallback(async (id: string, ma: string, stage: string, opts?: { force?: boolean; lyDo?: string }) => {
    setDangGui(`stage:${id}`);
    try {
      if (stage === 'paused') {
        await api.request(`/projects/${id}/stage`, { method: 'PUT', body: { stage: 'paused', pause_reason: opts?.lyDo || null } });
      } else {
        await api.updateProjectStage(id, stage, !!opts?.force);
      }
      toast(`Đã chuyển ${ma} sang «${stage === 'paused' ? 'Tạm dừng' : nhanGiaiDoan(stage)}»`, 'success');
      setTamDungId(null);
      setLyDoTamDung('');
      taiLai();
    } catch (e) {
      if (!opts?.force && e instanceof ApiError && e.status === 409 && e.data?.code === 'con_viec_mo') {
        const viec = e.data?.tasks;
        const ds = Array.isArray(viec) ? viec : [];
        setChoXacNhan({ id, ma, stage, message: e.message, soViec: ds.length });
        return;
      }
      toast(e instanceof Error && e.message ? e.message : 'Không đổi được giai đoạn', 'error');
    } finally {
      setDangGui(null);
    }
  }, [taiLai, toast]);

  // ── Dữ liệu dẫn xuất ─────────────────────────────────────────────────
  const nhanQuyTac = useMemo(() => {
    const m: Record<string, string> = {};
    for (const p of data?.phong || []) for (const q of p.quy_tac) m[q.ma] = q.nhan;
    return m;
  }, [data]);

  const tuyChonVanDe = useMemo(() => {
    const thieu = new Set<string>();
    for (const r of data?.can_xem || []) for (const t of r.thieu) thieu.add(t);
    return [
      ...(['lech', 'chua_ro', 'chua_cap_nhat'] as TrangThaiHoSo[]).map(t => ({ gt: `trang_thai:${t}`, nhan: NHAN_TRANG_THAI[t] })),
      ...[...thieu].sort().map(t => ({ gt: `thieu:${t}`, nhan: `Thiếu: ${nhanQuyTac[t] || t}` })),
    ];
  }, [data, nhanQuyTac]);

  const canXemLoc = useMemo(() => {
    let ds = data?.can_xem || [];
    if (locPhong) ds = ds.filter(r => r.phong_giu === locPhong);
    if (locVanDe.startsWith('trang_thai:')) {
      const t = locVanDe.slice('trang_thai:'.length);
      ds = ds.filter(r => r.trang_thai === t);
    } else if (locVanDe.startsWith('thieu:')) {
      const t = locVanDe.slice('thieu:'.length);
      ds = ds.filter(r => r.thieu.includes(t));
    }
    return ds;
  }, [data, locPhong, locVanDe]);

  const soTrang = Math.max(1, Math.ceil(canXemLoc.length / MOI_TRANG));
  const trangHienTai = Math.min(trang, soTrang);
  const canXemTrang = canXemLoc.slice((trangHienTai - 1) * MOI_TRANG, trangHienTai * MOI_TRANG);

  const lechLoc = useMemo(
    () => (locLech ? (data?.lech || []).filter(r => r.ma === locLech) : (data?.lech || [])),
    [data, locLech],
  );

  /** Quy tắc loại «lệch» (L1–L5) không nằm trong «Hồ sơ cần xem» theo phòng → nhảy tới mục Lệch, lọc theo mã. */
  const moLech = (ma: string) => {
    setLocLech(ma);
    setSoLech(MOI_TRANG);
    document.getElementById('lech-du-lieu')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const moMucCanXem = (phong: PhongDuLieu, vanDe: string) => {
    setLocPhong(phong);
    setLocVanDe(vanDe);
    setTrang(1);
    document.getElementById('ho-so-can-xem')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // ── Hiển thị ─────────────────────────────────────────────────────────
  if (loading || (!data && !error)) return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="skeleton h-8 w-64 max-w-full rounded-xl" />
      <div className="skeleton h-16 w-full rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map(i => <div key={i} className="glass-card p-5"><div className="skeleton h-20 w-full rounded-xl" /></div>)}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1, 2, 3, 4].map(i => <div key={i} className="glass-card p-5"><div className="skeleton h-40 w-full rounded-xl" /></div>)}
      </div>
    </div>
  );

  if (!user || !DUOC_XEM.includes(user.role)) return null;

  // Ngày kết thúc lấy từ backend (chay_thu_ngay cấu hình được), không tự cộng ở giao diện.
  const ketThucChayThu = data ? ngayThang(data.chay_thu_den) : '';

  return (
    <div className="p-4 sm:p-6 space-y-6 animate-in overflow-x-hidden">
      {/* ── 0. Đầu trang ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">
            Dữ liệu <span className="gold-gradient">chung</span>
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            CRM có đang phản ánh đúng công việc thật của từng phòng không.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <span className="text-xs text-[var(--text-muted)]">Cập nhật {gioPhut(data.cap_nhat_luc)}</span>
          )}
          <button type="button" onClick={taiLai} disabled={dangTai} className={NUT_PHU}>
            <LineIcon name="refresh" size={14} color="currentColor" />
            {dangTai ? 'Đang tải…' : 'Làm mới'}
          </button>
        </div>
      </div>

      <div className="px-4 py-3 rounded-2xl text-xs flex items-start gap-2 leading-relaxed"
        style={{ background: 'var(--info-bg)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
        <LineIcon name="info" size={16} color="var(--info)" className="mt-0.5" />
        <p>
          {data?.chay_thu && <><b className="text-[var(--text-primary)]">Chạy thử đến {ketThucChayThu}</b>: chỉ đo, không tính thưởng/phạt. </>}
          «Chưa cập nhật» = CRM chưa có dấu vết, <b className="text-[var(--text-primary)]">KHÔNG</b> có nghĩa là không làm.
        </p>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-2xl text-sm" style={{ background: 'var(--warning-bg)', border: '1px solid var(--border-default)', color: 'var(--warning)' }}>
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="glass-card p-5">
            {data.phan_anh.pct === null || data.phan_anh.tong === 0 ? (
              <p className="text-lg font-semibold">Chưa có dự án đang chạy để đo.</p>
            ) : (
              <p className="text-lg sm:text-xl font-semibold leading-snug">
                CRM phản ánh thực tế <span className="gold-gradient text-3xl font-bold align-baseline">{data.phan_anh.pct}%</span>{' '}
                của {fmtSo(data.phan_anh.tong)} dự án đang chạy
              </p>
            )}
            <p className="text-[11px] text-[var(--text-muted)] mt-2">
              {fmtSo(data.phan_anh.dat)}/{fmtSo(data.phan_anh.tong)} dự án có dấu vết trong hạn của phòng đang giữ, hoặc được trưởng phòng xác nhận «Đúng» trong {data.cau_hinh.ngay_doi_chieu} ngày. Tính cả dự án cũ chưa xếp giai đoạn.
            </p>
          </div>

          {/* ── 1. Hôm nay ───────────────────────────────────────────── */}
          <Khoi tieuDe="Hôm nay" phu="Tối đa 3 việc nên làm ngay — mỗi việc 1 chạm.">
            {data.hom_nay.length === 0 ? <Trong chu="Hôm nay chưa có việc gì cần nhắc." /> : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {data.hom_nay.slice(0, 3).map(t => (
                  <TheHomNay key={t.ma} the={t} dangGui={dangGui === `the:${t.ma}`}
                    onBam={() => {
                      if (t.nut.hanh_dong === 'mo') { if (t.nut.link) router.push(t.nut.link); return; }
                      const phong = t.nut.hanh_dong === 'nhac_chua_xep' ? 'chua_xep' : (t.nut.phong || t.phong);
                      if (!phong) return;
                      void nhac({ phong }, `the:${t.ma}`);
                    }} />
                ))}
              </div>
            )}
          </Khoi>

          {/* ── 2. Dải quy trình ─────────────────────────────────────── */}
          <Khoi tieuDe="Dải quy trình" phu="Số hồ sơ đang ở từng chặng. Tổng tiền chỉ cộng hồ sơ đã có giá trị. Chấm màu = mức phản ánh của phòng giữ chặng.">
            <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory -mx-5 px-5 pb-2 md:mx-0 md:px-0 md:grid md:grid-cols-7 md:overflow-visible">
              {data.dai_quy_trinh.map(o => (
                <div key={o.ma} className="snap-start shrink-0 w-[44%] min-w-[136px] md:w-auto md:min-w-0 rounded-2xl p-3"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center gap-1.5">
                    <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: mauMuc(o.muc) }}
                      title={o.muc ? NHAN_MUC[o.muc] : 'Không chấm'} />
                    <span className="text-[11px] text-[var(--text-muted)] truncate">{o.nhan}</span>
                  </div>
                  <p className="text-2xl font-bold mt-1">{fmtSo(o.so_luong)}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{o.so_co_gia_tri > 0 ? formatCurrency(o.tong_tien) : '—'}</p>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">có giá trị {fmtSo(o.so_co_gia_tri)}/{fmtSo(o.so_luong)}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <span className="badge text-[11px] px-3 py-1.5 rounded-full" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                Chưa xếp giai đoạn <b className="text-[var(--text-primary)]">{fmtSo(data.ngoai_dai.chua_xep.so_luong)}</b>
                {data.ngoai_dai.chua_xep.da_xep_tu_moc > 0 && <> · đã xếp {fmtSo(data.ngoai_dai.chua_xep.da_xep_tu_moc)} từ khi chạy</>}
              </span>
              <span className="badge text-[11px] px-3 py-1.5 rounded-full" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                Tạm dừng <b className="text-[var(--text-primary)]">{fmtSo(data.ngoai_dai.tam_dung.so_luong)}</b> (có lý do {fmtSo(data.ngoai_dai.tam_dung.co_ly_do)})
              </span>
              {data.ngoai_dai.lead_treo > 0 && (
                <span className="badge text-[11px] px-3 py-1.5 rounded-full" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
                  title={`Lead quá ${data.cau_hinh.lead_treo_ngay} ngày không có hoạt động — không tính vào độ tươi`}>
                  Lead treo <b className="text-[var(--text-primary)]">{fmtSo(data.ngoai_dai.lead_treo)}</b>
                </span>
              )}
            </div>
          </Khoi>

          {/* ── 3. 4 thẻ phòng ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.phong.map(p => (
              <ThePhong key={p.ma} phong={p} ngayDoiChieu={data.cau_hinh.ngay_doi_chieu}
                dangGui={dangGui === `phong:${p.ma}`}
                onNhac={() => void nhac({ phong: p.ma }, `phong:${p.ma}`)}
                onMoVanDe={vanDe => moMucCanXem(p.ma, vanDe)}
                onMoLech={moLech} />
            ))}
          </div>

          {/* ── 4. Lệch dữ liệu ──────────────────────────────────────── */}
          <Khoi id="lech-du-lieu" tieuDe={`Lệch dữ liệu (${fmtSo(lechLoc.length)})`}
            phu="CRM ghi một đằng, bằng chứng trong hệ thống nói một nẻo. Không trừ điểm — «Hỏi lại» nhắc cả hai phía liên quan.">
            {locLech && (
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-[11px] text-[var(--text-secondary)]">Đang lọc: <b className="text-[var(--text-primary)]">{NHAN_LECH[locLech] || locLech}</b></span>
                <button type="button" className={NUT_PHU} onClick={() => { setLocLech(''); setSoLech(MOI_TRANG); }}>Bỏ lọc</button>
              </div>
            )}
            {lechLoc.length === 0 ? <Trong chu={locLech ? 'Không còn hồ sơ nào lệch theo quy tắc này.' : 'Chưa thấy chỗ nào lệch.'} /> : (
              <>
                <ul className="space-y-2">
                  {lechLoc.slice(0, soLech).map(r => (
                    <li key={`${r.ma}:${r.id}`} className="rounded-2xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex items-start gap-2">
                        <LineIcon name="alert" size={16} color="var(--warning)" className="mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-[var(--text-primary)]">
                            {NHAN_LECH[r.ma] || r.ma}{r.ma_ho_so && <span className="text-[var(--text-muted)] font-normal"> · {r.ma_ho_so}</span>}
                          </p>
                          <p className="text-[11px] text-[var(--text-muted)] truncate">{r.ten}</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 mt-2 text-[11px] leading-snug">
                        <div className="rounded-xl p-2 min-w-0 break-words" style={{ background: 'var(--surface-3)' }}>
                          <span className="block text-[var(--text-muted)]">CRM</span>
                          <span className="text-[var(--text-primary)]">{r.crm_ghi}</span>
                        </div>
                        <div className="rounded-xl p-2 min-w-0 break-words" style={{ background: 'var(--surface-3)' }}>
                          <span className="block text-[var(--text-muted)]">Bằng chứng</span>
                          <span className="text-[var(--text-primary)]">{r.bang_chung}</span>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2 mt-2">
                        {r.phong_lien_quan.length > 0 && (
                          <span className="text-[10px] text-[var(--text-muted)] mr-auto">
                            {r.phong_lien_quan.map(ph => TEN_PHONG[ph] || ph).join(' · ')}
                          </span>
                        )}
                        <button type="button" className={NUT_PHU} disabled={dangGui === `lech:${r.ma}:${r.id}`}
                          onClick={() => void hoiLaiLech(r)}>
                          <LineIcon name="send" size={14} color="currentColor" /> Hỏi lại
                        </button>
                        <Link href={linkHoSo(r.loai, r.id)} className={NUT_PHU}>
                          <LineIcon name="eye" size={14} color="currentColor" /> Mở
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
                {lechLoc.length > soLech && (
                  <button type="button" className={`${NUT_PHU} w-full mt-3`} onClick={() => setSoLech(n => n + MOI_TRANG)}>
                    Xem thêm ({fmtSo(lechLoc.length - soLech)})
                  </button>
                )}
              </>
            )}
          </Khoi>

          {/* ── 5. Hồ sơ cần xem ─────────────────────────────────────── */}
          <Khoi id="ho-so-can-xem" tieuDe={`Hồ sơ cần xem (${fmtSo(canXemLoc.length)})`}
            phu="Thứ tự: lệch → chưa rõ mà giá trị cao → thiếu thông tin.">
            <div className="flex flex-wrap gap-2 mb-3">
              <select aria-label="Lọc theo phòng" value={locPhong}
                onChange={e => { setLocPhong(e.target.value as '' | PhongDuLieu); setTrang(1); }}
                className="input text-xs min-h-[44px] flex-1 min-w-[140px]">
                <option value="">Mọi phòng</option>
                {PHONG_DU_LIEU.map(p => <option key={p} value={p}>{TEN_PHONG[p]}</option>)}
              </select>
              <select aria-label="Lọc theo loại vấn đề" value={locVanDe}
                onChange={e => { setLocVanDe(e.target.value); setTrang(1); }}
                className="input text-xs min-h-[44px] flex-1 min-w-[140px]">
                <option value="">Mọi vấn đề</option>
                {tuyChonVanDe.map(o => <option key={o.gt} value={o.gt}>{o.nhan}</option>)}
              </select>
              {(locPhong || locVanDe) && (
                <button type="button" className={NUT_PHU} onClick={() => { setLocPhong(''); setLocVanDe(''); setTrang(1); }}>
                  Bỏ lọc
                </button>
              )}
            </div>
            {canXemTrang.length === 0 ? <Trong chu="Không có hồ sơ nào khớp bộ lọc." /> : (
              <ul className="space-y-2">
                {canXemTrang.map(r => (
                  <DongCanXem key={`${r.loai}:${r.id}`} r={r} nhanQuyTac={nhanQuyTac}
                    dangGui={dangGui === `hs:${r.id}`}
                    onHoiLai={() => { if (r.phong_giu) void nhac({ phong: r.phong_giu, id: r.id, loai: r.loai }, `hs:${r.id}`); }} />
                ))}
              </ul>
            )}
            {soTrang > 1 && (
              <div className="flex items-center justify-between gap-2 mt-3">
                <button type="button" className={NUT_PHU} disabled={trangHienTai <= 1} onClick={() => setTrang(trangHienTai - 1)}>Trước</button>
                <span className="text-xs text-[var(--text-muted)]">Trang {trangHienTai}/{soTrang}</span>
                <button type="button" className={NUT_PHU} disabled={trangHienTai >= soTrang} onClick={() => setTrang(trangHienTai + 1)}>Sau</button>
              </div>
            )}
          </Khoi>

          {/* ── 6. Dữ liệu cũ chờ phân loại ──────────────────────────── */}
          <section className="glass-card p-5">
            <button type="button" onClick={() => setMoCu(v => !v)} aria-expanded={moCu}
              className="flex w-full items-center justify-between gap-3 min-h-[44px] text-left">
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-[var(--text-primary)]">Dữ liệu cũ chờ phân loại ({fmtSo(data.du_lieu_cu.length)})</span>
                <span className="block text-[11px] text-[var(--text-muted)] mt-0.5">Dự án nhập từ hệ thống cũ chưa có giai đoạn — không tính vào điểm phòng nào.</span>
              </span>
              <LineIcon name="chevronDown" size={18} color="var(--text-muted)" className={moCu ? 'rotate-180 transition-transform' : 'transition-transform'} />
            </button>
            {moCu && (
              <div className="mt-3">
                {!laAdmin && (
                  <p className="text-[11px] text-[var(--text-muted)] mb-2">Chỉ tài khoản quản trị phân loại được (quyền đổi giai đoạn dự án). Trưởng phòng có thể tự nhận dự án về phòng ở trang Đối chiếu.</p>
                )}
                {data.du_lieu_cu.length === 0 ? <Trong chu="Đã phân loại hết dữ liệu cũ." /> : (
                  <ul className="space-y-2">
                    {data.du_lieu_cu.slice(0, soCu).map(r => (
                      <li key={r.id} className="rounded-2xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{r.ma} · {r.ten}</p>
                            <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                              {r.goi_y_giai_doan ? <>Gợi ý: <b className="text-[var(--gold-500)]">{nhanGiaiDoan(r.goi_y_giai_doan)}</b></> : 'Không suy ra được'}
                              {r.ly_do_goi_y && <> — {r.ly_do_goi_y}</>}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {r.gia_tri ? <span className="text-xs text-[var(--text-secondary)]">{formatCurrency(r.gia_tri)}</span> : null}
                            <Link href={linkHoSo('du_an', r.id)} aria-label={`Mở ${r.ma}`}
                              className="inline-flex items-center justify-center w-11 h-11 rounded-full border border-[var(--border-default)]">
                              <LineIcon name="eye" size={16} color="var(--text-secondary)" />
                            </Link>
                          </div>
                        </div>
                        {laAdmin && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {GIAI_DOAN_PHAN_LOAI.map(s => {
                              const goiY = s === r.goi_y_giai_doan;
                              return (
                                <button key={s} type="button" disabled={dangGui === `stage:${r.id}`}
                                  onClick={() => {
                                    if (s === 'paused') { setTamDungId(r.id); setLyDoTamDung(''); return; }
                                    void doiGiaiDoan(r.id, r.ma, s);
                                  }}
                                  className="min-h-[44px] px-3 rounded-full text-[11px] font-medium transition-colors disabled:opacity-50"
                                  style={goiY
                                    ? { background: 'var(--gold-500)', color: 'var(--surface-0)' }
                                    : { background: 'var(--surface-3)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
                                  {s === 'paused' ? 'Tạm dừng' : nhanGiaiDoan(s)}
                                </button>
                              );
                            })}
                          </div>
                        )}
                        {laAdmin && tamDungId === r.id && (
                          <div className="flex flex-wrap gap-2 mt-2">
                            <input className="input text-xs min-h-[44px] flex-1 min-w-[160px]" placeholder="Lý do tạm dừng (bắt buộc)"
                              value={lyDoTamDung} onChange={e => setLyDoTamDung(e.target.value)} aria-label="Lý do tạm dừng" />
                            <button type="button" className={NUT_CHINH} disabled={!lyDoTamDung.trim() || dangGui === `stage:${r.id}`}
                              onClick={() => void doiGiaiDoan(r.id, r.ma, 'paused', { lyDo: lyDoTamDung.trim() })}>Lưu</button>
                            <button type="button" className={NUT_PHU} onClick={() => setTamDungId(null)}>Huỷ</button>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {data.du_lieu_cu.length > soCu && (
                  <button type="button" className={`${NUT_PHU} w-full mt-3`} onClick={() => setSoCu(n => n + MOI_TRANG)}>
                    Xem thêm ({fmtSo(data.du_lieu_cu.length - soCu)})
                  </button>
                )}
              </div>
            )}
          </section>

          {/* ── Đã xong chờ BGĐ ──────────────────────────────────────── */}
          <Khoi tieuDe={`Đã xong chờ BGĐ (${fmtSo(data.cho_bgd.length)})`}
            phu="Trưởng phòng báo «Đã xong» khi đối chiếu. Hệ thống không tự đóng — BGĐ bấm «Hoàn thành».">
            {data.cho_bgd.length === 0 ? <Trong chu="Chưa có hồ sơ nào chờ đóng." /> : (
              <ul className="space-y-2">
                {data.cho_bgd.map(r => (
                  <li key={r.id} className="rounded-2xl p-3 flex flex-wrap items-center gap-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{r.ma}{r.khach ? ` · ${r.khach}` : ''}</p>
                      <p className="text-[11px] text-[var(--text-muted)]">Báo xong{r.boi ? ` bởi ${r.boi}` : ''} · {ngayThang(r.luc)}</p>
                    </div>
                    <Link href={linkHoSo('du_an', r.id)} className={NUT_PHU}>Mở</Link>
                    {laAdmin ? (
                      <button type="button" className={NUT_CHINH} disabled={dangGui === `stage:${r.id}`}
                        onClick={() => void doiGiaiDoan(r.id, r.ma, 'completed')}>
                        <LineIcon name="check" size={14} color="currentColor" /> Hoàn thành
                      </button>
                    ) : (
                      <span className="text-[10px] text-[var(--text-muted)]">Chỉ quản trị đóng được</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Khoi>

          {/* ── 7. Tín hiệu hệ thống 30 ngày ─────────────────────────── */}
          <footer className="text-[11px] leading-relaxed text-[var(--text-muted)] px-1 pb-4">
            <p className="font-semibold text-[var(--text-tertiary)] mb-1">Tín hiệu hệ thống 30 ngày</p>
            <p>
              {fmtSo(data.tin_hieu_30_ngay.task_activities)} báo cáo việc
              {' · '}{fmtSo(data.tin_hieu_30_ngay.anh)} ảnh / {fmtSo(data.tin_hieu_30_ngay.du_an_co_anh)} dự án có ảnh
              {' · '}việc xong: Thiết kế {fmtSo(data.tin_hieu_30_ngay.viec_xong.design)}, Báo giá {fmtSo(data.tin_hieu_30_ngay.viec_xong.quotation)}, Thu mua {fmtSo(data.tin_hieu_30_ngay.viec_xong.procurement)}, Thi công {fmtSo(data.tin_hieu_30_ngay.viec_xong.construction)}, Bàn giao {fmtSo(data.tin_hieu_30_ngay.viec_xong.acceptance)}
              {' · '}{fmtSo(data.tin_hieu_30_ngay.phieu_vat_tu)} phiếu vật tư
              {' · '}{fmtSo(data.tin_hieu_30_ngay.bao_gia)} báo giá
              {' · '}{fmtSo(data.tin_hieu_30_ngay.hd_da_ky)} HĐ đã ký.
            </p>
            <p className="mt-1">
              Báo cáo việc gần nhất: {data.tin_hieu_30_ngay.lan_cuoi.task_activity ? ngayThang(data.tin_hieu_30_ngay.lan_cuoi.task_activity) : 'chưa có'}
              {' · '}ảnh gần nhất: {data.tin_hieu_30_ngay.lan_cuoi.anh ? ngayThang(data.tin_hieu_30_ngay.lan_cuoi.anh) : 'chưa có'}.
              {' '}Phòng nào ít tín hiệu thì nhiều mục xám — CRM chưa nhận dấu vết, không phải phòng không làm.
            </p>
          </footer>
        </>
      )}

      <ConfirmDialog
        open={!!choXacNhan}
        title="Còn việc chưa xong"
        // force=true chỉ bỏ qua bước kiểm việc mở — backend KHÔNG đóng các việc đó.
        // Danh sách việc backend trả có thể bị cắt ngắn → chỉ ghi số khi chắc chắn đủ.
        message={choXacNhan
          ? `${choXacNhan.message}\n\nVẫn hoàn thành dù còn ${choXacNhan.soViec > 0 && choXacNhan.soViec < 5 ? `${choXacNhan.soViec} ` : ''}việc mở? Các việc này không tự đóng.`
          : ''}
        confirmLabel="Vẫn hoàn thành"
        variant="warning"
        onCancel={() => setChoXacNhan(null)}
        onConfirm={() => {
          const c = choXacNhan;
          setChoXacNhan(null);
          if (c) void doiGiaiDoan(c.id, c.ma, c.stage, { force: true });
        }}
      />
    </div>
  );
}

// ── Thẻ «Hôm nay» ──────────────────────────────────────────────────────
function TheHomNay({ the, dangGui, onBam }: { the: DuLieuChungThe; dangGui: boolean; onBam: () => void }) {
  const daNhac = the.da_nhac;
  // Nút «mở» (vd. sau khi đã nhắc: «Xem dữ liệu cũ») luôn hiện; chỉ nút NHẮC mới ẩn khi đã nhắc.
  const hienNut = the.nut.hanh_dong === 'mo' || !daNhac;
  return (
    <div className="rounded-2xl p-4 flex flex-col gap-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
      <p className="text-xs text-[var(--text-secondary)] leading-snug">{the.tieu_de}</p>
      <p className="text-3xl font-bold">{fmtSo(the.so_luong)}</p>
      {daNhac && (
        <p className="text-[11px] text-[var(--text-muted)] min-h-[44px] flex items-center gap-1.5">
          <LineIcon name="check" size={14} color="var(--success)" /> {nhanLanNhac(daNhac)}
        </p>
      )}
      {hienNut && (
        <button type="button" className={NUT_CHINH} disabled={dangGui} onClick={onBam}>
          {dangGui ? 'Đang gửi…' : the.nut.nhan}
        </button>
      )}
    </div>
  );
}

// ── Thẻ phòng ──────────────────────────────────────────────────────────
function DongThanhPhan({ nhan, dat, tong, chuaBatDau }: { nhan: string; dat: number; tong: number; chuaBatDau?: boolean }) {
  if (chuaBatDau) {
    return (
      <div>
        <div className="flex justify-between text-[11px]"><span className="text-[var(--text-secondary)]">{nhan}</span><span className="text-[var(--text-muted)]">Chưa bắt đầu đối chiếu</span></div>
        <Thanh pct={0} mau="var(--text-disabled)" cao={4} />
      </div>
    );
  }
  if (tong <= 0) {
    return (
      <div>
        <div className="flex justify-between text-[11px]"><span className="text-[var(--text-secondary)]">{nhan}</span><span className="text-[var(--text-muted)]">Không áp dụng</span></div>
        <Thanh pct={0} mau="var(--text-disabled)" cao={4} />
      </div>
    );
  }
  const pct = Math.round((dat / tong) * 100);
  return (
    <div>
      <div className="flex justify-between text-[11px]">
        <span className="text-[var(--text-secondary)]">{nhan}</span>
        <span className="text-[var(--text-muted)]">{fmtSo(dat)}/{fmtSo(tong)} · <b style={{ color: mauPct(pct) }}>{pct}%</b></span>
      </div>
      <Thanh pct={pct} mau={mauPct(pct)} cao={4} />
    </div>
  );
}

function ThePhong({ phong: p, ngayDoiChieu, dangGui, onNhac, onMoVanDe, onMoLech }: {
  phong: DuLieuChungPhong; ngayDoiChieu: number; dangGui: boolean;
  onNhac: () => void; onMoVanDe: (vanDe: string) => void; onMoLech: (ma: string) => void;
}) {
  const loiLon = [...p.quy_tac]
    .map(q => ({ ...q, thieu: q.tong - q.dat }))
    .filter(q => q.thieu > 0)
    .sort((a, b) => b.thieu - a.thieu)
    .slice(0, 2);
  const nhacHomNay = !!p.lan_nhac_cuoi && laHomNay(p.lan_nhac_cuoi.luc);
  const khongCoTP = p.truong_phong.length === 0;

  return (
    <section className="glass-card p-5 flex flex-col gap-3 min-w-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{p.ten || TEN_PHONG[p.ma]}</h2>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            {khongCoTP ? 'Chưa có trưởng phòng' : p.truong_phong.map(t => `${t.ten}${t.co_telegram ? '' : ' (chưa liên kết Telegram)'}`).join(', ')}
            {' · '}{fmtSo(p.so_ho_so)} hồ sơ
          </p>
        </div>
        <div className="text-right shrink-0">
          {p.diem !== null ? (
            <p className="text-2xl font-bold leading-none" style={{ color: mauMuc(p.muc) }}>{p.diem}</p>
          ) : null}
          <p className="text-[11px] font-semibold mt-1" style={{ color: mauMuc(p.muc) }}>{NHAN_MUC[p.muc] || p.muc}</p>
        </div>
      </div>

      <div className="space-y-2">
        <DongThanhPhan nhan="Đủ thông tin" dat={p.thanh_phan.du.dat} tong={p.thanh_phan.du.tong} />
        <DongThanhPhan nhan="Tươi (có dấu vết trong hạn)" dat={p.thanh_phan.tuoi.dat} tong={p.thanh_phan.tuoi.tong} />
        <DongThanhPhan nhan={`Đối chiếu (${ngayDoiChieu} ngày)`} dat={p.thanh_phan.doi_chieu.dat} tong={p.thanh_phan.doi_chieu.tong}
          chuaBatDau={!p.thanh_phan.doi_chieu.ap_dung} />
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
        {THU_TU_TRANG_THAI.map(t => (
          <span key={t} className="inline-flex items-center gap-1 text-[var(--text-muted)]">
            <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: mauTrangThai(t) }} />
            {NHAN_TRANG_THAI[t].toLowerCase()} <b className="text-[var(--text-secondary)]">{fmtSo(p.trang_thai?.[t] ?? 0)}</b>
          </span>
        ))}
      </div>

      {(loiLon.length > 0 || p.tre_han > 0) && (
        <div className="flex flex-col gap-1.5">
          {loiLon.map(q => (
            <button key={q.ma} type="button"
              onClick={() => (q.loai === 'lech' ? onMoLech(q.ma) : onMoVanDe(`thieu:${q.ma}`))}
              className="flex items-center justify-between gap-2 min-h-[44px] px-3 rounded-xl text-left text-xs transition-colors hover:bg-[var(--surface-3)]"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
              <span className="min-w-0 truncate text-[var(--text-secondary)]">{q.nhan}</span>
              <span className="shrink-0 font-semibold text-[var(--warning)]">{fmtSo(q.thieu)}/{fmtSo(q.tong)}</span>
            </button>
          ))}
          {p.tre_han > 0 && (
            <p className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)] px-1">
              <LineIcon name="hourglass" size={13} color="var(--warning)" /> Đang trễ hạn bàn giao <b className="text-[var(--text-secondary)]">{fmtSo(p.tre_han)}</b> (theo dõi riêng, không vào điểm)
            </p>
          )}
        </div>
      )}

      <p className="text-[11px] text-[var(--text-muted)]">
        {p.dau_vet_gan_nhat
          ? <>Dấu vết gần nhất: {baoLau(p.dau_vet_gan_nhat.luc)} · {nhanDauVet(p.dau_vet_gan_nhat.loai)}{p.dau_vet_gan_nhat.nguoi ? ` · ${p.dau_vet_gan_nhat.nguoi}` : ''}</>
          : 'Chưa có dấu vết nào trên CRM'}
      </p>

      <div className="flex flex-wrap items-center gap-2 mt-auto">
        <button type="button" className={NUT_CHINH} disabled={khongCoTP || nhacHomNay || dangGui} onClick={onNhac}>
          <LineIcon name="send" size={14} color="currentColor" />
          {dangGui ? 'Đang gửi…' : 'Nhắc trưởng phòng'}
        </button>
        <span className="text-[11px] text-[var(--text-muted)]">
          {khongCoTP ? 'Chưa có ai để nhắc' : p.lan_nhac_cuoi ? nhanLanNhac(p.lan_nhac_cuoi) : 'Chưa nhắc lần nào'}
        </span>
      </div>
    </section>
  );
}

// ── Dòng «Hồ sơ cần xem» ───────────────────────────────────────────────
function DongCanXem({ r, nhanQuyTac, dangGui, onHoiLai }: {
  r: DuLieuChungHoSo; nhanQuyTac: Record<string, string>; dangGui: boolean; onHoiLai: () => void;
}) {
  return (
    <li className="rounded-2xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
            {r.ma ? `${r.ma} · ` : ''}{r.ten}{r.khach && r.khach !== r.ten ? <span className="font-normal text-[var(--text-muted)]"> · {r.khach}</span> : null}
          </p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            {r.loai === 'lead' ? 'Lead' : 'Dự án'} · {nhanGiaiDoan(r.giai_doan)}
            {r.phong_giu ? ` · ${TEN_PHONG[r.phong_giu]}` : ''}
            {r.gia_tri ? ` · ${formatCurrency(r.gia_tri)}` : ''}
          </p>
        </div>
        <span className="shrink-0 text-[10px] font-semibold px-2 py-1 rounded-full"
          style={{ color: mauTrangThai(r.trang_thai), background: 'var(--surface-3)' }}>
          {NHAN_TRANG_THAI[r.trang_thai] || r.trang_thai}
        </span>
      </div>
      {r.thieu.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {r.thieu.map(t => (
            <span key={t} className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>
              {nhanQuyTac[t] || t}
            </span>
          ))}
        </div>
      )}
      <p className="text-[11px] text-[var(--text-muted)] mt-2">
        {r.dau_vet_cuoi
          ? <>Dấu vết cuối: {baoLau(r.dau_vet_cuoi.luc)} · {nhanDauVet(r.dau_vet_cuoi.loai)}{r.dau_vet_cuoi.nguoi ? ` · ${r.dau_vet_cuoi.nguoi}` : ''}</>
          : 'Chưa có dấu vết'}
        {' · '}
        {r.doi_chieu_cuoi
          ? <>Đối chiếu cuối: {ngayThang(r.doi_chieu_cuoi.luc)}{r.doi_chieu_cuoi.ket_qua ? ` · ${NHAN_KET_QUA[r.doi_chieu_cuoi.ket_qua] || r.doi_chieu_cuoi.ket_qua}` : ''}</>
          : 'Chưa đối chiếu'}
      </p>
      <div className="flex flex-wrap justify-end gap-2 mt-2">
        <button type="button" className={NUT_PHU} disabled={!r.phong_giu || r.da_hoi_hom_nay || dangGui} onClick={onHoiLai}>
          <LineIcon name="send" size={14} color="currentColor" />
          {r.da_hoi_hom_nay ? 'Đã hỏi hôm nay' : dangGui ? 'Đang gửi…' : 'Hỏi lại'}
        </button>
        <Link href={linkHoSo(r.loai, r.id)} className={NUT_PHU}>
          <LineIcon name="eye" size={14} color="currentColor" /> Mở
        </Link>
      </div>
    </li>
  );
}
