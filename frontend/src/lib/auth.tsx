'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, User } from '@/lib/api';
import { getEffectivePermissions, RolePermissions, UserRole } from '@/lib/roles';
import { SHOW_DEMO_MODE } from '@/lib/features';

// Demo mode — single shared password for all accounts (training/offline only)
const DEMO_PASSWORD = 'demo123';

const DEMO_USERS: Record<string, User> = {
  'admin@jamahome.vn': {
    id: 'demo-admin-001', full_name: 'Hồ Minh Tuấn', email: 'admin@jamahome.vn',
    phone: '0901234567', role: 'admin', department: 'Ban Giám Đốc', is_active: true, created_at: '2026-01-01T00:00:00Z',
  },
  'sales@jamahome.vn': {
    id: 'demo-sales-001', full_name: 'Trần Thị Sales', email: 'sales@jamahome.vn',
    phone: '0907654321', role: 'data_entry', department: 'Sales', team_id: 'team-01', is_active: true, created_at: '2026-01-15T00:00:00Z',
  },
  'leader@jamahome.vn': {
    id: 'demo-leader-001', full_name: 'Lê Văn Leader', email: 'leader@jamahome.vn',
    phone: '0909876543', role: 'leader', department: 'Sales', team_id: 'team-01', is_active: true, created_at: '2026-01-10T00:00:00Z',
  },
  'accountant@jamahome.vn': {
    id: 'demo-acct-001', full_name: 'Phạm Thị Kế Toán', email: 'accountant@jamahome.vn',
    phone: '0905555666', role: 'accountant', department: 'ACCT', is_active: true, created_at: '2026-01-20T00:00:00Z',
  },
  'ceo@jamahome.vn': {
    id: 'demo-exec-001', full_name: 'Đỗ Minh Tuấn', email: 'ceo@jamahome.vn',
    phone: '0901111222', role: 'executive', department: 'EXEC', is_active: true, created_at: '2026-01-01T00:00:00Z',
  },
  'supervisor@jamahome.vn': {
    id: 'demo-supervisor-001', full_name: 'Nguyễn Văn Giám Sát', email: 'supervisor@jamahome.vn',
    phone: '0902222333', role: 'supervisor', department: 'OPS', is_active: true, created_at: '2026-02-01T00:00:00Z',
  },
};

export type AppMode = 'demo' | 'work';

