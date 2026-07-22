'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api } from '@/lib/api';
import { DEMO_PNL_SUMMARY } from '@/lib/demo-data';
import { formatCurrency, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';

// ── Types ──────────────────────────────────────────────────
interface ProjectPL {
  project_id: string;
  project_code: string;
  project_name: string;
  revenue: number;
  costs: number;
  profit: number;
  margin: number;
  status: string;
  start_date: string; // ISO date
  cost_breakdown?: {
    materials: number;
    transactions: number;
    commissions: number;
  };
}

interface CompanyPLSummary {
  total_revenue: number;
  total_costs: number;
  net_profit: number;
  margin: number;
  project_count: number;
  profitable_projects: number;
  loss_projects: number;
}

type FilterType = 'all' | 'month' | 'quarter' | 'year' | 'custom';

// ── 25 Mock Projects ───────────────────────────────────────
const MOCK_PROJECT_PL_RAW: ProjectPL[] = [
  // ── Premium (5 dự án lớn) ──
  {
    project_id: 'proj-001', project_code: 'JMH-0601',
    project_name: 'Biệt thự An Lạc - Long An',
    revenue: 25_800_000_000, costs: 20_100_000_000, profit: 5_700_000_000, margin: 22.1,
    status: 'in_progress', start_date: '2026-01-10',
    cost_breakdown: { materials: 12_600_000_000, transactions: 5_200_000_000, commissions: 2_300_000_000 },
  },
  {
    project_id: 'proj-002', project_code: 'JMH-0608',
    project_name: 'Villa Thảo Điền - Quận 2',
    revenue: 28_500_000_000, costs: 22_800_000_000, profit: 5_700_000_000, margin: 20.0,
    status: 'in_progress', start_date: '2026-02-05',
    cost_breakdown: { materials: 14_200_000_000, transactions: 5_900_000_000, commissions: 2_700_000_000 },
  },
  {
    project_id: 'proj-003', project_code: 'JMH-0593',
    project_name: 'Penthouse Sky Garden - Quận 7',
    revenue: 22_300_000_000, costs: 17_400_000_000, profit: 4_900_000_000, margin: 22.0,
    status: 'completed', start_date: '2026-01-20',
    cost_breakdown: { materials: 10_800_000_000, transactions: 4_500_000_000, commissions: 2_100_000_000 },
  },
  {
    project_id: 'proj-004', project_code: 'JMH-0612',
    project_name: 'Biệt thự Phú Mỹ Hưng - Quận 7',
    revenue: 20_500_000_000, costs: 16_400_000_000, profit: 4_100_000_000, margin: 20.0,
    status: 'in_progress', start_date: '2026-03-15',
    cost_breakdown: { materials: 10_200_000_000, transactions: 4_200_000_000, commissions: 2_000_000_000 },
  },
  {
    project_id: 'proj-005', project_code: 'JMH-0618',
    project_name: 'Villa Riviera - Quận 2',
    revenue: 24_200_000_000, costs: 18_700_000_000, profit: 5_500_000_000, margin: 22.7,
    status: 'in_progress', start_date: '2026-04-01',
    cost_breakdown: { materials: 11_600_000_000, transactions: 4_900_000_000, commissions: 2_200_000_000 },
  },
  // ── Medium (8 dự án trung bình) ──
  {
    project_id: 'proj-006', project_code: 'JMH-0587',
    project_name: 'Nhà phố Sunrise - Quận 7',
    revenue: 15_500_000_000, costs: 12_400_000_000, profit: 3_100_000_000, margin: 20.0,
    status: 'in_progress', start_date: '2026-02-15',
    cost_breakdown: { materials: 7_700_000_000, transactions: 3_200_000_000, commissions: 1_500_000_000 },
  },
  {
    project_id: 'proj-007', project_code: 'JMH-0595',
    project_name: 'Căn hộ Penthouse - Thủ Đức',
    revenue: 12_200_000_000, costs: 9_500_000_000, profit: 2_700_000_000, margin: 22.1,
    status: 'completed', start_date: '2026-03-05',
    cost_breakdown: { materials: 5_900_000_000, transactions: 2_500_000_000, commissions: 1_100_000_000 },
  },
  {
    project_id: 'proj-008', project_code: 'JMH-0610',
    project_name: 'Villa The Manor - Bình Chánh',
    revenue: 11_800_000_000, costs: 9_400_000_000, profit: 2_400_000_000, margin: 20.3,
    status: 'in_progress', start_date: '2026-04-10',
    cost_breakdown: { materials: 5_800_000_000, transactions: 2_400_000_000, commissions: 1_200_000_000 },
  },
  {
    project_id: 'proj-009', project_code: 'JMH-0622',
    project_name: 'Nhà phố Lakeview - Quận 9',
    revenue: 9_500_000_000, costs: 7_600_000_000, profit: 1_900_000_000, margin: 20.0,
    status: 'in_progress', start_date: '2026-05-01',
    cost_breakdown: { materials: 4_700_000_000, transactions: 2_000_000_000, commissions: 900_000_000 },
  },
  {
    project_id: 'proj-010', project_code: 'JMH-0578',
    project_name: 'Căn hộ Vinhomes Central Park',
    revenue: 14_200_000_000, costs: 11_400_000_000, profit: 2_800_000_000, margin: 19.7,
    status: 'completed', start_date: '2026-01-05',
    cost_breakdown: { materials: 7_100_000_000, transactions: 2_900_000_000, commissions: 1_400_000_000 },
  },
  {
    project_id: 'proj-011', project_code: 'JMH-0603',
    project_name: 'Duplex Masteri Thảo Điền',
    revenue: 8_800_000_000, costs: 7_000_000_000, profit: 1_800_000_000, margin: 20.5,
    status: 'in_progress', start_date: '2026-03-20',
    cost_breakdown: { materials: 4_300_000_000, transactions: 1_800_000_000, commissions: 900_000_000 },
  },
  {
    project_id: 'proj-012', project_code: 'JMH-0585',
    project_name: 'Nhà phố Mega Village - Quận 9',
    revenue: 7_500_000_000, costs: 6_000_000_000, profit: 1_500_000_000, margin: 20.0,
    status: 'completed', start_date: '2026-02-01',
    cost_breakdown: { materials: 3_700_000_000, transactions: 1_500_000_000, commissions: 800_000_000 },
  },
  {
    project_id: 'proj-013', project_code: 'JMH-0625',
    project_name: 'Căn hộ Diamond Island - Quận 2',
    revenue: 10_800_000_000, costs: 8_600_000_000, profit: 2_200_000_000, margin: 20.4,
    status: 'in_progress', start_date: '2026-05-15',
    cost_breakdown: { materials: 5_300_000_000, transactions: 2_200_000_000, commissions: 1_100_000_000 },
  },
  // ── Small (10 dự án nhỏ) ──
  {
    project_id: 'proj-014', project_code: 'JMH-0575',
    project_name: 'Căn hộ The Sun Avenue - Quận 2',
    revenue: 5_500_000_000, costs: 4_400_000_000, profit: 1_100_000_000, margin: 20.0,
    status: 'completed', start_date: '2026-01-15',
    cost_breakdown: { materials: 2_700_000_000, transactions: 1_100_000_000, commissions: 600_000_000 },
  },
  {
    project_id: 'proj-015', project_code: 'JMH-0582',
    project_name: 'Studio Gateway Thảo Điền',
    revenue: 3_200_000_000, costs: 2_600_000_000, profit: 600_000_000, margin: 18.8,
    status: 'completed', start_date: '2026-02-20',
    cost_breakdown: { materials: 1_600_000_000, transactions: 650_000_000, commissions: 350_000_000 },
  },
  {
    project_id: 'proj-016', project_code: 'JMH-0598',
    project_name: 'Căn hộ Saigon Pearl - Bình Thạnh',
    revenue: 4_800_000_000, costs: 3_800_000_000, profit: 1_000_000_000, margin: 20.8,
    status: 'in_progress', start_date: '2026-03-10',
    cost_breakdown: { materials: 2_300_000_000, transactions: 1_000_000_000, commissions: 500_000_000 },
  },
  {
    project_id: 'proj-017', project_code: 'JMH-0614',
    project_name: 'Nhà phố Bình Thạnh - Chị Hương',
    revenue: 4_500_000_000, costs: 3_600_000_000, profit: 900_000_000, margin: 20.0,
    status: 'completed', start_date: '2026-04-15',
    cost_breakdown: { materials: 2_200_000_000, transactions: 900_000_000, commissions: 500_000_000 },
  },
  {
    project_id: 'proj-018', project_code: 'JMH-0628',
    project_name: 'Văn phòng Quận 1 - Interior',
    revenue: 3_800_000_000, costs: 3_000_000_000, profit: 800_000_000, margin: 21.1,
    status: 'in_progress', start_date: '2026-05-20',
    cost_breakdown: { materials: 1_800_000_000, transactions: 800_000_000, commissions: 400_000_000 },
  },
  {
    project_id: 'proj-019', project_code: 'JMH-0632',
    project_name: 'Căn hộ Estella Heights - Quận 2',
    revenue: 6_200_000_000, costs: 5_000_000_000, profit: 1_200_000_000, margin: 19.4,
    status: 'in_progress', start_date: '2026-06-01',
    cost_breakdown: { materials: 3_100_000_000, transactions: 1_300_000_000, commissions: 600_000_000 },
  },
  {
    project_id: 'proj-020', project_code: 'JMH-0572',
    project_name: 'Sửa chữa VP Tân Bình',
    revenue: 2_500_000_000, costs: 2_000_000_000, profit: 500_000_000, margin: 20.0,
    status: 'completed', start_date: '2026-01-25',
    cost_breakdown: { materials: 1_200_000_000, transactions: 500_000_000, commissions: 300_000_000 },
  },
  {
    project_id: 'proj-021', project_code: 'JMH-0635',
    project_name: 'Căn hộ Midtown Phú Mỹ Hưng',
    revenue: 4_800_000_000, costs: 3_800_000_000, profit: 1_000_000_000, margin: 20.8,
    status: 'in_progress', start_date: '2026-06-15',
    cost_breakdown: { materials: 2_300_000_000, transactions: 1_000_000_000, commissions: 500_000_000 },
  },
  {
    project_id: 'proj-022', project_code: 'JMH-0640',
    project_name: 'Nhà phố Gò Vấp - Chị Lan',
    revenue: 3_500_000_000, costs: 2_800_000_000, profit: 700_000_000, margin: 20.0,
    status: 'in_progress', start_date: '2026-07-01',
    cost_breakdown: { materials: 1_700_000_000, transactions: 700_000_000, commissions: 400_000_000 },
  },
  {
    project_id: 'proj-023', project_code: 'JMH-0616',
    project_name: 'Căn hộ Masteri An Phú',
    revenue: 5_200_000_000, costs: 4_200_000_000, profit: 1_000_000_000, margin: 19.2,
    status: 'in_progress', start_date: '2026-04-20',
    cost_breakdown: { materials: 2_600_000_000, transactions: 1_100_000_000, commissions: 500_000_000 },
  },
  // ── At Risk / Loss (2 dự án lỗ) ──
  {
    project_id: 'proj-024', project_code: 'JMH-0615',
    project_name: 'Shophouse Bến Thành - Quận 1',
    revenue: 6_500_000_000, costs: 6_900_000_000, profit: -400_000_000, margin: -6.2,
    status: 'at_risk', start_date: '2026-03-25',
    cost_breakdown: { materials: 4_300_000_000, transactions: 1_800_000_000, commissions: 800_000_000 },
  },
  {
    project_id: 'proj-025', project_code: 'JMH-0630',
    project_name: 'Căn hộ Quận 8 - Renovation',
    revenue: 2_800_000_000, costs: 3_200_000_000, profit: -400_000_000, margin: -14.3,
    status: 'at_risk', start_date: '2026-05-10',
    cost_breakdown: { materials: 2_000_000_000, transactions: 800_000_000, commissions: 400_000_000 },
  },
];

// Đồng bộ "câu chuyện số" demo toàn app (nguồn duy nhất: DEMO_PNL_SUMMARY trong lib/demo-data.ts —
// YTD 687,4 tỷ ≈ 98 tỷ/tháng, khớp dashboard CEO). Danh sách RAW ở trên chỉ giữ cấu trúc + tỷ lệ
// cost_breakdown; số tiền được thay bằng số chuẩn theo project_id để /pl không lệch trang chủ.
const PL_TARGETS = new Map(DEMO_PNL_SUMMARY.revenue_by_project.map(p => [p.project_id, p]));
const MOCK_PROJECT_PL: ProjectPL[] = MOCK_PROJECT_PL_RAW.map(p => {
  const t = PL_TARGETS.get(p.project_id);
  if (!t) return p;
  const rawCost = (p as any).costs || (p as any).cost || 0;
  const tCost = (t as any).costs || (t as any).cost || 0;
  const k = rawCost > 0 ? tCost / rawCost : 1;
  const materials = Math.round((p.cost_breakdown?.materials || 0) * k / 10_000_000) * 10_000_000;
  const commissions = Math.round((p.cost_breakdown?.commissions || 0) * k / 10_000_000) * 10_000_000;
  return {
    ...p,
    revenue: t.revenue, costs: t.cost, profit: t.profit, margin: t.margin_pct,
    cost_breakdown: p.cost_breakdown ? { materials, commissions, transactions: t.cost - materials - commissions } : p.cost_breakdown,
  };
});

// ── Helper: compute summary from a list of projects ────────
function computeSummary(items: ProjectPL[]): CompanyPLSummary {
  const total_revenue = items.reduce((s, p) => s + p.revenue, 0);
  const total_costs = items.reduce((s, p) => s + p.costs, 0);
  const net_profit = total_revenue - total_costs;
  return {
    total_revenue,
    total_costs,
    net_profit,
    margin: total_revenue > 0 ? (net_profit / total_revenue) * 100 : 0,
    project_count: items.length,
    profitable_projects: items.filter(p => p.profit > 0).length,
    loss_projects: items.filter(p => p.profit < 0).length,
  };
}

// ── Access denied view ─────────────────────────────────────
function AccessDenied() {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <span className="text-5xl block mb-4">🔒</span>
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Trang này chỉ dành cho Ban Giám đốc, Kế toán và Ban Quản trị.
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

// ── Skeleton loader ────────────────────────────────────────
function PLSkeleton() {
  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        <div className="skeleton h-8 w-72 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="glass-card p-5">
              <div className="skeleton h-3 w-24 mb-3 rounded" />
              <div className="skeleton h-7 w-32 mb-2 rounded" />
              <div className="skeleton h-3 w-20 rounded" />
            </div>
          ))}
        </div>
        <div className="glass-card p-6">
          <div className="skeleton h-4 w-40 mb-4 rounded" />
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="flex items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="skeleton h-4 w-20 rounded" />
              <div className="skeleton h-4 w-40 rounded" />
              <div className="skeleton h-4 w-24 rounded ml-auto" />
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-4 w-16 rounded" />
            </div>
          ))}
        </div>
      </div>
    </Sidebar>
  );
}

