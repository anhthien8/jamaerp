'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, User, Team, extractItems } from '@/lib/api';
import { getPermissions, UserRole } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';

const ROLE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  admin: { label: 'Admin', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  director: { label: 'Giám đốc', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
  sales_lead: { label: 'Trưởng Sales', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  data_entry: { label: 'Sales Rep', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  designer: { label: 'Thiết kế', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
  pm: { label: 'Project Manager', color: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
  accountant: { label: 'Kế toán', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
};

const DEPT_LABELS: Record<string, string> = {
  sales: 'Kinh doanh',
  design: 'Thiết kế',
  construction: 'Thi công',
  accounting: 'Kế toán',
  management: 'Ban lãnh đạo',
};

export default function HRPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [viewMode, setViewMode] = useState<'list' | 'org'>('list');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUser, setNewUser] = useState({
    full_name: '', email: '', phone: '', password: '', role: 'data_entry', department: 'SALES'
  });

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canViewHR) router.push('/');
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const [uResult, t] = await Promise.all([api.getUsers(), api.getTeams()]);
      setUsers(extractItems(uResult));
      setTeams(t);
    } catch { toast('Không thể tải nhân sự', 'error'); } finally {
      setLoadingData(false);
    }
  }, [toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  if (loading || !user) return null;

  // Group by department
  const byDept = users.reduce((acc, u) => {
    const dept = u.department || 'Khác';
    if (!acc[dept]) acc[dept] = [];
    acc[dept].push(u);
    return acc;
  }, {} as Record<string, User[]>);

  return (
    <Sidebar>
    <div className="p-6 space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Nhân sự</h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">{users.length} nhân viên • {teams.length} đội nhóm</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('list')}
            className="px-3 py-2 rounded-xl text-xs font-medium transition-all"
            style={{
              background: viewMode === 'list' ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
              color: viewMode === 'list' ? 'var(--gold-400)' : 'var(--text-tertiary)',
            }}
          >
            Danh sách
          </button>
          <button
            onClick={() => setViewMode('org')}
            className="px-3 py-2 rounded-xl text-xs font-medium transition-all"
            style={{
              background: viewMode === 'org' ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
              color: viewMode === 'org' ? 'var(--gold-400)' : 'var(--text-tertiary)',
            }}
          >
            Phòng ban
          </button>
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white text-sm font-medium hover:from-[#D4B97E] hover:to-[#C9A96E] transition-all"
          >
            + Thêm nhân viên
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Tổng nhân viên', value: users.length, icon: '👥', color: '#60a5fa' },
          { label: 'Đội nhóm', value: teams.length, icon: '🏢', color: 'var(--gold-400)' },
          { label: 'Phòng ban', value: Object.keys(byDept).length, icon: '📊', color: '#a78bfa' },
          { label: 'Đang hoạt động', value: users.filter(u => u.is_active).length, icon: '✅', color: '#34d399' },
        ].map(card => (
          <div key={card.label} className="rounded-2xl p-4" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{card.icon}</span>
              <span className="text-xs text-[var(--text-muted)]">{card.label}</span>
            </div>
            <p className="text-xl font-bold" style={{ color: card.color }}>{card.value}</p>
          </div>
        ))}
      </div>

      {loadingData ? (
        <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
      ) : viewMode === 'list' ? (
        /* List view */
        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Nhân viên</th>
                <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Vai trò</th>
                <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Phòng ban</th>
                <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Email</th>
                <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">SĐT</th>
                <th className="text-center px-5 py-3 text-[var(--text-tertiary)] font-medium">TT</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const role = ROLE_LABELS[u.role] || { label: u.role, color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' };
                return (
                  <tr
                    key={u.id}
                    className="transition-colors"
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))', color: 'white' }}>
                          {u.full_name?.split(' ').pop()?.charAt(0) || '?'}
                        </div>
                        <span className="font-medium text-[var(--text-primary)]">{u.full_name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: role.bg, color: role.color }}>{role.label}</span>
                    </td>
                    <td className="px-5 py-3.5 text-[var(--text-secondary)]">{DEPT_LABELS[u.department] || u.department}</td>
                    <td className="px-5 py-3.5 text-[var(--text-secondary)]">{u.email}</td>
                    <td className="px-5 py-3.5 text-[var(--text-secondary)]">{u.phone || '—'}</td>
                    <td className="px-5 py-3.5 text-center">
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: u.is_active ? '#34d399' : '#f87171' }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </div>
      ) : (
        /* Org chart view */
        <div className="space-y-6">
          {Object.entries(byDept).map(([dept, members]) => (
            <div key={dept} className="rounded-2xl p-5" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-3 mb-4">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">{DEPT_LABELS[dept] || dept}</h3>
                <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: 'var(--surface-3)', color: 'var(--text-muted)' }}>
                  {members.length} người
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {members.map(u => {
                  const role = ROLE_LABELS[u.role] || { label: u.role, color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' };
                  const team = teams.find(t => t.id === u.team_id);
                  return (
                    <div key={u.id} className="rounded-xl p-4 flex items-center gap-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="w-11 h-11 rounded-xl flex items-center justify-center text-sm font-bold flex-shrink-0" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))', color: 'white' }}>
                        {u.full_name?.split(' ').pop()?.charAt(0) || '?'}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{u.full_name}</p>
                        <p className="text-xs text-[var(--text-muted)]">{role.label}{team ? ` • ${team.name}` : ''}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
    {showCreateForm && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowCreateForm(false)}>
        <div className="glass-card p-6 w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
          <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Thêm nhân viên mới</h3>
          <div className="space-y-3">
            <input placeholder="Họ tên *" value={newUser.full_name} onChange={e => setNewUser({...newUser, full_name: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
            <input placeholder="Email *" value={newUser.email} onChange={e => setNewUser({...newUser, email: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
            <input placeholder="Số điện thoại" value={newUser.phone} onChange={e => setNewUser({...newUser, phone: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
            <input type="password" placeholder="Mật khẩu *" value={newUser.password} onChange={e => setNewUser({...newUser, password: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none" />
            <select value={newUser.role} onChange={e => setNewUser({...newUser, role: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none">
              <option value="data_entry">Nhân viên Sale</option>
              <option value="leader">Trưởng phòng</option>
              <option value="designer">Nhân viên Thiết kế</option>
              <option value="pm">Trưởng Dự án</option>
              <option value="purchasing">Thu mua</option>
              <option value="accountant">Kế toán</option>
              <option value="admin">Giám đốc</option>
              <option value="executive">Ban Quản Trị</option>
            </select>
            <select value={newUser.department} onChange={e => setNewUser({...newUser, department: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none">
              <option value="SALES">Kinh doanh</option>
              <option value="DESIGN">Thiết kế</option>
              <option value="PURCHASING">Thu mua</option>
              <option value="ACCT">Kế toán</option>
              <option value="EXEC">Ban Giám đốc</option>
              <option value="PROJECT">Dự án</option>
            </select>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={() => setShowCreateForm(false)} className="flex-1 py-2 rounded-xl text-sm border border-[var(--border-subtle)] text-[var(--text-secondary)]">Hủy</button>
            <button onClick={async () => {
              if (!newUser.full_name || !newUser.email || !newUser.password) return;
              try {
                await api.createUser({ ...newUser });
                toast('Đã thêm nhân viên mới', 'success');
                setShowCreateForm(false);
                setNewUser({ full_name: '', email: '', phone: '', password: '', role: 'data_entry', department: 'SALES' });
                load();
              } catch (e) {
                toast('Lỗi: ' + (e instanceof Error ? e.message : 'Unknown'), 'error');
              }
            }} className="flex-1 py-2 rounded-xl text-sm bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white font-medium">Thêm</button>
          </div>
        </div>
      </div>
    )}
    </Sidebar>
  );
}
