'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

interface CustomerData {
  name: string;
  phone: string;
  email: string;
  company_name?: string;
}

interface ProjectData {
  id: string;
  code: string;
  name: string;
  status: string;
  stage: string;
  progress: number;
  total_value?: number;
  created_at: string;
}

interface TaskData {
  id: string;
  title: string;
  status: string;
  stage: string;
}

interface ActivityData {
  id: string;
  content: string;
  media_url?: string;
  user_name: string;
  created_at: string;
}

const STAGE_LABELS: Record<string, string> = {
  design: 'Thiết kế', quotation: 'Báo giá', procurement: 'Thu mua',
  construction: 'Thi công', acceptance: 'Nghiệm thu', completed: 'Hoàn thành',
};

const STATUS_COLORS: Record<string, string> = {
  active: '#10B981', paused: '#F59E0B', completed: '#3B82F6', cancelled: '#EF4444',
};

export default function PortalPage() {
  const params = useParams();
  const token = params.token as string;
  const [customer, setCustomer] = useState<CustomerData | null>(null);
  const [projects, setProjects] = useState<ProjectData[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectData | null>(null);
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [activities, setActivities] = useState<ActivityData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadingDetail, setLoadingDetail] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/portal/${token}`)
      .then(r => { if (!r.ok) throw new Error('Link không hợp lệ'); return r.json(); })
      .then(data => { setCustomer(data.customer); setProjects(data.projects || []); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, API]);

  const loadProjectDetail = async (project: ProjectData) => {
    setSelectedProject(project);
    setLoadingDetail(true);
    try {
      const [projRes, actRes] = await Promise.all([
        fetch(`${API}/portal/${token}/projects/${project.id}`),
        fetch(`${API}/portal/${token}/projects/${project.id}/activities`),
      ]);
      if (projRes.ok) {
        const data = await projRes.json();
        setTasks(data.tasks || []);
      }
      if (actRes.ok) {
        const data = await actRes.json();
        setActivities(data.activities || []);
      }
    } catch {} finally { setLoadingDetail(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-2 border-[#C9A96E] border-t-transparent rounded-full"></div></div>;
  if (error) return <div className="min-h-screen flex items-center justify-center"><div className="text-center"><p className="text-red-400 text-lg mb-2">❌ {error}</p><p className="text-gray-500 text-sm">Vui lòng liên hệ JAMA HOME: 070.56.23456</p></div></div>;

  return (
    <div className="min-h-screen" style={{ background: '#0D1117', color: '#E6EDF3' }}>
      {/* Header */}
      <header className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.08)', background: '#161B22' }}>
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center font-bold" style={{ background: 'linear-gradient(135deg, #C9A96E, #B8935A)', color: 'white' }}>J</div>
            <div>
              <h1 className="text-lg font-bold" style={{ color: '#C9A96E' }}>JAMA HOME</h1>
              <p className="text-xs" style={{ color: '#9BA7B4' }}>Thiết kế cho cuộc sống mới</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto p-4 space-y-4">
        {/* Customer info */}
        {customer && (
          <div className="p-4 rounded-xl" style={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.08)' }}>
            <p className="text-sm" style={{ color: '#9BA7B4' }}>Xin chào, <span className="font-semibold text-white">{customer.name}</span></p>
            <p className="text-xs" style={{ color: '#6B7683' }}>{customer.phone}{customer.company_name ? ` · ${customer.company_name}` : ''}</p>
          </div>
        )}

        {/* Projects list or project detail */}
        {!selectedProject ? (
          <>
            <h2 className="text-sm font-semibold" style={{ color: '#9BA7B4' }}>📋 Dự án ({projects.length})</h2>
            {projects.length === 0 ? (
              <p className="text-xs text-center py-8" style={{ color: '#6B7683' }}>Chưa có dự án nào</p>
            ) : projects.map(p => (
              <button key={p.id} onClick={() => loadProjectDetail(p)}
                className="w-full p-4 rounded-xl text-left transition-all hover:bg-white/5"
                style={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-white">{p.code} — {p.name}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: `${STATUS_COLORS[p.status] || '#6B7280'}20`, color: STATUS_COLORS[p.status] || '#6B7280' }}>{p.status === 'active' ? 'Đang chạy' : p.status}</span>
                </div>
                <div className="flex items-center gap-2 mb-1">
                  <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.1)' }}>
                    <div className="h-full rounded-full" style={{ width: `${p.progress}%`, background: 'linear-gradient(90deg, #C9A96E, #B8935A)' }}></div>
                  </div>
                  <span className="text-[10px] font-mono" style={{ color: '#C9A96E' }}>{p.progress}%</span>
                </div>
                <p className="text-[10px] mt-1" style={{ color: '#6B7683' }}>Giai đoạn: {STAGE_LABELS[p.stage] || p.stage}</p>
              </button>
            ))}
          </>
        ) : (
          <>
            <button onClick={() => { setSelectedProject(null); setTasks([]); setActivities([]); }} className="text-xs mb-2" style={{ color: '#C9A96E' }}>← Quay lại danh sách</button>
            <h2 className="text-sm font-semibold text-white">{selectedProject.code} — {selectedProject.name}</h2>
            <div className="flex items-center gap-2 text-[10px]" style={{ color: '#9BA7B4' }}>
              <span>Giai đoạn: <span className="text-white">{STAGE_LABELS[selectedProject.stage]}</span></span>
              <span>·</span>
              <span style={{ color: '#C9A96E' }}>{selectedProject.progress}%</span>
            </div>
            {loadingDetail ? <p className="text-xs py-4" style={{ color: '#6B7683' }}>Đang tải...</p> : (
              <>
                {tasks.length > 0 && (
                  <div className="p-4 rounded-xl" style={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <h3 className="text-xs font-semibold mb-2" style={{ color: '#9BA7B4' }}>Tiến độ công việc</h3>
                    {tasks.map(t => (
                      <div key={t.id} className="flex items-center gap-2 py-1.5 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                        <span>{t.status === 'done' ? '✅' : t.status === 'in_progress' ? '🔄' : '⏳'}</span>
                        <span className="text-xs text-white">{t.title}</span>
                      </div>
                    ))}
                  </div>
                )}
                {activities.length > 0 && (
                  <div className="p-4 rounded-xl" style={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <h3 className="text-xs font-semibold mb-2" style={{ color: '#9BA7B4' }}>📸 Hoạt động gần đây</h3>
                    {activities.map(a => (
                      <div key={a.id} className="py-2 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                        <p className="text-xs text-white">{a.content.substring(0, 120)}{a.content.length > 120 ? '...' : ''}</p>
                        <p className="text-[10px] mt-0.5" style={{ color: '#6B7683' }}>{a.user_name} · {new Date(a.created_at).toLocaleDateString('vi-VN')}</p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Footer */}
        <footer className="text-center py-6 text-xs" style={{ color: '#6B7683' }}>
          <p>📞 Cần hỗ trợ? Gọi: <a href="tel:0705623456" style={{ color: '#C9A96E' }}>070.56.23456</a></p>
          <p className="mt-1">JAMA HOME — Thiết kế cho cuộc sống mới</p>
        </footer>
      </main>
    </div>
  );
}
