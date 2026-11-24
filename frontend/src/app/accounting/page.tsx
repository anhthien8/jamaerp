'use client';

import { useXacNhan } from '@/components/ui/XacNhan';
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Transaction, AccountingSummary, Commission, PayrollEntry, Project, User, extractItems, fetchAllPages } from '@/lib/api';
import { formatCurrency, formatDate, cn, chuanHoaTim } from '@/lib/utils';
import { labelOf, TX_CATEGORY_LABELS, COMMISSION_TYPE_LABELS, MILESTONE_LABELS, ROLE_LABELS } from '@/lib/labels';
import { useToast } from '@/components/ui/Toast';
import AccessDenied from '@/components/ui/AccessDenied';
import LineIcon from '@/components/ui/LineIcon';
import InfoTip from '@/components/ui/InfoTip';

type Tab = 'overview' | 'transactions' | 'commissions' | 'payroll';

export default function AccountingPage() {
  const xacNhan = useXacNhan();
  const { user, loading, effectivePermissions } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  // Mở đúng tab theo link (`/accounting?tab=payroll` từ Tổng quan). Đọc lúc khởi tạo: trang trả null khi chưa có
  // người dùng nên máy chủ và trình duyệt vẫn dựng ra cùng một thứ.
  const [tab, setTab] = useState<Tab>(() => {
    const tuLink = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('tab') : null;
    return (['transactions', 'commissions', 'payroll'] as const).find(k => k === tuLink) || 'overview';
  });
  const [summary, setSummary] = useState<AccountingSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [payroll, setPayroll] = useState<PayrollEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingData, setLoadingData] = useState(true);

  // Filters
  const [txSearch, setTxSearch] = useState('');
  const [txType, setTxType] = useState('all');
  const [txCategory, setTxCategory] = useState('all');
  const [txSort, setTxSort] = useState<'date' | 'amount'>('date');
  const [txSortAsc, setTxSortAsc] = useState(false);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [editingTx, setEditingTx] = useState<Transaction | null>(null);
  const [periodFilter, setPeriodFilter] = useState('all');

  // Create Transaction modal state
  const [showTxForm, setShowTxForm] = useState(false);
  const [txForm, setTxForm] = useState({
    type: 'expense',
    category: 'other',
    description: '',
    amount: '',
    date: new Date().toISOString().slice(0, 10),
    project_id: '',
    user_id: '',
  });
  const [savingTx, setSavingTx] = useState(false);
  const [activeProjects, setActiveProjects] = useState<Project[]>([]);
  const [staffList, setStaffList] = useState<User[]>([]);
  const [txAmountDisplay, setTxAmountDisplay] = useState('');

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
  }, [user, loading, router]);

  // Chỉ Giám đốc + Kế toán được xem bảng lương; các vai trò khác gọi /payroll sẽ bị 403.
  // Trước 12/08/2026 lời gọi này nằm chung Promise.all nên 403 làm hỏng CẢ trang kế toán
  // (Trưởng nhóm và Nhập liệu chỉ thấy "Không thể tải dữ liệu kế toán").
  // Từ 13/08/2026 dùng effectivePermissions (đã trộn quyền backend trả về) thay vì
  // ma trận cục bộ — trang hiển thị đúng những gì máy chủ thật sự cho phép.
  const canSeePayroll = !!user && effectivePermissions.canViewPayroll;
  // Tổng quan + sổ giao dịch nằm sau cửa «Xem Lợi nhuận (P&L)» — backend chặn thật,
  // nên vai trò không có quyền thì khỏi gọi (đỡ ăn 403) và ẩn luôn 2 tab tương ứng.
  const canSeePnL = !!user && effectivePermissions.canViewPnL;
  // Ghi sổ (tạo/sửa giao dịch) — backend accounting.py chỉ cho admin + kế toán.
  // Trưởng nhóm và Nhập liệu xem được sổ nhưng không sửa, nên ẩn nút cho khỏi ăn 403.
  const canEditAccounting = user?.role === 'admin' || user?.role === 'accountant';

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    setError(null);
    // allSettled: một mục hỏng thì chỉ mục đó trống, phần còn lại vẫn hiện.
    const [sRes, tRes, cRes, pRes] = await Promise.allSettled([
      canSeePnL ? api.getAccountingSummary() : Promise.resolve(null),
      // Tải ĐỦ mọi trang (24/11): trước đây chỉ lấy 50 dòng đầu rồi cộng «Tổng thu / Tổng chi /
      // Lợi nhuận» như thể đủ sổ — sổ vượt 50 dòng là tổng sai mà nhìn vẫn bình thường.
      canSeePnL ? fetchAllPages(q => api.getTransactions(q)) : Promise.resolve([]),
      fetchAllPages(q => api.getCommissions(q)),
      canSeePayroll ? fetchAllPages(q => api.getPayroll(q)) : Promise.resolve([]),
    ]);
    if (sRes.status === 'fulfilled') setSummary(sRes.value);
    if (tRes.status === 'fulfilled') setTransactions(extractItems(tRes.value));
    if (cRes.status === 'fulfilled') setCommissions(extractItems(cRes.value));
    if (pRes.status === 'fulfilled') setPayroll(extractItems(pRes.value));

    const hong = [
      sRes.status === 'rejected' && 'tổng quan',
      tRes.status === 'rejected' && 'giao dịch',
      cRes.status === 'rejected' && 'hoa hồng',
      pRes.status === 'rejected' && 'bảng lương',
    ].filter(Boolean) as string[];
    if (hong.length) {
      console.warn('Accounting API error:', { sRes, tRes, cRes, pRes });
      setError(`Chưa tải được: ${hong.join(', ')}. Phần đang trống là do lỗi tải, không phải bằng 0.`);
    }
    setLoadingData(false);
  }, [canSeePayroll, canSeePnL]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchData);
  }, [user, fetchData]);

  // Quyền backend về sau (tải nền) có thể tắt P&L khi đang đứng ở tab bị ẩn — nhảy
  // sang tab Hoa hồng thay vì để người dùng kẹt trên tab trống không bấm lại được.
  useEffect(() => {
    if (user && ((!canSeePnL && (tab === 'overview' || tab === 'transactions')) || (!canSeePayroll && tab === 'payroll'))) {
      void Promise.resolve().then(() => setTab('commissions'));
    }
  }, [user, canSeePnL, canSeePayroll, tab]);

  // Format number with thousand separators for VND display
  const formatAmountInput = (raw: string) => {
    const digits = raw.replace(/\D/g, '');
    if (!digits) return '';
    return Number(digits).toLocaleString('vi-VN');
  };

  /** Mở bảng Giao dịch. Truyền `tx` để SỬA, bỏ trống để TẠO MỚI.
   *
   *  Trước 12/08/2026 nút "Sửa" chỉ bật một biến `formOpen` không nối với gì —
   *  bấm vào là không có chuyện gì xảy ra, kế toán tưởng máy treo.
   */
  const openTxForm = async (tx?: Transaction, nhanBan = false) => {
    const today = new Date().toISOString().slice(0, 10);
    setEditingTx(nhanBan ? null : tx ?? null);
    setTxForm(tx
      ? {
          type: tx.type, category: tx.category, description: tx.description,
          amount: String(tx.amount), date: nhanBan ? today : (tx.date || today).slice(0, 10),
          project_id: tx.project_id || '', user_id: tx.related_user_id || '',
        }
      : { type: 'expense', category: 'other', description: '', amount: '', date: today, project_id: '', user_id: '' });
    setTxAmountDisplay(tx ? Number(tx.amount).toLocaleString('vi-VN') : '');
    setShowTxForm(true);
    // Load active projects + danh sách nhân viên (cho giao dịch Lương/Hoa hồng)
    try {
      const result = extractItems(await api.getProjects({ status: 'active' }));
      setActiveProjects(result);
      // Nhân bản: dự án đã đóng không còn trong ô chọn — bỏ gắn để khỏi cộng ngầm vào chi phí dự án
      if (nhanBan && tx?.project_id && !result.some(p => p.id === tx.project_id)) setTxForm(f => ({ ...f, project_id: '' }));
    } catch {
      setActiveProjects([]);
      if (nhanBan) setTxForm(f => ({ ...f, project_id: '' }));
    }
    try {
      setStaffList(extractItems(await api.getUsers()));
    } catch {
      setStaffList([]);
    }
  };

  const handleTxAmountChange = (raw: string) => {
    const digits = raw.replace(/\D/g, '');
    setTxForm(f => ({ ...f, amount: digits }));
    setTxAmountDisplay(formatAmountInput(digits));
  };

  // `?tab=transactions&new=1` từ nút «+» tạo nhanh: mở sẵn form Giao dịch mới, một lần, rồi gỡ tham số khỏi URL.
  useEffect(() => {
    if (!canEditAccounting || new URLSearchParams(window.location.search).get('new') !== '1') return;
    window.history.replaceState(null, '', '/accounting?tab=transactions');
    void Promise.resolve().then(() => openTxForm());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canEditAccounting]);

  // Duyệt / đánh dấu chi trả hoa hồng (admin + kế toán) — trước đây tab chỉ xem,
  // hoa hồng kẹt ở "Chờ" vĩnh viễn không ai chuyển trạng thái được (audit 22/07)
  const canActCommission = user?.role === 'admin' || user?.role === 'accountant';
  /** Số tiền viết đủ cho dòng chi tiết. `formatCurrency` làm tròn về triệu (12.700.000 đ → «13 triệu») — chỉ hợp thẻ tổng. */
  const tienDu = (v?: number | null) => (v == null ? '—' : `${Math.round(v).toLocaleString('vi-VN')} đ`);
  // Lọc theo trạng thái + khoá nút khi đang gửi (id khoản đang gửi, hoặc 'loat' khi duyệt cả loạt).
  const [hhLoc, setHhLoc] = useState('all');
  const [hhDang, setHhDang] = useState('');
  const handleCommissionStatus = async (id: string, status: 'approved' | 'paid') => {
    if (hhDang) return;
    setHhDang(id);
    try {
      await api.updateCommissionStatus(id, status);
      setCommissions(prev => prev.map(c => (c.id === id ? { ...c, status } : c)));
      toast(status === 'approved' ? 'Đã duyệt hoa hồng' : 'Đã đánh dấu chi trả', 'success');
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không cập nhật được hoa hồng'}`, 'error');
    } finally { setHhDang(''); }
  };
  /** Duyệt mọi khoản đang «Chờ duyệt». Gửi tuần tự: khoản nào máy chủ từ chối (VD kỳ lương đã khoá) thì bỏ qua,
   *  các khoản còn lại vẫn duyệt, cuối cùng báo rõ được mấy khoản. Chỉ DUYỆT — chi trả vẫn bấm từng khoản. */
  const duyetTatCaHoaHong = async () => {
    const ds = commissions.filter(c => c.status === 'pending');
    if (!ds.length || hhDang) return;
    const tong = ds.reduce((s, c) => s + (c.commission_amount || 0), 0);
    if (!await xacNhan(`Duyệt ${ds.length} khoản hoa hồng đang chờ, tổng ${tienDu(tong)}?`)) return;
    setHhDang('loat');
    let ok = 0;
    let loiDau = '';
    for (const c of ds) {
      try {
        await api.updateCommissionStatus(c.id, 'approved');
        ok += 1;
        setCommissions(prev => prev.map(x => (x.id === c.id ? { ...x, status: 'approved' } : x)));
      } catch (e) { loiDau ||= e instanceof Error ? e.message : 'lỗi không rõ'; }
    }
    setHhDang('');
    if (ok === ds.length) toast(`Đã duyệt ${ok} khoản hoa hồng`, 'success');
    else toast(`Đã duyệt ${ok}/${ds.length} khoản — ${ds.length - ok} khoản không duyệt được: ${loiDau}`, 'error');
  };

  const commissionChip = (status: string) =>
    status === 'paid'
      ? { cls: 'bg-emerald-500/15 text-emerald-400', label: 'Đã trả' }
      : status === 'approved'
        ? { cls: 'bg-sky-500/15 text-sky-400', label: 'Đã duyệt' }
        : status === 'cho_moc'
          // Theo JD: đã tính nhưng chưa tới mốc chi (VD thiết kế chờ thu đợt 2)
          ? { cls: 'bg-white/5 text-[var(--text-muted)]', label: 'Chờ mốc' }
          : { cls: 'bg-amber-500/15 text-amber-400', label: 'Chờ duyệt' };

  /** Lấy câu báo lỗi của máy chủ nếu có (VD "Không có quyền..."), không thì dùng câu mặc định. */
  const loiThaoTac = (e: unknown, macDinh: string) =>
    e instanceof Error && e.message ? e.message : macDinh;

  /** Nhân bản khoản chi lặp lại (thuê VP, điện, internet…): mở form TẠO MỚI điền sẵn,
   *  ngày = hôm nay; kế toán soát rồi mới bấm «Tạo giao dịch». Cảnh báo nếu tháng này đã có khoản giống hệt. */
  const nhanBanTx = async (tx: Transaction) => {
    const thang = new Date().toISOString().slice(0, 7);
    const daCo = transactions.some(t => t.type === tx.type && t.description === tx.description
      && Number(t.amount) === Number(tx.amount) && (t.date || '').slice(0, 7) === thang);
    if (daCo && !await xacNhan('Tháng này đã có giao dịch cùng mô tả và số tiền. Vẫn nhân bản?')) return;
    openTxForm(tx, true);
  };

  const handleCreateTransaction = async () => {
    if (!txForm.description.trim() || !txForm.amount || Number(txForm.amount) <= 0) {
      toast('Vui lòng nhập đầy đủ mô tả và số tiền', 'error');
      return;
    }
    setSavingTx(true);
    const payload = {
      type: txForm.type,
      category: txForm.category,
      description: txForm.description.trim(),
      amount: Number(txForm.amount),
      date: txForm.date,
      project_id: txForm.project_id || undefined,
      user_id: txForm.user_id || undefined,
    };
    try {
      if (editingTx) {
        const updated = await api.updateTransaction(editingTx.id, payload);
        setTransactions(prev => prev.map(t => (t.id === editingTx.id ? updated : t)));
      } else {
        const created = await api.createTransaction(payload);
        setTransactions(prev => [created, ...prev]);
      }
      setShowTxForm(false);
      setEditingTx(null);
      toast(editingTx ? 'Cập nhật giao dịch thành công' : 'Tạo giao dịch thành công', 'success');
      fetchData();
    } catch (e) {
      toast(loiThaoTac(e, editingTx ? 'Lỗi khi cập nhật giao dịch' : 'Lỗi khi tạo giao dịch'), 'error');
    } finally {
      setSavingTx(false);
    }
  };

  if (loading || !user) return null;

  const perms = effectivePermissions;
  if (!perms.canViewAccounting) return <AccessDenied />;

  const ALL_TABS: { key: Tab; label: string; icon: string }[] = [
    { key: 'overview', label: 'Tổng quan', icon: 'chart' },
    { key: 'transactions', label: 'Giao dịch', icon: 'wallet' },
    { key: 'commissions', label: 'Hoa hồng', icon: 'money' },
    { key: 'payroll', label: 'Bảng lương', icon: 'clipboard' },
  ];

  // Filter tabs based on role permissions
  const TABS = ALL_TABS.filter(t => {
    if ((t.key === 'overview' || t.key === 'transactions') && !perms.canViewPnL) return false;
    if (t.key === 'payroll' && !perms.canViewPayroll) return false;
    return true;
  });

  // Filter by period for overview
  const filterByPeriod = (txs: Transaction[]) => {
    if (periodFilter === 'all') return txs;
    const now = new Date();
    return txs.filter(tx => {
      const txDate = new Date(tx.date);
      if (periodFilter === 'month') {
        return txDate.getMonth() === now.getMonth() && txDate.getFullYear() === now.getFullYear();
      }
      if (periodFilter === 'quarter') {
        const q = Math.floor(now.getMonth() / 3);
        const txQ = Math.floor(txDate.getMonth() / 3);
        return txDate.getFullYear() === now.getFullYear() && txQ === q;
      }
      if (periodFilter === 'year') {
        return txDate.getFullYear() === now.getFullYear();
      }
      return true;
    });
  };

  const filteredTx = filterByPeriod(transactions);
  const filteredIncome = filteredTx.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0);
  const filteredExpense = filteredTx.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0);

  // Số dư thu-chi: trong sổ demo, thu thiết kế 25% ≈ chi (vật tư 15% + nhân công 10%) nên chênh
  // lệch chỉ là sai số làm tròn từng giao dịch (vài đồng). Làm tròn về triệu để không hiện
  // "Lợi nhuận: 2 đ" vô nghĩa — phản ánh đúng độ phân giải tiền tệ của báo cáo (số dư thực ≈ 0).
  const filteredNet = Math.round((filteredIncome - filteredExpense) / 1_000_000) * 1_000_000;

  // Danh mục lấy từ ĐÚNG tập giao dịch đang lọc (trước đây dùng summary.by_category toàn kỳ,
  // nên khi lọc "Tháng này" một danh mục có thể vượt Tổng thu/Tổng chi của thẻ — con số vô lý).
  const filteredByCategory = Object.values(
    filteredTx.reduce<Record<string, { category: string; type: string; total: number; count: number }>>((acc, t) => {
      const key = `${t.type}:${t.category}`;
      (acc[key] ??= { category: t.category, type: t.type, total: 0, count: 0 });
      acc[key].total += t.amount;
      acc[key].count += 1;
      return acc;
    }, {})
  ).sort((a, b) => b.total - a.total);

  const PERIOD_LABEL: Record<string, string> = { all: 'tất cả', month: 'tháng này', quarter: 'quý này', year: 'năm nay' };

  // Filter commissions based on role
  const hhTheoQuyen = commissions.filter(c => {
    if (user.role === 'data_entry') return c.user_id === user.id;
    if (user.role === 'leader') return true; // team sees all for now
    return true; // admin/accountant see all
  });
  const visibleCommissions = hhTheoQuyen.filter(c => hhLoc === 'all' || c.status === hhLoc);
  const soHhCho = hhTheoQuyen.filter(c => c.status === 'pending').length;

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Kế toán &amp; Tài chính</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">Quản lý thu chi, hoa hồng, lương</p>
          </div>
        </div>

        {/* Cảnh báo cục bộ: chỉ báo phần nào chưa tải được, KHÔNG che cả trang như trước. */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-center justify-between gap-4">
            <span><LineIcon name="alert" size={16} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{error}</span>
            <button
              onClick={() => { setError(null); void fetchData(); }}
              className="shrink-0 px-3 py-1.5 rounded-lg border border-red-500/30 hover:bg-red-500/15 transition-colors"
            >
              Thử lại
            </button>
          </div>
        )}

        {/* Tab Bar */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--surface-2)' }}>
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex-1 py-2 rounded-lg text-xs font-medium transition-all',
                tab === t.key
                  ? 'bg-[var(--gold-500)]/20 text-[var(--gold-500)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              )}
            >
              <LineIcon name={t.icon} size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />{t.label}
            </button>
          ))}
        </div>

        {loadingData ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            Đang tải...
          </div>
        ) : (
          <>
            {/* ── Overview Tab ── */}
            {tab === 'overview' && summary && (
              <div className="space-y-4">
                <div className="flex gap-2 mb-4">
                  {['all', 'month', 'quarter', 'year'].map(period => (
                    <button
                      key={period}
                      onClick={() => setPeriodFilter(period)}
                      className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                      style={{
                        background: periodFilter === period ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
                        color: periodFilter === period ? 'var(--gold-400)' : 'var(--text-tertiary)',
                        border: `1px solid ${periodFilter === period ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                      }}
                    >
                      {period === 'all' ? 'Tất cả' : period === 'month' ? 'Tháng này' : period === 'quarter' ? 'Quý này' : 'Năm nay'}
                    </button>
                  ))}
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="glass-card p-5 border-l-2 border-l-emerald-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="cash" size={16} className="inline-block align-[-2px] mr-1.5" />Tổng thu</p>
                    <p className="text-xl font-bold text-emerald-400">{formatCurrency(filteredIncome)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-red-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="cash" size={16} className="inline-block align-[-2px] mr-1.5" />Tổng chi</p>
                    <p className="text-xl font-bold text-red-400">{formatCurrency(filteredExpense)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-blue-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="trendUp" size={16} className="inline-block align-[-2px] mr-1.5" />Lợi nhuận</p>
                    <p className={cn('text-xl font-bold', filteredNet >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {formatCurrency(filteredNet)}
                    </p>
                  </div>
                </div>

                {/* Financial Summary */}
                <div className="glass-card p-5">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Tóm tắt tài chính</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-[var(--text-secondary)]">Tỷ lệ chi/thu</span>
                      <span className="text-sm font-semibold text-amber-400">
                        {filteredIncome > 0 ? ((filteredExpense / filteredIncome) * 100).toFixed(1) : '0'}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-[var(--text-secondary)]">Số giao dịch ({PERIOD_LABEL[periodFilter]})</span>
                      <span className="text-sm font-semibold text-blue-400">{filteredTx.length}</span>
                    </div>
                  </div>
                </div>

                {/* By Category */}
                <div className="glass-card p-5">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Theo danh mục</h3>
                  {filteredByCategory.length === 0 ? (
                    <p className="text-sm text-center text-[var(--text-muted)] py-4">Chưa có dữ liệu</p>
                  ) : (
                    <div className="space-y-2">
                      {filteredByCategory.map((cat, i) => (
                        <div key={i} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5">
                          <div className="flex items-center gap-2">
                            <span className={cn('text-xs font-medium px-2 py-0.5 rounded', cat.type === 'income' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                              {cat.type === 'income' ? '↑ Thu' : '↓ Chi'}
                            </span>
                            <span className="text-sm">{labelOf(TX_CATEGORY_LABELS, cat.category)}</span>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold">{formatCurrency(cat.total)}</p>
                            <p className="text-[10px] text-[var(--text-muted)]">{cat.count} giao dịch</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Transactions Tab ── */}
            {tab === 'transactions' && (
              <div className="space-y-4">
                {/* Filters */}
                <div className="glass-card p-4">
                  <div className="flex flex-col sm:flex-row gap-3">
                    {/* Search */}
                    <div className="relative flex-1 max-w-md">
                      <svg className="absolute left-3 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                      <input
                        type="text"
                        placeholder="Tìm giao dịch..."
                        value={txSearch}
                        onChange={e => setTxSearch(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 rounded-xl text-sm"
                        style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                      />
                    </div>

                    {/* Type filter */}
                    <div className="flex gap-2">
                      {['all', 'income', 'expense'].map(t => (
                        <button
                          key={t}
                          onClick={() => setTxType(t)}
                          className="px-3 py-2 rounded-xl text-xs font-medium transition-all"
                          style={{
                            background: txType === t ? (t === 'income' ? 'rgba(16,185,129,0.15)' : t === 'expense' ? 'rgba(239,68,68,0.15)' : 'rgba(201,169,110,0.15)') : 'var(--surface-2)',
                            color: txType === t ? (t === 'income' ? '#10B981' : t === 'expense' ? '#EF4444' : 'var(--gold-400)') : 'var(--text-tertiary)',
                            border: `1px solid ${txType === t ? (t === 'income' ? 'rgba(16,185,129,0.3)' : t === 'expense' ? 'rgba(239,68,68,0.3)' : 'rgba(201,169,110,0.3)') : 'var(--border-subtle)'}`,
                          }}
                        >
                          {t === 'all' ? 'Tất cả' : <><LineIcon name="cash" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />{t === 'income' ? 'Thu' : 'Chi'}</>}
                        </button>
                      ))}
                    </div>

                    {/* Sort */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setTxSort('date'); setTxSortAsc(!txSortAsc); }}
                        className="px-3 py-2 rounded-xl text-xs font-medium transition-all"
                        style={{
                          background: txSort === 'date' ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
                          color: txSort === 'date' ? 'var(--gold-400)' : 'var(--text-tertiary)',
                          border: `1px solid ${txSort === 'date' ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                        }}
                      >
                        <LineIcon name="calendar" size={16} className="inline-block align-[-2px] mr-1.5" />Ngày {txSort === 'date' ? (txSortAsc ? '↑' : '↓') : ''}
                      </button>
                      <button
                        onClick={() => { setTxSort('amount'); setTxSortAsc(!txSortAsc); }}
                        className="px-3 py-2 rounded-xl text-xs font-medium transition-all"
                        style={{
                          background: txSort === 'amount' ? 'rgba(201,169,110,0.15)' : 'var(--surface-2)',
                          color: txSort === 'amount' ? 'var(--gold-400)' : 'var(--text-tertiary)',
                          border: `1px solid ${txSort === 'amount' ? 'rgba(201,169,110,0.3)' : 'var(--border-subtle)'}`,
                        }}
                      >
                        <LineIcon name="money" size={16} className="inline-block align-[-2px] mr-1.5" />Số tiền {txSort === 'amount' ? (txSortAsc ? '↑' : '↓') : ''}
                      </button>
                    </div>

                    {/* Create Transaction — backend chỉ cho admin/kế toán ghi sổ */}
                    {canEditAccounting && (
                      <button
                        onClick={() => openTxForm()}
                        className="px-4 py-2 rounded-xl text-sm font-semibold transition-all flex items-center gap-2"
                        style={{ background: 'linear-gradient(135deg, #10B981, #059669)', color: 'white' }}
                      >
                        + Giao dịch mới
                      </button>
                    )}

                    {/* Xuất bảng tính */}
                    <button
                      onClick={() => {
                        // So bản NFC cả hai phía — mô tả gõ kiểu «Unicode tổ hợp» vẫn khớp (21/11/2026)
                        const tuKhoa = chuanHoaTim(txSearch);
                        const filtered = transactions
                          .filter(tx => txType === 'all' || tx.type === txType)
                          .filter(tx => txCategory === 'all' || tx.category === txCategory)
                          .filter(tx => txSearch === '' || chuanHoaTim(tx.description).includes(tuKhoa) || chuanHoaTim(tx.code).includes(tuKhoa))
                          .filter(tx => {
                            if (!dateFrom && !dateTo) return true;
                            const txDate = new Date(tx.date);
                            if (dateFrom && txDate < new Date(dateFrom)) return false;
                            if (dateTo && txDate > new Date(dateTo + 'T23:59:59')) return false;
                            return true;
                          });
                        const headers = ['Mã', 'Loại', 'Danh mục', 'Mô tả', 'Số tiền', 'Ngày', 'Trạng thái'];
                        const rows = filtered.map(tx => [
                          tx.code,
                          tx.type === 'income' ? 'Thu' : 'Chi',
                          labelOf(TX_CATEGORY_LABELS, tx.category),
                          tx.description,
                          tx.amount,
                          new Date(tx.date).toLocaleDateString('vi-VN'),
                          tx.status === 'completed' ? 'Đã xử lý' : 'Chờ duyệt',
                        ]);
                        const escape = (s: string) => s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
                        const csv = [headers, ...rows].map(r => r.map(c => escape(String(c))).join(',')).join('\n');
                        const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `giao-dich-${new Date().toISOString().slice(0,10)}.csv`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      className="px-3 py-1.5 rounded-xl text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                    >
                      <LineIcon name="download" size={16} className="inline-block align-[-2px] mr-1.5" />Xuất bảng tính
                    </button>
                  </div>

                  {/* Category filter */}
                  <div className="flex gap-2 flex-wrap mt-3">
                    {['all', ...Array.from(new Set(transactions.map(t => t.category)))].map(cat => (
                      <button
                        key={cat}
                        onClick={() => setTxCategory(cat)}
                        className="px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all"
                        style={{
                          background: txCategory === cat ? 'rgba(201,169,110,0.15)' : 'var(--surface-3)',
                          color: txCategory === cat ? 'var(--gold-400)' : 'var(--text-muted)',
                          border: `1px solid ${txCategory === cat ? 'rgba(201,169,110,0.3)' : 'transparent'}`,
                        }}
                      >
                        {cat === 'all' ? 'Tất cả danh mục' : labelOf(TX_CATEGORY_LABELS, cat)}
                      </button>
                    ))}
                  </div>

                  {/* Date range filter */}
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs text-[var(--text-muted)]">Từ:</span>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={e => setDateFrom(e.target.value)}
                      className="px-2 py-1.5 rounded-lg text-xs bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
                    />
                    <span className="text-xs text-[var(--text-muted)]">đến:</span>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={e => setDateTo(e.target.value)}
                      className="px-2 py-1.5 rounded-lg text-xs bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
                    />
                    {(dateFrom || dateTo) && (
                      <button onClick={() => { setDateFrom(''); setDateTo(''); }} className="text-xs text-[var(--gold-400)] hover:underline">Xóa</button>
                    )}
                  </div>
                </div>

                {/* Filtered + sorted transactions */}
                {(() => {
                  const tuKhoa = chuanHoaTim(txSearch);
                  const filteredTx = transactions
                    .filter(tx => txType === 'all' || tx.type === txType)
                    .filter(tx => txCategory === 'all' || tx.category === txCategory)
                    .filter(tx => txSearch === '' || chuanHoaTim(tx.description).includes(tuKhoa) || chuanHoaTim(tx.code).includes(tuKhoa))
                    .filter(tx => {
                      if (!dateFrom && !dateTo) return true;
                      const txDate = new Date(tx.date);
                      if (dateFrom && txDate < new Date(dateFrom)) return false;
                      if (dateTo && txDate > new Date(dateTo + 'T23:59:59')) return false;
                      return true;
                    })
                    .sort((a, b) => {
                      const diff = txSort === 'date'
                        ? new Date(a.date).getTime() - new Date(b.date).getTime()
                        : a.amount - b.amount;
                      return txSortAsc ? diff : -diff;
                    });

                  return (
                    <div className="glass-card overflow-hidden">
                      <div className="p-3 text-xs text-[var(--text-muted)]">
                        Hiển thị {filteredTx.length} / {transactions.length} giao dịch
                      </div>
                      {/* Mobile card view */}
                      <div className="md:hidden p-3 space-y-2">
                        {filteredTx.length === 0 ? (
                          <p className="text-center p-4 text-[var(--text-muted)]">Không tìm thấy giao dịch</p>
                        ) : filteredTx.map(tx => (
                          <div key={tx.id} className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="font-mono text-[10px] text-[var(--text-muted)]">{tx.code}</span>
                              <span className={cn('text-[10px] px-1.5 py-0.5 rounded', tx.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400' : tx.status === 'pending' ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-500/15 text-gray-400')}>
                                {tx.status === 'completed' ? 'Đã xử lý' : tx.status === 'pending' ? 'Chờ duyệt' : tx.status}
                              </span>
                            </div>
                            <p className="text-xs text-[var(--text-primary)] mb-1 truncate">
                              {tx.description}
                              {tx.related_user_name && <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'rgba(201,169,110,0.12)', color: 'var(--gold-500)' }}>{tx.related_user_name}</span>}
                            </p>
                            <div className="flex items-center justify-between">
                              <span className={cn('text-xs px-2 py-0.5 rounded', tx.type === 'income' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                                {tx.type === 'income' ? '↑ Thu' : '↓ Chi'} · {labelOf(TX_CATEGORY_LABELS, tx.category)}
                              </span>
                              <span className={cn('text-sm font-semibold', tx.type === 'income' ? 'text-emerald-400' : 'text-red-400')}>
                                {tx.type === 'income' ? '+' : '-'}{tienDu(tx.amount)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between mt-1">
                              <p className="text-[10px] text-[var(--text-muted)]">{formatDate(tx.date)}</p>
                              {canEditAccounting && tx.type === 'expense' && !tx.code.startsWith('THU-') && (
                                <button onClick={() => nhanBanTx(tx)} title="Mở form tạo mới điền sẵn nội dung giao dịch này, ngày hôm nay"
                                  className="text-[10px] px-2 py-1 rounded bg-white/5 text-[var(--text-muted)] hover:bg-[var(--gold-500)]/15 hover:text-[var(--gold-500)] transition-all">
                                  Nhân bản
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                      {/* Desktop table view */}
                      <div className="hidden md:block overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Mã</th>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Loại</th>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Danh mục</th>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Mô tả</th>
                              <th className="text-right p-3 text-xs text-[var(--text-muted)]">Số tiền</th>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Ngày</th>
                              <th className="text-left p-3 text-xs text-[var(--text-muted)]">Trạng thái</th>
                              <th className="text-right p-3 text-xs text-[var(--text-muted)]">Thao tác</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredTx.length === 0 ? (
                              <tr><td colSpan={7} className="text-center p-8 text-[var(--text-muted)]">Không tìm thấy giao dịch</td></tr>
                            ) : filteredTx.map(tx => (
                              <tr key={tx.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                                <td className="p-3 font-mono text-xs">{tx.code}</td>
                                <td className="p-3">
                                  <span className={cn('text-xs px-2 py-0.5 rounded', tx.type === 'income' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                                    {tx.type === 'income' ? '↑ Thu' : '↓ Chi'}
                                  </span>
                                </td>
                                <td className="p-3 text-xs">{labelOf(TX_CATEGORY_LABELS, tx.category)}</td>
                                <td className="p-3 text-xs max-w-[200px] truncate">
                                  {tx.description}
                                  {tx.related_user_name && <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] whitespace-nowrap" style={{ background: 'rgba(201,169,110,0.12)', color: 'var(--gold-500)' }}>{tx.related_user_name}</span>}
                                </td>
                                <td className="p-3 text-right font-semibold">
                                  <span className={tx.type === 'income' ? 'text-emerald-400' : 'text-red-400'}>
                                    {tx.type === 'income' ? '+' : '-'}{tienDu(tx.amount)}
                                  </span>
                                </td>
                                <td className="p-3 text-xs text-[var(--text-muted)]">{formatDate(tx.date)}</td>
                                <td className="p-3">
                                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                                    tx.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400' :
                                    tx.status === 'pending' ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-500/15 text-gray-400'
                                  )}>
                                    {tx.status === 'completed' ? 'Đã xử lý' : tx.status === 'pending' ? 'Chờ duyệt' : tx.status}
                                  </span>
                                </td>
                                <td className="p-3 text-right">
                                  <div className="flex items-center justify-end gap-1">
                                    {canEditAccounting && (
                                      <button onClick={() => openTxForm(tx)}
                                        className="text-[10px] px-2 py-1 rounded bg-white/5 text-[var(--text-muted)] hover:bg-[var(--gold-500)]/15 hover:text-[var(--gold-500)] transition-all">
                                        Sửa
                                      </button>
                                    )}
                                    {canEditAccounting && tx.type === 'expense' && !tx.code.startsWith('THU-') && (
                                      <button onClick={() => nhanBanTx(tx)} title="Mở form tạo mới điền sẵn nội dung giao dịch này, ngày hôm nay"
                                        className="text-[10px] px-2 py-1 rounded bg-white/5 text-[var(--text-muted)] hover:bg-[var(--gold-500)]/15 hover:text-[var(--gold-500)] transition-all">
                                        Nhân bản
                                      </button>
                                    )}
                                    {user?.role === 'admin' && (
                                      <button onClick={async () => {
                                        if (!await xacNhan('Xóa giao dịch này?')) return;
                                        try {
                                          await api.deleteTransaction(tx.id);
                                          setTransactions(prev => prev.filter(t => t.id !== tx.id));
                                          toast('Đã xóa giao dịch', 'success');
                                        } catch { toast('Lỗi xóa', 'error'); }
                                      }}
                                        className="text-[10px] px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all">
                                        Xóa
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* ── Commissions Tab ── */}
            {tab === 'commissions' && (
              <div className="glass-card overflow-hidden">
                {/* Lọc theo trạng thái + duyệt cả loạt */}
                <div className="p-3 flex flex-wrap items-center gap-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  {([['all', 'Tất cả'], ['pending', 'Chờ duyệt'], ['approved', 'Đã duyệt'], ['paid', 'Đã trả'], ['cho_moc', 'Chờ mốc']] as const).map(([k, nhan]) => {
                    const so = k === 'all' ? hhTheoQuyen.length : hhTheoQuyen.filter(c => c.status === k).length;
                    if (k !== 'all' && so === 0) return null;
                    return (
                      <button key={k} type="button" onClick={() => setHhLoc(k)} aria-pressed={hhLoc === k}
                        className="px-3 min-h-[36px] rounded-full text-xs font-medium"
                        style={hhLoc === k
                          ? { background: 'var(--gold-500)', color: 'var(--surface-0)' }
                          : { background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                        {nhan} ({so})
                      </button>
                    );
                  })}
                  {canActCommission && soHhCho > 0 && (
                    <button type="button" onClick={duyetTatCaHoaHong} disabled={!!hhDang}
                      className="ml-auto px-3 min-h-[36px] rounded-full text-xs font-semibold disabled:opacity-50" style={{ background: 'rgba(56,189,248,0.12)', color: '#38BDF8' }}>
                      <LineIcon name="tick" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />
                      {hhDang === 'loat' ? 'Đang duyệt…' : `Duyệt tất cả ${soHhCho} khoản`}
                    </button>
                  )}
                </div>
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-2">
                  {visibleCommissions.length === 0 ? (
                    <p className="text-center p-4 text-[var(--text-muted)]">Chưa có hoa hồng</p>
                  ) : visibleCommissions.map(c => (
                    <div key={c.id} className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-[var(--text-primary)]">{c.user_name || '—'}</span>
                        <span className={cn('text-[10px] px-1.5 py-0.5 rounded', commissionChip(c.status).cls)}>
                          {commissionChip(c.status).label}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] text-[var(--text-muted)]">{labelOf(COMMISSION_TYPE_LABELS, c.type)}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">·</span>
                        <span className="text-[10px] text-[var(--text-muted)]">{labelOf(MILESTONE_LABELS, c.milestone)}</span>
                        {c.period && <span className="text-[10px] text-[var(--text-muted)]">· Kỳ {c.period}</span>}
                      </div>
                      {c.note && <p className="text-[10px] text-[var(--text-muted)] mb-1">{c.note}</p>}
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-[var(--text-muted)]">Cơ sở: {tienDu(c.base_amount)} · {+(c.rate * 100).toFixed(2)}%</span>
                        <span className="text-sm font-semibold text-[var(--gold-500)]">{tienDu(c.commission_amount)}</span>
                      </div>
                      {canActCommission && c.status !== 'paid' && (
                        <div className="flex gap-2 mt-2">
                          {c.status === 'pending' && (
                            <button disabled={!!hhDang} onClick={() => handleCommissionStatus(c.id, 'approved')}
                              className="flex-1 py-1.5 rounded-lg text-[11px] font-semibold min-h-[36px] disabled:opacity-50" style={{ background: 'rgba(56,189,248,0.12)', color: '#38BDF8' }}>
                              <LineIcon name="tick" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />Duyệt
                            </button>
                          )}
                          {c.status === 'approved' && (
                            <button disabled={!!hhDang} onClick={() => handleCommissionStatus(c.id, 'paid')}
                              className="flex-1 py-1.5 rounded-lg text-[11px] font-semibold min-h-[36px] disabled:opacity-50" style={{ background: 'rgba(52,211,153,0.12)', color: '#34D399' }}>
                              <LineIcon name="cash" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />Đã chi trả
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Nhân viên</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Loại</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Mốc <InfoTip text="Thời điểm khoản hoa hồng này được tính: ký hợp đồng, thu từng đợt… Khoản «Chờ mốc» là đã tính sẵn nhưng chưa tới mốc chi, chưa duyệt được." /></th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Cơ sở <InfoTip text="Số tiền dùng để tính hoa hồng (giá trị hợp đồng hoặc số tiền đợt thu). Hoa hồng = Cơ sở × Tỷ lệ." /></th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Tỷ lệ</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Hoa hồng</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">TT</th>
                        {canActCommission && <th className="text-right p-3 text-xs text-[var(--text-muted)]">Thao tác</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleCommissions.length === 0 ? (
                        <tr><td colSpan={canActCommission ? 8 : 7} className="text-center p-8 text-[var(--text-muted)]">Chưa có hoa hồng</td></tr>
                      ) : visibleCommissions.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.user_name || '—'}</td>
                          <td className="p-3 text-xs">
                            {labelOf(COMMISSION_TYPE_LABELS, c.type)}
                            {c.note && <div className="text-[10px] text-[var(--text-muted)] max-w-[260px]">{c.note}</div>}
                          </td>
                          <td className="p-3 text-xs">
                            {labelOf(MILESTONE_LABELS, c.milestone)}
                            {c.period && <div className="text-[10px] text-[var(--text-muted)]">Kỳ {c.period}</div>}
                          </td>
                          <td className="p-3 text-right text-xs">{tienDu(c.base_amount)}</td>
                          <td className="p-3 text-right text-xs">{+(c.rate * 100).toFixed(2)}%</td>
                          <td className="p-3 text-right font-semibold text-[var(--gold-500)]">{tienDu(c.commission_amount)}</td>
                          <td className="p-3">
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap', commissionChip(c.status).cls)}>
                              {commissionChip(c.status).label}
                            </span>
                          </td>
                          {canActCommission && (
                            <td className="p-3 text-right">
                              {c.status === 'pending' && (
                                <button disabled={!!hhDang} onClick={() => handleCommissionStatus(c.id, 'approved')}
                                  className="px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold whitespace-nowrap disabled:opacity-50" style={{ background: 'rgba(56,189,248,0.12)', color: '#38BDF8' }}>
                                  <LineIcon name="tick" size={13} color="currentColor" className="inline-block align-[-2px] mr-1" />Duyệt
                                </button>
                              )}
                              {c.status === 'approved' && (
                                <button disabled={!!hhDang} onClick={() => handleCommissionStatus(c.id, 'paid')}
                                  className="px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold whitespace-nowrap disabled:opacity-50" style={{ background: 'rgba(52,211,153,0.12)', color: '#34D399' }}>
                                  <LineIcon name="cash" size={14} color="currentColor" className="inline-block align-[-2px] mr-1" />Đã chi trả
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── Payroll Tab ── */}
            {tab === 'payroll' && (
              <div className="glass-card overflow-hidden">
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-2">
                  {payroll.length === 0 ? (
                    <p className="text-center p-4 text-[var(--text-muted)]">Chưa có bảng lương</p>
                  ) : payroll.map(p => (
                    <div key={p.id} className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-[var(--text-primary)]">{p.user_name || '—'}</span>
                        <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                          (p.status === 'paid' || p.status === 'approved') ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                        )}>
                          {(p.status === 'paid' || p.status === 'approved') ? 'Đã trả' : 'Chờ'}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-muted)] mb-1.5">{p.period}</p>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Lương CB</span><span className="text-[var(--text-secondary)]">{tienDu(p.base_salary)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Hoa hồng</span><span className="text-[var(--gold-500)]">{tienDu(p.commission_total)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Thưởng</span><span className="text-emerald-400">{tienDu(p.bonus)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Khấu trừ</span><span className="text-red-400">{tienDu(p.deductions)}</span></div>
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                        <span className="text-[10px] text-[var(--text-muted)]">Thực lĩnh</span>
                        <span className="text-sm font-semibold text-[var(--text-primary)]">{tienDu(p.net_salary)}</span>
                      </div>
                    </div>
                  ))}
                </div>
                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Nhân viên</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Kỳ lương</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Lương cơ bản</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Hoa hồng</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Thưởng</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Khấu trừ</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Thực lĩnh</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">TT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payroll.length === 0 ? (
                        <tr><td colSpan={8} className="text-center p-8 text-[var(--text-muted)]">Chưa có bảng lương</td></tr>
                      ) : payroll.map(p => (
                        <tr key={p.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{p.user_name || '—'}</td>
                          <td className="p-3 text-xs">{p.period}</td>
                          <td className="p-3 text-right text-xs">{tienDu(p.base_salary)}</td>
                          <td className="p-3 text-right text-xs text-[var(--gold-500)]">{tienDu(p.commission_total)}</td>
                          <td className="p-3 text-right text-xs text-emerald-400">{tienDu(p.bonus)}</td>
                          <td className="p-3 text-right text-xs text-red-400">{tienDu(p.deductions)}</td>
                          <td className="p-3 text-right font-semibold">{tienDu(p.net_salary)}</td>
                          <td className="p-3">
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                              (p.status === 'paid' || p.status === 'approved') ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                            )}>
                              {(p.status === 'paid' || p.status === 'approved') ? 'Đã trả' : 'Chờ'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Create Transaction Modal ── */}
        {showTxForm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative glass-card p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in" onClick={e => e.stopPropagation()}>
              <h3 className="text-lg font-bold mb-4 gold-gradient">{editingTx ? 'Sửa giao dịch' : 'Tạo giao dịch mới'}</h3>

              {/* Type toggle */}
              <div className="flex gap-2 mb-4">
                {[
                  { key: 'income', label: 'Thu nhập', color: '#10B981' },
                  { key: 'expense', label: 'Chi phí', color: '#EF4444' },
                ].map(t => (
                  <button
                    key={t.key}
                    onClick={() => setTxForm(f => ({ ...f, type: t.key }))}
                    className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all"
                    style={{
                      background: txForm.type === t.key ? `${t.color}20` : 'var(--surface-2)',
                      border: `1px solid ${txForm.type === t.key ? t.color : 'var(--border-subtle)'}`,
                      color: txForm.type === t.key ? t.color : 'var(--text-muted)',
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Category */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Danh mục</label>
                <select
                  value={txForm.category}
                  onChange={e => setTxForm(f => ({ ...f, category: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                >
                  <option value="design_contract">HĐ Thiết kế</option>
                  <option value="construction_contract">HĐ Thi công</option>
                  <option value="material">Vật tư</option>
                  <option value="labor">Nhân công</option>
                  <option value="salary">Lương</option>
                  <option value="commission">Hoa hồng</option>
                  <option value="rent">Tiền mặt bằng</option>
                  <option value="utilities">Điện nước</option>
                  <option value="other">Khác</option>
                </select>
              </div>

              {/* Description */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Mô tả</label>
                <input
                  type="text"
                  value={txForm.description}
                  onChange={e => setTxForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Nhập mô tả giao dịch..."
                  className="w-full px-3 py-2.5 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
              </div>

              {/* Amount */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Số tiền (VND)</label>
                <input
                  type="text"
                  value={txAmountDisplay}
                  onChange={e => handleTxAmountChange(e.target.value)}
                  placeholder="0"
                  className="w-full px-3 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: txForm.type === 'income' ? '#10B981' : '#EF4444' }}
                />
              </div>

              {/* Date */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Ngày</label>
                <input
                  type="date"
                  value={txForm.date}
                  onChange={e => setTxForm(f => ({ ...f, date: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
              </div>

              {/* Nhân viên liên quan — hiện khi danh mục Lương/Hoa hồng */}
              {(txForm.category === 'salary' || txForm.category === 'commission') && (
                <div className="mb-3">
                  <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Liên kết nhân viên (tùy chọn)</label>
                  <select
                    value={txForm.user_id}
                    onChange={e => setTxForm(f => ({ ...f, user_id: e.target.value }))}
                    className="w-full px-3 py-2.5 rounded-xl text-sm"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                  >
                    <option value="">Không gắn — ghi tổng (cả kỳ/nhiều người)</option>
                    {staffList.map(u => (
                      <option key={u.id} value={u.id}>{u.full_name} — {labelOf(ROLE_LABELS, u.role)}</option>
                    ))}
                  </select>
                  <p className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>
                    Lương chi tiết TỪNG NHÂN VIÊN (công, OT, BHXH, thuế) quản lý ở <a href="/attendance" className="underline text-[var(--gold-500)]">Chấm công → Chốt sổ</a> — hệ thống tự sinh bảng lương. Ô này dùng khi ghi sổ khoản chi lẻ cho một người cụ thể.
                  </p>
                </div>
              )}

              {/* Project (optional) */}
              <div className="mb-4">
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Liên kết dự án (tùy chọn)</label>
                <select
                  value={txForm.project_id}
                  onChange={e => setTxForm(f => ({ ...f, project_id: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                >
                  <option value="">Không liên kết</option>
                  {activeProjects.map(p => (
                    <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                  ))}
                </select>
              </div>

              {/* Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setShowTxForm(false)}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}
                >
                  Hủy
                </button>
                <button
                  onClick={handleCreateTransaction}
                  disabled={savingTx || !txForm.description.trim() || !txForm.amount}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #10B981, #059669)', color: 'white' }}
                >
                  {savingTx ? 'Đang lưu...' : editingTx ? 'Lưu thay đổi' : 'Tạo giao dịch'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
