'use client';

// Sửa ca quên chấm của nhân viên (quản lý team / BGĐ / Kế toán) + lịch nghỉ lễ được tính công (27/10/2026)

import { useCallback, useEffect, useState } from 'react';
import { api, AttendanceRecord } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

const o = { background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' };

function gioVN(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });
}

/** "2026-10-27" + "08:05" giờ VN → ISO UTC */
function isoVN(ngay: string, gio: string): string | undefined {
  if (!gio) return undefined;
  return new Date(`${ngay}T${gio}:00+07:00`).toISOString();
}

export function SuaCongNhanVien({ userId, ten, period, onClose, onSaved }: {
  userId: string; ten: string; period: string; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [ds, setDs] = useState<AttendanceRecord[]>([]);
  const [sua, setSua] = useState<{ id: string; ngay: string; vao: string; ra: string; note: string } | null>(null);
  const [luu, setLuu] = useState(false);

  const tai = useCallback(async () => {
    try { setDs((await api.myAttendance(period, userId)).records); }
    catch (e) { toast(e instanceof Error ? e.message : 'Không tải được công', 'error'); }
  }, [period, userId, toast]);
  useEffect(() => { tai(); }, [tai]);

  const ghi = async () => {
    if (!sua || luu) return;
    if (sua.note.trim().length < 3) { toast('Ghi lý do sửa (ít nhất 3 ký tự)', 'error'); return; }
    setLuu(true);
    try {
      await api.editAttendance(sua.id, { check_in: isoVN(sua.ngay, sua.vao), check_out: isoVN(sua.ngay, sua.ra), note: sua.note.trim() });
      toast('Đã sửa công', 'success'); setSua(null); tai(); onSaved();
    } catch (e) { toast(e instanceof Error ? e.message : 'Sửa thất bại', 'error'); } finally { setLuu(false); }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[6vh] px-3" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div className="relative w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Công của {ten}</h3>
          <button onClick={onClose} className="text-sm" style={{ color: 'var(--text-muted)' }}>Đóng</button>
        </div>
        {ds.length === 0 && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Chưa có ngày công nào trong kỳ.</p>}
        <div className="space-y-2">
          {ds.map(r => (
            <div key={r.id} className="rounded-xl p-3" style={{ background: 'var(--surface-1)', border: `1px solid ${r.needs_review ? '#fbbf24' : 'var(--border-subtle)'}` }}>
              <div className="flex items-center justify-between text-sm">
                <span style={{ color: 'var(--text-primary)' }}>{new Date(r.work_date).toLocaleDateString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' })}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{gioVN(r.check_in) || '—'} → {gioVN(r.check_out) || '—'} · {r.work_hours}h</span>
                {sua?.id !== r.id && (
                  <button className="text-xs px-3 py-1 rounded-full" style={{ border: '1px solid var(--border-subtle)', color: 'var(--gold-400)' }}
                    onClick={() => setSua({ id: r.id, ngay: r.work_date.slice(0, 10), vao: gioVN(r.check_in), ra: gioVN(r.check_out), note: '' })}>Sửa</button>
                )}
              </div>
              {sua?.id === r.id && (
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <label className="text-xs" style={{ color: 'var(--text-muted)' }}>Giờ vào
                    <input type="time" className="w-full mt-1 px-2 py-1.5 rounded-lg text-sm" style={o} value={sua.vao} onChange={e => setSua({ ...sua, vao: e.target.value })} /></label>
                  <label className="text-xs" style={{ color: 'var(--text-muted)' }}>Giờ ra
                    <input type="time" className="w-full mt-1 px-2 py-1.5 rounded-lg text-sm" style={o} value={sua.ra} onChange={e => setSua({ ...sua, ra: e.target.value })} /></label>
                  <input className="col-span-2 px-2 py-1.5 rounded-lg text-sm" style={o} placeholder="Lý do sửa (bắt buộc) — VD: quên chấm ra, có xác nhận của TP"
                    value={sua.note} onChange={e => setSua({ ...sua, note: e.target.value })} />
                  <div className="col-span-2 flex justify-end gap-2">
                    <button className="text-xs px-3 py-1.5" style={{ color: 'var(--text-muted)' }} onClick={() => setSua(null)}>Huỷ</button>
                    <button className="text-xs px-3 py-1.5 rounded-full font-medium disabled:opacity-50" disabled={luu} onClick={ghi}
                      style={{ background: 'var(--gold-400)', color: '#000' }}>{luu ? 'Đang lưu…' : 'Lưu'}</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function LichNgayLe() {
  const { toast } = useToast();
  const [data, setData] = useState<{ nam: number; mac_dinh: string[]; them: string[] } | null>(null);
  const [moi, setMoi] = useState('');

  const tai = useCallback(async () => {
    try { setData(await api.ngayLe()); } catch { /* không có quyền xem thì thôi */ }
  }, []);
  useEffect(() => { tai(); }, [tai]);

  const luu = async (them: string[]) => {
    try { await api.luuNgayLe(them); toast('Đã lưu lịch nghỉ lễ', 'success'); tai(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lưu thất bại', 'error'); }
  };
  if (!data) return null;
  const vn = (d: string) => new Date(d).toLocaleDateString('vi-VN');

  return (
    <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-subtle)' }}>
      <div className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Lịch nghỉ lễ {data.nam} (được tính công)</div>
      <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>Lễ dương lịch có sẵn. Thêm Tết âm lịch, Giỗ Tổ, ngày nghỉ bù theo thông báo của Nhà nước. Ngày lễ không trừ phép.</p>
      <div className="flex flex-wrap gap-2 mb-3">
        {data.mac_dinh.map(d => <span key={d} className="text-xs px-2 py-1 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>{vn(d)}</span>)}
        {data.them.map(d => (
          <span key={d} className="text-xs px-2 py-1 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--gold-400)' }}>
            {vn(d)} <button className="ml-1" onClick={() => luu(data.them.filter(x => x !== d))}>✕</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input type="date" className="px-2 py-1.5 rounded-lg text-sm" style={o} value={moi} onChange={e => setMoi(e.target.value)} />
        <button className="text-xs px-3 py-1.5 rounded-full font-medium disabled:opacity-50" disabled={!moi}
          style={{ background: 'var(--gold-400)', color: '#000' }} onClick={() => { luu([...data.them, moi]); setMoi(''); }}>Thêm ngày lễ</button>
      </div>
    </div>
  );
}
