'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, User } from '@/lib/api';
import { duocXemLead, fetchMyPermissions, getEffectivePermissions, loadCustomRoles, RolePermissions, SYSTEM_ROLES, UserRole } from '@/lib/roles';

/**
 * Đọc hạn dùng (exp) ghi sẵn trong token, không cần gọi máy chủ.
 * Token của ERP sống 12 tiếng; hết hạn thì mọi lời gọi đều trả 401.
 */
function tokenConHan(token: string | null): boolean {
  if (!token) return false;
  try {
    const phan = token.split('.')[1];
    if (!phan) return false;
    const payload = JSON.parse(atob(phan.replace(/-/g, '+').replace(/_/g, '/')));
    return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  /** Effective permissions: role defaults merged with per-user custom overrides */
  effectivePermissions: RolePermissions;
  /**
   * true = effectivePermissions đã CHỐT (quyền backend tải xong, hoặc xác định
   * không có gì để tải: demo/chưa đăng nhập/mất mạng). Trang gate theo quyền
   * PHẢI đợi cờ này trước khi redirect — vai trò tùy chỉnh lúc đầu chỉ có
   * mặc định data_entry cục bộ, redirect sớm là đá nhầm người có quyền.
   */
  permsReady: boolean;
  /**
   * true = tải quyền backend LỖI TẠM (500/CORS/mất mạng/cold-start) dù đã retry.
   * Lúc này permsReady giữ false nên gate KHÔNG được redirect — quyền đang hiện
   * chỉ là bản cục bộ tạm, đá người ta đi là đá oan (backend vẫn tự chặn data
   * nên không rò rỉ gì). Trang gate hiện banner «Không tải được quyền — thử lại».
   */
  permsError: boolean;
  /** Nút «Thử lại» trên banner — nạp lại quyền backend (kèm vai trò tùy chỉnh). */
  retryPerms: () => void;
  /** Gộp thay đổi vào người dùng đang đăng nhập (vd ảnh đại diện mới) + lưu localStorage. */
  capNhatUser: (patch: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  effectivePermissions: getEffectivePermissions('data_entry'),
  permsReady: false,
  permsError: false,
  retryPerms: () => {},
  capNhatUser: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  // Quyền do backend tính (GET /users/permissions/me) — nguồn sự thật duy nhất.
  // null = chưa tải xong / demo / mất mạng → dùng bản tính cục bộ bên dưới.
  const [serverPerms, setServerPerms] = useState<RolePermissions | null>(null);
  const [permsReady, setPermsReady] = useState(false);
  const [permsError, setPermsError] = useState(false);
  // _customRoles (roles.ts) là cache module-level — trước đây chỉ Sidebar nạp và
  // bump cục bộ nên AuthProvider không re-render, effectivePermissions của vai trò
  // tùy chỉnh kẹt ở khung data_entry. Bump version này để useMemo tính lại.
  const [customRolesVersion, setCustomRolesVersion] = useState(0);

  // Effective permissions: ưu tiên bản backend (nơi thật sự chặn API — từ 13/08/2026
  // ma trận Phân quyền có hiệu lực thật trên máy chủ); rơi về bản tính cục bộ
  // (mặc định vai trò + override cá nhân) khi chưa có.
  const effectivePermissions = useMemo(() => {
    void customRolesVersion; // đổi khi cache vai trò tùy chỉnh vừa nạp xong → tính lại
    if (!user) return getEffectivePermissions('data_entry');
    const local = getEffectivePermissions(user.role as UserRole, user.custom_permissions);
    const tron = serverPerms ? ({ ...local, ...serverPerms } as RolePermissions) : local;
    // Chặn CỨNG theo bộ phận, áp sau cùng để không override nào mở lại được:
    // «trừ bộ phận kinh doanh và nhân sự thuộc ban giám đốc, không ai được quyền
    // thấy lead» (chốt 22/09). Khớp duoc_xem_lead() ở backend.
    if (tron.canViewLeads && !duocXemLead(user.role, user.department)) {
      return { ...tron, canViewLeads: false, leadsScope: 'none' } as RolePermissions;
    }
    return tron;
  }, [user, serverPerms, customRolesVersion]);

  // Nạp quyền backend cho phiên hiện tại. role truyền qua tham số vì lúc restore,
  // state user chưa kịp commit khi hàm này chạy.
  const napQuyenBackend = useCallback((role?: string) => {
    setPermsError(false);
    // Vai trò tùy chỉnh (sale_leader, admin_cskh…): nạp định nghĩa role TRƯỚC — nếu
    // /permissions/me lỗi thì bản cục bộ còn phủ đúng quyền đã lưu thay vì khung
    // data_entry (thiếu canViewHR → gate đá oan trưởng nhóm KD về trang chủ).
    const napCustom = role && !SYSTEM_ROLES.includes(role)
      ? loadCustomRoles().then((has) => { if (has) setCustomRolesVersion((v) => v + 1); })
      : Promise.resolve();
    void napCustom
      .then(() => fetchMyPermissions())
      .then((kq) => {
        if (kq.status === 'ok') {
          setServerPerms(kq.permissions);
          setPermsReady(true);
        } else if (kq.status === 'error') {
          // Lỗi tạm dù đã retry: KHÔNG chốt quyền (permsReady giữ false → gate
          // không redirect), bật banner cho người dùng bấm thử lại.
          setPermsError(true);
        } else {
          // skip (demo/không token) hoặc 401 (phiên hỏng — lời gọi data kế tiếp
          // sẽ bắt đăng nhập lại): không có gì để tải, chốt bản cục bộ.
          setPermsReady(true);
        }
      });
  }, []);

  const retryPerms = useCallback(() => {
    if (user) napQuyenBackend(user.role);
  }, [user, napQuyenBackend]);

  useEffect(() => {
    void Promise.resolve().then(() => {
      // Chế độ Tập luyện đã gỡ hẳn — dọn cờ cũ còn sót trên trình duyệt từng dùng demo
      // (token 'demo-token' không qua được tokenConHan bên dưới nên phiên demo tự bị xóa).
      localStorage.removeItem('jama_demo');
      localStorage.removeItem('jama_mode');

      // Phiên đã hết hạn thì KHÔNG dựng lại người dùng nữa. Trước đây vẫn khôi phục
      // từ localStorage nên app trông như đang đăng nhập (còn tên, còn menu) trong khi
      // mọi trang đều báo "Không thể tải dữ liệu" — không ai đoán được là phải đăng nhập lại.
      if (!tokenConHan(localStorage.getItem('jama_token'))) {
        localStorage.removeItem('jama_token');
        localStorage.removeItem('jama_user');
        setLoading(false);
        return;
      }

      const stored = localStorage.getItem('jama_user');
      let dangTaiQuyen = false;
      if (stored) {
        try {
          const restored = JSON.parse(stored) as User;
          setUser(restored);
          // Làm mới ảnh đại diện nền — bản localStorage có thể cũ (đổi ảnh ở máy khác)
          void api.me().then((me) => {
            if (!me || (me.avatar_url ?? null) === (restored.avatar_url ?? null)) return;
            setUser((u) => {
              if (!u) return u;
              const moi = { ...u, avatar_url: me.avatar_url ?? null };
              localStorage.setItem('jama_user', JSON.stringify(moi));
              return moi;
            });
          }).catch(() => {});
          // Tải quyền backend nền — không chặn màn hình (menu tạm vẽ theo bản cục bộ)
          dangTaiQuyen = true;
          napQuyenBackend(restored.role);
        } catch {}
      }
      if (!dangTaiQuyen) setPermsReady(true);
      setLoading(false);
    });
  }, [napQuyenBackend]);

  const login = async (email: string, password: string) => {
    try {
      const data = await api.login(email, password);
      setUser(data.user);
      setPermsReady(false);
      napQuyenBackend(data.user.role);
    } catch {
      throw new Error('Email hoặc mật khẩu không đúng');
    }
  };

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
    setServerPerms(null);
    window.location.href = '/login';
  }, []);

  const capNhatUser = useCallback((patch: Partial<User>) => {
    setUser((u) => {
      if (!u) return u;
      const moi = { ...u, ...patch };
      localStorage.setItem('jama_user', JSON.stringify(moi));
      return moi;
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, effectivePermissions, permsReady, permsError, retryPerms, capNhatUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
