'use client';

/**
 * Trợ lý hỏi đáp (24/11/2026) — nút tròn góc phải, bấm là hỏi cách dùng ERP.
 * Kiến thức = Sổ tay (/huong-dan, lib/huong-dan-content.ts): trình duyệt chọn vài mục
 * khớp từ khoá rồi gửi kèm câu hỏi lên /ai/hoi-dap. Sổ tay ~140KB nên chỉ tải khi mở
 * popup lần đầu. AI chưa bật/đang bận → vẫn chỉ ra các mục Sổ tay liên quan.
 * Hội thoại sống trong AppShell (layout) nên chuyển trang không mất.
 */

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { api, ApiError } from '@/lib/api';
import { chuanHoaTim } from '@/lib/utils';
import type { GuideSection, GuideBlock } from '@/lib/huong-dan-content';
import LineIcon from '@/components/ui/LineIcon';

interface TinNhan {
  role: 'user' | 'assistant';
  content: string;
  muc?: { id: string; title: string }[];
  loi?: boolean;
}

const GOI_Y = ['Tạo lead mới thế nào?', 'Quên mật khẩu thì làm sao?', 'Cách gửi báo cáo qua Telegram?'];
const TU_BO = new Set(['làm', 'sao', 'thế', 'nào', 'như', 'cho', 'của', 'và', 'là', 'có', 'không', 'được', 'tôi', 'mình', 'em', 'anh', 'chị', 'ở', 'đâu', 'gì', 'cách', 'muốn', 'cần', 'thì', 'với', 'để', 'một', 'các', 'những', 'này', 'ạ', 'nhé', 'vậy']);
const TRAN_MOI_MUC = 5000;
const TRAN_NGU_CANH = 15000;

function chuMuc(b: GuideBlock): string {
  return [b.text, ...(b.items ?? []), ...(b.header ?? []), ...(b.rows ?? []).map(r => r.join(' | '))]
    .filter(Boolean).join('\n');
}

function tachTu(s: string): string[] {
  return chuanHoaTim(s).split(/[^\p{L}\p{N}]+/u).filter(t => t.length >= 2);
}

/** Chấm điểm mục theo từ + cụm 2 từ (tiếng Việt nhiều từ ghép: «tạo lead», «báo giá»). */
function chonMuc(sections: GuideSection[], cauHoi: string) {
  const tu = tachTu(cauHoi);
  const tuKhoa = tu.filter(t => !TU_BO.has(t));
  const cum = tu.slice(1).map((t, i) => `${tu[i]} ${t}`);
  if (!tuKhoa.length) return [];
  return sections
    .map(s => {
      const tieuDe = chuanHoaTim(s.title);
      const than = chuanHoaTim(s.blocks.map(chuMuc).join('\n'));
      let diem = 0;
      for (const t of tuKhoa) {
        if (tieuDe.includes(t)) diem += 5;
        diem += Math.min(than.split(t).length - 1, 5);
      }
      for (const c of cum) {
        if (tieuDe.includes(c)) diem += 8;
        if (than.includes(c)) diem += 4;
      }
      return { s, diem };
    })
    .filter(x => x.diem > 0)
    .sort((a, b) => b.diem - a.diem)
    .slice(0, 3)
    .map(x => x.s);
}

function dungNguCanh(muc: GuideSection[]): string {
  let out = '';
  for (const s of muc) {
    const doan = `## ${s.title}\n${s.blocks.map(chuMuc).join('\n')}`.slice(0, TRAN_MOI_MUC);
    if (out.length + doan.length > TRAN_NGU_CANH) break;
    out += doan + '\n\n';
  }
  return out;
}

function dongChu(text: string): React.ReactNode {
  // Model hay trả markdown khối (> trích, # tiêu đề) — chỉ giữ **đậm** và `code`
  const gon = text.replace(/^\s*>\s?/gm, '').replace(/^\s*#{1,6}\s*/gm, '');
  return gon.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong>;
    if (p.startsWith('`') && p.endsWith('`')) return <code key={i} className="px-1 rounded bg-white/10 text-[0.85em]">{p.slice(1, -1)}</code>;
    return p;
  });
}