/**
 * Đọc hạn dùng (exp) ghi sẵn trong token, không cần gọi máy chủ.
 * Token của CRM sống 12 tiếng; hết hạn thì mọi lời gọi đều trả 401.
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
  login: (email: string, password: string, modeOverride?: AppMode) => Promise<void>;
  logout: () => void;
  isDemo: boolean;
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  /** Effective permissions: role defaults merged with per-user custom overrides */
  effectivePermissions: RolePermissions;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isDemo: false,
  mode: 'work',
  setMode: () => {},
  effectivePermissions: getEffectivePermissions('data_entry'),
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setModeState] = useState<AppMode>('work');

  // Derive isDemo from mode for backward compatibility
  const isDemo = mode === 'demo';

  // Effective permissions: role defaults merged with per-user custom overrides
  const effectivePermissions = useMemo(() => {
    if (!user) return getEffectivePermissions('data_entry');
    return getEffectivePermissions(user.role as UserRole, user.custom_permissions);
  }, [user]);

  useEffect(() => {
    void Promise.resolve().then(() => {
      // Chế độ Tập luyện đang tắt: phiên demo còn lưu trên máy sẽ restore thẳng vào app
      // và hiện DỮ LIỆU MẪU như thật (che cả lỗi API) — gặp là xóa sạch, bắt đăng nhập lại.
      if (!SHOW_DEMO_MODE && localStorage.getItem('jama_demo') === 'true') {
        localStorage.removeItem('jama_demo');
        localStorage.removeItem('jama_user');
        localStorage.removeItem('jama_token');
        localStorage.setItem('jama_mode', 'work');
        setLoading(false);
        return;
      }

      // Read persisted mode
      const storedMode = localStorage.getItem('jama_mode') as AppMode | null;
      if (storedMode === 'demo' || storedMode === 'work') {
        setModeState(storedMode);
      }

      // Phiên đã hết hạn thì KHÔNG dựng lại người dùng nữa. Trước đây vẫn khôi phục
      // từ localStorage nên app trông như đang đăng nhập (còn tên, còn menu) trong khi
      // mọi trang đều báo "Không thể tải dữ liệu" — không ai đoán được là phải đăng nhập lại.
      if (localStorage.getItem('jama_demo') !== 'true' && !tokenConHan(localStorage.getItem('jama_token'))) {
        localStorage.removeItem('jama_token');
        localStorage.removeItem('jama_user');
        setLoading(false);
        return;
      }

      const stored = localStorage.getItem('jama_user');
      if (stored) {
        try {
          setUser(JSON.parse(stored));
        } catch {}
      }
      setLoading(false);
    });
  }, []);

  const login = async (email: string, password: string, modeOverride?: AppMode) => {
    const effectiveMode = modeOverride || mode;
    // If currently in demo mode, use demo login directly (skip real API)
    if (effectiveMode === 'demo') {
      const demoUser = DEMO_USERS[email.toLowerCase()];
      if (demoUser && password === DEMO_PASSWORD) {
        setUser(demoUser);
        setModeState('demo');
        localStorage.setItem('jama_mode', 'demo');
        localStorage.setItem('jama_token', 'demo-token');
        localStorage.setItem('jama_user', JSON.stringify(demoUser));
        localStorage.setItem('jama_demo', 'true');
        return;
      }
      throw new Error('Email hoặc mật khẩu không đúng (Demo Mode)');
    }

    // Work mode: try real API first.
    // QUAN TRỌNG: phải xóa cờ jama_demo TRƯỚC khi gọi api.login — vì api.request()
    // kiểm isDemoMode() (đọc localStorage 'jama_demo') ngay đầu. Nếu phiên trước ở
    // Demo mà chưa xóa cờ, "login Work" sẽ chạy demo resolver → vào nhầm Demo (bug cũ).
    localStorage.setItem('jama_demo', 'false');
    localStorage.setItem('jama_mode', 'work');
    setModeState('work');
    try {
      const data = await api.login(email, password);
      setUser(data.user);
      return;
    } catch {
      // API unavailable — fallback to demo (chỉ khi đúng mật khẩu demo)
    }

    // Lối rơi về Chế độ Tập luyện — CHỈ chạy khi cờ SHOW_DEMO_MODE còn bật.
    // Nó bắt MỌI lỗi của api.login, kể cả 401 sai mật khẩu, nên khi cờ đã tắt mà vẫn
    // để chạy thì gõ nhầm mật khẩu vẫn "đăng nhập thành công" rồi hiện số liệu mẫu như
    // số thật. Mã bên dưới giữ nguyên ở trạng thái ngủ theo quyết định 12/08/2026.
    const demoUser = SHOW_DEMO_MODE ? DEMO_USERS[email.toLowerCase()] : undefined;
    if (demoUser && password === DEMO_PASSWORD) {
      setUser(demoUser);
      setModeState('demo');
      localStorage.setItem('jama_mode', 'demo');
      localStorage.setItem('jama_token', 'demo-token');
      localStorage.setItem('jama_user', JSON.stringify(demoUser));
      localStorage.setItem('jama_demo', 'true');
      return;
    }

    throw new Error('Email hoặc mật khẩu không đúng');
  };

  const logout = useCallback(() => {
    api.logout();
    localStorage.removeItem('jama_demo');
    setUser(null);
    window.location.href = '/login';
  }, []);

  const setMode = useCallback((newMode: AppMode) => {
    if (newMode === 'demo') {
      // Switch to demo mode: auto-login with admin demo account
      const adminUser = DEMO_USERS['admin@jamahome.vn'];
      setUser(adminUser);
      setModeState('demo');
      localStorage.setItem('jama_mode', 'demo');
      localStorage.setItem('jama_token', 'demo-token');
      localStorage.setItem('jama_user', JSON.stringify(adminUser));
      localStorage.setItem('jama_demo', 'true');
    } else {
      // Switch to work mode: logout and redirect to login
      setModeState('work');
      localStorage.setItem('jama_mode', 'work');
      api.logout();
      localStorage.removeItem('jama_demo');
      setUser(null);
      window.location.href = '/login';
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isDemo, mode, setMode, effectivePermissions }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
