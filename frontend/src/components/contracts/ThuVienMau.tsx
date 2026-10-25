'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ContractTemplate, NhomMau } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';

const NHOM: { key: NhomMau; label: string; icon: string }[] = [
  { key: 'hop_dong', label: 'Hợp đồng', icon: 'file' },
  { key: 'phu_luc', label: 'Phụ lục', icon: 'layers' },
  { key: 'bien_ban', label: 'Biên bản', icon: 'clipboard' },
  { key: 'thanh_toan', label: 'Thanh toán', icon: 'receipt' },
  { key: 'khac', label: 'Khác', icon: 'inbox' },
];
const LOAI_HD: Record<string, string> = { thiet_ke: 'Thiết kế', thi_cong: 'Thi công' };

function kichCo(b: number) {
  if (b >= 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
  return `${Math.max(1, Math.round(b / 1024))} KB`;
}
function duoi(ten: string) {
  return (ten.split('.').pop() || '').toUpperCase();
}
function ngay(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/** Thư viện mẫu hợp đồng / biên bản — tab trong trang Hợp đồng (25/10/2026). */
export default function ThuVienMau() {
  const { toast } = useToast();
  const [items, setItems] = useState<ContractTemplate[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [dangTai, setDangTai] = useState(true);
  const [hienAn, setHienAn] = useState(false);
  const [dangGui, setDangGui] = useState('');
  const [dangTaiVe, setDangTaiVe] = useState<string | null>(null);
  const [sua, setSua] = useState<{ id: string; name: string; category: NhomMau; contract_kind: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (an: boolean) => {
    try {
      const r = await api.getContractTemplates(an);
      setItems(r.items);
      setCanManage(r.can_manage);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không tải được thư viện mẫu', 'error');
    } finally {
      setDangTai(false);
    }
  }, [toast]);

  useEffect(() => { void Promise.resolve().then(() => load(hienAn)); }, [load, hienAn]);

  const taiLen = async (ds: FileList | null) => {
    if (!ds || ds.length === 0) return;
    const files = Array.from(ds);
    const tong = files.reduce((s, f) => s + f.size, 0);
    setDangGui(`Đang tải ${files.length} tệp (${kichCo(tong)})`);
    try {
      const r = await api.uploadContractTemplates(files);
      const phan = [r.created && `thêm ${r.created} mẫu mới`, r.replaced && `thay bản mới cho ${r.replaced} mẫu`].filter(Boolean);
      toast(`Đã ${phan.join(', ')}`, 'success');
      await load(hienAn);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Tải mẫu lên thất bại', 'error');
    } finally {
      setDangGui('');
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const taiVe = async (m: ContractTemplate) => {
    setDangTaiVe(m.id);
    try {
      await api.downloadContractTemplate(m);
    } catch {
      toast('Tải mẫu về thất bại', 'error');
    } finally {
      setDangTaiVe(null);
    }
  };

  const capNhat = async (id: string, data: Parameters<typeof api.updateContractTemplate>[1], baoTin: string) => {
    try {
      const m = await api.updateContractTemplate(id, data);
      setItems(prev => (!hienAn && !m.is_active ? prev.filter(x => x.id !== id) : prev.map(x => (x.id === id ? m : x))));
      toast(baoTin, 'success');
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lưu thất bại', 'error');
      return false;
    }
  };

  const luuSua = async () => {
    if (!sua || !sua.name.trim()) return;
    const ok = await capNhat(sua.id, { name: sua.name.trim(), category: sua.category, contract_kind: sua.contract_kind }, 'Đã lưu mẫu');
    if (ok) setSua(null);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[var(--text-primary)]">Mẫu hợp đồng, phụ lục, biên bản, thanh toán</p>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Luôn tải bản mới nhất ở đây trước khi soạn cho khách — không dùng bản cũ lưu trong máy.
          </p>
        </div>
        {canManage && (
          <div className="flex items-center gap-2 flex-wrap">
            <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer select-none">
              <input type="checkbox" checked={hienAn} onChange={e => setHienAn(e.target.checked)} />
              Hiện mẫu đã ẩn
            </label>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".doc,.docx,.xls,.xlsx,.pdf"
              className="hidden"
              onChange={e => void taiLen(e.target.files)}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={!!dangGui}
              className="px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2 disabled:opacity-60"
              style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: 'white' }}
            >
              <LineIcon name="upload" size={16} color="currentColor" />
              {dangGui ? `${dangGui}…` : 'Tải mẫu lên'}
            </button>
          </div>
        )}
      </div>

      {dangTai ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl p-10 text-center" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          <LineIcon name="file" size={36} className="block mx-auto mb-3" />
          <p className="text-sm text-[var(--text-primary)] font-medium">Chưa có mẫu nào</p>
          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
            {canManage
              ? 'Bấm «Tải mẫu lên» rồi chọn cùng lúc tất cả tệp Word/Excel mẫu — app tự xếp vào Hợp đồng, Phụ lục, Biên bản, Thanh toán theo tên tệp.'
              : 'Nhờ Kế toán hoặc Ban giám đốc tải bộ mẫu lên.'}
          </p>
        </div>
      ) : (
        NHOM.map(n => {
          const ds = items.filter(m => m.category === n.key);
          if (ds.length === 0) return null;
          return (
            <section key={n.key} className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)] px-1">
                <LineIcon name={n.icon} size={16} />
                {n.label}
                <span className="text-xs font-normal text-[var(--text-muted)]">({ds.length})</span>
              </h3>
              <div className="grid gap-2 md:grid-cols-2">
                {ds.map(m => (
                  <div
                    key={m.id}
                    className="rounded-2xl p-3.5 flex items-start gap-3"
                    style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', opacity: m.is_active ? 1 : 0.55 }}
                  >
                    <span
                      className="shrink-0 w-11 h-11 rounded-xl flex items-center justify-center text-[10px] font-bold"
                      style={{ background: 'var(--surface-2)', color: 'var(--gold-500)' }}
                    >
                      {duoi(m.filename)}
                    </span>
                    <div className="flex-1 min-w-0">
                      {sua?.id === m.id ? (
                        <div className="space-y-2">
                          <input
                            value={sua.name}
                            onChange={e => setSua({ ...sua, name: e.target.value })}
                            className="w-full px-3 py-2 rounded-xl text-sm"
                            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                          />
                          <div className="flex gap-2">
                            <select
                              value={sua.category}
                              onChange={e => setSua({ ...sua, category: e.target.value as NhomMau })}
                              className="flex-1 px-2 py-2 rounded-xl text-sm"
                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                            >
                              {NHOM.map(x => <option key={x.key} value={x.key}>{x.label}</option>)}
                            </select>
                            <select
                              value={sua.contract_kind}
                              onChange={e => setSua({ ...sua, contract_kind: e.target.value })}
                              className="flex-1 px-2 py-2 rounded-xl text-sm"
                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                            >
                              <option value="">Không gắn loại HĐ</option>
                              <option value="thiet_ke">Thiết kế</option>
                              <option value="thi_cong">Thi công</option>
                            </select>
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => void luuSua()} className="px-3 py-1.5 rounded-full text-xs font-semibold" style={{ background: 'var(--gold-500)', color: 'white' }}>Lưu</button>
                            <button onClick={() => setSua(null)} className="px-3 py-1.5 rounded-full text-xs" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>Hủy</button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <p className="text-sm font-medium text-[var(--text-primary)] break-words">
                            {m.name}
                            {m.contract_kind && (
                              <span className="ml-2 align-middle text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                                {LOAI_HD[m.contract_kind]}
                              </span>
                            )}
                            {!m.is_active && <span className="ml-2 text-[10px] text-[var(--text-muted)]">(đã ẩn)</span>}
                          </p>
                          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                            {kichCo(m.size_bytes)} · bản {m.version}
                            {m.updated_at && ` · ${ngay(m.updated_at)}`}
                            {m.updated_by_name && ` · ${m.updated_by_name}`}
                          </p>
                          {canManage && (
                            <div className="flex gap-3 mt-1.5 text-[11px]">
                              <button
                                className="text-[var(--text-secondary)] hover:text-[var(--gold-500)]"
                                onClick={() => setSua({ id: m.id, name: m.name, category: m.category, contract_kind: m.contract_kind || '' })}
                              >
                                Sửa tên/nhóm
                              </button>
                              <button
                                className="text-[var(--text-secondary)] hover:text-[var(--gold-500)]"
                                onClick={() => void capNhat(m.id, { is_active: !m.is_active }, m.is_active ? 'Đã ẩn mẫu' : 'Đã hiện lại mẫu')}
                              >
                                {m.is_active ? 'Ẩn' : 'Hiện lại'}
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                    {sua?.id !== m.id && (
                      <button
                        onClick={() => void taiVe(m)}
                        disabled={dangTaiVe === m.id}
                        aria-label={`Tải ${m.name}`}
                        className="shrink-0 px-3 py-2 rounded-full text-xs font-semibold flex items-center gap-1.5 disabled:opacity-60"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
                      >
                        <LineIcon name="download" size={14} />
                        {dangTaiVe === m.id ? 'Đang tải…' : 'Tải về'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>
          );
        })
      )}
      {canManage && items.length > 0 && (
        <p className="text-[11px] text-[var(--text-muted)] px-1">
          Sửa mẫu: tải bản Word mới lên với <b>cùng tên tệp</b> — app thay bản cũ và tăng số phiên bản, không tạo bản trùng.
        </p>
      )}
    </div>
  );
}
