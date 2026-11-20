'use client';

/**
 * Đối chiếu (20/11/2026) — đích của mọi tin «Nhắc trưởng phòng» trên Telegram.
 *
 * Trưởng phòng mở link `/doi-chieu?phong=X`, lướt danh sách hồ sơ của phòng mình,
 * sửa dòng nào sai rồi bấm «Còn lại đều đúng — Xác nhận» (~2 phút/tuần).
 * • BGĐ (admin/executive) xem được mọi phòng; trưởng phòng CHỈ phòng mình
 *   (backend trả 403 nếu gọi phòng khác — khớp backend/app/api/du_lieu_chung.py).
 * • Không hiện tiền cho trưởng phòng: backend chỉ gửi `gia_tri` cho BGĐ.
 * • «Đã xong» KHÔNG tự đóng dự án — dồn về BGĐ ở trang Dữ liệu chung.
 * • Phòng Kinh doanh chỉ đối chiếu lead chờ ký (Đã gửi báo giá / Đang đàm phán).
 */

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';
import { Trong } from '@/components/dashboard/KhoiDashboard';
import {
  api, DoiChieu, DoiChieuHoSo, DoiChieuMuc, KetQuaDoiChieu, PhongDuLieu,
} from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import {
  GIAI_DOAN_DU_AN, GIAI_DOAN_LEAD, GIAI_DOAN_THEO_PHONG, NHAN_KET_QUA, PHONG_DU_LIEU, TEN_PHONG,
  baoLau, duocDoiChieu, duocDoiGiaiDoanDuAn, laBGD, linkHoSo, ngayThang, nhanDauVet, nhanGiaiDoan,
  nhanLoiDoiChieu, phongCuaNguoi,
} from '@/lib/du-lieu-chung';

type Tab = 'ho_so' | 'chua_xep';
type Chon = { ket_qua?: KetQuaDoiChieu; giai_doan_moi?: string; ly_do?: string; pic_id?: string };

const NUT = 'inline-flex items-center justify-center gap-1.5 min-h-[44px] px-4 rounded-full text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const NUT_CHINH = `${NUT} bg-[var(--gold-500)] text-[var(--surface-0)] hover:bg-[var(--gold-400)]`;
const NUT_PHU = `${NUT} border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]`;

function laPhong(x: string | null): x is PhongDuLieu {
  return !!x && (PHONG_DU_LIEU as string[]).includes(x);
}

/** Tên ngắn của một dòng — lead không có mã nên lùi về tên. */
function tenDong(r: Pick<DoiChieuHoSo, 'ma' | 'ten'>): string {
  return r.ma || r.ten || '';
}

