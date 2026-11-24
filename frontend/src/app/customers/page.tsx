'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import { useToast } from '@/components/ui/Toast';
import { api, Customer, fetchAllPages } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import GuiLinkKhach from '@/components/projects/GuiLinkKhach';
import { compressImage } from '@/lib/nhan-su';

const vnd = (n?: number) => (n ? `${Math.round(n).toLocaleString('vi-VN')}đ` : '—');
function BadgeSinhNhat({ n }: { n?: number | null }) {
  if (n == null || n > 7) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-medium" style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-500)' }}>
      <LineIcon name="gift" size={12} color="currentColor" />{n === 0 ? 'Sinh nhật hôm nay' : `Sinh nhật còn ${n} ngày`}
    </span>
  );
}

const TYPE_LABELS: Record<string, string> = {
  individual: 'Cá nhân',
  company: 'Doanh nghiệp',
};

// Trạng thái doanh thu — khóa do backend trả (services/khach_hang.py).
const TRANG_THAI_DT: Record<string, { nhan: string; mau: string; nen: string; giai: string }> = {
  da_chot: { nhan: 'Đã chốt', mau: '#34d399', nen: 'rgba(16,185,129,0.12)', giai: 'Deal đã thắng — giá trị các dự án của khách (không tính dự án hủy).' },
  dang_chot: { nhan: 'Đang chốt', mau: 'var(--gold-500)', nen: 'rgba(201,169,110,0.15)', giai: 'Đã gửi báo giá / đang đàm phán — số dự kiến, chưa phải doanh thu.' },
  tiem_nang: { nhan: 'Tiềm năng', mau: '#60a5fa', nen: 'rgba(59,130,246,0.12)', giai: 'Còn đang tư vấn / khảo sát — số ước lượng của sale.' },
  da_mat: { nhan: 'Đã mất', mau: '#f87171', nen: 'rgba(239,68,68,0.12)', giai: 'Lead đã chuyển sang «Mất».' },
  da_huy: { nhan: 'Đã hủy', mau: '#f87171', nen: 'rgba(239,68,68,0.12)', giai: 'Mọi dự án của khách đều đã hủy.' },
};

function BadgeDoanhThu({ c }: { c: Customer }) {
  const t = c.trang_thai_doanh_thu ? TRANG_THAI_DT[c.trang_thai_doanh_thu] : null;
  if (!t) return null;
  return (
    <span title={t.giai} className="inline-block px-2 py-0.5 rounded-lg text-[11px] font-medium whitespace-nowrap" style={{ background: t.nen, color: t.mau }}>
      {t.nhan}
    </span>
  );
}

/** Số tiền hiện cạnh nhãn trạng thái: đã chốt thì lấy doanh thu, chưa chốt thì lấy số dự kiến. */
const tienDoanhThu = (c: Customer) => c.doanh_thu || c.doanh_thu_du_kien || 0;

const TRANG_THAI_DU_AN: Record<string, { nhan: string; mau: string; nen: string }> = {
  active: { nhan: 'Đang chạy', mau: '#34d399', nen: 'rgba(16,185,129,0.1)' },
  completed: { nhan: 'Hoàn thành', mau: '#60a5fa', nen: 'rgba(59,130,246,0.1)' },
  paused: { nhan: 'Tạm dừng', mau: 'var(--gold-500)', nen: 'rgba(201,169,110,0.15)' },
  cancelled: { nhan: 'Đã hủy', mau: '#f87171', nen: 'rgba(239,68,68,0.1)' },
};

/** SĐT bấm là gọi. Số đang bị che (091***) thì chỉ hiện chữ — gọi số che là gọi sai. */
function SoDienThoai({ so }: { so?: string | null }) {
  if (!so) return <span className="text-[var(--text-muted)]">Chưa có</span>;
  if (so.includes('*')) return <span>{so}</span>;
  return (
    <span className="inline-flex items-center gap-1">
      <a
        href={`tel:${so.replace(/[^\d+]/g, '')}`}
        onClick={e => e.stopPropagation()}
        title="Bấm để gọi"
        className="inline-flex items-center gap-1.5 hover:text-[var(--gold-500)] hover:underline underline-offset-4 transition-colors"
      >
        <LineIcon name="phone" size={13} color="currentColor" />{so}
      </a>
      <a
        href={`https://zalo.me/${so.replace(/\D/g, '')}`}
        target="_blank"
        rel="noopener noreferrer"
        onClick={e => e.stopPropagation()}
        aria-label={`Nhắn Zalo ${so}`}
        title="Nhắn Zalo"
        className="w-9 h-9 -my-2 rounded-full inline-flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--gold-500)] hover:bg-white/10 transition-colors"
      >
        <LineIcon name="message" size={14} color="currentColor" />
      </a>
    </span>
  );
}


