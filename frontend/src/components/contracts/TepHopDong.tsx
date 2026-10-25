'use client';

import { useEffect, useRef, useState } from 'react';
import { api, ContractFile } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';

const NHAN_TEP = '.pdf,.doc,.docx,.jpg,.jpeg,.png';

function coTep(b: number) {
  return b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
}

/** Tệp HĐ đã ký (PDF/Word/ảnh scan) trong cửa sổ chi tiết hợp đồng. */
export default function TepHopDong({ contractId, choTaiLen, laQuanLy, userId }: {
  contractId: string; choTaiLen: boolean; laQuanLy: boolean; userId?: string;
}) {
  const { toast } = useToast();
  const [items, setItems] = useState<ContractFile[]>([]);
  const [dangTai, setDangTai] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let huy = false;
    api.listContractFiles(contractId).then(r => { if (!huy) setItems(r.items); }).catch(() => {});
    return () => { huy = true; };
  }, [contractId]);

  const taiLen = async (ds: FileList | null) => {
    if (!ds?.length) return;
    setDangTai(true);
    try {
      const r = await api.uploadContractFiles(contractId, Array.from(ds));
      setItems(prev => [...r.items, ...prev]);
      toast(`Đã đính kèm ${r.items.length} tệp`, 'success');
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Tải tệp lên thất bại', 'error');
    } finally {
      setDangTai(false);
      if (input.current) input.current.value = '';
    }
  };

  const mo = (f: ContractFile, xem: boolean) =>
    api.openContractFile(contractId, f, xem).catch(() => toast('Không mở được tệp', 'error'));

  const go = async (f: ContractFile) => {
    if (!confirm(`Gỡ tệp «${f.filename}» khỏi hợp đồng?`)) return;
    try {
      await api.removeContractFile(contractId, f.id);
      setItems(prev => prev.filter(x => x.id !== f.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Không gỡ được tệp', 'error');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Tệp hợp đồng đã ký</h3>
        {choTaiLen && (
          <>
            <input ref={input} type="file" multiple accept={NHAN_TEP} className="hidden"
              onChange={e => taiLen(e.target.files)} />
            <button type="button" disabled={dangTai} onClick={() => input.current?.click()}
              className="btn-primary inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold disabled:opacity-60">
              <LineIcon name="upload" size={14} color="currentColor" />
              {dangTai ? 'Đang tải…' : 'Đính kèm HĐ đã ký'}
            </button>
          </>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">Chưa có tệp. Nhận PDF, Word, ảnh scan (tối đa 40MB/tệp).</p>
      ) : (
        <ul className="space-y-2">
          {items.map(f => (
            <li key={f.id} className="glass-card flex flex-wrap items-center gap-2 p-3 rounded-xl">
              <LineIcon name="file" size={18} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-[var(--text-primary)] truncate">{f.filename}</p>
                <p className="text-[11px] text-[var(--text-muted)]">
                  {coTep(f.size_bytes)}
                  {f.uploaded_by_name ? ` · ${f.uploaded_by_name}` : ''}
                  {f.created_at ? ` · ${new Date(f.created_at).toLocaleDateString('vi-VN')}` : ''}
                </p>
              </div>
              <div className="flex gap-1">
                <button type="button" onClick={() => mo(f, true)} title="Xem"
                  className="inline-flex items-center gap-1 px-3 py-2 rounded-full text-xs border border-[var(--border)] text-[var(--text-secondary)]">
                  <LineIcon name="eye" size={14} /> Xem
                </button>
                <button type="button" onClick={() => mo(f, false)} title="Tải về"
                  className="inline-flex items-center gap-1 px-3 py-2 rounded-full text-xs border border-[var(--border)] text-[var(--text-secondary)]">
                  <LineIcon name="download" size={14} /> Tải
                </button>
                {(laQuanLy || (userId && f.uploaded_by === userId)) && (
                  <button type="button" onClick={() => go(f)} title="Gỡ tệp"
                    className="inline-flex items-center px-2.5 py-2 rounded-full text-xs border border-[var(--border)] text-red-400">
                    <LineIcon name="trash" size={14} />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
