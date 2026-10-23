'use client';

/**
 * Cài đặt › Nhân sự › Chế độ thưởng (23/10/2026).
 *
 * • 5 chương trình bật/tắt riêng, mỗi cái chọn chu kỳ Tháng/Quý: Hũ doanh số, Chuyên cần,
 *   Phản hồi khách, Khách hàng đánh giá, Ngôi sao quý.
 * • Điểm JAMA = trọng số theo phòng → hệ số nhân phần hũ.
 * • Lưu = phiên bản mới, áp từ KỲ SAU (lần lưu đầu áp ngay kỳ này); lịch sử giữ lại.
 * • Tab «Bảng thưởng»: xem thử từng người, đánh dấu kỷ luật, chốt kỳ → Bonus chờ duyệt.
 * Admin sửa; Kế toán xem + chốt. Mọi con số do backend tính (services/che_do_thuong.py).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { useToast } from '@/components/ui/Toast';
import { api, CdtBang, CdtCauHinh, CdtCauHinhResp, CdtChuKy } from '@/lib/api';
import { DEPARTMENT_LABELS } from '@/lib/labels';
import { tien } from '@/lib/tien-gon';

const VAI_XEM = ['admin', 'accountant'];
const PHONG_TRONG_SO = ['SALES', 'DESIGN', 'OPS', 'PM', '_khac'];
const THANH_PHAN: { ma: string; nhan: string }[] = [
  { ma: 'doanh_so', nhan: 'Doanh số' },
  { ma: 'chuyen_can', nhan: 'Chuyên cần' },
  { ma: 'phan_hoi', nhan: 'Phản hồi' },
  { ma: 'danh_gia', nhan: 'Đánh giá' },
];
const MOC_DANH_GIA: Record<string, string> = {
  ky_hd_tk: 'Ký HĐ thiết kế', chot_ban_ve: 'Chốt bản vẽ', ban_giao: 'Bàn giao', sau_3_thang: 'Sau 3 tháng',
};

const tenPhong = (p: string) => (p === '_khac' ? 'Phòng khác' : DEPARTMENT_LABELS[p] || p);

function kyHienTai() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
function kyLech(ky: string, n: number) {
  const [y, m] = ky.split('-').map(Number);
  const t = new Date(y, m - 1 + n, 1);
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}`;
}
const nhanKy = (ky: string) => `T${Number(ky.slice(5))}/${ky.slice(0, 4)}`;

// ── Ô nhập nhỏ ──────────────────────────────────────────────────────────────

function Cong({ bat, doi, khoa }: { bat: boolean; doi: (v: boolean) => void; khoa?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={bat} disabled={khoa} onClick={() => doi(!bat)}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 disabled:opacity-60 ${bat ? 'bg-[#C9A96E]' : 'bg-white/15'}`}>
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${bat ? 'translate-x-5' : ''}`} />
    </button>
  );
}

function ChonChuKy({ v, doi, khoa }: { v: CdtChuKy; doi: (v: CdtChuKy) => void; khoa?: boolean }) {
  return (
    <div className="inline-flex rounded-full bg-white/5 p-0.5 text-xs">
      {(['thang', 'quy'] as CdtChuKy[]).map(k => (
        <button key={k} type="button" disabled={khoa} onClick={() => doi(k)}
          className={`px-3 py-1 rounded-full ${v === k ? 'bg-white text-black font-semibold' : 'text-[var(--text-secondary)]'}`}>
          {k === 'thang' ? 'Tháng' : 'Quý'}
        </button>
      ))}
    </div>
  );
}

/** Số có đơn vị: lưu bằng đồng/điểm, hiển thị chia `don_vi` (1e6 = triệu, 1e9 = tỷ). */
function So({ v, doi, don_vi = 1, hau_to, khoa, rong = 'w-20', buoc }: {
  v: number; doi: (n: number) => void; don_vi?: number; hau_to?: string; khoa?: boolean; rong?: string; buoc?: number;
}) {
  const hien = String(+(v / don_vi).toFixed(3)).replace('.', ',');
  const [chu, setChu] = useState(hien);
  const [goc, setGoc] = useState(hien);
  if (goc !== hien) { setGoc(hien); setChu(hien); }  // giá trị ngoài đổi (tải lại) → đồng bộ ô
  return (
    <span className="inline-flex items-center gap-1">
      <input inputMode="decimal" disabled={khoa} value={chu} step={buoc}
        onChange={e => setChu(e.target.value)}
        onBlur={() => {
          const n = parseFloat(chu.replace(/\./g, '').replace(',', '.'));
          if (Number.isFinite(n)) doi(Math.round(n * don_vi * 1000) / 1000);
          else setChu(hien);
        }}
        className={`input !py-1 !px-2 text-right font-mono ${rong}`} />
      {hau_to && <span className="text-xs text-[var(--text-muted)]">{hau_to}</span>}
    </span>
  );
}

