'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import { getPermissions, isSalesCoordinator, UserRole } from '@/lib/roles';
import Sidebar from '@/components/layout/Sidebar';
import { api, laLoiThieuQuyen } from '@/lib/api';
import type { KpiCongThuc, KpiCuaToi, KpiNhanVien, KpiTongQuan } from '@/lib/api';
import { monthLabelVN } from '@/lib/labels';
import { tien } from '@/lib/tien-gon';
import LineIcon from '@/components/ui/LineIcon';
import { BangNhanVien, CachTinhDiem, ChiTietDiem, Delta, ViecNenLam, mauDiem, mauMuc, so } from '@/components/kpi/BangKpi';

// Kỳ theo lịch VN — toISOString() là UTC nên trước 7h sáng mùng 1 vẫn ra tháng cũ.
const currentPeriod = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

type Tab = 'company' | 'me' | 'team' | 'leaderboard';

interface LeaderboardEntry {
  rank: number;
  score: number;
  name: string | null;
  team_id?: string;
  is_me: boolean;
}

function The({ nhan, children }: { nhan: string; children: React.ReactNode }) {
  return (
    <div className="glass-card p-5 min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)] mb-2">{nhan}</p>
      {children}
    </div>
  );
}

/** Góc nhìn BGĐ: công ty đang ở đâu so với mục tiêu, nhóm nào kéo/ghì, việc gì cần hỏi ngay. */
function TongQuanCongTy({ d }: { d: KpiTongQuan }) {
  const t = d.tong;
  const pb = t.phan_bo;
  const coSo = pb.dat + pb.trung_binh + pb.can_kem;
  const tyLeTienDo = t.muc_tieu_thang ? Math.min(100, (t.muc_tieu_tien_do / t.muc_tieu_thang) * 100) : 0;
  const tyLeThucTe = t.muc_tieu_thang ? Math.min(100, (t.doanh_so / t.muc_tieu_thang) * 100) : 0;
  const phanBo = [
    { nhan: 'Đạt', n: pb.dat, mau: 'var(--success)' },
    { nhan: 'Trung bình', n: pb.trung_binh, mau: 'var(--warning)' },
    { nhan: 'Cần kèm', n: pb.can_kem, mau: 'var(--danger)' },
    { nhan: 'Chưa có dữ liệu', n: pb.chua_du_lieu, mau: 'var(--surface-4)' },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <The nhan="Doanh số thắng deal">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-2xl font-bold text-[var(--text-primary)]">{tien(t.doanh_so)}</span>
            {t.doanh_so_truoc != null && t.doanh_so_truoc > 0 && (
              <Delta v={((t.doanh_so - t.doanh_so_truoc) / t.doanh_so_truoc) * 100} donVi="% so với kỳ trước" />
            )}
          </div>
          {t.muc_tieu_thang > 0 ? (
            <>
              <div className="relative h-2 rounded-full mt-3 mb-2" style={{ background: 'var(--surface-4)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.max(1, tyLeThucTe)}%`, background: mauDiem(t.dat_pct ?? 0, 100, 70) }} />
                {d.tien_do.dang_chay && (
                  <div className="absolute -top-1 w-0.5 h-4 rounded" style={{ left: `${tyLeTienDo}%`, background: 'var(--text-primary)' }} title="Mốc tiến độ hôm nay" />
                )}
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Đạt <b style={{ color: mauDiem(t.dat_pct ?? 0, 100, 70) }}>{so(t.dat_pct)}%</b>{' '}
                {d.tien_do.dang_chay ? `mục tiêu tính đến hôm nay (${tien(t.muc_tieu_tien_do)})` : 'mục tiêu kỳ'}
                {' '}· mục tiêu tháng {tien(t.muc_tieu_thang)}
              </p>
            </>
          ) : (
            <p className="text-xs text-[var(--text-muted)] mt-2">Chưa đặt mục tiêu doanh số tháng.</p>
          )}
        </The>

        <The nhan="Deal thắng">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[var(--text-primary)]">{so(t.deal)}</span>
            {t.deal_truoc != null && <span className="text-xs text-[var(--text-muted)]">kỳ trước {so(t.deal_truoc)}</span>}
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-3">
            Dự báo từ lead đang mở: <b className="text-[var(--text-primary)]">{tien(t.du_bao)}</b>
          </p>
          <p className="text-xs text-[var(--text-muted)] mt-1">Giá trị lead đang mở nhân xác suất thắng theo từng bước.</p>
        </The>

        <The nhan={`Điểm KPI trung bình · ${coSo} người có số`}>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold" style={{ color: t.diem_tb == null ? 'var(--text-muted)' : mauDiem(t.diem_tb) }}>{so(t.diem_tb)}</span>
            {t.diem_tb != null && t.diem_tb_truoc != null && <Delta v={Math.round((t.diem_tb - t.diem_tb_truoc) * 10) / 10} donVi=" điểm" />}
          </div>
          <div className="flex h-2 rounded-full overflow-hidden mt-3 mb-2" style={{ background: 'var(--surface-4)' }}>
            {phanBo.filter(p => p.n > 0).map(p => (
              <div key={p.nhan} style={{ width: `${(p.n / t.so_nguoi) * 100}%`, background: p.mau }} />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--text-secondary)]">
            {phanBo.map(p => (
              <span key={p.nhan} className="inline-flex items-center gap-1 whitespace-nowrap">
                <span className="w-2 h-2 rounded-full" style={{ background: p.mau }} />{p.nhan} {p.n}
              </span>
            ))}
          </div>
        </The>

        <The nhan="Lead trong kỳ">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[var(--text-primary)]">{so(t.lead_nhan)}</span>
            <span className="text-xs text-[var(--text-muted)]">lead đã giao cho sale</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-[var(--text-secondary)] mt-3">
            <span>Tiến bước <b className="text-[var(--text-primary)]">{so(t.ty_le_tien_buoc)}%</b></span>
            <span>Mất khách <b className="text-[var(--text-primary)]">{so(t.ty_le_mat)}%</b></span>
            <span>Đang giữ <b className="text-[var(--text-primary)]">{so(t.lead_dang_giu)}</b></span>
            <span>Quá hạn chăm <b style={{ color: t.lead_tre_cham ? 'var(--warning)' : 'var(--text-primary)' }}>{so(t.lead_tre_cham)}</b></span>
          </div>
        </The>
      </div>

      {d.can_chu_y.length > 0 && (
        <div className="glass-card p-5">
          <p className="text-sm font-semibold text-[var(--text-primary)] mb-3">Điều cần chú ý</p>
          <ul className="space-y-2.5">
            {d.can_chu_y.map((c, i) => (
              <li key={i} className="flex gap-3">
                <span className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{ background: mauMuc(c.muc) }} />
                <div className="min-w-0">
                  <p className="text-sm text-[var(--text-primary)]">{c.tieu_de}</p>
                  {c.chi_tiet && <p className="text-xs text-[var(--text-muted)] mt-0.5">{c.chi_tiet}</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="glass-card overflow-x-auto">
        <p className="text-sm font-semibold text-[var(--text-primary)] px-4 pt-4 pb-2">So sánh các nhóm</p>
        <table className="w-full text-sm min-w-[720px]">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              {['Nhóm', 'Người', 'Điểm TB', 'Doanh số', 'So mục tiêu', 'Deal', 'Lead nhận', 'Tiến bước', 'Quá hạn chăm'].map((h, i) => (
                <th key={h} className={`px-3 py-2.5 font-medium text-[var(--text-muted)] whitespace-nowrap ${i === 0 ? 'text-left pl-4' : 'text-right'}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {d.nhom.map(n => (
              <tr key={n.team_id || 'chua-xep'} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <td className="px-4 py-3">
                  <span className="font-medium text-[var(--text-primary)]">{n.ten}</span>
                  {n.truong_nhom && <span className="block text-xs text-[var(--text-muted)]">Trưởng nhóm: {n.truong_nhom}</span>}
                </td>
                <td className="px-3 py-3 text-right">{n.so_nguoi}</td>
                <td className="px-3 py-3 text-right font-bold" style={{ color: n.diem_tb == null ? 'var(--text-muted)' : mauDiem(n.diem_tb) }}>{so(n.diem_tb)}</td>
                <td className="px-3 py-3 text-right whitespace-nowrap text-[var(--text-primary)]">{tien(n.doanh_so)}</td>
                <td className="px-3 py-3 text-right" style={{ color: n.dat_pct == null ? 'var(--text-muted)' : mauDiem(n.dat_pct, 100, 70) }}>
                  {n.dat_pct == null ? '—' : `${so(n.dat_pct, 0)}%`}
                </td>
                <td className="px-3 py-3 text-right">{so(n.deal)}</td>
                <td className="px-3 py-3 text-right">{so(n.lead_nhan)}</td>
                <td className="px-3 py-3 text-right">{n.ty_le_tien_buoc == null ? '—' : `${so(n.ty_le_tien_buoc)}%`}</td>
                <td className="px-3 py-3 text-right" style={{ color: n.lead_tre_cham ? 'var(--warning)' : 'var(--text-muted)' }}>{so(n.lead_tre_cham)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CachTinhDiem congThuc={d.cong_thuc} />

      <p className="text-xs text-[var(--text-muted)]">
        {d.tien_do.dang_chay
          ? `Kỳ đang chạy — ngày ${d.tien_do.ngay_da_qua}/${d.tien_do.so_ngay}; mục tiêu đã chia theo số ngày đã qua nên điểm là tạm tính.`
          : 'Kỳ đã khép.'}
        {d.tinh_luc && ` Số chốt lúc ${new Date(d.tinh_luc).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}.`}
        {' '}Mục tiêu tháng chỉnh ở <Link href="/sale-dashboard" className="underline">Bảng điều khiển Kinh doanh</Link>.
      </p>
    </div>
  );
}

export default function KpiPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  // BGĐ không gánh chỉ tiêu nên không có «Của tôi» — mở thẳng góc nhìn toàn công ty.
  const laBgd = !!user && ['admin', 'executive'].includes(user.role);
  const [tabChon, setTab] = useState<Tab | null>(null);
  // `?tab=team`: «Việc của tôi» của BGĐ dẫn thẳng vào tab Đội nhóm. Đọc trong effect vì khi chuyển
  // trang trong app, Next chỉ đổi thanh địa chỉ sau lượt render đầu (đọc lúc khởi tạo state là trượt).
  useEffect(() => {
    void Promise.resolve().then(() => {
      const t = new URLSearchParams(window.location.search).get('tab');
      if (t === 'team' || t === 'leaderboard') setTab(t);
    });
  }, []);
  const tab: Tab = tabChon ?? (laBgd ? 'company' : 'me');

  const [period, setPeriod] = useState(currentPeriod());
  const [myKpi, setMyKpi] = useState<KpiCuaToi | null>(null);
  const [teamData, setTeamData] = useState<KpiNhanVien[]>([]);
  const [congThuc, setCongThuc] = useState<KpiCongThuc | undefined>();
  const [tongQuan, setTongQuan] = useState<KpiTongQuan | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [kpiError, setKpiError] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);

  // Ai thấy tab "Đội nhóm" — PHẢI khớp chốt chặn GET /kpi/team ở backend, nếu không
  // là hoặc giấu tab của người có quyền, hoặc mở tab rồi để họ ăn 403.
  // sale_leader: backend cho qua is_team_lead từ trước nhưng FE quên — mở 09/09.
  const isLeaderOrAbove = !!user && (
    ['admin', 'leader', 'executive', 'sale_leader'].includes(user.role) || isSalesCoordinator(user.role, user.department)
  );

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
    if (!loading && user && !getPermissions(user.role as UserRole).canViewKPI) router.push('/');
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    void Promise.resolve().then(() => {
      setBusy(true);
      setKpiError(null);
      // Tách 403 khỏi lỗi hệ thống: vai trò tùy chỉnh (VD Điều phối KD) chưa được backend
      // cho xem KPI đội, trước đây chỉ hiện "Không thể tải dữ liệu KPI" nên nhìn như ERP hỏng.
      const bao = (e: unknown) => setKpiError(
        laLoiThieuQuyen(e)
          ? 'Tài khoản của bạn chưa được cấp quyền xem mục này. Liên hệ quản trị nếu cần.'
          : 'Không thể tải dữ liệu KPI — vui lòng thử lại.'
      );
      const xong = () => setBusy(false);
      if (laBgd) {
        // BGĐ: một lần gọi nuôi cả 3 tab (toàn công ty, đội nhóm, xếp hạng) — đổi tab không tải lại.
        api.getKpiTongQuan(period).then(d => { setTongQuan(d); setTeamData(d.nhan_vien); setCongThuc(d.cong_thuc); }).catch(bao).finally(xong);
      } else if (tab === 'me') {
        api.getKpiMe(period).then(setMyKpi).catch(bao).finally(xong);
      } else if (tab === 'team' && isLeaderOrAbove) {
        api.getKpiTeam(period).then(d => { setTeamData(d.members || []); setCongThuc(d.cong_thuc); }).catch(bao).finally(xong);
      } else if (tab === 'leaderboard') {
        api.getKpiLeaderboard(period).then(d => setLeaderboard(d.leaderboard || [])).catch(bao).finally(xong);
      } else {
        xong();
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [laBgd ? 'bgd' : tab, period, user, lanTai]);

  if (loading || !user) return <Sidebar><div className="p-6 space-y-4"><div className="skeleton h-8 w-48 rounded-xl" /><div className="skeleton h-32 rounded-xl" /></div></Sidebar>;

  const cacTab: Array<[Tab, string]> = [
    ...(laBgd ? [['company', 'Toàn công ty'] as [Tab, string]] : [['me', 'Của tôi'] as [Tab, string]]),
    ...(isLeaderOrAbove ? [['team', 'Đội nhóm'] as [Tab, string]] : []),
    ['leaderboard', 'Bảng xếp hạng'],
  ];
  // BGĐ: bảng xếp hạng dựng từ chính dữ liệu tổng quan → đủ tên, kèm nhóm và biến động.
  const xepHangBgd = laBgd ? teamData.filter(h => !h.metrics.chua_du_lieu) : [];

  return (
    <Sidebar>
      <main className="flex-1 overflow-auto p-4 sm:p-6">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold">Đánh giá hiệu suất KPI</h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">Kỳ: {monthLabelVN(period)} · Phòng Kinh doanh</p>
          </div>
          <input
            type="month"
            aria-label="Chọn kỳ"
            value={period}
            max={currentPeriod()}
            onChange={e => e.target.value && setPeriod(e.target.value)}
            className="px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {cacTab.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                tab === key ? 'text-white' : 'text-[var(--text-muted)] hover:bg-white/5'
              }`}
              style={tab === key ? { background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' } : {}}
            >
              {label}
            </button>
          ))}
        </div>

        {busy && <p className="text-[var(--text-muted)] text-sm">Đang tải...</p>}

        {!busy && kpiError && (
          <div className="glass-card p-8 flex flex-col items-center text-center">
            <div className="mb-3"><LineIcon name="alert" size={40} color="#f87171" /></div>
            <p className="text-sm text-red-400 mb-2">{kpiError}</p>
            <button onClick={() => setLanTai(n => n + 1)} className="text-xs px-3 py-1 rounded-lg bg-white/5">Thử lại</button>
          </div>
        )}

        {/* Tab: Toàn công ty (BGĐ) */}
        {!busy && !kpiError && tab === 'company' && tongQuan && <TongQuanCongTy d={tongQuan} />}

        {/* Tab: Của tôi */}
        {!busy && !kpiError && tab === 'me' && myKpi && myKpi.thuoc_doi === false && (
          <div className="glass-card p-8 flex flex-col items-center text-center">
            <div className="mb-3"><LineIcon name="chart" size={40} /></div>
            <p className="text-sm text-[var(--text-secondary)] max-w-md leading-relaxed">
              KPI ở trang này chấm cho đội Kinh doanh (nhân viên và trưởng nhóm gánh chỉ tiêu).
              Tài khoản của bạn không gánh chỉ tiêu doanh số nên không có điểm và không có việc được giao ở đây.
            </p>
          </div>
        )}
        {!busy && !kpiError && tab === 'me' && myKpi && myKpi.thuoc_doi !== false && (
          <div className="space-y-4">
            <div className="glass-card p-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-4 min-w-0">
                {myKpi.metrics.chua_du_lieu ? (
                  <div className="w-16 h-16 rounded-full flex items-center justify-center shrink-0" style={{ border: '3px solid var(--surface-4)' }}>
                    <span className="text-xl font-bold text-[var(--text-muted)]">—</span>
                  </div>
                ) : (
                  <div className="w-16 h-16 rounded-full flex items-center justify-center shrink-0" style={{ border: `3px solid ${mauDiem(myKpi.score)}` }}>
                    <span className="text-xl font-bold" style={{ color: mauDiem(myKpi.score) }}>{so(myKpi.score)}</span>
                  </div>
                )}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">Điểm KPI</p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {myKpi.metrics.chua_du_lieu
                      ? 'Kỳ này bạn chưa có lead hay deal nào để chấm'
                      : <>
                          {myKpi.rank_overall ? `Hạng ${myKpi.rank_overall} toàn công ty` : 'Chưa xếp hạng'}
                          {myKpi.rank_in_team ? ` · hạng ${myKpi.rank_in_team} trong nhóm` : ''}
                        </>}
                  </p>
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs text-[var(--text-muted)]">Doanh số</p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">{tien(myKpi.metrics.doanh_so || 0)}</p>
              </div>
            </div>
            {/* `?.`/`||`: backend bản cũ (trước khi có viec_tiep) vẫn mở được trang, chỉ thiếu khối việc */}
            {myKpi.tien_do?.dang_chay
              ? <ViecNenLam ds={myKpi.viec_tiep || []} diem={myKpi.score} nguongDat={myKpi.cong_thuc?.moc.nguong_dat} />
              : myKpi.tien_do && <p className="text-xs text-[var(--text-muted)]">Kỳ này đã khép nên không còn việc để làm tiếp. Chọn tháng hiện tại để xem việc đang cần làm.</p>}
            <div className="glass-card p-5">
              <p className="text-sm font-semibold text-[var(--text-primary)] mb-3">Điểm của bạn được tính từ đâu</p>
              <ChiTietDiem m={myKpi.metrics} congThuc={myKpi.cong_thuc} />
            </div>
            <CachTinhDiem congThuc={myKpi.cong_thuc} />
            {myKpi.tien_do?.dang_chay && (
              <p className="text-xs text-[var(--text-muted)]">
                Kỳ đang chạy, ngày {myKpi.tien_do.ngay_da_qua}/{myKpi.tien_do.so_ngay}: mục tiêu đã chia theo số ngày đã qua nên điểm là tạm tính.
              </p>
            )}
          </div>
        )}
        {!busy && !kpiError && tab === 'me' && !myKpi && (
          <div className="glass-card p-10 flex flex-col items-center text-center">
            <div className="mb-3"><LineIcon name="chart" size={40} /></div>
            <p className="text-sm text-[var(--text-secondary)] max-w-md">
              Chưa có dữ liệu KPI kỳ này — KPI sẽ hiện khi có lead/công trình được gán cho bạn
            </p>
          </div>
        )}

        {/* Tab: Đội nhóm — luôn gom theo nhóm, có tên nhóm + trưởng nhóm + số tổng của nhóm */}
        {!busy && !kpiError && tab === 'team' && (
          <div className="space-y-4">
            <BangNhanVien ds={teamData} congThuc={congThuc} />
            <p className="text-xs text-[var(--text-muted)]">Bấm vào một người để xem điểm được tính từ đâu.</p>
            {!laBgd && <CachTinhDiem congThuc={congThuc} />}
          </div>
        )}

        {/* Tab: Bảng xếp hạng */}
        {!busy && !kpiError && tab === 'leaderboard' && laBgd && (
          <div className="space-y-3">
            {xepHangBgd.map((h, i) => (
              <div key={h.user_id} className="glass-card p-4 flex items-center gap-4">
                <span className="text-lg font-bold w-8 text-center shrink-0" style={{ color: 'var(--text-muted)' }}>
                  {i < 3 ? <LineIcon name="award" size={22} color={['#c9a96e', '#9ca3af', '#b45309'][i]} className="inline-block" /> : `#${i + 1}`}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-[var(--text-primary)] truncate">{h.name}</p>
                  <p className="text-xs text-[var(--text-muted)] truncate">
                    {h.ten_nhom || 'Chưa xếp nhóm'} · {tien(h.metrics.doanh_so || 0)} · {so(h.metrics.deal_thang)} deal
                  </p>
                </div>
                <Delta v={h.delta} />
                <span className="text-lg font-bold shrink-0" style={{ color: mauDiem(h.score) }}>{so(h.score)}</span>
              </div>
            ))}
            {xepHangBgd.length === 0 && <p className="text-center text-[var(--text-muted)] py-8">Chưa có dữ liệu KPI kỳ này</p>}
          </div>
        )}
        {!busy && !kpiError && tab === 'leaderboard' && !laBgd && (
          <div className="space-y-3">
            {leaderboard.map((entry) => (
              <div
                key={entry.rank}
                className={`glass-card p-4 flex items-center gap-4 ${entry.is_me ? 'ring-2 ring-[var(--gold-500)]' : ''}`}
              >
                <span className="text-lg font-bold w-8 text-center" style={{ color: entry.rank <= 3 ? '#c9a96e' : 'var(--text-muted)' }}>
                  {entry.rank <= 3 ? <LineIcon name="award" size={22} color={['#c9a96e', '#9ca3af', '#b45309'][entry.rank - 1]} className="inline-block" /> : `#${entry.rank}`}
                </span>
                <div className="flex-1">
                  <span className={`font-medium ${entry.name ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
                    {entry.name || `Nhân viên #${entry.rank}`}
                  </span>
                  {entry.is_me && <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-[var(--gold-500)]/20 text-[var(--gold-500)]">Bạn</span>}
                </div>
                <span className="text-lg font-bold" style={{ color: mauDiem(entry.score) }}>{so(entry.score)}</span>
              </div>
            ))}
            {leaderboard.length === 0 && (
              <p className="text-center text-[var(--text-muted)] py-8">Chưa có dữ liệu KPI kỳ này</p>
            )}
          </div>
        )}

        <p className="text-xs text-[var(--text-disabled)] mt-8 text-center">
          Dữ liệu quá tải chỉ dùng để hỗ trợ, không dùng để phạt hay xếp loại.
        </p>
      </main>
    </Sidebar>
  );
}
