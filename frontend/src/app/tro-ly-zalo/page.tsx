'use client';

/**
 * Trợ lý Zalo (23/10/2026) — nơi BGĐ và trưởng phòng nắm việc trong các nhóm Zalo.
 *
 * • BGĐ (admin/executive) thấy mọi nhóm; trưởng phòng + kế toán chỉ thấy nhóm gắn
 *   phòng mình. Phạm vi do backend lọc (pham_vi_zalo) — trang này chỉ hiển thị.
 * • Tab «Tín hiệu»: việc cần xử lý trợ lý bắt được (khách chờ, hỏi giá, lead…).
 * • Tab «Tóm tắt cuối ngày»: bản tóm tắt mỗi nhóm, cùng nội dung gửi Telegram ~17h.
 * • Chỉ NGHE: hệ thống không bao giờ nhắn vào Zalo. Tin gốc tự xóa sau 7 ngày.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/layout/Sidebar';
import { api, ZaloDigestList, ZaloOverview, ZaloSignalInfo } from '@/lib/api';
import { DEPARTMENT_LABELS } from '@/lib/labels';
import { duocXemTroLyZalo } from '@/lib/roles';

const TEN_LOAI: Record<string, string> = {
  unanswered: 'Khách chờ',
  deal_risk: 'Khách không hài lòng',
  quote_request: 'Hỏi giá',
  lead_candidate: 'Lead mới',
  commitment: 'Cam kết',
  faq: 'Câu hỏi lặp lại',
};

const MAU_LOAI: Record<string, string> = {
  unanswered: '#F87171',
  deal_risk: '#F87171',
  quote_request: '#FBBF24',
  lead_candidate: '#34D399',
  commitment: '#60A5FA',
  faq: '#A78BFA',
};

const PHONG = ['EXEC', 'SALES', 'DESIGN', 'ACCT', 'OPS', 'PURCHASING', 'HR', 'PM'];
const tenPhong = (d?: string | null) => (d ? DEPARTMENT_LABELS[d] || d : 'Chưa gắn phòng');

function thoiGian(iso: string) {
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
}

function nhanNgay(day: string) {
  const [y, m, d] = day.split('-');
  const hom = new Date();
  const homNay = `${hom.getFullYear()}-${String(hom.getMonth() + 1).padStart(2, '0')}-${String(hom.getDate()).padStart(2, '0')}`;
  return day === homNay ? 'Hôm nay' : `${d}/${m}${y === String(hom.getFullYear()) ? '' : `/${y}`}`;
}

export default function TroLyZaloPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'tin_hieu' | 'tom_tat'>('tin_hieu');
  const [overview, setOverview] = useState<ZaloOverview | null>(null);
  const [signals, setSignals] = useState<ZaloSignalInfo[] | null>(null);
  const [loai, setLoai] = useState('');
  const [phong, setPhong] = useState('');
  const [digest, setDigest] = useState<ZaloDigestList | null>(null);
  const [ngay, setNgay] = useState<string | undefined>(undefined);
  const [error, setError] = useState('');
  const [dangLam, setDangLam] = useState('');

  const duocXem = duocXemTroLyZalo(user);
  const laBgd = user?.role === 'admin' || user?.role === 'executive';

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push('/login'); return; }
    if (!duocXem) router.push('/');
  }, [user, loading, duocXem, router]);

  const taiTinHieu = useCallback(() => {
    api.zaloSignals('new', { type: loai || undefined, department: phong || undefined })
      .then(r => { setSignals(r.items); setError(''); })
      .catch(e => setError(e.message));
  }, [loai, phong]);

  useEffect(() => {
    if (!duocXem) return;
    api.zaloOverview().then(setOverview).catch(e => setError(e.message));
  }, [duocXem]);

  useEffect(() => {
    if (!duocXem || tab !== 'tin_hieu') return;
    taiTinHieu();
  }, [duocXem, tab, taiTinHieu]);

  useEffect(() => {
    if (!duocXem || tab !== 'tom_tat') return;
    api.zaloDigests(ngay).then(d => { setDigest(d); setError(''); }).catch(e => setError(e.message));
  }, [duocXem, tab, ngay]);

  async function xuLy(s: ZaloSignalInfo, action: 'actioned' | 'dismissed') {
    setDangLam(s.id);
    try {
      await api.zaloActSignal(s.id, action);
      setSignals(prev => (prev || []).filter(x => x.id !== s.id));
      setOverview(o => o && {
        ...o,
        new_by_type: { ...o.new_by_type, [s.type]: Math.max(0, (o.new_by_type[s.type] || 0) - 1) },
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDangLam('');
    }
  }

  async function lamTomTat(send: boolean) {
    setDangLam(send ? 'gui' : 'lam');
    try {
      await api.zaloRunDigest(send);
      setNgay(undefined);
      const d = await api.zaloDigests();
      setDigest(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDangLam('');
    }
  }

  if (loading || !user || !duocXem) return <Sidebar><div className="p-6"><div className="skeleton h-8 w-60 rounded-xl" /></div></Sidebar>;

  const dem = overview?.new_by_type || {};
  const the = [
    { ma: 'unanswered', nhan: 'Khách đang chờ' },
    { ma: 'deal_risk', nhan: 'Khách không hài lòng' },
    { ma: 'quote_request', nhan: 'Hỏi giá' },
    { ma: 'lead_candidate', nhan: 'Lead mới' },
  ];
  const ketNoi = overview?.listener_status === 'logged_in';

  return (
    <Sidebar>
      <div className="p-4 sm:p-6 space-y-5 max-w-6xl">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Trợ lý Zalo</h1>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              {overview?.scope === 'phong'
                ? `Các nhóm Zalo của phòng ${tenPhong(overview.department)}`
                : 'Mọi nhóm Zalo đang theo dõi'}
              {' · '}{overview?.groups_monitored ?? '…'} nhóm · chỉ nghe, không nhắn vào Zalo
            </p>
          </div>
          <span
            className="text-[11px] font-semibold px-3 py-1.5 rounded-full"
            style={{
              background: ketNoi ? 'rgba(52,211,153,0.12)' : 'rgba(248,113,113,0.12)',
              color: ketNoi ? '#34D399' : '#F87171',
            }}
          >
            {ketNoi ? '● Đang nghe' : '● Chưa kết nối Zalo'}
          </span>
        </header>

        {error && <p className="text-xs text-[#F87171] glass-card p-3">{error}</p>}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {the.map(t => (
            <button
              key={t.ma}
              onClick={() => { setTab('tin_hieu'); setLoai(loai === t.ma ? '' : t.ma); }}
              className="glass-card p-4 text-left min-h-[44px] transition-colors"
              style={loai === t.ma ? { borderColor: MAU_LOAI[t.ma] } : undefined}
            >
              <p className="text-[11px] text-[var(--text-muted)]">{t.nhan}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: (dem[t.ma] || 0) > 0 ? MAU_LOAI[t.ma] : 'var(--text-primary)' }}>
                {dem[t.ma] || 0}
              </p>
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          {([['tin_hieu', 'Tín hiệu cần xử lý'], ['tom_tat', 'Tóm tắt cuối ngày']] as const).map(([ma, nhan]) => (
            <button
              key={ma}
              onClick={() => setTab(ma)}
              className="px-4 min-h-[44px] rounded-full text-sm font-medium"
              style={tab === ma
                ? { background: 'var(--text-primary)', color: 'var(--surface-1, #000)' }
                : { background: 'var(--surface-2)', color: 'var(--text-secondary)' }}
            >
              {nhan}
            </button>
          ))}
        </div>

        {tab === 'tin_hieu' && (
          <section className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <select value={loai} onChange={e => setLoai(e.target.value)} className="min-h-[44px] px-3 rounded-full bg-white/5 border border-white/10 text-sm focus:outline-none">
                <option value="">Mọi loại</option>
                {Object.entries(TEN_LOAI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {overview?.scope === 'tat_ca' && (
                <select value={phong} onChange={e => setPhong(e.target.value)} className="min-h-[44px] px-3 rounded-full bg-white/5 border border-white/10 text-sm focus:outline-none">
                  <option value="">Mọi phòng</option>
                  {PHONG.map(d => <option key={d} value={d}>{tenPhong(d)}</option>)}
                </select>
              )}
            </div>

            {signals === null ? (
              <div className="skeleton h-24 rounded-xl" />
            ) : signals.length === 0 ? (
              <p className="glass-card p-8 text-center text-sm text-[var(--text-muted)]">Không còn tín hiệu nào cần xử lý 🎉</p>
            ) : (
              <ul className="space-y-2">
                {signals.map(s => (
                  <li key={s.id} className="glass-card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="font-semibold px-2 py-0.5 rounded-full" style={{ color: MAU_LOAI[s.type], background: 'var(--surface-2)' }}>
                          {TEN_LOAI[s.type] || s.type}
                        </span>
                        <span className="text-[var(--text-secondary)] truncate">{s.group_name}</span>
                        <span className="text-[var(--text-muted)]">· {tenPhong(s.group_department)}</span>
                        <span className="text-[var(--text-muted)]">· {thoiGian(s.created_at)}</span>
                      </div>
                      <p className="text-sm text-[var(--text-primary)] mt-1.5 break-words">{s.summary}</p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        disabled={dangLam === s.id}
                        onClick={() => xuLy(s, 'actioned')}
                        className="min-h-[44px] px-4 rounded-full text-sm font-semibold"
                        style={{ background: 'rgba(52,211,153,0.15)', color: '#34D399' }}
                      >✓ Đã xử lý</button>
                      <button
                        disabled={dangLam === s.id}
                        onClick={() => xuLy(s, 'dismissed')}
                        className="min-h-[44px] px-4 rounded-full text-sm"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}
                      >Bỏ qua</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {tab === 'tom_tat' && (
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {(digest?.days || []).map(d => (
                <button
                  key={d}
                  onClick={() => setNgay(d)}
                  className="min-h-[44px] px-4 rounded-full text-sm"
                  style={(ngay || digest?.day) === d
                    ? { background: 'var(--text-primary)', color: 'var(--surface-1, #000)' }
                    : { background: 'var(--surface-2)', color: 'var(--text-secondary)' }}
                >{nhanNgay(d)}</button>
              ))}
              {user.role === 'admin' && (
                <span className="flex gap-2 ml-auto">
                  <button
                    disabled={!!dangLam}
                    onClick={() => lamTomTat(false)}
                    className="min-h-[44px] px-4 rounded-full text-sm font-semibold"
                    style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
                  >{dangLam === 'lam' ? 'Đang tóm tắt…' : 'Làm tóm tắt hôm nay'}</button>
                  <button
                    disabled={!!dangLam}
                    onClick={() => { if (confirm('Gửi bản tóm tắt hôm nay qua Telegram cho BGĐ và trưởng phòng?')) lamTomTat(true); }}
                    className="min-h-[44px] px-4 rounded-full text-sm font-semibold"
                    style={{ background: 'rgba(96,165,250,0.15)', color: '#60A5FA' }}
                  >{dangLam === 'gui' ? 'Đang gửi…' : 'Gửi Telegram ngay'}</button>
                </span>
              )}
            </div>

            {digest === null ? (
              <div className="skeleton h-24 rounded-xl" />
            ) : digest.items.length === 0 ? (
              <p className="glass-card p-8 text-center text-sm text-[var(--text-muted)]">
                Chưa có bản tóm tắt nào. Trợ lý tự tóm tắt mỗi chiều và gửi Telegram cho {laBgd ? 'BGĐ + trưởng phòng' : 'bạn'}.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {digest.items.map(it => (
                  <article key={it.group_id} className="glass-card p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{it.group_name}</h3>
                        <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                          {tenPhong(it.department)} · {it.kind === 'customer' ? 'Nhóm khách' : 'Nhóm nội bộ'} · {it.msg_count} tin
                        </p>
                      </div>
                      {it.by_llm && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0" style={{ background: 'rgba(167,139,250,0.15)', color: '#A78BFA' }}>AI</span>
                      )}
                    </div>
                    <p className="text-sm text-[var(--text-secondary)] mt-3 whitespace-pre-line break-words">{it.summary}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        <p className="text-[11px] text-[var(--text-disabled)]">
          Dùng để nắm việc và chăm khách — không dùng để chấm điểm hay kỷ luật nhân viên. Tin nhắn gốc tự xóa sau 7 ngày.
        </p>
      </div>
    </Sidebar>
  );
}
