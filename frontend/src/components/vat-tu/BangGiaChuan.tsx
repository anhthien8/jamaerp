'use client';

// Bảng giá chuẩn (22/11/2026) — «đơn giá là hằng số»: chỉ Giám đốc đặt giá chuẩn (đơn giá bán) của
// từng mẫu; Thu mua nạp giá nhập của các NCC làm căn cứ. Cả bảng là giá vốn + tên NCC + mức lời nên
// server chỉ trả cho Thu mua và Giám đốc.

import { useXacNhan } from '@/components/ui/XacNhan';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type BangGiaChuanVatTu, type GiaChuanVatTu } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import InfoTip from '@/components/ui/InfoTip';
import { ngayThang } from '@/lib/du-lieu-chung';
import { AnhMau, NHAN_HANG_NCC, NccGoiY, btn, btnGhost, btnGold, inp, loi, tienDu, type Bao } from './chung';

type Loc = 'tat_ca' | 'chua_co' | 'duoi_he_so';
const LOC: { id: Loc; nhan: string; dem: 'tong' | 'so_chua_co' | 'so_duoi_he_so' }[] = [
  { id: 'tat_ca', nhan: 'Tất cả', dem: 'tong' },
  { id: 'chua_co', nhan: 'Chưa có giá chuẩn', dem: 'so_chua_co' },
  { id: 'duoi_he_so', nhan: 'Lời dưới hệ số', dem: 'so_duoi_he_so' },
];
const CO_TRANG = 30;
// Ô tiền: chỉ giữ chữ số, hiện có dấu chấm ngăn nghìn cho dễ soát
const chiSo = (s: string) => s.replace(/\D/g, '').slice(0, 12);
const hienSo = (s: string) => (s ? Number(s).toLocaleString('vi-VN') : '');

