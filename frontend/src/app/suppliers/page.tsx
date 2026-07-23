'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, type Supplier, type SupplierQuote, type PriceComparison } from '@/lib/api';
import PriceComparisonTable from '@/components/ui/PriceComparison';

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

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [quotes, setQuotes] = useState<SupplierQuote[]>([]);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [compareData, setCompareData] = useState<PriceComparison | null>(null);
  const [compareMaterial, setCompareMaterial] = useState('');

  // Form states
  const [form, setForm] = useState({ name: '', contact_person: '', phone: '', email: '', address: '', category: 'general', notes: '' });
  const [quoteForm, setQuoteForm] = useState({ material_name: '', material_category: 'general', unit: 'cái', unit_price: 0, min_quantity: 1, lead_time_days: 3, notes: '' });

  const loadSuppliers = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (categoryFilter !== 'all') params.category = categoryFilter;
      const res = await api.getSuppliers(params);
      setSuppliers(Array.isArray(res) ? res : res.items);
    } catch { /* ignore */ }
    setLoading(false);
  }, [search, categoryFilter]);

  useEffect(() => { loadSuppliers(); }, [loadSuppliers]);

  const loadQuotes = async (supplierId: string) => {
    setQuotesLoading(true);
    try {
      const data = await api.getSupplierQuotes(supplierId);
      setQuotes(Array.isArray(data) ? data : []);
    } catch { setQuotes([]); }
    setQuotesLoading(false);
  };

  const handleSelectSupplier = (supplier: Supplier) => {
    setSelectedSupplier(supplier);
    loadQuotes(supplier.id);
  };

  const handleCreateSupplier = async () => {
    try {
      await api.createSupplier(form);
      setShowAddModal(false);
      setForm({ name: '', contact_person: '', phone: '', email: '', address: '', category: 'general', notes: '' });
      loadSuppliers();
    } catch { /* ignore */ }
  };

  const handleAddQuote = async () => {
    if (!selectedSupplier) return;
    try {
      await api.addSupplierQuote(selectedSupplier.id, { ...quoteForm, valid_from: new Date().toISOString().slice(0, 10) });
      setShowQuoteModal(false);
      setQuoteForm({ material_name: '', material_category: 'general', unit: 'cái', unit_price: 0, min_quantity: 1, lead_time_days: 3, notes: '' });
      loadQuotes(selectedSupplier.id);
    } catch { /* ignore */ }
  };

  const handleCompare = async () => {
    if (!compareMaterial.trim()) return;
    try {
      const data = await api.comparePrices(compareMaterial);
      setCompareData(data);
      setShowCompare(true);
    } catch { /* ignore */ }
  };

  const fmt = (n: number) => n.toLocaleString('vi-VN');

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Nha cung cap</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Quan ly nha cung cap va bang gia</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
          style={{ background: 'var(--gold-500)', color: '#000' }}
        >
          + Them nha cung cap
        </button>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Tim kiem nha cung cap..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-4 py-2.5 rounded-xl text-sm outline-none"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
        />
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl text-sm outline-none"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
        >
          <option value="all">Tat ca loai</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {/* Price Compare Quick Search */}
      <div
        className="flex items-center gap-3 p-4 rounded-xl"
        style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>So sanh gia:</span>
        <input
          type="text"
          placeholder="Nhap ten vat tu (VD: Go soi, Son noi that)..."
          value={compareMaterial}
          onChange={e => setCompareMaterial(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleCompare()}
          className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
        />
        <button
          onClick={handleCompare}
          className="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
          style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)', border: '1px solid rgba(201,169,110,0.3)' }}
        >
          So sanh gia
        </button>
      </div>

      {/* Main Content: List + Detail */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Supplier List */}
        <div className="lg:w-1/2 space-y-3">
          {loading ? (
            <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Dang tai...</div>
          ) : suppliers.length === 0 ? (
            <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Khong co nha cung cap nao</div>
          ) : (
            suppliers.map(s => (
              <div
                key={s.id}
                onClick={() => handleSelectSupplier(s)}
                className="p-4 rounded-xl cursor-pointer transition-all"
                style={{
                  background: selectedSupplier?.id === s.id ? 'rgba(201,169,110,0.1)' : 'var(--surface-elevated)',
                  border: `1px solid ${selectedSupplier?.id === s.id ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
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
                    </div>
                    {s.contact_person && (
                      <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                        {s.contact_person}{s.phone ? ` · ${s.phone}` : ''}
                      </p>
                    )}
                  </div>
                  {s.quote_count != null && s.quote_count > 0 && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                      {s.quote_count} bao gia
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail Panel */}
        <div className="lg:w-1/2">
          {selectedSupplier ? (
            <div className="space-y-4">
              {/* Supplier Info Card */}
              <div className="p-5 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{selectedSupplier.name}</h2>
                  <button
                    onClick={() => setShowQuoteModal(true)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold"
                    style={{ background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }}
                  >
                    + Them bao gia
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {selectedSupplier.contact_person && <div><span style={{ color: 'var(--text-muted)' }}>Lien he:</span> {selectedSupplier.contact_person}</div>}
                  {selectedSupplier.phone && <div><span style={{ color: 'var(--text-muted)' }}>Dien thoai:</span> {selectedSupplier.phone}</div>}
                  {selectedSupplier.email && <div><span style={{ color: 'var(--text-muted)' }}>Email:</span> {selectedSupplier.email}</div>}
                  {selectedSupplier.address && <div><span style={{ color: 'var(--text-muted)' }}>Dia chi:</span> {selectedSupplier.address}</div>}
                </div>
                {selectedSupplier.notes && (
                  <p className="text-xs mt-3 p-2 rounded-lg" style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                    {selectedSupplier.notes}
                  </p>
                )}
              </div>

              {/* Price Quotes */}
              <div className="p-5 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
                <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
                  Bang gia ({quotes.length})
                </h3>
                {quotesLoading ? (
                  <div className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>Dang tai...</div>
                ) : quotes.length === 0 ? (
                  <div className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>Chua co bao gia</div>
                ) : (
                  <div className="space-y-2">
                    {quotes.map(q => (
                      <div key={q.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{q.material_name}</p>
                          <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                            {q.unit} · SL toi thieu: {q.min_quantity || '-'} · Giao hang: {q.lead_time_days || '-'} ngay
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0 ml-3">
                          <p className="text-sm font-bold" style={{ color: 'var(--gold-400)' }}>{fmt(q.unit_price)}d</p>
                          {q.valid_until && (
                            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>HS den {q.valid_until}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 rounded-xl" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chon nha cung cap de xem chi tiet</p>
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
                So sanh gia: {compareData.material_name}
              </h2>
              <button onClick={() => setShowCompare(false)} className="text-sm" style={{ color: 'var(--text-muted)' }}>Dong</button>
            </div>
            <PriceComparisonTable data={compareData} />
          </div>
        </div>
      )}

      {/* Add Supplier Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowAddModal(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg rounded-2xl p-6 space-y-4"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Them nha cung cap moi</h2>
            <div className="grid grid-cols-2 gap-3">
              {([
                { key: 'name', label: 'Ten NCC', required: true },
                { key: 'contact_person', label: 'Nguoi lien he', required: false },
                { key: 'phone', label: 'Dien thoai', required: false },
                { key: 'email', label: 'Email', required: false },
                { key: 'address', label: 'Dia chi', required: false },
              ] as const).map(f => (
                <div key={f.key} className={f.key === 'name' ? 'col-span-2' : ''}>
                  <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>{f.label}{f.required && ' *'}</label>
                  <input
                    type={f.key === 'email' ? 'email' : 'text'}
                    value={form[f.key]}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                  />
                </div>
              ))}
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Loai</label>
                <select
                  value={form.category}
                  onChange={e => setForm({ ...form, category: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                >
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Ghi chu</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Huy</button>
              <button
                onClick={handleCreateSupplier}
                disabled={!form.name.trim()}
                className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--gold-500)', color: '#000' }}
              >
                Them
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Quote Modal */}
      {showQuoteModal && selectedSupplier && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowQuoteModal(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg rounded-2xl p-6 space-y-4"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Them bao gia — {selectedSupplier.name}
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Ten vat tu *</label>
                <input
                  type="text"
                  value={quoteForm.material_name}
                  onChange={e => setQuoteForm({ ...quoteForm, material_name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Don vi</label>
                <input
                  type="text"
                  value={quoteForm.unit}
                  onChange={e => setQuoteForm({ ...quoteForm, unit: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Don gia (VND) *</label>
                <input
                  type="number"
                  value={quoteForm.unit_price}
                  onChange={e => setQuoteForm({ ...quoteForm, unit_price: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>SL toi thieu</label>
                <input
                  type="number"
                  value={quoteForm.min_quantity}
                  onChange={e => setQuoteForm({ ...quoteForm, min_quantity: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Giao hang (ngay)</label>
                <input
                  type="number"
                  value={quoteForm.lead_time_days}
                  onChange={e => setQuoteForm({ ...quoteForm, lead_time_days: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Ghi chu</label>
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
              <button onClick={() => setShowQuoteModal(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Huy</button>
              <button
                onClick={handleAddQuote}
                disabled={!quoteForm.material_name.trim() || quoteForm.unit_price <= 0}
                className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--gold-500)', color: '#000' }}
              >
                Them bao gia
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
