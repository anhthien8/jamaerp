'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { useToast } from '@/components/ui/Toast';
import { api, Customer, extractItems } from '@/lib/api';
import { getPermissions, UserRole } from '@/lib/roles';

const TYPE_LABELS: Record<string, string> = {
  individual: 'Cá nhân',
  company: 'Doanh nghiệp',
};

type CustomerForm = {
  name: string;
  phone: string;
  email: string;
  address: string;
  type: string;
  company_name: string;
  tax_code: string;
  notes: string;
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
  };
}

function cleanPayload(form: CustomerForm) {
  return Object.fromEntries(
    Object.entries(form).map(([key, value]) => [key, value.trim() || undefined])
  );
}

function AccessDenied() {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <span className="text-5xl block mb-4">🔒</span>
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
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selected, setSelected] = useState<Customer | null>(null);
  const [customerDetail, setCustomerDetail] = useState<Customer | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // Fetch customer detail with projects when selected
  useEffect(() => {
    if (!selected) { setCustomerDetail(null); return; }
    setLoadingDetail(true);
    api.getCustomer(selected.id)
      .then(d => setCustomerDetail(d as Customer))
      .catch(() => setCustomerDetail(selected))
      .finally(() => setLoadingDetail(false));
  }, [selected]);

  const load = useCallback(async () => {
    setLoadingData(true);
    try {
      const params: Record<string, string> = {};
      if (typeFilter !== 'all') params.type = typeFilter;
      if (search.trim()) params.search = search.trim();
      const result = await api.getCustomers(params);
      const data = extractItems(result);
      setCustomers(data);
      setSelected(prev => (prev ? data.find(c => c.id === prev.id) || prev : prev));
    } catch (e) {
      setError('Không thể tải dữ liệu khách hàng. Vui lòng thử lại.');
      toast(`Không tải được khách hàng: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      setLoadingData(false);
    }
  }, [search, typeFilter, toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  if (loading || !user) return null;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <span className="text-4xl block mb-4">⚠️</span>
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); load(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }

  const perms = getPermissions(user.role as UserRole);
  if (!perms?.canViewProjects) return <AccessDenied />;

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
          <button
            onClick={openCreate}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white text-sm font-semibold hover:from-[#D4B97E] hover:to-[#C9A96E] transition-all active:scale-95 shadow-lg shadow-[#C9A96E]/10"
          >
            + Thêm khách hàng
          </button>
        </div>

        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1 max-w-md">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input
              type="text"
              placeholder="Tìm theo tên, SĐT, email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm outline-none focus:border-[#C9A96E]"
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
              <span className="text-4xl block mb-3">👥</span>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Chưa có khách hàng</h3>
              <p className="text-sm text-[var(--text-muted)] mb-4">Khách hàng sẽ xuất hiện khi lead ký hợp đồng</p>
              <button onClick={openCreate} className="px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white hover:from-[#D4B97E] hover:to-[#C9A96E] transition-all">
                + Thêm khách hàng
              </button>
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
                        </div>
                      </div>
                      <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: c.type === 'company' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: c.type === 'company' ? '#60a5fa' : '#34d399' }}>
                        {TYPE_LABELS[c.type] || c.type}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                      {c.phone && <span>{c.phone}</span>}
                      {c.email && <span className="truncate">{c.email}</span>}
                      {'project_count' in c && (c as Customer).project_count ? (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: 'rgba(201,169,110,0.1)', color: '#C9A96E' }}>
                          {(c as Customer).project_count} dự án
                        </span>
                      ) : null}
                    </div>
                    <div className="flex justify-end mt-2 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <button onClick={e => { e.stopPropagation(); openEdit(c); }} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] hover:bg-[#C9A96E]/15 hover:text-[#C9A96E] transition-all">
                        Sửa
                      </button>
                    </div>
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
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Email</th>
                    <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Địa chỉ</th>
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
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: c.type === 'company' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: c.type === 'company' ? '#60a5fa' : '#34d399' }}>
                          {TYPE_LABELS[c.type] || c.type}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-[var(--text-secondary)]">{c.phone || '—'}</td>
                      <td className="px-5 py-3.5 text-[var(--text-secondary)]">{c.email || '—'}</td>
                      <td className="px-5 py-3.5 text-[var(--text-secondary)] max-w-[220px] truncate">{c.address || '—'}</td>
                      <td className="px-5 py-3.5 text-right">
                        <button onClick={e => { e.stopPropagation(); openEdit(c); }} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] hover:bg-[#C9A96E]/15 hover:text-[#C9A96E] transition-all">
                          Sửa
                        </button>
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
            <div className="relative w-full max-w-lg rounded-2xl p-6" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <button onClick={() => setSelected(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-[rgba(255,255,255,0.05)]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-lg font-bold" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}>
                  {selected.name?.charAt(0) || '?'}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-[var(--text-primary)]">{selected.name}</h2>
                  <p className="text-sm text-[var(--text-muted)]">{TYPE_LABELS[selected.type] || selected.type}{selected.company_name ? ` — ${selected.company_name}` : ''}</p>
                </div>
              </div>
              <div className="space-y-3 text-sm">
                {[
                  ['SĐT', selected.phone],
                  ['Email', selected.email],
                  ['Địa chỉ', selected.address],
                  ['MST', selected.tax_code],
                  ['Ghi chú', selected.notes],
                ].map(([label, value]) => value && (
                  <div key={label as string} className="flex justify-between gap-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <span className="text-[var(--text-muted)]">{label}</span>
                    <span className="text-[var(--text-primary)] text-right max-w-[65%]">{value}</span>
                  </div>
                ))}
              </div>
              {/* Projects section */}
              <div className="mt-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-2">
                  <span>📋 Dự án</span>
                  {customerDetail?.project_count != null && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E' }}>
                      {customerDetail.project_count}
                    </span>
                  )}
                </h3>
                <div className="mb-4">
                  {(customerDetail as any)?.portal_token ? (
                    <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'rgba(201,169,110,0.05)', border: '1px solid rgba(201,169,110,0.2)' }}>
                      <span className="text-xs text-[var(--text-muted)] truncate flex-1">
                        Portal: {window.location.origin}/portal/{(customerDetail as any).portal_token}
                      </span>
                      <button onClick={() => {
                        navigator.clipboard.writeText(`${window.location.origin}/portal/${(customerDetail as any).portal_token}`);
                        toast('Đã copy link portal', 'success');
                      }} className="text-[10px] font-bold text-[#C9A96E] hover:underline">Copy</button>
                    </div>
                  ) : (
                    <button onClick={async () => {
                      if (!selected) return;
                      try {
                        const { token } = await api.generatePortalLink(selected.id);
                        toast('Đã tạo link portal thành công', 'success');
                        setCustomerDetail(prev => ({ ...prev, portal_token: token } as any));
                      } catch (e: any) {
                        toast(`Lỗi tạo link: ${e.message}`, 'error');
                      }
                    }} className="w-full text-center text-xs py-2 rounded-lg bg-[#C9A96E]/10 text-[#C9A96E] hover:bg-[#C9A96E]/20 transition-all">
                      Tạo link portal
                    </button>
                  )}
                </div>
                {loadingDetail ? (
                  <p className="text-xs text-[var(--text-muted)]">Đang tải...</p>
                ) : customerDetail?.projects && customerDetail.projects.length > 0 ? (
                  <div className="space-y-2">
                    {customerDetail.projects.map(p => (
                      <div key={p.id} className="p-3 rounded-xl text-xs" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-[var(--text-primary)]">{p.code} — {p.name}</span>
                          <span className="px-1.5 py-0.5 rounded text-[10px]" style={{
                            background: p.status === 'active' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                            color: p.status === 'active' ? '#34d399' : '#f87171',
                          }}>{p.status === 'active' ? 'Đang chạy' : p.status}</span>
                        </div>
                        <div className="flex items-center gap-3 text-[var(--text-muted)]">
                          <span>{p.total_value ? `${(p.total_value / 1_000_000).toFixed(0)}tr` : '—'}</span>
                          <span>Tiến độ: {p.progress}%</span>
                        </div>
                        <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-3)' }}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${p.progress}%`, background: 'linear-gradient(90deg, var(--gold-500), var(--gold-700))' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">Chưa có dự án</p>
                )}
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button onClick={() => setSelected(null)} className="px-3 py-2 rounded-xl text-sm bg-white/5 text-[var(--text-secondary)] hover:bg-white/10 transition-all">Đóng</button>
                <button onClick={() => openEdit(selected)} className="px-3 py-2 rounded-xl text-sm bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 transition-all">Sửa hồ sơ</button>
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
                  <p className="text-xs text-[var(--text-muted)] mt-1">Dữ liệu khách hàng phục vụ CRM, hợp đồng và dự án.</p>
                </div>
                <button type="button" onClick={() => !saving && setFormOpen(false)} className="p-2 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  ['name', 'Tên khách hàng *'],
                  ['phone', `SĐT ${editing ? '' : '*'}`],
                  ['email', 'Email'],
                  ['company_name', 'Tên công ty'],
                  ['tax_code', 'Mã số thuế'],
                ].map(([key, label]) => (
                  <label key={key} className="space-y-1">
                    <span className="text-xs text-[var(--text-muted)]">{label}</span>
                    <input type={key === 'email' ? 'email' : 'text'} value={form[key as keyof CustomerForm]} onChange={e => setForm({ ...form, [key]: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[#C9A96E]" />
                  </label>
                ))}
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Loại khách hàng</span>
                  <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[#C9A96E]">
                    <option value="individual">Cá nhân</option>
                    <option value="company">Doanh nghiệp</option>
                  </select>
                </label>
              </div>
              <label className="block space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Địa chỉ</span>
                <input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[#C9A96E]" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Ghi chú nội bộ</span>
                <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={3} className="w-full px-3 py-2 rounded-xl text-sm bg-white/5 border border-white/10 text-white outline-none focus:border-[#C9A96E] resize-none" />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" disabled={saving} onClick={() => setFormOpen(false)} className="px-4 py-2 rounded-xl text-sm bg-white/5 text-[var(--text-secondary)] hover:bg-white/10 disabled:opacity-40 transition-all">Hủy</button>
                <button type="submit" disabled={saving} className="px-4 py-2 rounded-xl text-sm font-semibold bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white disabled:opacity-50 transition-all">
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
