'use client';

// Vật tư Đợt 1 (25/10/2026): danh mục mẫu · phiếu chọn theo dự án · bảng «Cần hỏi giá».
// Giá vốn/NCC/lãi chỉ hiện khi backend trả thay_gia_von (Giám đốc, Thu mua, Trưởng phòng);
// sale/thiết kế không bao giờ nhận các cột đó trong JSON — FE chỉ vẽ cái có.

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api, mediaUrl, type CanThuongLuong, type DongVatTu, type GoiYNcc, type MauVatTu, type ShopeeSanPham, type PhieuVatTu, type Project, type VatTuTongQuan } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { tien } from '@/lib/tien-gon';
import { compressImage } from '@/lib/nhan-su';

// Bỏ dấu + thường hoá để tìm dự án không cần gõ dấu
const boDau = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

type Tab = 'danh-muc' | 'can-hoi-gia' | 'thuong-luong' | 'du-an' | 'dat-nhan' | 'cai-gia';

const MAU_TRANG_THAI: Record<string, string> = {
  khach_chon: '#F59E0B', hoi_ncc: '#3B82F6', het_hang: '#EF4444', cho_khach_duyet_lai: '#A78BFA',
  da_chot_gia: '#10B981', cho_duyet_dat: '#F97316', da_dat: '#06B6D4', giao_thieu: '#EF4444', da_giao: '#9CA3AF', huy: '#6B7280',
};

const inp = 'w-full rounded-xl px-3 py-2 text-base sm:text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--gold-400)]';
const btn = 'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium border transition-colors disabled:opacity-50';
const btnGold = `${btn} bg-[var(--gold-400)] text-black border-transparent hover:opacity-90`;
const btnGhost = `${btn} bg-transparent text-[var(--text-secondary)] border-[var(--border-default)] hover:text-[var(--text-primary)]`;
const loi = (e: unknown, mac: string) => (e instanceof Error && e.message ? e.message : mac);

function NhanTrangThai({ d }: { d: DongVatTu }) {
  const mau = MAU_TRANG_THAI[d.trang_thai] || '#9CA3AF';
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: `${mau}22`, color: mau }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: mau }} />
      {d.trang_thai_nhan}
    </span>
  );
}

function AnhMau({ url, size = 40 }: { url?: string | null; size?: number }) {
  const src = url ? mediaUrl(url) : '';
  if (!src || !/^https?:/.test(src)) {
    return <div className="rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0" style={{ width: size, height: size }}><LineIcon name="package" size={16} /></div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" className="rounded-lg object-cover shrink-0" style={{ width: size, height: size }} loading="lazy" />;
}

// Ô chọn dự án có tìm (mã/tên, không dấu); dự án có hoạt động 7 ngày gần nhất xếp lên đầu.
function ChonDuAn({ duAns, value, onChange }: { duAns: Project[]; value: string; onChange: (id: string) => void }) {
  const [q, setQ] = useState('');
  const [mo, setMo] = useState(false);
  const chon = duAns.find(p => p.id === value);
  // Mốc "7 ngày gần nhất" chốt 1 lần khi mở ô chọn (Date.now() không được gọi lúc render)
  const [moc] = useState(() => Date.now() - 7 * 86400_000);
  const { ganDay, conLai } = useMemo(() => {
    const k = boDau(q.trim());
    const loc = duAns.filter(p => !k || boDau(`${p.code} ${p.name}`).includes(k));
    const thoi = (p: Project) => new Date(p.updated_at || p.created_at || 0).getTime();
    const ganDay = loc.filter(p => thoi(p) >= moc).sort((a, b) => thoi(b) - thoi(a));
    const conLai = loc.filter(p => thoi(p) < moc).sort((a, b) => a.code.localeCompare(b.code));
    return { ganDay, conLai };
  }, [duAns, q, moc]);
  const Dong = ({ p }: { p: Project }) => (
    <button type="button" className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--surface-3)] ${p.id === value ? 'bg-[var(--surface-3)]' : ''}`}
      onClick={() => { onChange(p.id); setQ(''); setMo(false); }}>
      <span className="text-xs font-mono text-[var(--gold-400)] shrink-0">{p.code}</span>
      <span className="text-sm text-[var(--text-primary)] truncate">{p.name}</span>
    </button>
  );
  return (
    <div className="relative flex-1 min-w-[220px]">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"><LineIcon name="search" size={16} /></span>
      <input className={`${inp} pl-9 pr-8`} placeholder={chon ? `${chon.code} · ${chon.name}` : 'Tìm dự án theo mã hoặc tên…'}
        value={q} onFocus={() => setMo(true)} onBlur={() => setTimeout(() => setMo(false), 150)}
        onChange={e => { setQ(e.target.value); setMo(true); }} />
      {value && !q && (
        <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]" title="Bỏ chọn" onClick={() => { onChange(''); setMo(false); }}><LineIcon name="x" size={14} /></button>
      )}
      {mo && (
        <div className="absolute z-20 mt-1 w-full max-h-72 overflow-auto rounded-xl bg-[var(--surface-2)] border border-[var(--border-default)] shadow-xl">
          {ganDay.length > 0 && <div className="px-3 pt-2 pb-1 text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Gần đây (7 ngày)</div>}
          {ganDay.map(p => <Dong key={p.id} p={p} />)}
          {conLai.length > 0 && <div className="px-3 pt-2 pb-1 text-[11px] uppercase tracking-wide text-[var(--text-muted)]">{ganDay.length ? 'Dự án khác' : 'Tất cả dự án'}</div>}
          {conLai.map(p => <Dong key={p.id} p={p} />)}
          {ganDay.length + conLai.length === 0 && <div className="px-3 py-3 text-sm text-[var(--text-muted)]">Không có dự án khớp «{q}»</div>}
        </div>
      )}
    </div>
  );
}

export default function VatTuPage() {
  return (
    <Suspense fallback={<Sidebar><div className="p-6 text-[var(--text-muted)]">Đang tải…</div></Sidebar>}>
      <VatTuNoiDung />
    </Suspense>
  );
}

function VatTuNoiDung() {
  const sp = useSearchParams();
  const projectParam = sp.get('project');
  const { user } = useAuth();
  const laAdmin = user?.role === 'admin';
  const [tongQuan, setTongQuan] = useState<VatTuTongQuan | null>(null);
  const [tabChon, setTab] = useState<Tab | null>(null);
  const tab: Tab = tabChon ?? (sp.get('tab') === 'dat-nhan' ? 'dat-nhan' : projectParam ? 'du-an' : 'danh-muc');
  const [thongBao, setThongBao] = useState<{ loai: 'ok' | 'loi'; text: string } | null>(null);
  const bao = (loai: 'ok' | 'loi', text: string) => { setThongBao({ loai, text }); setTimeout(() => setThongBao(null), 4000); };

  useEffect(() => { api.vatTuTongQuan().then(setTongQuan).catch(() => setTongQuan(null)); }, [tab]);

  const thayGiaVon = !!tongQuan?.thay_gia_von;
  const laThuMua = !!tongQuan?.la_thu_mua;
  const qDatNhan: QuyenDatNhan = {
    laThuMua, laLeader: !!tongQuan?.la_leader_thu_mua, laGiamSat: !!tongQuan?.la_giam_sat,
    thayGiaVon, soAnh: tongQuan?.so_anh_toi_thieu ?? 2,
  };
  const soDatNhan = tongQuan ? (tongQuan.theo_trang_thai.cho_duyet_dat || 0) + (tongQuan.theo_trang_thai.da_dat || 0) + (tongQuan.theo_trang_thai.giao_thieu || 0) : 0;
  const choHoi = tongQuan ? (tongQuan.theo_trang_thai.khach_chon || 0) + (tongQuan.theo_trang_thai.hoi_ncc || 0) + (tongQuan.theo_trang_thai.het_hang || 0) + (tongQuan.theo_trang_thai.cho_khach_duyet_lai || 0) : 0;

  const tabs: { id: Tab; nhan: string; icon: string; so?: number; an?: boolean }[] = [
    { id: 'du-an', nhan: 'Phiếu dự án', icon: 'clipboard' },
    { id: 'danh-muc', nhan: 'Danh mục mẫu', icon: 'package', so: tongQuan?.so_mau },
    { id: 'can-hoi-gia', nhan: 'Cần hỏi giá', icon: 'receipt', so: choHoi, an: !thayGiaVon },
    { id: 'thuong-luong', nhan: 'Cần thương lượng', icon: 'handshake', an: !thayGiaVon },
    { id: 'dat-nhan', nhan: 'Đặt & nhận hàng', icon: 'truck', so: soDatNhan },
    { id: 'cai-gia', nhan: '% lãi theo nhóm', icon: 'percent', an: !laAdmin },
  ];

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold text-[var(--text-primary)] flex items-center gap-2"><LineIcon name="package" size={22} /> Vật tư</h1>
            <p className="text-sm text-[var(--text-muted)]">Khách chọn mẫu → Thu mua hỏi NCC → chốt giá bán. Chỉ Thu mua quyết định giá cuối.</p>
          </div>
          {thongBao && (
            <div className={`rounded-xl px-3 py-2 text-sm ${thongBao.loai === 'ok' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-red-500/15 text-red-300'}`}>{thongBao.text}</div>
          )}
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {tabs.filter(t => !t.an).map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`${btn} whitespace-nowrap ${tab === t.id ? 'bg-[var(--surface-3)] text-[var(--text-primary)] border-[var(--gold-400)]' : 'text-[var(--text-secondary)] border-[var(--border-subtle)]'}`}>
              <LineIcon name={t.icon} size={14} /> {t.nhan}
              {t.so !== undefined && t.so > 0 && <span className="ml-1 rounded-full bg-[var(--gold-400)]/20 text-[var(--gold-400)] px-1.5 text-xs">{t.so}</span>}
            </button>
          ))}
        </div>

        {tab === 'du-an' && <PhieuDuAn key={projectParam || ''} projectId={projectParam} thayGiaVon={thayGiaVon} laAdmin={laAdmin} q={qDatNhan} userId={user?.id} bao={bao} />}
        {tab === 'dat-nhan' && <DatNhanTab q={qDatNhan} bao={bao} />}
        {tab === 'danh-muc' && <DanhMuc thayGiaVon={thayGiaVon} laThuMua={laThuMua} bao={bao} />}
        {tab === 'can-hoi-gia' && thayGiaVon && <CanHoiGia laThuMua={laThuMua} bao={bao} />}
        {tab === 'thuong-luong' && thayGiaVon && <CanThuongLuongTab />}
        {tab === 'cai-gia' && laAdmin && <CaiGia bao={bao} />}
      </div>
    </Sidebar>
  );
}

