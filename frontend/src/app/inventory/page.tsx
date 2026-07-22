'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Material, extractItems, PaginatedResponse } from '@/lib/api';
import { DEMO_MATERIALS } from '@/lib/demo-data';
import { useToast } from '@/components/ui/Toast';
import { getPermissions, UserRole } from '@/lib/roles';
import { labelOf, MATERIAL_CATEGORY_LABELS } from '@/lib/labels';

function fmtVND(n?: number) {
  if (!n) return '—';
  return new Intl.NumberFormat('vi-VN').format(n) + ' ₫';
}

function fmtNum(n?: number) {
  if (n === undefined || n === null) return '—';
  return new Intl.NumberFormat('vi-VN').format(n);
}

export default function InventoryPage() {
  const { user, loading, isDemo } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [lowStock, setLowStock] = useState<Material[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('all');
  const [supplierFilter, setSupplierFilter] = useState('all');
  const [pageInfo, setPageInfo] = useState<{ page: number; total_pages: number; total: number }>({ page: 1, total_pages: 1, total: 0 });
  const [error, setError] = useState<string | null>(null);
  // Import báo giá/vật tư từ file CSV (Bước 1 gói NCC — 22/07)
  const [importOpen, setImportOpen] = useState(false);
  const [importRows, setImportRows] = useState<Array<Record<string, unknown>>>([]);
  const [importIssues, setImportIssues] = useState<string[]>([]);
  const [importFileName, setImportFileName] = useState('');
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // ── CSV helpers: parse trên trình duyệt để xem trước (chạy cả demo lẫn work) ──
  const HEADER_MAP: Record<string, string> = {
    'mã': 'code', 'ma': 'code', 'mã vật tư': 'code',
    'tên': 'name', 'ten': 'name', 'tên vật tư': 'name', 'ten vat tu': 'name',
    'danh mục': 'category', 'danh muc': 'category',
    'đơn vị': 'unit', 'don vi': 'unit', 'đvt': 'unit', 'dvt': 'unit',
    'đơn giá': 'unit_price', 'don gia': 'unit_price', 'giá': 'unit_price', 'gia': 'unit_price',
    'ncc': 'supplier', 'nhà cung cấp': 'supplier', 'nha cung cap': 'supplier',
    'tồn kho': 'quantity_in_stock', 'ton kho': 'quantity_in_stock', 'tồn': 'quantity_in_stock',
    'tồn tối thiểu': 'min_stock', 'ton toi thieu': 'min_stock', 'min': 'min_stock',
  };
  const NUMBER_FIELDS = new Set(['unit_price', 'quantity_in_stock', 'min_stock']);

  const parseCsvLine = (line: string, delim: string): string[] => {
    const out: string[] = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') inQ = false;
        else cur += ch;
      } else if (ch === '"') inQ = true;
      else if (ch === delim) { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur);
    return out;
  };

  const handleImportFile = (file: File) => {
    setImportFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '').replace(/^﻿/, '');
      const lines = text.split(/\r?\n/).filter(l => l.trim() !== '');
      if (lines.length < 2) { setImportRows([]); setImportIssues(['File cần dòng tiêu đề + ít nhất 1 dòng dữ liệu']); return; }
      // Excel VN hay xuất CSV với dấu ';'
      const delim = (lines[0].match(/;/g) || []).length > (lines[0].match(/,/g) || []).length ? ';' : ',';
      const headers = parseCsvLine(lines[0], delim).map(h => HEADER_MAP[h.trim().toLowerCase()] || null);
      if (!headers.includes('name')) { setImportRows([]); setImportIssues(['Không tìm thấy cột "Tên vật tư" — tải file mẫu để xem đúng định dạng']); return; }
      const rows: Array<Record<string, unknown>> = [];
      const issues: string[] = [];
      lines.slice(1).forEach((line, idx) => {
        const cells = parseCsvLine(line, delim);
        const row: Record<string, unknown> = {};
        headers.forEach((h, c) => {
          if (!h) return;
          const raw = (cells[c] || '').trim();
          if (raw === '') return;
          if (NUMBER_FIELDS.has(h)) {
            const num = Number(raw.replace(/[^\d]/g, ''));
            if (Number.isNaN(num)) issues.push(`Dòng ${idx + 2}: "${raw}" không phải số`);
            else row[h] = num;
          } else row[h] = raw;
        });
        if (Object.keys(row).length > 0) rows.push(row);
      });
      setImportRows(rows);
      setImportIssues(issues);
    };
    reader.readAsText(file, 'utf-8');
  };

  const downloadTemplate = () => {
    const csv = '﻿Mã,Tên vật tư,Danh mục,Đơn vị,Đơn giá,NCC,Tồn kho,Tồn tối thiểu\n'
      + 'VT-101,Gỗ óc chó tự nhiên,Gỗ,m2,2800000,Công ty An Cường,50,10\n'
      + ',Đèn thả trần phòng khách,Điện,cái,1250000,Rạng Đông,20,5\n';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    a.download = 'mau-import-vat-tu-jama.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleImportConfirm = async () => {
    if (importRows.length === 0) return;
    setImporting(true);
    try {
      const res = await api.importMaterials(importRows);
      toast(`Nhập xong: ${res.created} vật tư mới, ${res.updated} cập nhật${res.errors.length ? ` — ${res.errors.length} dòng lỗi` : ''}`, res.errors.length ? 'error' : 'success');
      if (res.errors.length) setImportIssues(res.errors);
      else { setImportOpen(false); setImportRows([]); setImportFileName(''); }
      load();
    } catch (e) {
      toast(`Lỗi nhập file: ${e instanceof Error ? e.message : 'Thử lại sau'}`, 'error');
    } finally {
      setImporting(false);
    }
  };

  const load = useCallback(async () => {
    // In demo mode, use local demo data directly
    if (isDemo) {
      setMaterials(DEMO_MATERIALS);
      setLowStock(DEMO_MATERIALS.filter(m => m.quantity_in_stock <= m.min_stock));
      setPageInfo({ page: 1, total_pages: 1, total: DEMO_MATERIALS.length });
      setLoadingData(false);
      return;
    }
    try {
      const [matResult, lowResult] = await Promise.all([api.getMaterials(), api.getLowStock()]);
      const mats = extractItems(matResult);
      const low = extractItems(lowResult);
      setMaterials(mats);
      setLowStock(low);
      // Track pagination info if available
      if (!Array.isArray(matResult) && matResult.total_pages) {
        setPageInfo({ page: matResult.page, total_pages: matResult.total_pages, total: matResult.total });
      } else {
        setPageInfo({ page: 1, total_pages: 1, total: mats.length });
      }
    } catch {
      setError('Không thể tải dữ liệu kho. Vui lòng thử lại.');
      // Fallback to demo data if API fails
      setMaterials(DEMO_MATERIALS);
      setLowStock(DEMO_MATERIALS.filter(m => m.quantity_in_stock <= m.min_stock));
      setPageInfo({ page: 1, total_pages: 1, total: DEMO_MATERIALS.length });
    } finally {
      setLoadingData(false);
    }
  }, [isDemo, toast]);

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


  // RBAC check - only admin and purchasing can view inventory
  const perms = getPermissions(user.role as UserRole);
  if (!perms.canViewInventory) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-12 text-center max-w-md">
            <span className="text-5xl block mb-4">🔒</span>
            <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
            <p className="text-sm text-[var(--text-muted)] mb-6">Chỉ Admin và bộ phận Thu mua được phép xem kho vật tư.</p>
            <button onClick={() => router.push('/')} className="px-6 py-2.5 rounded-xl text-sm font-medium" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: '#fff' }}>
              Quay về Tổng quan
            </button>
          </div>
        </div>
      </Sidebar>
    );
  }

  const categories = ['all', ...Array.from(new Set(materials.map(m => m.category)))];
  const suppliers = ['all', ...Array.from(new Set(materials.map(m => m.supplier).filter(Boolean) as string[]))];

  const filtered = materials
    .filter(m => catFilter === 'all' || m.category === catFilter)
    .filter(m => supplierFilter === 'all' || m.supplier === supplierFilter)
    .filter(m => m.name.toLowerCase().includes(search.toLowerCase()) || m.code.toLowerCase().includes(search.toLowerCase()));

  const totalValue = materials.reduce((s, m) => s + m.unit_price * m.quantity_in_stock, 0);

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Kho vật tư</h1>
            <p className="text-sm text-[var(--text-tertiary)] mt-1">{materials.length} mặt hàng</p>
          </div>
          <button
            onClick={() => { setImportOpen(true); setImportRows([]); setImportIssues([]); setImportFileName(''); }}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}
          >
            📥 Nhập từ file
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Tổng mặt hàng', value: materials.length, icon: '📦', color: '#60a5fa' },
            { label: 'Giá trị tồn kho', value: fmtVND(totalValue), icon: '💎', color: 'var(--gold-400)' },
            { label: 'Cảnh báo hết hàng', value: lowStock.length, icon: '⚠️', color: '#f87171' },
            { label: 'Danh mục', value: categories.length - 1, icon: '🏷️', color: '#a78bfa' },
          ].map(card => (
            <div key={card.label} className="rounded-2xl p-4" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{card.icon}</span>
                <span className="text-xs text-[var(--text-muted)]">{card.label}</span>
              </div>
              <p className="text-xl font-bold" style={{ color: card.color }}>{card.value}</p>
            </div>
          ))}
        </div>

        {/* Low stock alert */}
        {lowStock.length > 0 && (
          <div className="rounded-2xl p-4" style={{ background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.2)' }}>
            <p className="text-sm font-semibold mb-2" style={{ color: '#f87171' }}>⚠️ Vật tư sắp hết</p>
            <div className="flex flex-wrap gap-2">
              {lowStock.map(m => (
                <span key={m.id} className="px-3 py-1 rounded-lg text-xs font-medium" style={{ background: 'rgba(248,113,113,0.1)', color: '#f87171' }}>
                  {m.name}: {fmtNum(m.quantity_in_stock)} {m.unit} (min: {fmtNum(m.min_stock)})
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Search + Category filter + Supplier filter */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1 max-w-md">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input
                type="text"
                placeholder="Tìm vật tư..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
          </div>

          {/* Category filter */}
          <div>
            <p className="text-xs text-[var(--text-muted)] mb-1.5">Danh mục</p>
            <div className="flex gap-2 flex-wrap">
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setCatFilter(cat)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: catFilter === cat ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
                    color: catFilter === cat ? 'var(--gold-400)' : 'var(--text-tertiary)',
                    border: `1px solid ${catFilter === cat ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                  }}
                >
                  {cat === 'all' ? 'Tất cả' : labelOf(MATERIAL_CATEGORY_LABELS, cat)}
                </button>
              ))}
            </div>
          </div>

          {/* Supplier (NCC) filter */}
          <div>
            <p className="text-xs text-[var(--text-muted)] mb-1.5">Nhà cung cấp (NCC)</p>
            <div className="flex gap-2 flex-wrap">
              {suppliers.map(sup => (
                <button
                  key={sup}
                  onClick={() => setSupplierFilter(sup)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: supplierFilter === sup ? 'rgba(167,139,250,0.15)' : 'var(--surface-2)',
                    color: supplierFilter === sup ? '#a78bfa' : 'var(--text-tertiary)',
                    border: `1px solid ${supplierFilter === sup ? 'rgba(167,139,250,0.3)' : 'var(--border-subtle)'}`,
                  }}
                >
                  {sup === 'all' ? 'Tất cả NCC' : sup}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          {loadingData ? (
            <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <span className="text-4xl block mb-3">📦</span>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Không tìm thấy vật tư</h3>
              <p className="text-sm text-[var(--text-muted)]">Thử đổi bộ lọc hoặc từ khóa tìm kiếm</p>
            </div>
          ) : (
            <>
              {/* Mobile card view */}
              <div className="md:hidden p-3 space-y-3">
                {filtered.map(m => {
                  const isLow = m.quantity_in_stock <= m.min_stock;
                  return (
                    <div key={m.id} className="p-4 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-xs text-[var(--gold-400)]">{m.code}</span>
                        <span className="px-2 py-1 rounded-lg text-xs" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>{labelOf(MATERIAL_CATEGORY_LABELS, m.category)}</span>
                      </div>
                      <p className="text-sm font-medium text-[var(--text-primary)] mb-2">{m.name}</p>
                      <div className="flex items-center justify-between text-xs">
                        <div>
                          <span className="text-[var(--text-muted)]">Tồn kho: </span>
                          <span className={`font-semibold ${isLow ? 'text-[#f87171]' : 'text-[var(--text-primary)]'}`}>
                            {fmtNum(m.quantity_in_stock)} {m.unit}
                          </span>
                          {isLow && <span className="ml-1 text-[#f87171]">⚠</span>}
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)]">Đơn giá: </span>
                          <span className="font-semibold text-[var(--text-primary)]">{fmtVND(m.unit_price)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* Desktop table view */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Mã</th>
                      <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Tên vật tư</th>
                      <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Danh mục</th>
                      <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Tồn kho</th>
                      <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Đơn giá</th>
                      <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Giá trị</th>
                      <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">NCC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(m => {
                      const isLow = m.quantity_in_stock <= m.min_stock;
                      return (
                        <tr
                          key={m.id}
                          className="transition-colors"
                          style={{ borderBottom: '1px solid var(--border-subtle)' }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                        >
                          <td className="px-5 py-3.5 font-mono text-xs text-[var(--gold-400)]">{m.code}</td>
                          <td className="px-5 py-3.5 font-medium text-[var(--text-primary)]">{m.name}</td>
                          <td className="px-5 py-3.5">
                            <span className="px-2 py-1 rounded-lg text-xs" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>{labelOf(MATERIAL_CATEGORY_LABELS, m.category)}</span>
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <span className={`font-semibold ${isLow ? 'text-[#f87171]' : 'text-[var(--text-primary)]'}`}>
                              {fmtNum(m.quantity_in_stock)}
                            </span>
                            <span className="text-xs text-[var(--text-muted)] ml-1">{m.unit}</span>
                            {isLow && <span className="ml-2 text-xs text-[#f87171]">⚠</span>}
                          </td>
                          <td className="px-5 py-3.5 text-right text-[var(--text-secondary)]">{fmtVND(m.unit_price)}</td>
                          <td className="px-5 py-3.5 text-right text-[var(--text-secondary)]">{fmtVND(m.unit_price * m.quantity_in_stock)}</td>
                          <td className="px-5 py-3.5 text-[var(--text-muted)] max-w-[150px] truncate">{m.supplier || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {/* Pagination info */}
          {!loadingData && (
            <div className="px-5 py-3 text-xs text-[var(--text-muted)]" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              Trang {pageInfo.page}/{pageInfo.total_pages} — Tổng {pageInfo.total} mặt hàng
            </div>
          )}
        </div>
      </div>

      {/* Modal Nhập từ file (CSV) */}
      {importOpen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center px-4" onClick={() => !importing && setImportOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-2xl rounded-2xl p-5 sm:p-6 max-h-[88vh] overflow-y-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-1 text-[var(--text-primary)]">📥 Nhập vật tư / báo giá NCC từ file</h3>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
              File CSV (Excel: <b>Lưu dưới dạng → CSV UTF-8</b>). Cột bắt buộc: <b>Tên vật tư</b>; tùy chọn: Mã, Danh mục, Đơn vị, Đơn giá, NCC, Tồn kho, Tồn tối thiểu.
              Trùng Mã/Tên = cập nhật giá & NCC (báo giá mới); chưa có = tạo mới.{' '}
              <button onClick={downloadTemplate} className="underline text-[#C9A96E]">Tải file mẫu</button>
            </p>

            <label className="block w-full p-6 rounded-xl text-center cursor-pointer transition-all hover:opacity-80 mb-3" style={{ border: '2px dashed var(--border-default)', color: 'var(--text-secondary)' }}>
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ''; }} />
              {importFileName ? <span className="text-sm font-medium">📄 {importFileName} — bấm để chọn file khác</span> : <span className="text-sm">Bấm để chọn file CSV</span>}
            </label>

            {importIssues.length > 0 && (
              <div className="mb-3 p-3 rounded-xl text-xs space-y-1" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', color: '#F87171' }}>
                {importIssues.slice(0, 6).map((iss, i) => <p key={i}>⚠️ {iss}</p>)}
                {importIssues.length > 6 && <p>… và {importIssues.length - 6} lỗi khác</p>}
              </div>
            )}

            {importRows.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-semibold mb-2 text-[var(--text-secondary)]">Xem trước {Math.min(importRows.length, 8)}/{importRows.length} dòng:</p>
                <div className="rounded-xl overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        {['Mã', 'Tên vật tư', 'Danh mục', 'ĐVT', 'Đơn giá', 'NCC', 'Tồn'].map(h => <th key={h} className="text-left p-2 text-[var(--text-muted)] whitespace-nowrap">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {importRows.slice(0, 8).map((r, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td className="p-2 font-mono">{String(r.code || '—')}</td>
                          <td className="p-2">{String(r.name || '')}</td>
                          <td className="p-2">{String(r.category || '—')}</td>
                          <td className="p-2">{String(r.unit || '—')}</td>
                          <td className="p-2 whitespace-nowrap">{r.unit_price != null ? Number(r.unit_price).toLocaleString('vi-VN') + ' đ' : '—'}</td>
                          <td className="p-2">{String(r.supplier || '—')}</td>
                          <td className="p-2">{r.quantity_in_stock != null ? String(r.quantity_in_stock) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button onClick={() => setImportOpen(false)} disabled={importing} className="px-4 py-2.5 rounded-xl text-sm font-medium disabled:opacity-50" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                Hủy
              </button>
              <button onClick={handleImportConfirm} disabled={importing || importRows.length === 0} className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                {importing ? 'Đang nhập...' : `Nhập ${importRows.length} dòng`}
              </button>
            </div>
          </div>
        </div>
      )}
    </Sidebar>
  );
}
