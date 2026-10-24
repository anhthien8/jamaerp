'use client';

/**
 * Nhập danh sách nhân sự từ Excel của HCNS (24/10/2026). Hai bước: chọn file →
 * xem trước (khớp ai, đổi ô nào, ai không khớp) → bấm «Áp dụng». Không tạo tài
 * khoản mới; người không khớp tên cần sửa tên tài khoản rồi nhập lại.
 * Màn này không hiện giá trị lương/CCCD — chỉ tên ô sẽ đổi.
 */

import { useState } from 'react';
import { api, type KetQuaNhapNhanSu } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';
import { deptLabel } from '@/lib/nhan-su';

export default function NhapExcelNhanSu({ onClose, onDone }: { onClose: () => void; onDone?: () => void }) {
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [kq, setKq] = useState<KetQuaNhapNhanSu | null>(null);
  const [dang, setDang] = useState(false);

  const gui = async (apply: boolean) => {
    if (!file) return;
    setDang(true);
    try {
      const r = await api.importEmployeesExcel(file, apply);
      setKq(r);
      if (apply) {
        toast(`Đã cập nhật hồ sơ ${r.se_cap_nhat} người`, 'success');
        onDone?.();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Nhập file thất bại', 'error');
    } finally {
      setDang(false);
    }
  };

  const chonFile = (f: File | null) => {
    setFile(f);
    setKq(null);
  };

  const doi = kq?.khop.filter(k => k.o_thay_doi.length) ?? [];

  return (
    <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center sm:px-4 bg-black/60" onClick={onClose}>
      <div
        className="w-full sm:max-w-lg max-h-[88vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl p-4 sm:p-5"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-[var(--text-primary)]">Nhập Excel nhân sự</h3>
          <button onClick={onClose} className="p-2 rounded-lg min-h-[40px]" aria-label="Đóng">
            <LineIcon name="x" size={18} />
          </button>
        </div>
        <p className="text-xs text-[var(--text-muted)] mb-3">
          Dùng file danh sách nhân sự của HCNS (.xlsx, có cột «HỌ VÀ TÊN»). Hệ thống khớp theo họ tên, điền CCCD,
          MST, BHXH, ngày ký HĐLĐ, lương HĐ và lương đóng BHXH vào Hồ sơ 360°. Ô trống trong file giữ nguyên dữ liệu cũ.
        </p>

        <label className="flex items-center gap-3 p-3 rounded-xl cursor-pointer min-h-[52px]"
          style={{ background: 'var(--surface-2)', border: '1px dashed var(--border-subtle)' }}>
          <LineIcon name="upload" size={18} color="var(--gold-400)" />
          <span className="text-sm text-[var(--text-secondary)] truncate">{file ? file.name : 'Chọn file Excel…'}</span>
          <input type="file" accept=".xlsx" className="hidden" onChange={e => chonFile(e.target.files?.[0] ?? null)} />
        </label>

        {!kq && (
          <button onClick={() => void gui(false)} disabled={!file || dang}
            className="w-full mt-3 py-2.5 rounded-full text-sm font-semibold disabled:opacity-40 min-h-[44px]"
            style={{ background: 'var(--gold-500)', color: '#000' }}>
            {dang ? 'Đang đọc…' : 'Xem trước'}
          </button>
        )}

        {kq && (
          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                ['Dòng trong file', kq.tong_dong],
                ['Khớp tài khoản', kq.khop.length],
                [kq.da_ap_dung ? 'Đã cập nhật' : 'Sẽ cập nhật', kq.se_cap_nhat],
              ].map(([nhan, so]) => (
                <div key={nhan as string} className="p-2 rounded-xl" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-lg font-bold text-[var(--text-primary)]">{so}</p>
                  <p className="text-[10px] text-[var(--text-muted)]">{nhan}</p>
                </div>
              ))}
            </div>

            {doi.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-[var(--text-secondary)] mb-1.5">{kq.da_ap_dung ? 'Đã cập nhật' : 'Sẽ cập nhật'}</p>
                <div className="space-y-1">
                  {doi.map(k => (
                    <div key={k.user_id} className="p-2 rounded-lg text-xs" style={{ background: 'var(--surface-2)' }}>
                      <span className="font-medium text-[var(--text-primary)]">{k.ten}</span>
                      <span className="text-[var(--text-muted)]"> · {deptLabel(k.phong_ban)}</span>
                      <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{k.o_thay_doi.join(', ')}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(kq.khong_khop.length > 0 || kq.trung_ten.length > 0) && (
              <div className="p-3 rounded-xl" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
                <p className="text-xs font-semibold text-amber-400 mb-1">
                  <LineIcon name="alert" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />
                  Chưa nhập được {kq.khong_khop.length + kq.trung_ten.length} người
                </p>
                <p className="text-[10px] text-[var(--text-muted)] mb-1.5">Sửa họ tên tài khoản cho khớp file (hoặc tạo tài khoản) rồi nhập lại.</p>
                <ul className="text-xs text-[var(--text-secondary)] space-y-0.5">
                  {kq.khong_khop.map((k, i) => <li key={`k${i}`}>{k.ten}{k.phong_ban ? ` · ${k.phong_ban}` : ''} — chưa có tài khoản</li>)}
                  {kq.trung_ten.map((k, i) => <li key={`t${i}`}>{k.ten} — trùng tên {k.so_tai_khoan} tài khoản</li>)}
                </ul>
              </div>
            )}

            {!kq.da_ap_dung ? (
              <div className="flex gap-2">
                <button onClick={() => chonFile(null)} className="flex-1 py-2.5 rounded-full text-sm min-h-[44px]"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>Chọn file khác</button>
                <button onClick={() => void gui(true)} disabled={dang || kq.se_cap_nhat === 0}
                  className="flex-1 py-2.5 rounded-full text-sm font-semibold disabled:opacity-40 min-h-[44px]"
                  style={{ background: 'var(--gold-500)', color: '#000' }}>
                  {dang ? 'Đang lưu…' : `Áp dụng (${kq.se_cap_nhat})`}
                </button>
              </div>
            ) : (
              <button onClick={onClose} className="w-full py-2.5 rounded-full text-sm font-semibold min-h-[44px]"
                style={{ background: 'var(--gold-500)', color: '#000' }}>Xong</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