// ───────────────────────── Danh mục mẫu ─────────────────────────
function DanhMuc({ thayGiaVon, laThuMua, bao }: { thayGiaVon: boolean; laThuMua: boolean; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [items, setItems] = useState<MauVatTu[]>([]);
  const [total, setTotal] = useState(0);
  const [nhoms, setNhoms] = useState<{ nhom: string; so_mau: number }[]>([]);
  const [q, setQ] = useState('');
  const [nhom, setNhom] = useState('');
  const [loading, setLoading] = useState(true);
  const [moImport, setMoImport] = useState(false);
  const [sheetUrl, setSheetUrl] = useState('');
  const [ghiDe, setGhiDe] = useState(false);
  const [dangImport, setDangImport] = useState(false);
  const [sua, setSua] = useState<Partial<MauVatTu> | null>(null);
  const [nhomMoi, setNhomMoi] = useState(false);
  const [dangTaiAnh, setDangTaiAnh] = useState(false);
  const [shopee, setShopee] = useState<MauVatTu | null>(null);

  const taiAnh = async (f: File | undefined) => {
    if (!f || !sua) return;
    setDangTaiAnh(true);
    try {
      const nen = await compressImage(f);
      if (!nen) throw new Error('Không đọc được ảnh — chọn JPG/PNG/WebP');
      const r = await api.vatTuTaiAnh(nen.base64);
      setSua(s => ({ ...s, anh_url: r.anh_url }));
      bao('ok', 'Đã tải ảnh');
    } catch (e) { bao('loi', loi(e, 'Không tải được ảnh')); }
    finally { setDangTaiAnh(false); }
  };
  const linkShopeeTim = (s: Partial<MauVatTu>) => `https://shopee.vn/search?keyword=${encodeURIComponent([s.hang, s.ma].filter(Boolean).join(' ') || 'gạch')}`;

  const tai = useCallback(async () => {
    setLoading(true);
    try {
      const p: Record<string, string> = { limit: '200' };
      if (q) p.q = q; if (nhom) p.nhom = nhom;
      const [r, n] = await Promise.all([api.vatTuMau(p), api.vatTuNhom()]);
      setItems(r.items); setTotal(r.total); setNhoms(n);
    } catch (e) { bao('loi', loi(e, 'Không tải được danh mục')); }
    finally { setLoading(false); }
  }, [q, nhom, bao]);
  useEffect(() => { const t = setTimeout(tai, 250); return () => clearTimeout(t); }, [tai]);

  const importSheet = async () => {
    if (!sheetUrl.trim()) return;
    setDangImport(true);
    try {
      const r = await api.vatTuImportSheet(sheetUrl.trim(), ghiDe);
      bao('ok', `Đọc ${r.doc_duoc} dòng · thêm ${r.them} · cập nhật ${r.sua}${r.ncc_moi ? ` · tạo ${r.ncc_moi} NCC mới` : ''}`);
      setMoImport(false); tai();
    } catch (e) { bao('loi', loi(e, 'Nhập sheet thất bại')); }
    finally { setDangImport(false); }
  };

  const luuMau = async () => {
    if (!sua?.ma?.trim()) { bao('loi', 'Cần mã mẫu'); return; }
    try {
      if (sua.id) await api.vatTuSuaMau(sua.id, sua); else await api.vatTuTaoMau(sua);
      bao('ok', 'Đã lưu mẫu'); setSua(null); tai();
    } catch (e) { bao('loi', loi(e, 'Không lưu được')); }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"><LineIcon name="search" size={16} /></span>
          <input className={`${inp} pl-9`} placeholder="Tìm mã, hãng, bề mặt…" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <select className={`${inp} w-auto`} value={nhom} onChange={e => setNhom(e.target.value)}>
          <option value="">Tất cả nhóm</option>
          {nhoms.map(n => <option key={n.nhom} value={n.nhom}>{n.nhom} ({n.so_mau})</option>)}
        </select>
        {laThuMua && (
          <>
            <button className={btnGhost} onClick={() => setMoImport(v => !v)}><LineIcon name="list" size={14} /> Nhập Google Sheet</button>
            <button className={btnGold} onClick={() => { setNhomMoi(false); setSua({ ma: '', nhom: nhom || nhoms[0]?.nhom || 'Khác', don_vi: 'm2', is_active: true }); }}><LineIcon name="plus" size={14} color="currentColor" /> Thêm mẫu</button>
          </>
        )}
      </div>

      {moImport && laThuMua && (
        <div className="glass-card p-4 space-y-2">
          <p className="text-sm text-[var(--text-secondary)]">Dán link Google Sheet đã chia sẻ «Bất kỳ ai có liên kết». Mỗi tab = một nhóm (30x30, 60x60…). Cột cần: MÃ, THƯƠNG HIỆU, HÌNH ẢNH, TÍNH CHẤT, TÌNH TRẠNG, ĐƠN GIÁ, NCC, GHI CHÚ.</p>
          <input className={inp} placeholder="https://docs.google.com/spreadsheets/d/…" value={sheetUrl} onChange={e => setSheetUrl(e.target.value)} />
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]"><input type="checkbox" checked={ghiDe} onChange={e => setGhiDe(e.target.checked)} /> Ghi đè mẫu đã có (hãng, ảnh, giá tham khảo)</label>
          <div className="flex gap-2"><button className={btnGold} disabled={dangImport} onClick={importSheet}>{dangImport ? 'Đang đọc…' : 'Nhập'}</button><button className={btnGhost} onClick={() => setMoImport(false)}>Đóng</button></div>
        </div>
      )}

      {sua && (
        <div className="glass-card p-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input className={inp} placeholder="Mã *" value={sua.ma || ''} onChange={e => setSua({ ...sua, ma: e.target.value })} />
          <input className={inp} placeholder="Hãng" value={sua.hang || ''} onChange={e => setSua({ ...sua, hang: e.target.value })} />
          {nhomMoi || (sua.nhom && !nhoms.some(n => n.nhom === sua.nhom) && sua.nhom !== 'Khác') ? (
            <div className="flex gap-1">
              <input className={inp} placeholder="Tên nhóm mới (30x30, 60x60…)" value={sua.nhom || ''} autoFocus onChange={e => setSua({ ...sua, nhom: e.target.value })} />
              <button type="button" className={btnGhost} title="Chọn nhóm có sẵn" onClick={() => { setNhomMoi(false); setSua({ ...sua, nhom: nhoms[0]?.nhom || 'Khác' }); }}><LineIcon name="list" size={14} /></button>
            </div>
          ) : (
            <select className={inp} value={sua.nhom || 'Khác'} onChange={e => { if (e.target.value === '__moi') { setNhomMoi(true); setSua({ ...sua, nhom: '' }); } else setSua({ ...sua, nhom: e.target.value }); }}>
              {!nhoms.some(n => n.nhom === 'Khác') && <option value="Khác">Khác</option>}
              {nhoms.map(n => <option key={n.nhom} value={n.nhom}>{n.nhom} ({n.so_mau})</option>)}
              <option value="__moi">+ Nhóm mới…</option>
            </select>
          )}
          <input className={inp} placeholder="Bề mặt / tính chất" value={sua.be_mat || ''} onChange={e => setSua({ ...sua, be_mat: e.target.value })} />
          <input className={inp} placeholder="Đơn vị" value={sua.don_vi || ''} onChange={e => setSua({ ...sua, don_vi: e.target.value })} />
          <div className="sm:col-span-3 flex flex-wrap gap-3 items-start">
            <AnhMau url={sua.anh_url} size={96} />
            <div className="flex-1 min-w-[220px] space-y-2">
              <input className={inp} placeholder="Link ảnh (dán vào là hiện ngay)" value={sua.anh_url || ''} onChange={e => setSua({ ...sua, anh_url: e.target.value })} />
              <div className="flex flex-wrap gap-2">
                <label className={`${btnGhost} cursor-pointer`}>
                  <LineIcon name="camera" size={14} /> {dangTaiAnh ? 'Đang tải…' : 'Tải ảnh lên'}
                  <input type="file" accept="image/*" className="hidden" disabled={dangTaiAnh} onChange={e => { taiAnh(e.target.files?.[0]); e.target.value = ''; }} />
                </label>
                <a className={btnGhost} href={sua.link_shopee || linkShopeeTim(sua)} target="_blank" rel="noopener noreferrer" title={sua.link_shopee ? 'Mở sản phẩm trên Shopee' : 'Tìm mẫu này trên Shopee để lấy ảnh & giá thị trường'}>
                  <LineIcon name="link" size={14} /> {sua.link_shopee ? 'Mở Shopee' : 'Tìm trên Shopee'}
                </a>
                {sua.anh_url && <button type="button" className={btnGhost} onClick={() => setSua({ ...sua, anh_url: '' })}><LineIcon name="x" size={14} /> Bỏ ảnh</button>}
              </div>
              <input className={inp} placeholder="Link Shopee sản phẩm (để so giá thị trường)" value={sua.link_shopee || ''} onChange={e => setSua({ ...sua, link_shopee: e.target.value })} />
            </div>
          </div>
          <input className={inp} type="number" placeholder="Giá tham khảo (vốn)" value={sua.gia_tham_khao ?? ''} onChange={e => setSua({ ...sua, gia_tham_khao: e.target.value ? Number(e.target.value) : null })} />
          <input className={inp} type="number" placeholder="Giá bán cố định (nếu có)" value={sua.gia_ban_co_dinh ?? ''} onChange={e => setSua({ ...sua, gia_ban_co_dinh: e.target.value ? Number(e.target.value) : null })} />
          <NccGoiY /><input className={inp} list="ds-ncc" placeholder="NCC quen — gõ để chọn NCC có sẵn" value={sua.ncc_gan_nhat_ten || ''} onChange={e => setSua({ ...sua, ncc_gan_nhat_ten: e.target.value })} />
          <input className={`${inp} sm:col-span-2`} placeholder="Ghi chú" value={sua.ghi_chu || ''} onChange={e => setSua({ ...sua, ghi_chu: e.target.value })} />
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]"><input type="checkbox" checked={sua.is_active !== false} onChange={e => setSua({ ...sua, is_active: e.target.checked })} /> Đang dùng</label>
          <div className="flex gap-2 sm:col-span-3"><button className={btnGold} onClick={luuMau}><LineIcon name="check" size={14} color="currentColor" /> Lưu</button><button className={btnGhost} onClick={() => setSua(null)}>Huỷ</button></div>
        </div>
      )}

      <div className="text-xs text-[var(--text-muted)]">{total} mẫu{nhom ? ` · nhóm ${nhom}` : ''}</div>
      {loading ? <div className="text-[var(--text-muted)] text-sm p-4">Đang tải…</div> : items.length === 0 ? (
        <div className="glass-card p-8 text-center text-[var(--text-muted)]">Chưa có mẫu nào.{laThuMua && ' Bấm «Nhập Google Sheet» để lấy danh mục của JAMA.'}</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {items.map(m => (
            <div key={m.id} className={`glass-card p-3 flex gap-3 ${m.is_active ? '' : 'opacity-50'}`}>
              <AnhMau url={m.anh_url} size={48} />
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm text-[var(--text-primary)] truncate" title={m.ma}>{m.ma}</div>
                <div className="text-xs text-[var(--text-muted)] truncate">{[m.hang, m.be_mat].filter(Boolean).join(' · ') || m.nhom}</div>
                <div className="text-xs text-[var(--text-secondary)]">{m.nhom}{m.tinh_trang ? ` · ${m.tinh_trang}` : ''}</div>
                {thayGiaVon && (m.gia_von_gan_nhat || m.gia_tham_khao) && (
                  <div className="text-xs text-[var(--gold-400)] mt-0.5">Vốn {tien(m.gia_von_gan_nhat || m.gia_tham_khao || 0)}{m.ncc_gan_nhat_ten ? ` · ${m.ncc_gan_nhat_ten}` : ''}
                    {m.gia_cu && <span className="ml-1 rounded-full bg-amber-500/15 text-amber-300 px-1.5" title="Giá khung quá 60 ngày — hỏi lại NCC trước khi đặt">giá cũ</span>}</div>
                )}
                <GiaShopee m={m} />
                {laThuMua && (
                  <div className="flex flex-wrap gap-x-3">
                    <button className="text-xs text-[var(--text-muted)] hover:text-[var(--gold-400)] mt-1 inline-flex items-center gap-1" onClick={() => setSua({ ...m })}><LineIcon name="edit" size={12} /> Sửa</button>
                    <button className="text-xs text-[var(--text-muted)] hover:text-[var(--gold-400)] mt-1 inline-flex items-center gap-1" onClick={() => setShopee(m)}><LineIcon name="search" size={12} /> Giá Shopee</button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {shopee && <ChonShopee mau={shopee} onDong={() => setShopee(null)}
        onXong={mm => { setItems(ds => ds.map(x => x.id === mm.id ? { ...x, ...mm } : x)); setShopee(null); bao('ok', mm.gia_shopee ? `Đã ghép giá Shopee ${tien(mm.gia_shopee)}` : 'Đã lưu'); }}
        bao={bao} />}
    </div>
  );
}

// ───────────────────────── Chọn mẫu (dùng chung) ─────────────────────────
function ChonMau({ onChon, placeholder = 'Gõ mã hoặc hãng…' }: { onChon: (m: MauVatTu | null, maTuDo: string) => void; placeholder?: string }) {
  const [q, setQ] = useState('');
  const [ds, setDs] = useState<MauVatTu[]>([]);
  const [mo, setMo] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => !q.trim() ? setDs([]) : api.vatTuMau({ q, limit: '12' }).then(r => setDs(r.items)).catch(() => setDs([])), 200);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div className="relative">
      <input className={inp} placeholder={placeholder} value={q} onFocus={() => setMo(true)}
        onChange={e => { setQ(e.target.value); setMo(true); onChon(null, e.target.value); }} />
      {mo && ds.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-64 overflow-auto rounded-xl bg-[var(--surface-2)] border border-[var(--border-default)] shadow-xl">
          {ds.map(m => (
            <button key={m.id} type="button" className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--surface-3)]"
              onClick={() => { onChon(m, m.ma); setQ(m.ma); setMo(false); }}>
              <AnhMau url={m.anh_url} size={32} />
              <div className="min-w-0"><div className="text-sm text-[var(--text-primary)] truncate">{m.ma}</div><div className="text-xs text-[var(--text-muted)] truncate">{[m.nhom, m.hang, m.be_mat].filter(Boolean).join(' · ')}</div></div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ───────────────────────── Phiếu dự án ─────────────────────────
function PhieuDuAn({ projectId, thayGiaVon, laAdmin, q, userId, bao }: { projectId: string | null; thayGiaVon: boolean; laAdmin: boolean; q: QuyenDatNhan; userId?: string; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [duAns, setDuAns] = useState<Project[]>([]);
  const [pid, setPid] = useState(projectId || '');
  const [phieu, setPhieu] = useState<PhieuVatTu | null>(null);
  const [loading, setLoading] = useState(false);
  const [moThem, setMoThem] = useState(false);
  const [form, setForm] = useState<{ phong: string; hang_muc: string; mau_id: string | null; ma_tu_do: string; so_luong: number; don_vi: string; ghi_chu: string; can_ngay: string }>({ phong: 'Chung', hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, don_vi: 'm2', ghi_chu: '', can_ngay: '' });
  const [dongY, setDongY] = useState<{ id: string; ghi_chu: string } | null>(null);

  useEffect(() => { api.getProjects({ page_size: '200' }).then(r => setDuAns(r.items || [])).catch(() => setDuAns([])); }, []);

  const tai = useCallback(async () => {
    setLoading(true);
    try { setPhieu(pid ? await api.vatTuPhieu(pid) : null); } catch (e) { bao('loi', loi(e, 'Không tải được phiếu')); setPhieu(null); }
    finally { setLoading(false); }
  }, [pid, bao]);
  useEffect(() => { void Promise.resolve().then(() => tai()); }, [tai]);

  const them = async () => {
    if (!form.mau_id && !form.ma_tu_do.trim()) { bao('loi', 'Chọn mẫu hoặc gõ mã'); return; }
    try {
      await api.vatTuThemDong(pid, { phong: form.phong || 'Chung', hang_muc: form.hang_muc || null, mau_id: form.mau_id, ma_tu_do: form.mau_id ? null : form.ma_tu_do, so_luong: form.so_luong, don_vi: form.don_vi, ghi_chu: form.ghi_chu || null, can_ngay: form.can_ngay || null });
      bao('ok', 'Đã thêm vào phiếu'); setMoThem(false); setForm(f => ({ ...f, hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, ghi_chu: '', can_ngay: '' })); tai();
    } catch (e) { bao('loi', loi(e, 'Không thêm được')); }
  };
  const xoa = async (d: DongVatTu) => {
    if (!confirm(`Xoá dòng ${d.ma || d.ma_tu_do}?`)) return;
    try { await api.vatTuXoaDong(d.id); tai(); } catch (e) { bao('loi', loi(e, 'Không xoá được')); }
  };
  const guiDongY = async () => {
    if (!dongY) return;
    try { await api.vatTuKhachDongY(dongY.id, dongY.ghi_chu); bao('ok', 'Đã ghi khách đồng ý'); setDongY(null); tai(); } catch (e) { bao('loi', loi(e, 'Không ghi được')); }
  };

  const theoPhong = useMemo(() => {
    const m = new Map<string, DongVatTu[]>();
    (phieu?.items || []).forEach(d => { const k = d.phong || 'Chung'; m.set(k, [...(m.get(k) || []), d]); });
    return [...m.entries()];
  }, [phieu]);
  const dsPhong = useMemo(() => Array.from(new Set(['Chung', 'Phòng khách', 'Bếp', 'Phòng ngủ 1', 'Phòng ngủ 2', 'WC 1', 'WC 2', 'Ban công', 'Sân', ...theoPhong.map(([p]) => p)])), [theoPhong]);
  const duAn = duAns.find(p => p.id === pid);
  // Giám sát phụ trách dự án (pm) cũng nhận hàng được dù không thuộc bộ phận Giám sát
  const qDuAn: QuyenDatNhan = { ...q, laGiamSat: q.laGiamSat || (!!userId && duAn?.pm_id === userId) };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <ChonDuAn duAns={duAns} value={pid} onChange={setPid} />
        {pid && <Link href={`/projects?id=${pid}`} className={btnGhost}><LineIcon name="eye" size={14} /> Mở dự án</Link>}
        {pid && <button className={btnGold} onClick={() => setMoThem(v => !v)}><LineIcon name="plus" size={14} color="currentColor" /> Khách chọn mẫu</button>}
      </div>

      {!pid && <div className="glass-card p-8 text-center text-[var(--text-muted)]">Chọn dự án để xem phiếu vật tư. Mỗi phòng một nhóm dòng: khách chọn → Thu mua hỏi NCC → chốt giá.</div>}

      {moThem && pid && (
        <div className="glass-card p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <input className={inp} list="ds-phong" placeholder="Phòng / khu vực" value={form.phong} onChange={e => setForm({ ...form, phong: e.target.value })} />
          <datalist id="ds-phong">{dsPhong.map(p => <option key={p} value={p} />)}</datalist>
          <input className={inp} placeholder="Hạng mục (sàn, tường, ốp bếp…)" value={form.hang_muc} onChange={e => setForm({ ...form, hang_muc: e.target.value })} />
          <div className="lg:col-span-2"><ChonMau onChon={(m, ma) => setForm(f => ({ ...f, mau_id: m?.id || null, ma_tu_do: ma, don_vi: m?.don_vi || f.don_vi }))} /></div>
          <input className={inp} type="number" min={0} step="0.1" placeholder="Số lượng" value={form.so_luong} onChange={e => setForm({ ...form, so_luong: Number(e.target.value) })} />
          <input className={inp} placeholder="Đơn vị" value={form.don_vi} onChange={e => setForm({ ...form, don_vi: e.target.value })} />
          <input className={`${inp} lg:col-span-2`} placeholder="Ghi chú cho Thu mua" value={form.ghi_chu} onChange={e => setForm({ ...form, ghi_chu: e.target.value })} />
          <label className="text-xs text-[var(--text-muted)] flex items-center gap-2">Cần có trước ngày
            <input className={inp} type="date" value={form.can_ngay} onChange={e => setForm({ ...form, can_ngay: e.target.value })} /></label>
          <div className="flex gap-2 sm:col-span-2 lg:col-span-4"><button className={btnGold} onClick={them}><LineIcon name="check" size={14} color="currentColor" /> Thêm dòng</button><button className={btnGhost} onClick={() => setMoThem(false)}>Đóng</button></div>
        </div>
      )}

      {pid && loading && <div className="text-sm text-[var(--text-muted)] p-4">Đang tải…</div>}
      {pid && !loading && phieu && (
        <>
          <div className="glass-card p-3 flex flex-wrap gap-4 text-sm">
            <div><span className="text-[var(--text-muted)]">Dự án</span> <span className="text-[var(--text-primary)] font-medium">{duAn ? `${duAn.code} · ${duAn.name}` : pid}</span></div>
            <div><span className="text-[var(--text-muted)]">Dòng</span> <span className="text-[var(--text-primary)] font-medium">{phieu.items.length}</span></div>
            <div><span className="text-[var(--text-muted)]">Tổng giá bán (đã chốt)</span> <span className="text-[var(--gold-400)] font-semibold">{tien(phieu.tong_gia_ban)}</span></div>
            {thayGiaVon && phieu.tong_lai !== undefined && <div><span className="text-[var(--text-muted)]">Lãi dự kiến</span> <span className="text-emerald-400 font-semibold">{tien(phieu.tong_lai)}</span></div>}
          </div>
          {phieu.items.length === 0 && <div className="glass-card p-8 text-center text-[var(--text-muted)]">Chưa có dòng nào. Bấm «Khách chọn mẫu» khi ngồi cùng khách.</div>}
          {theoPhong.map(([phong, ds]) => (
            <div key={phong} className="glass-card overflow-hidden">
              <div className="px-4 py-2 text-sm font-semibold text-[var(--text-primary)] bg-[var(--surface-2)] border-b border-[var(--border-subtle)]">{phong} <span className="text-[var(--text-muted)] font-normal">· {ds.length} dòng</span></div>
              <div className="divide-y divide-[var(--border-subtle)]">
                {ds.map(d => (
                  <div key={d.id} className="p-3 flex gap-3">
                    <AnhMau url={d.anh_url} size={44} />
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-[var(--text-primary)]">{d.ma || d.ma_tu_do}</span>
                        {d.hang && <span className="text-xs text-[var(--text-muted)]">{d.hang}</span>}
                        {d.nhom && <span className="text-xs rounded-full bg-[var(--surface-3)] px-2 text-[var(--text-secondary)]">{d.nhom}</span>}
                        <NhanTrangThai d={d} />
                      </div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {d.hang_muc && <span>{d.hang_muc} · </span>}{d.so_luong} {d.don_vi}
                        {d.gia_ban != null && <> · <span className="text-[var(--gold-400)]">{tien(d.gia_ban)}/{d.don_vi}</span> = <span className="text-[var(--text-primary)] font-medium">{tien(d.thanh_tien || 0)}</span></>}
                        {thayGiaVon && d.gia_von != null && <span className="text-[var(--text-muted)]"> · vốn {tien(d.gia_von)}{d.ncc_ten ? ` (${d.ncc_ten})` : ''}{d.phan_tram_ap_dung != null ? ` · +${d.phan_tram_ap_dung}%` : ' · giá cố định'}</span>}
                      </div>
                      {(d.trang_thai === 'het_hang' || d.trang_thai === 'cho_khach_duyet_lai') && (
                        <div className="text-xs rounded-lg bg-red-500/10 text-red-300 px-2 py-1 flex items-start gap-1"><LineIcon name="alert" size={12} /> Hết hàng. Đề xuất thay: <b>{d.ma_thay_the || '—'}</b>{d.ly_do_doi ? ` — ${d.ly_do_doi}` : ''}. Cần khách duyệt lại.</div>
                      )}
                      {d.khach_dong_y_luc && <div className="text-xs text-emerald-400">Khách đồng ý {new Date(d.khach_dong_y_luc).toLocaleDateString('vi-VN')}{d.khach_ghi_chu ? ` — ${d.khach_ghi_chu}` : ''}</div>}
                      {d.can_ngay && <div className="text-xs text-amber-300">Cần trước {new Date(d.can_ngay).toLocaleDateString('vi-VN')}</div>}
                      {d.ghi_chu && <div className="text-xs text-[var(--text-muted)]">{d.ghi_chu}</div>}
                      <ThongTinDatNhan d={d} />
                      <HanhDongDatNhan d={d} q={qDuAn} xong={() => tai()} bao={bao} />
                      {dongY?.id === d.id && (
                        <div className="flex gap-2 pt-1">
                          <input className={inp} autoFocus placeholder="Ghi chú (khách nói gì, qua kênh nào)" value={dongY.ghi_chu} onChange={e => setDongY({ ...dongY, ghi_chu: e.target.value })} />
                          <button className={btnGold} onClick={guiDongY}>Ghi</button><button className={btnGhost} onClick={() => setDongY(null)}>Huỷ</button>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col gap-1 items-end shrink-0">
                      {!d.khach_dong_y_luc && ['khach_chon', 'het_hang', 'cho_khach_duyet_lai'].includes(d.trang_thai) && dongY?.id !== d.id && (
                        <button className={`${btn} text-xs text-emerald-300 border-emerald-500/40`} onClick={() => setDongY({ id: d.id, ghi_chu: '' })}><LineIcon name="tick" size={12} /> Khách đã đồng ý</button>
                      )}
                      {(laAdmin || !['da_chot_gia', 'cho_duyet_dat', 'da_dat', 'giao_thieu', 'da_giao'].includes(d.trang_thai)) && (
                        <button className="text-[var(--text-muted)] hover:text-red-400 p-1" title="Xoá" onClick={() => xoa(d)}><LineIcon name="trash" size={14} /></button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ───────── Đặt hàng – Leader Thu mua duyệt – Giám sát nhận hàng (13/11/2026) ─────────
// Luật: mọi đơn đối chiếu khối lượng + đơn giá báo giá; trong báo giá tự qua, vượt bất kỳ
// mức nào (kể cả đội ngân sách dự án) → Leader Thu mua duyệt. Hàng về: Giám sát xác nhận
// đủ/thiếu kèm tối thiểu 2 ảnh hiện trường (server kiểm lại). Thu mua chỉ xem.
type QuyenDatNhan = { laThuMua: boolean; laLeader: boolean; laGiamSat: boolean; thayGiaVon: boolean; soAnh: number };

const ngayGio = (s?: string | null) => (s ? new Date(s).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

async function anhSangBlob(f: File): Promise<Blob> {
  const nen = await compressImage(f).catch(() => null);
  if (!nen) return f;
  return (await fetch(`data:${nen.mime};base64,${nen.base64}`)).blob();
}

/** Thông tin đặt/nhận của một dòng: ai đặt, vượt gì, bị từ chối vì sao, nhận đủ/thiếu + ảnh. */
function ThongTinDatNhan({ d }: { d: DongVatTu }) {
  return (
    <>
      {d.gia_cu && <div className="text-xs rounded-lg bg-amber-500/10 text-amber-300 px-2 py-1 flex items-start gap-1"><LineIcon name="hourglass" size={12} /> Giá cũ — chốt đã quá 60 ngày, hỏi lại NCC và chốt lại trước khi đặt.</div>}
      {d.tu_choi_dat_ly_do && d.trang_thai === 'da_chot_gia' && <div className="text-xs rounded-lg bg-red-500/10 text-red-300 px-2 py-1 flex items-start gap-1"><LineIcon name="x" size={12} /> Leader từ chối đơn trước: {d.tu_choi_dat_ly_do}</div>}
      {d.dat_luc && ['cho_duyet_dat', 'da_dat', 'giao_thieu', 'da_giao'].includes(d.trang_thai) && (
        <div className="text-xs text-[var(--text-secondary)]">
          Đặt {d.sl_dat ?? d.so_luong} {d.don_vi}{d.gia_dat != null ? ` × ${tien(d.gia_dat)}` : ''} · {d.dat_boi_ten || '—'} · {ngayGio(d.dat_luc)}
          {d.duyet_dat_boi_ten && <span className="text-emerald-400"> · {d.duyet_dat_boi_ten} duyệt</span>}
        </div>
      )}
      {d.ly_do_vuot && d.trang_thai === 'cho_duyet_dat' && <div className="text-xs rounded-lg bg-orange-500/10 text-orange-300 px-2 py-1 flex items-start gap-1"><LineIcon name="alert" size={12} /> Vượt báo giá: {d.ly_do_vuot}</div>}
      {d.nhan_luc && (
        <div className={`text-xs ${d.nhan_ket_qua === 'thieu' ? 'text-red-300' : 'text-emerald-400'}`}>
          {d.nhan_ket_qua === 'thieu' ? `Giao thiếu${d.sl_nhan != null ? ` (nhận ${d.sl_nhan}/${d.sl_dat ?? d.so_luong} ${d.don_vi})` : ''}` : 'Hàng về đủ'} · {d.nhan_boi_ten || '—'} · {ngayGio(d.nhan_luc)}{d.nhan_ghi_chu ? ` — ${d.nhan_ghi_chu}` : ''}
        </div>
      )}
      {!!d.nhan_anh?.length && (
        <div className="flex gap-1.5 flex-wrap">
          {d.nhan_anh.map(a => (
            <a key={a.id} href={mediaUrl(a.url)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={mediaUrl(a.url)} alt="Ảnh nhận hàng" className="w-12 h-12 rounded-lg object-cover" loading="lazy" />
            </a>
          ))}
        </div>
      )}
    </>
  );
}

/** Nút + ô nhập cho bước đặt/duyệt/nhận của một dòng. Trả null khi người xem không có việc gì ở dòng này. */
function HanhDongDatNhan({ d, q, xong, bao }: { d: DongVatTu; q: QuyenDatNhan; xong: (d: DongVatTu) => void; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [mo, setMo] = useState<'dat' | 'tu_choi' | 'nhan' | null>(null);
  const [sl, setSl] = useState(String(d.so_luong));
  const [gia, setGia] = useState(d.gia_von != null ? String(d.gia_von) : '');
  const [lyDo, setLyDo] = useState('');
  const [ketQua, setKetQua] = useState<'du' | 'thieu'>('du');
  const [slNhan, setSlNhan] = useState('');
  const [ghiChu, setGhiChu] = useState('');
  const [anh, setAnh] = useState<File[]>([]);
  const [dangGui, setDangGui] = useState(false);
  const xem = useMemo(() => anh.map(f => URL.createObjectURL(f)), [anh]);
  useEffect(() => () => xem.forEach(u => URL.revokeObjectURL(u)), [xem]);

  const chay = async (fn: () => Promise<DongVatTu>, ok: string) => {
    setDangGui(true);
    try { const moi = await fn(); bao('ok', ok); setMo(null); setAnh([]); xong(moi); }
    catch (e) { bao('loi', loi(e, 'Không ghi được')); }
    finally { setDangGui(false); }
  };

  const slSo = Number(sl.replace(',', '.')) || 0;
  const giaSo = Number(gia.replace(/\D/g, '')) || 0;
  const vuotTruoc = [
    slSo > d.so_luong ? `khối lượng ${slSo} > báo giá ${d.so_luong}` : '',
    q.thayGiaVon && d.gia_von != null && giaSo > d.gia_von ? `đơn giá ${tien(giaSo)} > ${tien(d.gia_von)}` : '',
  ].filter(Boolean);

  const datHang = () => chay(() => api.vatTuDatHang(d.id, {
    so_luong: slSo && slSo !== d.so_luong ? slSo : null,
    don_gia: q.thayGiaVon && giaSo && giaSo !== d.gia_von ? giaSo : null,
  }), 'Đã gửi đơn đặt hàng');

  const nhanHang = () => chay(async () => {
    const blobs = await Promise.all(anh.map(anhSangBlob));
    const up = await api.uploadMediaBatch(blobs, { projectId: d.project_id, kind: 'vat_tu', caption: `Nhận hàng ${d.ma || d.ma_tu_do || ''} · ${d.phong}` });
    return api.vatTuNhanHang(d.id, {
      ket_qua: ketQua, so_luong_nhan: ketQua === 'thieu' && slNhan ? Number(slNhan.replace(',', '.')) : null,
      ghi_chu: ghiChu.trim(), anh_ids: up.items.map(x => x.id),
    });
  }, ketQua === 'du' ? 'Đã xác nhận hàng về đủ' : 'Đã báo hàng về thiếu');

  const nutDat = q.laThuMua && d.trang_thai === 'da_chot_gia';
  const nutDuyet = q.laLeader && d.trang_thai === 'cho_duyet_dat';
  const nutNhan = q.laGiamSat && ['da_dat', 'giao_thieu'].includes(d.trang_thai);
  if (!nutDat && !nutDuyet && !nutNhan) return null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {nutDat && mo !== 'dat' && <button className={`${btn} text-xs`} disabled={!!d.gia_cu} title={d.gia_cu ? 'Giá cũ — chốt lại giá trước' : ''} onClick={() => setMo('dat')}><LineIcon name="receipt" size={12} /> Đặt hàng</button>}
        {nutDuyet && mo !== 'tu_choi' && <>
          <button className={`${btn} text-xs text-emerald-300 border-emerald-500/40`} disabled={dangGui} onClick={() => chay(() => api.vatTuDuyetDat(d.id, true), 'Đã duyệt đơn')}><LineIcon name="tick" size={12} /> Duyệt đơn</button>
          <button className={`${btn} text-xs text-red-300 border-red-500/40`} onClick={() => setMo('tu_choi')}><LineIcon name="x" size={12} /> Từ chối</button>
        </>}
        {nutNhan && mo !== 'nhan' && <button className={`${btn} text-xs text-[var(--gold-400)] border-[var(--gold-400)]/50`} onClick={() => setMo('nhan')}><LineIcon name="truck" size={12} /> {d.trang_thai === 'giao_thieu' ? 'Nhận bù hàng' : 'Nhận hàng'}</button>}
      </div>

      {mo === 'dat' && (
        <div className="rounded-xl bg-[var(--surface-2)] p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-[var(--text-muted)]">Khối lượng ({d.don_vi}) — báo giá {d.so_luong}
              <input className={inp} inputMode="decimal" value={sl} onChange={e => setSl(e.target.value)} /></label>
            {q.thayGiaVon && d.gia_von != null && (
              <label className="text-xs text-[var(--text-muted)]">Đơn giá — đã chốt {tien(d.gia_von)}
                <input className={inp} inputMode="numeric" value={gia} onChange={e => setGia(e.target.value)} /></label>
            )}
          </div>
          <div className={`text-xs ${vuotTruoc.length ? 'text-orange-300' : 'text-emerald-400'}`}>
            {vuotTruoc.length ? `Vượt báo giá (${vuotTruoc.join(', ')}) → gửi Leader Thu mua duyệt.` : 'Nằm trong báo giá → đặt luôn (nếu không đội ngân sách dự án).'}
          </div>
          <div className="flex gap-2"><button className={btnGold} disabled={dangGui || slSo <= 0} onClick={datHang}>{dangGui ? 'Đang gửi…' : 'Xác nhận đặt'}</button><button className={btnGhost} onClick={() => setMo(null)}>Huỷ</button></div>
        </div>
      )}

      {mo === 'tu_choi' && (
        <div className="rounded-xl bg-[var(--surface-2)] p-3 space-y-2">
          <input className={inp} autoFocus placeholder="Lý do từ chối (Thu mua sửa theo đó)" value={lyDo} onChange={e => setLyDo(e.target.value)} />
          <div className="flex gap-2"><button className={btnGold} disabled={dangGui || !lyDo.trim()} onClick={() => chay(() => api.vatTuDuyetDat(d.id, false, lyDo.trim()), 'Đã trả đơn về Thu mua')}>Gửi từ chối</button><button className={btnGhost} onClick={() => setMo(null)}>Huỷ</button></div>
        </div>
      )}

      {mo === 'nhan' && (
        <div className="rounded-xl bg-[var(--surface-2)] p-3 space-y-2">
          <div className="flex gap-2">
            {(['du', 'thieu'] as const).map(k => (
              <button key={k} className={`${btn} text-xs ${ketQua === k ? (k === 'du' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/50' : 'bg-red-500/15 text-red-300 border-red-500/50') : 'text-[var(--text-secondary)] border-[var(--border-subtle)]'}`} onClick={() => setKetQua(k)}>
                {k === 'du' ? 'Đủ hàng' : 'Thiếu hàng'}
              </button>
            ))}
          </div>
          {ketQua === 'thieu' && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input className={inp} inputMode="decimal" placeholder={`Nhận được bao nhiêu ${d.don_vi}`} value={slNhan} onChange={e => setSlNhan(e.target.value)} />
              <input className={`${inp} sm:col-span-2`} placeholder="Thiếu gì, bao nhiêu (bắt buộc)" value={ghiChu} onChange={e => setGhiChu(e.target.value)} />
            </div>
          )}
          {ketQua === 'du' && <input className={inp} placeholder="Ghi chú (không bắt buộc)" value={ghiChu} onChange={e => setGhiChu(e.target.value)} />}
          <label className={`${btnGhost} text-xs cursor-pointer w-fit`}>
            <LineIcon name="camera" size={12} /> Chụp / chọn ảnh hiện trường
            <input type="file" accept="image/*" capture="environment" multiple className="hidden"
              onChange={e => { const fs = Array.from(e.target.files || []); setAnh(a => [...a, ...fs].slice(0, 10)); e.target.value = ''; }} />
          </label>
          {xem.length > 0 && (
            <div className="flex gap-1.5 flex-wrap">
              {xem.map((u, i) => (
                <div key={u} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt="" className="w-14 h-14 rounded-lg object-cover" />
                  <button className="absolute -top-1 -right-1 rounded-full bg-black/70 p-0.5" aria-label="Bỏ ảnh" onClick={() => setAnh(a => a.filter((_, j) => j !== i))}><LineIcon name="x" size={10} /></button>
                </div>
              ))}
            </div>
          )}
          <div className={`text-xs ${anh.length >= q.soAnh ? 'text-emerald-400' : 'text-amber-300'}`}>{anh.length}/{q.soAnh} ảnh tối thiểu — ảnh vào Kho ảnh dự án.</div>
          <div className="flex gap-2">
            <button className={btnGold} disabled={dangGui || anh.length < q.soAnh || (ketQua === 'thieu' && !ghiChu.trim())} onClick={nhanHang}>{dangGui ? 'Đang tải ảnh…' : 'Xác nhận'}</button>
            <button className={btnGhost} onClick={() => { setMo(null); setAnh([]); }}>Huỷ</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Hai hàng chờ: đơn vượt chờ Leader duyệt · hàng đã đặt chờ Giám sát nhận. */
function DatNhanTab({ q, bao }: { q: QuyenDatNhan; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [data, setData] = useState<{ cho_duyet: DongVatTu[]; cho_nhan: DongVatTu[] } | null>(null);
  const tai = useCallback(() => { api.vatTuViecDatNhan().then(setData).catch(e => { bao('loi', loi(e, 'Không tải được')); setData({ cho_duyet: [], cho_nhan: [] }); }); }, [bao]);
  useEffect(() => { tai(); }, [tai]);
  if (!data) return <div className="text-sm text-[var(--text-muted)] p-4">Đang tải…</div>;
  const khoi = (tieuDe: string, ds: DongVatTu[], rong: string, qq: QuyenDatNhan) => (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-2 text-sm font-semibold text-[var(--text-primary)] bg-[var(--surface-2)] border-b border-[var(--border-subtle)]">{tieuDe} <span className="text-[var(--text-muted)] font-normal">· {ds.length}</span></div>
      {ds.length === 0 && <div className="p-4 text-sm text-[var(--text-muted)]">{rong}</div>}
      <div className="divide-y divide-[var(--border-subtle)]">
        {ds.map(d => (
          <div key={d.id} className="p-3 flex gap-3">
            <AnhMau url={d.anh_url} size={44} />
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-[var(--text-primary)]">{d.ma || d.ma_tu_do}</span>
                <NhanTrangThai d={d} />
                <Link href={`/vat-tu?project=${d.project_id}`} className="text-xs text-[var(--gold-400)] hover:underline">{d.project_code} · {d.project_name}</Link>
              </div>
              <div className="text-xs text-[var(--text-secondary)]">{d.phong}{d.hang_muc ? ` · ${d.hang_muc}` : ''} · báo giá {d.so_luong} {d.don_vi}</div>
              <ThongTinDatNhan d={d} />
              <HanhDongDatNhan d={d} q={qq} xong={tai} bao={bao} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
  return (
    <div className="space-y-3">
      {(q.laLeader || data.cho_duyet.length > 0) && khoi('Đơn vượt báo giá chờ Leader Thu mua duyệt', data.cho_duyet, 'Không có đơn nào chờ duyệt.', { ...q, laGiamSat: false })}
      {khoi('Hàng đã đặt, chờ Giám sát nhận tại công trình', data.cho_nhan, 'Không có hàng nào đang chờ nhận.', { ...q, laLeader: false, laThuMua: false })}
    </div>
  );
}

// ───────────────────────── Cần hỏi giá (Thu mua) ─────────────────────────
function CanHoiGia({ laThuMua, bao }: { laThuMua: boolean; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [items, setItems] = useState<DongVatTu[]>([]);
  const [loading, setLoading] = useState(true);
  const [mo, setMo] = useState<string | null>(null);
  const [bg, setBg] = useState({ ncc_ten: '', gia: '', con_hang: true, ngay_giao: '', ghi_chu: '' });
  const [hetHang, setHetHang] = useState<{ id: string; ma_thay_the: string; mau_thay_the_id: string | null; ly_do: string } | null>(null);
  const [giaTay, setGiaTay] = useState<{ id: string; gia_von: string; ncc_ten: string } | null>(null);

  const tai = useCallback(async () => {
    setLoading(true);
    try { setItems((await api.vatTuCanHoiGia()).items); } catch (e) { bao('loi', loi(e, 'Không tải được')); }
    finally { setLoading(false); }
  }, [bao]);
  useEffect(() => { void Promise.resolve().then(() => tai()); }, [tai]);

  const themBaoGia = async (id: string) => {
    if (!bg.ncc_ten.trim() || !bg.gia) { bao('loi', 'Cần tên NCC và giá'); return; }
    try {
      await api.vatTuThemBaoGia(id, { ncc_ten: bg.ncc_ten.trim(), gia: Number(bg.gia), con_hang: bg.con_hang, ngay_giao: bg.ngay_giao || undefined, ghi_chu: bg.ghi_chu || undefined });
      setBg({ ncc_ten: '', gia: '', con_hang: true, ngay_giao: '', ghi_chu: '' }); tai();
    } catch (e) { bao('loi', loi(e, 'Không thêm được báo giá')); }
  };
  const chot = async (id: string, bao_gia_id: string) => {
    try { const d = await api.vatTuChot(id, { bao_gia_id }); bao('ok', `Đã chốt — giá bán ${tien(d.gia_ban || 0)}/${d.don_vi}`); setMo(null); tai(); }
    catch (e) { bao('loi', loi(e, 'Không chốt được')); }
  };
  const chotTay = async () => {
    if (!giaTay || !giaTay.gia_von) return;
    try { const d = await api.vatTuChot(giaTay.id, { gia_von: Number(giaTay.gia_von), ncc_ten: giaTay.ncc_ten || undefined }); bao('ok', `Đã chốt — giá bán ${tien(d.gia_ban || 0)}/${d.don_vi}`); setGiaTay(null); tai(); }
    catch (e) { bao('loi', loi(e, 'Không chốt được')); }
  };
  const baoHetHang = async () => {
    if (!hetHang || !hetHang.ma_thay_the.trim()) { bao('loi', 'Cần mã thay thế'); return; }
    try {
      await api.vatTuSuaDong(hetHang.id, { trang_thai: 'het_hang', ma_thay_the: hetHang.ma_thay_the, mau_thay_the_id: hetHang.mau_thay_the_id, ly_do_doi: hetHang.ly_do || null });
      bao('ok', 'Đã báo hết hàng, chờ khách duyệt lại'); setHetHang(null); tai();
    } catch (e) { bao('loi', loi(e, 'Không ghi được')); }
  };

  if (loading) return <div className="text-sm text-[var(--text-muted)] p-4">Đang tải…</div>;
  if (items.length === 0) return <div className="glass-card p-8 text-center text-[var(--text-muted)]">Không có dòng nào chờ hỏi giá.</div>;

  return (
    <div className="space-y-2">
      {items.map(d => {
        const bgs = [...(d.bao_gia || [])].sort((a, b) => a.gia - b.gia);
        const dangMo = mo === d.id;
        return (
          <div key={d.id} className="glass-card overflow-hidden">
            <button type="button" className="w-full p-3 flex gap-3 text-left" onClick={() => setMo(dangMo ? null : d.id)}>
              <AnhMau url={d.anh_url} size={44} />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-[var(--text-primary)]">{d.ma || d.ma_tu_do}</span>
                  {d.hang && <span className="text-xs text-[var(--text-muted)]">{d.hang}</span>}
                  <NhanTrangThai d={d} />
                  {d.khach_dong_y_luc && <span className="text-xs text-emerald-400">khách đã đồng ý</span>}
                </div>
                <div className="text-xs text-[var(--text-secondary)]">
                  <Link href={`/vat-tu?project=${d.project_id}`} className="hover:text-[var(--gold-400)]" onClick={e => e.stopPropagation()}>{d.project_code} · {d.project_name}</Link>
                  {d.client_name && <> · {d.client_name}</>} · {d.phong}{d.hang_muc ? ` · ${d.hang_muc}` : ''} · {d.so_luong} {d.don_vi}
                </div>
                <div className="text-xs text-[var(--text-muted)]">
                  {d.gia_shopee ? <span className="text-orange-300">Shopee {tien(d.gia_shopee)} · </span> : null}
                  {d.so_bao_gia} báo giá{d.gia_von_gan_nhat ? ` · giá gần nhất ${tien(d.gia_von_gan_nhat)}` : d.gia_tham_khao ? ` · tham khảo ${tien(d.gia_tham_khao)}` : ''}
                  {d.can_ngay && <> · <span className="text-amber-300">cần trước {new Date(d.can_ngay).toLocaleDateString('vi-VN')}</span></>}
                  {d.ghi_chu && <> · {d.ghi_chu}</>}
                </div>
              </div>
            </button>
            {dangMo && (
              <div className="border-t border-[var(--border-subtle)] p-3 space-y-3 bg-[var(--surface-1)]">
                {d.mau_id && <GoiYNccKhoi mauId={d.mau_id} />}
                {bgs.length > 0 && (
                  <div className="space-y-1">
                    {bgs.map((b, i) => (
                      <div key={b.id} className={`flex flex-wrap items-center gap-2 rounded-lg px-3 py-2 text-sm ${i === 0 ? 'bg-emerald-500/10' : 'bg-[var(--surface-2)]'}`}>
                        <span className="font-medium text-[var(--text-primary)]">{b.ncc_ten}</span>
                        <span className="text-[var(--gold-400)] font-semibold">{tien(b.gia)}</span>
                        {i === 0 && <span className="text-xs text-emerald-400">rẻ nhất</span>}
                        {!b.con_hang && <span className="text-xs text-red-300">hết hàng</span>}
                        {b.cao_hon_shopee && d.gia_shopee && <span className="text-xs rounded-full px-2 py-0.5 bg-red-500/15 text-red-300">cao hơn Shopee {Math.round((b.gia / d.gia_shopee - 1) * 100)}%</span>}
                        {b.ngay_giao && <span className="text-xs text-[var(--text-muted)]">giao {b.ngay_giao}</span>}
                        {b.ghi_chu && <span className="text-xs text-[var(--text-muted)]">{b.ghi_chu}</span>}
                        <span className="flex-1" />
                        {laThuMua && b.con_hang && <button className={`${btnGold} text-xs`} onClick={() => chot(d.id, b.id)}><LineIcon name="check" size={12} color="currentColor" /> Chốt giá này</button>}
                        {laThuMua && <button className="text-[var(--text-muted)] hover:text-red-400 p-1" onClick={async () => { await api.vatTuXoaBaoGia(b.id).catch(() => null); tai(); }}><LineIcon name="trash" size={12} /></button>}
                      </div>
                    ))}
                  </div>
                )}
                {laThuMua && (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      <NccGoiY /><input className={inp} list="ds-ncc" placeholder="Tên NCC *" value={bg.ncc_ten} onChange={e => setBg({ ...bg, ncc_ten: e.target.value })} />
                      <input className={inp} type="number" placeholder={`Giá vốn/${d.don_vi} *`} value={bg.gia} onChange={e => setBg({ ...bg, gia: e.target.value })} />
                      <input className={inp} placeholder="Giao (vd 3 ngày)" value={bg.ngay_giao} onChange={e => setBg({ ...bg, ngay_giao: e.target.value })} />
                      <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)] px-1"><input type="checkbox" checked={bg.con_hang} onChange={e => setBg({ ...bg, con_hang: e.target.checked })} /> Còn hàng</label>
                      <button className={btnGhost} onClick={() => themBaoGia(d.id)}><LineIcon name="plus" size={14} /> Thêm báo giá</button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {giaTay?.id === d.id ? (
                        <>
                          <input className={`${inp} w-40`} type="number" placeholder="Giá vốn" value={giaTay.gia_von} onChange={e => setGiaTay({ ...giaTay, gia_von: e.target.value })} />
                          <input className={`${inp} w-48`} list="ds-ncc" placeholder="NCC" value={giaTay.ncc_ten} onChange={e => setGiaTay({ ...giaTay, ncc_ten: e.target.value })} />
                          <button className={btnGold} onClick={chotTay}>Chốt</button><button className={btnGhost} onClick={() => setGiaTay(null)}>Huỷ</button>
                        </>
                      ) : (
                        <button className={`${btnGhost} text-xs`} onClick={() => setGiaTay({ id: d.id, gia_von: String(d.gia_von_gan_nhat || d.gia_tham_khao || ''), ncc_ten: '' })}>Chốt nhanh theo giá vốn</button>
                      )}
                      {d.trang_thai !== 'het_hang' && d.trang_thai !== 'cho_khach_duyet_lai' && (
                        hetHang?.id === d.id ? (
                          <div className="flex flex-wrap gap-2 w-full">
                            <div className="flex-1 min-w-[200px]"><ChonMau placeholder="Mã thay thế *" onChon={(m, ma) => setHetHang(h => h && { ...h, ma_thay_the: ma, mau_thay_the_id: m?.id || null })} /></div>
                            <input className={`${inp} flex-1 min-w-[160px]`} placeholder="Lý do" value={hetHang.ly_do} onChange={e => setHetHang({ ...hetHang, ly_do: e.target.value })} />
                            <button className={btnGold} onClick={baoHetHang}>Gửi đề xuất</button><button className={btnGhost} onClick={() => setHetHang(null)}>Huỷ</button>
                          </div>
                        ) : (
                          <button className={`${btnGhost} text-xs text-red-300`} onClick={() => setHetHang({ id: d.id, ma_thay_the: '', mau_thay_the_id: null, ly_do: '' })}><LineIcon name="alert" size={12} /> Hết hàng / đề xuất thay</button>
                        )
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ───────────────────────── % lãi theo nhóm (admin) ─────────────────────────
function CaiGia({ bao }: { bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [ds, setDs] = useState<{ nhom: string; phan_tram_lai: number }[]>([]);
  const [moi, setMoi] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.vatTuCaiGia().then(setDs).catch(e => bao('loi', loi(e, 'Không tải được'))); }, [bao]);
  const luu = async () => {
    setSaving(true);
    try { await api.vatTuLuuCaiGia(ds); bao('ok', 'Đã lưu % lãi'); } catch (e) { bao('loi', loi(e, 'Không lưu được')); } finally { setSaving(false); }
  };
  return (
    <div className="glass-card p-4 space-y-3 max-w-xl">
      <p className="text-sm text-[var(--text-secondary)]">Giá bán = giá vốn × (1 + % lãi nhóm). Nếu mẫu có giá bán cố định, áp giá nào cao hơn. Chỉ Thu mua chốt; không ai gõ giá bán tay.</p>
      {ds.map((r, i) => (
        <div key={r.nhom} className="flex items-center gap-2">
          <span className="flex-1 text-sm text-[var(--text-primary)]">{r.nhom}</span>
          <input className={`${inp} w-24 text-right`} type="number" step="0.5" value={r.phan_tram_lai} onChange={e => setDs(ds.map((x, j) => j === i ? { ...x, phan_tram_lai: Number(e.target.value) } : x))} />
          <span className="text-sm text-[var(--text-muted)]">%</span>
        </div>
      ))}
      <div className="flex gap-2">
        <input className={inp} placeholder="Thêm nhóm mới (vd Thiết bị vệ sinh)" value={moi} onChange={e => setMoi(e.target.value)} />
        <button className={btnGhost} onClick={() => { if (moi.trim() && !ds.some(x => x.nhom === moi.trim())) { setDs([...ds, { nhom: moi.trim(), phan_tram_lai: 15 }]); setMoi(''); } }}><LineIcon name="plus" size={14} /></button>
      </div>
      <button className={btnGold} disabled={saving} onClick={luu}><LineIcon name="check" size={14} color="currentColor" /> {saving ? 'Đang lưu…' : 'Lưu'}</button>
    </div>
  );
}


// ── Shopee: giá thị trường, ghép sản phẩm, thương lượng, gợi ý NCC (26/10/2026) ──

function GiaShopee({ m }: { m: MauVatTu }) {
  if (!m.gia_shopee) return null;
  return (
    <div className="text-xs mt-0.5 text-orange-300 flex items-center gap-1">
      Shopee {tien(m.gia_shopee)}
      {m.link_shopee_aff && <a href={m.link_shopee_aff} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--gold-400)]" title="Mở trên Shopee"><LineIcon name="link" size={11} /></a>}
    </div>
  );
}

function ChonShopee({ mau, onDong, onXong, bao }: { mau: MauVatTu; onDong: () => void; onXong: (m: MauVatTu) => void; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [q, setQ] = useState('');
  const [ds, setDs] = useState<ShopeeSanPham[] | null>(null);
  const [dang, setDang] = useState(false);
  const [loiTim, setLoiTim] = useState('');
  const [link, setLink] = useState('');

  const tim = useCallback(async (tu?: string) => {
    setDang(true); setLoiTim('');
    try { const r = await api.vatTuTimShopee(mau.id, tu); setQ(r.tu_khoa); setDs(r.items); }
    catch (e) { setLoiTim(loi(e, 'Không tìm được trên Shopee')); setDs([]); }
    finally { setDang(false); }
  }, [mau.id]);
  useEffect(() => { void Promise.resolve().then(() => tim()); }, [tim]);

  const chon = async (sp: ShopeeSanPham) => {
    try { onXong(await api.vatTuChonShopee(mau.id, { item_id: sp.item_id, ten: sp.ten, gia: sp.gia, link_aff: sp.link_aff })); }
    catch (e) { bao('loi', loi(e, 'Lưu thất bại')); }
  };
  const doiLink = async () => {
    try { onXong(await api.vatTuLinkAff(mau.id, link.trim())); }
    catch (e) { bao('loi', loi(e, 'Không đổi được link')); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center" onClick={onDong}>
      <div className="glass-card w-full sm:max-w-2xl max-h-[85vh] overflow-y-auto p-4 space-y-3 rounded-b-none sm:rounded-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-[var(--text-primary)]">Giá Shopee · {mau.ma}</h3>
          <button className="p-1 text-[var(--text-muted)]" onClick={onDong} aria-label="Đóng"><LineIcon name="x" size={16} /></button>
        </div>
        <form className="flex gap-2" onSubmit={e => { e.preventDefault(); tim(q); }}>
          <input className={inp} value={q} onChange={e => setQ(e.target.value)} placeholder="Từ khoá tìm trên Shopee" />
          <button className={btnGold} disabled={dang}><LineIcon name="search" size={14} color="currentColor" /> Tìm</button>
        </form>
        {loiTim && <p className="text-sm text-red-300">{loiTim}</p>}
        {dang && <p className="text-sm text-[var(--text-muted)]">Đang tìm…</p>}
        {ds && !dang && ds.length === 0 && !loiTim && <p className="text-sm text-[var(--text-muted)]">Không có trên Shopee — thử từ khoá khác.</p>}
        <div className="space-y-2">
          {ds?.map(sp => (
            <div key={sp.item_id} className="flex gap-3 items-center rounded-xl p-2 bg-[var(--surface-2)]">
              {sp.anh ? <img src={sp.anh} alt="" className="w-14 h-14 rounded-lg object-cover flex-shrink-0" /> : <div className="w-14 h-14 rounded-lg bg-[var(--surface-3)]" />}
              <div className="flex-1 min-w-0">
                <div className="text-sm text-[var(--text-primary)] line-clamp-2">{sp.ten}</div>
                <div className="text-xs text-[var(--text-muted)]">
                  <span className="text-orange-300 font-semibold">{sp.gia ? tien(sp.gia) : '—'}</span>
                  {sp.gia_max && sp.gia && sp.gia_max > sp.gia ? ` – ${tien(sp.gia_max)}` : ''} · đã bán {sp.da_ban}{sp.shop ? ` · ${sp.shop}` : ''}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <button className={`${btnGold} text-xs`} onClick={() => chon(sp)}><LineIcon name="check" size={12} color="currentColor" /> Chọn</button>
                {sp.link && <a className="text-xs text-center text-[var(--text-muted)] hover:text-[var(--gold-400)]" href={sp.link_aff || sp.link} target="_blank" rel="noopener noreferrer">Xem</a>}
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-[var(--border-subtle)] pt-3 space-y-2">
          <p className="text-xs text-[var(--text-muted)]">Hoặc dán link sản phẩm Shopee đã tìm tay.</p>
          <div className="flex gap-2">
            <input className={inp} value={link} onChange={e => setLink(e.target.value)} placeholder="https://shopee.vn/…" />
            <button className={btnGhost} disabled={link.trim().length < 8} onClick={doiLink}>Lưu link</button>
          </div>
          {mau.gia_shopee && (
            <button className="text-xs text-red-300 hover:underline" onClick={async () => {
              try { onXong(await api.vatTuBoShopee(mau.id)); } catch (e) { bao('loi', loi(e, 'Bỏ ghép thất bại')); }
            }}>Bỏ ghép Shopee hiện tại ({tien(mau.gia_shopee)})</button>
          )}
        </div>
      </div>
    </div>
  );
}

function GoiYNccKhoi({ mauId }: { mauId: string }) {
  const [ds, setDs] = useState<GoiYNcc[] | null>(null);
  useEffect(() => { api.vatTuGoiYNcc(mauId).then(r => setDs(r.items)).catch(() => setDs([])); }, [mauId]);
  if (!ds || ds.length === 0) return null;
  return (
    <div className="rounded-xl p-3 bg-[var(--surface-2)] space-y-1">
      <div className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1"><LineIcon name="sparkle" size={12} /> Gợi ý NCC (giá sau chiết khấu → JAMA đã mua nhiều)</div>
      {ds.slice(0, 3).map((g, i) => (
        <div key={(g.supplier_id || g.ncc_ten) + i} className="flex flex-wrap items-center gap-2 text-sm">
          <span className={i === 0 ? 'text-emerald-400 font-medium' : 'text-[var(--text-primary)]'}>{i + 1}. {g.ncc_ten}</span>
          <span className="text-[var(--gold-400)]">{tien(g.gia_sau_ck)}</span>
          {g.chiet_khau_pct > 0 && <span className="text-xs text-[var(--text-muted)]">(CK {g.chiet_khau_pct}% từ {tien(g.gia)})</span>}
          {g.da_mua > 0 && <span className="text-xs text-[var(--text-muted)]">đã mua {tien(g.da_mua)}</span>}
          {!g.con_hang && <span className="text-xs text-red-300">hết hàng</span>}
          {g.cao_hon_shopee && <span className="text-xs text-red-300">cao hơn Shopee</span>}
        </div>
      ))}
    </div>
  );
}

function CanThuongLuongTab() {
  const [items, setItems] = useState<CanThuongLuong[] | null>(null);
  useEffect(() => { api.vatTuCanThuongLuong().then(r => setItems(r.items)).catch(() => setItems([])); }, []);
  if (!items) return <div className="glass-card p-8 text-center text-[var(--text-muted)]">Đang tải…</div>;
  if (items.length === 0) return <div className="glass-card p-8 text-center text-[var(--text-muted)]">Chưa có báo giá NCC nào cao hơn Shopee. Ghép giá Shopee ở «Danh mục mẫu» để bảng này tự so.</div>;
  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--text-muted)]">Báo giá NCC cao hơn giá bán lẻ trên Shopee — mang số này đi thương lượng.</p>
      {items.map(x => (
        <div key={x.bao_gia_id} className="glass-card p-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="font-medium text-[var(--text-primary)]">{x.ma}</span>
          {x.hang && <span className="text-xs text-[var(--text-muted)]">{x.hang}</span>}
          <span className="text-[var(--text-secondary)]">{x.ncc_ten} <span className="text-[var(--gold-400)]">{tien(x.gia_ncc)}</span></span>
          <span className="text-orange-300">Shopee {tien(x.gia_shopee)}</span>
          <span className="rounded-full px-2 py-0.5 text-xs bg-red-500/15 text-red-300">+{x.chenh_pct}% ({tien(x.chenh)}/{x.don_vi})</span>
          {x.project_code && <span className="text-xs text-[var(--text-muted)]">{x.project_code}</span>}
          {x.duoc_chon && <span className="text-xs text-amber-300">đã chốt</span>}
          {x.link_shopee_aff && <a href={x.link_shopee_aff} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--text-muted)] hover:text-[var(--gold-400)] inline-flex items-center gap-1"><LineIcon name="link" size={11} /> Shopee</a>}
        </div>
      ))}
    </div>
  );
}

// Gợi ý tên NCC có sẵn trong mục Nhà cung cấp (gõ tên mới thì tự tạo NCC khi lưu)
let nccCache: Promise<{ id: string; name: string }[]> | null = null;
function NccGoiY() {
  const [ds, setDs] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => {
    nccCache ??= api.vatTuDsNcc().catch(() => { nccCache = null; return []; });
    nccCache.then(setDs);
  }, []);
  return <datalist id="ds-ncc">{ds.map(n => <option key={n.id} value={n.name} />)}</datalist>;
}