/** `locDau`: bộ lọc mở sẵn lấy từ URL (?loc=) — giá trị lạ thì về «Tất cả» (gửi sai server trả 422). */
export default function BangGiaChuan({ locDau, bao }: { locDau?: string | null; bao: Bao }) {
  const [loc, setLoc] = useState<Loc>(LOC.find(l => l.id === locDau)?.id ?? 'tat_ca');
  const [q, setQ] = useState('');
  const [nhom, setNhom] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BangGiaChuanVatTu | null>(null);
  const [dang, setDang] = useState(true);
  const [nhoms, setNhoms] = useState<{ nhom: string; so_mau: number }[]>([]);

  useEffect(() => { api.vatTuNhom().then(setNhoms).catch(() => setNhoms([])); }, []);

  const lanTai = useRef(0);
  const tai = useCallback(async () => {
    const lan = ++lanTai.current; // gõ tìm nhanh trên mạng chậm: chỉ nhận kết quả của lần tải mới nhất
    setDang(true);
    try {
      const p: Record<string, string> = { loc, page: String(page), page_size: String(CO_TRANG) };
      if (q.trim()) p.q = q.trim();
      if (nhom) p.nhom = nhom;
      const r = await api.vatTuGiaChuan(p);
      if (lan !== lanTai.current) return;
      setData(r);
      // Trang đang đứng không còn dòng nào (vừa sửa/xoá làm danh sách ngắn lại) → lùi về trang cuối
      if (!r.items.length && r.total > 0 && page > 1) setPage(Math.ceil(r.total / r.page_size));
    } catch (e) { if (lan === lanTai.current) bao('loi', loi(e, 'Không tải được bảng giá chuẩn')); }
    finally { if (lan === lanTai.current) setDang(false); }
  }, [loc, q, nhom, page, bao]);
  useEffect(() => { const t = setTimeout(tai, 250); return () => clearTimeout(t); }, [tai]);

  // Sửa xong một mẫu: thay tại chỗ (thẻ không nhảy khỏi tay người đang duyệt cả danh sách) và
  // chỉnh số đếm trên các nút lọc theo cờ mới của mẫu đó.
  const thay = (moi: GiaChuanVatTu) => setData(d => {
    const cu = d?.items.find(x => x.id === moi.id);
    if (!d || !cu) return d;
    return {
      ...d, items: d.items.map(x => (x.id === moi.id ? moi : x)),
      so_chua_co: d.so_chua_co + Number(moi.chua_co) - Number(cu.chua_co),
      so_duoi_he_so: d.so_duoi_he_so + Number(moi.duoi_he_so) - Number(cu.duoi_he_so),
    };
  });
  const soTrang = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--text-muted)]">
        Giá chuẩn là đơn giá bán của mẫu — chỉ Giám đốc đặt. Đổi giá chuẩn thì dòng tạo sau và dòng khách chưa đồng ý giá
        (chưa đặt hàng) lấy ngay giá mới; dòng khách đã đồng ý và dòng đã đặt hàng giữ giá cũ.
        Thu mua nạp giá nhập của từng NCC làm căn cứ. Giá gợi ý = giá nhập mốc × (1 + hệ số nhóm).
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
        {LOC.map(l => (
          <button key={l.id} onClick={() => { setLoc(l.id); setPage(1); }}
            className={`${btn} whitespace-nowrap ${loc === l.id ? 'bg-[var(--surface-3)] text-[var(--text-primary)] border-[var(--gold-400)]' : 'text-[var(--text-secondary)] border-[var(--border-subtle)]'}`}>
            {l.nhan}
            {data && <span className="ml-1 rounded-full bg-[var(--gold-400)]/20 text-[var(--gold-400)] px-1.5 text-xs">{data[l.dem]}</span>}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"><LineIcon name="search" size={16} /></span>
          <input className={`${inp} pl-9`} placeholder="Tìm mã, tên, hãng…" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} />
        </div>
        <select className={`${inp} w-auto`} aria-label="Lọc theo nhóm" value={nhom} onChange={e => { setNhom(e.target.value); setPage(1); }}>
          <option value="">Tất cả nhóm</option>
          {nhoms.map(n => <option key={n.nhom} value={n.nhom}>{n.nhom} ({n.so_mau})</option>)}
        </select>
      </div>
      <NccGoiY />

      {!data ? (
        dang ? <div className="text-sm text-[var(--text-muted)] p-4">Đang tải…</div>
          : <div className="glass-card p-8 text-center text-[var(--text-muted)] space-y-2"><div>Không tải được bảng giá chuẩn.</div><button className={btnGhost} onClick={tai}><LineIcon name="refresh" size={14} /> Thử lại</button></div>
      ) : data.items.length === 0 ? (
        <div className="glass-card p-8 text-center text-[var(--text-muted)]">
          {loc === 'chua_co' ? 'Mẫu nào cũng đã có giá chuẩn.' : loc === 'duoi_he_so' ? 'Không có mẫu nào lời dưới hệ số nhóm.' : 'Không có mẫu nào khớp.'}
        </div>
      ) : (
        <div className={`grid grid-cols-1 lg:grid-cols-2 gap-2 items-start ${dang ? 'opacity-60' : ''}`}>
          {/* key kèm giá chuẩn: giá đổi (mình lưu hoặc tải lại) thì ô nhập lấy lại đúng số đang lưu */}
          {data.items.map(m => <TheMau key={`${m.id}|${m.gia_chuan ?? ''}`} m={m} coTheSua={data.co_the_sua_gia_chuan} onDoi={thay} onTaiLai={tai} bao={bao} />)}
        </div>
      )}

      {data && soTrang > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button className={btnGhost} disabled={page <= 1 || dang} onClick={() => setPage(p => p - 1)}>Trước</button>
          <span className="text-sm text-[var(--text-muted)]">Trang {data.page}/{soTrang} · {data.total} mẫu</span>
          <button className={btnGhost} disabled={page >= soTrang || dang} onClick={() => setPage(p => p + 1)}>Sau</button>
        </div>
      )}
    </div>
  );
}

