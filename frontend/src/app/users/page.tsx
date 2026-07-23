'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { api, SalaryGrade, User } from '@/lib/api';
import { getPermissions, getEffectivePermissions, getRoleLabel, ALL_PERMISSION_KEYS, UserRole } from '@/lib/roles';
import { labelOf, ROLE_LABELS, DEPARTMENT_LABELS } from '@/lib/labels';
import { useToast } from '@/components/ui/Toast';
import Sidebar from '@/components/layout/Sidebar';

const ROLES: UserRole[] = ['admin', 'executive', 'leader', 'data_entry', 'accountant', 'supervisor'];
const DEPARTMENTS = ['EXEC', 'SALES', 'OPS', 'ACCT'];

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-500/15 text-red-400 border-red-500/25',
  executive: 'bg-purple-500/15 text-purple-400 border-purple-500/25',
  leader: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  data_entry: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  accountant: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  supervisor: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/25',
};

interface FormData {
  full_name: string;
  email: string;
  password: string;
  phone: string;
  role: UserRole;
  department: string;
  /** Cấu hình lương — không gán bậc thì payroll sinh 0đ (audit 22/07) */
  salary_grade_id: string;
  dependents_count: string;
}

const EMPTY_FORM: FormData = { full_name: '', email: '', password: '', phone: '', role: 'data_entry', department: 'SALES', salary_grade_id: '', dependents_count: '0' };

