'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { api, SalaryGrade, Team, User } from '@/lib/api';
import { getPermissions, getEffectivePermissions, getRoleLabel, ALL_PERMISSION_KEYS, UserRole } from '@/lib/roles';
import { labelOf, ROLE_LABELS, DEPARTMENT_LABELS } from '@/lib/labels';
import { useToast } from '@/components/ui/Toast';
import Sidebar from '@/components/layout/Sidebar';

interface CustomRole {
  role_key: string;
  role_name: string;
  department: string;
  permissions: Record<string, boolean>;
}

// 'executive' bị bỏ khỏi dropdown từ 13/08/2026 — không ai mang vai trò này (backend
// vẫn nhận để tương thích tài khoản cũ nếu có). DESIGN/PURCHASING thêm cùng đợt
// 4 vai trò phòng ban (Thiết kế, Thu mua) để gán đúng phòng cho nhân sự mới.
const BUILTIN_ROLES: UserRole[] = ['admin', 'leader', 'data_entry', 'accountant', 'supervisor'];
const DEPARTMENTS = ['EXEC', 'SALES', 'DESIGN', 'OPS', 'PURCHASING', 'ACCT'];

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
  role: string;
  department: string;
  /** Cấu hình lương — không gán bậc thì payroll sinh 0đ (audit 22/07) */
  salary_grade_id: string;
  dependents_count: string;
  team_id: string;
}

const EMPTY_FORM: FormData = { full_name: '', email: '', password: '', phone: '', role: 'data_entry', department: 'SALES', salary_grade_id: '', dependents_count: '0', team_id: '' };

