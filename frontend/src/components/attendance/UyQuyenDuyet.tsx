'use client';

// Ủy quyền duyệt khi vắng — dùng ở /approvals (nút + dải trạng thái) và sau khi gửi đơn nghỉ (gợi ý điền sẵn).
// Server quyết định ai được ủy quyền / được nhận (GET /approvals/delegate); ở đây chỉ chọn và bấm xác nhận.

import { useCallback, useEffect, useState } from 'react';
import { api, ApprovalDelegateInfo } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';
import { ROLE_LABELS, labelOf } from '@/lib/labels';

/** Ngày theo giờ VN, lệch `offset` ngày so với hôm nay → "YYYY-MM-DD" */
export const ngayVN = (offset = 0) =>
  new Date(Date.now() + offset * 86_400_000).toLocaleDateString('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' });
/** Hết ngày (23:59 giờ VN) → ISO UTC */
const hetNgay = (ngay: string) => new Date(`${ngay}T23:59:00+07:00`).toISOString();
const hienHan = (iso: string) =>
  new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });

const HAN = [
  { label: 'Hết hôm nay', offset: 0 },
  { label: '3 ngày', offset: 2 },
  { label: '7 ngày', offset: 6 },
];

/** `denNgay` ("YYYY-MM-DD"): chế độ gợi ý sau khi gửi đơn nghỉ — hạn điền sẵn tới hết ngày đó. */
export function UyQuyenDuyet({ denNgay, onDong }: { denNgay?: string; onDong?: () => void }) {
  const { toast } = useToast();
  const [info, setInfo] = useState<ApprovalDelegateInfo | null>(null);
  const [mo, setMo] = useState(false);
  const [nguoi, setNguoi] = useState('');
  const [busy, setBusy] = useState(false);

  const tai = useCallback(async () => {
    try { setInfo(await api.getApprovalDelegate()); } catch { setInfo(null); }
  }, []);
  useEffect(() => { void Promise.resolve().then(tai); }, [tai]);

  if (!info?.can_delegate) return null;

  const dat = async (delegateTo: string | null, ngay?: string) => {
    if (busy) return;
    if (delegateTo === '') { toast('Chọn người nhận ủy quyền', 'error'); return; }
    setBusy(true);
    try {
      await api.setApprovalDelegate(delegateTo, ngay ? hetNgay(ngay) : undefined);
      toast(delegateTo ? 'Đã ủy quyền — người nhận được báo qua thông báo' : 'Đã tắt ủy quyền', 'success');
      setMo(false);
      await tai();
      if (denNgay) onDong?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không đặt được ủy quyền', 'error');
    } finally { setBusy(false); }
  };

  const chonNguoi = (
    <select value={nguoi} onChange={e => setNguoi(e.target.value)}
      className="w-full px-3 py-2 rounded-lg border text-sm"
      style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}>
      <option value="">— Chọn người duyệt thay —</option>
      {info.candidates.map(c => <option key={c.id} value={c.id}>{c.full_name} · {labelOf(ROLE_LABELS, c.role)}</option>)}
    </select>
  );
  const luuY = (
    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
      Người nhận duyệt thay <b>mọi loại đơn</b> đang chờ bạn, gồm cả tạm ứng và bảng lương. Hết hạn tự tắt; tắt sớm bất cứ lúc nào ở trang Phê duyệt.
    </p>
  );
  const hop = { background: 'var(--surface-2)', borderColor: 'var(--border-subtle)' };

  // Gợi ý sau khi gửi đơn nghỉ
  if (denNgay) {
    if (info.candidates.length === 0) return null;
    return (
      <div className="rounded-2xl p-4 border space-y-3" style={hop}>
        <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          <LineIcon name="users" size={16} className="inline-block align-[-2px] mr-1.5" />
          Ủy quyền duyệt đơn của team đến hết {denNgay.slice(8, 10)}/{denNgay.slice(5, 7)}?
        </div>
        {info.delegate_to && info.until && (
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Đang ủy quyền cho {info.delegate_name} đến {hienHan(info.until)} — xác nhận sẽ thay bằng lựa chọn mới.</p>
        )}
        {chonNguoi}
        {luuY}
        <div className="flex gap-2">
          <button disabled={busy} onClick={() => dat(nguoi, denNgay)} className="px-4 rounded-full text-sm font-semibold disabled:opacity-40"
            style={{ background: 'var(--gold-400)', color: '#000', minHeight: 44 }}>Xác nhận ủy quyền</button>
          <button onClick={onDong} className="px-4 rounded-full text-sm border" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)', minHeight: 44 }}>Không cần</button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 space-y-3">
      {info.delegate_to && info.until ? (
        <div className="rounded-2xl p-3 border flex flex-wrap items-center justify-between gap-2 text-sm" style={hop}>
          <span style={{ color: 'var(--text-primary)' }}>
            <LineIcon name="users" size={16} className="inline-block align-[-2px] mr-1.5" />
            Đang ủy quyền duyệt cho <b>{info.delegate_name}</b> đến {hienHan(info.until)}
          </span>
          <button disabled={busy} onClick={() => dat(null)} className="px-3 py-1.5 rounded-full text-sm border disabled:opacity-40"
            style={{ borderColor: 'var(--border-subtle)', color: '#f87171' }}>Tắt ủy quyền</button>
        </div>
      ) : (
        <button onClick={() => setMo(v => !v)} className="px-3 py-1.5 rounded-full text-sm border"
          style={{ borderColor: 'var(--border-subtle)', color: 'var(--gold-400)' }}>
          <LineIcon name="users" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Ủy quyền khi vắng
        </button>
      )}
      {mo && !info.delegate_to && (
        <div className="rounded-2xl p-4 border space-y-3" style={hop}>
          {info.candidates.length === 0
            ? <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có ai khác có vai trò duyệt để nhận ủy quyền.</p>
            : <>
              {chonNguoi}
              {luuY}
              <div className="flex flex-wrap gap-2">
                {HAN.map(h => (
                  <button key={h.label} disabled={busy} onClick={() => dat(nguoi, ngayVN(h.offset))}
                    className="px-4 rounded-full text-sm font-semibold disabled:opacity-40" style={{ background: 'var(--gold-400)', color: '#000', minHeight: 44 }}>
                    {h.label}
                  </button>
                ))}
              </div>
            </>}
        </div>
      )}
    </div>
  );
}
