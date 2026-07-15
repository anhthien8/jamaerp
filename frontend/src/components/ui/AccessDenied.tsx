'use client';

import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';

interface AccessDeniedProps {
  message?: string;
}

export default function AccessDenied({ message = 'Bạn không có quyền truy cập trang này.' }: AccessDeniedProps) {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <span className="text-5xl block mb-4">🔒</span>
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            {message}
          </p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2.5 rounded-xl text-sm font-medium transition-all"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: '#fff' }}
          >
            Quay về Tổng quan
          </button>
        </div>
      </div>
    </Sidebar>
  );
}
