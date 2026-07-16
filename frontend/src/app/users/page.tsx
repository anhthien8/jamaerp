'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { api, User } from '@/lib/api';
import { getPermissions, getRoleLabel, UserRole } from '@/lib/roles';
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
}

const EMPTY_FORM: FormData = { full_name: '', email: '', password: '', phone: '', role: 'data_entry', department: 'SALES' };

export default function UsersPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
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
  const [error, setError] = useState('');
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

  const openCreate = () => { setForm(EMPTY_FORM); setModal('create'); setError(''); };
  const openEdit = (u: User) => { setForm({ full_name: u.full_name, email: u.email, password: '', phone: u.phone || '', role: u.role as UserRole, department: u.department }); setEditId(u.id); setModal('edit'); setError(''); };
  const openPassword = (u: User) => { setEditId(u.id); setPwForm({ password: '', confirm: '' }); setModal('password'); setError(''); };

  const handleCreate = async () => {
    if (!form.full_name || !form.email || !form.password) { setError('Vui lòng điền đầy đủ'); return; }
    if (form.password.length < 8) { setError('Mật khẩu tối thiểu 8 ký tự'); return; }
    setSaving(true);
    try {
      await api.createUser({ ...form, is_active: true });
      setModal(null);
      loadUsers();
    } catch (e: unknown) { setError((e as Error).message || 'Lỗi tạo user'); }
    setSaving(false);
  };

  const handleEdit = async () => {
    if (!form.full_name) { setError('Tên không được để trống'); return; }
    setSaving(true);
    try {
      await api.updateUser(editId, { full_name: form.full_name, phone: form.phone, role: form.role, department: form.department });
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
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      loadUsers();
    } catch { /* empty */ }
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
            <table className="w-full text-sm">
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
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{u.department}</td>
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
                  <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value as UserRole })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {ROLES.map(r => <option key={r} value={r}>{getRoleLabel(r)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bộ phận</label>
                  <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
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
