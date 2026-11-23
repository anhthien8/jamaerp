'use client';

// Vật tư Đợt 1 (25/10/2026): danh mục mẫu · phiếu chọn theo dự án · bảng «Cần hỏi giá».
// Giá vốn/NCC/lãi chỉ hiện khi backend trả thay_gia_von (Giám đốc, Thu mua, Trưởng phòng);
// sale/thiết kế không bao giờ nhận các cột đó trong JSON — FE chỉ vẽ cái có.

import { Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api, mediaUrl, type DongVatTu, type GoiYNcc, type MauVatTu, type PhieuVatTu, type Project, type VatTuTongQuan } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { tien } from '@/lib/tien-gon';
import { compressImage } from '@/lib/nhan-su';
import { chuanHoaTim } from '@/lib/utils';
import { docGio, ngayThang } from '@/lib/du-lieu-chung';
import BangGiaChuan from '@/components/vat-tu/BangGiaChuan';
import ChonNgayHen, { ngayNgan } from '@/components/vat-tu/NgayHenGiao';
import { AnhMau, NHAN_HANG_NCC, NccGoiY, btn, btnGhost, btnGold, inp, loi, tienDu } from '@/components/vat-tu/chung';

// Bỏ dấu + thường hoá để tìm dự án không cần gõ dấu
const boDau = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

const TAB_IDS = ['danh-muc', 'can-hoi-gia', 'du-an', 'dat-nhan', 'gia-chuan', 'cai-gia'] as const;
type Tab = (typeof TAB_IDS)[number];

const MAU_TRANG_THAI: Record<string, string> = {
  khach_chon: '#F59E0B', hoi_ncc: '#3B82F6', het_hang: '#EF4444', cho_khach_duyet_lai: '#A78BFA',
  da_chot_gia: '#10B981', cho_duyet_dat: '#F97316', da_dat: '#06B6D4', giao_thieu: '#EF4444', da_giao: '#9CA3AF', huy: '#6B7280',
};

// Kiểu nút/ô nhập, loi(), tienDu(), AnhMau, NccGoiY dùng chung với các khối tách file → components/vat-tu/chung.tsx
// Số điện thoại → dạng zalo.me nhận (chỉ chữ số, 84… → 0…); rỗng khi không ra số hợp lệ
const soZalo = (s?: string | null) => { const so = (s || '').replace(/\D/g, '').replace(/^84(?=\d{9}$)/, '0'); return /^0\d{9,10}$/.test(so) ? so : ''; };
const chepTin = async (text: string) => { try { await navigator.clipboard.writeText(text); return true; } catch { return false; } };

// Dòng đã đặt hàng (kể cả đang chờ Leader duyệt): không sửa, không xoá được nữa — chỉ Leader Thu mua huỷ kèm lý do
const DA_DAT = ['cho_duyet_dat', 'da_dat', 'giao_thieu', 'da_giao'];
// Dòng có giá bán mà khách chưa đồng ý. 22/11/2026: lời đồng ý có hiệu lực tới khi giá bán đổi (server tự xoá
// khi đổi) → mẫu có giá chuẩn thì khách duyệt được ngay, không phải chờ Thu mua chốt giá vốn. Cùng luật
// server dùng khi đặt hàng (vat_tu.py dat_hang).
const choDuyetGia = (d: DongVatTu) => d.gia_ban != null && !d.khach_dong_y_luc && ['khach_chon', 'hoi_ncc', 'da_chot_gia'].includes(d.trang_thai);
// Dòng đang chờ khách duyệt (mẫu thay thế hoặc giá bán) — cùng luật với portal khách
const choKhachDuyet = (d: DongVatTu) => ['het_hang', 'cho_khach_duyet_lai'].includes(d.trang_thai) || choDuyetGia(d);

/** Tin đã soạn sẵn: đã chép vào bộ nhớ tạm (hoặc để chép tay), kèm nút mở khung chat Zalo.
 *  Chỉ là đường dẫn mở Zalo — app không tự gửi gì. */
type TinSoan = { tieuDe: string; text: string; chep: boolean; phone?: string | null; nhanZalo?: string };
function TinDaSoan({ tin, onDong }: { tin: TinSoan; onDong: () => void }) {
  const [chep, setChep] = useState(tin.chep);
  const so = soZalo(tin.phone);
  return (
    <div className="glass-card p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium text-[var(--text-primary)]">{tin.tieuDe}</div>
        <button className="p-1 text-[var(--text-muted)]" aria-label="Đóng" onClick={onDong}><LineIcon name="x" size={16} /></button>
      </div>
      <div className={`text-xs ${chep ? 'text-emerald-400' : 'text-amber-300'}`}>{chep ? 'Đã chép tin — mở Zalo rồi dán vào khung chat.' : 'Máy không cho chép tự động — chạm vào ô dưới, chọn tất cả rồi chép tay.'}</div>
      <textarea readOnly className={inp} rows={Math.min(12, tin.text.split('\n').length + 1)} value={tin.text} onFocus={e => e.currentTarget.select()} />
      <div className="flex flex-wrap gap-2">
        {so && <a href={`https://zalo.me/${so}`} target="_blank" rel="noopener noreferrer" className={btnGold}><LineIcon name="send" size={14} color="currentColor" /> Mở Zalo {tin.nhanZalo || so}</a>}
        <button className={btnGhost} onClick={async () => setChep(await chepTin(tin.text))}><LineIcon name="copy" size={14} /> Chép lại</button>
      </div>
    </div>
  );
}

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
  // Tab chỉ đọc từ URL (?tab=…), bấm tab là đổi URL. Trước đây tab bấm tay nằm trong state gắn với URL lúc bấm
  // → bấm tiếp một link trùng URL đó (thông báo «Giá chuẩn cần xét lại» kế tiếp, link dự án ở tab Đặt & nhận
  // hàng) thì không có gì xảy ra. replaceState: Next đồng bộ useSearchParams, không gọi lại server, không
  // thêm bước vào nút Back.
  const tabUrl = sp.get('tab') as Tab | null;
  const tab: Tab = tabUrl && TAB_IDS.includes(tabUrl) ? tabUrl : projectParam ? 'du-an' : 'danh-muc';
  const setTab = (t: Tab) => window.history.replaceState(null, '', `/vat-tu?${new URLSearchParams({ ...(projectParam ? { project: projectParam } : {}), tab: t }).toString()}`);
  const [thongBao, setThongBao] = useState<{ loai: 'ok' | 'loi'; text: string } | null>(null);
  // Một hàm giữ nguyên qua các lần vẽ: các tab để `bao` trong dependency của lệnh tải — hàm đổi là tải lại
  const bao = useCallback((loai: 'ok' | 'loi', text: string) => { setThongBao({ loai, text }); setTimeout(() => setThongBao(null), 4000); }, []);

  useEffect(() => { api.vatTuTongQuan().then(setTongQuan).catch(() => setTongQuan(null)); }, [tab]);

  const thayGiaVon = !!tongQuan?.thay_gia_von;
  const laThuMua = !!tongQuan?.la_thu_mua;
  const qDatNhan: QuyenDatNhan = {
    laThuMua, laLeader: !!tongQuan?.la_leader_thu_mua, laGiamSat: !!tongQuan?.la_giam_sat,
    thayGiaVon, soAnh: tongQuan?.so_anh_toi_thieu ?? 2, lyDoLoi: tongQuan?.ly_do_loi_nhan_hang ?? {},
    laAdmin, userId: user?.id,
  };
  const soDatNhan = tongQuan ? (tongQuan.theo_trang_thai.cho_duyet_dat || 0) + (tongQuan.theo_trang_thai.da_dat || 0) + (tongQuan.theo_trang_thai.giao_thieu || 0) : 0;
  const choHoi = tongQuan ? (tongQuan.theo_trang_thai.khach_chon || 0) + (tongQuan.theo_trang_thai.hoi_ncc || 0) + (tongQuan.theo_trang_thai.het_hang || 0) + (tongQuan.theo_trang_thai.cho_khach_duyet_lai || 0) : 0;

  const tabs: { id: Tab; nhan: string; icon: string; so?: number; an?: boolean }[] = [
    { id: 'du-an', nhan: 'Phiếu dự án', icon: 'clipboard' },
    { id: 'danh-muc', nhan: 'Danh mục mẫu', icon: 'package', so: tongQuan?.so_mau },
    { id: 'can-hoi-gia', nhan: 'Cần hỏi giá', icon: 'receipt', so: choHoi, an: !thayGiaVon },
    { id: 'dat-nhan', nhan: 'Đặt & nhận hàng', icon: 'truck', so: soDatNhan },
    { id: 'gia-chuan', nhan: 'Bảng giá chuẩn', icon: 'cash', an: !laThuMua },
    { id: 'cai-gia', nhan: '% lãi theo nhóm', icon: 'percent', an: !laAdmin },
  ];

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold text-[var(--text-primary)] flex items-center gap-2"><LineIcon name="package" size={22} /> Vật tư</h1>
            <p className="text-sm text-[var(--text-muted)]">Khách chọn mẫu → Thu mua hỏi NCC, chốt giá vốn → đặt hàng → Giám sát nhận. Giá bán theo giá chuẩn Giám đốc đặt (mẫu chưa có giá chuẩn: giá vốn + % lãi nhóm).</p>
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

        {tab === 'du-an' && <PhieuDuAn key={projectParam || ''} projectId={projectParam} thayGiaVon={thayGiaVon} laAdmin={laAdmin} q={qDatNhan} userId={user?.id} tenNV={user?.full_name} bao={bao} />}
        {tab === 'dat-nhan' && <DatNhanTab q={qDatNhan} bao={bao} />}
        {tab === 'danh-muc' && <DanhMuc thayGiaVon={thayGiaVon} laThuMua={laThuMua} laAdmin={laAdmin} bao={bao} />}
        {tab === 'gia-chuan' && laThuMua && <BangGiaChuan key={sp.get('loc') || ''} locDau={sp.get('loc')} bao={bao} />}
        {/* Tab giờ mở được bằng URL → người không có quyền mở link của tab ẩn thì thấy lý do, không phải trang trắng */}
        {tongQuan && tabs.some(t => t.id === tab && t.an) && <div className="glass-card p-8 text-center text-[var(--text-muted)]">{tab === 'gia-chuan' ? 'Bảng giá chuẩn chỉ dành cho bộ phận Thu mua và Giám đốc.' : 'Mục này không mở cho tài khoản của bạn.'}</div>}
        {tab === 'can-hoi-gia' && thayGiaVon && <CanHoiGia laThuMua={laThuMua} soNgayGiaCu={tongQuan?.so_ngay_gia_cu ?? 60} bao={bao} />}
        {tab === 'cai-gia' && laAdmin && <CaiGia bao={bao} />}
      </div>
    </Sidebar>
  );
}

