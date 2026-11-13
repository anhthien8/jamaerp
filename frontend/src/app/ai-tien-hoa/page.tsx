'use client';

/**
 * AI Tiến Hoá (13/11/2026) — chỉ admin, khớp _chi_quan_tri() ở backend/app/api/ai.py.
 *
 * Bảng theo dõi AI học được gì từ cách sale dùng gợi ý, cộng vòng tự học: AI gom phản hồi
 * theo từng loại gợi ý thành «bài học» (ưu tiên / hạ xuống), admin duyệt thì Co-Pilot mới
 * xếp lại gợi ý và đưa bài học vào lời dặn LLM. Không duyệt thì không có gì thay đổi.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { api, type AiBaiHoc, type AiHuong, type AiTienHoa } from '@/lib/api';
import {
  BangTroLy, BangTuan, ChenhLech, ChuGiai, CotTroLy, DuongLamTheo, GatBang, MAU_1, MAU_2, Sparkline, The, pct,
} from '@/components/ai-tien-hoa/BieuDo';

const DUOC_XEM = ['admin'];
const KY = [4, 8, 12, 26];
const so = (n: number) => n.toLocaleString('vi-VN');
const TEN_HUONG: Record<AiHuong, string> = { uu_tien: 'Ưu tiên', ha: 'Hạ xuống' };

/** Chuỗi tỷ lệ cho đường nhỏ, 12 tuần cuối. */
const tyLe = (tu: number[], mau: number[]) => tu.map((t, i) => (mau[i] ? t / mau[i] : null)).slice(-12);
/** Chuỗi số đếm quy về 0–1 theo tuần cao nhất. */
const quyVe = (gt: number[]) => {
  const g = gt.slice(-12);
  const max = Math.max(1, ...g);
  return g.map(v => v / max);
};

function NhanHuong({ huong }: { huong: AiHuong }) {
  const len = huong === 'uu_tien';
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold bg-[var(--surface-3)]"
      style={{ color: len ? 'var(--success)' : 'var(--warning)' }}>
      <LineIcon name={len ? 'trendUp' : 'trendDown'} size={12} color="currentColor" />
      {TEN_HUONG[huong]}
    </span>
  );
}

function OSo({ nhan, gt, phu, chuoi }: { nhan: string; gt: string; phu: string; chuoi?: (number | null)[] }) {
  return (
    <div className="card p-4 flex flex-col gap-2 min-w-0">
      <div className="text-xs text-[var(--text-muted)]">{nhan}</div>
      <div className="flex items-end justify-between gap-2 min-h-[30px]">
        <div className="text-2xl font-semibold text-[var(--text-primary)] leading-none">{gt}</div>
        {chuoi && <Sparkline gt={chuoi} rong={88} cao={30} nhan={`${nhan} theo tuần`} />}
      </div>
      <div className="text-xs text-[var(--text-secondary)]">{phu}</div>
    </div>
  );
}

