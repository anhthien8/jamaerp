'use client';

import { useXacNhan } from '@/components/ui/XacNhan';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { api, ApiError, type HangNcc, type Supplier, type SupplierBody, type SupplierQuote, type PriceComparison } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import PriceComparisonTable from '@/components/ui/PriceComparison';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';

// Số điện thoại → dạng zalo.me nhận (chỉ chữ số, 84… → 0…); rỗng khi không ra số hợp lệ
const soZalo = (s?: string | null) => { const so = (s || '').replace(/\D/g, '').replace(/^84(?=\d{9}$)/, '0'); return /^0\d{9,10}$/.test(so) ? so : ''; };
// Bỏ dấu + viết thường để gõ «go soi» vẫn ra «Gỗ Sồi» (cùng cách với trang Vật tư)
const boDau = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
const loi = (e: unknown, mac: string) => (e instanceof Error && e.message ? e.message : mac);

const CATEGORY_LABELS: Record<string, string> = {
  wood: 'Gỗ', stone: 'Đá', metal: 'Kim loại', paint: 'Sơn',
  electrical: 'Điện', plumbing: 'Nước', furniture: 'Nội thất',
  glass: 'Kính', general: 'Khác',
};

const CATEGORY_COLORS: Record<string, string> = {
  wood: '#8B6914', stone: '#6B7280', metal: '#9CA3AF', paint: '#3B82F6',
  electrical: '#F59E0B', plumbing: '#06B6D4', furniture: '#A78BFA',
  glass: '#34D399', general: '#9CA3AF',
};

