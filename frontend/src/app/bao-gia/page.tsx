'use client';

/**
 * Trang báo giá công khai — lead magnet.
 * Khách tự nhập nhu cầu → nhận khoảng giá 3 phương án → hệ thống tự tạo lead nóng.
 * KHÔNG cần đăng nhập. Chỉ hiển thị khoảng giá (không lộ đơn giá chi tiết).
 */

import { useState, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const PROPERTY_TYPES = [
  { value: 'apartment', label: '🏢 Căn hộ' },
  { value: 'townhouse', label: '🏠 Nhà phố' },
  { value: 'villa', label: '🏡 Biệt thự' },
  { value: 'office', label: '💼 Văn phòng' },
  { value: 'shophouse', label: '🏬 Shophouse' },
];

interface PublicTier { label: string; range_low: number; range_high: number; per_sqm: number }
interface PublicQuote {
  area_sqm: number; property_type: string; bedrooms: number;
  suggested_tier: 'basic' | 'standard' | 'premium';
  tiers: Record<'basic' | 'standard' | 'premium', PublicTier>;
  disclaimer: string; message: string;
}

function fmtVND(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
  return `${Math.round(v / 1_000_000).toLocaleString('vi-VN')} triệu`;
}

export default function PublicQuotePage() {
  const [form, setForm] = useState({
    name: '', phone: '', area: '', ptype: 'apartment', bedrooms: '', budget: '', note: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PublicQuote | null>(null);

  const submit = useCallback(async () => {
    setError('');
    if (!form.name.trim() || form.phone.replace(/\D/g, '').length < 9) {
      setError('Vui lòng nhập họ tên và số điện thoại hợp lệ');
      return;
    }
    const areaNum = parseFloat(form.area);
    if (!areaNum || areaNum <= 0) {
      setError('Vui lòng nhập diện tích (m²)');
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/instant-quote/public`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          phone: form.phone.trim(),
          area_sqm: areaNum,
          property_type: form.ptype,
          bedrooms: form.bedrooms ? parseInt(form.bedrooms, 10) : null,
          budget: form.budget ? parseFloat(form.budget) * 1_000_000 : null,
          note: form.note.trim() || null,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Có lỗi xảy ra');
      setResult(data as PublicQuote);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không kết nối được — thử lại sau');
    } finally {
      setLoading(false);
    }
  }, [form]);

  const inputCls = 'w-full px-4 py-3 rounded-xl bg-white/5 border border-white/15 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#C9A96E]';

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(160deg, #0D1117 0%, #131A24 60%, #1A2530 100%)' }}>
      <div className="max-w-2xl mx-auto px-5 py-12">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="text-5xl mb-3">🏠</div>
          <h1 className="text-3xl font-bold text-white mb-2">
            JAMA <span style={{ color: '#C9A96E' }}>HOME</span>
          </h1>
          <p className="text-lg text-white/80 font-medium">Báo giá nội thất trong 30 giây</p>
          <p className="text-sm text-white/50 mt-2">
            Nhập thông tin căn nhà — nhận ngay khoảng chi phí 3 phương án, kèm lịch khảo sát MIỄN PHÍ
          </p>
        </div>

        {!result ? (
          <div className="rounded-2xl p-6 sm:p-8" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <input placeholder="Họ tên *" value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className={inputCls} />
              <input placeholder="Số điện thoại *" value={form.phone}
                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className={inputCls} />
              <input type="number" placeholder="Diện tích (m²) *" value={form.area}
                onChange={e => setForm(f => ({ ...f, area: e.target.value }))} className={inputCls} />
              <select value={form.ptype} onChange={e => setForm(f => ({ ...f, ptype: e.target.value }))} className={inputCls}>
                {PROPERTY_TYPES.map(t => <option key={t.value} value={t.value} style={{ background: '#131A24' }}>{t.label}</option>)}
              </select>
              <input type="number" placeholder="Số phòng ngủ (nếu có)" value={form.bedrooms}
                onChange={e => setForm(f => ({ ...f, bedrooms: e.target.value }))} className={inputCls} />
              <input type="number" placeholder="Ngân sách dự kiến (triệu)" value={form.budget}
                onChange={e => setForm(f => ({ ...f, budget: e.target.value }))} className={inputCls} />
            </div>
            <textarea placeholder="Mô tả thêm (phong cách yêu thích, yêu cầu đặc biệt...)" rows={2} value={form.note}
              onChange={e => setForm(f => ({ ...f, note: e.target.value }))} className={`${inputCls} mt-4`} />

            {error && <p className="text-sm mt-3" style={{ color: '#F85149' }}>❌ {error}</p>}

            <button
              onClick={submit}
              disabled={loading}
              className="w-full mt-5 py-3.5 rounded-xl text-base font-bold transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: '#C9A96E', color: '#12100B' }}
            >
              {loading ? '⏳ Đang tính toán...' : '⚡ Nhận báo giá ngay'}
            </button>
            <p className="text-xs text-white/40 text-center mt-3">
              Miễn phí · Không ràng buộc · JAMA HOME liên hệ tư vấn trong 24h
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-2xl p-6 text-center" style={{ background: 'rgba(201,169,110,0.1)', border: '1px solid rgba(201,169,110,0.35)' }}>
              <p className="text-white/80 text-sm">
                📐 {result.area_sqm}m² · {PROPERTY_TYPES.find(t => t.value === result.property_type)?.label}
                {result.bedrooms ? ` · ${result.bedrooms} phòng ngủ` : ''}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {(['basic', 'standard', 'premium'] as const).map(tier => {
                const t = result.tiers[tier];
                const suggested = result.suggested_tier === tier;
                return (
                  <div
                    key={tier}
                    className="rounded-2xl p-5 text-center"
                    style={{
                      background: suggested ? 'rgba(201,169,110,0.12)' : 'rgba(255,255,255,0.04)',
                      border: suggested ? '2px solid #C9A96E' : '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    {suggested && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-bold" style={{ background: '#C9A96E', color: '#12100B' }}>
                        PHÙ HỢP VỚI BẠN
                      </span>
                    )}
                    <p className="text-white font-semibold mt-2">{t.label}</p>
                    <p className="text-lg font-bold mt-1" style={{ color: '#C9A96E' }}>
                      {fmtVND(t.range_low)} – {fmtVND(t.range_high)}
                    </p>
                    <p className="text-xs text-white/40 mt-1">≈ {(t.per_sqm / 1_000_000).toFixed(1)} triệu/m²</p>
                  </div>
                );
              })}
            </div>

            <div className="rounded-2xl p-6 text-center" style={{ background: 'rgba(63,185,80,0.1)', border: '1px solid rgba(63,185,80,0.3)' }}>
              <p className="text-white font-semibold">✅ {result.message}</p>
              <p className="text-xs text-white/50 mt-2">{result.disclaimer}</p>
            </div>

            <button
              onClick={() => setResult(null)}
              className="w-full py-3 rounded-xl text-sm text-white/70 hover:text-white"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              ← Báo giá căn khác
            </button>
          </div>
        )}

        <p className="text-center text-xs text-white/30 mt-10">
          © JAMA HOME — Thiết kế & thi công nội thất trọn gói TP.HCM
        </p>
      </div>
    </div>
  );
}