export default function AiTienHoaPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [soTuan, setSoTuan] = useState(12);
  const [d, setD] = useState<AiTienHoa | null>(null);
  const [loi, setLoi] = useState('');
  const [bangTuan, setBangTuan] = useState(false);
  const [bangTroLy, setBangTroLy] = useState(false);
  const [dangLuu, setDangLuu] = useState<string | null>(null);
  const [baoLoi, setBaoLoi] = useState('');

  useEffect(() => {
    if (loading) return;
    if (!user) router.push('/login');
    else if (!DUOC_XEM.includes(user.role)) router.push('/');
  }, [user, loading, router]);

  const tai = useCallback(async (n: number) => {
    try {
      setD(await api.aiTienHoa(n));
      setLoi('');
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Không tải được số liệu');
    }
  }, []);

  useEffect(() => {
    if (!user || !DUOC_XEM.includes(user.role)) return;
    let bo = false;
    api.aiTienHoa(soTuan)
      .then(kq => { if (!bo) { setD(kq); setLoi(''); } })
      .catch(e => { if (!bo) setLoi(e instanceof Error ? e.message : 'Không tải được số liệu'); });
    return () => { bo = true; };
  }, [user, soTuan]);

  const quyet = async (b: AiBaiHoc, quyetDinh: 'duyet' | 'tu_choi' | 'go', huong: AiHuong | null = b.huong) => {
    setDangLuu(b.code);
    setBaoLoi('');
    try {
      await api.aiTienHoaQuyet(b.code, quyetDinh === 'go' ? null : huong, quyetDinh);
      await tai(soTuan);
    } catch (e) {
      setBaoLoi(e instanceof Error ? e.message : 'Không lưu được quyết định');
    } finally {
      setDangLuu(null);
    }
  };

  if (loading || (user && DUOC_XEM.includes(user.role) && !d && !loi)) {
    return (
      <Sidebar>
        <div className="p-4 sm:p-6 space-y-4">
          <div className="skeleton h-8 w-56 rounded-lg" />
          <div className="glass-card skeleton h-[320px]" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[0, 1, 2, 3].map(i => <div key={i} className="glass-card skeleton h-[112px]" />)}
          </div>
        </div>
      </Sidebar>
    );
  }
  if (!user || !DUOC_XEM.includes(user.role)) return null;

  if (!d) {
    return (
      <Sidebar>
        <div className="p-4 sm:p-6">
          <div className="card p-6 text-sm text-[var(--text-secondary)] flex items-center gap-3">
            <LineIcon name="alert" size={18} color="var(--danger)" />
            <span className="flex-1">{loi}</span>
            <button type="button" onClick={() => tai(soTuan)}
              className="min-h-[40px] px-4 rounded-full text-sm font-medium border border-[var(--border-default)] text-[var(--text-primary)]">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }

  const t = d.tong;
  const w = d.theo_tuan;
  const choDuyet = d.bai_hoc.filter(b => b.trang_thai === 'cho_duyet' || b.de_xuat_moi);
  const conLai = d.bai_hoc.filter(b => !(b.trang_thai === 'cho_duyet' || b.de_xuat_moi));
  const coDuLieu = t.so_lan_chay > 0 || t.so_goi_y > 0;

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 space-y-5 sm:space-y-6 animate-in max-w-[1200px]">
        {/* Đầu trang + chọn kỳ */}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold">AI <span className="gold-gradient">Tiến Hoá</span></h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              AI học từ việc sale làm theo hay bỏ qua gợi ý. Bạn duyệt bài học thì Co-Pilot mới đổi cách gợi ý.
            </p>
          </div>
          <div className="inline-flex rounded-full bg-[var(--surface-3)] p-0.5 text-sm" role="group" aria-label="Khoảng thời gian">
            {KY.map(k => (
              <button key={k} type="button" onClick={() => setSoTuan(k)} aria-pressed={soTuan === k}
                className={`px-3 sm:px-4 py-1.5 rounded-full min-h-[36px] ${soTuan === k ? 'bg-[var(--text-primary)] text-[var(--surface-0)] font-semibold' : 'text-[var(--text-secondary)]'}`}>
                {k} tuần
              </button>
            ))}
          </div>
        </div>

        {loi && (
          <div className="flex items-center gap-2 text-sm rounded-xl px-3 py-2 bg-[var(--surface-2)] border border-[var(--border-default)]" role="alert">
            <LineIcon name="alert" size={16} color="var(--danger)" />
            <span className="text-[var(--text-primary)]">Không tải được kỳ {soTuan} tuần — đang hiện số liệu {d.so_tuan} tuần. {loi}</span>
          </div>
        )}

        {choDuyet.length > 0 && (
          <a href="#bai-hoc" className="flex items-center gap-3 rounded-2xl px-4 py-3 bg-[var(--surface-2)] border border-[var(--border-default)] hover:border-[var(--border-strong)] min-h-[52px]">
            <LineIcon name="bulb" size={18} color="var(--warning)" />
            <span className="text-sm text-[var(--text-primary)]"><b>{choDuyet.length}</b> bài học đang chờ bạn duyệt</span>
            <LineIcon name="arrowRight" size={16} color="var(--text-muted)" className="ml-auto" />
          </a>
        )}

        {!coDuLieu && (
          <div className="card p-4 text-sm text-[var(--text-secondary)] flex items-start gap-3">
            <LineIcon name="info" size={18} color="var(--text-muted)" />
            Chưa có lần AI chạy nào trong {d.so_tuan} tuần qua. Số liệu sẽ hiện khi sale mở Co-Pilot và bấm «Đã làm» / «Bỏ qua» trên gợi ý.
          </div>
        )}

        {/* Số chính: tỷ lệ làm theo gợi ý */}
        <The tieuDe="Sale làm theo gợi ý"
          phu={`Trong các gợi ý đã có phản hồi «Đã làm» hoặc «Bỏ qua», ${d.so_tuan} tuần từ ${new Date(d.tu_ngay).toLocaleDateString('vi-VN')}`}
          phai={<GatBang bang={bangTuan} onDoi={setBangTuan} />}>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2 mb-4">
            <div>
              <div className="text-xs text-[var(--text-muted)] mb-1">4 tuần gần nhất</div>
              <div className="text-5xl font-semibold leading-none text-[var(--text-primary)]">{pct(t.ty_le_lam_theo_4_tuan)}</div>
            </div>
            <div className="pb-1 space-y-1">
              <ChenhLech v={t.chenh_lech} so_voi="4 tuần trước" />
              <div className="text-xs text-[var(--text-secondary)]">
                Cả kỳ {pct(t.ty_le_lam_theo)} · {so(t.lam)} đã làm, {so(t.bo_qua)} bỏ qua trên {so(t.so_goi_y)} gợi ý
              </div>
            </div>
          </div>
          {bangTuan ? <BangTuan tuan={w} /> : <DuongLamTheo tuan={w} />}
        </The>

        {/* Ô số vận hành */}
        <div className="grid grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-4 gap-3">
          <OSo nhan="Lần AI chạy" gt={so(t.so_lan_chay)} phu={`${so(t.so_lan_chay - t.dung_lai)} lần chạy mới`}
            chuoi={quyVe(w.map(x => x.chay))} />
          <OSo nhan="Dùng lại bộ nhớ" gt={pct(t.ty_le_dung_lai)} phu={`${so(t.dung_lai)} lần lấy kết quả cũ, không gọi lại AI`}
            chuoi={tyLe(w.map(x => x.dung_lai), w.map(x => x.chay))} />
          <OSo nhan="Do LLM trả lời" gt={pct(t.ty_le_llm)} phu={`${so(t.llm)} LLM · ${so(t.rule)} bộ luật`}
            chuoi={tyLe(w.map(x => x.llm), w.map(x => x.llm + x.rule))} />
          <OSo nhan="Làm theo khi có bài học" gt={pct(t.ap_bai_hoc.ty_le_lam_theo)}
            phu={t.ap_bai_hoc.so_goi_y ? `trên ${so(t.ap_bai_hoc.so_goi_y)} gợi ý đã xếp theo bài học` : 'chưa có gợi ý nào chạy theo bài học'} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5 sm:gap-6">
          {/* Theo trợ lý */}
          <The className="lg:col-span-3" tieuDe="Từng trợ lý AI" phu="Lần chạy trong kỳ, tách phần LLM trả lời và phần bộ luật trả lời"
            phai={<GatBang bang={bangTroLy} onDoi={setBangTroLy} />}>
            {d.theo_agent.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Chưa có trợ lý nào chạy trong kỳ.</p>
            ) : bangTroLy ? <BangTroLy rows={d.theo_agent} /> : (
              <>
                <div className="mb-3"><ChuGiai muc={[{ mau: MAU_1, nhan: 'AI (LLM)' }, { mau: MAU_2, nhan: 'Bộ luật' }]} /></div>
                <CotTroLy rows={d.theo_agent} />
              </>
            )}
          </The>

          {/* Model */}
          <The className="lg:col-span-2" tieuDe="Model đang dùng"
            phai={<Link href="/settings" className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] inline-flex items-center gap-1 min-h-[32px]">Đổi ở Cài đặt <LineIcon name="arrowRight" size={14} color="currentColor" /></Link>}>
            {!d.model.dang_bat ? (
              <div className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                <LineIcon name="alert" size={16} color="var(--warning)" />
                AI đang tắt — mọi gợi ý do bộ luật đưa ra.
              </div>
            ) : (
              <div className="space-y-3 text-sm">
                <div>
                  <div className="text-xs text-[var(--text-muted)]">Model chính</div>
                  <div className="font-mono text-[var(--text-primary)] break-all">{d.model.chinh || '—'}</div>
                </div>
                {d.model.du_phong.length > 0 && (
                  <div>
                    <div className="text-xs text-[var(--text-muted)]">Dự phòng theo thứ tự</div>
                    <ol className="mt-1 space-y-0.5">
                      {d.model.du_phong.map((m, i) => (
                        <li key={m} className="font-mono text-xs text-[var(--text-secondary)] break-all">{i + 1}. {m}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}
            {d.model.da_tra_loi.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[var(--border-subtle)]">
                <div className="text-xs text-[var(--text-muted)] mb-1.5">Đã trả lời trong kỳ</div>
                <ul className="space-y-1" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {d.model.da_tra_loi.map(m => (
                    <li key={m.model} className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-[var(--text-secondary)] truncate">{m.model}</span>
                      <span className="ml-auto font-semibold text-[var(--text-primary)]">{so(m.so_lan)} lần</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </The>
        </div>

        {/* Theo loại gợi ý */}
        <The tieuDe="Loại gợi ý hay bị bỏ qua"
          phu={`Xếp theo số lần bỏ qua. Từ ${d.nguong.mau_toi_thieu} phản hồi trở lên: bỏ qua ≥ ${Math.round(d.nguong.bo_qua * 100)}% thì AI đề xuất hạ, làm theo ≥ ${Math.round(d.nguong.lam * 100)}% thì đề xuất ưu tiên.`}>
          {d.theo_loai.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">Chưa có gợi ý nào trong kỳ.</p>
          ) : (
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="text-xs text-[var(--text-muted)] text-left">
                    <th className="font-medium py-2 px-1">Loại gợi ý</th>
                    <th className="font-medium py-2 px-1 text-right">Bỏ qua</th>
                    <th className="font-medium py-2 px-1 text-right">Đã làm</th>
                    <th className="font-medium py-2 px-1 text-right">Chưa phản hồi</th>
                    <th className="font-medium py-2 px-1 text-right">Làm theo</th>
                    <th className="font-medium py-2 px-1 text-right">AI đề xuất</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {d.theo_loai.map(r => {
                    const du = r.lam + r.bo_qua >= d.nguong.mau_toi_thieu;
                    const huong: AiHuong | null = !du ? null
                      : (r.ty_le_bo_qua ?? 0) >= d.nguong.bo_qua ? 'ha'
                      : (r.ty_le_lam ?? 0) >= d.nguong.lam ? 'uu_tien' : null;
                    return (
                      <tr key={r.code}>
                        <td className="py-2 px-1 text-[var(--text-primary)]">{r.nhan}</td>
                        <td className="py-2 px-1 text-right font-semibold">{so(r.bo_qua)}</td>
                        <td className="py-2 px-1 text-right">{so(r.lam)}</td>
                        <td className="py-2 px-1 text-right text-[var(--text-muted)]">{so(r.chua_phan_hoi)}</td>
                        <td className="py-2 px-1 text-right">{pct(r.ty_le_lam)}</td>
                        <td className="py-2 px-1 text-right">
                          {huong ? <NhanHuong huong={huong} /> : <span className="text-xs text-[var(--text-muted)]">{du ? 'giữ nguyên' : 'chưa đủ mẫu'}</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </The>

        {/* Bài học — vòng tự học */}
        <The id="bai-hoc" tieuDe="Bài học AI rút ra" className="scroll-mt-20"
          phu="Duyệt thì Co-Pilot xếp gợi ý theo bài học và nhắc LLM; bỏ qua thì giữ cách gợi ý cũ. Gỡ lúc nào cũng được.">
          {baoLoi && (
            <div className="mb-3 flex items-center gap-2 text-sm text-[var(--text-primary)] rounded-xl px-3 py-2 bg-[var(--surface-2)] border border-[var(--border-default)]" role="alert">
              <LineIcon name="alert" size={16} color="var(--danger)" />{baoLoi}
            </div>
          )}
          {d.bai_hoc.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">
              Chưa có bài học nào. Một loại gợi ý cần ít nhất {d.nguong.mau_toi_thieu} phản hồi và nghiêng rõ về một phía thì AI mới đề xuất.
            </p>
          ) : (
            <ul className="space-y-3">
              {[...choDuyet, ...conLai].map(b => (
                <TheBaiHoc key={b.code} b={b} dangLuu={dangLuu === b.code} khoa={dangLuu != null} onQuyet={quyet} />
              ))}
            </ul>
          )}
        </The>
      </div>
    </Sidebar>
  );
}

const TRANG_THAI: Record<AiBaiHoc['trang_thai'], { nhan: string; icon: string; mau: string }> = {
  cho_duyet: { nhan: 'Chờ duyệt', icon: 'clock', mau: 'var(--warning)' },
  dang_ap_dung: { nhan: 'Đang áp dụng', icon: 'tick', mau: 'var(--success)' },
  da_bo_qua: { nhan: 'Đã bỏ qua', icon: 'xCircle', mau: 'var(--text-muted)' },
};

function TheBaiHoc({ b, dangLuu, khoa, onQuyet }: {
  b: AiBaiHoc; dangLuu: boolean; khoa: boolean;
  onQuyet: (b: AiBaiHoc, q: 'duyet' | 'tu_choi' | 'go', huong?: AiHuong | null) => void;
}) {
  const tt = TRANG_THAI[b.trang_thai];
  const nut = 'min-h-[40px] px-4 rounded-full text-sm font-medium disabled:opacity-50';
  const chinh = `${nut} bg-[var(--text-primary)] text-[var(--surface-0)]`;
  const phu = `${nut} border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]`;
  return (
    <li className="rounded-2xl p-4 bg-[var(--surface-2)] border border-[var(--border-subtle)]">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="font-semibold text-[var(--text-primary)]">{b.nhan}</span>
        <NhanHuong huong={b.huong} />
        <span className="ml-auto inline-flex items-center gap-1 text-xs" style={{ color: tt.mau }}>
          <LineIcon name={tt.icon} size={14} color="currentColor" />{tt.nhan}
        </span>
      </div>
      <p className="text-sm text-[var(--text-secondary)]">{b.noi_dung}</p>
      {b.de_xuat_moi && (
        <p className="mt-2 text-sm text-[var(--text-primary)] flex items-start gap-2">
          <LineIcon name="refresh" size={16} color="var(--warning)" />
          Số liệu mới nghiêng về «{TEN_HUONG[b.de_xuat_moi]}» — ngược với bài học đang áp dụng.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 mt-3">
        {b.trang_thai === 'cho_duyet' && (
          <>
            <button type="button" disabled={khoa} onClick={() => onQuyet(b, 'duyet')} className={chinh}>{dangLuu ? 'Đang lưu…' : 'Duyệt áp dụng'}</button>
            <button type="button" disabled={khoa} onClick={() => onQuyet(b, 'tu_choi')} className={phu}>Bỏ qua</button>
          </>
        )}
        {b.trang_thai === 'dang_ap_dung' && (
          <>
            {b.de_xuat_moi && (
              <button type="button" disabled={khoa} onClick={() => onQuyet(b, 'duyet', b.de_xuat_moi)} className={chinh}>
                {dangLuu ? 'Đang lưu…' : `Đổi sang «${TEN_HUONG[b.de_xuat_moi]}»`}
              </button>
            )}
            <button type="button" disabled={khoa} onClick={() => onQuyet(b, 'go')} className={phu}>Gỡ bài học</button>
          </>
        )}
        {b.trang_thai === 'da_bo_qua' && (
          <button type="button" disabled={khoa} onClick={() => onQuyet(b, 'duyet')} className={phu}>{dangLuu ? 'Đang lưu…' : 'Duyệt lại'}</button>
        )}
        {b.quyet_boi && (
          <span className="text-xs text-[var(--text-muted)] ml-auto">
            {b.trang_thai === 'da_bo_qua' ? 'Bỏ qua' : 'Duyệt'} bởi {b.quyet_boi}
            {b.quyet_luc ? ` · ${new Date(b.quyet_luc + 'Z').toLocaleDateString('vi-VN')}` : ''}
          </span>
        )}
      </div>
    </li>
  );
}