function Dong({ nhan, children, phu }: { nhan: string; children: React.ReactNode; phu?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-t border-white/5 first:border-t-0">
      <div className="min-w-0">
        <div className="text-sm">{nhan}</div>
        {phu && <div className="text-[11px] text-[var(--text-muted)]">{phu}</div>}
      </div>
      <div className="shrink-0 flex items-center gap-2">{children}</div>
    </div>
  );
}

function TheChuongTrinh({ ten, mo_ta, bat, chu_ky, doiBat, doiChuKy, khoa, children }: {
  ten: string; mo_ta: string; bat: boolean; chu_ky: CdtChuKy; doiBat: (v: boolean) => void;
  doiChuKy: (v: CdtChuKy) => void; khoa: boolean; children: React.ReactNode;
}) {
  return (
    <div className={`card p-4 sm:p-5 ${bat ? '' : 'opacity-70'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-h3">{ten}</h3>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">{mo_ta}</p>
        </div>
        <Cong bat={bat} doi={doiBat} khoa={khoa} />
      </div>
      {bat && (
        <div className="mt-3">
          <Dong nhan="Chu kỳ chi"><ChonChuKy v={chu_ky} doi={doiChuKy} khoa={khoa} /></Dong>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Trang ───────────────────────────────────────────────────────────────────

export default function CheDoThuongPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [tab, setTab] = useState<'cai_dat' | 'bang'>('cai_dat');
  const [ky, setKy] = useState(kyHienTai);
  const [goc, setGoc] = useState<CdtCauHinhResp | null>(null);
  const [cfg, setCfg] = useState<CdtCauHinh | null>(null);
  const [bang, setBang] = useState<CdtBang | null>(null);
  const [loaiTru, setLoaiTru] = useState<string[]>([]);
  const [dangLuu, setDangLuu] = useState(false);
  const [dangChot, setDangChot] = useState(false);
  const [moNguoi, setMoNguoi] = useState<string | null>(null);
  const [loi, setLoi] = useState('');

  const duocXem = !!user && VAI_XEM.includes(user.role);
  const khoa = user?.role !== 'admin';

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    if (!duocXem) router.push('/');
  }, [user, loading, duocXem, router]);

  const taiCauHinh = useCallback(() => {
    // Sửa cấu hình luôn nhắm kỳ sẽ áp (lan_luu_sau_ap_tu) để admin thấy đúng bản mình đang sửa.
    api.cdtCauHinh().then(r => {
      if (r.lan_luu_sau_ap_tu !== r.ky) {
        return api.cdtCauHinh(r.lan_luu_sau_ap_tu).then(r2 => { setGoc(r2); setCfg(r2.cau_hinh); });
      }
      setGoc(r); setCfg(r.cau_hinh);
    }).catch(e => setLoi(e.message));
  }, []);

  const taiBang = useCallback(() => {
    api.cdtXemThu(ky).then(setBang).catch(e => setLoi(e.message));
    api.cdtLoaiTru(ky).then(r => setLoaiTru(r.user_ids)).catch(() => {});
  }, [ky]);

  useEffect(() => { if (duocXem) taiCauHinh(); }, [duocXem, taiCauHinh]);
  useEffect(() => { if (duocXem) taiBang(); }, [duocXem, taiBang]);

  const thayDoi = useMemo(() => !!goc && !!cfg && JSON.stringify(goc.cau_hinh) !== JSON.stringify(cfg), [goc, cfg]);

  function sua<K extends keyof CdtCauHinh['chuong_trinh']>(ma: K, patch: Partial<CdtCauHinh['chuong_trinh'][K]>) {
    setCfg(c => c && { ...c, chuong_trinh: { ...c.chuong_trinh, [ma]: { ...c.chuong_trinh[ma], ...patch } } });
  }

  async function luu() {
    if (!cfg) return;
    setDangLuu(true);
    try {
      const r = await api.cdtLuu(cfg);
      toast(`Đã lưu — áp dụng từ ${nhanKy(r.hieu_luc_tu)}`, 'success');
      taiCauHinh();
      taiBang();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally { setDangLuu(false); }
  }

  async function doiKyLuat(uid: string) {
    const moi = loaiTru.includes(uid) ? loaiTru.filter(x => x !== uid) : [...loaiTru, uid];
    try {
      const r = await api.cdtLuuLoaiTru(ky, moi);
      setLoaiTru(r.user_ids);
      api.cdtXemThu(ky).then(setBang).catch(() => {});
    } catch (e) { toast((e as Error).message, 'error'); }
  }

  async function chot() {
    if (!bang) return;
    if (!confirm(`Chốt bảng thưởng ${nhanKy(ky)}: ${bang.so_nguoi_nhan} người, tổng ${tien(bang.tong_chi)}?\nSẽ tạo khoản thưởng chờ duyệt và gửi 1 đơn sang Phê duyệt.`)) return;
    setDangChot(true);
    try {
      const r = await api.cdtChot(ky);
      toast(r.approval_id ? 'Đã chốt — đơn «Bảng thưởng» đang chờ duyệt' : 'Đã chốt — kỳ này không ai có khoản thưởng', 'success');
      taiBang();
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally { setDangChot(false); }
  }

  if (loading || !user || !duocXem) return <Sidebar><div className="p-6"><div className="skeleton h-8 w-60 rounded-xl" /></div></Sidebar>;

  const ct = cfg?.chuong_trinh;
  const soBat = ct ? Object.values(ct).filter(c => c.bat).length : 0;
  const daQua = ky < kyHienTai();

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 space-y-5 max-w-6xl pb-28">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-overline text-[var(--text-muted)]">Cài đặt › Nhân sự</div>
            <h1 className="text-h1">Chế độ thưởng</h1>
          </div>
          <div className="inline-flex rounded-full bg-white/5 p-1 text-sm">
            {([['cai_dat', 'Cài đặt'], ['bang', 'Bảng thưởng']] as const).map(([k, n]) => (
              <button key={k} onClick={() => setTab(k)}
                className={`px-4 py-1.5 rounded-full ${tab === k ? 'bg-white text-black font-semibold' : 'text-[var(--text-secondary)]'}`}>{n}</button>
            ))}
          </div>
        </div>

        {loi && <div className="card p-3 text-sm text-[var(--danger)]">{loi}</div>}

        {/* Hàng tóm tắt */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="stat-card"><div className="text-caption text-[var(--text-muted)]">Đang bật</div><div className="text-h2 font-mono">{soBat}/5</div></div>
          <div className="stat-card"><div className="text-caption text-[var(--text-muted)]">Dự kiến chi {nhanKy(ky)}</div>
            <div className={`text-h2 font-mono ${bang?.vuot_tran ? 'text-[var(--danger)]' : ''}`}>{bang ? tien(bang.tong_chi) : '…'}</div></div>
          <div className="stat-card"><div className="text-caption text-[var(--text-muted)]">Người có thưởng</div>
            <div className="text-h2 font-mono">{bang ? `${bang.so_nguoi_nhan}/${bang.so_nguoi}` : '…'}</div></div>
          <div className="stat-card"><div className="text-caption text-[var(--text-muted)]">Quỹ trần / tháng</div>
            <div className="text-h2 font-mono">{cfg ? tien(cfg.quy_tran_thang) : '…'}</div></div>
        </div>

        {tab === 'cai_dat' && cfg && ct && goc && (
          <>
            <div className="text-xs text-[var(--text-muted)]">
              {goc.hieu_luc_tu ? <>Đang sửa bản áp từ <b className="text-[var(--text-primary)]">{nhanKy(goc.lan_luu_sau_ap_tu)}</b>. Thay đổi không đụng kỳ đang chạy.</>
                : <>Chưa lưu lần nào — hệ thống đang dùng số mẫu, chưa tự chốt thưởng. Lưu lần đầu sẽ áp ngay {nhanKy(goc.lan_luu_sau_ap_tu)}.</>}
              {khoa && ' (Kế toán chỉ xem — Admin mới sửa được.)'}
            </div>

            <div className="grid lg:grid-cols-2 gap-4 items-start">
              <TheChuongTrinh ten="1 · Hũ doanh số" mo_ta="Doanh số công ty chạm mốc → mở quỹ, chia cho phòng nhận."
                bat={ct.hu_doanh_so.bat} chu_ky={ct.hu_doanh_so.chu_ky} khoa={khoa}
                doiBat={v => sua('hu_doanh_so', { bat: v })} doiChuKy={v => sua('hu_doanh_so', { chu_ky: v })}>
                <div className="py-2 space-y-2">
                  {ct.hu_doanh_so.moc.map((m, i) => (
                    <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="w-6 text-[var(--text-muted)] font-mono">{i + 1}</span>
                      <input className="input !py-1 !px-2 w-28" disabled={khoa} value={m.nhan}
                        onChange={e => sua('hu_doanh_so', { moc: ct.hu_doanh_so.moc.map((x, j) => j === i ? { ...x, nhan: e.target.value } : x) })} />
                      <So v={m.doanh_so} don_vi={1e9} hau_to="tỷ →" khoa={khoa} rong="w-16"
                        doi={n => sua('hu_doanh_so', { moc: ct.hu_doanh_so.moc.map((x, j) => j === i ? { ...x, doanh_so: n } : x) })} />
                      <So v={m.quy} don_vi={1e6} hau_to="tr" khoa={khoa} rong="w-16"
                        doi={n => sua('hu_doanh_so', { moc: ct.hu_doanh_so.moc.map((x, j) => j === i ? { ...x, quy: n } : x) })} />
                      {!khoa && ct.hu_doanh_so.moc.length > 1 && (
                        <button className="text-xs text-[var(--danger)] ml-auto" onClick={() => sua('hu_doanh_so', { moc: ct.hu_doanh_so.moc.filter((_, j) => j !== i) })}>Xóa</button>
                      )}
                    </div>
                  ))}
                  {!khoa && ct.hu_doanh_so.moc.length < 8 && (
                    <button className="btn-ghost !py-1 !px-3 text-xs" onClick={() => {
                      const cuoi = ct.hu_doanh_so.moc[ct.hu_doanh_so.moc.length - 1];
                      sua('hu_doanh_so', { moc: [...ct.hu_doanh_so.moc, { nhan: `Mốc ${ct.hu_doanh_so.moc.length + 1}`, doanh_so: (cuoi?.doanh_so || 0) + 2e9, quy: (cuoi?.quy || 0) + 50e6 }] });
                    }}>+ Thêm mốc</button>
                  )}
                </div>
                <Dong nhan="Cộng dồn các mốc" phu={ct.hu_doanh_so.cong_don ? 'Đạt mốc 3 = quỹ mốc 1+2+3' : 'Chỉ lấy quỹ mốc cao nhất'}>
                  <Cong bat={ct.hu_doanh_so.cong_don} doi={v => sua('hu_doanh_so', { cong_don: v })} khoa={khoa} />
                </Dong>
                <Dong nhan="Cách chia">
                  <select className="input !py-1 text-sm" disabled={khoa} value={ct.hu_doanh_so.cach_chia} onChange={e => sua('hu_doanh_so', { cach_chia: e.target.value })}>
                    <option value="theo_doanh_so">Theo % doanh số</option>
                    <option value="chia_deu">Chia đều</option>
                    <option value="hon_hop">Nửa đều, nửa theo số</option>
                  </select>
                </Dong>
                <Dong nhan="Phạm vi">
                  <select className="input !py-1 text-sm" disabled={khoa} value={ct.hu_doanh_so.pham_vi} onChange={e => sua('hu_doanh_so', { pham_vi: e.target.value })}>
                    <option value="cong_ty">Cả công ty</option>
                    <option value="theo_phong">Theo phòng</option>
                    <option value="theo_nhom">Theo nhóm</option>
                  </select>
                </Dong>
                <Dong nhan="Ai thấy hũ trên Tổng quan">
                  <select className="input !py-1 text-sm" disabled={khoa} value={ct.hu_doanh_so.ai_thay_hu} onChange={e => sua('hu_doanh_so', { ai_thay_hu: e.target.value })}>
                    <option value="kinh_doanh">Khối kinh doanh</option>
                    <option value="tat_ca">Mọi người</option>
                    <option value="quan_ly">Chỉ quản lý</option>
                  </select>
                </Dong>
                <Dong nhan="Báo nhóm Telegram khi chạm mốc" phu="Không ghi số tiền từng người">
                  <Cong bat={ct.hu_doanh_so.bao_telegram} doi={v => sua('hu_doanh_so', { bao_telegram: v })} khoa={khoa} />
                </Dong>
              </TheChuongTrinh>

              <TheChuongTrinh ten="2 · Chuyên cần" mo_ta="Bắt đầu 100 điểm, trừ theo chấm công. Nghỉ phép, công tác, ca công trình không trừ."
                bat={ct.chuyen_can.bat} chu_ky={ct.chuyen_can.chu_ky} khoa={khoa}
                doiBat={v => sua('chuyen_can', { bat: v })} doiChuKy={v => sua('chuyen_can', { chu_ky: v })}>
                <Dong nhan="Giờ vào ca">
                  <input type="time" className="input !py-1 !px-2 w-28" disabled={khoa} value={ct.chuyen_can.gio_vao_ca}
                    onChange={e => sua('chuyen_can', { gio_vao_ca: e.target.value })} />
                </Dong>
                <Dong nhan="Tính trễ khi quá"><So v={ct.chuyen_can.tre_phut} hau_to="phút" khoa={khoa} doi={n => sua('chuyen_can', { tre_phut: n })} /></Dong>
                <Dong nhan="Mỗi lần trễ"><So v={ct.chuyen_can.tru_tre} hau_to="−điểm" khoa={khoa} doi={n => sua('chuyen_can', { tru_tre: n })} /></Dong>
                <Dong nhan="Quên chấm ra"><So v={ct.chuyen_can.tru_quen_ra} hau_to="−điểm" khoa={khoa} doi={n => sua('chuyen_can', { tru_quen_ra: n })} /></Dong>
                <Dong nhan="Nghỉ không phép / ngày"><So v={ct.chuyen_can.tru_nghi_khong_phep} hau_to="−điểm" khoa={khoa} doi={n => sua('chuyen_can', { tru_nghi_khong_phep: n })} /></Dong>
                <Dong nhan="Thưởng đủ công, không trễ"><So v={ct.chuyen_can.thuong_du_cong} don_vi={1e3} hau_to="k" khoa={khoa} doi={n => sua('chuyen_can', { thuong_du_cong: n })} /></Dong>
              </TheChuongTrinh>

              <TheChuongTrinh ten="3 · Phản hồi khách" mo_ta="Gọi lead mới đúng hạn + trả lời Zalo khách nhanh (giờ hành chính)."
                bat={ct.phan_hoi.bat} chu_ky={ct.phan_hoi.chu_ky} khoa={khoa}
                doiBat={v => sua('phan_hoi', { bat: v })} doiChuKy={v => sua('phan_hoi', { chu_ky: v })}>
                <Dong nhan="Gọi lead trong" phu="Mục tiêu tỷ lệ đạt">
                  <So v={ct.phan_hoi.gio_goi} hau_to="giờ" khoa={khoa} rong="w-14" doi={n => sua('phan_hoi', { gio_goi: n })} />
                  <So v={ct.phan_hoi.muc_tieu_goi} hau_to="%" khoa={khoa} rong="w-14" doi={n => sua('phan_hoi', { muc_tieu_goi: n })} />
                </Dong>
                <Dong nhan="Trả lời Zalo trong" phu="Mục tiêu tỷ lệ đạt">
                  <So v={ct.phan_hoi.phut_zalo} hau_to="phút" khoa={khoa} rong="w-14" doi={n => sua('phan_hoi', { phut_zalo: n })} />
                  <So v={ct.phan_hoi.muc_tieu_zalo} hau_to="%" khoa={khoa} rong="w-14" doi={n => sua('phan_hoi', { muc_tieu_zalo: n })} />
                </Dong>
                <Dong nhan="Mỗi lead bỏ quá 24h"><So v={ct.phan_hoi.tru_qua_24h} hau_to="−điểm" khoa={khoa} doi={n => sua('phan_hoi', { tru_qua_24h: n })} /></Dong>
                <Dong nhan="Thưởng khi đạt cả 2 mục tiêu"><So v={ct.phan_hoi.thuong} don_vi={1e6} hau_to="tr" khoa={khoa} doi={n => sua('phan_hoi', { thuong: n })} /></Dong>
              </TheChuongTrinh>

              <TheChuongTrinh ten="4 · Khách hàng đánh giá" mo_ta="Khách chấm sao trên trang tiến độ (portal) ở các mốc dự án."
                bat={ct.danh_gia.bat} chu_ky={ct.danh_gia.chu_ky} khoa={khoa}
                doiBat={v => sua('danh_gia', { bat: v })} doiChuKy={v => sua('danh_gia', { chu_ky: v })}>
                <div className="py-2 flex flex-wrap gap-2">
                  {Object.entries(MOC_DANH_GIA).map(([ma, ten]) => {
                    const co = ct.danh_gia.thoi_diem.includes(ma);
                    return (
                      <button key={ma} disabled={khoa} onClick={() => sua('danh_gia', { thoi_diem: co ? ct.danh_gia.thoi_diem.filter(x => x !== ma) : [...ct.danh_gia.thoi_diem, ma] })}
                        className={`px-3 py-1 rounded-full text-xs border ${co ? 'border-[#C9A96E] text-[#C9A96E]' : 'border-white/10 text-[var(--text-muted)]'}`}>
                        {co ? '✓ ' : ''}{ten}
                      </button>
                    );
                  })}
                </div>
                <Dong nhan="Trung bình đạt từ"><So v={ct.danh_gia.nguong_sao} hau_to="sao" khoa={khoa} rong="w-14" doi={n => sua('danh_gia', { nguong_sao: n })} /></Dong>
                <Dong nhan="Thưởng / dự án đạt" phu="Chia cho đội dự án"><So v={ct.danh_gia.thuong_du_an} don_vi={1e6} hau_to="tr" khoa={khoa} doi={n => sua('danh_gia', { thuong_du_an: n })} /></Dong>
                <Dong nhan="Mỗi lần khách khen tên"><So v={ct.danh_gia.thuong_khen} don_vi={1e3} hau_to="k" khoa={khoa} doi={n => sua('danh_gia', { thuong_khen: n })} /></Dong>
                <p className="text-[11px] text-[var(--text-muted)] pt-1">Khách chấm ≤ 2 sao → báo ngay Trưởng phòng & BGĐ, giữ thưởng dự án đó.</p>
              </TheChuongTrinh>

              <TheChuongTrinh ten="5 · Ngôi sao quý" mo_ta="Top Điểm JAMA cả quý nhận giải — chi ở tháng cuối quý."
                bat={ct.ngoi_sao.bat} chu_ky={ct.ngoi_sao.chu_ky} khoa={khoa}
                doiBat={v => sua('ngoi_sao', { bat: v })} doiChuKy={v => sua('ngoi_sao', { chu_ky: v })}>
                {ct.ngoi_sao.giai.map((g, i) => (
                  <Dong key={i} nhan={`Hạng ${i + 1}`}>
                    <So v={g} don_vi={1e6} hau_to="tr" khoa={khoa} doi={n => sua('ngoi_sao', { giai: ct.ngoi_sao.giai.map((x, j) => j === i ? n : x) })} />
                  </Dong>
                ))}
              </TheChuongTrinh>

              {/* Điểm JAMA */}
              <div className="card p-4 sm:p-5">
                <h3 className="text-h3">Điểm JAMA</h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">Trọng số theo phòng (%). Thành phần chưa có số → chia lại cho phần còn lại, không phạt.</p>
                <div className="table-scroll mt-3">
                  <table className="w-full text-sm">
                    <thead><tr className="text-[11px] text-[var(--text-muted)]">
                      <th className="text-left font-medium py-1">Phòng</th>
                      {THANH_PHAN.map(t => <th key={t.ma} className="font-medium py-1 text-right">{t.nhan}</th>)}
                    </tr></thead>
                    <tbody>
                      {PHONG_TRONG_SO.map(p => {
                        const ts = cfg.diem_jama.trong_so[p] || {};
                        return (
                          <tr key={p} className="border-t border-white/5">
                            <td className="py-1.5 pr-2 whitespace-nowrap">{tenPhong(p)}</td>
                            {THANH_PHAN.map(t => (
                              <td key={t.ma} className="py-1.5 text-right">
                                <So v={ts[t.ma] || 0} rong="w-14" khoa={khoa} doi={n => setCfg(c => c && {
                                  ...c, diem_jama: { ...c.diem_jama, trong_so: { ...c.diem_jama.trong_so, [p]: { ...(c.diem_jama.trong_so[p] || {}), [t.ma]: n } } },
                                })} />
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 text-sm font-medium">Hệ số nhân phần hũ</div>
                {cfg.diem_jama.he_so.map((h, i) => (
                  <Dong key={i} nhan={i === cfg.diem_jama.he_so.length - 1 ? `Dưới ${cfg.diem_jama.he_so[i - 1]?.tu ?? 0} điểm` : `Từ ${h.tu} điểm`}>
                    {i < cfg.diem_jama.he_so.length - 1 && (
                      <So v={h.tu} rong="w-14" hau_to="điểm" khoa={khoa} doi={n => setCfg(c => c && { ...c, diem_jama: { ...c.diem_jama, he_so: c.diem_jama.he_so.map((x, j) => j === i ? { ...x, tu: n } : x) } })} />
                    )}
                    <span className="text-xs text-[var(--text-muted)]">×</span>
                    <So v={h.he_so} rong="w-14" khoa={khoa} doi={n => setCfg(c => c && { ...c, diem_jama: { ...c.diem_jama, he_so: c.diem_jama.he_so.map((x, j) => j === i ? { ...x, he_so: n } : x) } })} />
                  </Dong>
                ))}
              </div>

              {/* Điều kiện chung */}
              <div className="card p-4 sm:p-5">
                <h3 className="text-h3">Điều kiện chung</h3>
                <Dong nhan="Quỹ trần / tháng" phu="Vượt trần chỉ cảnh báo, không tự cắt">
                  <So v={cfg.quy_tran_thang} don_vi={1e6} hau_to="tr" khoa={khoa} doi={n => setCfg(c => c && { ...c, quy_tran_thang: n })} />
                </Dong>
                <Dong nhan="Phải còn làm việc khi chi">
                  <Cong bat={cfg.dieu_kien.con_lam_viec} khoa={khoa} doi={v => setCfg(c => c && { ...c, dieu_kien: { ...c.dieu_kien, con_lam_viec: v } })} />
                </Dong>
                <Dong nhan="Nhân viên thử việc nhận">
                  <So v={cfg.dieu_kien.thu_viec_pct} hau_to="%" rong="w-14" khoa={khoa} doi={n => setCfg(c => c && { ...c, dieu_kien: { ...c.dieu_kien, thu_viec_pct: n } })} />
                </Dong>
                <Dong nhan="Bị kỷ luật trong kỳ → không nhận">
                  <Cong bat={cfg.dieu_kien.ky_luat_khong_nhan} khoa={khoa} doi={v => setCfg(c => c && { ...c, dieu_kien: { ...c.dieu_kien, ky_luat_khong_nhan: v } })} />
                </Dong>
                <Dong nhan="Nhân viên tự xem điểm trong Hồ sơ 360°">
                  <Cong bat={cfg.dieu_kien.nv_xem_diem} khoa={khoa} doi={v => setCfg(c => c && { ...c, dieu_kien: { ...c.dieu_kien, nv_xem_diem: v } })} />
                </Dong>
                <Dong nhan="Tự chốt kỳ trước vào ngày 1" phu="Tạo khoản thưởng chờ duyệt, Kế toán duyệt rồi mới vào lương">
                  <Cong bat={cfg.tu_dong_chot} khoa={khoa} doi={v => setCfg(c => c && { ...c, tu_dong_chot: v })} />
                </Dong>
              </div>
            </div>

            {goc.lich_su.length > 0 && (
              <div className="card p-4 sm:p-5">
                <h3 className="text-h3 mb-2">Lịch sử thay đổi</h3>
                <ul className="text-sm space-y-1">
                  {goc.lich_su.map((l, i) => (
                    <li key={i} className="flex justify-between gap-3 text-[var(--text-secondary)]">
                      <span>{l.boi} — áp từ {nhanKy(l.hieu_luc_tu)}</span>
                      <span className="text-xs text-[var(--text-muted)] font-mono">{new Date(l.luc).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!khoa && (
              <div className="fixed bottom-0 inset-x-0 lg:left-auto lg:right-6 lg:bottom-6 z-30 p-3 lg:p-0 bg-[var(--card-bg)] lg:bg-transparent border-t border-white/10 lg:border-0"
                style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}>
                <div className="flex gap-2 justify-end">
                  <button className="btn-ghost" onClick={() => setTab('bang')}>Xem thử bảng thưởng</button>
                  <button className="btn-primary" disabled={!thayDoi || dangLuu} onClick={luu}>
                    {dangLuu ? 'Đang lưu…' : `Lưu — áp từ ${nhanKy(goc.lan_luu_sau_ap_tu)}`}
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {tab === 'bang' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn-ghost !px-3" onClick={() => setKy(k => kyLech(k, -1))} aria-label="Kỳ trước">‹</button>
              <span className="font-mono text-sm w-24 text-center">{nhanKy(ky)}</span>
              <button className="btn-ghost !px-3" disabled={ky >= kyHienTai()} onClick={() => setKy(k => kyLech(k, 1))} aria-label="Kỳ sau">›</button>
              {bang && <span className="text-xs text-[var(--text-muted)]">{bang.quy}{bang.cuoi_quy ? ' · tháng cuối quý — chi cả khoản theo quý' : ''}</span>}
              <div className="ml-auto">
                {bang?.da_chot ? (
                  <span className="badge">Đã chốt {new Date(bang.da_chot.luc).toLocaleDateString('vi-VN')} · vào lương {nhanKy(bang.da_chot.ky_luong)}</span>
                ) : daQua ? (
                  <button className="btn-primary" disabled={dangChot || !bang} onClick={chot}>{dangChot ? 'Đang chốt…' : 'Chốt kỳ → gửi duyệt'}</button>
                ) : (
                  <span className="text-xs text-[var(--text-muted)]">Kỳ đang chạy — số liệu dự kiến</span>
                )}
              </div>
            </div>

            {bang?.vuot_tran && (
              <div className="card p-3 text-sm text-[var(--warning)]">Tổng chi {tien(bang.tong_chi)} vượt quỹ trần {tien(bang.quy_tran)} — xem lại trước khi chốt.</div>
            )}

            {bang?.hu && (
              <div className="card p-4 text-sm flex flex-wrap gap-x-6 gap-y-1">
                <span>Doanh số: <b className="font-mono">{tien(bang.hu.doanh_so)}</b></span>
                <span>Mốc đạt: <b className="font-mono">{bang.hu.so_moc_dat}/{bang.hu.moc.length}</b></span>
                <span>Quỹ hũ mở: <b className="font-mono text-[#C9A96E]">{tien(bang.hu.quy_mo)}</b></span>
                {bang.hu.moc_tiep && <span className="text-[var(--text-muted)]">Còn {tien(bang.hu.con_thieu)} tới «{bang.hu.moc_tiep.nhan}»</span>}
              </div>
            )}

            {!bang || bang.ky !== ky ? <div className="skeleton h-40 rounded-2xl" /> : bang.nguoi.length === 0 ? (
              <div className="card p-6 text-sm text-[var(--text-muted)] text-center">Chưa có nhân viên nào thuộc diện xét thưởng.</div>
            ) : (
              <div className="card divide-y divide-white/5">
                {[...bang.nguoi].sort((a, b) => (b.tong + b.du_kien_cuoi_quy) - (a.tong + a.du_kien_cuoi_quy)).map(r => {
                  const mo = moNguoi === r.user_id;
                  const kyLuat = loaiTru.includes(r.user_id);
                  return (
                    <div key={r.user_id} className="p-3 sm:p-4">
                      <button className="w-full flex items-center gap-3 text-left" onClick={() => setMoNguoi(mo ? null : r.user_id)}>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium truncate">{r.ten}</div>
                          <div className="text-[11px] text-[var(--text-muted)]">{tenPhong(r.phong || '_khac')}{r.nhom ? ` · ${r.nhom}` : ''}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-xs text-[var(--text-muted)]">{r.diem == null ? 'Chưa đủ số' : `${r.diem} điểm · ×${r.he_so}`}</div>
                          <div className="font-mono text-sm">{tien(r.tong)}{r.du_kien_cuoi_quy > 0 && <span className="text-[var(--text-muted)]"> +{tien(r.du_kien_cuoi_quy)} cuối quý</span>}</div>
                        </div>
                      </button>
                      {mo && (
                        <div className="mt-3 pl-1 space-y-2 text-sm">
                          <div className="flex flex-wrap gap-2">
                            {THANH_PHAN.map(t => (
                              <span key={t.ma} className="badge">{t.nhan}: {r.thanh_phan[t.ma] == null ? '—' : r.thanh_phan[t.ma]}</span>
                            ))}
                          </div>
                          {r.khoan.length === 0 ? <div className="text-xs text-[var(--text-muted)]">Chưa có khoản nào.</div> : (
                            <ul className="space-y-1">
                              {r.khoan.map((k, i) => (
                                <li key={i} className="flex justify-between gap-3">
                                  <span className="text-[var(--text-secondary)]">{k.nhan}{!k.chi_ky_nay && ' (chi cuối quý)'}</span>
                                  <span className="font-mono">{tien(k.so_tien)}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                          {r.ghi_chu.map((g, i) => <div key={i} className="text-xs text-[var(--warning)]">{g}</div>)}
                          {!bang.da_chot && (
                            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                              <input type="checkbox" checked={kyLuat} onChange={() => doiKyLuat(r.user_id)} />
                              Bị kỷ luật trong {nhanKy(ky)} (không nhận thưởng)
                            </label>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {bang && bang.du_an_danh_gia.length > 0 && (
              <div className="card p-4">
                <h3 className="text-h3 mb-2">Khách đánh giá — {bang.quy}</h3>
                <ul className="text-sm space-y-1">
                  {bang.du_an_danh_gia.map(d => (
                    <li key={d.project_id} className="flex justify-between gap-3">
                      <span className="truncate">{d.code} · {d.name}</span>
                      <span className={`font-mono shrink-0 ${d.khieu_nai ? 'text-[var(--danger)]' : d.dat ? 'text-[var(--success)]' : ''}`}>
                        {d.sao_tb.toLocaleString('vi-VN')}★ · {d.so_luot} lượt{d.khieu_nai ? ' · giữ thưởng' : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Sidebar>
  );
}