export default function TroLyHoiDap() {
  const [mo, setMo] = useState(false);
  const [tin, setTin] = useState<TinNhan[]>([]);
  const [nhap, setNhap] = useState('');
  const [dangHoi, setDangHoi] = useState(false);
  const soTay = useRef<GuideSection[] | null>(null);
  const cuoi = useRef<HTMLDivElement>(null);
  const oNhap = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!mo) return;
    oNhap.current?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setMo(false); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [mo]);

  useEffect(() => { cuoi.current?.scrollIntoView({ block: 'end' }); }, [tin, dangHoi]);

  async function hoi(cauHoi: string) {
    const q = cauHoi.trim();
    if (!q || dangHoi) return;
    const lichSu: TinNhan[] = [...tin.filter(t => !t.loi), { role: 'user', content: q }];
    setTin(t => [...t, { role: 'user', content: q }]);
    setNhap('');
    setDangHoi(true);
    let muc: GuideSection[] = [];
    try {
      soTay.current ??= (await import('@/lib/huong-dan-content')).GUIDE_SECTIONS;
      // Câu nối tiếp («còn trên điện thoại?») ít từ khoá → ghép thêm câu hỏi trước
      const truoc = lichSu.filter(t => t.role === 'user').slice(-2).map(t => t.content).join(' ');
      muc = chonMuc(soTay.current, q);
      if (!muc.length) muc = chonMuc(soTay.current, truoc);
      const r = await api.request<{ tra_loi: string }>('/ai/hoi-dap', {
        method: 'POST',
        body: {
          messages: lichSu.slice(-10).map(({ role, content }) => ({ role, content: content.slice(0, 2000) })),
          ngu_canh: dungNguCanh(muc),
        },
      });
      setTin(t => [...t, { role: 'assistant', content: r.tra_loi, muc: muc.map(({ id, title }) => ({ id, title })) }]);
    } catch (e) {
      const chuaBat = e instanceof ApiError && e.status === 503;
      setTin(t => [...t, {
        role: 'assistant',
        loi: true,
        content: (chuaBat ? e.message : 'Không kết nối được trợ lý.')
          + (muc.length ? ' Bạn xem thử các mục Sổ tay này:' : ' Bạn thử lại sau hoặc mở **Sổ tay**.'),
        muc: muc.map(({ id, title }) => ({ id, title })),
      }]);
    } finally {
      setDangHoi(false);
    }
  }

  return (
    <>
      {!mo && (
        <button
          type="button"
          onClick={() => setMo(true)}
          aria-label="Mở trợ lý hỏi đáp"
          title="Hỏi trợ lý JAMA"
          className="fixed z-[46] right-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] lg:right-6 lg:bottom-6 w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-105 active:scale-95"
          style={{ background: 'var(--gold-500)' }}
        >
          <LineIcon name="message" size={22} color="var(--surface-0)" />
        </button>
      )}

      {mo && (
        <div
          role="dialog"
          aria-label="Trợ lý hỏi đáp"
          className="fixed z-[60] inset-x-2 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] top-16 lg:inset-x-auto lg:top-auto lg:right-6 lg:bottom-6 lg:w-[380px] lg:h-[560px] flex flex-col rounded-2xl shadow-2xl animate-in overflow-hidden"
          style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <LineIcon name="robot" size={18} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Trợ lý JAMA</div>
              <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Hỏi cách dùng phần mềm — trả lời theo Sổ tay</div>
            </div>
            {tin.length > 0 && (
              <button type="button" onClick={() => setTin([])} title="Xoá hội thoại" aria-label="Xoá hội thoại"
                className="p-2 rounded-lg hover:bg-white/5">
                <LineIcon name="refresh" size={16} color="var(--text-muted)" />
              </button>
            )}
            <button type="button" onClick={() => setMo(false)} aria-label="Đóng" className="p-2 rounded-lg hover:bg-white/5">
              <LineIcon name="x" size={16} color="var(--text-muted)" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
            {tin.length === 0 && (
              <div className="space-y-2">
                <p style={{ color: 'var(--text-secondary)' }}>Chào bạn! Cần làm gì trên phần mềm cứ hỏi, ví dụ:</p>
                {GOI_Y.map(g => (
                  <button key={g} type="button" onClick={() => hoi(g)}
                    className="block w-full text-left px-3 py-2 rounded-xl hover:bg-white/5"
                    style={{ border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}>
                    {g}
                  </button>
                ))}
              </div>
            )}
            {tin.map((t, i) => (
              <div key={i} className={t.role === 'user' ? 'flex justify-end' : ''}>
                <div
                  className="max-w-[88%] px-3 py-2 rounded-2xl whitespace-pre-line break-words"
                  style={t.role === 'user'
                    ? { background: 'var(--gold-500)', color: 'var(--surface-0)' }
                    : { background: 'var(--surface-2)', color: 'var(--text-primary)' }}
                >
                  {t.role === 'assistant' ? dongChu(t.content) : t.content}
                  {!!t.muc?.length && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {t.muc.map(m => (
                        <Link key={m.id} href={`/huong-dan#${m.id}`} onClick={() => setMo(false)}
                          className="text-[11px] px-2 py-0.5 rounded-full hover:opacity-80"
                          style={{ border: '1px solid var(--gold-500)', color: 'var(--gold-500)' }}>
                          Sổ tay: {m.title}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {dangHoi && <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Trợ lý đang trả lời…</div>}
            <div ref={cuoi} />
          </div>

          <form
            className="flex items-end gap-2 p-3 border-t"
            style={{ borderColor: 'var(--border-subtle)' }}
            onSubmit={e => { e.preventDefault(); void hoi(nhap); }}
          >
            <textarea
              ref={oNhap}
              value={nhap}
              onChange={e => setNhap(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void hoi(nhap); }
              }}
              rows={1}
              maxLength={2000}
              placeholder="Nhập câu hỏi…"
              className="flex-1 resize-none max-h-28 px-3 py-2 rounded-xl bg-transparent outline-none"
              style={{ border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
            />
            <button type="submit" disabled={!nhap.trim() || dangHoi} aria-label="Gửi"
              className="w-10 h-10 rounded-full flex items-center justify-center disabled:opacity-40"
              style={{ background: 'var(--gold-500)' }}>
              <LineIcon name="send" size={18} color="var(--surface-0)" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
