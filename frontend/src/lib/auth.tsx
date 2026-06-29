'use client';

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { api, User } from '@/lib/api';

// Demo users — used when backend is unavailable
const DEMO_USERS: Record<string, { password: string; user: User }> = {
  'admin@jamahome.vn': {
    password: 'admin123',
    user: {
      id: 'demo-admin-001',
      full_name: 'Nguyễn Văn Admin',
      email: 'admin@jamahome.vn',
      phone: '0901234567',
      role: 'admin',
      department: 'Ban Giám Đốc',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    },
  },
  'sales@jamahome.vn': {
    password: 'sales123',
    user: {
      id: 'demo-sales-001',
      full_name: 'Trần Thị Sales',
      email: 'sales@jamahome.vn',
      phone: '0907654321',
      role: 'data_entry',
      department: 'Sales',
      team_id: 'team-01',
      is_active: true,
      created_at: '2026-01-15T00:00:00Z',
    },
  },
  'leader@jamahome.vn': {
    password: 'leader123',
    user: {
      id: 'demo-leader-001',
      full_name: 'Lê Văn Leader',
      email: 'leader@jamahome.vn',
      phone: '0909876543',
      role: 'leader',
      department: 'Sales',
      team_id: 'team-01',
      is_active: true,
      created_at: '2026-01-10T00:00:00Z',
    },
  },
  'accountant@jamahome.vn': {
    password: 'account123',
    user: {
      id: 'demo-acct-001',
      full_name: 'Phạm Thị Kế Toán',
      email: 'accountant@jamahome.vn',
      phone: '0905555666',
      role: 'accountant',
      department: 'ACCT',
      is_active: true,
      created_at: '2026-01-20T00:00:00Z',
    },
  },
  'ceo@jamahome.vn': {
    password: 'ceo123',
    user: {
      id: 'demo-exec-001',
      full_name: 'Đỗ Minh Tuấn',
      email: 'ceo@jamahome.vn',
      phone: '0901111222',
      role: 'executive',
      department: 'EXEC',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    },
  },
};

export type AppMode = 'demo' | 'work';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isDemo: boolean;
  mode: AppMode;
  setMode: (mode: AppMode) => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isDemo: false,
  mode: 'work',
  setMode: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setModeState] = useState<AppMode>('work');

  // Derive isDemo from mode for backward compatibility
  const isDemo = mode === 'demo';

  useEffect(() => {
    void Promise.resolve().then(() => {
      // Read persisted mode
      const storedMode = localStorage.getItem('jama_mode') as AppMode | null;
      if (storedMode === 'demo' || storedMode === 'work') {
        setModeState(storedMode);
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

  const login = async (email: string, password: string) => {
    // Try real API first
    try {
      const data = await api.login(email, password);
      setUser(data.user);
      setModeState('work');
      localStorage.setItem('jama_mode', 'work');
      localStorage.setItem('jama_demo', 'false');
      return;
    } catch {
      // API unavailable — fallback to demo
    }

    // Demo login
    const demoEntry = DEMO_USERS[email.toLowerCase()];
    if (demoEntry && demoEntry.password === password) {
      setUser(demoEntry.user);
      setModeState('demo');
      localStorage.setItem('jama_mode', 'demo');
      localStorage.setItem('jama_token', 'demo-token');
      localStorage.setItem('jama_user', JSON.stringify(demoEntry.user));
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
      const adminEntry = DEMO_USERS['admin@jamahome.vn'];
      setUser(adminEntry.user);
      setModeState('demo');
      localStorage.setItem('jama_mode', 'demo');
      localStorage.setItem('jama_token', 'demo-token');
      localStorage.setItem('jama_user', JSON.stringify(adminEntry.user));
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
    <AuthContext.Provider value={{ user, loading, login, logout, isDemo, mode, setMode }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