export default function UsersPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading2, setLoading2] = useState(true);
  const [modal, setModal] = useState<'create' | 'edit' | 'password' | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [editId, setEditId] = useState('');
  const [pwForm, setPwForm] = useState({ password: '', confirm: '' });
  const [saving, setSaving] = useState(false);
  const [grades, setGrades] = useState<SalaryGrade[]>([]);
  const [error, setError] = useState('');
  // Per-user permission overrides
  const [customPerms, setCustomPerms] = useState<Record<string, boolean>>({});
  const [customPermsLoaded, setCustomPermsLoaded] = useState(false);
  const pageSize = 20;

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !getPermissions(user.role as UserRole).canManageUsers) router.push('/');
  }, [user, loading, router]);

  const loadUsers = useCallback(async () => {
    setLoading2(true);
    try {
      const params: Record<string, string> = { page: String(page), page_size: String(pageSize) };
      if (roleFilter) params.role = roleFilter;
      const res = await api.getUsers(params);
      let filtered = res.items || [];
      if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(u => u.full_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
      }
      setUsers(filtered);
      setTotal(res.total || 0);
    } catch { /* empty */ }
    setLoading2(false);
  }, [page, roleFilter, search]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const openCreate = () => { setForm(EMPTY_FORM); setModal('create'); setError(''); setCustomPerms({}); setCustomPermsLoaded(false); };
  const openEdit = (u: User) => {
    setForm({ full_name: u.full_name, email: u.email, password: '', phone: u.phone || '', role: u.role as UserRole, department: u.department, salary_grade_id: u.salary_grade_id || '', dependents_count: String(u.dependents_count ?? 0) });
    setEditId(u.id); setModal('edit'); setError('');
    // Load salary grades and custom permissions
    api.getSalaryGrades().then(setGrades).catch(() => setGrades([]));
    api.getUserPermissions(u.id).then(res => {
      setCustomPerms(res.custom_permissions || {});
      setCustomPermsLoaded(true);
    }).catch(() => { setCustomPerms({}); setCustomPermsLoaded(true); });
  };
  const openPassword = (u: User) => { setEditId(u.id); setPwForm({ password: '', confirm: '' }); setModal('password'); setError(''); };

  const handleCreate = async () => {
    if (!form.full_name || !form.email || !form.password) { setError('Vui lòng điền đầy đủ'); return; }
    if (form.password.length < 8) { setError('Mật khẩu tối thiểu 8 ký tự'); return; }
    setSaving(true);
    try {
      // Tách 2 trường lương (string trong form) — gán bậc lương làm ở bước Sửa sau khi tạo
      const { salary_grade_id: _sg, dependents_count: _dc, ...createPayload } = form;
      await api.createUser({ ...createPayload, is_active: true });
      setModal(null);
      loadUsers();
    } catch (e: unknown) { setError((e as Error).message || 'Lỗi tạo user'); }
    setSaving(false);
  };

  const handleEdit = async () => {
    if (!form.full_name) { setError('Tên không được để trống'); return; }
    setSaving(true);
    try {
      await api.updateUser(editId, {
        full_name: form.full_name, phone: form.phone, role: form.role, department: form.department,
        salary_grade_id: form.salary_grade_id || null,
        dependents_count: Number(form.dependents_count) || 0,
      });
      // Save custom permissions if any changes were made
      if (customPermsLoaded && isAdmin) {
        await api.setUserPermissions(editId, customPerms);
      }
      setModal(null);
      loadUsers();
    } catch (e: unknown) { setError((e as Error).message || 'Lỗi cập nhật'); }
    setSaving(false);
  };

  const handlePassword = async () => {
    if (!pwForm.password || pwForm.password.length < 8) { setError('Mật khẩu tối thiểu 8 ký tự'); return; }
    if (pwForm.password !== pwForm.confirm) { setError('Mật khẩu xác nhận không khớp'); return; }
    setSaving(true);
    try {
      await api.updateUser(editId, { password: pwForm.password } as Partial<User>);
      setModal(null);
    } catch (e: unknown) { setError((e as Error).message || 'Lỗi đổi mật khẩu'); }
    setSaving(false);
  };

  const handleToggleActive = async (u: User) => {
    if (!isAdmin) return;
    const next = !u.is_active;
    // Optimistic: lật ngay trên UI để phản hồi tức thì (kể cả Chế độ Tập luyện dùng dữ liệu tĩnh)
    setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: next } : x));
    try {
      await api.updateUser(u.id, { is_active: next });
    } catch (e) {
      // Lỗi → hoàn tác + báo bằng toast (trước đây set vào state error nhưng không render → trông như "không bấm được")
      setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: u.is_active } : x));
      toast((e as Error).message || 'Không đổi được trạng thái tài khoản', 'error');
    }
  };

  if (!user) return null;

  return (
    <Sidebar>
      <div className="p-4 lg:p-6 max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Quản lý tài khoản</h1>
            <p className="text-sm text-[var(--text-muted)] mt-0.5">{total} tài khoản trong hệ thống</p>
          </div>
          {isAdmin && (
            <button onClick={openCreate} className="px-4 py-2 rounded-xl text-sm font-semibold text-white" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
              + Tạo tài khoản
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <input
            type="text"
            placeholder="Tìm theo tên hoặc email..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            className="flex-1 px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)] placeholder:text-[var(--text-disabled)]"
          />
          <select
            value={roleFilter}
            onChange={e => { setRoleFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
          >
            <option value="">Tất cả vai trò</option>
            {ROLES.map(r => <option key={r} value={r}>{getRoleLabel(r)}</option>)}
          </select>
        </div>

        {/* Table */}
        <div className="rounded-2xl border overflow-hidden" style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-1)' }}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm hidden md:table">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <th className="text-left px-4 py-3 font-medium text-[var(--text-muted)]">Họ tên</th>
                  <th className="text-left px-4 py-3 font-medium text-[var(--text-muted)]">Email</th>
                  <th className="text-left px-4 py-3 font-medium text-[var(--text-muted)]">Vai trò</th>
                  <th className="text-left px-4 py-3 font-medium text-[var(--text-muted)]">Bộ phận</th>
                  <th className="text-center px-4 py-3 font-medium text-[var(--text-muted)]">Trạng thái</th>
                  {isAdmin && <th className="text-right px-4 py-3 font-medium text-[var(--text-muted)]">Thao tác</th>}
                </tr>
              </thead>
              <tbody>
                {loading2 ? (
                  <tr><td colSpan={6} className="text-center py-8 text-[var(--text-muted)]">Đang tải...</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-8 text-[var(--text-muted)]">Không tìm thấy tài khoản</td></tr>
                ) : users.map(u => (
                  <tr key={u.id} className="border-b last:border-0 hover:bg-[var(--surface-2)] transition-colors" style={{ borderColor: 'var(--border-subtle)' }}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))' }}>
                          {u.full_name?.split(' ').pop()?.charAt(0) || '?'}
                        </div>
                        <span className="font-medium text-[var(--text-primary)]">{u.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-lg text-xs font-medium border ${ROLE_COLORS[u.role] || 'bg-gray-500/15 text-gray-400 border-gray-500/25'}`}>
                        {getRoleLabel(u.role as UserRole)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{labelOf(DEPARTMENT_LABELS, u.department)}</td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => isAdmin && handleToggleActive(u)}
                        disabled={!isAdmin}
                        className={`w-10 h-5 rounded-full transition-colors relative ${u.is_active ? 'bg-emerald-500' : 'bg-gray-600'} ${isAdmin ? 'cursor-pointer' : 'cursor-default'}`}
                      >
                        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${u.is_active ? 'translate-x-5' : 'translate-x-0.5'}`} />
                      </button>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => openEdit(u)} className="px-2 py-1 rounded-lg text-xs text-[var(--text-muted)] hover:bg-[var(--surface-3)] transition-colors">Sửa</button>
                          <button onClick={() => openPassword(u)} className="px-2 py-1 rounded-lg text-xs text-amber-400 hover:bg-amber-500/10 transition-colors">Mật khẩu</button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile: danh sách thẻ (bảng ẩn dưới md nên cần bản thẻ đủ thao tác) */}
          <div className="md:hidden">
            {loading2 ? (
              <p className="text-center py-8 text-sm text-[var(--text-muted)]">Đang tải...</p>
            ) : users.length === 0 ? (
              <p className="text-center py-8 text-sm text-[var(--text-muted)]">Không tìm thấy tài khoản</p>
            ) : users.map(u => (
              <div key={u.id} className="p-4 border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0" style={{ background: 'linear-gradient(135deg, var(--navy-600), var(--navy-700))' }}>
                      {u.full_name?.split(' ').pop()?.charAt(0) || '?'}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-[var(--text-primary)] truncate">{u.full_name}</p>
                      <p className="text-xs text-[var(--text-muted)] truncate">{u.email}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => isAdmin && handleToggleActive(u)}
                    disabled={!isAdmin}
                    aria-label={u.is_active ? 'Tắt tài khoản' : 'Bật tài khoản'}
                    className={`flex items-center justify-center h-10 w-14 flex-shrink-0 ${isAdmin ? 'cursor-pointer' : 'cursor-default'}`}
                  >
                    <span className={`relative w-11 h-6 rounded-full transition-colors ${u.is_active ? 'bg-emerald-500' : 'bg-gray-600'}`}>
                      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${u.is_active ? 'translate-x-5' : 'translate-x-0.5'}`} />
                    </span>
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className={`inline-block px-2 py-0.5 rounded-lg text-xs font-medium border ${ROLE_COLORS[u.role] || 'bg-gray-500/15 text-gray-400 border-gray-500/25'}`}>
                    {labelOf(ROLE_LABELS, u.role)}
                  </span>
                  <span className="inline-block px-2 py-0.5 rounded-lg text-xs font-medium border bg-[var(--surface-2)] text-[var(--text-secondary)]" style={{ borderColor: 'var(--border-subtle)' }}>
                    {labelOf(DEPARTMENT_LABELS, u.department)}
                  </span>
                </div>
                {isAdmin && (
                  <div className="flex gap-2 mt-3">
                    <button onClick={() => openEdit(u)} className="flex-1 min-h-[40px] rounded-xl text-sm font-medium text-[var(--text-secondary)] bg-[var(--surface-2)] hover:bg-[var(--surface-3)] transition-colors">
                      Sửa
                    </button>
                    <button onClick={() => openPassword(u)} className="flex-1 min-h-[40px] rounded-xl text-sm font-medium text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 transition-colors">
                      Mật khẩu
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {total > pageSize && (
            <div className="flex items-center justify-between px-4 py-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
              <span className="text-xs text-[var(--text-muted)]">Trang {page} / {Math.ceil(total / pageSize)}</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 rounded-lg text-xs bg-[var(--surface-2)] text-[var(--text-secondary)] disabled:opacity-40">Trước</button>
                <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / pageSize)} className="px-3 py-1 rounded-lg text-xs bg-[var(--surface-2)] text-[var(--text-secondary)] disabled:opacity-40">Sau</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Create / Edit */}
      {modal && (modal === 'create' || modal === 'edit') && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setModal(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl p-6 bg-[var(--surface-1)] border border-[var(--border-subtle)] shadow-2xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">{modal === 'create' ? 'Tạo tài khoản mới' : 'Chỉnh sửa tài khoản'}</h2>
            {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Họ tên *</label>
                <input value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Email *</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} disabled={modal === 'edit'} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)] disabled:opacity-50" />
              </div>
              {modal === 'create' && (
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Mật khẩu * (tối thiểu 8 ký tự)</label>
                  <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Số điện thoại</label>
                <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Vai trò</label>
                  <select value={form.role} onChange={e => {
                    const newRole = e.target.value as UserRole;
                    const defaultDept: Record<string, string> = {
                      admin: 'EXEC', executive: 'EXEC', leader: 'SALES',
                      data_entry: 'SALES', accountant: 'ACCT', supervisor: 'OPS',
                    };
                    setForm({ ...form, role: newRole, department: defaultDept[newRole] || form.department });
                  }} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {ROLES.map(r => <option key={r} value={r}>{getRoleLabel(r)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bộ phận</label>
                  <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {DEPARTMENTS.map(d => <option key={d} value={d}>{labelOf(DEPARTMENT_LABELS, d)}</option>)}
                  </select>
                </div>
              </div>
              {modal === 'edit' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bậc lương</label>
                    <select value={form.salary_grade_id} onChange={e => setForm({ ...form, salary_grade_id: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                      <option value="">Chưa gán (lương = 0)</option>
                      {grades.map(g => <option key={g.id} value={g.id}>{g.grade_name} — {(g.base_salary / 1_000_000).toLocaleString('vi-VN')}tr</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Người phụ thuộc (giảm trừ thuế)</label>
                    <input type="number" min={0} max={20} value={form.dependents_count} onChange={e => setForm({ ...form, dependents_count: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
                  </div>
                </div>
              )}
              {/* Per-user permission overrides (admin only) */}
              {modal === 'edit' && isAdmin && customPermsLoaded && (
                <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-semibold text-[var(--text-primary)]">Phân quyền tùy chỉnh</h3>
                    <button
                      type="button"
                      onClick={() => setCustomPerms({})}
                      className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] underline"
                    >
                      Xóa tất cả (dùng mặc định vai trò)
                    </button>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] mb-2">
                    Bỏ chọn = tắt quyền, chọn = bật. Chỉ quyền thay đổi so với vai trò mặc định sẽ được lưu.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 max-h-48 overflow-y-auto pr-1">
                    {ALL_PERMISSION_KEYS.map(({ key, label }) => {
                      const roleDefault = getPermissions(form.role as UserRole);
                      const defaultVal = Boolean(roleDefault[key]);
                      const currentVal = key in customPerms ? customPerms[key] : defaultVal;
                      const isOverridden = key in customPerms;
                      return (
                        <label
                          key={key}
                          className={`flex items-center gap-1.5 py-0.5 px-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                            currentVal
                              ? isOverridden ? 'bg-emerald-500/10' : 'bg-[var(--surface-2)]'
                              : isOverridden ? 'bg-red-500/10' : 'bg-[var(--surface-2)] opacity-60'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={currentVal}
                            onChange={() => {
                              setCustomPerms(prev => {
                                const next = { ...prev };
                                const newVal = !currentVal;
                                if (newVal === defaultVal) {
                                  // Reset to role default — remove override
                                  delete next[key];
                                } else {
                                  next[key] = newVal;
                                }
                                return next;
                              });
                            }}
                            className="w-3.5 h-3.5 rounded accent-emerald-500"
                          />
                          <span className={`truncate ${isOverridden ? 'font-medium' : ''}`}>{label}</span>
                          {isOverridden && (
                            <span className={`ml-auto text-[9px] px-1 rounded ${currentVal ? 'text-emerald-400' : 'text-red-400'}`}>
                              {currentVal ? 'BẬT' : 'TẮT'}
                            </span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)]">Hủy</button>
              <button onClick={modal === 'create' ? handleCreate : handleEdit} disabled={saving} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                {saving ? 'Đang lưu...' : modal === 'create' ? 'Tạo' : 'Lưu'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Change Password */}
      {modal === 'password' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setModal(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-sm rounded-2xl p-6 bg-[var(--surface-1)] border border-[var(--border-subtle)] shadow-2xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">Đổi mật khẩu</h2>
            {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Mật khẩu mới * (tối thiểu 8 ký tự)</label>
                <input type="password" value={pwForm.password} onChange={e => setPwForm({ ...pwForm, password: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" autoFocus />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Xác nhận mật khẩu</label>
                <input type="password" value={pwForm.confirm} onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)]">Hủy</button>
              <button onClick={handlePassword} disabled={saving} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50 bg-amber-600 hover:bg-amber-700">
                {saving ? 'Đang lưu...' : 'Đổi mật khẩu'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Sidebar>
  );
}