type CustomerForm = {
  name: string;
  phone: string;
  email: string;
  address: string;
  type: string;
  company_name: string;
  tax_code: string;
  notes: string;
  birthday: string;
  national_id: string;
};

const EMPTY_FORM: CustomerForm = {
  name: '',
  phone: '',
  email: '',
  address: '',
  type: 'individual',
  company_name: '',
  tax_code: '',
  notes: '',
  birthday: '',
  national_id: '',
};

function toForm(customer?: Customer | null): CustomerForm {
  if (!customer) return EMPTY_FORM;
  return {
    name: customer.name || '',
    phone: customer.phone || '',
    email: customer.email || '',
    address: customer.address || '',
    type: customer.type || 'individual',
    company_name: customer.company_name || '',
    tax_code: customer.tax_code || '',
    notes: customer.notes || '',
    birthday: customer.birthday || '',
    national_id: customer.national_id || '',
  };
}

function cleanPayload(form: CustomerForm) {
  const out: Record<string, string | undefined> = Object.fromEntries(
    Object.entries(form).map(([key, value]) => [key, value.trim() || undefined])
  );
  // Số CCCD đang hiện dạng che (***) thì không gửi để khỏi ghi đè số thật
  if (out.national_id?.includes('*')) delete out.national_id;
  return out;
}

function AccessDenied() {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <LineIcon name="lock" size={48} className="block mx-auto mb-4" />
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Bạn không có quyền truy cập trang này.
          </p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2.5 rounded-xl text-sm font-medium transition-all"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: '#fff' }}
          >
            Quay về Tổng quan
          </button>
        </div>
      </div>
    </Sidebar>
  );
}