function Chip({ chon, onClick, children, disabled }: { chon: boolean; onClick: () => void; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={chon}
      className="min-h-[44px] px-3 rounded-full text-[11px] font-medium transition-colors disabled:opacity-50"
      style={chon
        ? { background: 'var(--gold-500)', color: 'var(--surface-0)' }
        : { background: 'var(--surface-3)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
      {children}
    </button>
  );
}

function DoiChieuNoiDung() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const bgd = laBGD(user);
  const doiGiaiDoanDuAn = duocDoiGiaiDoanDuAn(user);
  const phongMinh = phongCuaNguoi(user);
  const phongThamSo = searchParams.get('phong');
  const phong: PhongDuLieu | null = bgd
    ? (laPhong(phongThamSo) ? phongThamSo : 'SALES')
    : phongMinh;
  const coTabChuaXep = phong !== null && phong !== 'SALES';
  const tab: Tab = coTabChuaXep && searchParams.get('tab') === 'chua_xep' ? 'chua_xep' : 'ho_so';

  const [data, setData] = useState<DoiChieu | null>(null);
  const [khoaDaTai, setKhoaDaTai] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [lanTai, setLanTai] = useState(0);
  const [chon, setChon] = useState<Record<string, Chon>>({});
  const [timKiem, setTimKiem] = useState('');
  const [dangGui, setDangGui] = useState(false);

  const khoa = `${phong}|${tab}|${lanTai}`;
  const dangTai = khoaDaTai !== khoa;

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    if (!duocDoiChieu(user)) { router.push('/'); return; }
    // Trưởng phòng mở link của phòng khác (vd. bấm nhầm link chuyển tiếp) → về phòng mình.
    if (!bgd && phongMinh && phongThamSo !== phongMinh) {
      router.replace(`/doi-chieu?phong=${phongMinh}${tab === 'chua_xep' ? '&tab=chua_xep' : ''}`);
    }
  }, [user, loading, router, bgd, phongMinh, phongThamSo, tab]);

  useEffect(() => {
    if (!user || !duocDoiChieu(user) || !phong) return;
    let huy = false;
    api.getDoiChieu(phong, tab)
      .then(d => { if (!huy) { setData(d); setError(''); setChon({}); } })
      .catch(e => { if (!huy) setError(e instanceof Error ? e.message : 'Không tải được danh sách'); })
      .finally(() => { if (!huy) setKhoaDaTai(`${phong}|${tab}|${lanTai}`); });
    return () => { huy = true; };
  }, [user, phong, tab, lanTai]);

  const doiUrl = useCallback((p: PhongDuLieu, t: Tab) => {
    setTimKiem('');
    router.replace(`/doi-chieu?phong=${p}${t === 'chua_xep' ? '&tab=chua_xep' : ''}`);
  }, [router]);

  const datChon = useCallback((id: string, them: Partial<Chon> | null) => {
    setChon(prev => {
      const sau = { ...prev };
      if (them === null) delete sau[id];
      else sau[id] = { ...prev[id], ...them };
      return sau;
    });
  }, []);

  const goc = useMemo(() => (tab === 'chua_xep' ? data?.chua_xep : data?.ho_so) || [], [data, tab]);
  const danhSach = useMemo(() => {
    const q = timKiem.trim().toLowerCase();
    if (!q) return goc;
    // Lead không có mã (ma = null) — mọi trường đều có thể null.
    return goc.filter(r => [r.ma, r.ten, r.khach, r.dia_chi].some(s => (s ?? '').toLowerCase().includes(q)));
  }, [goc, timKiem]);

  // Dòng đã sửa lấy từ CẢ danh sách, không theo ô tìm — sửa rồi gõ tìm cho ẩn đi vẫn được gửi.
  // ids_hien_thi («còn lại đều đúng») thì chỉ là dòng đang hiện.
  const daChon = goc.filter(r => chon[r.id]?.ket_qua);
  const loiNhap = daChon.find(r => {
    const c = chon[r.id];
    return (c.ket_qua === 'sai_giai_doan' && !c.giai_doan_moi) || (c.ket_qua === 'tam_dung' && !c.ly_do?.trim());
  });

  const gui = async (conLaiDung: boolean) => {
    if (!phong || !data) return;
    if (loiNhap) {
      toast(`${tenDong(loiNhap)}: ${chon[loiNhap.id]?.ket_qua === 'tam_dung' ? 'cần ghi lý do tạm dừng' : 'chưa chọn giai đoạn đúng'}`, 'warning');
      return;
    }
    const muc: DoiChieuMuc[] = daChon.map(r => {
      const c = chon[r.id];
      const m: DoiChieuMuc = { id: r.id, loai: r.loai, ket_qua: c.ket_qua as KetQuaDoiChieu };
      if (c.ket_qua === 'sai_giai_doan' && c.giai_doan_moi) m.giai_doan_moi = c.giai_doan_moi;
      if (c.ket_qua === 'tam_dung' && c.ly_do) m.ly_do = c.ly_do.trim();
      if (c.pic_id) m.pic_id = c.pic_id;
      return m;
    });
    if (muc.length === 0 && !conLaiDung) return;
    setDangGui(true);
    try {
      const kq = await api.guiDoiChieu({
        phong,
        muc,
        tat_ca_con_lai_dung: conLaiDung,
        ids_hien_thi: danhSach.map(r => r.id),
      });
      const phan = [`Đã ghi ${kq.da_ghi} hồ sơ`];
      if (kq.da_doi_giai_doan > 0) phan.push(`đổi giai đoạn ${kq.da_doi_giai_doan}`);
      if (kq.loi.length > 0) {
        const tenLoi = kq.loi.slice(0, 3).map(l => {
          const r = goc.find(x => x.id === l.id);
          return `${r ? tenDong(r) : 'Hồ sơ'}: ${nhanLoiDoiChieu(l.ly_do)}`;
        });
        phan.push(`${kq.loi.length} dòng lỗi (${tenLoi.join('; ')}${kq.loi.length > 3 ? '; …' : ''})`);
      }
      toast(phan.join(' · '), kq.loi.length > 0 ? 'warning' : 'success');
      setLanTai(n => n + 1);
    } catch (e) {
      toast(e instanceof Error && e.message ? e.message : 'Không lưu được đối chiếu', 'error');
    } finally {
      setDangGui(false);
    }
  };

  if (loading || !user || !duocDoiChieu(user) || !phong) {
    return (
      <div className="p-4 sm:p-6 space-y-4">
        <div className="skeleton h-8 w-56 max-w-full rounded-xl" />
        {[1, 2, 3].map(i => <div key={i} className="glass-card p-5"><div className="skeleton h-24 w-full rounded-xl" /></div>)}
      </div>
    );
  }

  const nguoi = data?.nguoi_trong_phong || [];

  return (
    <div className="p-4 sm:p-6 space-y-4 animate-in">
      {/* ── Đầu trang ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">
            Đối chiếu <span className="gold-gradient">{TEN_PHONG[phong]}</span>
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Dòng nào CRM ghi chưa đúng thì sửa; còn lại bấm xác nhận một lần — khoảng 2 phút.
          </p>
        </div>
        {bgd && (
          <select aria-label="Chọn phòng" value={phong} onChange={e => doiUrl(e.target.value as PhongDuLieu, 'ho_so')}
            className="input text-xs min-h-[44px] w-auto">
            {PHONG_DU_LIEU.map(p => <option key={p} value={p}>{TEN_PHONG[p]}</option>)}
          </select>
        )}
      </div>

      <div className="px-4 py-3 rounded-2xl text-xs flex items-start gap-2 leading-relaxed"
        style={{ background: 'var(--info-bg)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
        <LineIcon name="info" size={16} color="var(--info)" className="mt-0.5" />
        <p>
          Đây là việc giữ CRM khớp thực tế, không phải chấm điểm cá nhân. «Đã xong» chỉ báo lên Ban giám đốc, hệ thống không tự đóng dự án.
          {phong === 'SALES' && <> Lead muốn chuyển «Mất» hay «Deal đã thắng» thì bấm <b>Mở</b> để làm ở trang Quy trình.</>}
        </p>
      </div>

      {coTabChuaXep && (
        <div className="flex gap-2" role="tablist">
          <Chip chon={tab === 'ho_so'} onClick={() => doiUrl(phong, 'ho_so')}>Hồ sơ của phòng</Chip>
          <Chip chon={tab === 'chua_xep'} onClick={() => doiUrl(phong, 'chua_xep')}>Chưa xếp giai đoạn</Chip>
        </div>
      )}

      {(tab === 'chua_xep' || (data?.ho_so.length || 0) > 8) && (
        <div className="relative">
          <input className="input text-sm min-h-[44px] pl-10" placeholder={tab === 'chua_xep' ? 'Tìm theo tên khách để nhận dự án về phòng…' : 'Tìm theo mã, tên, khách…'}
            value={timKiem} onChange={e => setTimKiem(e.target.value)} aria-label="Tìm hồ sơ" />
          <span className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <LineIcon name="search" size={16} color="var(--text-muted)" />
          </span>
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-2xl text-sm" style={{ background: 'var(--warning-bg)', border: '1px solid var(--border-default)', color: 'var(--warning)' }}>
          {error}
        </div>
      )}

      {dangTai && !data ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="glass-card p-5"><div className="skeleton h-24 w-full rounded-xl" /></div>)}
        </div>
      ) : data && (
        <>
          <p className="text-[11px] text-[var(--text-muted)]">
            {danhSach.length} hồ sơ{dangTai ? ' · đang tải lại…' : ''}
            {tab === 'chua_xep' && ' · dự án nhập từ hệ thống cũ, chưa phòng nào nhận'}
            {tab === 'chua_xep' && !doiGiaiDoanDuAn && ' · chỉ trưởng phòng hoặc quản trị nhận được dự án về phòng'}
          </p>
          {danhSach.length === 0 ? (
            <div className="glass-card p-5">
              <Trong chu={tab === 'chua_xep' ? 'Không có dự án cũ nào khớp.' : 'Phòng chưa có hồ sơ nào cần đối chiếu.'} />
            </div>
          ) : (
            <ul className="space-y-3">
              {danhSach.map(r => (
                <DongDoiChieu key={r.id} r={r} phong={phong} tab={tab} chon={chon[r.id]} nguoi={nguoi}
                  doiGiaiDoanDuAn={doiGiaiDoanDuAn}
                  onDat={them => datChon(r.id, them)} />
              ))}
            </ul>
          )}

          {/* ── Nút dính cuối trang ─────────────────────────────── */}
          {(danhSach.length > 0 || daChon.length > 0) && !(tab === 'chua_xep' && !doiGiaiDoanDuAn) && (
            <div className="sticky z-30 bottom-[calc(4rem+env(safe-area-inset-bottom))] lg:bottom-0 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 flex flex-wrap items-center gap-2"
              style={{ background: 'var(--surface-1)', borderTop: '1px solid var(--border-subtle)' }}>
              <span className="text-[11px] text-[var(--text-muted)] mr-auto">
                {daChon.length > 0 ? `Đã sửa ${daChon.length} dòng` : 'Chưa sửa dòng nào'}
              </span>
              {tab === 'ho_so' ? (
                <>
                  {daChon.length > 0 && (
                    <button type="button" className={NUT_PHU} disabled={dangGui} onClick={() => void gui(false)}>
                      Chỉ lưu {daChon.length} dòng
                    </button>
                  )}
                  <button type="button" className={NUT_CHINH} disabled={dangGui} onClick={() => void gui(true)}>
                    <LineIcon name="check" size={14} color="currentColor" />
                    {dangGui ? 'Đang lưu…' : 'Còn lại đều đúng — Xác nhận'}
                  </button>
                </>
              ) : (
                <button type="button" className={NUT_CHINH} disabled={dangGui || daChon.length === 0} onClick={() => void gui(false)}>
                  <LineIcon name="check" size={14} color="currentColor" />
                  {dangGui ? 'Đang lưu…' : `Nhận ${daChon.length} dự án về phòng`}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DongDoiChieu({ r, phong, tab, chon, nguoi, doiGiaiDoanDuAn, onDat }: {
  r: DoiChieuHoSo; phong: PhongDuLieu; tab: Tab; chon?: Chon;
  nguoi: Array<{ id: string; ten: string }>;
  /** false = executive: backend chưa cho đổi giai đoạn / tạm dừng dự án. Lead đi luồng
   *  PUT /leads/{id}/stage riêng nên vẫn được «Sai giai đoạn». */
  doiGiaiDoanDuAn: boolean;
  onDat: (them: Partial<Chon> | null) => void;
}) {
  const laLead = r.loai === 'lead';
  const duocDoiGiaiDoan = laLead || doiGiaiDoanDuAn;
  const kq = chon?.ket_qua;
  const chonKetQua = (k: KetQuaDoiChieu) => {
    if (kq === k) { onDat(chon?.pic_id ? { ket_qua: 'dung', giai_doan_moi: undefined, ly_do: undefined } : null); return; }
    onDat({ ket_qua: k, giai_doan_moi: undefined, ly_do: undefined });
  };
  const luaChonGiaiDoan = (laLead ? GIAI_DOAN_LEAD : GIAI_DOAN_DU_AN).filter(s => s !== r.giai_doan);
  const giaiDoanNhan = phong !== 'SALES' ? GIAI_DOAN_THEO_PHONG[phong] : [];

  return (
    <li className="glass-card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{r.ten}</p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5 break-words">
            {[r.ma, r.khach && r.khach !== r.ten ? r.khach : null, r.dia_chi].filter(Boolean).join(' · ') || (laLead ? 'Lead' : '')}
          </p>
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            CRM ghi: <b>{nhanGiaiDoan(r.giai_doan)}</b>
            {r.pic ? ` · Phụ trách: ${r.pic.ten}` : laLead ? '' : ' · Chưa có người phụ trách'}
            {r.han_ban_giao ? ` · Hạn bàn giao ${ngayThang(r.han_ban_giao)}` : ''}
            {r.gia_tri ? ` · ${formatCurrency(r.gia_tri)}` : ''}
          </p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            {r.dau_vet_cuoi
              ? <>Dấu vết cuối: {baoLau(r.dau_vet_cuoi.luc)} · {nhanDauVet(r.dau_vet_cuoi.loai)}{r.dau_vet_cuoi.nguoi ? ` · ${r.dau_vet_cuoi.nguoi}` : ''}</>
              : 'CRM chưa có dấu vết'}
            {' · '}
            {r.doi_chieu_cuoi
              ? <>Đối chiếu cuối: {ngayThang(r.doi_chieu_cuoi.luc)}{r.doi_chieu_cuoi.ket_qua ? ` (${NHAN_KET_QUA[r.doi_chieu_cuoi.ket_qua] || r.doi_chieu_cuoi.ket_qua})` : ''}</>
              : 'chưa đối chiếu'}
          </p>
        </div>
        <Link href={linkHoSo(r.loai, r.id)} aria-label={`Mở ${tenDong(r)}`}
          className="inline-flex shrink-0 items-center justify-center w-11 h-11 rounded-full border border-[var(--border-default)]">
          <LineIcon name="eye" size={16} color="var(--text-secondary)" />
        </Link>
      </div>

      {tab === 'chua_xep' ? (doiGiaiDoanDuAn && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-[var(--text-muted)] mr-1">Nhận về giai đoạn:</span>
          {giaiDoanNhan.map(s => (
            <Chip key={s} chon={kq === 'sai_giai_doan' && chon?.giai_doan_moi === s}
              onClick={() => (kq === 'sai_giai_doan' && chon?.giai_doan_moi === s)
                ? onDat(null)
                : onDat({ ket_qua: 'sai_giai_doan', giai_doan_moi: s, ly_do: undefined })}>
              {nhanGiaiDoan(s)}
            </Chip>
          ))}
        </div>
      )) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            <Chip chon={kq === 'dung'} onClick={() => chonKetQua('dung')}>Đúng</Chip>
            {duocDoiGiaiDoan && <Chip chon={kq === 'sai_giai_doan'} onClick={() => chonKetQua('sai_giai_doan')}>Sai giai đoạn</Chip>}
            {!laLead && duocDoiGiaiDoan && <Chip chon={kq === 'tam_dung'} onClick={() => chonKetQua('tam_dung')}>Tạm dừng</Chip>}
            {!laLead && <Chip chon={kq === 'da_xong'} onClick={() => chonKetQua('da_xong')}>Đã xong</Chip>}
          </div>
          {kq === 'sai_giai_doan' && (
            <div className="flex flex-wrap items-center gap-1.5 pl-1">
              <span className="text-[11px] text-[var(--text-muted)] mr-1">Thực tế đang ở:</span>
              {luaChonGiaiDoan.map(s => (
                <Chip key={s} chon={chon?.giai_doan_moi === s} onClick={() => onDat({ giai_doan_moi: s })}>{nhanGiaiDoan(s)}</Chip>
              ))}
            </div>
          )}
          {kq === 'tam_dung' && (
            <input className="input text-sm min-h-[44px]" placeholder="Lý do tạm dừng (bắt buộc)" aria-label="Lý do tạm dừng"
              value={chon?.ly_do || ''} onChange={e => onDat({ ly_do: e.target.value })} />
          )}
        </>
      )}

      {/* Tab chưa xếp: chỉ chọn người phụ trách SAU khi chọn giai đoạn nhận về — chọn PIC
          mà chưa nhận dự án thì không có gì để gửi. */}
      {!laLead && nguoi.length > 0 && (tab === 'ho_so' || kq === 'sai_giai_doan') && (
        <select aria-label="Người phụ trách" value={chon?.pic_id || ''}
          onChange={e => {
            const v = e.target.value || undefined;
            // Chọn người phụ trách mà chưa chọn kết quả ⇒ coi dòng này «Đúng» (ở tab hồ sơ).
            if (v && !kq && tab === 'ho_so') onDat({ ket_qua: 'dung', pic_id: v });
            else onDat({ pic_id: v });
          }}
          className="input text-xs min-h-[44px]">
          <option value="">{r.pic ? `Giữ người phụ trách: ${r.pic.ten}` : 'Người phụ trách (không bắt buộc)'}</option>
          {nguoi.map(n => <option key={n.id} value={n.id}>{n.ten}</option>)}
        </select>
      )}
    </li>
  );
}

export default function DoiChieuPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><LineIcon name="hourglass" size={28} /></div>}>
      <DoiChieuNoiDung />
    </Suspense>
  );
}
