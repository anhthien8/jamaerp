'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, InstantQuoteResult, PriceItemDTO } from '@/lib/api';

const PROPERTY_TYPES = [
  { value: 'apartment', label: '🏢 Căn hộ' },
  { value: 'townhouse', label: '🏠 Nhà phố' },
  { value: 'villa', label: '🏡 Biệt thự' },
  { value: 'office', label: '💼 Văn phòng' },
  { value: 'shophouse', label: '🏬 Shophouse' },
];

const CATEGORY_LABELS: Record<string, string> = {
  tran_vach: 'Trần & vách', san: 'Sàn', son_giay: 'Sơn & giấy',
  tu_bep: 'Tủ bếp', tu_ao_go: 'Tủ áo & đồ gỗ', sofa_ban_ghe: 'Sofa & bàn ghế',
  giuong_nem: 'Giường & nệm', den_dien: 'Đèn & điện', rem_trang_tri: 'Rèm & trang trí',
  thiet_bi: 'Thiết bị', khac: 'Khác',
};

function fmtVND(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
  if (v >= 1_000_000) return `${Math.round(v / 1_000_000).toLocaleString('vi-VN')} tr`;
  return `${Math.round(v / 1000).toLocaleString('vi-VN')}k`;
}

export default function QuoteToolPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<'form' | 'paste'>('form');
  const [area, setArea] = useState('');
  const [ptype, setPtype] = useState('apartment');
  const [bedrooms, setBedrooms] = useState('');
  const [budget, setBudget] = useState('');
  const [rawText, setRawText] = useState('');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<InstantQuoteResult | null>(null);
  const [activeTier, setActiveTier] = useState<'basic' | 'standard' | 'premium'>('standard');
  const [message, setMessage] = useState('');
  const [showPriceBook, setShowPriceBook] = useState(false);
  const [priceItems, setPriceItems] = useState<PriceItemDTO[]>([]);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setMessage('');
    setResult(null);
    try {
      const payload = mode === 'paste'
        ? { raw_text: rawText, budget: budget ? parseFloat(budget) * 1_000_000 : undefined }
        : {
            area_sqm: parseFloat(area),
            property_type: ptype,
            bedrooms: bedrooms ? parseInt(bedrooms, 10) : undefined,
            budget: budget ? parseFloat(budget) * 1_000_000 : undefined,
          };
      if (mode === 'form' && (!payload.area_sqm || isNaN(payload.area_sqm))) {
        setMessage('❌ Nhập diện tích (m²)');
        setGenerating(false);
        return;
      }
      const res = await api.generateInstantQuote(payload);
      setResult(res);
      setActiveTier(res.suggested_tier);
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi tạo báo giá'}`);
    } finally {
      setGenerating(false);
    }
  }, [mode, rawText, area, ptype, bedrooms, budget]);

  const copyZalo = useCallback(() => {
    if (!result) return;
    navigator.clipboard.writeText(result.zalo_text).then(
      () => setMessage('✅ Đã copy — dán vào Zalo gửi khách ngay!'),
      () => setMessage('❌ Không copy được'),
    );
  }, [result]);

  const loadPriceBook = useCallback(() => {
    api.getPriceItems().then(setPriceItems).catch(() => {});
  }, []);

  if (loading || !user) return null;
  const canEditPrices = user.role === 'admin' || user.role === 'purchasing';

  const inputCls = 'w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-[#C9A96E]';

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
          <h1 className="text-2xl font-bold">⚡ Báo giá tức thì</h1>
          <button
            onClick={() => { setShowPriceBook(s => !s); if (!showPriceBook) loadPriceBook(); }}
            className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10"
          >
            📒 {showPriceBook ? 'Đóng bảng đơn giá' : 'Xem bảng đơn giá'}
          </button>
        </div>
        <p className="text-sm text-[var(--text-muted)] mb-6">
          Báo giá sơ bộ ±15% trong 30 giây — gửi khách khi còn &quot;nóng&quot;, chốt lịch khảo sát. Giá chính xác vẫn do Thu mua lập sau khảo sát.
        </p>

        {/* ── Price book ── */}
        {showPriceBook && (
          <div className="glass-card p-5 mb-6 overflow-x-auto">
            <p className="text-xs text-[var(--text-muted)] mb-3">
              {canEditPrices
                ? '⚠️ Đơn giá seed là số tham khảo thị trường — Thu mua cập nhật giá thật trước khi dùng. Sửa trực tiếp ô giá rồi bấm ra ngoài để lưu.'
                : 'Bảng đơn giá chuẩn (chỉ Admin/Thu mua được sửa).'}
            </p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[var(--text-muted)] border-b border-white/10">
                  <th className="py-2 pr-2">Hạng mục</th>
                  <th className="py-2 pr-2">Nhóm</th>
                  <th className="py-2 pr-2">ĐV</th>
                  <th className="py-2 pr-2 text-right">Cơ bản</th>
                  <th className="py-2 pr-2 text-right">Tiêu chuẩn</th>
                  <th className="py-2 text-right">Cao cấp</th>
                </tr>
              </thead>
              <tbody>
                {priceItems.map(p => (
                  <tr key={p.id} className="border-b border-white/5">
                    <td className="py-1.5 pr-2">{p.name}</td>
                    <td className="py-1.5 pr-2 text-[var(--text-muted)]">{CATEGORY_LABELS[p.category] || p.category}</td>
                    <td className="py-1.5 pr-2 text-[var(--text-muted)]">{p.unit}</td>
                    {(['price_basic', 'price_standard', 'price_premium'] as const).map(field => (
                      <td key={field} className="py-1.5 pr-2 text-right">
                        {canEditPrices ? (
                          <input
                            type="number"
                            defaultValue={p[field]}
                            onBlur={e => {
                              const v = parseFloat(e.target.value);
                              if (!isNaN(v) && v >= 0 && v !== p[field]) {
                                api.updatePriceItem(p.id, { [field]: v }).then(loadPriceBook).catch(() => {});
                              }
                            }}
                            className="w-24 px-1 py-0.5 rounded bg-white/5 border border-white/10 text-right font-mono text-xs"
                          />
                        ) : (
                          <span className="font-mono">{p[field].toLocaleString('vi-VN')}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Input ── */}
        <div className="glass-card p-6 mb-6 max-w-3xl">
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setMode('form')}
              className={`px-4 py-2 rounded-xl text-sm font-semibold ${mode === 'form' ? 'bg-[#C9A96E] text-black' : 'bg-white/5 border border-white/10'}`}
            >
              📐 Nhập số liệu
            </button>
            <button
              onClick={() => setMode('paste')}
              className={`px-4 py-2 rounded-xl text-sm font-semibold ${mode === 'paste' ? 'bg-[#C9A96E] text-black' : 'bg-white/5 border border-white/10'}`}
            >
              🤖 Paste tin Zalo (AI)
            </button>
          </div>

          {mode === 'form' ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">Diện tích (m²) *</label>
                <input type="number" value={area} onChange={e => setArea(e.target.value)} placeholder="75" className={inputCls} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">Loại nhà</label>
                <select value={ptype} onChange={e => setPtype(e.target.value)} className={inputCls}>
                  {PROPERTY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">Phòng ngủ</label>
                <input type="number" value={bedrooms} onChange={e => setBedrooms(e.target.value)} placeholder="Tự ước lượng" className={inputCls} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">Ngân sách KH (triệu)</label>
                <input type="number" value={budget} onChange={e => setBudget(e.target.value)} placeholder="300" className={inputCls} />
              </div>
            </div>
          ) : (
            <textarea
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              placeholder={'Paste tin nhắn Zalo của khách, vd:\n"chị ơi nhà em chung cư vinhomes q9 75m2 2 phòng ngủ, muốn làm nội thất hiện đại tầm 300tr đổ lại thì được không"'}
              rows={4}
              className={inputCls}
            />
          )}

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={generate}
              disabled={generating}
              className="px-6 py-2.5 rounded-xl bg-[#C9A96E] text-black text-sm font-bold hover:opacity-90 disabled:opacity-50"
            >
              {generating ? '⏳ Đang tính...' : '⚡ Tạo báo giá'}
            </button>
            {message && <span className="text-sm text-[var(--text-secondary)]">{message}</span>}
          </div>
        </div>

        {/* ── Result ── */}
        {result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] flex-wrap">
              <span>📐 {result.area_sqm}m² · {PROPERTY_TYPES.find(t => t.value === result.property_type)?.label} · {result.bedrooms} PN</span>
              {result.customer_budget && (
                <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-xs">
                  Ngân sách KH: {fmtVND(result.customer_budget)}
                </span>
              )}
            </div>

            {/* 3 tier cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {(['basic', 'standard', 'premium'] as const).map(tier => {
                const t = result.tiers[tier];
                const isSuggested = result.suggested_tier === tier;
                const isActive = activeTier === tier;
                return (
                  <button
                    key={tier}
                    onClick={() => setActiveTier(tier)}
                    className={`glass-card p-5 text-left transition-all ${isActive ? 'ring-2 ring-[#C9A96E]' : 'hover:bg-white/5'}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold">{t.label}</span>
                      {isSuggested && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#C9A96E] text-black font-bold">GỢI Ý</span>
                      )}
                    </div>
                    <p className="text-xl font-bold text-[#C9A96E]">{fmtVND(t.range_low)} – {fmtVND(t.range_high)}</p>
                    <p className="text-xs text-[var(--text-muted)] mt-1">≈ {fmtVND(t.per_sqm)}/m²</p>
                  </button>
                );
              })}
            </div>

            {/* Actions */}
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={copyZalo}
                className="px-5 py-2.5 rounded-xl bg-[#1A535C] text-white text-sm font-semibold hover:opacity-90"
              >
                📋 Copy text gửi Zalo
              </button>
            </div>

            {/* Detail table */}
            <div className="glass-card p-5 overflow-x-auto">
              <h3 className="text-sm font-semibold mb-3">
                Chi tiết phương án {result.tiers[activeTier].label} — tổng {fmtVND(result.tiers[activeTier].total)}
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[var(--text-muted)] border-b border-white/10">
                    <th className="py-2 pr-2">Hạng mục</th>
                    <th className="py-2 pr-2 text-right">SL</th>
                    <th className="py-2 pr-2">ĐV</th>
                    <th className="py-2 pr-2 text-right">Đơn giá</th>
                    <th className="py-2 text-right">Thành tiền</th>
                  </tr>
                </thead>
                <tbody>
                  {result.tiers[activeTier].items.map(item => (
                    <tr key={item.code} className="border-b border-white/5">
                      <td className="py-1.5 pr-2">{item.name}</td>
                      <td className="py-1.5 pr-2 text-right font-mono">{item.qty}</td>
                      <td className="py-1.5 pr-2 text-[var(--text-muted)]">{item.unit}</td>
                      <td className="py-1.5 pr-2 text-right font-mono">{item.unit_price.toLocaleString('vi-VN')}</td>
                      <td className="py-1.5 text-right font-mono">{item.total.toLocaleString('vi-VN')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-[var(--text-muted)] mt-3">{result.disclaimer}</p>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
