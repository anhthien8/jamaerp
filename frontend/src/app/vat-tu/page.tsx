'use client';

// Vật tư Đợt 1 (25/10/2026): danh mục mẫu · phiếu chọn theo dự án · bảng «Cần hỏi giá».
// Giá vốn/NCC/lãi chỉ hiện khi backend trả thay_gia_von (Giám đốc, Thu mua, Trưởng phòng);
// sale/thiết kế không bao giờ nhận các cột đó trong JSON — FE chỉ vẽ cái có.

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api, type DongVatTu, type MauVatTu, type PhieuVatTu, type Project, type VatTuTongQuan } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { tien } from '@/lib/tien-gon';

type Tab = 'danh-muc' | 'can-hoi-gia' | 'du-an' | 'cai-gia';

const MAU_TRANG_THAI: Record<string, string> = {
  khach_chon: '#F59E0B', hoi_ncc: '#3B82F6', het_hang: '#EF4444', cho_khach_duyet_lai: '#A78BFA',
  da_chot_gia: '#10B981', da_dat: '#06B6D4', da_giao: '#9CA3AF', huy: '#6B7280',
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
  if (!url || !/^https?:/.test(url)) {
    return <div className="rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0" style={{ width: size, height: size }}><LineIcon name="package" size={16} /></div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" className="rounded-lg object-cover shrink-0" style={{ width: size, height: size }} loading="lazy" />;
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
  const tab: Tab = tabChon ?? (projectParam ? 'du-an' : 'danh-muc');
  const [thongBao, setThongBao] = useState<{ loai: 'ok' | 'loi'; text: string } | null>(null);
  const bao = (loai: 'ok' | 'loi', text: string) => { setThongBao({ loai, text }); setTimeout(() => setThongBao(null), 4000); };

  useEffect(() => { api.vatTuTongQuan().then(setTongQuan).catch(() => setTongQuan(null)); }, [tab]);

  const thayGiaVon = !!tongQuan?.thay_gia_von;
  const laThuMua = !!tongQuan?.la_thu_mua;
  const choHoi = tongQuan ? (tongQuan.theo_trang_thai.khach_chon || 0) + (tongQuan.theo_trang_thai.hoi_ncc || 0) + (tongQuan.theo_trang_thai.het_hang || 0) + (tongQuan.theo_trang_thai.cho_khach_duyet_lai || 0) : 0;

  const tabs: { id: Tab; nhan: string; icon: string; so?: number; an?: boolean }[] = [
    { id: 'du-an', nhan: 'Phiếu dự án', icon: 'clipboard' },
    { id: 'danh-muc', nhan: 'Danh mục mẫu', icon: 'package', so: tongQuan?.so_mau },
    { id: 'can-hoi-gia', nhan: 'Cần hỏi giá', icon: 'receipt', so: choHoi, an: !thayGiaVon },
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

        {tab === 'du-an' && <PhieuDuAn key={projectParam || ''} projectId={projectParam} thayGiaVon={thayGiaVon} laThuMua={laThuMua} laAdmin={laAdmin} bao={bao} />}
        {tab === 'danh-muc' && <DanhMuc thayGiaVon={thayGiaVon} laThuMua={laThuMua} bao={bao} />}
        {tab === 'can-hoi-gia' && thayGiaVon && <CanHoiGia laThuMua={laThuMua} bao={bao} />}
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
      bao('ok', `Đọc ${r.doc_duoc} dòng · thêm ${r.them} · cập nhật ${r.sua}`);
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
            <button className={btnGold} onClick={() => setSua({ ma: '', nhom: nhom || 'Khác', don_vi: 'm2', is_active: true })}><LineIcon name="plus" size={14} /> Thêm mẫu</button>
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
          <input className={inp} placeholder="Nhóm (30x30, 60x60…)" value={sua.nhom || ''} onChange={e => setSua({ ...sua, nhom: e.target.value })} list="ds-nhom" />
          <datalist id="ds-nhom">{nhoms.map(n => <option key={n.nhom} value={n.nhom} />)}</datalist>
          <input className={inp} placeholder="Bề mặt / tính chất" value={sua.be_mat || ''} onChange={e => setSua({ ...sua, be_mat: e.target.value })} />
          <input className={inp} placeholder="Đơn vị" value={sua.don_vi || ''} onChange={e => setSua({ ...sua, don_vi: e.target.value })} />
          <input className={inp} placeholder="Link ảnh" value={sua.anh_url || ''} onChange={e => setSua({ ...sua, anh_url: e.target.value })} />
          <input className={inp} type="number" placeholder="Giá tham khảo (vốn)" value={sua.gia_tham_khao ?? ''} onChange={e => setSua({ ...sua, gia_tham_khao: e.target.value ? Number(e.target.value) : null })} />
          <input className={inp} type="number" placeholder="Giá bán cố định (nếu có)" value={sua.gia_ban_co_dinh ?? ''} onChange={e => setSua({ ...sua, gia_ban_co_dinh: e.target.value ? Number(e.target.value) : null })} />
          <input className={inp} placeholder="NCC quen" value={sua.ncc_gan_nhat_ten || ''} onChange={e => setSua({ ...sua, ncc_gan_nhat_ten: e.target.value })} />
          <input className={`${inp} sm:col-span-2`} placeholder="Ghi chú" value={sua.ghi_chu || ''} onChange={e => setSua({ ...sua, ghi_chu: e.target.value })} />
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]"><input type="checkbox" checked={sua.is_active !== false} onChange={e => setSua({ ...sua, is_active: e.target.checked })} /> Đang dùng</label>
          <div className="flex gap-2 sm:col-span-3"><button className={btnGold} onClick={luuMau}><LineIcon name="check" size={14} /> Lưu</button><button className={btnGhost} onClick={() => setSua(null)}>Huỷ</button></div>
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
                  <div className="text-xs text-[var(--gold-400)] mt-0.5">Vốn {tien(m.gia_von_gan_nhat || m.gia_tham_khao || 0)}{m.ncc_gan_nhat_ten ? ` · ${m.ncc_gan_nhat_ten}` : ''}</div>
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
function PhieuDuAn({ projectId, thayGiaVon, laThuMua, laAdmin, bao }: { projectId: string | null; thayGiaVon: boolean; laThuMua: boolean; laAdmin: boolean; bao: (l: 'ok' | 'loi', t: string) => void }) {
  const [duAns, setDuAns] = useState<Project[]>([]);
  const [pid, setPid] = useState(projectId || '');
  const [phieu, setPhieu] = useState<PhieuVatTu | null>(null);
  const [loading, setLoading] = useState(false);
  const [moThem, setMoThem] = useState(false);
  const [form, setForm] = useState<{ phong: string; hang_muc: string; mau_id: string | null; ma_tu_do: string; so_luong: number; don_vi: string; ghi_chu: string }>({ phong: 'Chung', hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, don_vi: 'm2', ghi_chu: '' });
  const [dongY, setDongY] = useState<{ id: string; ghi_chu: string } | null>(null);

  useEffect(() => { api.getProjects({ page_size: '200' }).then(r => setDuAns(r.items || [])).catch(() => setDuAns([])); }, []);

  const tai = useCallback(async () => {
    setLoading(true);
    try { setPhieu(pid ? await api.vatTuPhieu(pid) : null); } catch (e) { bao('loi', loi(e, 'Không tải được phiếu')); setPhieu(null); }
    finally { setLoading(false); }
  }, [pid, bao]);
  useEffect(() => { tai(); }, [tai]);

  const them = async () => {
    if (!form.mau_id && !form.ma_tu_do.trim()) { bao('loi', 'Chọn mẫu hoặc gõ mã'); return; }
    try {
      await api.vatTuThemDong(pid, { phong: form.phong || 'Chung', hang_muc: form.hang_muc || null, mau_id: form.mau_id, ma_tu_do: form.mau_id ? null : form.ma_tu_do, so_luong: form.so_luong, don_vi: form.don_vi, ghi_chu: form.ghi_chu || null });
      bao('ok', 'Đã thêm vào phiếu'); setMoThem(false); setForm(f => ({ ...f, hang_muc: '', mau_id: null, ma_tu_do: '', so_luong: 1, ghi_chu: '' })); tai();
    } catch (e) { bao('loi', loi(e, 'Không thêm được')); }
  };
  const xoa = async (d: DongVatTu) => {
    if (!confirm(`Xoá dòng ${d.ma || d.ma_tu_do}?`)) return;
    try { await api.vatTuXoaDong(d.id); tai(); } catch (e) { bao('loi', loi(e, 'Không xoá được')); }
  };
  const doiTrangThai = async (d: DongVatTu, tt: string) => {
    try { await api.vatTuSuaDong(d.id, { trang_thai: tt as DongVatTu['trang_thai'] }); tai(); } catch (e) { bao('loi', loi(e, 'Không đổi được')); }
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

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <select className={`${inp} flex-1 min-w-[220px]`} value={pid} onChange={e => setPid(e.target.value)}>
          <option value="">— Chọn dự án —</option>
          {duAns.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}
        </select>
        {pid && <Link href={`/projects?id=${pid}`} className={btnGhost}><LineIcon name="eye" size={14} /> Mở dự án</Link>}
        {pid && <button className={btnGold} onClick={() => setMoThem(v => !v)}><LineIcon name="plus" size={14} /> Khách chọn mẫu</button>}
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
          <div className="flex gap-2 sm:col-span-2 lg:col-span-4"><button className={btnGold} onClick={them}><LineIcon name="check" size={14} /> Thêm dòng</button><button className={btnGhost} onClick={() => setMoThem(false)}>Đóng</button></div>
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
                      {d.ghi_chu && <div className="text-xs text-[var(--text-muted)]">{d.ghi_chu}</div>}
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
                      {laThuMua && d.trang_thai === 'da_chot_gia' && <button className={`${btn} text-xs`} onClick={() => doiTrangThai(d, 'da_dat')}><LineIcon name="receipt" size={12} /> Đã đặt</button>}
                      {laThuMua && d.trang_thai === 'da_dat' && <button className={`${btn} text-xs`} onClick={() => doiTrangThai(d, 'da_giao')}><LineIcon name="truck" size={12} /> Đã giao</button>}
                      {(laAdmin || !['da_chot_gia', 'da_dat', 'da_giao'].includes(d.trang_thai)) && (
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
  useEffect(() => { tai(); }, [tai]);

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
                  {d.so_bao_gia} báo giá{d.gia_von_gan_nhat ? ` · giá gần nhất ${tien(d.gia_von_gan_nhat)}` : d.gia_tham_khao ? ` · tham khảo ${tien(d.gia_tham_khao)}` : ''}
                  {d.ghi_chu && <> · {d.ghi_chu}</>}
                </div>
              </div>
            </button>
            {dangMo && (
              <div className="border-t border-[var(--border-subtle)] p-3 space-y-3 bg-[var(--surface-1)]">
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
                        <span className="flex-1" />
                        {laThuMua && b.con_hang && <button className={`${btnGold} text-xs`} onClick={() => chot(d.id, b.id)}><LineIcon name="check" size={12} /> Chốt giá này</button>}
                        {laThuMua && <button className="text-[var(--text-muted)] hover:text-red-400 p-1" onClick={async () => { await api.vatTuXoaBaoGia(b.id).catch(() => null); tai(); }}><LineIcon name="trash" size={12} /></button>}
                      </div>
                    ))}
                  </div>
                )}
                {laThuMua && (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      <input className={inp} placeholder="Tên NCC *" value={bg.ncc_ten} onChange={e => setBg({ ...bg, ncc_ten: e.target.value })} />
                      <input className={inp} type="number" placeholder={`Giá vốn/${d.don_vi} *`} value={bg.gia} onChange={e => setBg({ ...bg, gia: e.target.value })} />
                      <input className={inp} placeholder="Giao (vd 3 ngày)" value={bg.ngay_giao} onChange={e => setBg({ ...bg, ngay_giao: e.target.value })} />
                      <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)] px-1"><input type="checkbox" checked={bg.con_hang} onChange={e => setBg({ ...bg, con_hang: e.target.checked })} /> Còn hàng</label>
                      <button className={btnGhost} onClick={() => themBaoGia(d.id)}><LineIcon name="plus" size={14} /> Thêm báo giá</button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {giaTay?.id === d.id ? (
                        <>
                          <input className={`${inp} w-40`} type="number" placeholder="Giá vốn" value={giaTay.gia_von} onChange={e => setGiaTay({ ...giaTay, gia_von: e.target.value })} />
                          <input className={`${inp} w-48`} placeholder="NCC" value={giaTay.ncc_ten} onChange={e => setGiaTay({ ...giaTay, ncc_ten: e.target.value })} />
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
      <button className={btnGold} disabled={saving} onClick={luu}><LineIcon name="check" size={14} /> {saving ? 'Đang lưu…' : 'Lưu'}</button>
    </div>
  );
}
