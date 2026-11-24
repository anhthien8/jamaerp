'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Quotation, Project, extractItems } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { getPermissions, canApproveQuotation, UserRole } from '@/lib/roles';
import AccessDenied from '@/components/ui/AccessDenied';
import MoneyInput from '@/components/ui/MoneyInput';
import LineIcon from '@/components/ui/LineIcon';

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Nháp', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
  approved: { label: 'Duyệt', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  sent: { label: 'Đã gửi', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  rejected: { label: 'Từ chối', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  expired: { label: 'Hết hạn', color: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
};

const TYPE_MAP: Record<string, string> = {
  design: 'Thiết kế',
  construction: 'Thi công',
};

function fmtVND(n?: number) {
  if (!n) return '—';
  return new Intl.NumberFormat('vi-VN').format(n) + ' ₫';
}

/** Một dòng hạng mục trong editor. quantity/unit_price lưu dạng string (đơn giá tính bằng ĐỒNG như MoneyInput emit). */
interface LineItemForm {
  name: string;
  unit: string;
  quantity: string;
  unit_price: string;
}

function lineItemTotal(li: LineItemForm) {
  return (Number(li.quantity) || 0) * (Number(li.unit_price) || 0);
}

interface QuotationFormData {
  title: string;
  type: string;
  project_id: string;
  total_amount: string;
  tax_amount: string;
  valid_until: string;
  notes: string;
}

const EMPTY_FORM: QuotationFormData = {
  title: '',
  type: 'design',
  project_id: '',
  total_amount: '',
  tax_amount: '',
  valid_until: '',
  notes: '',
};

/** Parse q.items.line_items có sẵn (shape lưu trong DB) vào các dòng editor. */
function parseLineItems(items: unknown): LineItemForm[] {
  const raw = (items as { line_items?: unknown } | null)?.line_items;
  if (!Array.isArray(raw)) return [];
  return raw.map(r => {
    const o = (r || {}) as Record<string, unknown>;
    return {
      name: o.name != null ? String(o.name) : '',
      unit: o.unit != null ? String(o.unit) : '',
      quantity: o.quantity != null ? String(o.quantity) : '',
      unit_price: o.unit_price != null ? String(o.unit_price) : '',
    };
  });
}

/** Hạng mục thô đúng như lưu trong DB, số đã ép kiểu — dùng cho xem chi tiết, nhân bản, copy gửi khách. */
function rawLineItems(items: unknown) {
  const raw = (items as { line_items?: unknown } | null)?.line_items;
  if (!Array.isArray(raw)) return [];
  return raw.map(r => {
    const o = (r || {}) as Record<string, unknown>;
    const quantity = Number(o.quantity) || 0;
    const unit_price = Number(o.unit_price) || 0;
    return {
      name: o.name != null ? String(o.name) : '',
      description: o.description != null ? String(o.description) : undefined,
      category: o.category != null ? String(o.category) : undefined,
      unit: o.unit != null ? String(o.unit) : '',
      quantity,
      unit_price,
      total: o.total != null ? Number(o.total) || 0 : quantity * unit_price,
    };
  });
}

export default function QuotationsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [selected, setSelected] = useState<Quotation | null>(null);
  const [filter, setFilter] = useState('all');

  // Create/Edit form state
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Quotation | null>(null);
  const [formData, setFormData] = useState<QuotationFormData>(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [lineItems, setLineItems] = useState<LineItemForm[]>([]);
  const [saving, setSaving] = useState(false);

  // Projects list for the select dropdown
  const [projects, setProjects] = useState<Project[]>([]);

  const perms = user ? getPermissions(user.role as UserRole) : null;
  const canCreate = perms?.canCreateQuotations ?? false;
  // Duyệt là quyền cấp trên, khác quyền soạn — backend chặn 403, FE ẩn nút cho khớp.
  const canApprove = canApproveQuotation(user);

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const data = extractItems(await api.getQuotations());
      setQuotations(data);
    } catch { toast('Không thể tải báo giá', 'error'); } finally {
      setLoadingData(false);
    }
  }, [toast]);

  const loadProjects = useCallback(async () => {
    try {
      const data = extractItems(await api.getProjects());
      setProjects(data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { if (user) { void Promise.resolve().then(load); void Promise.resolve().then(loadProjects); } }, [user, load, loadProjects]);

  const handleApprove = async (id: string) => {
    try {
      const updated = await api.approveQuotation(id);
      setQuotations(prev => prev.map(q => q.id === updated.id ? updated : q));
      setSelected(updated);
    } catch { toast('Duyệt báo giá thất bại', 'error'); }
  };

  // Nhân bản: bản sao luôn là NHÁP (backend ép status=draft), phải duyệt lại; bản gốc giữ nguyên.
  const handleDuplicate = async (q: Quotation) => {
    if (saving) return;
    setSaving(true);
    try {
      const han = new Date();
      han.setDate(han.getDate() + 15);
      const pad = (n: number) => String(n).padStart(2, '0');
      const created = await api.createQuotation({
        title: `${q.title} (bản sao)`,
        type: q.type,
        project_id: q.project_id || undefined,
        lead_id: q.lead_id || undefined,
        items: rawLineItems(q.items),
        total_amount: q.total_amount ?? undefined,
        tax_amount: q.tax_amount ?? undefined,
        valid_until: `${han.getFullYear()}-${pad(han.getMonth() + 1)}-${pad(han.getDate())}`,
        notes: q.notes || undefined,
      });
      setQuotations(prev => [created, ...prev]);
      setSelected(null);
      openEditForm(created);
      toast('Đã nhân bản — bản sao là nháp, cần duyệt lại', 'success');
    } catch {
      toast('Nhân bản báo giá thất bại', 'error');
    } finally {
      setSaving(false);
    }
  };

  // Copy nội dung báo giá ĐÃ DUYỆT để dán gửi khách (chỉ giá bán; không kèm phiên bản/trạng thái nội bộ).
  const copyForCustomer = (q: Quotation) => {
    const lines = [q.title, `Mã báo giá: ${q.code} (${TYPE_MAP[q.type] || q.type})`, ''];
    for (const li of rawLineItems(q.items)) {
      lines.push(`- ${li.name}: ${li.quantity} ${li.unit} x ${fmtVND(li.unit_price)} = ${fmtVND(li.total)}`);
    }
    lines.push('', `Tổng giá: ${fmtVND(q.total_amount)}`);
    if (q.tax_amount) lines.push(`Thuế: ${fmtVND(q.tax_amount)}`);
    if (q.valid_until) lines.push(`Hiệu lực đến: ${new Date(q.valid_until).toLocaleDateString('vi-VN')}`);
    const hetHan = !!q.valid_until && q.valid_until.slice(0, 10) < new Date().toLocaleDateString('en-CA');
    navigator.clipboard.writeText(lines.join('\n')).then(
      () => (hetHan
        ? toast('Đã copy — lưu ý báo giá này đã quá hạn hiệu lực', 'warning')
        : toast('Đã copy — dán vào Zalo gửi khách', 'success')),
      () => toast('Không copy được', 'error'),
    );
  };

  const openCreateForm = () => {
    setEditing(null);
    setFormError('');
    // Hạn hiệu lực mặc định 15 ngày — cùng quy ước với Báo giá tức thì.
    const han = new Date();
    han.setDate(han.getDate() + 15);
    setFormData({ ...EMPTY_FORM, valid_until: han.toLocaleDateString('sv-SE') });
    setLineItems([]);
    setShowForm(true);
  };

  const openEditForm = (q: Quotation, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditing(q);
    setFormError('');
    setFormData({
      title: q.title,
      type: q.type || 'design',
      project_id: q.project_id || '',
      total_amount: q.total_amount != null ? String(q.total_amount) : '',
      tax_amount: q.tax_amount != null ? String(q.tax_amount) : '',
      valid_until: q.valid_until ? q.valid_until.slice(0, 10) : '',
      notes: q.notes || '',
    });
    setLineItems(parseLineItems(q.items));
    setShowForm(true);
  };

  // Cập nhật danh sách dòng hạng mục; nếu tổng > 0 thì tự điền "Tổng tiền" (vẫn cho phép ghi đè tay).
  const updateLineItems = (next: LineItemForm[]) => {
    setLineItems(next);
    const sum = next.reduce((s, li) => s + lineItemTotal(li), 0);
    if (sum > 0) setFormData(p => ({ ...p, total_amount: String(sum) }));
  };
  const addLineItem = () => updateLineItems([...lineItems, { name: '', unit: '', quantity: '1', unit_price: '' }]);
  const patchLineItem = (i: number, patch: Partial<LineItemForm>) =>
    updateLineItems(lineItems.map((li, idx) => (idx === i ? { ...li, ...patch } : li)));
  const removeLineItem = (i: number) => updateLineItems(lineItems.filter((_, idx) => idx !== i));

  const handleFormSubmit = async () => {
    if (!formData.title.trim()) {
      setFormError('Tiêu đề không được để trống');
      toast('Tiêu đề không được để trống', 'error');
      return;
    }
    setFormError('');
    setSaving(true);
    try {
      const line_items = lineItems
        .filter(li => li.name.trim() !== '' || li.unit.trim() !== '' || li.unit_price !== '')
        .map(li => {
          const quantity = Number(li.quantity) || 0;
          const unit_price = Number(li.unit_price) || 0;
          return { name: li.name.trim(), unit: li.unit.trim(), quantity, unit_price, total: quantity * unit_price };
        });
      // Backend (QuotationCreate/Update) nhận items là MẢNG hạng mục rồi tự bọc
      // {line_items} khi lưu — FE gửi sẵn object bọc là 422, nút «Tạo báo giá»
      // chưa từng chạy được (mã BG giờ backend tự sinh, không cần gửi code).
      const payload: Partial<Quotation> = {
        title: formData.title.trim(),
        type: formData.type,
        project_id: formData.project_id || undefined,
        total_amount: formData.total_amount ? Number(formData.total_amount) : undefined,
        tax_amount: formData.tax_amount ? Number(formData.tax_amount) : undefined,
        valid_until: formData.valid_until || undefined,
        notes: formData.notes.trim() || undefined,
        items: line_items,
      };

      let updated: Quotation;
      if (editing) {
        updated = await api.updateQuotation(editing.id, payload);
        setQuotations(prev => prev.map(q => q.id === updated.id ? updated : q));
        toast('Cập nhật báo giá thành công', 'success');
      } else {
        updated = await api.createQuotation(payload);
        setQuotations(prev => [updated, ...prev]);
        toast('Tạo báo giá thành công', 'success');
      }
      setShowForm(false);
      setEditing(null);
    } catch {
      toast(editing ? 'Cập nhật báo giá thất bại' : 'Tạo báo giá thất bại', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;
  if (!user) return null;

  if (!perms?.canViewQuotations) return <AccessDenied />;

  const filtered = filter === 'all' ? quotations : quotations.filter(q => q.type === filter);

  return (
    <Sidebar>
    <div className="p-6 space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Báo giá</h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">{quotations.length} báo giá</p>
        </div>
        {canCreate && (
          <button
            onClick={openCreateForm}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold transition-all"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}
          >
            + Tạo báo giá mới
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {[
          { key: 'all', label: 'Tất cả' },
          { key: 'design', label: 'Thiết kế' },
          { key: 'construction', label: 'Thi công' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            style={{
              background: filter === tab.key ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
              color: filter === tab.key ? 'var(--gold-400)' : 'var(--text-tertiary)',
              border: `1px solid ${filter === tab.key ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grid cards */}
      {loadingData ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
      ) : filtered.length === 0 ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Chưa có báo giá nào</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(q => {
            const st = STATUS_MAP[q.status] || STATUS_MAP.draft;
            return (
              <div
                key={q.id}
                className="rounded-2xl p-5 cursor-pointer transition-all hover:scale-[1.01]"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
                onClick={() => setSelected(q)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-mono text-xs text-[var(--gold-400)]">{q.code}</p>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-1">{q.title}</h3>
                  </div>
                  <span className="px-2 py-1 rounded-lg text-xs font-medium whitespace-nowrap" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                  <span>{TYPE_MAP[q.type] || q.type}</span>
                  <span className="font-semibold text-sm text-[var(--text-primary)]">{fmtVND(q.total_amount)}</span>
                </div>
                <div className="flex items-center justify-between mt-3 pt-3 text-xs text-[var(--text-muted)]" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <span>Rev. {q.revision}</span>
                  <div className="flex items-center gap-2">
                    <span>{q.valid_until ? `HH: ${new Date(q.valid_until).toLocaleDateString('vi-VN')}` : '—'}</span>
                    {canCreate && (
                      <button
                        onClick={(e) => openEditForm(q, e)}
                        className="px-2 py-1 rounded-lg text-xs font-medium transition-colors"
                        style={{ background: 'rgba(96,165,250,0.1)', color: '#60a5fa', border: '1px solid rgba(96,165,250,0.2)' }}
                      >
                        Sửa
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detail modal */}
      {selected && !showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center pt-[6vh] px-4" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg mx-4 rounded-2xl p-6 max-h-[80vh] overflow-y-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
            <button onClick={() => setSelected(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/5">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
            <p className="font-mono text-xs text-[var(--gold-400)]">{selected.code}</p>
            <h2 className="text-xl font-bold text-[var(--text-primary)] mt-1 mb-4">{selected.title}</h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              {[
                ['Loại', TYPE_MAP[selected.type] || selected.type],
                ['Trạng thái', STATUS_MAP[selected.status]?.label || selected.status],
                ['Tổng giá', fmtVND(selected.total_amount)],
                ['Thuế', fmtVND(selected.tax_amount)],
                ['Phiên bản', `Rev. ${selected.revision}`],
                ['Hiệu lực', selected.valid_until ? new Date(selected.valid_until).toLocaleDateString('vi-VN') : '—'],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{value}</p>
                </div>
              ))}
            </div>

            {selected.notes && (
              <div className="rounded-xl p-3 mb-4" style={{ background: 'var(--surface-2)' }}>
                <p className="text-xs text-[var(--text-muted)] mb-1">Ghi chú</p>
                <p className="text-sm text-[var(--text-secondary)]">{selected.notes}</p>
              </div>
            )}

            {rawLineItems(selected.items).length > 0 && (
              <div className="rounded-xl p-3 mb-4" style={{ background: 'var(--surface-2)' }}>
                <p className="text-xs text-[var(--text-muted)] mb-2">Hạng mục</p>
                <div className="space-y-1.5">
                  {rawLineItems(selected.items).map((li, i) => (
                    <div key={i} className="flex items-start justify-between gap-3 text-xs">
                      <span className="text-[var(--text-secondary)] min-w-0">
                        {li.name}
                        <span className="text-[var(--text-muted)]"> · {li.quantity} {li.unit} x {fmtVND(li.unit_price)}</span>
                      </span>
                      <span className="font-mono whitespace-nowrap text-[var(--text-primary)]">{fmtVND(li.total)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2 flex-wrap">
              {(selected.status === 'approved' || selected.status === 'sent') && (
                <button
                  onClick={() => copyForCustomer(selected)}
                  className="flex-1 py-2.5 px-3 rounded-xl text-sm font-semibold transition-all whitespace-nowrap"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                >
                  <LineIcon name="clipboard" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Copy gửi khách
                </button>
              )}
              {canCreate && (
                <button
                  onClick={() => handleDuplicate(selected)}
                  disabled={saving}
                  className="flex-1 py-2.5 px-3 rounded-xl text-sm font-semibold transition-all whitespace-nowrap disabled:opacity-50"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                >
                  <LineIcon name="copy" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{saving ? 'Đang nhân bản...' : 'Nhân bản'}
                </button>
              )}
              {selected.status === 'draft' && canApprove && (
                <button
                  onClick={() => handleApprove(selected.id)}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all"
                  style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}
                >
                  Duyệt báo giá
                </button>
              )}
              {canCreate && (
                <button
                  onClick={() => { setSelected(null); openEditForm(selected); }}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                >
                  Chỉnh sửa
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit quotation modal */}
      {showForm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center pt-[6vh] px-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg mx-4 rounded-2xl p-6 max-h-[85vh] overflow-y-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
            <button onClick={() => { setShowForm(false); setEditing(null); }} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/5">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
            <h2 className="text-xl font-bold text-[var(--text-primary)] mb-4">
              {editing ? 'Chỉnh sửa báo giá' : 'Tạo báo giá mới'}
            </h2>

            <div className="space-y-4">
              {/* Title */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Tiêu đề <span style={{color:'#f87171'}}>*</span></label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={e => { setFormData(p => ({ ...p, title: e.target.value })); if (formError) setFormError(''); }}
                  placeholder="Nhập tiêu đề báo giá"
                  className="w-full px-3 py-2 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: formError ? '1px solid #f87171' : '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
                {formError && <p className="text-xs text-red-400 mt-1 font-medium">{formError}</p>}
              </div>

              {/* Type */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Loại báo giá</label>
                <select
                  value={formData.type}
                  onChange={e => setFormData(p => ({ ...p, type: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                >
                  <option value="design">Thiết kế</option>
                  <option value="construction">Thi công</option>
                </select>
              </div>

              {/* Project */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Dự án</label>
                <select
                  value={formData.project_id}
                  onChange={e => {
                    const da = projects.find(x => x.id === e.target.value);
                    // Chọn dự án thì điền luôn tiêu đề nếu ô còn trống.
                    setFormData(p => ({ ...p, project_id: e.target.value, title: p.title.trim() || !da ? p.title : `Báo giá ${p.type === 'construction' ? 'thi công' : 'thiết kế'} - ${da.name}` }));
                  }}
                  className="w-full px-3 py-2 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                >
                  <option value="">-- Chọn dự án --</option>
                  {projects.map(p => (
                    <option key={p.id} value={p.id}>{p.code} - {p.name}</option>
                  ))}
                </select>
              </div>

              {/* Amounts row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[var(--text-muted)] mb-1 block">Tổng tiền</label>
                  <MoneyInput
                    valueDong={formData.total_amount}
                    onChangeDong={v => setFormData(p => ({ ...p, total_amount: v }))}
                    placeholder="VD: 450000 = 450 triệu"
                    className="w-full px-3 py-2 rounded-xl text-sm pr-24"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                  />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-muted)] mb-1 flex items-center justify-between gap-2">
                    Thuế
                    <button
                      type="button"
                      disabled={!Number(formData.total_amount)}
                      onClick={() => setFormData(p => ({ ...p, tax_amount: String(Math.round(Number(p.total_amount) * 0.1)) }))}
                      className="px-2 rounded-full text-[11px] font-medium disabled:opacity-40"
                      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--gold-500)' }}
                    >
                      VAT 10%
                    </button>
                  </label>
                  <MoneyInput
                    valueDong={formData.tax_amount}
                    onChangeDong={v => setFormData(p => ({ ...p, tax_amount: v }))}
                    placeholder="VD: 45000 = 45 triệu"
                    className="w-full px-3 py-2 rounded-xl text-sm pr-24"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                  />
                </div>
              </div>

              {/* Valid until */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Hiệu lực đến</label>
                <input
                  type="date"
                  value={formData.valid_until}
                  onChange={e => setFormData(p => ({ ...p, valid_until: e.target.value }))}
                  className="w-full px-3 py-2 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
              </div>

              {/* Notes */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Ghi chú</label>
                <textarea
                  value={formData.notes}
                  onChange={e => setFormData(p => ({ ...p, notes: e.target.value }))}
                  placeholder="Ghi chú thêm..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-xl text-sm resize-none"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
              </div>

              <datalist id="dv-bao-gia">
                {['gói', 'm2', 'md', 'bộ', 'cái', 'phòng', 'công'].map(dv => <option key={dv} value={dv} />)}
              </datalist>
              {/* Items editor — danh sách dòng hạng mục (thay cho ô JSON thô) */}
              <div>
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Mục báo giá</label>
                <div className="space-y-3">
                  {lineItems.length === 0 && (
                    <p className="text-xs italic text-[var(--text-muted)]">Chưa có hạng mục nào. Nhấn &quot;+ Thêm hạng mục&quot; để bắt đầu.</p>
                  )}
                  {lineItems.map((li, i) => (
                    <div
                      key={i}
                      className="rounded-xl p-3 space-y-2"
                      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={li.name}
                          onChange={e => patchLineItem(i, { name: e.target.value })}
                          placeholder="Tên hạng mục"
                          className="flex-1 px-3 py-2 rounded-lg text-sm"
                          style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                        />
                        <button
                          onClick={() => removeLineItem(i)}
                          className="p-2 rounded-lg transition-colors shrink-0"
                          style={{ background: 'rgba(248,113,113,0.1)', color: '#f87171', border: '1px solid rgba(248,113,113,0.2)' }}
                          title="Xóa hạng mục"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Đơn vị</label>
                          <input
                            type="text"
                            value={li.unit}
                            onChange={e => patchLineItem(i, { unit: e.target.value })}
                            placeholder="gói / m2 / bộ"
                            list="dv-bao-gia"
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Số lượng</label>
                          <input
                            type="number"
                            min="0"
                            value={li.quantity}
                            onChange={e => patchLineItem(i, { quantity: e.target.value })}
                            placeholder="1"
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Đơn giá</label>
                        <MoneyInput
                          valueDong={li.unit_price}
                          onChangeDong={v => patchLineItem(i, { unit_price: v })}
                          placeholder="VD: 150000 = 150 triệu"
                          className="w-full px-3 py-2 rounded-lg text-sm pr-24"
                          style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                        />
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-[var(--text-muted)]">Thành tiền</span>
                        <span className="text-sm font-semibold text-[var(--text-primary)]">{fmtVND(lineItemTotal(li))}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={addLineItem}
                  className="mt-3 w-full py-2 rounded-xl text-sm font-medium transition-all"
                  style={{ background: 'var(--surface-2)', color: 'var(--gold-400)', border: '1px dashed var(--border-subtle)' }}
                >
                  + Thêm hạng mục
                </button>
                {lineItems.length > 0 && (
                  <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <span className="text-sm font-medium text-[var(--text-secondary)]">Tổng cộng</span>
                    <span className="text-base font-bold text-[var(--gold-400)]">{fmtVND(lineItems.reduce((s, li) => s + lineItemTotal(li), 0))}</span>
                  </div>
                )}
              </div>

              {/* Submit buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => { setShowForm(false); setEditing(null); }}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                >
                  Hủy
                </button>
                <button
                  onClick={handleFormSubmit}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40"
                  style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}
                >
                  {saving ? 'Đang lưu...' : editing ? 'Cập nhật' : 'Tạo mới'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
    </Sidebar>
  );
}