// ── Main Page ──────────────────────────────────────────────
export default function PLPage() {
  const { user, loading, isDemo } = useAuth();
  const router = useRouter();
  const [allProjects, setAllProjects] = useState<ProjectPL[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [plError, setPlError] = useState('');
  const [sortBy, setSortBy] = useState<'revenue' | 'profit' | 'margin'>('revenue');
  const [sortAsc, setSortAsc] = useState(false);

  // ── Filter state ──
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [filterMonth, setFilterMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [filterQuarter, setFilterQuarter] = useState(() => {
    const now = new Date();
    const q = Math.ceil((now.getMonth() + 1) / 3);
    return `${now.getFullYear()}-Q${q}`;
  });
  const [filterYear, setFilterYear] = useState(() => String(new Date().getFullYear()));
  const [customFrom, setCustomFrom] = useState('2026-01-01');
  const [customTo, setCustomTo] = useState('2026-12-31');
  const [customDays, setCustomDays] = useState('');
  const [detailProject, setDetailProject] = useState<ProjectPL | null>(null);  // modal chi tiết P&L dự án
  const [receivables, setReceivables] = useState<import('@/lib/api').ReceivablesResponse | null>(null);
  const [showReceivables, setShowReceivables] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // Phải thu theo hợp đồng — các đợt thanh toán pending của HĐ đã ký
  useEffect(() => {
    if (!user) return;
    api.getReceivables().then(setReceivables).catch(() => setReceivables(null));
  }, [user, isDemo]);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      if (isDemo) {
        setAllProjects(MOCK_PROJECT_PL);
      } else {
        try {
          const p = await api.getPnLProjects();
          const normalizedProjects: ProjectPL[] = (p || []).map((item: any) => ({
            project_id: item.project_id || '',
            project_code: item.project_code || '',
            project_name: item.project_name || '',
            revenue: item.revenue || 0,
            costs: item.costs || 0,
            profit: item.profit || 0,
            margin: item.margin_pct || item.margin || 0,
            status: item.status || 'active',
            start_date: item.start_date || '2026-01-01',
          }));
          setAllProjects(normalizedProjects);
          setPlError('');
        } catch {
          // TUYỆT ĐỐI không rơi về MOCK ở chế độ Làm việc — kế toán sẽ nhìn số bịa
          // tưởng là thật (audit 22/07). Hiện lỗi rõ ràng, danh sách để trống.
          setAllProjects([]);
          setPlError('Không tải được số liệu P&L từ máy chủ. Vui lòng tải lại trang hoặc báo kỹ thuật.');
        }
      }
    } catch (e) {
      console.warn('P&L API error:', e);
    } finally {
      setLoadingData(false);
    }
  }, [isDemo]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchData);
  }, [user, fetchData]);

  // ── Date filtering logic ──
  const filteredProjects = useMemo(() => {
    if (filterType === 'all') return allProjects;

    return allProjects.filter(p => {
      const d = new Date(p.start_date);
      if (isNaN(d.getTime())) return true;

      switch (filterType) {
        case 'month': {
          const [fy, fm] = filterMonth.split('-').map(Number);
          return d.getFullYear() === fy && (d.getMonth() + 1) === fm;
        }
        case 'quarter': {
          const [qy, qq] = filterQuarter.split('-Q').map(Number);
          const pq = Math.ceil((d.getMonth() + 1) / 3);
          return d.getFullYear() === qy && pq === qq;
        }
        case 'year': {
          return d.getFullYear() === Number(filterYear);
        }
        case 'custom': {
          if (customDays) {
            const now = new Date();
            const daysAgo = new Date(now.getTime() - Number(customDays) * 86400000);
            return d >= daysAgo && d <= now;
          }
          const from = new Date(customFrom);
          const to = new Date(customTo);
          return d >= from && d <= to;
        }
        default:
          return true;
      }
    });
  }, [allProjects, filterType, filterMonth, filterQuarter, filterYear, customFrom, customTo, customDays]);

  // ── Dynamic summary from filtered projects ──
  const summary = useMemo(() => computeSummary(filteredProjects), [filteredProjects]);

  // Auth gate
  if (loading) return <PLSkeleton />;
  if (!user) return null;

  // Role check
  const perms = getPermissions(user.role as UserRole);
  if (!perms.canViewPnL) return <AccessDenied />;

  // Sort handler
  const sortedProjects = [...filteredProjects].sort((a, b) => {
    const diff = a[sortBy] - b[sortBy];
    return sortAsc ? diff : -diff;
  });

  const toggleSort = (field: 'revenue' | 'profit' | 'margin') => {
    if (sortBy === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(field);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ field }: { field: string }) => (
    <span className="ml-1 inline-block text-[10px]" style={{ opacity: sortBy === field ? 1 : 0.3 }}>
      {sortBy === field ? (sortAsc ? '▲' : '▼') : '▲▼'}
    </span>
  );

  // Available months/quarters/years for selectors
  const availableMonths = [...new Set(allProjects.map(p => p.start_date.slice(0, 7)))].sort();
  const availableQuarters = [...new Set(allProjects.map(p => {
    const d = new Date(p.start_date);
    return `${d.getFullYear()}-Q${Math.ceil((d.getMonth() + 1) / 3)}`;
  }))].sort();
  const availableYears = [...new Set(allProjects.map(p => new Date(p.start_date).getFullYear().toString()))].sort();

  const monthLabel = (m: string) => {
    const [y, mo] = m.split('-');
    const months = ['', 'Th01', 'Th02', 'Th03', 'Th04', 'Th05', 'Th06', 'Th07', 'Th08', 'Th09', 'Th10', 'Th11', 'Th12'];
    return `${months[Number(mo)]}/${y}`;
  };

  // Active filter label for badge
  const getFilterLabel = (): string => {
    switch (filterType) {
      case 'all': return 'Tất cả';
      case 'month': return monthLabel(filterMonth);
      case 'quarter': return filterQuarter.replace('-', ' ');
      case 'year': return `Năm ${filterYear}`;
      case 'custom': return customDays ? `${customDays} ngày qua` : `${customFrom} → ${customTo}`;
      default: return '';
    }
  };

  return (
    <Sidebar>
      <div className="p-4 md:p-6 space-y-5 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl md:text-2xl font-bold">
              P&L <span className="gold-gradient">&mdash; Tổng quan Lợi nhuận</span>
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Phân tích lợi nhuận theo dự án và toàn công ty
            </p>
          </div>
          {isDemo && (
            <div className="px-3 py-1.5 rounded-lg text-center" style={{ background: 'var(--warning-bg)', border: '1px solid rgba(251,191,36,0.2)' }}>
              <span className="text-[0.6875rem] font-semibold" style={{ color: 'var(--warning)' }}>TẬP LUYỆN</span>
            </div>
          )}
        </div>

        {plError && (
          <div className="p-4 rounded-xl text-sm" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', color: '#F87171' }}>
            ⚠️ {plError}
          </div>
        )}

        {/* ── Date Filter Bar ── */}
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mr-1">📅 Lọc theo:</span>
            {(['all', 'month', 'quarter', 'year', 'custom'] as FilterType[]).map(ft => (
              <button
                key={ft}
                onClick={() => setFilterType(ft)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                  filterType === ft
                    ? 'text-white shadow-lg'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5'
                )}
                style={filterType === ft ? { background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' } : {}}
              >
                {ft === 'all' ? 'Tất cả' : ft === 'month' ? 'Tháng' : ft === 'quarter' ? 'Quý' : ft === 'year' ? 'Năm' : 'Tùy chọn'}
              </button>
            ))}
            {filterType !== 'all' && (
              <span className="ml-auto text-xs px-2 py-1 rounded-md bg-[var(--gold-500)]/10 text-[var(--gold-400)] font-medium">
                {getFilterLabel()} — {filteredProjects.length}/{allProjects.length} dự án
              </span>
            )}
          </div>

          {/* Filter selectors */}
          {filterType === 'month' && (
            <div className="flex items-center gap-2 flex-wrap">
              {availableMonths.map(m => (
                <button
                  key={m}
                  onClick={() => setFilterMonth(m)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                    filterMonth === m
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : 'text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--text-secondary)]'
                  )}
                >
                  {monthLabel(m)}
                </button>
              ))}
            </div>
          )}

          {filterType === 'quarter' && (
            <div className="flex items-center gap-2 flex-wrap">
              {availableQuarters.map(q => (
                <button
                  key={q}
                  onClick={() => setFilterQuarter(q)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                    filterQuarter === q
                      ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                      : 'text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--text-secondary)]'
                  )}
                >
                  {q.replace('-', ' ')}
                </button>
              ))}
            </div>
          )}

          {filterType === 'year' && (
            <div className="flex items-center gap-2 flex-wrap">
              {availableYears.map(y => (
                <button
                  key={y}
                  onClick={() => setFilterYear(y)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                    filterYear === y
                      ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      : 'text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--text-secondary)]'
                  )}
                >
                  Năm {y}
                </button>
              ))}
            </div>
          )}

          {filterType === 'custom' && (
            <div className="flex items-center gap-3 flex-wrap">
              {/* Quick presets */}
              <div className="flex items-center gap-1.5">
                {[7, 14, 30, 60, 90].map(d => (
                  <button
                    key={d}
                    onClick={() => { setCustomDays(String(d)); }}
                    className={cn(
                      'px-2.5 py-1 rounded text-xs font-medium transition-all border',
                      customDays === String(d)
                        ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                        : 'text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--text-secondary)]'
                    )}
                  >
                    {d} ngày
                  </button>
                ))}
              </div>
              <span className="text-xs text-[var(--text-muted)]">hoặc</span>
              {/* Custom range */}
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={customFrom}
                  onChange={(e) => { setCustomFrom(e.target.value); setCustomDays(''); }}
                  className="px-2 py-1.5 rounded-lg text-xs border bg-transparent text-[var(--text-primary)]"
                  style={{ borderColor: 'var(--border-subtle)' }}
                />
                <span className="text-xs text-[var(--text-muted)]">→</span>
                <input
                  type="date"
                  value={customTo}
                  onChange={(e) => { setCustomTo(e.target.value); setCustomDays(''); }}
                  className="px-2 py-1.5 rounded-lg text-xs border bg-transparent text-[var(--text-primary)]"
                  style={{ borderColor: 'var(--border-subtle)' }}
                />
              </div>
            </div>
          )}
        </div>

        {loadingData ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Đang tải dữ liệu P&L...
          </div>
        ) : (
          <>
            {/* ── Company Summary Cards ── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
              {/* Total Revenue */}
              <div className="glass-card p-4 md:p-5 border-l-2 border-l-emerald-500">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] md:text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Tổng Doanh thu</p>
                    <p className="text-lg md:text-2xl font-bold text-emerald-400">{formatCurrency(summary.total_revenue)}</p>
                    <p className="text-[10px] md:text-xs text-[var(--text-secondary)] mt-1">{summary.project_count} dự án</p>
                  </div>
                  <span className="text-xl md:text-2xl">&#x1F4B5;</span>
                </div>
              </div>

              {/* Total Costs */}
              <div className="glass-card p-4 md:p-5 border-l-2 border-l-red-500">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] md:text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Tổng Chi phí</p>
                    <p className="text-lg md:text-2xl font-bold text-red-400">{formatCurrency(summary.total_costs)}</p>
                    <p className="text-[10px] md:text-xs text-[var(--text-secondary)] mt-1">
                      {summary.total_revenue > 0 ? ((summary.total_costs / summary.total_revenue) * 100).toFixed(1) : '0'}% doanh thu
                    </p>
                  </div>
                  <span className="text-xl md:text-2xl">&#x1F4B8;</span>
                </div>
              </div>

              {/* Net Profit */}
              <div className="glass-card p-4 md:p-5 border-l-2 border-l-blue-500">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] md:text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Lợi nhuận ròng</p>
                    <p className={cn('text-lg md:text-2xl font-bold', summary.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {formatCurrency(summary.net_profit)}
                    </p>
                    <p className="text-[10px] md:text-xs text-[var(--text-secondary)] mt-1">
                      {summary.profitable_projects} lãi / {summary.loss_projects} lỗ
                    </p>
                  </div>
                  <span className="text-xl md:text-2xl">&#x1F4C8;</span>
                </div>
              </div>

              {/* Margin */}
              <div className="glass-card p-4 md:p-5 border-l-2" style={{ borderLeftColor: summary.margin >= 50 ? '#10B981' : summary.margin >= 20 ? '#F59E0B' : '#EF4444' }}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] md:text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">Biên lợi nhuận</p>
                    <p
                      className="text-lg md:text-2xl font-bold"
                      style={{ color: summary.margin >= 50 ? '#10B981' : summary.margin >= 20 ? '#F59E0B' : '#EF4444' }}
                    >
                      {(summary.margin ?? 0).toFixed(1)}%
                    </p>
                    <p className="text-[10px] md:text-xs text-[var(--text-secondary)] mt-1">TB toàn công ty</p>
                  </div>
                  <span className="text-xl md:text-2xl">&#x1F3AF;</span>
                </div>
              </div>
            </div>

            {/* ── Visual Summary Bar ── */}
            <div className="glass-card p-4 md:p-5">
              <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Cơ cấu Thu - Chi</h3>
              <div className="h-8 rounded-full overflow-hidden flex" style={{ background: 'rgba(255,255,255,0.05)' }}>
                <div
                  className="h-full transition-all duration-1000 rounded-l-full"
                  style={{
                    width: `${Math.min(100, summary.total_revenue > 0 ? (summary.total_costs / summary.total_revenue) * 100 : 0)}%`,
                    background: 'linear-gradient(90deg, rgba(239,68,68,0.4), rgba(239,68,68,0.2))',
                  }}
                />
              </div>
              <div className="flex flex-wrap justify-between mt-2 gap-2">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(16,185,129,0.4)' }} />
                  <span className="text-xs text-[var(--text-secondary)]">
                    Doanh thu: {formatCurrency(summary.total_revenue)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(239,68,68,0.4)' }} />
                  <span className="text-xs text-[var(--text-secondary)]">
                    Chi phí: {formatCurrency(summary.total_costs)} ({summary.total_revenue > 0 ? ((summary.total_costs / summary.total_revenue) * 100).toFixed(1) : '0'}%)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: 'rgba(59,130,246,0.4)' }} />
                  <span className="text-xs text-[var(--text-secondary)]">
                    Lợi nhuận: {formatCurrency(summary.net_profit)}
                  </span>
                </div>
              </div>
            </div>

            {/* ── Phải thu theo hợp đồng — dòng tiền sắp về ── */}
            {receivables && receivables.contract_count > 0 && (
              <div className="glass-card p-4 md:p-5 border-l-2 border-l-amber-500">
                <button onClick={() => setShowReceivables(v => !v)} className="w-full flex items-center justify-between gap-3">
                  <div className="text-left">
                    <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide">Phải thu theo hợp đồng</p>
                    <p className="text-lg md:text-2xl font-bold text-amber-400 mt-1">{formatCurrency(receivables.total_receivable)}</p>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{receivables.contract_count} hợp đồng còn đợt thanh toán chờ thu</p>
                  </div>
                  <span className="text-xs text-[var(--text-muted)]">{showReceivables ? 'Thu gọn ▲' : 'Chi tiết ▼'}</span>
                </button>
                {showReceivables && (
                  <div className="mt-4 space-y-3">
                    {receivables.contracts.map(c => (
                      <div key={c.contract_id} className="p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div>
                            <p className="text-sm font-semibold text-white">{c.contract_code} · {c.project_name}</p>
                            <p className="text-[11px] text-[var(--text-muted)]">
                              {c.signed_date ? `Ký ${new Date(c.signed_date).toLocaleDateString('vi-VN')} · ` : ''}HĐ {formatCurrency(c.total_value)}
                            </p>
                          </div>
                          <p className="text-sm font-bold text-amber-400">{formatCurrency(c.pending_amount)}</p>
                        </div>
                        <div className="mt-2 space-y-1">
                          {c.pending_installments.map((inst, i) => (
                            <div key={i} className="flex items-center justify-between text-xs text-[var(--text-secondary)]">
                              <span>• {inst.name} ({inst.percentage}%)</span>
                              <span className="font-mono">{formatCurrency(inst.amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── Per-Project P&L ── */}
            <div className="glass-card overflow-hidden">
              <div className="p-4 md:p-5 pb-0 flex items-center justify-between flex-wrap gap-2">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                  Lợi nhuận theo Dự án ({sortedProjects.length})
                </h3>
              </div>

              {/* Desktop table */}
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                      <th className="text-left p-3 text-xs text-[var(--text-muted)]">#</th>
                      <th className="text-left p-3 text-xs text-[var(--text-muted)]">Dự án</th>
                      <th className="text-left p-3 text-xs text-[var(--text-muted)]">Trạng thái</th>
                      <th className="text-center p-3 text-xs text-[var(--text-muted)]">Ngày BĐ</th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('revenue')}
                      >
                        Doanh thu <SortIcon field="revenue" />
                      </th>
                      <th className="text-right p-3 text-xs text-[var(--text-muted)]">Chi phí</th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('profit')}
                      >
                        Lợi nhuận <SortIcon field="profit" />
                      </th>
                      <th
                        className="text-right p-3 text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-secondary)] select-none"
                        onClick={() => toggleSort('margin')}
                      >
                        Biên LN <SortIcon field="margin" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedProjects.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="text-center p-8 text-[var(--text-muted)]">
                          Không có dự án trong khoảng thời gian đã chọn
                        </td>
                      </tr>
                    ) : sortedProjects.map((p, idx) => (
                      <tr
                        key={p.project_id}
                        onClick={() => setDetailProject(p)}
                        className="border-b hover:bg-white/[0.05] transition-colors cursor-pointer"
                        style={{ borderColor: 'var(--border-subtle)' }}
                        title="Bấm để xem chi tiết P&L dự án"
                      >
                        <td className="p-3 text-xs text-[var(--text-muted)]">{idx + 1}</td>
                        <td className="p-3">
                          <div>
                            <span className="font-mono text-xs text-[var(--gold-400)]">{p.project_code} ›</span>
                            <p className="text-sm font-medium mt-0.5">{p.project_name}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <StatusBadge status={p.status} margin={p.margin} />
                        </td>
                        <td className="p-3 text-center text-xs text-[var(--text-secondary)]">
                          {new Date(p.start_date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                        </td>
                        <td className="p-3 text-right font-semibold text-emerald-400">
                          {formatCurrency(p.revenue)}
                        </td>
                        <td className="p-3 text-right text-red-400">
                          {formatCurrency(p.costs)}
                        </td>
                        <td className={cn('p-3 text-right font-bold', p.profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {p.profit >= 0 ? '+' : ''}{formatCurrency(p.profit)}
                        </td>
                        <td className="p-3 text-right">
                          <span
                            className={cn(
                              'text-xs font-bold px-2 py-1 rounded-lg',
                              p.margin >= 50 ? 'bg-emerald-500/15 text-emerald-400' :
                              p.margin >= 20 ? 'bg-amber-500/15 text-amber-400' :
                              'bg-red-500/15 text-red-400'
                            )}
                          >
                            {p.margin >= 0 ? '+' : ''}{p.margin.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {/* Totals row */}
                  {sortedProjects.length > 0 && (
                    <tfoot>
                      <tr className="border-t-2 font-bold" style={{ borderColor: 'var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                        <td className="p-3"></td>
                        <td className="p-3 text-sm gold-gradient">TỔNG CỘNG</td>
                        <td className="p-3"></td>
                        <td className="p-3"></td>
                        <td className="p-3 text-right text-emerald-400">
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.revenue, 0))}
                        </td>
                        <td className="p-3 text-right text-red-400">
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.costs, 0))}
                        </td>
                        <td className={cn('p-3 text-right', sortedProjects.reduce((s, p) => s + p.profit, 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {formatCurrency(sortedProjects.reduce((s, p) => s + p.profit, 0))}
                        </td>
                        <td className="p-3 text-right">
                          <span className="text-xs font-bold px-2 py-1 rounded-lg bg-[#C9A96E]/15 text-[#C9A96E]">
                            {(() => {
                              const totalRev = sortedProjects.reduce((s, p) => s + p.revenue, 0);
                              const totalCost = sortedProjects.reduce((s, p) => s + p.costs, 0);
                              return totalRev > 0 ? ((totalRev - totalCost) / totalRev * 100).toFixed(1) : '0.0';
                            })()}%
                          </span>
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>

            {/* ── Mobile Cards (visible below lg) ── */}
            <div className="lg:hidden space-y-3">
              {sortedProjects.length === 0 ? (
                <div className="glass-card p-6 text-center text-[var(--text-muted)] text-sm">
                  Không có dự án trong khoảng thời gian đã chọn
                </div>
              ) : sortedProjects.map((p, idx) => (
                <div key={p.project_id} className="glass-card p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[var(--text-muted)]">#{idx + 1}</span>
                        <span className="font-mono text-xs text-[var(--gold-400)]">{p.project_code}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">
                          {new Date(p.start_date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-sm font-medium mt-0.5">{p.project_name}</p>
                    </div>
                    <StatusBadge status={p.status} margin={p.margin} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Doanh thu</p>
                      <p className="text-sm font-semibold text-emerald-400">{formatCurrency(p.revenue)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Chi phí</p>
                      <p className="text-sm text-red-400">{formatCurrency(p.costs)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Lợi nhuận</p>
                      <p className={cn('text-sm font-bold', p.profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {p.profit >= 0 ? '+' : ''}{formatCurrency(p.profit)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Biên LN</p>
                      <span
                        className={cn(
                          'text-xs font-bold px-2 py-0.5 rounded',
                          p.margin >= 50 ? 'bg-emerald-500/15 text-emerald-400' :
                          p.margin >= 20 ? 'bg-amber-500/15 text-amber-400' :
                          'bg-red-500/15 text-red-400'
                        )}
                      >
                        {p.margin >= 0 ? '+' : ''}{p.margin.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}

              {/* Mobile totals */}
              {sortedProjects.length > 0 && (
                <div className="glass-card p-4" style={{ borderTop: '2px solid var(--gold-500)', background: 'rgba(201,169,110,0.05)' }}>
                  <p className="text-sm font-bold gold-gradient mb-3">TỔNG CỘNG ({sortedProjects.length} dự án)</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Doanh thu</p>
                      <p className="text-sm font-bold text-emerald-400">{formatCurrency(sortedProjects.reduce((s, p) => s + p.revenue, 0))}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Chi phí</p>
                      <p className="text-sm font-bold text-red-400">{formatCurrency(sortedProjects.reduce((s, p) => s + p.costs, 0))}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Lợi nhuận</p>
                      <p className={cn('text-sm font-bold', sortedProjects.reduce((s, p) => s + p.profit, 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {formatCurrency(sortedProjects.reduce((s, p) => s + p.profit, 0))}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase">Biên LN</p>
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-[#C9A96E]/15 text-[#C9A96E]">
                        {(() => {
                          const r = sortedProjects.reduce((s, p) => s + p.revenue, 0);
                          const c = sortedProjects.reduce((s, p) => s + p.costs, 0);
                          return r > 0 ? ((r - c) / r * 100).toFixed(1) : '0.0';
                        })()}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Modal chi tiết P&L dự án — bấm dòng để mở (bug feedback #8) */}
      {detailProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setDetailProject(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg rounded-2xl p-6 animate-in" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <span className="font-mono text-xs text-[var(--gold-400)]">{detailProject.project_code}</span>
                <h3 className="text-lg font-bold text-[var(--text-primary)]">{detailProject.project_name}</h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">Bắt đầu: {new Date(detailProject.start_date).toLocaleDateString('vi-VN')}</p>
              </div>
              <button onClick={() => setDetailProject(null)} className="text-[var(--text-muted)] hover:text-white text-xl leading-none">×</button>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                <div className="text-[10px] text-[var(--text-muted)]">Doanh thu</div>
                <div className="text-sm font-bold text-emerald-400">{formatCurrency(detailProject.revenue)}</div>
              </div>
              <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                <div className="text-[10px] text-[var(--text-muted)]">Chi phí</div>
                <div className="text-sm font-bold text-red-400">{formatCurrency(detailProject.costs)}</div>
              </div>
              <div className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                <div className="text-[10px] text-[var(--text-muted)]">Lợi nhuận</div>
                <div className={cn('text-sm font-bold', detailProject.profit >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                  {detailProject.profit >= 0 ? '+' : ''}{formatCurrency(detailProject.profit)}
                </div>
              </div>
            </div>

            <div className="rounded-xl p-4 mb-3" style={{ background: 'var(--surface-2)' }}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-semibold text-[var(--text-secondary)]">Biên lợi nhuận</span>
                <span className={cn('text-lg font-bold', detailProject.margin >= 20 ? 'text-emerald-400' : detailProject.margin >= 0 ? 'text-amber-400' : 'text-red-400')}>
                  {detailProject.margin >= 0 ? '+' : ''}{detailProject.margin.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, detailProject.margin))}%`, background: detailProject.margin >= 20 ? '#34d399' : detailProject.margin >= 0 ? '#fbbf24' : '#f87171' }} />
              </div>
            </div>

            {detailProject.cost_breakdown && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-[var(--text-muted)] uppercase">Phân tích chi phí</div>
                {[
                  { label: '📦 Vật tư', value: detailProject.cost_breakdown.materials },
                  { label: '🔨 Nhân công / giao dịch', value: detailProject.cost_breakdown.transactions },
                  { label: '💰 Hoa hồng', value: detailProject.cost_breakdown.commissions },
                ].map(row => (
                  <div key={row.label} className="flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">{row.label}</span>
                    <span className="font-medium text-[var(--text-primary)]">{formatCurrency(row.value)}</span>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => { setDetailProject(null); router.push('/projects'); }}
              className="mt-4 w-full py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ background: 'var(--gold-500)' }}
            >
              Mở dự án đầy đủ →
            </button>
          </div>
        </div>
      )}
    </Sidebar>
  );
}

// ── Status Badge Component ─────────────────────────────────
function StatusBadge({ status, margin }: { status: string; margin: number }) {
  if (margin < 0) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-red-500/15 text-red-400">
        Lỗ
      </span>
    );
  }
  if (margin < 15) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-500/15 text-amber-400">
        Biên LN thấp
      </span>
    );
  }
  if (status === 'completed') {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">
        Hoàn thành
      </span>
    );
  }
  if (status === 'at_risk') {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-red-500/15 text-red-400">
        Rủi ro
      </span>
    );
  }
  return (
    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
      Đang chạy
    </span>
  );
}