export default function CustomersPage() {
  const { user, loading, effectivePermissions } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  // Gõ xong 300ms mới gọi máy chủ — trước đây mỗi phím một lượt tải cả danh sách.
  const [searchTre, setSearchTre] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setSearchTre(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);
  const [typeFilter, setTypeFilter] = useState('all');
  const [selected, setSelected] = useState<Customer | null>(null);
  const [customerDetail, setCustomerDetail] = useState<Customer | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [docCccd, setDocCccd] = useState(false);

  const handleCccd = async (file?: File) => {
    if (!file) return;
    setDocCccd(true);
    try {
      const anh = await compressImage(file);
      if (!anh) throw new Error('Không mở được ảnh');
      const d = await api.docCccd(anh.base64);
      setForm(f => ({
        ...f,
        name: d.name || f.name,
        national_id: d.national_id || f.national_id,
        birthday: d.birthday || f.birthday,
        address: d.address || f.address,
      }));
      toast('Đã điền thông tin từ CCCD — kiểm tra lại trước khi lưu', 'success');
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không đọc được CCCD', 'error');
    } finally {
      setDocCccd(false);
    }
  };

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
  }, [user, loading, router]);

  // Fetch customer detail with projects when selected
  useEffect(() => {
    void Promise.resolve().then(() => {
      if (!selected) { setCustomerDetail(null); return; }
      setLoadingDetail(true);
      api.getCustomer(selected.id)
        .then(d => setCustomerDetail(d as Customer))
        .catch(() => setCustomerDetail(selected))
        .finally(() => setLoadingDetail(false));
    });
  }, [selected]);

  const load = useCallback(async () => {
    setLoadingData(true);
    try {
      const params: Record<string, string> = {};
      if (typeFilter !== 'all') params.type = typeFilter;
      if (searchTre) params.search = searchTre;
      // Lấy đủ mọi trang — lọc/sắp xếp chạy phía trình duyệt (xem fetchAllPages).
      const data = await fetchAllPages(p => api.getCustomers(p), params);
      setCustomers(data);
      setSelected(prev => (prev ? data.find(c => c.id === prev.id) || prev : prev));
    } catch (e) {
      setError('Không thể tải dữ liệu khách hàng. Vui lòng thử lại.');
      toast(`Không tải được khách hàng: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      setLoadingData(false);
    }
  }, [searchTre, typeFilter, toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  // Đóng modal "Thêm/Sửa khách hàng" bằng phím Escape (không đóng khi đang lưu)
  useEffect(() => {
    if (!formOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) setFormOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [formOpen, saving]);

  if (loading || !user) return null;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <LineIcon name="alert" size={40} className="block mx-auto mb-4" />
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); load(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }

  const perms = effectivePermissions;
  if (!perms?.canViewProjects) return <AccessDenied />;

  // 22/09: theo ô «Sửa Khách hàng» trong ma trận thay vì danh sách vai trò cứng.
  // Giữ được mục đích cũ (không hiện nút cho người sẽ ăn 403) nhưng nay admin
  // cấp/thu được ở trang Phân quyền — kể cả cấp riêng cho đúng một người.
  const canEditCustomers = perms.canEditCustomers;

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const openEdit = (customer: Customer) => {
    setEditing(customer);
    setForm(toForm(customer));
    setFormOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) {
      toast('Tên khách hàng là bắt buộc', 'error');
      return;
    }
    if (!editing && !form.phone.trim()) {
      toast('SĐT là bắt buộc khi tạo khách hàng', 'error');
      return;
    }

    setSaving(true);
    try {
      const payload = cleanPayload(form);
      const saved = editing
        ? await api.updateCustomer(editing.id, payload)
        : await api.createCustomer(payload);
      toast(editing ? 'Đã cập nhật khách hàng' : 'Đã tạo khách hàng', 'success');
      setFormOpen(false);
      setEditing(null);
      await load();
      if (saved && saved.id) setSelected(saved);
    } catch (e) {
      toast(`Lỗi lưu khách hàng: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Khách hàng</h1>
            <p className="text-sm text-[var(--text-tertiary)] mt-1">
              {customers.length} hồ sơ khách hàng · quản lý liên hệ, pháp nhân và ghi chú nội bộ
            </p>
          </div>
          {canEditCustomers && (
            <button
              onClick={openCreate}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-[var(--gold-500)] to-[#B8935A] text-white text-sm font-semibold hover:from-[#D4B97E] hover:to-[var(--gold-500)] transition-all active:scale-95 shadow-lg shadow-[var(--gold-500)]/10"
            >
              + Thêm khách hàng
            </button>
          )}
        </div>

        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1 max-w-md">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input
              type="text"
              placeholder="Tìm theo tên, SĐT, email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm outline-none focus:border-[var(--gold-500)]"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
            />
          </div>
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="px-3 py-2.5 rounded-xl text-sm outline-none"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
          >
            <option value="all">Tất cả loại KH</option>
            <option value="individual">Cá nhân</option>
            <option value="company">Doanh nghiệp</option>
          </select>
        </div>

        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          {loadingData ? (
            <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
          ) : customers.length === 0 ? (
            <div className="text-center py-12">
              <LineIcon name="users" size={40} className="block mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Chưa có khách hàng</h3>
              <p className="text-sm text-[var(--text-muted)] mb-4">Khách hàng sẽ xuất hiện khi lead ký hợp đồng</p>
              {canEditCustomers && (
                <button onClick={openCreate} className="px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-[var(--gold-500)] to-[#B8935A] text-white hover:from-[#D4B97E] hover:to-[var(--gold-500)] transition-all">
                  + Thêm khách hàng
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Mobile card view */}
              <div className="md:hidden p-3 space-y-3">
                {customers.map(c => (
                  <div key={c.id} className="p-4 rounded-xl cursor-pointer transition-all" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }} onClick={() => setSelected(c)}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}>
                          {c.name?.charAt(0) || '?'}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-[var(--text-primary)]">{c.name}</p>
                          {c.company_name && <p className="text-[10px] text-[var(--text-muted)]">{c.company_name}</p>}
                          <BadgeSinhNhat n={c.sinh_nhat_con_ngay} />
                        </div>
                      </div>
                      <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: c.type === 'company' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: c.type === 'company' ? '#60a5fa' : '#34d399' }}>
                        {TYPE_LABELS[c.type] || c.type}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                      {c.phone && <SoDienThoai so={c.phone} />}
                      {c.email && <span className="truncate">{c.email}</span>}
                      {!!tienDoanhThu(c) && <span className="font-medium text-[var(--text-primary)]">{vnd(tienDoanhThu(c))} · {c.so_hop_dong || 0} HĐ</span>}
                      <BadgeDoanhThu c={c} />
                      {'project_count' in c && (c as Customer).project_count ? (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: 'rgba(201,169,110,0.1)', color: '#C9A96E' }}>
                          {(c as Customer).project_count} dự án
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-xs text-[var(--text-muted)]">
                      <LineIcon name="user" size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />
                      Chăm sóc: <span className="text-[var(--text-secondary)]">{c.cham_soc_ten || 'Chưa có người chăm sóc'}</span>
                    </p>
                    {canEditCustomers && (
                      <div className="flex justify-end mt-2 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                        <button onClick={e => { e.stopPropagation(); openEdit(c); }} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] hover:bg-[var(--gold-500)]/15 hover:text-[var(--gold-500)] transition-all">
                          Sửa
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {/* Desktop table view */}
              <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Tên</th>
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Loại</th>
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">SĐT</th>
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Người chăm sóc</th>
                    <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Doanh thu</th>
                    <th className="text-center px-5 py-3 text-[var(--text-tertiary)] font-medium">Số HĐ</th>
                    <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map(c => (
                    <tr key={c.id} className="cursor-pointer transition-colors" style={{ borderBottom: '1px solid var(--border-subtle)' }} onClick={() => setSelected(c)}>
                      <td className="px-5 py-3.5 font-medium text-[var(--text-primary)]">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}>
                            {c.name?.charAt(0) || '?'}
                          </div>
                          <div>
                            <p>{c.name}</p>
                            {c.company_name && <p className="text-xs text-[var(--text-muted)]">{c.company_name}</p>}
                            <BadgeSinhNhat n={c.sinh_nhat_con_ngay} />
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: c.type === 'company' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: c.type === 'company' ? '#60a5fa' : '#34d399' }}>
                          {TYPE_LABELS[c.type] || c.type}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-[var(--text-secondary)] whitespace-nowrap"><SoDienThoai so={c.phone} /></td>
                      <td className="px-5 py-3.5 text-[var(--text-secondary)]">{c.cham_soc_ten || <span className="text-[var(--text-muted)]">Chưa có</span>}</td>
                      <td className="px-5 py-3.5 text-right font-medium text-[var(--text-primary)] whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">{vnd(tienDoanhThu(c))}<BadgeDoanhThu c={c} /></div>
                      </td>
                      <td className="px-5 py-3.5 text-center text-[var(--text-secondary)]">{c.so_hop_dong || 0}</td>
                      <td className="px-5 py-3.5 text-right">
                        {canEditCustomers && (
                          <button onClick={e => { e.stopPropagation(); openEdit(c); }} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] hover:bg-[var(--gold-500)]/15 hover:text-[var(--gold-500)] transition-all">
                            Sửa
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </>
          )}
        </div>

        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" onClick={() => setSelected(null)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative w-full max-w-lg max-h-[86vh] overflow-y-auto rounded-2xl p-6" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <button onClick={() => setSelected(null)} aria-label="Đóng" className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/5">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
              <div className="flex items-center gap-4 mb-5 pr-8">
                <div className="w-14 h-14 shrink-0 rounded-2xl flex items-center justify-center text-lg font-bold" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}>
                  {selected.name?.charAt(0) || '?'}
                </div>
                <div className="min-w-0">
                  <h2 className="text-xl font-bold text-[var(--text-primary)] break-words">{selected.name}</h2>
                  <p className="text-sm text-[var(--text-muted)]">{TYPE_LABELS[selected.type] || selected.type}{selected.company_name ? ` — ${selected.company_name}` : ''}</p>
                  <BadgeSinhNhat n={selected.sinh_nhat_con_ngay} />
                </div>
              </div>

              {/* Khách của ai — hiện trước tiên để trưởng phòng nhìn là biết */}
              <div className="flex items-center gap-3 p-3 rounded-xl mb-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                <LineIcon name="user" size={18} color="var(--gold-500)" />
                <div className="min-w-0 text-sm">
                  <p className="text-xs text-[var(--text-muted)]">Người chăm sóc</p>
                  <p className="font-medium text-[var(--text-primary)] truncate">
                    {selected.cham_soc_ten || 'Chưa có người chăm sóc'}
                    {selected.cham_soc_id && selected.cham_soc_id === user.id && (
                      <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-500)' }}>Bạn</span>
                    )}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                  <p className="text-xs text-[var(--text-muted)] mb-1">
                    {selected.doanh_thu || !selected.doanh_thu_du_kien ? 'Doanh thu mang lại' : 'Doanh thu dự kiến'}
                  </p>
                  <p className="text-base font-bold text-[var(--text-primary)] mb-1">{vnd(tienDoanhThu(selected))}</p>
                  {selected.trang_thai_doanh_thu
                    ? <BadgeDoanhThu c={selected} />
                    : <span className="text-[11px] text-[var(--text-muted)]">Chưa có lead hay dự án</span>}
                </div>
                <div className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                  <p className="text-xs text-[var(--text-muted)] mb-1">Số hợp đồng</p>
                  <p className="text-base font-bold text-[var(--text-primary)] mb-1">{selected.so_hop_dong || 0}</p>
                  <span className="text-[11px] text-[var(--text-muted)]">{selected.so_du_an || 0} dự án</span>
                </div>
              </div>
              {selected.trang_thai_doanh_thu && (
                <p className="text-xs text-[var(--text-muted)] -mt-2 mb-4">{TRANG_THAI_DT[selected.trang_thai_doanh_thu]?.giai}</p>
              )}

              {/* Thông tin khách: các dòng chính LUÔN hiện, thiếu thì ghi «Chưa có» để biết còn phải hỏi khách */}
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Thông tin khách hàng</h3>
              <div className="text-sm">
                {([
                  ['Họ tên', selected.name, true],
                  ['SĐT', <SoDienThoai key="sdt" so={selected.phone} />, true],
                  ['Địa chỉ', selected.address ? <a key="dc" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(selected.address)}`} target="_blank" rel="noopener noreferrer" title="Mở chỉ đường" className="hover:text-[var(--gold-500)] hover:underline underline-offset-4"><LineIcon name="pin" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />{selected.address}</a> : '', true],
                  ['Email', selected.email ? <a key="mail" href={`mailto:${selected.email}`} className="hover:text-[var(--gold-500)] hover:underline underline-offset-4 break-all">{selected.email}</a> : '', true],
                  ['Sinh nhật', selected.birthday ? selected.birthday.split('-').reverse().join('/') : '', true],
                  ['Số CCCD', selected.national_id, false],
                  ['Tên công ty', selected.company_name, selected.type === 'company'],
                  ['MST', selected.tax_code, selected.type === 'company'],
                  ['Ghi chú', selected.notes, false],
                ] as [string, React.ReactNode, boolean][]).map(([label, value, luonHien]) => (value || luonHien) && (
                  <div key={label} className="flex justify-between gap-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <span className="text-[var(--text-muted)] shrink-0">{label}</span>
                    <span className="text-[var(--text-primary)] text-right max-w-[68%] break-words whitespace-pre-line">
                      {value || <span className="text-[var(--text-muted)]">Chưa có</span>}
                    </span>
                  </div>
                ))}
              </div>
              {/* Projects section */}
              <div className="mt-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-2">
                  <span><LineIcon name="clipboard" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />Dự án</span>
                  {customerDetail?.project_count != null && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>
                      {customerDetail.project_count}
                    </span>
                  )}
                </h3>
                <div className="mb-4">
                  <GuiLinkKhach
                    key={selected.id}
                    layLink={() => api.getPortalLink(selected.id)}
                    phone={selected.phone}
                    nhan="Gửi link theo dõi qua Zalo"
                    choTaoLai
                    soanTin={link => `Dạ em gửi anh/chị ${selected.name} link theo dõi tiến độ công trình JAMA HOME: ${link}`}
                  />
                </div>
                {loadingDetail ? (
                  <p className="text-xs text-[var(--text-muted)]">Đang tải...</p>
                ) : customerDetail?.projects && customerDetail.projects.length > 0 ? (
                  <div className="space-y-2">
                    {customerDetail.projects.map(p => (
                      <Link key={p.id} href={`/projects?id=${p.id}`} title="Mở chi tiết dự án" className="group block p-3 rounded-xl text-xs transition-colors hover:border-[var(--gold-500)]" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-medium text-[var(--text-primary)] group-hover:text-[var(--gold-500)] transition-colors">{p.code} — {p.name}</span>
                          <span className="shrink-0 flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 rounded text-[10px]" style={{
                              background: (TRANG_THAI_DU_AN[p.status] || TRANG_THAI_DU_AN.cancelled).nen,
                              color: (TRANG_THAI_DU_AN[p.status] || TRANG_THAI_DU_AN.cancelled).mau,
                            }}>{TRANG_THAI_DU_AN[p.status]?.nhan || p.status}</span>
                            <LineIcon name="link" size={12} color="var(--text-muted)" />
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[var(--text-muted)]">
                          <span>{p.total_value ? `${(p.total_value / 1_000_000).toFixed(0)}tr` : '—'}</span>
                          <span>Tiến độ: {p.progress}%</span>
                        </div>
                        <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-3)' }}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${p.progress}%`, background: 'linear-gradient(90deg, var(--gold-500), var(--gold-700))' }} />
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">Chưa có dự án</p>
                )}
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button onClick={() => setSelected(null)} className="px-3 py-2 rounded-xl text-sm bg-white/5 text-[var(--text-secondary)] hover:bg-white/10 transition-all">Đóng</button>
                {canEditCustomers && (
                  <button onClick={() => openEdit(selected)} className="px-3 py-2 rounded-xl text-sm bg-[var(--gold-500)]/20 text-[var(--gold-500)] hover:bg-[var(--gold-500)]/30 transition-all">Sửa hồ sơ</button>
                )}
              </div>
            </div>
          </div>
        )}

        {formOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" onClick={() => !saving && setFormOpen(false)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <form onSubmit={handleSubmit} className="relative w-full max-w-2xl max-h-[78vh] overflow-y-auto rounded-2xl p-6 space-y-4" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h2 className="text-xl font-bold text-[var(--text-primary)]">{editing ? 'Sửa khách hàng' : 'Thêm khách hàng'}</h2>
                  <p className="text-xs text-[var(--text-muted)] mt-1">Dữ liệu khách hàng phục vụ ERP, hợp đồng và dự án.</p>
                </div>
                <button type="button" onClick={() => !saving && setFormOpen(false)} className="p-2 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
              </div>

              <label className="flex items-center gap-3 p-3 rounded-xl cursor-pointer border border-dashed border-white/15 hover:border-[var(--gold-500)] transition-all">
                <LineIcon name="camera" size={22} />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm text-[var(--text-primary)]">{docCccd ? 'Đang đọc CCCD…' : 'Tải ảnh CCCD — tự điền họ tên, ngày sinh, số, địa chỉ'}</span>
                  <span className="block text-xs text-[var(--text-muted)]">Chụp mặt trước, rõ chữ. Ảnh chỉ dùng để đọc, không lưu lại.</span>
                </span>
                <input type="file" accept="image/*" className="hidden" disabled={docCccd} onChange={e => { handleCccd(e.target.files?.[0]); e.target.value = ''; }} />
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Ngày sinh (nhắc sale tặng quà)</span>
                  <input type="date" value={form.birthday} onChange={e => setForm({ ...form, birthday: e.target.value })} className="w-full px-3 py-2 rounded-xl text-base sm:text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)]" />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Số CCCD</span>
                  <input inputMode="numeric" value={form.national_id} onChange={e => setForm({ ...form, national_id: e.target.value })} className="w-full px-3 py-2 rounded-xl text-base sm:text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)]" />
                </label>
                {[
                  ['name', 'Tên khách hàng *'],
                  ['phone', `SĐT ${editing ? '' : '*'}`],
                  ['email', 'Email'],
                  ['company_name', 'Tên công ty'],
                  ['tax_code', 'Mã số thuế'],
                ].map(([key, label]) => (
                  <label key={key} className="space-y-1">
                    <span className="text-xs text-[var(--text-muted)]">{label}</span>
                    <input type={key === 'email' ? 'email' : 'text'} inputMode={key === 'phone' ? 'tel' : undefined} value={form[key as keyof CustomerForm]} onChange={e => setForm({ ...form, [key]: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)]" />
                  </label>
                ))}
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Loại khách hàng</span>
                  <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)]">
                    <option value="individual">Cá nhân</option>
                    <option value="company">Doanh nghiệp</option>
                  </select>
                </label>
              </div>
              <label className="block space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Địa chỉ</span>
                <input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)]" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Ghi chú nội bộ</span>
                <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={3} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[var(--gold-500)] resize-none" />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" disabled={saving} onClick={() => setFormOpen(false)} className="px-4 py-2 rounded-xl text-sm bg-white/5 text-[var(--text-secondary)] hover:bg-white/10 disabled:opacity-40 transition-all">Hủy</button>
                <button type="submit" disabled={saving} className="px-4 py-2 rounded-xl text-sm font-semibold bg-gradient-to-r from-[var(--gold-500)] to-[#B8935A] text-white disabled:opacity-50 transition-all">
                  {saving ? 'Đang lưu...' : editing ? 'Lưu thay đổi' : 'Tạo khách hàng'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