/** Một mẫu: giá nhập theo NCC → giá gợi ý → giá chuẩn + mức lời. Dạng thẻ nên điện thoại xem vừa. */
function TheMau({ m, coTheSua, onDoi, onTaiLai, bao }: { m: GiaChuanVatTu; coTheSua: boolean; onDoi: (m: GiaChuanVatTu) => void; onTaiLai: () => void; bao: Bao }) {
  const xacNhan = useXacNhan();
  const giaDangLuu = m.gia_chuan != null ? String(Math.round(m.gia_chuan)) : '';
  const [gia, setGia] = useState(giaDangLuu);
  const [them, setThem] = useState<{ ncc: string; gia: string; ghi_chu: string } | null>(null);
  const [dang, setDang] = useState(false);

  const luuGiaChuan = async () => {
    const so = gia ? Number(gia) : null;
    // Khớp `ghi_doi_gia_chuan` + `chot_gia` ở server: bỏ giá chuẩn đổi ngay giá của dòng khách chưa đồng ý
    if (so === null && !await xacNhan(`Bỏ giá chuẩn của ${m.ma}?\n\nDòng tạo sau và dòng khách chưa đồng ý giá sẽ tính ngay giá bán = giá vốn × (1 + hệ số nhóm) — chưa chốt giá vốn thì chưa có giá bán.\nDòng khách đã đồng ý giữ giá cho tới khi Thu mua chốt lại giá vốn; lúc đó cũng tính theo hệ số, giá đổi thì khách phải duyệt lại.\nDòng đã đặt hàng không đổi.`)) return;
    setDang(true);
    try {
      onDoi(await api.vatTuDatGiaChuan(m.id, so));
      bao('ok', so === null ? `Đã bỏ giá chuẩn của ${m.ma}` : `Đã đặt giá chuẩn ${m.ma}: ${tienDu(so)}/${m.don_vi}`);
    } catch (e) { bao('loi', loi(e, 'Không lưu được giá chuẩn')); }
    finally { setDang(false); }
  };
  const luuGiaNhap = async () => {
    if (!them) return;
    const ten = them.ncc.trim();
    if (!ten) { bao('loi', 'Chọn hoặc gõ tên nhà cung cấp'); return; }
    if (!(Number(them.gia) > 0)) { bao('loi', 'Giá nhập phải lớn hơn 0'); return; }
    setDang(true);
    try {
      onDoi(await api.vatTuThemGiaNhap(m.id, { ncc_ten: ten, gia: Number(them.gia), ghi_chu: them.ghi_chu.trim() || undefined }));
      bao('ok', `Đã nạp giá nhập ${m.ma}: ${tienDu(Number(them.gia))} · ${ten}`);
      setThem(null);
    } catch (e) { bao('loi', loi(e, 'Không nạp được giá nhập')); }
    finally { setDang(false); }
  };
  const xoaGiaNhap = async (id: string, ten: string) => {
    if (!await xacNhan(`Xoá giá nhập của ${ten} cho ${m.ma}? Giá nạp liền trước của NCC này (nếu có) sẽ hiện lại.`)) return;
    try { await api.vatTuXoaGiaNhap(id); bao('ok', 'Đã xoá giá nhập'); onTaiLai(); }
    catch (e) { bao('loi', loi(e, 'Không xoá được giá nhập')); }
  };

  const ganNhat = m.gia_nhap_gan_nhat;
  return (
    <div className="glass-card p-3 space-y-2">
      <div className="flex gap-3">
        <AnhMau url={m.anh_url} size={48} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-medium text-[var(--text-primary)]">{m.ma}</span>
            <span className="text-xs rounded-full bg-[var(--surface-3)] px-2 text-[var(--text-secondary)]">{m.nhom}</span>
            {m.chua_co && <span className="text-xs rounded-full bg-amber-500/15 text-amber-300 px-2">chưa có giá chuẩn</span>}
            {m.duoi_he_so && <span className="text-xs rounded-full bg-red-500/15 text-red-300 px-2">lời dưới hệ số</span>}
          </div>
          <div className="text-xs text-[var(--text-muted)] truncate">{[m.ten, m.hang, `đơn vị ${m.don_vi}`].filter(Boolean).join(' · ')}</div>
        </div>
      </div>

      <div className="rounded-xl bg-[var(--surface-2)] p-2 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-[var(--text-secondary)]">Giá nhập theo NCC</span>
          {!them && <button className={`${btnGhost} text-xs`} onClick={() => setThem({ ncc: '', gia: '', ghi_chu: '' })}><LineIcon name="plus" size={12} /> Thêm giá nhập</button>}
        </div>
        {m.gia_nhap.length === 0 && <div className="text-xs text-[var(--text-muted)]">Chưa có giá nhập của NCC nào.</div>}
        {m.gia_nhap.map(g => (
          <div key={g.supplier_id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
            <span className="text-[var(--text-primary)]">{g.ncc_ten}</span>
            {g.hang && NHAN_HANG_NCC[g.hang] && <span className="text-xs rounded-full bg-[var(--surface-3)] px-2 text-[var(--text-secondary)]">{NHAN_HANG_NCC[g.hang]}</span>}
            <span className="text-[var(--gold-400)] font-medium">{tienDu(g.gia)}</span>
            <span className="text-xs text-[var(--text-muted)]">{ngayThang(g.luc)}{g.gia_nhap_id ? '' : ' · báo giá dự án'}</span>
            {g.cu && <span className="text-xs rounded-full bg-amber-500/15 text-amber-300 px-1.5" title="Giá quá 60 ngày — hỏi lại NCC">giá cũ</span>}
            {g.ghi_chu && <span className="text-xs text-[var(--text-muted)]">{g.ghi_chu}</span>}
            {g.xoa_duoc && g.gia_nhap_id && (
              <button className="ml-auto p-1 text-[var(--text-muted)] hover:text-red-400" aria-label={`Xoá giá nhập của ${g.ncc_ten}`}
                onClick={() => xoaGiaNhap(g.gia_nhap_id as string, g.ncc_ten)}><LineIcon name="trash" size={12} /></button>
            )}
          </div>
        ))}
        {them && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            <input className={inp} list="ds-ncc" autoFocus placeholder="NCC * — gõ để chọn NCC có sẵn" value={them.ncc} onChange={e => setThem({ ...them, ncc: e.target.value })} />
            <input className={inp} inputMode="numeric" placeholder={`Giá nhập/${m.don_vi} *`} value={hienSo(them.gia)} onChange={e => setThem({ ...them, gia: chiSo(e.target.value) })} />
            <input className={`${inp} sm:col-span-2`} placeholder="Ghi chú (bảng giá tháng nào, điều kiện giao…)" value={them.ghi_chu} onChange={e => setThem({ ...them, ghi_chu: e.target.value })} />
            <div className="flex gap-2 sm:col-span-2">
              <button className={btnGold} disabled={dang} onClick={luuGiaNhap}><LineIcon name="check" size={14} color="currentColor" /> {dang ? 'Đang lưu…' : 'Lưu giá nhập'}</button>
              <button className={btnGhost} disabled={dang} onClick={() => setThem(null)}>Huỷ</button>
            </div>
          </div>
        )}
      </div>

      <div className="text-xs text-[var(--text-secondary)] space-y-0.5">
        <div>
          <span className="text-[var(--text-muted)]">Giá nhập mốc</span>{' '}
          {m.gia_nhap_moc != null ? <span className="text-[var(--text-primary)]">{tienDu(m.gia_nhap_moc)}</span> : '—'}
          {ganNhat ? (
            <span className="text-[var(--text-muted)]"> · giá vốn chốt gần nhất{ganNhat.ncc_ten ? ` · ${ganNhat.ncc_ten}` : ''}{ganNhat.luc ? ` · ${ngayThang(ganNhat.luc)}` : ''}
              {ganNhat.cu && <span className="ml-1 rounded-full bg-amber-500/15 text-amber-300 px-1.5">giá cũ</span>}</span>
          ) : m.gia_nhap_moc != null && <span className="text-[var(--text-muted)]"> · giá NCC thấp nhất</span>}
          {m.gia_tham_khao ? <span className="text-[var(--text-muted)]"> · tham khảo danh mục {tienDu(m.gia_tham_khao)}</span> : null}
        </div>
        <div className="flex flex-wrap gap-x-4">
          <span><span className="text-[var(--text-muted)]">Giá gợi ý (+{m.he_so}%)</span> <span className="text-[var(--text-primary)] font-medium">{m.gia_goi_y != null ? tienDu(m.gia_goi_y) : '—'}</span></span>
          <span><span className="text-[var(--text-muted)]">Mức lời <InfoTip text="(Giá chuẩn − giá nhập mốc) ÷ giá nhập mốc. Thấp hơn hệ số lãi của nhóm thì hiện đỏ và gắn nhãn «lời dưới hệ số» — nên xét lại giá chuẩn hoặc tìm NCC rẻ hơn." /></span>{' '}
            {m.muc_loi_pct != null ? <span className={`font-medium ${m.duoi_he_so ? 'text-red-300' : 'text-emerald-400'}`}>{m.muc_loi_pct.toLocaleString('vi-VN')}%</span> : '—'}
            <span className="text-[var(--text-muted)]"> / hệ số nhóm {m.he_so}%</span></span>
        </div>
      </div>

      {coTheSua ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] flex-1 min-w-[190px]"><span className="shrink-0">Giá chuẩn/{m.don_vi}</span>
            <input className={inp} inputMode="numeric" placeholder="Chưa có" value={hienSo(gia)} onChange={e => setGia(chiSo(e.target.value))} /></label>
          {m.gia_goi_y != null && gia !== String(m.gia_goi_y) && <button className={`${btnGhost} text-xs`} disabled={dang} onClick={() => setGia(String(m.gia_goi_y))}>Lấy giá gợi ý</button>}
          <button className={btnGold} disabled={dang || gia === giaDangLuu} onClick={luuGiaChuan}><LineIcon name="check" size={14} color="currentColor" /> {dang ? 'Đang lưu…' : 'Lưu'}</button>
        </div>
      ) : (
        <div className="text-sm text-[var(--text-secondary)]">Giá chuẩn{' '}
          {m.gia_chuan != null ? <span className="text-[var(--gold-400)] font-semibold">{tienDu(m.gia_chuan)}/{m.don_vi}</span> : <span className="text-amber-300">chưa có — chờ Giám đốc đặt</span>}
        </div>
      )}
    </div>
  );
}
