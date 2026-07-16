'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, User, Team, extractItems } from '@/lib/api';
import { getPermissions, UserRole } from '@/lib/roles';
import { useToast } from '@/components/ui/Toast';

const ROLE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  admin: { label: 'Giám đốc', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  leader: { label: 'Trưởng phòng', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  executive: { label: 'Ban Quản Trị', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
  data_entry: { label: 'Nhân viên Sale', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  supervisor: { label: 'Giám sát', color: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
  accountant: { label: 'Kế toán / Nhân sự', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
};

const DEPT_LABELS: Record<string, string> = {
  SALES: 'Kinh doanh',
  OPS: 'Giám sát / Vận hành',
  ACCT: 'Kế toán',
  EXEC: 'Ban Giám đốc',
  // giữ chữ thường phòng khi dữ liệu cũ còn lưu lowercase
  sales: 'Kinh doanh', design: 'Thiết kế', construction: 'Thi công',
  accounting: 'Kế toán', management: 'Ban lãnh đạo',
};

interface ResignPreviewData {
  user_name: string;
  leads: Array<{ id: string; name: string; phone: string; stage: string }>;
  tasks: Array<{ id: string; title: string; project_name: string; status: string }>;
  lead_count: number;
  task_count: number;
}

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

  // Resignation flow state
  const [resignTarget, setResignTarget] = useState<User | null>(null);
  const [resignStep, setResignStep] = useState<'preview' | 'confirm'>('preview');
  const [resignPreview, setResignPreview] = useState<ResignPreviewData | null>(null);
  const [resignLoading, setResignLoading] = useState(false);
  const [resignConfirmLoading, setResignConfirmLoading] = useState(false);
  const [transferLeadsTo, setTransferLeadsTo] = useState<string>('');
  const [transferTasksTo, setTransferTasksTo] = useState<string>('');
  const [autoDistribute, setAutoDistribute] = useState(true);

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

  // --- Resignation handlers ---

  const openResignPreview = async (u: User) => {
    setResignTarget(u);
    setResignStep('preview');
    setResignPreview(null);
    setTransferLeadsTo('');
    setTransferTasksTo('');
    setAutoDistribute(true);
    setResignLoading(true);
    try {
      const data = await api.resignPreview(u.id);
      setResignPreview(data);
      setResignStep('confirm');
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không thể tải dữ liệu'}`, 'error');
      setResignTarget(null);
    } finally {
      setResignLoading(false);
    }
  };

  const handleResignConfirm = async () => {
    if (!resignTarget) return;
    setResignConfirmLoading(true);
    try {
      const result = await api.resignUser({
        user_id: resignTarget.id,
        transfer_leads_to: autoDistribute ? undefined : transferLeadsTo || undefined,
        transfer_tasks_to: autoDistribute ? undefined : transferTasksTo || undefined,
      });
      toast(result.message || `Đã xử lý nghỉ việc cho ${resignTarget.full_name}`, 'success');
      closeResignModal();
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không thể thực hiện'}`, 'error');
    } finally {
      setResignConfirmLoading(false);
    }
  };

  const handleUndoResign = async (u: User) => {
    try {
      const result = await api.undoResign(u.id);
      toast(result.message || `Đã hoàn tác nghỉ việc cho ${u.full_name}`, 'success');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không thể hoàn tác'}`, 'error');
    }
  };

  const closeResignModal = () => {
    setResignTarget(null);
    setResignPreview(null);
    setResignStep('preview');
  };

  const handleReactivate = async (u: User) => {
    try {
      await api.updateUser(u.id, { is_active: true });
      toast(`Đã kích hoạt lại ${u.full_name}`, 'success');
      await load();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    }
  };

  const isRecentlyResigned = (u: User): boolean => {
    if (!u.resign_date) return false;
    const resignDate = new Date(u.resign_date);
    const now = new Date();
    const diffDays = (now.getTime() - resignDate.getTime()) / (1000 * 60 * 60 * 24);
    return diffDays <= 7;
  };

  const permissions = user ? getPermissions(user.role as UserRole) : null;

  if (loading || !user) return null;

  // Group by department
  const byDept = users.reduce((acc, u) => {
    const dept = u.department || 'Khác';
    if (!acc[dept]) acc[dept] = [];
    acc[dept].push(u);
    return acc;
  }, {} as Record<string, User[]>);

  // Other active users for transfer dropdowns (exclude resign target)
  const transferableUsers = users.filter(u => u.is_active && u.id !== resignTarget?.id);

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
          {permissions?.canManageUsers && (
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white text-sm font-medium hover:from-[#D4B97E] hover:to-[#C9A96E] transition-all"
            >
              + Thêm nhân viên
            </button>
          )}
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
          {/* Mobile card view */}
          <div className="md:hidden p-3 space-y-3">
            {users.map(u => {
              const role = ROLE_LABELS[u.role] || { label: u.role, color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' };
              return (
                <div key={u.id} className="p-4 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))', color: 'white' }}>
                        {u.full_name?.split(' ').pop()?.charAt(0) || '?'}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{u.full_name}</p>
                        <p className="text-[10px] text-[var(--text-muted)]">{DEPT_LABELS[u.department] || u.department}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: u.is_active ? '#34d399' : '#f87171' }} />
                      <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: role.bg, color: role.color }}>{role.label}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-[var(--text-muted)] mb-2">
                    <span>{u.email}</span>
                  </div>
                  <div className="flex items-center justify-end gap-2 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    {permissions?.canManageUsers && u.id !== user?.id && (
                      u.is_active ? (
                        isRecentlyResigned(u) ? (
                          <button
                            onClick={() => handleUndoResign(u)}
                            className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
                            title="Hoàn tác nghỉ việc"
                          >
                            Hoàn tác
                          </button>
                        ) : (
                          <button
                            onClick={() => openResignPreview(u)}
                            className="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                            title="Nghỉ việc"
                          >
                            Nghỉ việc
                          </button>
                        )
                      ) : (
                        <button
                          onClick={() => handleReactivate(u)}
                          className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                          title="Kích hoạt lại"
                        >
                          Kích hoạt
                        </button>
                      )
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {/* Desktop table view */}
          <div className="hidden md:block overflow-x-auto">
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
                      <div className="flex items-center justify-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: u.is_active ? '#34d399' : '#f87171' }} />
                        {permissions?.canManageUsers && u.id !== user?.id && (
                          u.is_active ? (
                            isRecentlyResigned(u) ? (
                              <button
                                onClick={() => handleUndoResign(u)}
                                className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
                                title="Hoàn tác nghỉ việc"
                              >
                                Hoàn tác
                              </button>
                            ) : (
                              <button
                                onClick={() => openResignPreview(u)}
                                className="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                                title="Nghỉ việc"
                              >
                                Nghỉ việc
                              </button>
                            )
                          ) : (
                            <button
                              onClick={() => handleReactivate(u)}
                              className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                              title="Kích hoạt lại"
                            >
                              Kích hoạt
                            </button>
                          )
                        )}
                      </div>
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

    {/* Create User Modal */}
    {showCreateForm && permissions?.canManageUsers && (
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
              <option value="supervisor">Giám sát (Thiết kế / Thu mua / Dự án)</option>
              <option value="accountant">Kế toán / Nhân sự</option>
              <option value="admin">Giám đốc</option>
              <option value="executive">Ban Quản Trị</option>
            </select>
            <select value={newUser.department} onChange={e => setNewUser({...newUser, department: e.target.value})} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none">
              <option value="SALES">Kinh doanh</option>
              <option value="OPS">Giám sát / Vận hành</option>
              <option value="ACCT">Kế toán</option>
              <option value="EXEC">Ban Giám đốc</option>
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

    {/* Resignation Modal */}
    {resignTarget && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={closeResignModal}>
        <div className="glass-card p-6 w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>

          {/* Loading state */}
          {resignLoading && (
            <div className="text-center py-8">
              <div className="inline-block w-8 h-8 border-2 border-[var(--border-subtle)] border-t-[var(--gold-400)] rounded-full animate-spin mb-3" />
              <p className="text-sm text-[var(--text-secondary)]">Đang tải dữ liệu chuyển giao...</p>
            </div>
          )}

          {/* Confirm step */}
          {!resignLoading && resignPreview && resignStep === 'confirm' && (
            <>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))', color: 'white' }}>
                  {resignPreview.user_name?.split(' ').pop()?.charAt(0) || '?'}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-[var(--text-primary)]">Nghỉ việc — {resignPreview.user_name}</h3>
                  <p className="text-xs text-[var(--text-muted)]">Xác nhận chuyển giao dữ liệu trước khi nghỉ</p>
                </div>
              </div>

              {/* Leads section */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">Leads cần chuyển giao</span>
                  <span className="text-xs px-2 py-0.5 rounded-lg font-medium" style={{ background: 'rgba(96,165,250,0.1)', color: '#60a5fa' }}>
                    {resignPreview.lead_count} leads
                  </span>
                </div>
                {resignPreview.leads.length > 0 ? (
                  <div className="max-h-32 overflow-y-auto rounded-xl space-y-1" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    {resignPreview.leads.map(lead => (
                      <div key={lead.id} className="flex items-center justify-between px-3 py-1.5 text-xs">
                        <span className="text-[var(--text-primary)] truncate">{lead.name}</span>
                        <span className="text-[var(--text-muted)] ml-2 flex-shrink-0">{lead.stage}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)] italic">Không có leads nào</p>
                )}
              </div>

              {/* Tasks section */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">Tasks cần chuyển giao</span>
                  <span className="text-xs px-2 py-0.5 rounded-lg font-medium" style={{ background: 'rgba(251,191,36,0.1)', color: '#fbbf24' }}>
                    {resignPreview.task_count} tasks
                  </span>
                </div>
                {resignPreview.tasks.length > 0 ? (
                  <div className="max-h-32 overflow-y-auto rounded-xl space-y-1" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    {resignPreview.tasks.map(task => (
                      <div key={task.id} className="flex items-center justify-between px-3 py-1.5 text-xs">
                        <span className="text-[var(--text-primary)] truncate">{task.title}</span>
                        <span className="text-[var(--text-muted)] ml-2 flex-shrink-0">{task.project_name}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)] italic">Không có tasks nào</p>
                )}
              </div>

              {/* Auto distribute toggle */}
              <div className="mb-4 p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoDistribute}
                    onChange={e => setAutoDistribute(e.target.checked)}
                    className="w-4 h-4 rounded accent-[var(--gold-400)]"
                  />
                  <span className="text-sm text-[var(--text-primary)]">Tự động phân bổ đều</span>
                </label>
                <p className="text-[10px] text-[var(--text-muted)] mt-1 ml-6">Hệ thống sẽ tự động phân bổ leads và tasks cho các nhân viên còn lại</p>
              </div>

              {/* Manual transfer dropdowns */}
              {!autoDistribute && (
                <div className="space-y-3 mb-4">
                  {resignPreview.lead_count > 0 && (
                    <div>
                      <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">Chuyển leads cho</label>
                      <select
                        value={transferLeadsTo}
                        onChange={e => setTransferLeadsTo(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none"
                      >
                        <option value="">-- Chọn nhân viên --</option>
                        {transferableUsers.map(u => (
                          <option key={u.id} value={u.id}>{u.full_name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  {resignPreview.task_count > 0 && (
                    <div>
                      <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">Chuyển tasks cho</label>
                      <select
                        value={transferTasksTo}
                        onChange={e => setTransferTasksTo(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none"
                      >
                        <option value="">-- Chọn nhân viên --</option>
                        {transferableUsers.map(u => (
                          <option key={u.id} value={u.id}>{u.full_name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}

              {/* Warning */}
              <div className="mb-4 px-3 py-2 rounded-xl text-xs" style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.15)' }}>
                <span className="text-amber-400">Lưu ý:</span>{' '}
                <span className="text-[var(--text-secondary)]">Sau khi xác nhận, có thể hoàn tác trong 7 ngày</span>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={closeResignModal}
                  className="flex-1 py-2.5 rounded-xl text-sm border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-white/5 transition-colors"
                >
                  Hủy
                </button>
                <button
                  onClick={handleResignConfirm}
                  disabled={resignConfirmLoading}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)', color: 'white' }}
                >
                  {resignConfirmLoading && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {resignConfirmLoading ? 'Đang xử lý...' : 'Xác nhận nghỉ việc'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    )}
    </Sidebar>
  );
}
