'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { getPermissions, UserRole } from '@/lib/roles';
import Sidebar from '@/components/layout/Sidebar';
import { api } from '@/lib/api';

const fmtMoney = (v: number) => `${v.toLocaleString('vi-VN')}đ`;
const currentPeriod = () => new Date().toISOString().slice(0, 7);

type Tab = 'me' | 'team' | 'leaderboard';

interface KpiMetrics {
  activity_rate: number;
  sla_compliance: number;
  first_touch_hours: number;
  signed_count: number;
  signed_value: number;
  stage_conversion: number;
  pipeline_value_weighted: number;
  recall_rate: number;
  lost_no_response_rate: number;
}

interface KpiMe {
  period: string;
  score: number;
  metrics: KpiMetrics;
  rank_in_team: number | null;
  rank_overall: number | null;
}

interface TeamMember {
  user_id: string;
  name: string;
  team_id: string;
  score: number;
  metrics: KpiMetrics;
  rank_in_team: number | null;
}

interface LeaderboardEntry {
  rank: number;
  score: number;
  name: string | null;
  team_id?: string;
  is_me: boolean;
}

const SCORE_COLOR = (score: number) => {
  if (score >= 80) return '#10b981';
  if (score >= 60) return '#f59e0b';
  return '#ef4444';
};

function MetricBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-[var(--text-secondary)] w-36 shrink-0">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-sm font-mono w-16 text-right">{typeof value === 'number' && value % 1 !== 0 ? value.toFixed(1) : value}</span>
    </div>
  );
}