// ───────────────────────── Danh mục mẫu ─────────────────────────
function DanhMuc({ thayGiaVon, laThuMua, laAdmin, bao }: { thayGiaVon: boolean; laThuMua: boolean; laAdmin: boolean; bao: (l: 'ok' | 'loi', t: string) => void }) {
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
                {sua.anh_url && <button type="button" className={btnGhost} onClick={() => setSua({ ...sua, anh_url: '' })}><LineIcon name="x" size={14} /> Bỏ ảnh</button>}
              </div>
            </div>
          </div>
          <input className={inp} type="number" placeholder="Giá tham khảo (vốn)" value={sua.gia_tham_khao ?? ''} onChange={e => setSua({ ...sua, gia_tham_khao: e.target.value ? Number(e.target.value) : null })} />
          {/* Giá chuẩn chỉ Giám đốc đặt — người khác gửi lên server cũng bỏ qua, nên không hiện ô cho họ */}
          {laAdmin && <input className={inp} type="number" placeholder="Giá chuẩn — đơn giá bán (nếu có)" value={sua.gia_ban_co_dinh ?? ''} onChange={e => setSua({ ...sua, gia_ban_co_dinh: e.target.value ? Number(e.target.value) : null })} />}
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
                {laThuMua && <button className="text-xs text-[var(--text-muted)] hover:text-[var(--gold-400)] mt-1 inline-flex items-center gap-1" onClick={() => setSua({ ...m })}><LineIcon name="edit" size={12} /> Sửa</button>}
              </div>
            </div>
          ))}
        </div>
      )}
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
function PhieuDuAn({ projectId, thayGiaVon, laAdmin, q, userId, tenNV, bao }: { projectId: string | null; thayGiaVon: boolean; laAdmin: boolean; q: QuyenDatNhan; userId?: string; tenNV?: string; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [duAns, setDuAns] = useState<Project[]>([]);
  const [pid, setPid] = useState(projectId || '');
  const [phieu, setPhieu] = useState<PhieuVatTu | null>(null);
  const [loading, setLoading] = useState(false);
  const [moThem, setMoThem] = useState(false);
  const [form, setForm] = useState<{ phong: string; hang_muc: string; mau_id: string | null; ma_tu_do: string; so_luong: number; don_vi: string; ghi_chu: string; can_ngay: string }>({ phong: 'Chung', hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, don_vi: 'm2', ghi_chu: '', can_ngay: '' });
  const [dongY, setDongY] = useState<{ id: string; ghi_chu: string } | null>(null);
  const [tin, setTin] = useState<TinSoan | null>(null);
  const [dongYLoat, setDongYLoat] = useState<string | null>(null); // ghi chú chung khi ghi «khách đồng ý» nhiều dòng
  const [dangLoat, setDangLoat] = useState('');

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
      const d = await api.vatTuThemDong(pid, { phong: form.phong || 'Chung', hang_muc: form.hang_muc || null, mau_id: form.mau_id, ma_tu_do: form.mau_id ? null : form.ma_tu_do, so_luong: form.so_luong, don_vi: form.don_vi, ghi_chu: form.ghi_chu || null, can_ngay: form.can_ngay || null });
      // Mã gõ tay trùng mã một mẫu trong danh mục → server gắn mẫu đó và lấy đơn vị của mẫu (giá chuẩn tính trên đơn vị đó)
      bao('ok', d.mau_id && d.don_vi !== form.don_vi ? `Đã thêm vào phiếu — mã có trong danh mục nên đơn vị theo mẫu: ${d.don_vi}` : 'Đã thêm vào phiếu');
      setMoThem(false); setForm(f => ({ ...f, hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, ghi_chu: '', can_ngay: '' })); tai();
    } catch (e) { bao('loi', loi(e, 'Không thêm được')); }
  };
  const xoa = async (d: DongVatTu) => {
    if (!confirm(`Xoá dòng ${d.ma || d.ma_tu_do}?`)) return;
    try { await api.vatTuXoaDong(d.id); tai(); } catch (e) { bao('loi', loi(e, 'Không xoá được')); }
  };
  // Endpoint không lưu ai bấm thay khách → chèn tên nhân viên vào ghi chú để còn vết
  const ghiThay = (gc: string) => `${tenNV || 'Nhân viên'} ghi thay khách${gc.trim() ? `: ${gc.trim()}` : ''}`;
  const guiDongY = async () => {
    if (!dongY) return;
    const d = phieu?.items.find(x => x.id === dongY.id);
    if (d && choDuyetGia(d) && !dongY.ghi_chu.trim()) { bao('loi', 'Ghi rõ khách đồng ý giá qua kênh nào (Zalo, điện thoại, gặp trực tiếp…)'); return; }
    try { await api.vatTuKhachDongY(dongY.id, ghiThay(dongY.ghi_chu)); bao('ok', 'Đã ghi khách đồng ý'); setDongY(null); tai(); } catch (e) { bao('loi', loi(e, 'Không ghi được')); }
  };

  // Dòng đã có giá bán (giá chuẩn của mẫu, hoặc Thu mua đã chốt) mà khách chưa đồng ý → chưa đặt hàng được
  const dsChoDuyetGia = useMemo(() => (phieu?.items || []).filter(choDuyetGia), [phieu]);
  const tongChoDuyet = dsChoDuyetGia.reduce((s, d) => s + (d.thanh_tien || 0), 0);
  // Tin gửi khách: CHỈ dùng phòng, mã, số lượng, giá bán, thành tiền — không đụng giá vốn/NCC/lãi
  const soanTinKhach = async () => {
    const dong = dsChoDuyetGia.map((d, i) => `${i + 1}) ${d.phong} · ${d.ma || d.ma_tu_do || ''}: ${d.so_luong} ${d.don_vi} × ${tienDu(d.gia_ban || 0)} = ${tienDu(d.thanh_tien || 0)}`);
    const text = [`JAMA HOME gửi anh/chị đơn giá vật tư${duAn ? ` — ${duAn.name}` : ''}:`, ...dong, `Tổng cộng: ${tienDu(tongChoDuyet)}`, 'Anh/chị xem và nhắn lại «đồng ý» giúp em để bên em tiến hành đặt hàng ạ.'].join('\n');
    setTin({ tieuDe: `Tin gửi khách duyệt giá · ${dsChoDuyetGia.length} dòng`, text, chep: await chepTin(text), phone: duAn?.client_phone, nhanZalo: 'khách' });
  };
  const dongYHangLoat = async () => {
    if (!dongYLoat?.trim() || dangLoat) return;
    const ds = dsChoDuyetGia;
    const con: string[] = [];
    for (let i = 0; i < ds.length; i++) {
      setDangLoat(`Đang ghi ${i + 1}/${ds.length}…`);
      try { await api.vatTuKhachDongY(ds[i].id, ghiThay(dongYLoat)); }
      catch (e) { con.push(`${ds[i].ma || ds[i].ma_tu_do || '?'} (${loi(e, 'lỗi')})`); }
    }
    setDangLoat('');
    if (con.length) bao('loi', `Đã ghi ${ds.length - con.length}/${ds.length} — còn: ${con.join(', ')}`);
    else { bao('ok', `Đã ghi khách đồng ý ${ds.length} dòng`); setDongYLoat(null); }
    tai();
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
        {pid && dsChoDuyetGia.length > 0 && <>
          <button className={btnGhost} onClick={soanTinKhach}><LineIcon name="send" size={14} /> Gửi khách duyệt giá</button>
          <button className={`${btn} text-emerald-300 border-emerald-500/40`} onClick={() => setDongYLoat(v => (v === null ? '' : null))}><LineIcon name="tick" size={14} /> Khách đồng ý giá {dsChoDuyetGia.length} dòng</button>
        </>}
      </div>

      {tin && <TinDaSoan key={tin.text} tin={tin} onDong={() => setTin(null)} />}

      {dongYLoat !== null && dsChoDuyetGia.length > 0 && (
        <div className="glass-card p-3 space-y-2">
          <div className="text-sm text-[var(--text-primary)]">Ghi nhận khách đồng ý giá bán của <b>{dsChoDuyetGia.length} dòng</b> đã có giá — tổng <b className="text-[var(--gold-400)]">{tienDu(tongChoDuyet)}</b>. Khách đồng ý rồi Thu mua mới đặt hàng được; sau này giá bán đổi thì phải hỏi lại khách.</div>
          <ul className="text-xs text-[var(--text-secondary)] space-y-0.5 max-h-40 overflow-auto">
            {dsChoDuyetGia.map(d => <li key={d.id}>{d.phong} · {d.ma || d.ma_tu_do} — {d.so_luong} {d.don_vi} × {tienDu(d.gia_ban || 0)} = {tienDu(d.thanh_tien || 0)}</li>)}
          </ul>
          <input className={inp} placeholder="Khách nói gì, qua kênh nào, lúc nào (bắt buộc)" value={dongYLoat} onChange={e => setDongYLoat(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <button className={btnGold} disabled={!dongYLoat.trim() || !!dangLoat} onClick={dongYHangLoat}><LineIcon name="tick" size={14} color="currentColor" /> {dangLoat || `Xác nhận khách đồng ý ${dsChoDuyetGia.length} dòng`}</button>
            <button className={btnGhost} disabled={!!dangLoat} onClick={() => setDongYLoat(null)}>Huỷ</button>
          </div>
        </div>
      )}

      {!pid && <div className="glass-card p-8 text-center text-[var(--text-muted)]">Chọn dự án để xem phiếu vật tư. Mỗi phòng một nhóm dòng: khách chọn → Thu mua hỏi NCC → chốt giá.</div>}

      {moThem && pid && (
        <div className="glass-card p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <input className={inp} list="ds-phong" placeholder="Phòng / khu vực" value={form.phong} onChange={e => setForm({ ...form, phong: e.target.value })} />
          <datalist id="ds-phong">{dsPhong.map(p => <option key={p} value={p} />)}</datalist>
          <input className={inp} placeholder="Hạng mục (sàn, tường, ốp bếp…)" value={form.hang_muc} onChange={e => setForm({ ...form, hang_muc: e.target.value })} />
          <div className="lg:col-span-2"><ChonMau onChon={(m, ma) => setForm(f => ({ ...f, mau_id: m?.id || null, ma_tu_do: ma, don_vi: m?.don_vi || f.don_vi }))} /></div>
          <input className={inp} type="number" min={0} step="0.1" placeholder="Số lượng" value={form.so_luong} onChange={e => setForm({ ...form, so_luong: Number(e.target.value) })} />
          {/* Dòng có mẫu trong danh mục luôn lấy đơn vị của mẫu (server bỏ qua đơn vị gõ khác) → khoá ô, chỉ mã gõ tay mới gõ đơn vị */}
          <input className={`${inp} disabled:opacity-60`} placeholder="Đơn vị" aria-label="Đơn vị" value={form.don_vi} disabled={!!form.mau_id} title={form.mau_id ? 'Đơn vị theo mẫu trong danh mục' : undefined} onChange={e => setForm({ ...form, don_vi: e.target.value })} />
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
            <div><span className="text-[var(--text-muted)]">Tổng giá bán (dòng đã có giá)</span> <span className="text-[var(--gold-400)] font-semibold">{tien(phieu.tong_gia_ban)}</span></div>
            {thayGiaVon && phieu.tong_lai !== undefined && <div><span className="text-[var(--text-muted)]">Lãi dự kiến</span> <span className="text-emerald-400 font-semibold">{tien(phieu.tong_lai)}</span></div>}
          </div>
          {qDuAn.laThuMua && thayGiaVon && <DatTheoBaoGia key={phieu.items.map(d => `${d.id}${d.trang_thai}`).join()} items={phieu.items} tai={tai} bao={bao} />}
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
                        {thayGiaVon && d.gia_von != null && <span className="text-[var(--text-muted)]"> · vốn {tien(d.gia_von)}{d.ncc_ten ? ` (${d.ncc_ten})` : ''}{d.phan_tram_ap_dung != null ? ` · +${d.phan_tram_ap_dung}%` : ' · giá chuẩn'}</span>}
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
                      {choKhachDuyet(d) && dongY?.id !== d.id && (
                        <button className={`${btn} text-xs text-emerald-300 border-emerald-500/40`} onClick={() => setDongY({ id: d.id, ghi_chu: '' })}><LineIcon name="tick" size={12} /> {choDuyetGia(d) ? 'Khách đồng ý giá' : 'Khách đã đồng ý'}</button>
                      )}
                      {/* Dòng đã đặt hàng không xoá được (server chặn cả Admin) — Leader Thu mua bấm «Huỷ dòng» kèm lý do.
                          Dòng đã huỷ SAU khi đặt (còn sl_dat) cũng không xoá, không mở lại: giữ làm lịch sử đơn. */}
                      {!DA_DAT.includes(d.trang_thai) && !(d.trang_thai === 'huy' && d.sl_dat != null) && (laAdmin || d.trang_thai !== 'da_chot_gia') && (
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
// lyDoLoi: lý do hàng lỗi khi nhận hàng (khoá → nhãn) lấy từ /vat-tu/tong-quan
// laAdmin + userId: để biết đơn vượt nào do chính người xem đặt (không tự duyệt được, trừ Admin)
type QuyenDatNhan = { laThuMua: boolean; laLeader: boolean; laGiamSat: boolean; thayGiaVon: boolean; soAnh: number; lyDoLoi: Record<string, string>; laAdmin: boolean; userId?: string };

// docGio: server trả giờ UTC không kèm múi — đọc thẳng bằng new Date() thì lệch 7 tiếng
const ngayGio = (s?: string | null) => (s ? docGio(s).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

// Thu mua: đặt một loạt dòng đúng báo giá đã chốt (không sửa khối lượng/đơn giá).
// Gọi tuần tự từng dòng — server cộng dồn ngân sách theo từng lần đặt và tự đẩy dòng vượt sang Leader duyệt.
// Dòng chốt giá mà chưa có NCC (chốt trước 22/11/2026) server không cho đặt → không đưa vào lô
const datDuoc = (d: DongVatTu) => d.trang_thai === 'da_chot_gia' && !d.gia_cu && !!d.ncc_id && !choDuyetGia(d);
function DatTheoBaoGia({ items, tai, bao }: { items: DongVatTu[]; tai: () => void; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [mo, setMo] = useState(false);
  const [chon, setChon] = useState<Set<string>>(new Set()); // nhóm NCC đã chọn — mặc định không chọn
  const [ngay, setNgay] = useState<Record<string, string>>({}); // ngày NCC hẹn giao: mỗi NCC một ngày cho cả lô, không chọn sẵn
  const [dang, setDang] = useState('');
  const ds = useMemo(() => items.filter(datDuoc), [items]);
  const nhom = useMemo(() => {
    const m = new Map<string, DongVatTu[]>();
    ds.forEach(d => { const k = d.ncc_ten || 'Chưa rõ NCC'; m.set(k, [...(m.get(k) || []), d]); });
    return [...m.entries()];
  }, [ds]);
  if (!ds.length) return null;
  const tienDong = (d: DongVatTu) => d.so_luong * (d.gia_von || 0);
  const nhomChon = nhom.filter(([k]) => chon.has(k));
  const dsChon = nhomChon.flatMap(([k, v]) => v.map(d => ({ d, ngayHen: ngay[k] || '' })));
  const thieuNgay = nhomChon.some(([k]) => !ngay[k]);
  const tong = dsChon.reduce((s, x) => s + tienDong(x.d), 0);
  const dat = async () => {
    if (!dsChon.length || thieuNgay || dang) return;
    let daDat = 0, choDuyet = 0;
    const con: string[] = [];
    for (let i = 0; i < dsChon.length; i++) {
      const { d, ngayHen } = dsChon[i];
      setDang(`Đang đặt ${i + 1}/${dsChon.length}…`);
      try {
        const r = await api.vatTuDatHang(d.id, { so_luong: null, don_gia: null, ngay_giao_hen: ngayHen });
        if (r.trang_thai === 'cho_duyet_dat') choDuyet++; else daDat++;
      } catch (e) { con.push(`${d.ma || d.ma_tu_do || '?'} (${loi(e, 'lỗi')})`); }
    }
    setDang('');
    const tom = `${daDat} dòng đã đặt${choDuyet ? `, ${choDuyet} dòng chờ Leader duyệt` : ''}`;
    if (con.length) bao('loi', `${tom}, ${con.length} lỗi: ${con.join(', ')}`); else bao('ok', tom);
    setMo(false); setChon(new Set()); setNgay({}); tai();
  };
  return (
    <div className="glass-card p-3 space-y-2">
      <button className={btnGhost} disabled={!!dang} onClick={() => setMo(v => !v)}><LineIcon name="receipt" size={14} /> Đặt {ds.length} dòng đúng báo giá</button>
      {mo && (
        <div className="space-y-2">
          <div className="text-xs text-[var(--text-muted)]">Chỉ gồm dòng đã chốt giá kèm NCC, giá chưa cũ, khách đã đồng ý giá bán. Đặt đúng khối lượng và đơn giá đã chốt; dòng cần sửa thì dùng nút «Đặt hàng» của riêng dòng đó. Mỗi NCC chọn một ngày hẹn giao cho cả lô. Dòng vượt ngân sách sẽ tự chuyển Leader Thu mua duyệt.</div>
          {nhom.map(([k, v]) => (
            <div key={k} className="rounded-lg border border-[var(--border-subtle)] p-2 space-y-2">
              <label className="block cursor-pointer">
                <div className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
                  {/* Tick hay bỏ tick đều xoá ngày hẹn của NCC đó — không có ngày nào được chọn sẵn */}
                  <input type="checkbox" className="w-5 h-5 shrink-0 accent-[var(--gold-400)]" disabled={!!dang} checked={chon.has(k)}
                    onChange={() => { setNgay(m => ({ ...m, [k]: '' })); setChon(c => { const n = new Set(c); if (n.has(k)) n.delete(k); else n.add(k); return n; }); }} />
                  <span className="font-medium">{k}</span><span className="text-[var(--text-muted)]">· {v.length} dòng · {tienDu(v.reduce((s, d) => s + tienDong(d), 0))}</span>
                </div>
                <ul className="mt-1 ml-7 text-xs text-[var(--text-secondary)] space-y-0.5">
                  {v.map(d => <li key={d.id}>{d.ma || d.ma_tu_do} · {d.phong} — {d.so_luong} {d.don_vi} × {tienDu(d.gia_von || 0)}</li>)}
                </ul>
              </label>
              {chon.has(k) && <div className="ml-7"><ChonNgayHen value={ngay[k] || ''} onChange={n => setNgay(m => ({ ...m, [k]: n }))} disabled={!!dang} /></div>}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <button className={btnGold} disabled={!!dang || !dsChon.length || thieuNgay} onClick={dat}>
              <LineIcon name="receipt" size={14} color="currentColor" /> {dang || (thieuNgay ? 'Chọn ngày hẹn giao cho từng NCC đã tick' : `Xác nhận đặt ${dsChon.length} dòng · ${tienDu(tong)}`)}
            </button>
            <button className={btnGhost} disabled={!!dang} onClick={() => { setMo(false); setChon(new Set()); setNgay({}); }}>Huỷ</button>
          </div>
        </div>
      )}
    </div>
  );
}

async function anhSangBlob(f: File): Promise<Blob> {
  const nen = await compressImage(f).catch(() => null);
  if (!nen) return f;
  return (await fetch(`data:${nen.mime};base64,${nen.base64}`)).blob();
}

/** Thông tin đặt/nhận của một dòng: ai đặt, vượt gì, bị từ chối vì sao, nhận đủ/thiếu + ảnh. */
function ThongTinDatNhan({ d }: { d: DongVatTu }) {
  return (
    <>
      {d.gia_cu && <div className="text-xs rounded-lg bg-amber-500/10 text-amber-300 px-2 py-1 flex items-start gap-1"><LineIcon name="hourglass" size={12} /> Giá cũ — NCC báo giá này{d.gia_xac_nhan_luc ? ` từ ${docGio(d.gia_xac_nhan_luc).toLocaleDateString('vi-VN')}` : ''}, đã quá 60 ngày. Thu mua bấm «Hỏi lại giá», ghi báo giá mới của NCC rồi chốt lại trước khi đặt.</div>}
      {/* Chỉ người xem được giá vốn mới nhận gia_von / ncc_id → người khác không thấy dòng nhắc này */}
      {d.trang_thai === 'da_chot_gia' && d.gia_von != null && !d.ncc_id && <div className="text-xs rounded-lg bg-amber-500/10 text-amber-300 px-2 py-1 flex items-start gap-1"><LineIcon name="alert" size={12} /> Giá đã chốt nhưng chưa rõ nhà cung cấp. Thu mua bấm «Hỏi lại giá», chốt lại kèm NCC rồi mới đặt hàng được.</div>}
      {d.trang_thai === 'da_chot_gia' && choDuyetGia(d) && <div className="text-xs text-amber-300">Chờ khách đồng ý giá bán — chưa đặt hàng được.</div>}
      {d.tu_choi_dat_ly_do && d.trang_thai === 'da_chot_gia' && <div className="text-xs rounded-lg bg-red-500/10 text-red-300 px-2 py-1 flex items-start gap-1"><LineIcon name="x" size={12} /> Leader từ chối đơn trước: {d.tu_choi_dat_ly_do}</div>}
      {d.dat_luc && DA_DAT.includes(d.trang_thai) && (
        <div className="text-xs text-[var(--text-secondary)]">
          Đặt {d.sl_dat ?? d.so_luong} {d.don_vi}{d.gia_dat != null ? ` × ${tien(d.gia_dat)}` : ''} · {d.dat_boi_ten || '—'} · {ngayGio(d.dat_luc)}
          {d.duyet_dat_boi_ten && <span className="text-emerald-400"> · {d.duyet_dat_boi_ten} duyệt</span>}
        </div>
      )}
      {d.ngay_giao_hen && DA_DAT.includes(d.trang_thai) && (
        <div className="text-xs text-[var(--text-secondary)] flex flex-wrap items-center gap-1.5">
          <LineIcon name="calendar" size={12} /> Hẹn giao {ngayNgan(d.ngay_giao_hen)}
          {d.ngay_giao_hen_dau && d.ngay_giao_hen_dau !== d.ngay_giao_hen && <span className="text-[var(--text-muted)]">(hẹn đầu {ngayNgan(d.ngay_giao_hen_dau)})</span>}
          {d.tre_hen && <span className="rounded-full bg-red-500/15 text-red-300 px-2 py-0.5 font-medium">Trễ hẹn</span>}
        </div>
      )}
      {d.ly_do_vuot && d.trang_thai === 'cho_duyet_dat' && <div className="text-xs rounded-lg bg-orange-500/10 text-orange-300 px-2 py-1 flex items-start gap-1"><LineIcon name="alert" size={12} /> Vượt báo giá: {d.ly_do_vuot}</div>}
      {/* Từng LẦN nhận hàng, cũ → mới (giao thiếu, giao bù, hàng lỗi). Dòng chưa có lịch sử thì hiện lần nhận gần nhất như trước. */}
      {d.nhan_lich_su?.length ? (
        <ul className="text-xs space-y-0.5">
          {d.nhan_lich_su.map((n, i) => (
            <li key={i} className={n.ket_qua === 'thieu' ? 'text-red-300' : 'text-emerald-400'}>
              {/* Lần nhận ghi trước 22/11/2026 (chép sang lúc nâng cấp) có thể không có số lượng → bỏ hẳn phần số, không in ô trống */}
              {ngayGio(n.luc)} · {n.boi_ten || '—'} · {n.ket_qua === 'thieu' ? 'về thiếu' : 'về đủ'}{n.sl_luy_ke != null ? `: lần này ${n.sl_lan_nay ?? '—'}, tổng ${n.sl_luy_ke}/${d.sl_dat ?? d.so_luong} ${d.don_vi}` : ''}
              {n.ly_do_loi_nhan ? ` · ${n.ly_do_loi_nhan}` : ''}{n.ghi_chu ? ` — ${n.ghi_chu}` : ''}
            </li>
          ))}
        </ul>
      ) : d.nhan_luc && (
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
      {/* Vết huỷ. Dòng giao thiếu đã về một phần thì Leader không huỷ được cả dòng: server đóng dòng ở số đã nhận
          (trạng thái «đã giao», khối lượng = số đã nhận) và vẫn ghi ai bỏ phần còn lại, lúc nào, vì sao. */}
      {d.huy_luc && (d.trang_thai === 'huy' || d.trang_thai === 'da_giao') && <div className="text-xs text-[var(--text-muted)]">{d.trang_thai === 'huy' ? 'Đã huỷ' : 'Đã chốt ở số đã nhận, bỏ phần còn lại'} {ngayGio(d.huy_luc)} · {d.huy_boi_ten || '—'}{d.huy_ly_do ? ` — ${d.huy_ly_do}` : ''}</div>}
    </>
  );
}

/** Nút + ô nhập cho bước đặt/duyệt/nhận/huỷ của một dòng. Trả null khi người xem không có việc gì ở dòng này. */
function HanhDongDatNhan({ d, q, xong, bao }: { d: DongVatTu; q: QuyenDatNhan; xong: (d: DongVatTu) => void; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [mo, setMo] = useState<'dat' | 'tu_choi' | 'nhan' | 'huy' | null>(null);
  const [sl, setSl] = useState(String(d.so_luong));
  // Ô đơn giá mở sẵn giá đã chốt, làm tròn về đồng: giá vốn có thể lẻ thập phân (181818.18 đọc từ tệp NCC) mà ô
  // chỉ nhận chữ số — bỏ dấu chấm thành 18181818. Chỉ gửi `don_gia` khi người đặt thật sự sửa ô này.
  const giaDau = d.gia_von != null ? String(Math.round(d.gia_von)) : '';
  const [gia, setGia] = useState(giaDau);
  const [ngayHen, setNgayHen] = useState(''); // ngày NCC hẹn giao — không chọn sẵn; chưa chọn thì chưa đặt được
  const [lyDo, setLyDo] = useState('');
  const [lyDoHuy, setLyDoHuy] = useState('');
  const [ketQua, setKetQua] = useState<'du' | 'thieu'>('du');
  const [slNhan, setSlNhan] = useState('');
  const [lyDoLoi, setLyDoLoi] = useState(''); // khoá lý do hàng lỗi — tuỳ chọn
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
  const doiGia = q.thayGiaVon && gia !== giaDau && giaSo > 0; // người đặt đã sửa ô đơn giá
  const vuotTruoc = [
    slSo > d.so_luong ? `khối lượng ${slSo} > báo giá ${d.so_luong}` : '',
    // Cùng ngưỡng với server (vat_tu.py dat_hang): lệch quá 0,5đ mới là vượt
    doiGia && d.gia_von != null && giaSo > d.gia_von + 0.5 ? `đơn giá ${tien(giaSo)} > ${tien(d.gia_von)}` : '',
  ].filter(Boolean);

  const datHang = () => chay(() => api.vatTuDatHang(d.id, {
    so_luong: slSo && slSo !== d.so_luong ? slSo : null,
    don_gia: doiGia ? giaSo : null,
    ngay_giao_hen: ngayHen,
  }), 'Đã gửi đơn đặt hàng');

  // «Thiếu»: bắt buộc ghi TỔNG đã về tới giờ (tính cả các lần trước) — cùng ba điều kiện server kiểm
  const slDat = d.sl_dat ?? d.so_luong;
  const daVe = d.trang_thai === 'giao_thieu' ? d.sl_nhan ?? 0 : 0;
  const tongVe = slNhan.trim() ? Number(slNhan.replace(',', '.')) : NaN;
  const loiSlNhan = ketQua !== 'thieu' ? '' : !(tongVe >= 0) ? 'Ghi tổng số lượng đã về tới giờ'
    : tongVe >= slDat ? 'Số lượng nhận đã đủ — chọn «Đủ hàng»'
    : tongVe < daVe ? `Tổng đã về không thể ít hơn lần trước (${daVe} ${d.don_vi})` : '';

  const nhanHang = () => chay(async () => {
    const blobs = await Promise.all(anh.map(anhSangBlob));
    const up = await api.uploadMediaBatch(blobs, { projectId: d.project_id, kind: 'vat_tu', caption: `Nhận hàng ${d.ma || d.ma_tu_do || ''} · ${d.phong}` });
    return api.vatTuNhanHang(d.id, {
      ket_qua: ketQua, so_luong_nhan: ketQua === 'thieu' ? tongVe : null, ly_do_loi: lyDoLoi || null,
      ghi_chu: ghiChu.trim(), anh_ids: up.items.map(x => x.id),
    });
  }, ketQua === 'du' ? 'Đã xác nhận hàng về đủ' : 'Đã báo hàng về thiếu');

  const nutDat = q.laThuMua && d.trang_thai === 'da_chot_gia';
  // Dòng đã chốt mà KHÔNG đặt được: giá cũ (quá 60 ngày), hoặc chốt từ trước 22/11/2026 không kèm NCC. Màn «Cần hỏi
  // giá» không chứa dòng đã chốt → một chạm đưa dòng về «Hỏi NCC» để ghi báo giá mới rồi chốt lại (PATCH cho phép
  // Thu mua). Giá bán không đổi thì lời đồng ý của khách còn nguyên.
  const thieuNcc = q.thayGiaVon && d.gia_von != null && !d.ncc_id;
  const nutHoiLai = nutDat && (!!d.gia_cu || thieuNcc);
  // Đơn vượt do chính mình đặt: server trả 403 khi tự duyệt / tự từ chối (trừ Admin) → không hiện hai nút đó
  const tuDat = d.trang_thai === 'cho_duyet_dat' && !q.laAdmin && !!q.userId && d.dat_boi === q.userId;
  const nutDuyet = q.laLeader && d.trang_thai === 'cho_duyet_dat' && !tuDat;
  const nutNhan = q.laGiamSat && ['da_dat', 'giao_thieu'].includes(d.trang_thai);
  // Dòng đã đặt hàng: chỉ Leader Thu mua / Admin huỷ được và phải ghi lý do; hàng đã giao đủ thì không huỷ
  const nutHuy = q.laLeader && ['cho_duyet_dat', 'da_dat', 'giao_thieu'].includes(d.trang_thai);
  // Giao thiếu mà đã về một phần: không huỷ cả dòng — server đóng dòng ở số đã nhận (tiền phần đã nhận vẫn tính
  // vào chi phí dự án), phần chưa về bỏ hẳn. Cùng một lệnh PATCH trang_thai = huy, chỉ khác tên gọi trên màn hình.
  const chotSoNhan = d.trang_thai === 'giao_thieu' && (d.sl_nhan ?? 0) > 0;
  if (!nutDat && !nutDuyet && !nutNhan && !nutHuy) return null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {nutDat && mo !== 'dat' && <button className={`${btn} text-xs`} disabled={!!d.gia_cu || thieuNcc || choDuyetGia(d)} title={d.gia_cu ? 'Giá cũ — bấm «Hỏi lại giá» rồi chốt lại' : thieuNcc ? 'Chưa rõ NCC — bấm «Hỏi lại giá» rồi chốt lại kèm NCC' : choDuyetGia(d) ? 'Khách chưa đồng ý giá bán' : ''} onClick={() => { setNgayHen(''); setSl(String(d.so_luong)); setGia(giaDau); setMo('dat'); }}><LineIcon name="receipt" size={12} /> Đặt hàng</button>}
        {nutHoiLai && <button className={`${btn} text-xs text-amber-300 border-amber-500/40`} disabled={dangGui} onClick={() => chay(() => api.vatTuSuaDong(d.id, { trang_thai: 'hoi_ncc' }), 'Đã đưa dòng về tab «Cần hỏi giá» — ghi báo giá mới của NCC rồi chốt lại')}><LineIcon name="refresh" size={12} /> Hỏi lại giá</button>}
        {q.laLeader && tuDat && <span className="self-center text-xs text-[var(--text-muted)]">Đơn bạn đặt — chờ Leader Thu mua khác hoặc Giám đốc duyệt</span>}
        {nutDuyet && mo !== 'tu_choi' && <>
          <button className={`${btn} text-xs text-emerald-300 border-emerald-500/40`} disabled={dangGui} onClick={() => chay(() => api.vatTuDuyetDat(d.id, true), 'Đã duyệt đơn')}><LineIcon name="tick" size={12} /> Duyệt đơn</button>
          <button className={`${btn} text-xs text-red-300 border-red-500/40`} onClick={() => setMo('tu_choi')}><LineIcon name="x" size={12} /> Từ chối</button>
        </>}
        {nutNhan && mo !== 'nhan' && <button className={`${btn} text-xs text-[var(--gold-400)] border-[var(--gold-400)]/50`} onClick={() => { setKetQua('du'); setSlNhan(''); setGhiChu(''); setLyDoLoi(''); setMo('nhan'); }}><LineIcon name="truck" size={12} /> {d.trang_thai === 'giao_thieu' ? 'Nhận bù hàng' : 'Nhận hàng'}</button>}
        {nutHuy && mo !== 'huy' && <button className={`${btn} text-xs text-red-300 border-red-500/40`} onClick={() => { setLyDoHuy(''); setMo('huy'); }}><LineIcon name="xCircle" size={12} /> {chotSoNhan ? 'Chốt số đã nhận, bỏ phần còn lại' : 'Huỷ đơn'}</button>}
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
          <ChonNgayHen value={ngayHen} onChange={setNgayHen} disabled={dangGui} />
          <div className="flex gap-2"><button className={btnGold} disabled={dangGui || slSo <= 0 || !ngayHen} onClick={datHang}>{dangGui ? 'Đang gửi…' : ngayHen ? 'Xác nhận đặt' : 'Chọn ngày hẹn giao để đặt'}</button><button className={btnGhost} onClick={() => setMo(null)}>Huỷ</button></div>
        </div>
      )}

      {mo === 'tu_choi' && (
        <div className="rounded-xl bg-[var(--surface-2)] p-3 space-y-2">
          <input className={inp} autoFocus placeholder="Lý do từ chối (Thu mua sửa theo đó)" value={lyDo} onChange={e => setLyDo(e.target.value)} />
          <div className="flex gap-2"><button className={btnGold} disabled={dangGui || !lyDo.trim()} onClick={() => chay(() => api.vatTuDuyetDat(d.id, false, lyDo.trim()), 'Đã trả đơn về Thu mua')}>Gửi từ chối</button><button className={btnGhost} onClick={() => setMo(null)}>Huỷ</button></div>
        </div>
      )}

      {mo === 'huy' && (
        <div className="rounded-xl bg-[var(--surface-2)] p-3 space-y-2">
          <div className="text-xs text-[var(--text-muted)]">
            {chotSoNhan
              ? `Hàng đã về ${d.sl_nhan}/${slDat} ${d.don_vi}. Dòng sẽ đóng ở số đã nhận (${d.sl_nhan} ${d.don_vi}): chi phí dự án chỉ còn tính phần đã nhận, phần chưa về bỏ hẳn — cần mua tiếp thì tạo dòng mới. Lưu vết ai bỏ, lúc nào, vì sao. Nhớ báo NCC ngừng giao phần còn lại.`
              : 'Dòng đã đặt hàng không sửa, không xoá được — chỉ huỷ kèm lý do (lưu vết ai huỷ, lúc nào). Huỷ rồi không mở lại được, cần mua lại thì tạo dòng mới. Nhớ báo NCC huỷ đơn.'}
          </div>
          <input className={inp} autoFocus placeholder={chotSoNhan ? 'Lý do bỏ phần còn lại (bắt buộc)' : 'Lý do huỷ (bắt buộc)'} value={lyDoHuy} onChange={e => setLyDoHuy(e.target.value)} />
          <div className="flex gap-2"><button className={btnGold} disabled={dangGui || !lyDoHuy.trim()} onClick={() => chay(() => api.vatTuSuaDong(d.id, { trang_thai: 'huy', huy_ly_do: lyDoHuy.trim() }), chotSoNhan ? 'Đã chốt dòng ở số đã nhận' : 'Đã huỷ đơn')}>{chotSoNhan ? `Xác nhận chốt ${d.sl_nhan} ${d.don_vi}` : 'Xác nhận huỷ đơn'}</button><button className={btnGhost} onClick={() => setMo(null)}>Thôi</button></div>
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
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input className={inp} inputMode="decimal" aria-label={`Tổng đã về tới giờ (${d.don_vi})`} placeholder={`Tổng đã về tới giờ (${d.don_vi}) *`} value={slNhan} onChange={e => setSlNhan(e.target.value)} />
                <input className={`${inp} sm:col-span-2`} placeholder="Thiếu gì, bao nhiêu (bắt buộc)" value={ghiChu} onChange={e => setGhiChu(e.target.value)} />
              </div>
              <div className={`text-xs ${slNhan.trim() && loiSlNhan ? 'text-amber-300' : 'text-[var(--text-muted)]'}`}>
                {slNhan.trim() && loiSlNhan ? loiSlNhan
                  : `Đặt ${slDat} ${d.don_vi}${daVe ? `, các lần trước đã về ${daVe}` : ''} — ghi TỔNG đã về, tính cả lần này${slNhan.trim() ? ` (lần này về ${Math.round((tongVe - daVe) * 1000) / 1000})` : ''}.`}
              </div>
            </>
          )}
          {ketQua === 'du' && <input className={inp} placeholder="Ghi chú (không bắt buộc)" value={ghiChu} onChange={e => setGhiChu(e.target.value)} />}
          {Object.keys(q.lyDoLoi).length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-[var(--text-muted)]">Hàng lỗi (nếu có)</span>
              {Object.entries(q.lyDoLoi).map(([k, nhan]) => (
                <button key={k} type="button" className={`${btn} text-xs ${lyDoLoi === k ? 'bg-amber-500/15 text-amber-300 border-amber-500/50' : 'text-[var(--text-secondary)] border-[var(--border-subtle)]'}`}
                  onClick={() => setLyDoLoi(v => (v === k ? '' : k))}>{nhan}</button>
              ))}
            </div>
          )}
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
            <button className={btnGold} disabled={dangGui || anh.length < q.soAnh || (ketQua === 'thieu' && (!ghiChu.trim() || !!loiSlNhan))} onClick={nhanHang}>{dangGui ? 'Đang tải ảnh…' : 'Xác nhận'}</button>
            <button className={btnGhost} onClick={() => { setMo(null); setAnh([]); }}>Huỷ</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Hai hàng chờ: đơn vượt chờ Leader duyệt · hàng đã đặt chờ Giám sát nhận. */
function DatNhanTab({ q, bao }: { q: QuyenDatNhan; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [data, setData] = useState<{ cho_duyet: DongVatTu[]; cho_nhan: DongVatTu[]; nhan_cua_toi?: string[] } | null>(null);
  const tai = useCallback(() => { api.vatTuViecDatNhan().then(setData).catch(e => { bao('loi', loi(e, 'Không tải được')); setData({ cho_duyet: [], cho_nhan: [] }); }); }, [bao]);
  useEffect(() => { tai(); }, [tai]);
  // Gom hàng chờ nhận theo dự án: ảnh nhận hàng chỉ hợp lệ trong đúng dự án (server kiểm)
  const nhomNhan = useMemo(() => {
    const m = new Map<string, DongVatTu[]>();
    (data?.cho_nhan || []).forEach(d => m.set(d.project_id, [...(m.get(d.project_id) || []), d]));
    return [...m.entries()];
  }, [data]);
  if (!data) return <div className="text-sm text-[var(--text-muted)] p-4">Đang tải…</div>;
  const cuaToi = new Set(data.nhan_cua_toi || []);
  const khoi = (tieuDe: string, ds: DongVatTu[], rong: string, qq: QuyenDatNhan) => (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-2 text-sm font-semibold text-[var(--text-primary)] bg-[var(--surface-2)] border-b border-[var(--border-subtle)]">{tieuDe} <span className="text-[var(--text-muted)] font-normal">· {ds.length}</span></div>
      {ds.length === 0 && <div className="p-4 text-sm text-[var(--text-muted)]">{rong}</div>}
      <div className="divide-y divide-[var(--border-subtle)]">
        {ds.map(d => <DongDatNhan key={d.id} d={d} q={qq} xong={tai} bao={bao} />)}
      </div>
    </div>
  );
  return (
    <div className="space-y-3">
      {(q.laLeader || data.cho_duyet.length > 0) && khoi('Đơn vượt báo giá chờ Leader Thu mua duyệt', data.cho_duyet, 'Không có đơn nào chờ duyệt.', { ...q, laGiamSat: false })}
      <div className="glass-card overflow-hidden">
        <div className="px-4 py-2 text-sm font-semibold text-[var(--text-primary)] bg-[var(--surface-2)] border-b border-[var(--border-subtle)]">Hàng đã đặt, chờ Giám sát nhận tại công trình <span className="text-[var(--text-muted)] font-normal">· {data.cho_nhan.length}</span></div>
        {data.cho_nhan.length === 0 && <div className="p-4 text-sm text-[var(--text-muted)]">Không có hàng nào đang chờ nhận.</div>}
        {nhomNhan.map(([pid, ds]) => (
          <NhomChoNhan key={pid} ds={ds} cuaToi={cuaToi} q={{ ...q, laThuMua: false }} tai={tai} bao={bao} />
        ))}
      </div>
    </div>
  );
}

/** Một dòng ở tab «Đặt & nhận hàng»; `truoc` là ô tick (nếu có) đặt trước ảnh mẫu. */
function DongDatNhan({ d, q, xong, bao, truoc }: { d: DongVatTu; q: QuyenDatNhan; xong: () => void; bao: (l: 'ok' | 'loi', t: string) => void; truoc?: ReactNode }) {
  return (
    <div className="p-3 flex gap-3">
      {truoc}
      <AnhMau url={d.anh_url} size={44} />
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-[var(--text-primary)]">{d.ma || d.ma_tu_do}</span>
          <NhanTrangThai d={d} />
          <Link href={`/vat-tu?project=${d.project_id}`} className="text-xs text-[var(--gold-400)] hover:underline">{d.project_code} · {d.project_name}</Link>
        </div>
        <div className="text-xs text-[var(--text-secondary)]">{d.phong}{d.hang_muc ? ` · ${d.hang_muc}` : ''} · báo giá {d.so_luong} {d.don_vi}</div>
        <ThongTinDatNhan d={d} />
        <HanhDongDatNhan d={d} q={q} xong={xong} bao={bao} />
      </div>
    </div>
  );
}

/** Hàng chờ nhận của MỘT dự án. Giám sát tick các dòng về đủ trong cùng chuyến xe, chụp một bộ
 *  ảnh, bấm một lần — vẫn gọi endpoint nhận hàng cho từng dòng nên luật số ảnh tối thiểu do
 *  server gác. Dòng thiếu hàng đi nút «Nhận hàng» từng dòng như cũ (bắt buộc ghi thiếu gì). */
function NhomChoNhan({ ds, cuaToi, q, tai, bao }: { ds: DongVatTu[]; cuaToi: Set<string>; q: QuyenDatNhan; tai: () => void; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [chon, setChon] = useState<Set<string>>(new Set());
  const [anh, setAnh] = useState<File[]>([]);
  const [anhIds, setAnhIds] = useState<string[] | null>(null); // ảnh đã tải — lỗi giữa chừng bấm lại không tải lại
  const [daDem, setDaDem] = useState(false);
  const [dangGui, setDangGui] = useState('');
  const xem = useMemo(() => anh.map(f => URL.createObjectURL(f)), [anh]);
  useEffect(() => () => xem.forEach(u => URL.revokeObjectURL(u)), [xem]);

  const dsChon = ds.filter(d => cuaToi.has(d.id) && chon.has(d.id));
  const doi = (id: string) => { setDaDem(false); setChon(c => { const m = new Set(c); if (m.has(id)) m.delete(id); else m.add(id); return m; }); };

  const nhan = async () => {
    if (!dsChon.length || dangGui) return;
    let ids = anhIds;
    if (!ids) {
      setDangGui('Đang tải ảnh…');
      try {
        const blobs = await Promise.all(anh.map(anhSangBlob));
        const up = await api.uploadMediaBatch(blobs, { projectId: ds[0].project_id, kind: 'vat_tu', caption: `Nhận hàng ${dsChon.length} dòng · ${ds[0].project_code || ''}` });
        ids = up.items.map(x => x.id);
        setAnhIds(ids);
      } catch (e) { bao('loi', loi(e, 'Không tải được ảnh')); setDangGui(''); return; }
    }
    const xong = new Set<string>();
    const con: string[] = [];
    for (let i = 0; i < dsChon.length; i++) { // tuần tự để biết đúng dòng nào chưa xong
      const d = dsChon[i];
      setDangGui(`Đang ghi ${i + 1}/${dsChon.length}…`);
      try { await api.vatTuNhanHang(d.id, { ket_qua: 'du', anh_ids: ids, ghi_chu: '' }); xong.add(d.id); }
      catch (e) { con.push(`${d.ma || d.ma_tu_do || '?'} (${loi(e, 'lỗi')})`); }
    }
    setChon(c => new Set([...c].filter(i => !xong.has(i))));
    setDaDem(false); setDangGui('');
    if (con.length) bao('loi', `Đã nhận ${xong.size}/${dsChon.length} — còn: ${con.join(', ')}`);
    else { bao('ok', `Đã xác nhận ${xong.size} dòng về đủ`); setAnh([]); setAnhIds(null); }
    tai();
  };

  return (
    <div className="border-b border-[var(--border-subtle)] last:border-b-0">
      <div className="divide-y divide-[var(--border-subtle)]">
        {ds.map(d => (
          <DongDatNhan key={d.id} d={d} q={{ ...q, laGiamSat: q.laGiamSat || cuaToi.has(d.id) }} xong={tai} bao={bao}
            truoc={cuaToi.has(d.id) ? (
              <input type="checkbox" className="mt-3 w-5 h-5 shrink-0 accent-[var(--gold-400)]" disabled={!!dangGui}
                aria-label={`Chọn ${d.ma || d.ma_tu_do || 'dòng'} để nhận đủ`} checked={chon.has(d.id)} onChange={() => doi(d.id)} />
            ) : undefined} />
        ))}
      </div>
      {dsChon.length > 0 && (
        <div className="p-3 space-y-2 bg-[var(--surface-2)]">
          <div className="text-sm font-medium text-[var(--text-primary)]">Nhận đủ cả chuyến · {ds[0].project_code} — {dsChon.length} dòng</div>
          <ul className="text-xs text-[var(--text-secondary)] space-y-0.5">
            {dsChon.map(d => <li key={d.id}>{d.ma || d.ma_tu_do} — đặt <b className="text-[var(--text-primary)]">{d.sl_dat ?? d.so_luong} {d.don_vi}</b> · {d.phong}</li>)}
          </ul>
          <label className={`${btnGhost} text-xs cursor-pointer w-fit`}>
            <LineIcon name="camera" size={12} /> Chụp / chọn ảnh hiện trường (dùng chung cho các dòng)
            <input type="file" accept="image/*" capture="environment" multiple className="hidden" disabled={!!dangGui}
              onChange={e => { const fs = Array.from(e.target.files || []); setAnh(a => [...a, ...fs].slice(0, 10)); setAnhIds(null); e.target.value = ''; }} />
          </label>
          {xem.length > 0 && (
            <div className="flex gap-1.5 flex-wrap">
              {xem.map((u, i) => (
                <div key={u} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt="" className="w-14 h-14 rounded-lg object-cover" />
                  <button className="absolute -top-1 -right-1 rounded-full bg-black/70 p-0.5" aria-label="Bỏ ảnh" disabled={!!dangGui} onClick={() => { setAnh(a => a.filter((_, j) => j !== i)); setAnhIds(null); }}><LineIcon name="x" size={10} /></button>
                </div>
              ))}
            </div>
          )}
          <div className={`text-xs ${anh.length >= q.soAnh ? 'text-emerald-400' : 'text-amber-300'}`}>{anh.length}/{q.soAnh} ảnh tối thiểu — ảnh vào Kho ảnh dự án. Dòng nào thiếu hàng thì bỏ tick, dùng nút «Nhận hàng» của riêng dòng đó.</div>
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <input type="checkbox" className="w-5 h-5 shrink-0 accent-[var(--gold-400)]" checked={daDem} disabled={!!dangGui} onChange={e => setDaDem(e.target.checked)} />
            Tôi đã đếm đủ số lượng của {dsChon.length} dòng trên
          </label>
          <div className="flex flex-wrap gap-2">
            <button className={btnGold} disabled={!!dangGui || !daDem || anh.length < q.soAnh} onClick={nhan}>
              <LineIcon name="truck" size={14} color="currentColor" /> {dangGui || `Nhận đủ ${dsChon.length} dòng đã chọn`}
            </button>
            <button className={btnGhost} disabled={!!dangGui} onClick={() => { setChon(new Set()); setDaDem(false); }}>Bỏ chọn</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────────── Cần hỏi giá (Thu mua) ─────────────────────────
function CanHoiGia({ laThuMua, soNgayGiaCu, bao }: { laThuMua: boolean; soNgayGiaCu: number; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [items, setItems] = useState<DongVatTu[]>([]);
  // Báo giá quá `soNgayGiaCu` ngày = «giá cũ» (cùng luật server: chốt theo báo giá đó thì chưa đặt hàng được).
  // Mốc «bây giờ» chốt một lần lúc mở tab (Date.now() không được gọi lúc render).
  const [bayGio] = useState(() => Date.now());
  const quaHan = (iso?: string | null) => !!iso && bayGio - docGio(iso).getTime() > soNgayGiaCu * 86_400_000;
  // Đang gửi lệnh chốt của dòng nào — chặn bấm đúp ở cả ba lối chốt (mỗi lần chốt gõ tay server ghi thêm một
  // dòng báo giá và báo lại thiết kế / KD / giám sát)
  const [dangChot, setDangChot] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mo, setMo] = useState<string | null>(null);
  const [bg, setBg] = useState({ ncc_ten: '', gia: '', con_hang: true, ngay_giao: '', ghi_chu: '' });
  const [hetHang, setHetHang] = useState<{ id: string; ma_thay_the: string; mau_thay_the_id: string | null; ly_do: string } | null>(null);
  const [giaTay, setGiaTay] = useState<{ id: string; gia_von: string; ncc_ten: string } | null>(null);
  const [chon, setChon] = useState<Set<string>>(new Set()); // dòng chọn để soạn tin hỏi giá NCC
  const [nccHoi, setNccHoi] = useState('');
  const [tin, setTin] = useState<TinSoan | null>(null);

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
    if (dangChot) return;
    setDangChot(id);
    try { const d = await api.vatTuChot(id, { bao_gia_id }); bao('ok', `Đã chốt — giá bán ${tien(d.gia_ban || 0)}/${d.don_vi}`); setMo(null); tai(); }
    catch (e) { bao('loi', loi(e, 'Không chốt được')); }
    finally { setDangChot(null); }
  };
  const chotTay = async () => {
    if (!giaTay || dangChot) return;
    if (!(Number(giaTay.gia_von) > 0)) { bao('loi', 'Gõ giá vốn lớn hơn 0'); return; }
    // 22/11/2026: giá vốn phải rõ của NCC nào — thiếu thì server cũng trả 400
    if (!giaTay.ncc_ten.trim()) { bao('loi', 'Chốt giá phải kèm nhà cung cấp — chọn hoặc gõ tên NCC'); return; }
    setDangChot(giaTay.id);
    try { const d = await api.vatTuChot(giaTay.id, { gia_von: Number(giaTay.gia_von), ncc_ten: giaTay.ncc_ten.trim() }); bao('ok', `Đã chốt — giá bán ${tien(d.gia_ban || 0)}/${d.don_vi}`); setGiaTay(null); tai(); }
    catch (e) { bao('loi', loi(e, 'Không chốt được')); }
    finally { setDangChot(null); }
  };
  // Một chạm: chốt theo giá vốn + NCC của lần mua gần nhất (gửi supplier_id để không khớp nhầm tên)
  const chotGanNhat = async (d: DongVatTu) => {
    if (!d.gia_von_gan_nhat || dangChot) return;
    setDangChot(d.id);
    try { const r = await api.vatTuChot(d.id, { gia_von: d.gia_von_gan_nhat, supplier_id: d.ncc_gan_nhat_id || null, ncc_ten: d.ncc_gan_nhat_ten || undefined }); bao('ok', `Đã chốt — giá bán ${tien(r.gia_ban || 0)}/${r.don_vi}`); tai(); }
    catch (e) { bao('loi', loi(e, 'Không chốt được')); }
    finally { setDangChot(null); }
  };
  // Tin hỏi giá gửi NCC: CHỈ mã, hãng, số lượng, đơn vị, hạn cần — không tên khách/dự án, không giá nào, không ghi chú nội bộ.
  // Là tin «xin báo giá», không phải đơn đặt hàng.
  const soanTinHoiGia = async () => {
    const gop = new Map<string, { ten: string; so_luong: number; don_vi: string; can_ngay: string | null }>();
    items.filter(d => chon.has(d.id)).forEach(d => {
      const k = d.mau_id || `${d.ma_tu_do || d.ma || ''}|${d.don_vi}`;
      const cu = gop.get(k);
      const can = d.can_ngay || null;
      if (cu) { cu.so_luong += d.so_luong; if (can && (!cu.can_ngay || can < cu.can_ngay)) cu.can_ngay = can; }
      else gop.set(k, { ten: [d.ma || d.ma_tu_do, d.hang].filter(Boolean).join(' '), so_luong: d.so_luong, don_vi: d.don_vi, can_ngay: can });
    });
    const dong = [...gop.values()].map((g, i) => `${i + 1}) ${g.ten} — ${Math.round(g.so_luong * 100) / 100} ${g.don_vi}${g.can_ngay ? `, cần trước ${new Date(g.can_ngay).toLocaleDateString('vi-VN')}` : ''}`);
    const text = ['JAMA HOME xin báo giá các mã sau:', ...dong, 'Anh/chị báo giúp đơn giá, tình trạng còn hàng và thời gian giao. Cảm ơn anh/chị!'].join('\n');
    let phone: string | null = null;
    if (nccHoi.trim()) {
      // So tên NCC bản NFC cả hai phía — tên gõ kiểu «Unicode tổ hợp» vẫn ra đúng số Zalo (21/11/2026)
      try { const r = await api.getSuppliers({ search: nccHoi.trim() }); const s = r.items.find(x => chuanHoaTim(x.name) === chuanHoaTim(nccHoi.trim())); phone = s?.zalo || s?.phone || null; }
      catch { phone = null; } // không xem được danh bạ NCC → chỉ chép tin
    }
    setTin({ tieuDe: `Tin hỏi giá · ${dong.length} mã`, text, chep: await chepTin(text), phone, nhanZalo: nccHoi.trim() || undefined });
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
      {laThuMua && (
        <div className="glass-card p-3 flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <input type="checkbox" className="w-5 h-5 accent-[var(--gold-400)]" checked={chon.size === items.length}
              onChange={e => setChon(e.target.checked ? new Set(items.map(d => d.id)) : new Set())} /> Chọn tất cả
          </label>
          <NccGoiY /><input className={`${inp} w-48`} list="ds-ncc" placeholder="Gửi NCC (để mở Zalo)" value={nccHoi} onChange={e => setNccHoi(e.target.value)} />
          <button className={btnGold} disabled={!chon.size} onClick={soanTinHoiGia}><LineIcon name="copy" size={14} color="currentColor" /> Sao chép tin hỏi giá ({chon.size})</button>
        </div>
      )}
      {tin && <TinDaSoan key={tin.text + (tin.phone || '')} tin={tin} onDong={() => setTin(null)} />}
      {items.map(d => {
        const bgs = [...(d.bao_gia || [])].sort((a, b) => a.gia - b.gia);
        const dangMo = mo === d.id;
        return (
          <div key={d.id} className="glass-card overflow-hidden">
            <div className="flex">
            {laThuMua && (
              <input type="checkbox" className="ml-3 mt-4 w-5 h-5 shrink-0 accent-[var(--gold-400)]" aria-label={`Chọn ${d.ma || d.ma_tu_do || 'dòng'} để hỏi giá`}
                checked={chon.has(d.id)} onChange={() => setChon(c => { const n = new Set(c); if (n.has(d.id)) n.delete(d.id); else n.add(d.id); return n; })} />
            )}
            <button type="button" className="flex-1 min-w-0 p-3 flex gap-3 text-left" onClick={() => setMo(dangMo ? null : d.id)}>
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
                  {d.so_bao_gia} báo giá{d.gia_von_gan_nhat ? ` · giá gần nhất ${tien(d.gia_von_gan_nhat)}` : d.gia_tham_khao ? ` · tham khảo ${tien(d.gia_tham_khao)}` : ''}
                  {d.can_ngay && <> · <span className="text-amber-300">cần trước {new Date(d.can_ngay).toLocaleDateString('vi-VN')}</span></>}
                  {d.ghi_chu && <> · {d.ghi_chu}</>}
                </div>
              </div>
            </button>
            </div>
            {laThuMua && d.gia_von_gan_nhat && d.ncc_gan_nhat_ten && !d.gia_gan_nhat_cu && (
              <div className="px-3 pb-3 -mt-1">
                <button className={`${btn} text-xs text-emerald-300 border-emerald-500/40`} disabled={dangChot === d.id} onClick={() => chotGanNhat(d)}>
                  <LineIcon name="check" size={12} /> Chốt {tien(d.gia_von_gan_nhat)} · {d.ncc_gan_nhat_ten}{d.gia_von_cap_nhat_luc ? ` (giá ngày ${new Date(d.gia_von_cap_nhat_luc).toLocaleDateString('vi-VN')})` : ''}
                </button>
              </div>
            )}
            {dangMo && (
              <div className="border-t border-[var(--border-subtle)] p-3 space-y-3 bg-[var(--surface-1)]">
                {d.mau_id && <GoiYNccKhoi mauId={d.mau_id} quaHan={quaHan} onDung={laThuMua ? g => setGiaTay({ id: d.id, gia_von: String(g.gia), ncc_ten: g.ncc_ten }) : undefined} />}
                {bgs.length > 0 && (
                  <div className="space-y-1">
                    {bgs.map((b, i) => (
                      <div key={b.id} className={`flex flex-wrap items-center gap-2 rounded-lg px-3 py-2 text-sm ${i === 0 ? 'bg-emerald-500/10' : 'bg-[var(--surface-2)]'}`}>
                        <span className="font-medium text-[var(--text-primary)]">{b.ncc_ten}</span>
                        <span className="text-[var(--gold-400)] font-semibold">{tien(b.gia)}</span>
                        {i === 0 && <span className="text-xs text-emerald-400">rẻ nhất</span>}
                        {!b.con_hang && <span className="text-xs text-red-300">hết hàng</span>}
                        {b.ngay_giao && <span className="text-xs text-[var(--text-muted)]">giao {b.ngay_giao}</span>}
                        {b.ghi_chu && <span className="text-xs text-[var(--text-muted)]">{b.ghi_chu}</span>}
                        {/* Ngày báo giá = ngày bằng chứng giá nếu chốt theo dòng này → báo giá quá hạn phải thấy được TRƯỚC khi bấm chốt */}
                        {b.created_at && <span className="text-xs text-[var(--text-muted)]">báo giá {ngayThang(b.created_at)}</span>}
                        {quaHan(b.created_at) && <span className="text-xs rounded-full bg-amber-500/15 text-amber-300 px-1.5" title={`Báo giá quá ${soNgayGiaCu} ngày — chốt giá này thì chưa đặt hàng được. Hỏi lại NCC, thêm báo giá mới.`}>giá cũ</span>}
                        <span className="flex-1" />
                        {laThuMua && b.con_hang && <button className={`${btnGold} text-xs`} disabled={dangChot === d.id} onClick={() => chot(d.id, b.id)}><LineIcon name="check" size={12} color="currentColor" /> Chốt giá này</button>}
                        {laThuMua && <button className="text-[var(--text-muted)] hover:text-red-400 p-1" onClick={async () => { try { await api.vatTuXoaBaoGia(b.id); } catch (e) { bao('loi', loi(e, 'Không xoá được báo giá')); } tai(); }}><LineIcon name="trash" size={12} /></button>}
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
                          <input className={`${inp} w-48`} list="ds-ncc" placeholder="NCC *" value={giaTay.ncc_ten} onChange={e => setGiaTay({ ...giaTay, ncc_ten: e.target.value })} />
                          <button className={btnGold} disabled={dangChot === d.id} onClick={chotTay}>Chốt</button><button className={btnGhost} onClick={() => setGiaTay(null)}>Huỷ</button>
                          {/* Cũng nhắc ở dòng vừa «Hỏi lại giá» (giá đã chốt của chính dòng đó quá hạn): server giữ ngày cũ khi gõ lại đúng giá + NCC cũ */}
                          {(d.gia_gan_nhat_cu || quaHan(d.gia_xac_nhan_luc)) && <div className="w-full text-xs text-amber-300">Giá đang nhớ đã quá {soNgayGiaCu} ngày: gõ lại đúng giá đó của cùng NCC thì vẫn là «giá cũ», chưa đặt hàng được. Hỏi lại NCC, bấm «Thêm báo giá» rồi «Chốt giá này».</div>}
                        </>
                      ) : (
                        <button className={`${btnGhost} text-xs`} onClick={() => setGiaTay({ id: d.id, gia_von: String(d.gia_von_gan_nhat || d.gia_tham_khao || ''), ncc_ten: d.ncc_gan_nhat_ten || '' })}>Chốt nhanh theo giá vốn</button>
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
      <p className="text-sm text-[var(--text-secondary)]">Mẫu có giá chuẩn → bán đúng giá chuẩn (Giám đốc đặt ở tab «Bảng giá chuẩn»). Mẫu chưa có giá chuẩn → giá bán = giá vốn × (1 + % lãi nhóm). % này cũng là hệ số để tính «giá gợi ý» và cảnh báo «lời dưới hệ số». Không ai gõ giá bán tay trên dòng vật tư.</p>
      {ds.map((r, i) => (
        <div key={r.nhom} className="flex items-center gap-2">
          <span className="flex-1 text-sm text-[var(--text-primary)]">{r.nhom}</span>
          <input className={`${inp} w-24 text-right`} type="number" step="0.5" value={r.phan_tram_lai} onChange={e => setDs(ds.map((x, j) => j === i ? { ...x, phan_tram_lai: Number(e.target.value) } : x))} />
          <span className="text-sm text-[var(--text-muted)]">%</span>
        </div>
      ))}
      <div className="flex gap-2">
        <input className={inp} placeholder="Thêm nhóm mới (vd Thiết bị vệ sinh)" value={moi} onChange={e => setMoi(e.target.value)} />
        <button className={btnGhost} onClick={() => {
          // So + giữ bản NFC (21/11/2026): tên nhóm gõ kiểu «Unicode tổ hợp» trùng nhóm đã có thì không thêm
          // dòng thứ hai trông y hệt (backend lưu NFC → hai dòng đụng khoá chính khi bấm Lưu). Chỉ chuẩn hoá
          // lúc bấm thêm, không sửa ô đang gõ; giữ phân biệt hoa/thường như khoá nhóm ở backend.
          const ten = moi.trim().normalize('NFC');
          if (ten && !ds.some(x => x.nhom.normalize('NFC') === ten)) { setDs([...ds, { nhom: ten, phan_tram_lai: 15 }]); setMoi(''); }
        }}><LineIcon name="plus" size={14} /></button>
      </div>
      <button className={btnGold} disabled={saving} onClick={luu}><LineIcon name="check" size={14} color="currentColor" /> {saving ? 'Đang lưu…' : 'Lưu'}</button>
    </div>
  );
}

// ───────────────────────── Gợi ý NCC ─────────────────────────
/** `quaHan`: báo giá đã quá hạn «giá cũ» chưa. Gợi ý lấy báo giá MỚI NHẤT của NCC ở bất kỳ dự án nào, cũ mấy cũng
 *  hiện; «Dùng» điền vào ô chốt gõ tay, mà chốt gõ tay thì server coi là giá xác nhận hôm nay → báo giá quá hạn
 *  không được «Dùng», phải hỏi lại NCC rồi ghi báo giá mới. */
function GoiYNccKhoi({ mauId, quaHan, onDung }: { mauId: string; quaHan: (iso?: string | null) => boolean; onDung?: (g: GoiYNcc) => void }) {
  const [ds, setDs] = useState<GoiYNcc[] | null>(null);
  useEffect(() => { api.vatTuGoiYNcc(mauId).then(r => setDs(r.items)).catch(() => setDs([])); }, [mauId]);
  if (!ds || ds.length === 0) return null;
  return (
    <div className="rounded-xl p-3 bg-[var(--surface-2)] space-y-1">
      <div className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1"><LineIcon name="sparkle" size={12} /> Gợi ý NCC (hạng NCC → giá sau chiết khấu → JAMA đã mua nhiều)</div>
      {ds.slice(0, 3).map((g, i) => (
        <div key={(g.supplier_id || g.ncc_ten) + i} className="flex flex-wrap items-center gap-2 text-sm">
          <span className={i === 0 ? 'text-emerald-400 font-medium' : 'text-[var(--text-primary)]'}>{i + 1}. {g.ncc_ten}</span>
          {g.hang && NHAN_HANG_NCC[g.hang] && <span className="text-xs rounded-full bg-[var(--surface-3)] px-2 text-[var(--text-secondary)]">{NHAN_HANG_NCC[g.hang]}</span>}
          <span className="text-[var(--gold-400)]">{tien(g.gia_sau_ck)}</span>
          {g.chiet_khau_pct > 0 && <span className="text-xs text-[var(--text-muted)]">(CK {g.chiet_khau_pct}% từ {tien(g.gia)})</span>}
          {g.da_mua > 0 && <span className="text-xs text-[var(--text-muted)]">đã mua {tien(g.da_mua)}</span>}
          {!g.con_hang && <span className="text-xs text-red-300">hết hàng</span>}
          {g.bao_gia_luc && <span className="text-xs text-[var(--text-muted)]">báo giá {ngayThang(g.bao_gia_luc)}</span>}
          {quaHan(g.bao_gia_luc) && <span className="text-xs rounded-full bg-amber-500/15 text-amber-300 px-1.5" title="Báo giá đã quá hạn — hỏi lại NCC rồi ghi báo giá mới, không dùng lại giá này">giá cũ</span>}
          {onDung && g.con_hang && !quaHan(g.bao_gia_luc) && <button className={`${btnGhost} text-xs ml-auto`} onClick={() => onDung(g)}>Dùng</button>}
        </div>
      ))}
    </div>
  );
}