// Hạng NCC (22/11/2026) — khớp HANG_NCC ở backend; chưa có hạng = «Chưa xếp»
const HANG_LABELS: Record<HangNcc, string> = { chinh: 'Chính', du_phong: 'Dự phòng', thu: 'Đang thử' };
const HANG_MAU: Record<HangNcc, { background: string; color: string }> = {
  chinh: { background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' },
  du_phong: { background: 'var(--info-bg)', color: 'var(--info)' },
  thu: { background: 'var(--warning-bg)', color: 'var(--warning)' },
};

const BAO_GIA_TRONG = { material_name: '', material_category: 'general', unit: 'cái', unit_price: 0, min_quantity: 1, lead_time_days: 3, notes: '' };
const FORM_TRONG = { name: '', ma_so_thue: '', ten_cong_ty: '', contact_name: '', phone: '', zalo: '', email: '', address: '', region: '', category: 'general', hang: '' as HangNcc | '', notes: '', chiet_khau_pct: 0 };
// Các ô chữ của form NCC. `max` = độ dài cột trong DB — chặn ngay ở ô nhập, khỏi để máy chủ báo lỗi.
const O_CHU: { key: 'name' | 'ten_cong_ty' | 'contact_name' | 'phone' | 'zalo' | 'email' | 'address' | 'region'; label: string; max: number; rong?: boolean; goiY?: string }[] = [
  { key: 'name', label: 'Tên NCC *', max: 255, rong: true },
  { key: 'ten_cong_ty', label: 'Tên công ty (theo mã số thuế)', max: 255, rong: true },
  { key: 'contact_name', label: 'Người liên hệ', max: 255 },
  { key: 'phone', label: 'Điện thoại', max: 20 },
  { key: 'zalo', label: 'Zalo', max: 50, goiY: 'Để trống nếu trùng SĐT' },
  { key: 'email', label: 'Email', max: 255 },
  { key: 'address', label: 'Địa chỉ', max: 500, rong: true },
  { key: 'region', label: 'Khu vực', max: 100, goiY: 'VD: TP.HCM' },
];
const O_NHAP = { background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' };

function NhanHang({ hang }: { hang?: HangNcc | null }) {
  if (!hang || !HANG_LABELS[hang]) return null;
  return <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={HANG_MAU[hang]}>{HANG_LABELS[hang]}</span>;
}
function NhanNgung() {
  return <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>Đã ngừng dùng</span>;
}

export default function SuppliersPage() {
  const xacNhan = useXacNhan();
  // Backend chỉ cho admin + supervisor (mua hàng) thêm/sửa NCC (require_supplier_write).
  // Kế toán vẫn vào được trang này để tra giá, nên trước 12/08/2026 họ thấy nút "Thêm nhà
  // cung cấp" rồi nhập cả bảng xong mới ăn 403. Ẩn nút cho đúng quyền thật.
  const { user, effectivePermissions } = useAuth();
  const { toast } = useToast();
  // 22/09: theo ô «Sửa Nhà cung cấp» trong ma trận thay vì hardcode 2 vai trò —
  // nhân sự Thu mua được cấp là thấy nút ngay, không phải bấm rồi ăn 403.
  const canEditSuppliers = effectivePermissions.canEditSuppliers;
  // Gộp NCC trùng = xoá hẳn một NCC: máy chủ chỉ cho Ban giám đốc, không cấp qua ma trận.
  const laAdmin = user?.role === 'admin';
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [hangFilter, setHangFilter] = useState('all'); // all | chinh | du_phong | thu | chua_xep
  const [hienNgung, setHienNgung] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<SupplierQuote[]>([]);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [compareData, setCompareData] = useState<PriceComparison | null>(null);
  const [compareMaterial, setCompareMaterial] = useState('');

  // Cả trang trước 12/08/2026 dùng `catch { /* ignore */ }`: NCC không tải được thì hiện
  // "Chưa có nhà cung cấp", thêm NCC thất bại thì bảng chỉ đóng lại im lặng. Nay mọi lỗi
  // đều hiện chữ, và các nút lưu bị khoá trong lúc gửi để không tạo trùng khi bấm đúp.
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [comparing, setComparing] = useState(false);

  // Form thêm / sửa NCC: 'moi' = thêm, Supplier = đang sửa NCC đó, null = đóng
  const [formNcc, setFormNcc] = useState<Supplier | 'moi' | null>(null);
  const [form, setForm] = useState(FORM_TRONG);
  // Lỗi hiện NGAY TRONG bảng nhập (banner của trang nằm khuất sau lớp phủ).
  // `trung` = NCC đang có mà máy chủ báo trùng tên / mã số thuế (409).
  const [formLoi, setFormLoi] = useState<{ message: string; trung?: { id: string; ten: string; dangDung: boolean } } | null>(null);
  const [traMst, setTraMst] = useState('');
  const [quoteForm, setQuoteForm] = useState(BAO_GIA_TRONG);
  // Gộp NCC trùng: `nguon` bị xoá, `dichId` = NCC giữ lại
  const [gop, setGop] = useState<{ nguon: Supplier; dichId: string; tim: string; loi?: string } | null>(null);
  // Gộp hai tên KHÁC cách viết: tên cũ còn nằm ở Google Sheet / tệp báo giá thì lần nhập sau tạo lại NCC vừa gộp.
  // Nằm lại trên trang tới khi bấm «Đã hiểu» — toast 3 giây không kịp đọc.
  const [luuYGop, setLuuYGop] = useState<string | null>(null);

  // Tải HẾT một lần (kể cả NCC đã ngừng) rồi lọc tại chỗ: gõ tìm không gọi máy chủ từng phím,
  // bảng «Gộp» và nút «Mở NCC đang có» luôn có đủ danh sách. Trước 22/11/2026 trang chỉ
  // lấy 50 NCC đầu, không có nút sang trang.
  const loadSuppliers = useCallback(async () => {
    setLoading(true);
    try {
      const ds: Supplier[] = [];
      for (let page = 1; ; page++) {
        const res = await api.getSuppliers({ page: String(page), page_size: '500', include_inactive: 'true' });
        ds.push(...res.items);
        if (page >= (res.total_pages || 1)) break;
      }
      setSuppliers(ds);
      setError(null);
    } catch (e) {
      setSuppliers([]);
      setError(loi(e, 'Chưa tải được danh sách nhà cung cấp.'));
    }
    setLoading(false);
  }, []);

  useEffect(() => { void Promise.resolve().then(() => loadSuppliers()); }, [loadSuppliers]);

  const selected = useMemo(() => suppliers.find(s => s.id === selectedId) ?? null, [suppliers, selectedId]);
  const soNgung = useMemo(() => suppliers.filter(s => !s.is_active).length, [suppliers]);
  const khuVuc = useMemo(() => Array.from(new Set(suppliers.map(s => s.region || '').filter(Boolean))).sort((a, b) => a.localeCompare(b, 'vi')), [suppliers]);
  const hienThi = useMemo(() => {
    const k = boDau(search.trim());
    return suppliers.filter(s =>
      (hienNgung || s.is_active)
      && (categoryFilter === 'all' || s.category === categoryFilter)
      && (hangFilter === 'all' || (s.hang || 'chua_xep') === hangFilter)
      && (!k || boDau(`${s.name} ${s.contact_name || ''} ${s.phone || ''} ${s.ma_so_thue || ''} ${s.ten_cong_ty || ''}`).includes(k)));
  }, [suppliers, search, categoryFilter, hangFilter, hienNgung]);
  const ungVienGop = useMemo(() => {
    if (!gop) return [];
    const k = boDau(gop.tim.trim());
    return suppliers.filter(s => s.id !== gop.nguon.id
      && (!k || boDau(`${s.name} ${s.ma_so_thue || ''} ${s.ten_cong_ty || ''} ${s.phone || ''}`).includes(k)));
  }, [gop, suppliers]);
  const dichGop = gop ? suppliers.find(s => s.id === gop.dichId) ?? null : null;

  // Thay (hoặc thêm) một NCC trong danh sách đang giữ bằng bản máy chủ vừa trả — không tải lại cả trang,
  // nên NCC vừa «Ngừng dùng» vẫn nằm ở thẻ chi tiết để bấm «Dùng lại» nếu lỡ tay.
  const capNhatDs = (r: Supplier) => setSuppliers(ds => [...ds.filter(x => x.id !== r.id), r].sort((a, b) => a.name.localeCompare(b.name, 'vi')));

  const loadQuotes = async (supplierId: string) => {
    setQuotesLoading(true);
    try {
      const data = await api.getSupplierQuotes(supplierId);
      setQuotes(Array.isArray(data) ? data : []);
    } catch (e) {
      setQuotes([]);
      setError(loi(e, 'Chưa tải được báo giá của nhà cung cấp này.'));
    }
    setQuotesLoading(false);
  };

  const handleSelectSupplier = (id: string) => {
    setSelectedId(id);
    loadQuotes(id);
    // Điện thoại: danh sách nhường chỗ cho thẻ chi tiết → đưa về đầu trang để thấy thẻ từ dòng tên
    requestAnimationFrame(() => { if (window.matchMedia('(max-width: 1023px)').matches) window.scrollTo(0, 0); });
  };

  // Điện thoại: quay lại danh sách, cuộn tới đúng NCC vừa xem
  const veDanhSach = () => {
    const id = selectedId;
    setSelectedId(null);
    requestAnimationFrame(() => document.getElementById(`ncc-${id}`)?.scrollIntoView({ block: 'center' }));
  };

  const moThem = () => { setForm(FORM_TRONG); setFormLoi(null); setTraMst(''); setFormNcc('moi'); };
  const moSua = (s: Supplier) => {
    setForm({
      name: s.name, ma_so_thue: s.ma_so_thue || '', ten_cong_ty: s.ten_cong_ty || '', contact_name: s.contact_name || '',
      phone: s.phone || '', zalo: s.zalo || '', email: s.email || '', address: s.address || '', region: s.region || '',
      category: s.category, hang: s.hang || '', notes: s.notes || '', chiet_khau_pct: s.chiet_khau_pct || 0,
    });
    setFormLoi(null); setTraMst(''); setFormNcc(s);
  };

  const handleSaveSupplier = async () => {
    if (saving || !formNcc) return;
    if (!form.name.trim()) { setFormLoi({ message: 'Vui lòng nhập tên nhà cung cấp.' }); return; }
    setSaving(true);
    // Ô để trống gửi null: khi sửa, máy chủ hiểu là xoá ô đó (hạng null = «Chưa xếp»)
    const t = (v: string) => v.trim() || null;
    const body: SupplierBody = {
      name: form.name.trim(), ma_so_thue: t(form.ma_so_thue), ten_cong_ty: t(form.ten_cong_ty),
      contact_name: t(form.contact_name), phone: t(form.phone), zalo: t(form.zalo), email: t(form.email),
      address: t(form.address), region: t(form.region), category: form.category, hang: form.hang || null,
      notes: t(form.notes), chiet_khau_pct: form.chiet_khau_pct,
    };
    try {
      if (formNcc === 'moi') {
        const r = await api.createSupplier(body);
        capNhatDs(r);
        handleSelectSupplier(r.id);
      } else {
        capNhatDs(await api.updateSupplier(formNcc.id, body));
      }
      setFormNcc(null);
      setFormLoi(null);
      setError(null);
    } catch (e) {
      // 409: tên / mã số thuế trùng một NCC đang có — câu báo đã nêu đích danh, kèm id để mở thẳng NCC đó
      const d = e instanceof ApiError && e.status === 409 ? e.data : undefined;
      setFormLoi({
        message: loi(e, 'Không lưu được nhà cung cấp.'),
        trung: typeof d?.supplier_id === 'string'
          ? { id: d.supplier_id, ten: String(d.supplier_name ?? ''), dangDung: d.is_active !== false } : undefined,
      });
    }
    setSaving(false);
  };

  // Từ lỗi trùng: đóng form, mở đúng NCC đang có. NCC đã ngừng thì bật luôn «Hiện NCC đã ngừng»
  // để nó nằm trong danh sách; thẻ chi tiết có sẵn nút «Dùng lại».
  const moNccDangCo = async (trung: { id: string; dangDung: boolean }) => {
    setFormNcc(null);
    setFormLoi(null);
    if (!trung.dangDung) setHienNgung(true);
    if (!suppliers.some(s => s.id === trung.id)) await loadSuppliers();
    handleSelectSupplier(trung.id);
  };

  // Sửa nhanh ngay trên thẻ chi tiết (hạng, ngừng dùng / dùng lại) — 1 chạm, không mở form
  const luuNhanh = async (id: string, body: SupplierBody, xong?: string) => {
    if (saving) return;
    setSaving(true);
    try {
      capNhatDs(await api.updateSupplier(id, body));
      setError(null);
      if (xong) toast(xong, 'success');
    } catch (e) {
      setError(loi(e, 'Không lưu được thay đổi.'));
    }
    setSaving(false);
  };

  const handleGop = async () => {
    if (!gop || !dichGop || saving) return;
    const a = gop.nguon.name, b = dichGop.name;
    if (!await xacNhan(`Gộp «${a}» vào «${b}»?\n\n«${a}» sẽ bị xoá hẳn; mọi phiếu vật tư, mẫu vật tư, báo giá và giá nhập của nó chuyển sang «${b}».\n\nKhông hoàn tác được.`)) return;
    setSaving(true);
    try {
      const r = await api.gopSupplier(gop.nguon.id, dichGop.id);
      const soDong = Object.values(r.da_chuyen).reduce((x, y) => x + y, 0);
      setSuppliers(ds => ds.filter(x => x.id !== gop.nguon.id).map(x => (x.id === r.supplier.id ? r.supplier : x)));
      setGop(null);
      setError(null);
      handleSelectSupplier(r.supplier.id);
      toast(`Đã gộp «${a}» vào «${r.supplier.name}» — chuyển ${soDong} dòng dữ liệu`, 'success');
      // Chỉ thêm, không xoá lưu ý của lần gộp trước: BGĐ gộp liền mấy NCC, lưu ý nào chưa bấm «Đã hiểu» thì còn nguyên
      if (r.ten_khac_khoa) {
        setLuuYGop(cu => `${cu ? `${cu}\n` : ''}Tên «${a}» viết khác «${r.supplier.name}»: sửa tên này trong Google Sheet / tệp báo giá nguồn, không thì lần nhập sau sẽ tạo lại nhà cung cấp vừa gộp.`);
      }
    } catch (e) {
      setGop(g => g && { ...g, loi: loi(e, 'Không gộp được nhà cung cấp.') });
    }
    setSaving(false);
  };

  const handleAddQuote = async () => {
    if (!selected || saving) return;
    if (!quoteForm.material_name.trim()) { setError('Vui lòng nhập tên vật tư.'); return; }
    setSaving(true);
    try {
      // Không gửi valid_from: bảng supplier_quotes không có cột này, backend tự đặt quote_date.
      await api.addSupplierQuote(selected.id, quoteForm);
      setShowQuoteModal(false);
      setQuoteForm(BAO_GIA_TRONG);
      setError(null);
      loadQuotes(selected.id);
    } catch (e) {
      setError(loi(e, 'Không thêm được báo giá.'));
    }
    setSaving(false);
  };

  // `ten`: bấm «So sánh» ngay trên một dòng báo giá — khỏi gõ lại tên vật tư vào ô so sánh.
  const handleCompare = async (ten?: string) => {
    const vatTu = (ten ?? compareMaterial).trim();
    if (!vatTu || comparing) return;
    if (ten) setCompareMaterial(ten);
    setComparing(true);
    try {
      const data = await api.comparePrices(vatTu);
      setCompareData(data);
      setShowCompare(true);
      setError(null);
    } catch (e) {
      setError(loi(e, 'Không so sánh được giá vật tư này.'));
    }
    setComparing(false);
  };

  const fmt = (n: number) => n.toLocaleString('vi-VN');

  return (
    <Sidebar>
    {/* Trang duy nhất từng thiếu Sidebar: vào từ menu xong là "kẹt" — không có
        thanh điều hướng để quay lại, phải bấm Back trình duyệt. */}
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Nhà cung cấp</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Quản lý nhà cung cấp và bảng giá</p>
        </div>
        {canEditSuppliers && (
          <button
            onClick={moThem}
            className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
            style={{ background: 'var(--gold-500)', color: '#000' }}
          >
            + Thêm nhà cung cấp
          </button>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-xl text-sm flex items-center justify-between gap-4"
          style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>
          <span><LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{error}</span>
          <button onClick={() => { setError(null); loadSuppliers(); }} className="shrink-0 px-3 py-1.5 rounded-lg"
            style={{ border: '1px solid rgba(239,68,68,0.3)' }}>
            Thử lại
          </button>
        </div>
      )}

      {luuYGop && (
        <div className="p-3 rounded-xl text-sm flex items-center justify-between gap-4"
          style={{ background: 'var(--warning-bg)', border: '1px solid var(--border-default)', color: 'var(--warning)' }}>
          <span className="whitespace-pre-line"><LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{luuYGop}</span>
          <button onClick={() => setLuuYGop(null)} className="shrink-0 px-3 py-1.5 rounded-lg" style={{ border: '1px solid currentColor' }}>
            Đã hiểu
          </button>
        </div>
      )}

      {/* Điện thoại: đang mở một NCC thì ẩn bộ lọc + danh sách, chỉ còn thẻ chi tiết (nút «Danh sách» quay lại) */}
      <div className={`space-y-6 ${selected ? 'hidden lg:block' : ''}`}>
        {/* Search & Filter */}
        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3">
          <input
            type="text"
            placeholder="Tìm theo tên, người liên hệ, số điện thoại, mã số thuế..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 sm:min-w-[240px] px-4 py-2.5 rounded-xl text-sm outline-none"
            style={O_NHAP}
          />
          <div className="flex gap-3">
            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="flex-1 min-w-0 px-4 py-2.5 rounded-xl text-sm outline-none"
              style={O_NHAP}
            >
              <option value="all">Tất cả loại</option>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select
              value={hangFilter}
              onChange={e => setHangFilter(e.target.value)}
              aria-label="Lọc theo hạng"
              className="flex-1 min-w-0 px-4 py-2.5 rounded-xl text-sm outline-none"
              style={O_NHAP}
            >
              <option value="all">Tất cả hạng</option>
              {Object.entries(HANG_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
              <option value="chua_xep">Chưa xếp</option>
            </select>
          </div>
          <label className="flex items-center gap-2 py-1 text-sm cursor-pointer select-none" style={{ color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={hienNgung} onChange={e => setHienNgung(e.target.checked)}
              className="w-4 h-4" style={{ accentColor: 'var(--gold-500)' }} />
            Hiện NCC đã ngừng{soNgung > 0 ? ` (${soNgung})` : ''}
          </label>
        </div>

        {/* Price Compare Quick Search */}
        <div
          className="flex items-center gap-3 p-4 rounded-xl"
          style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}
        >
          <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>So sánh giá:</span>
          <input
            type="text"
            placeholder="Nhập tên vật tư (VD: Gỗ sồi, Sơn nội thất)..."
            value={compareMaterial}
            onChange={e => setCompareMaterial(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCompare()}
            className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
          />
          <button
            onClick={() => handleCompare()}
            disabled={comparing}
            className="px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
            style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)', border: '1px solid rgba(201,169,110,0.3)' }}
          >
            {comparing ? 'Đang so sánh...' : 'So sánh giá'}
          </button>
        </div>
      </div>

      {/* Main Content: List + Detail */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Supplier List — màn rộng: cuộn riêng trong cột để thẻ chi tiết bên phải luôn trong tầm mắt */}
        <div className={`lg:w-1/2 space-y-3 lg:max-h-[75vh] lg:overflow-y-auto lg:pr-1 ${selected ? 'hidden lg:block' : ''}`}>
          {loading ? (
            <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Đang tải...</div>
          ) : hienThi.length === 0 ? (
            <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Không có nhà cung cấp nào</div>
          ) : (
            <>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{hienThi.length} nhà cung cấp</p>
              {hienThi.map(s => (
                <div
                  key={s.id}
                  id={`ncc-${s.id}`}
                  onClick={() => handleSelectSupplier(s.id)}
                  className="p-4 rounded-xl cursor-pointer transition-all"
                  style={{
                    background: selectedId === s.id ? 'rgba(201,169,110,0.1)' : 'var(--surface-elevated)',
                    border: `1px solid ${selectedId === s.id ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                    opacity: s.is_active ? 1 : 0.6,
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{s.name}</span>
                        <span
                          className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                          style={{
                            background: `${CATEGORY_COLORS[s.category] || '#9CA3AF'}20`,
                            color: CATEGORY_COLORS[s.category] || '#9CA3AF',
                          }}
                        >
                          {CATEGORY_LABELS[s.category] || s.category}
                        </span>
                        <NhanHang hang={s.hang} />
                        {!s.is_active && <NhanNgung />}
                      </div>
                      {(s.contact_name || s.phone) && (
                        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                          {[s.contact_name, s.phone].filter(Boolean).join(' · ')}
                        </p>
                      )}
                    </div>
                    {/* Gọi / Zalo một chạm ngay trên dòng — không phải mở thẻ NCC rồi mới bấm số */}
                    <div className="flex items-center gap-1.5 shrink-0 mx-2" onClick={e => e.stopPropagation()}>
                      {s.phone && (
                        <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} aria-label={`Gọi ${s.name}`} title="Gọi"
                          className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', color: 'var(--gold-400)' }}>
                          <LineIcon name="phone" size={16} color="currentColor" />
                        </a>
                      )}
                      {(soZalo(s.zalo) || soZalo(s.phone)) && (
                        <a href={`https://zalo.me/${soZalo(s.zalo) || soZalo(s.phone)}`} target="_blank" rel="noopener noreferrer" aria-label={`Nhắn Zalo ${s.name}`} title="Zalo"
                          className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', color: 'var(--gold-400)' }}>
                          <LineIcon name="message" size={16} color="currentColor" />
                        </a>
                      )}
                    </div>
                    {s.quote_count != null && s.quote_count > 0 && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                        {s.quote_count} báo giá
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Detail Panel */}
        <div className="lg:w-1/2">
          {selected ? (
            <div className="space-y-4">
              <button onClick={veDanhSach} className="lg:hidden py-1 text-sm font-medium" style={{ color: 'var(--gold-400)' }}>
                <LineIcon name="arrowRight" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5 rotate-180" />Danh sách nhà cung cấp
              </button>
              {/* Supplier Info Card */}
              <div className="p-5 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
                <div className="flex items-center gap-2 flex-wrap mb-3">
                  <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{selected.name}</h2>
                  <NhanHang hang={selected.hang} />
                  {!selected.is_active && <NhanNgung />}
                </div>
                {(canEditSuppliers || laAdmin) && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {canEditSuppliers && (
                      <>
                        <button
                          onClick={() => moSua(selected)}
                          className="px-3 py-2 rounded-lg text-xs font-semibold"
                          style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}
                        >
                          <LineIcon name="edit" size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />Sửa
                        </button>
                        <button
                          onClick={() => { setQuoteForm(BAO_GIA_TRONG); setShowQuoteModal(true); }}
                          className="px-3 py-2 rounded-lg text-xs font-semibold"
                          style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}
                        >
                          + Thêm báo giá
                        </button>
                        {selected.is_active ? (
                          <button
                            onClick={() => luuNhanh(selected.id, { is_active: false }, `Đã ngừng dùng «${selected.name}»`)}
                            disabled={saving}
                            className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-50"
                            style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                          >
                            Ngừng dùng
                          </button>
                        ) : (
                          <button
                            onClick={() => luuNhanh(selected.id, { is_active: true }, `Đã dùng lại «${selected.name}»`)}
                            disabled={saving}
                            className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-50"
                            style={{ background: 'var(--success-bg)', color: 'var(--success)' }}
                          >
                            Dùng lại
                          </button>
                        )}
                      </>
                    )}
                    {laAdmin && (
                      <button
                        onClick={() => setGop({ nguon: selected, dichId: '', tim: '' })}
                        className="px-3 py-2 rounded-lg text-xs font-semibold"
                        style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}
                      >
                        Gộp vào NCC khác
                      </button>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {selected.contact_name && <div><span style={{ color: 'var(--text-muted)' }}>Liên hệ:</span> {selected.contact_name}</div>}
                  {selected.phone && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Điện thoại:</span>{' '}
                      <a href={`tel:${selected.phone.replace(/[^\d+]/g, '')}`} className="underline" style={{ color: 'var(--gold-400)' }}>{selected.phone}</a>
                      {!selected.zalo && soZalo(selected.phone) && (
                        <>{' · '}<a href={`https://zalo.me/${soZalo(selected.phone)}`} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: 'var(--gold-400)' }}>Zalo</a></>
                      )}
                    </div>
                  )}
                  {selected.zalo && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Zalo:</span>{' '}
                      {soZalo(selected.zalo) ? (
                        <a href={`https://zalo.me/${soZalo(selected.zalo)}`} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: 'var(--gold-400)' }}>{selected.zalo}</a>
                      ) : selected.zalo}
                    </div>
                  )}
                  {selected.email && <div><span style={{ color: 'var(--text-muted)' }}>Email:</span> {selected.email}</div>}
                  {selected.address && <div><span style={{ color: 'var(--text-muted)' }}>Địa chỉ:</span> {selected.address}</div>}
                  {selected.region && <div><span style={{ color: 'var(--text-muted)' }}>Khu vực:</span> {selected.region}</div>}
                  {selected.ten_cong_ty && <div className="col-span-2"><span style={{ color: 'var(--text-muted)' }}>Công ty:</span> {selected.ten_cong_ty}</div>}
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Mã số thuế:</span>{' '}
                    {selected.ma_so_thue ? (
                      <a href={`https://masothue.com/Search/?q=${encodeURIComponent(selected.ma_so_thue)}&type=auto`} target="_blank" rel="noopener noreferrer"
                        className="underline" style={{ color: 'var(--gold-400)' }}>{selected.ma_so_thue}</a>
                    ) : canEditSuppliers ? (
                      <button className="underline" style={{ color: 'var(--gold-400)' }} onClick={() => moSua(selected)}>Thêm</button>
                    ) : '—'}
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Chiết khấu:</span> {selected.chiet_khau_pct || 0}%
                  </div>
                  <div className="col-span-2 flex items-center gap-2">
                    <span style={{ color: 'var(--text-muted)' }}>Hạng:</span>
                    {canEditSuppliers ? (
                      <select
                        value={selected.hang || ''}
                        disabled={saving}
                        onChange={e => luuNhanh(selected.id, { hang: (e.target.value || null) as HangNcc | null })}
                        aria-label="Hạng nhà cung cấp"
                        className="px-2 py-1.5 rounded-lg text-xs outline-none"
                        style={O_NHAP}
                      >
                        <option value="">Chưa xếp</option>
                        {Object.entries(HANG_LABELS).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
                        ))}
                      </select>
                    ) : (
                      <span>{selected.hang ? HANG_LABELS[selected.hang] || selected.hang : 'Chưa xếp'}</span>
                    )}
                  </div>
                </div>
                {selected.notes && (
                  <p className="text-xs mt-3 p-2 rounded-lg" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                    {selected.notes}
                  </p>
                )}
              </div>

              {/* Price Quotes */}
              <div className="p-5 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
                <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
                  Bảng giá ({quotes.length})
                </h3>
                {quotesLoading ? (
                  <div className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>Đang tải...</div>
                ) : quotes.length === 0 ? (
                  <div className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>Chưa có báo giá</div>
                ) : (
                  <div className="space-y-2">
                    {quotes.map(q => (
                      <div key={q.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{q.material_name}</p>
                          <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                            {q.unit} · SL tối thiểu: {q.min_quantity || '-'} · Giao hàng: {q.lead_time_days || '-'} ngày
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0 ml-3">
                          <p className="text-sm font-bold" style={{ color: 'var(--gold-400)' }}>{fmt(q.unit_price)}đ</p>
                          {/* Trước đây hiện "HL đến {valid_until}" — cột đó không tồn tại nên
                              dòng này không bao giờ ra chữ. Bảng giá chỉ có ngày báo giá. */}
                          {q.quote_date && (
                            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              Báo giá {new Date(q.quote_date).toLocaleDateString('vi-VN')}
                            </p>
                          )}
                          <div className="flex gap-1.5 justify-end mt-1.5">
                            <button type="button" disabled={comparing} onClick={() => handleCompare(q.material_name)}
                              className="px-2.5 min-h-[32px] rounded-lg text-[11px] font-medium disabled:opacity-50" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                              So sánh
                            </button>
                            {(canEditSuppliers || laAdmin) && (
                              <button type="button"
                                onClick={() => {
                                  // Mở form báo giá điền sẵn mọi thứ của dòng này — chỉ còn sửa con số giá. Lưu = thêm một dòng báo giá mới (giữ lịch sử).
                                  setQuoteForm({ material_name: q.material_name, material_category: q.material_category || 'general', unit: q.unit, unit_price: q.unit_price, min_quantity: q.min_quantity ?? 1, lead_time_days: q.lead_time_days ?? 3, notes: '' });
                                  setShowQuoteModal(true);
                                }}
                                className="px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold" style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}>
                                Cập nhật giá
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="hidden lg:flex items-center justify-center h-64 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chọn nhà cung cấp để xem chi tiết</p>
            </div>
          )}
        </div>
      </div>

      {/* Price Comparison Modal */}
      {showCompare && compareData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowCompare(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-3xl max-h-[80vh] overflow-auto rounded-2xl p-6"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                So sánh giá: {compareData.material_name}
              </h2>
              <button onClick={() => setShowCompare(false)} className="text-sm" style={{ color: 'var(--text-muted)' }}>Đóng</button>
            </div>
            <PriceComparisonTable data={compareData} />
          </div>
        </div>
      )}

      {/* Add / Edit Supplier Modal */}
      {formNcc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !saving && setFormNcc(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl p-5 sm:p-6 space-y-4"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              {formNcc === 'moi' ? 'Thêm nhà cung cấp mới' : `Sửa nhà cung cấp — ${formNcc.name}`}
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Mã số thuế</label>
                <div className="flex gap-2">
                  <input inputMode="numeric" maxLength={20} value={form.ma_so_thue} placeholder="10 số — bấm Tra để tự điền"
                    onChange={e => setForm({ ...form, ma_so_thue: e.target.value })}
                    className="flex-1 min-w-0 px-3 py-2 rounded-lg text-base sm:text-sm outline-none"
                    style={O_NHAP} />
                  <button type="button" disabled={!form.ma_so_thue.trim() || traMst === 'dang'}
                    className="px-4 py-2 rounded-full text-sm font-semibold disabled:opacity-50"
                    style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}
                    onClick={async () => {
                      setTraMst('dang');
                      try {
                        const t = await api.traMaSoThue(form.ma_so_thue);
                        setForm(f => ({ ...f, ma_so_thue: t.ma_so_thue, ten_cong_ty: t.ten_cong_ty || '',
                          name: f.name || t.ten_ngan || t.ten_cong_ty || '', address: f.address || t.dia_chi || '' }));
                        setTraMst(t.trang_thai ? `Đã điền · ${t.trang_thai}` : 'Đã điền');
                      } catch (e) { setTraMst(e instanceof Error ? e.message : 'Không tra được'); }
                    }}>{traMst === 'dang' ? 'Đang tra…' : 'Tra'}</button>
                </div>
                {traMst && traMst !== 'dang' && <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{traMst}</p>}
              </div>
              {O_CHU.map(f => (
                <div key={f.key} className={f.rong ? 'col-span-2' : ''}>
                  <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>{f.label}</label>
                  <input
                    type={f.key === 'email' ? 'email' : 'text'}
                    inputMode={f.key === 'phone' ? 'tel' : undefined}
                    list={f.key === 'region' ? 'ncc-khu-vuc' : undefined}
                    maxLength={f.max}
                    placeholder={f.goiY}
                    value={form[f.key]}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={O_NHAP}
                  />
                </div>
              ))}
              {/* Gợi ý khu vực đã dùng ở NCC khác — để không sinh «HCM» lẫn «TP.HCM» */}
              <datalist id="ncc-khu-vuc">{khuVuc.map(k => <option key={k} value={k} />)}</datalist>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Loại</label>
                <select
                  value={form.category}
                  onChange={e => setForm({ ...form, category: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={O_NHAP}
                >
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                  {!(form.category in CATEGORY_LABELS) && <option value={form.category}>{form.category}</option>}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Hạng</label>
                <select
                  value={form.hang}
                  onChange={e => setForm({ ...form, hang: e.target.value as HangNcc | '' })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={O_NHAP}
                >
                  <option value="">Chưa xếp</option>
                  {Object.entries(HANG_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Chiết khấu cho JAMA (%)</label>
                <input type="number" min={0} max={100} step={0.5} inputMode="decimal"
                  value={form.chiet_khau_pct}
                  onChange={e => setForm({ ...form, chiet_khau_pct: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })}
                  className="w-full px-3 py-2 rounded-lg text-base sm:text-sm outline-none"
                  style={O_NHAP} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Ghi chú</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
                  style={O_NHAP}
                />
              </div>
            </div>
            {formLoi && (
              <div className="p-3 rounded-xl text-sm space-y-2" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}>
                <p><LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{formLoi.message}</p>
                {formLoi.trung && (
                  <button onClick={() => formLoi.trung && moNccDangCo(formLoi.trung)} className="px-3 py-2 rounded-lg text-xs font-semibold"
                    style={{ border: '1px solid currentColor' }}>
                    {formLoi.trung.dangDung ? `Mở «${formLoi.trung.ten}»` : `Mở «${formLoi.trung.ten}» để dùng lại`}
                  </button>
                )}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setFormNcc(null)} disabled={saving} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Hủy</button>
              <button
                onClick={handleSaveSupplier}
                disabled={!form.name.trim() || saving}
                className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--gold-500)', color: '#000' }}
              >
                {saving ? 'Đang lưu...' : formNcc === 'moi' ? 'Thêm' : 'Lưu'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Merge Supplier Modal — chỉ Ban giám đốc */}
      {gop && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !saving && setGop(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl p-5 sm:p-6 space-y-4"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Gộp «{gop.nguon.name}» vào nhà cung cấp khác
            </h2>
            <p className="text-sm" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Chọn nhà cung cấp <b>giữ lại</b>. Mọi phiếu vật tư, mẫu vật tư, báo giá và giá nhập của «{gop.nguon.name}» chuyển
              sang nhà cung cấp đó, rồi «{gop.nguon.name}» bị xoá. Ô còn trống của nhà cung cấp giữ lại được điền bằng
              thông tin của «{gop.nguon.name}».
            </p>
            <p className="text-sm font-semibold" style={{ color: 'var(--danger)' }}>
              <LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Không hoàn tác được.
            </p>
            <input
              type="text"
              placeholder="Tìm nhà cung cấp giữ lại..."
              value={gop.tim}
              onChange={e => setGop({ ...gop, tim: e.target.value })}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={O_NHAP}
            />
            <div className="max-h-64 overflow-y-auto space-y-1.5">
              {ungVienGop.length === 0 ? (
                <p className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>Không có nhà cung cấp nào khớp</p>
              ) : ungVienGop.map(s => (
                <button
                  key={s.id}
                  onClick={() => setGop({ ...gop, dichId: s.id, loi: undefined })}
                  aria-pressed={gop.dichId === s.id}
                  className="w-full text-left p-3 rounded-lg"
                  style={{
                    background: gop.dichId === s.id ? 'rgba(201,169,110,0.1)' : 'var(--surface-2)',
                    border: `1px solid ${gop.dichId === s.id ? 'rgba(201,169,110,0.4)' : 'var(--border-subtle)'}`,
                  }}
                >
                  <span className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{s.name}</span>
                    <NhanHang hang={s.hang} />
                    {!s.is_active && <NhanNgung />}
                  </span>
                  <span className="block text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    {[s.ma_so_thue && `MST ${s.ma_so_thue}`, s.contact_name, s.phone].filter(Boolean).join(' · ') || 'Chưa có thông tin liên hệ'}
                  </span>
                </button>
              ))}
            </div>
            {dichGop && !dichGop.is_active && (
              <p className="text-xs" style={{ color: 'var(--warning)' }}>
                «{dichGop.name}» đang ngừng dùng và vẫn ngừng dùng sau khi gộp — bấm «Dùng lại» nếu muốn dùng tiếp.
              </p>
            )}
            {gop.loi && (
              <p className="p-3 rounded-xl text-sm" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}>
                <LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{gop.loi}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setGop(null)} disabled={saving} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Hủy</button>
              <button
                onClick={handleGop}
                disabled={!dichGop || saving}
                className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--danger)', color: '#fff' }}
              >
                {saving ? 'Đang gộp...' : dichGop ? `Gộp vào «${dichGop.name}»` : 'Chọn NCC giữ lại'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Quote Modal */}
      {showQuoteModal && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowQuoteModal(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg rounded-2xl p-6 space-y-4"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Thêm báo giá — {selected.name}
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Tên vật tư *</label>
                <input
                  type="text"
                  value={quoteForm.material_name}
                  onChange={e => setQuoteForm({ ...quoteForm, material_name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Đơn vị</label>
                <input
                  type="text"
                  value={quoteForm.unit}
                  onChange={e => setQuoteForm({ ...quoteForm, unit: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Đơn giá (VND) *</label>
                <input
                  type="number"
                  value={quoteForm.unit_price}
                  onChange={e => setQuoteForm({ ...quoteForm, unit_price: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>SL tối thiểu</label>
                <input
                  type="number"
                  value={quoteForm.min_quantity}
                  onChange={e => setQuoteForm({ ...quoteForm, min_quantity: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Giao hàng (ngày)</label>
                <input
                  type="number"
                  value={quoteForm.lead_time_days}
                  onChange={e => setQuoteForm({ ...quoteForm, lead_time_days: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Ghi chú</label>
                <input
                  type="text"
                  value={quoteForm.notes}
                  onChange={e => setQuoteForm({ ...quoteForm, notes: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowQuoteModal(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Hủy</button>
              <button
                onClick={handleAddQuote}
                disabled={!quoteForm.material_name.trim() || quoteForm.unit_price <= 0 || saving}
                className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--gold-500)', color: '#000' }}
              >
                {saving ? 'Đang lưu...' : 'Thêm báo giá'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </Sidebar>
  );
}