export default function KpiPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<Tab>('me');
  const [period, setPeriod] = useState(currentPeriod());
  const [myKpi, setMyKpi] = useState<KpiMe | null>(null);
  const [teamData, setTeamData] = useState<TeamMember[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [busy, setBusy] = useState(false);

  const isLeaderOrAbove = user && ['admin', 'leader', 'executive'].includes(user.role);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canViewKPI) router.push('/');
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    setBusy(true);
    if (tab === 'me') {
      api.getKpiMe(period).then(setMyKpi).catch(() => {}).finally(() => setBusy(false));
    } else if (tab === 'team' && isLeaderOrAbove) {
      api.getKpiTeam(period).then((d: any) => setTeamData(d.members || [])).catch(() => {}).finally(() => setBusy(false));
    } else if (tab === 'leaderboard') {
      api.getKpiLeaderboard(period).then((d: any) => setLeaderboard(d.leaderboard || [])).catch(() => {}).finally(() => setBusy(false));
    }
  }, [tab, period, user]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <main className="flex-1 overflow-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Đánh giá hiệu suất KPI</h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">Kỳ: {period}</p>
          </div>
          <input
            type="month"
            value={period}
            onChange={e => setPeriod(e.target.value)}
            className="px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {([
            ['me', 'Của tôi'],
            ...(isLeaderOrAbove ? [['team', 'Team'] as const] : []),
            ['leaderboard', 'Bảng xếp hạng'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                tab === key
                  ? 'text-white' : 'text-[var(--text-muted)] hover:bg-white/5'
              }`}
              style={tab === key ? { background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' } : {}}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        {busy && <p className="text-[var(--text-muted)] text-sm">Đang tải...</p>}

        {/* Tab: My KPI */}
        {!busy && tab === 'me' && myKpi && (
          <div className="space-y-6">
            {/* Score card */}
            <div className="glass-card p-6 flex items-center gap-6">
              <div className="w-24 h-24 rounded-full flex items-center justify-center" style={{ border: `4px solid ${SCORE_COLOR(myKpi.score)}` }}>
                <span className="text-2xl font-bold" style={{ color: SCORE_COLOR(myKpi.score) }}>{myKpi.score}</span>
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Điểm KPI tổng hợp</h2>
                <p className="text-sm text-[var(--text-muted)]">
                  {myKpi.rank_overall && `Xếp hạng #${myKpi.rank_overall} toàn công ty`}
                  {myKpi.rank_in_team && ` · #${myKpi.rank_in_team} trong team`}
                </p>
              </div>
            </div>

            {/* Metrics breakdown */}
            <div className="glass-card p-6 space-y-4">
              <h3 className="font-semibold text-white mb-3">Nỗ lực (30%)</h3>
              <MetricBar label="Tần suất hoạt động" value={myKpi.metrics.activity_rate} max={3} color="#3b82f6" />
              <MetricBar label="Tuân thủ SLA" value={myKpi.metrics.sla_compliance} max={100} color="#10b981" />
              <MetricBar label="Phản hồi (giờ)" value={myKpi.metrics.first_touch_hours} max={48} color="#f59e0b" />
            </div>

            <div className="glass-card p-6 space-y-4">
              <h3 className="font-semibold text-white mb-3">Kết quả (50%)</h3>
              <MetricBar label="HĐ đã ký" value={myKpi.metrics.signed_count} max={10} color="#10b981" />
              <MetricBar label="Giá trị ký" value={myKpi.metrics.signed_value / 1_000_000} max={5_000} color="#c9a96e" />
              <MetricBar label="Tỷ lệ chuyển đổi" value={myKpi.metrics.stage_conversion} max={100} color="#8b5cf6" />
            </div>

            <div className="glass-card p-6 space-y-4">
              <h3 className="font-semibold text-white mb-3">Chất lượng (20%)</h3>
              <MetricBar label="Tỷ lệ thu hồi" value={myKpi.metrics.recall_rate} max={10} color="#ef4444" />
              <MetricBar label="Mất KH không phản hồi" value={myKpi.metrics.lost_no_response_rate} max={50} color="#f97316" />
            </div>
          </div>
        )}

        {/* Tab: Team */}
        {!busy && tab === 'team' && (
          <div className="glass-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  <th className="px-4 py-3 text-left text-[var(--text-muted)]">#</th>
                  <th className="px-4 py-3 text-left text-[var(--text-muted)]">Nhân viên</th>
                  <th className="px-4 py-3 text-right text-[var(--text-muted)]">Điểm</th>
                  <th className="px-4 py-3 text-right text-[var(--text-muted)]">SLA</th>
                  <th className="px-4 py-3 text-right text-[var(--text-muted)]">HĐ ký</th>
                  <th className="px-4 py-3 text-right text-[var(--text-muted)]">Hoạt động/ngày</th>
                </tr>
              </thead>
              <tbody>
                {teamData.map((m, i) => (
                  <tr key={m.user_id} className="border-b border-[var(--border-subtle)] hover:bg-white/5">
                    <td className="px-4 py-3 font-mono">{i + 1}</td>
                    <td className="px-4 py-3 font-medium text-white">{m.name}</td>
                    <td className="px-4 py-3 text-right font-bold" style={{ color: SCORE_COLOR(m.score) }}>{m.score}</td>
                    <td className="px-4 py-3 text-right">{m.metrics.sla_compliance}%</td>
                    <td className="px-4 py-3 text-right">{m.metrics.signed_count}</td>
                    <td className="px-4 py-3 text-right">{m.metrics.activity_rate}</td>
                  </tr>
                ))}
                {teamData.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-[var(--text-muted)]">Chưa có dữ liệu KPI kỳ này</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab: Leaderboard */}
        {!busy && tab === 'leaderboard' && (
          <div className="space-y-3">
            {leaderboard.map((entry) => (
              <div
                key={entry.rank}
                className={`glass-card p-4 flex items-center gap-4 ${entry.is_me ? 'ring-2 ring-[var(--gold-500)]' : ''}`}
              >
                <span className="text-lg font-bold w-8 text-center" style={{ color: entry.rank <= 3 ? '#c9a96e' : 'var(--text-muted)' }}>
                  {entry.rank <= 3 ? ['🥇', '🥈', '🥉'][entry.rank - 1] : `#${entry.rank}`}
                </span>
                <div className="flex-1">
                  <span className={`font-medium ${entry.name ? 'text-white' : 'text-[var(--text-muted)]'}`}>
                    {entry.name || `Nhân viên #${entry.rank}`}
                  </span>
                  {entry.is_me && <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-[var(--gold-500)]/20 text-[var(--gold-500)]">Bạn</span>}
                </div>
                <span className="text-lg font-bold" style={{ color: SCORE_COLOR(entry.score) }}>{entry.score}</span>
              </div>
            ))}
            {leaderboard.length === 0 && (
              <p className="text-center text-[var(--text-muted)] py-8">Chưa có dữ liệu KPI kỳ này</p>
            )}
          </div>
        )}

        {/* Policy footer */}
        <p className="text-xs text-[var(--text-disabled)] mt-8 text-center">
          Dữ liệu burnout chỉ dùng để hỗ trợ, không dùng để phạt hay xếp loại.
        </p>
      </main>
    </Sidebar>
  );
}