export default function UsersPage() {
  const router = useRouter();
  const { user, loading, effectivePermissions, permsReady } = useAuth();
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
  // Custom roles
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([]);
  const [roleModal, setRoleModal] = useState(false);
  const [roleForm, setRoleForm] = useState({ role_key: '', role_name: '', department: 'SALES' });
  const [rolePerms, setRolePerms] = useState<Record<string, boolean>>(() => {
    const all: Record<string, boolean> = {};
    ALL_PERMISSION_KEYS.forEach(k => { all[k.key] = true; });
    return all;
  });
  const [roleSaving, setRoleSaving] = useState(false);
  const [roleError, setRoleError] = useState('');
  // Per-user permission overrides
  const [customPerms, setCustomPerms] = useState<Record<string, boolean>>({});
  const [customPermsLoaded, setCustomPermsLoaded] = useState(false);
  // Đội nhóm — tạo/sửa đội, chọn trưởng nhóm, xếp thành viên
  const [teams, setTeams] = useState<Team[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]); // đủ toàn bộ nhân sự cho modal đội (bảng chính phân trang 20)
  const [teamModal, setTeamModal] = useState<'create' | 'edit' | null>(null);
  const [teamForm, setTeamForm] = useState({ name: '', code: '', department: 'SALES', leader_id: '' });
  const [teamMemberIds, setTeamMemberIds] = useState<Set<string>>(new Set());
  const [teamEditId, setTeamEditId] = useState('');
  const [teamSaving, setTeamSaving] = useState(false);
  const [teamError, setTeamError] = useState('');
  const pageSize = 20;

  const isAdmin = user?.role === 'admin';
  const canManageTeams = Boolean(effectivePermissions.canManageUsers);

  /** Get display label for built-in or custom roles */
  const getAnyRoleLabel = (roleKey: string): string => {
    const custom = customRoles.find(r => r.role_key === roleKey);
    if (custom) return custom.role_name;
    return getRoleLabel(roleKey as UserRole);
  };

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    // Gate theo quyền HIỆU LỰC (backend) và chỉ sau khi quyền đã chốt (permsReady) —
    // vai trò tùy chỉnh lúc mới vào chỉ có mặc định cục bộ, redirect sớm là đá nhầm.
    // Trang này mở cho ai có «Quản lý Users» hoặc «Xem Nhân sự» (khớp gate GET /users).
    if (!loading && permsReady && user
        && !effectivePermissions.canManageUsers && !effectivePermissions.canViewHR) {
      router.push('/');
    }
  }, [user, loading, permsReady, effectivePermissions, router]);

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

  // Load custom roles on mount
  useEffect(() => {
    api.getCustomRoles().then(res => setCustomRoles(res.roles || [])).catch(() => {});
  }, []);

  // Đội nhóm: danh sách đội cho cột «Đội» (mọi người xem được);
  // full nhân sự chỉ tải khi có quyền quản lý (cần cho modal xếp thành viên)
  const loadTeamsData = useCallback(async () => {
    api.getTeams().then(setTeams).catch(() => {});
    if (canManageTeams) {
      api.getUsers({ page_size: '500' }).then(res => {
        setAllUsers(res.items || []);
        // Quá trần 1 trang → danh sách tick thành viên thiếu người, lưu sẽ gỡ nhầm
        if ((res.total ?? 0) > (res.items || []).length) {
          toast('Hệ thống vượt 500 nhân sự — danh sách xếp đội đang thiếu người, cần nâng cấp trước khi lưu đội', 'error');
        }
      }).catch(() => {
        // Nuốt lỗi im lặng làm modal treo «Đang tải...» vô hạn (review 14/08)
        toast('Không tải được danh sách nhân sự cho xếp đội — thử tải lại trang', 'error');
      });
    }
  }, [canManageTeams, toast]);
  useEffect(() => { if (user && permsReady) loadTeamsData(); }, [user, permsReady, loadTeamsData]);

  const openCreate = () => { setForm(EMPTY_FORM); setModal('create'); setError(''); setCustomPerms({}); setCustomPermsLoaded(false); };
  const openEdit = (u: User) => {
    setForm({ full_name: u.full_name, email: u.email, password: '', phone: u.phone || '', role: u.role, department: u.department, salary_grade_id: u.salary_grade_id || '', dependents_count: String(u.dependents_count ?? 0), team_id: u.team_id || '' });
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
      // Tách 2 trường lương (string trong form) — gán bậc lương làm ở bước Sửa sau khi tạo.
      // team_id cũng bỏ: xếp đội làm ở khối «Đội nhóm» hoặc bước Sửa (tránh gửi chuỗi rỗng).
      const { salary_grade_id: _sg, dependents_count: _dc, team_id: _t, ...createPayload } = form;
      await api.createUser({ ...createPayload, is_active: true });
      setModal(null);
      loadUsers();
      loadTeamsData(); // đồng bộ allUsers — tránh modal đội dùng danh sách cũ gỡ nhầm người mới
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
        team_id: form.team_id || null,
      });
      // Save custom permissions if any changes were made
      if (customPermsLoaded && isAdmin) {
        await api.setUserPermissions(editId, customPerms);
      }
      setModal(null);
      loadUsers();
      loadTeamsData(); // đồng bộ allUsers/teams — sửa hồ sơ có thể đổi đội, sĩ số phải khớp
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
      loadTeamsData(); // người nghỉ/làm lại đổi trạng thái tick trong modal đội
    } catch (e) {
      // Lỗi → hoàn tác + báo bằng toast (trước đây set vào state error nhưng không render → trông như "không bấm được")
      setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: u.is_active } : x));
      toast((e as Error).message || 'Không đổi được trạng thái tài khoản', 'error');
    }
  };

  const openRoleModal = () => {
    setRoleForm({ role_key: '', role_name: '', department: 'SALES' });
    const all: Record<string, boolean> = {};
    ALL_PERMISSION_KEYS.forEach(k => { all[k.key] = true; });
    setRolePerms(all);
    setRoleError('');
    setRoleModal(true);
  };

  const handleCreateRole = async () => {
    if (!roleForm.role_key.trim() || !roleForm.role_name.trim()) {
      setRoleError('Vui lòng điền tên vai trò và key'); return;
    }
    setRoleSaving(true);
    try {
      const res = await api.createCustomRole({
        role_key: roleForm.role_key.trim().toLowerCase().replace(/\s+/g, '_'),
        role_name: roleForm.role_name.trim(),
        department: roleForm.department,
        permissions: rolePerms,
      });
      setCustomRoles(prev => [...prev, res.role]);
      // Auto-select the new role and fill department
      setForm(f => ({ ...f, role: res.role.role_key, department: res.role.department }));
      setRoleModal(false);
    } catch (e: unknown) {
      setRoleError((e as Error).message || 'Lỗi tạo vai trò');
    }
    setRoleSaving(false);
  };

  // ===== Đội nhóm =====
  const openTeamCreate = () => {
    setTeamForm({ name: '', code: '', department: 'SALES', leader_id: '' });
    setTeamMemberIds(new Set());
    setTeamEditId(''); setTeamError(''); setTeamModal('create');
  };
  const openTeamEdit = (t: Team) => {
    setTeamForm({ name: t.name, code: t.code, department: t.department, leader_id: t.leader_id || '' });
    // Chỉ seed người CÒN LÀM VIỆC — seed cả người nghỉ thì không có checkbox để bỏ tick,
    // lưu lần nào cũng 400 «người đã nghỉ việc» (review 14/08). Người nghỉ vẫn giữ
    // nhãn đội phía backend, không bị đụng khi lưu roster.
    setTeamMemberIds(new Set(allUsers.filter(u => u.team_id === t.id && u.is_active).map(u => u.id)));
    setTeamEditId(t.id); setTeamError(''); setTeamModal('edit');
  };

  const handleTeamSave = async () => {
    if (!teamForm.name.trim()) { setTeamError('Tên đội không được để trống'); return; }
    if (teamModal === 'create' && !teamForm.code.trim()) { setTeamError('Mã đội không được để trống (VD: SALE-A)'); return; }
    setTeamSaving(true);
    try {
      let teamId = teamEditId;
      if (teamModal === 'create') {
        const created = await api.createTeam({
          name: teamForm.name.trim(),
          code: teamForm.code.trim().toUpperCase(),
          department: teamForm.department,
          leader_id: teamForm.leader_id || null,
        });
        teamId = created.id;
        // Đội đã tạo xong trên server — chuyển modal sang chế độ sửa NGAY để nếu bước
        // xếp thành viên lỗi, bấm Lưu lại đi đường update (không tạo trùng «Mã đội đã tồn tại»)
        setTeamEditId(created.id);
        setTeamModal('edit');
        loadTeamsData();
      } else {
        await api.updateTeam(teamId, {
          name: teamForm.name.trim(),
          department: teamForm.department,
          leader_id: teamForm.leader_id || null,
        });
      }
      // Gửi danh sách ĐẦY ĐỦ thành viên — backend tự giữ trưởng nhóm nếu thiếu
      await api.setTeamMembers(teamId, Array.from(teamMemberIds));
      setTeamModal(null);
      await Promise.all([loadTeamsData(), loadUsers()]);
      toast('Đã lưu đội nhóm', 'success');
    } catch (e: unknown) { setTeamError((e as Error).message || 'Lỗi lưu đội nhóm'); }
    setTeamSaving(false);
  };

  const handleTeamDelete = async () => {
    const t = teams.find(x => x.id === teamEditId);
    // Vừa tạo đội xong mà getTeams chưa kịp về thì đừng câm lặng (phản biện vá 14/08)
    if (!t) { toast('Danh sách đội chưa tải xong — chờ vài giây rồi thử lại', 'error'); return; }
    const ok = window.confirm(
      `Giải tán đội ${t.name}? ${t.member_count ?? 0} thành viên sẽ về «chưa xếp đội», `
      + 'data đang gắn nhãn đội chỉ mất nhãn (người phụ trách giữ nguyên). Không hoàn tác được.'
    );
    if (!ok) return;
    setTeamSaving(true);
    try {
      await api.deleteTeam(teamEditId);
      setTeamModal(null);
      await Promise.all([loadTeamsData(), loadUsers()]);
      toast(`Đã giải tán đội ${t.name}`, 'success');
    } catch (e: unknown) { setTeamError((e as Error).message || 'Lỗi giải tán đội'); }
    setTeamSaving(false);
  };

  // Ứng viên trưởng nhóm: đang hoạt động + vai trò trưởng (leader hệ thống / sale_leader tùy chỉnh);
  // giữ cả trưởng nhóm hiện tại để select không rơi về rỗng nếu vai trò của họ đã bị đổi
  const leaderOptions = allUsers.filter(u =>
    (u.is_active && (u.role === 'leader' || u.role === 'sale_leader')
      // Đang lãnh đội KHÁC thì ẩn khỏi lựa chọn — backend cũng chặn, tránh chọn xong mới 400
      && !teams.some(t => t.leader_id === u.id && t.id !== teamEditId))
    || u.id === teamForm.leader_id
  );
  // Danh sách tick thành viên: bỏ admin (không xếp đội), người cùng bộ phận với đội lên trước
  const memberCandidates = [...allUsers]
    .filter(u => u.is_active && u.role !== 'admin')
    .sort((a, b) => {
      const ad = a.department === teamForm.department ? 0 : 1;
      const bd = b.department === teamForm.department ? 0 : 1;
      return ad !== bd ? ad - bd : a.full_name.localeCompare(b.full_name, 'vi');
    });

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
            {BUILTIN_ROLES.map(r => <option key={r} value={r}>{getRoleLabel(r)}</option>)}
            {customRoles.length > 0 && <option disabled className="text-[var(--text-muted)]">── Tùy chỉnh ──</option>}
            {customRoles.map(r => <option key={r.role_key} value={r.role_key}>{r.role_name}</option>)}
          </select>
        </div>

        {/* Đội nhóm — trưởng nhóm chỉ thấy & được giao data trong đội mình (luồng chia data 14/08) */}
        {canManageTeams && (
          <div className="mb-4 rounded-2xl border p-4" style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-1)' }}>
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h2 className="text-sm font-bold text-[var(--text-primary)]">Đội nhóm</h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">Chia đội để trưởng nhóm quản thành viên của mình — bấm vào đội để sửa</p>
              </div>
              <button onClick={openTeamCreate} className="flex-shrink-0 px-3 py-1.5 rounded-xl text-xs font-semibold text-[var(--gold-500)] bg-[var(--surface-2)] border border-[var(--border-subtle)] hover:bg-[var(--surface-3)] transition-colors">
                + Tạo đội
              </button>
            </div>
            {teams.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">Chưa có đội nào — bấm «+ Tạo đội» để bắt đầu chia nhóm.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {teams.map(t => (
                  <button key={t.id} onClick={() => openTeamEdit(t)} className="text-left rounded-xl p-3 bg-[var(--surface-2)] border border-[var(--border-subtle)] hover:border-[var(--gold-500)] transition-colors">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{t.name}</p>
                      <span className="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-3)] text-[var(--text-muted)]">{t.code}</span>
                    </div>
                    <p className={`text-xs mt-1 truncate ${t.leader_name ? 'text-[var(--text-secondary)]' : 'text-amber-400'}`}>
                      {t.leader_name ? `Trưởng nhóm: ${t.leader_name}` : 'Chưa có trưởng nhóm'}
                    </p>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{t.member_count ?? 0} thành viên · {labelOf(DEPARTMENT_LABELS, t.department)}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

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
                  <th className="text-left px-4 py-3 font-medium text-[var(--text-muted)]">Đội</th>
                  <th className="text-center px-4 py-3 font-medium text-[var(--text-muted)]">Trạng thái</th>
                  {isAdmin && <th className="text-right px-4 py-3 font-medium text-[var(--text-muted)]">Thao tác</th>}
                </tr>
              </thead>
              <tbody>
                {loading2 ? (
                  <tr><td colSpan={7} className="text-center py-8 text-[var(--text-muted)]">Đang tải...</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={7} className="text-center py-8 text-[var(--text-muted)]">Không tìm thấy tài khoản</td></tr>
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
                        {getAnyRoleLabel(u.role)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{labelOf(DEPARTMENT_LABELS, u.department)}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{teams.find(t => t.id === u.team_id)?.name || '—'}</td>
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
                    {getAnyRoleLabel(u.role)}
                  </span>
                  <span className="inline-block px-2 py-0.5 rounded-lg text-xs font-medium border bg-[var(--surface-2)] text-[var(--text-secondary)]" style={{ borderColor: 'var(--border-subtle)' }}>
                    {labelOf(DEPARTMENT_LABELS, u.department)}
                  </span>
                  {u.team_id && (
                    <span className="inline-block px-2 py-0.5 rounded-lg text-xs font-medium border bg-[var(--surface-2)] text-[var(--text-secondary)]" style={{ borderColor: 'var(--border-subtle)' }}>
                      {teams.find(t => t.id === u.team_id)?.name || 'Đội'}
                    </span>
                  )}
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
                <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} inputMode="tel" className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Vai trò</label>
                  <div className="flex gap-1.5">
                    <select value={form.role} onChange={e => {
                      const newRole = e.target.value;
                      // Auto-fill department from built-in defaults or custom role
                      const builtInDept: Record<string, string> = {
                        admin: 'EXEC', executive: 'EXEC', leader: 'SALES',
                        data_entry: 'SALES', accountant: 'ACCT', supervisor: 'OPS',
                      };
                      const custom = customRoles.find(r => r.role_key === newRole);
                      const dept = builtInDept[newRole] || custom?.department || form.department;
                      setForm({ ...form, role: newRole, department: dept });
                    }} className="flex-1 min-w-0 px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                      {BUILTIN_ROLES.map(r => <option key={r} value={r}>{getRoleLabel(r)}</option>)}
                      {customRoles.length > 0 && <option disabled className="text-[var(--text-muted)]">── Tùy chỉnh ──</option>}
                      {customRoles.map(r => <option key={r.role_key} value={r.role_key}>{r.role_name}</option>)}
                    </select>
                    {isAdmin && (
                      <button type="button" onClick={openRoleModal} title="Tạo vai trò mới" className="flex-shrink-0 w-9 h-[38px] rounded-xl text-sm font-bold text-[var(--gold-500)] bg-[var(--surface-2)] border border-[var(--border-subtle)] hover:bg-[var(--surface-3)] transition-colors">
                        +
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bộ phận</label>
                  <select data-qc="dept-select" value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
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
              {modal === 'edit' && (() => {
                // Trưởng nhóm không đổi đội tại đây — kéo họ đi sẽ làm đội cũ mồ côi;
                // muốn chuyển thì đổi trưởng nhóm của đội đó ở khối «Đội nhóm» trước
                const leadingTeam = teams.find(t => t.leader_id === editId);
                return (
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Đội nhóm</label>
                    <select
                      value={form.team_id}
                      onChange={e => setForm({ ...form, team_id: e.target.value })}
                      disabled={Boolean(leadingTeam)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)] disabled:opacity-50"
                    >
                      <option value="">Chưa xếp đội</option>
                      {teams.map(t => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
                    </select>
                    {leadingTeam && (
                      <p className="text-[10px] text-amber-400 mt-1">Đang là trưởng nhóm {leadingTeam.name} — muốn chuyển đội, đổi trưởng nhóm của đội đó trước (khối «Đội nhóm»)</p>
                    )}
                  </div>
                );
              })()}
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

      {/* Modal: Tạo vai trò mới */}
      {roleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setRoleModal(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl p-6 bg-[var(--surface-1)] border border-[var(--border-subtle)] shadow-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">Tạo vai trò mới</h2>
            {roleError && <p className="text-sm text-red-400 mb-3">{roleError}</p>}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Tên vai trò *</label>
                <input
                  value={roleForm.role_name}
                  onChange={e => setRoleForm({ ...roleForm, role_name: e.target.value })}
                  placeholder="VD: Trưởng phòng Design"
                  className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Key (tự动生成, không dấu cách)</label>
                <input
                  value={roleForm.role_key}
                  onChange={e => setRoleForm({ ...roleForm, role_key: e.target.value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '') })}
                  placeholder="VD: design_leader"
                  className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bộ phận</label>
                <select value={roleForm.department} onChange={e => setRoleForm({ ...roleForm, department: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{labelOf(DEPARTMENT_LABELS, d)}</option>)}
                </select>
              </div>
              {/* Permission checklist */}
              <div className="pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-[var(--text-primary)]">Phân quyền mặc định</h3>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => { const all: Record<string, boolean> = {}; ALL_PERMISSION_KEYS.forEach(k => { all[k.key] = true; }); setRolePerms(all); }} className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] underline">Chọn tất cả</button>
                    <button type="button" onClick={() => { const all: Record<string, boolean> = {}; ALL_PERMISSION_KEYS.forEach(k => { all[k.key] = false; }); setRolePerms(all); }} className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] underline">Bỏ tất cả</button>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 max-h-56 overflow-y-auto pr-1">
                  {ALL_PERMISSION_KEYS.map(({ key, label }) => (
                    <label
                      key={key}
                      className={`flex items-center gap-1.5 py-0.5 px-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                        rolePerms[key] ? 'bg-[var(--surface-2)]' : 'bg-[var(--surface-2)] opacity-60'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={!!rolePerms[key]}
                        onChange={() => setRolePerms(prev => ({ ...prev, [key]: !prev[key] }))}
                        className="w-3.5 h-3.5 rounded accent-emerald-500"
                      />
                      <span className="truncate">{label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setRoleModal(false)} className="px-4 py-2 rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)]">Hủy</button>
              <button onClick={handleCreateRole} disabled={roleSaving} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                {roleSaving ? 'Đang lưu...' : 'Tạo vai trò'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Tạo / Sửa đội nhóm */}
      {teamModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setTeamModal(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl p-6 bg-[var(--surface-1)] border border-[var(--border-subtle)] shadow-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">{teamModal === 'create' ? 'Tạo đội mới' : 'Sửa đội nhóm'}</h2>
            {teamError && <p className="text-sm text-red-400 mb-3">{teamError}</p>}
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Tên đội *</label>
                  <input value={teamForm.name} onChange={e => setTeamForm({ ...teamForm, name: e.target.value })} placeholder="VD: Sale Team A" className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)] placeholder:text-[var(--text-disabled)]" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">{teamModal === 'create' ? 'Mã đội *' : 'Mã đội (không đổi được)'}</label>
                  <input value={teamForm.code} onChange={e => setTeamForm({ ...teamForm, code: e.target.value.toUpperCase().replace(/\s+/g, '-') })} disabled={teamModal === 'edit'} placeholder="VD: SALE-A" className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)] placeholder:text-[var(--text-disabled)] disabled:opacity-50" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Bộ phận</label>
                  <select value={teamForm.department} onChange={e => setTeamForm({ ...teamForm, department: e.target.value })} className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {DEPARTMENTS.map(d => <option key={d} value={d}>{labelOf(DEPARTMENT_LABELS, d)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Trưởng nhóm</label>
                  <select
                    value={teamForm.leader_id}
                    onChange={e => {
                      const lid = e.target.value;
                      setTeamForm(f => ({ ...f, leader_id: lid }));
                      // Trưởng nhóm luôn thuộc đội — tick sẵn trong danh sách thành viên
                      if (lid) setTeamMemberIds(prev => new Set(prev).add(lid));
                    }}
                    className="w-full px-3 py-2 rounded-xl text-sm bg-[var(--surface-2)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
                  >
                    <option value="">— Chưa chọn —</option>
                    {leaderOptions.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                  </select>
                  <p className="text-[10px] text-[var(--text-muted)] mt-1">Chỉ vai trò Trưởng phòng / Trưởng nhóm KD</p>
                </div>
              </div>
              {/* Thành viên */}
              <div className="pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <h3 className="text-xs font-semibold text-[var(--text-primary)] mb-1">Thành viên ({teamMemberIds.size})</h3>
                <p className="text-[10px] text-[var(--text-muted)] mb-2">Tick người thuộc đội — người đang ở đội khác sẽ được kéo về đội này khi lưu.</p>
                <div className="space-y-0.5 max-h-56 overflow-y-auto pr-1">
                  {memberCandidates.length === 0 ? (
                    <p className="text-xs text-[var(--text-muted)] py-2">Đang tải danh sách nhân sự...</p>
                  ) : memberCandidates.map(u => {
                    const isLeader = u.id === teamForm.leader_id;
                    const leadsOther = teams.find(t => t.leader_id === u.id && t.id !== teamEditId);
                    const otherTeam = !isLeader && u.team_id && u.team_id !== teamEditId ? teams.find(t => t.id === u.team_id) : null;
                    return (
                      <label key={u.id} className={`flex items-center gap-2 py-1 px-1.5 rounded-lg text-xs transition-colors ${leadsOther ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-[var(--surface-2)]'}`}>
                        <input
                          type="checkbox"
                          checked={teamMemberIds.has(u.id) || isLeader}
                          disabled={isLeader || Boolean(leadsOther)}
                          onChange={() => setTeamMemberIds(prev => {
                            const next = new Set(prev);
                            if (next.has(u.id)) next.delete(u.id); else next.add(u.id);
                            return next;
                          })}
                          className="w-3.5 h-3.5 rounded accent-emerald-500 flex-shrink-0"
                        />
                        <span className="truncate text-[var(--text-primary)]">{u.full_name}</span>
                        <span className="ml-auto flex-shrink-0 text-[10px] text-[var(--text-muted)]">
                          {isLeader ? 'Trưởng nhóm' : leadsOther ? `Trưởng nhóm ${leadsOther.name}` : otherTeam ? `đang ở ${otherTeam.name}` : labelOf(DEPARTMENT_LABELS, u.department)}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between gap-2 mt-5">
              {teamModal === 'edit' ? (
                <button onClick={handleTeamDelete} disabled={teamSaving} className="px-3 py-2 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50">
                  Giải tán đội
                </button>
              ) : <span />}
              <div className="flex gap-2">
                <button onClick={() => setTeamModal(null)} className="px-4 py-2 rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)]">Hủy</button>
                <button onClick={handleTeamSave} disabled={teamSaving} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                  {teamSaving ? 'Đang lưu...' : teamModal === 'create' ? 'Tạo đội' : 'Lưu'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Sidebar>
  );
}
