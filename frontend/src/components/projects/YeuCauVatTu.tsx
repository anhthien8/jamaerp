'use client';

import type { Dispatch, SetStateAction } from 'react';
import LineIcon from '@/components/ui/LineIcon';
import type { Material } from '@/lib/api';

/** Modal yêu cầu vật tư. */
export default function YeuCauVatTu({
  setShowMaterialRequest,
  materialRequestForm,
  setMaterialRequestForm,
  materialsList,
  handleSubmitMaterialRequest,
  savingMaterialRequest,
}: {
  setShowMaterialRequest: Dispatch<SetStateAction<boolean>>;
  materialRequestForm: { material_id: string; quantity: string; note: string; };
  setMaterialRequestForm: Dispatch<SetStateAction<{ material_id: string; quantity: string; note: string; }>>;
  materialsList: Material[];
  handleSubmitMaterialRequest: () => Promise<void>;
  savingMaterialRequest: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={() => setShowMaterialRequest(false)}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-2xl animate-in p-6"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-white"><LineIcon name="package" size={16} className="inline-block align-[-2px] mr-1.5" />Yêu cầu vật tư</h2>
          <button onClick={() => setShowMaterialRequest(false)} className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-muted)]">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Vật tư *</label>
            <select
              value={materialRequestForm.material_id}
              onChange={e => setMaterialRequestForm(f => ({ ...f, material_id: e.target.value }))}
              className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none cursor-pointer"
            >
              <option value="">-- Chọn vật tư --</option>
              {materialsList.map(m => (
                <option key={m.id} value={m.id}>{m.name} ({m.unit} - tồn: {m.quantity_in_stock})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Số lượng *</label>
            <input
              type="number"
              min="1"
              value={materialRequestForm.quantity}
              onChange={e => setMaterialRequestForm(f => ({ ...f, quantity: e.target.value }))}
              className="w-full px-3 py-2 rounded-xl text-sm text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
              placeholder="Nhập số lượng"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)] block mb-1">Ghi chú</label>
            <textarea
              value={materialRequestForm.note}
              onChange={e => setMaterialRequestForm(f => ({ ...f, note: e.target.value }))}
              rows={2}
              className="w-full px-3 py-2 rounded-xl text-sm text-white resize-none bg-[var(--surface-2)] border border-[var(--border-subtle)] outline-none focus:border-[var(--gold-500)]"
              placeholder="Ghi chú (không bắt buộc)"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setShowMaterialRequest(false)}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-white/10 border border-[var(--border-subtle)]"
            >
              Hủy
            </button>
            <button
              onClick={handleSubmitMaterialRequest}
              disabled={savingMaterialRequest || !materialRequestForm.material_id || !materialRequestForm.quantity}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-[#10B981] text-white hover:bg-[#059669] disabled:opacity-50 transition-all"
            >
              {savingMaterialRequest ? 'Đang gửi...' : 'Gửi yêu cầu'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
