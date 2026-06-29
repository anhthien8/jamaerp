'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Transaction, AccountingSummary, Commission, PayrollEntry, extractItems } from '@/lib/api';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';

type Tab = 'overview' | 'transactions' | 'commissions' | 'payroll';

export default function AccountingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('overview');
  const [summary, setSummary] = useState<AccountingSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [payroll, setPayroll] = useState<PayrollEntry[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // Filters
  const [txSearch, setTxSearch] = useState('');
  const [txType, setTxType] = useState('all');
  const [txCategory, setTxCategory] = useState('all');
  const [txSort, setTxSort] = useState<'date' | 'amount'>('date');
  const [txSortAsc, setTxSortAsc] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      const [s, tResult, cResult, pResult] = await Promise.all([
        api.getAccountingSummary(),
        api.getTransactions(),
        api.getCommissions(),
        api.getPayroll(),
      ]);
      setSummary(s);
      setTransactions(extractItems(tResult));
      setCommissions(extractItems(cResult));
      setPayroll(extractItems(pResult));
    } catch (e) {
      console.warn('Accounting API error:', e);
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchData);
  }, [user, fetchData]);

  if (loading || !user) return null;

  const perms = getPermissions(user.role as UserRole);
  const ALL_TABS: { key: Tab; label: string; icon: string }[] = [
    { key: 'overview', label: 'Tổng quan', icon: '📊' },
    { key: 'transactions', label: 'Giao dịch', icon: '💳' },
    { key: 'commissions', label: 'Hoa hồng', icon: '💰' },
    { key: 'payroll', label: 'Bảng lương', icon: '📋' },
  ];

  // Filter tabs based on role permissions
  const TABS = ALL_TABS.filter(t => {
    if (t.key === 'payroll' && !perms.canViewPayroll) return false;
    return true;
  });

  // Filter commissions based on role
  const visibleCommissions = commissions.filter(c => {
    if (user.role === 'data_entry') return c.user_id === user.id;
    if (user.role === 'leader') return true; // team sees all for now
    return true; // admin/accountant see all
  });

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">💰 Kế toán & Tài chính</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">Quản lý thu chi, hoa hồng, lương</p>
          </div>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--surface-2)' }}>
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex-1 py-2 rounded-lg text-xs font-medium transition-all',
                tab === t.key
                  ? 'bg-[#C9A96E]/20 text-[#C9A96E] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              )}
            >
              {t.icon} {t.label}
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
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="glass-card p-5 border-l-2 border-l-emerald-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1">💵 Tổng thu</p>
                    <p className="text-xl font-bold text-emerald-400">{formatCurrency(summary.total_income)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-red-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1">💸 Tổng chi</p>
                    <p className="text-xl font-bold text-red-400">{formatCurrency(summary.total_expense)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-blue-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1">📈 Lợi nhuận</p>
                    <p className={cn('text-xl font-bold', summary.net >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {formatCurrency(summary.net)}
                    </p>
                  </div>
                </div>

                {/* By Category */}
                <div className="glass-card p-5">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Theo danh mục</h3>
                  {summary.by_category.length === 0 ? (
                    <p className="text-sm text-center text-[var(--text-muted)] py-4">Chưa có dữ liệu</p>
                  ) : (
                    <div className="space-y-2">
                      {summary.by_category.map((cat, i) => (
                        <div key={i} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5">
                          <div className="flex items-center gap-2">
                            <span className={cn('text-xs font-medium px-2 py-0.5 rounded', cat.type === 'income' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                              {cat.type === 'income' ? '↑ Thu' : '↓ Chi'}
                            </span>
                            <span className="text-sm">{cat.category}</span>
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
                          {t === 'all' ? 'Tất cả' : t === 'income' ? '💵 Thu' : '💸 Chi'}
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
                        📅 Ngày {txSort === 'date' ? (txSortAsc ? '↑' : '↓') : ''}
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
                        💰 Số tiền {txSort === 'amount' ? (txSortAsc ? '↑' : '↓') : ''}
                      </button>
                    </div>
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
                        {cat === 'all' ? 'Tất cả danh mục' : cat}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Filtered + sorted transactions */}
                {(() => {
                  const filteredTx = transactions
                    .filter(tx => txType === 'all' || tx.type === txType)
                    .filter(tx => txCategory === 'all' || tx.category === txCategory)
                    .filter(tx => txSearch === '' || tx.description.toLowerCase().includes(txSearch.toLowerCase()) || tx.code.toLowerCase().includes(txSearch.toLowerCase()))
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
                      <div className="overflow-x-auto">
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
                                <td className="p-3 text-xs">{tx.category}</td>
                                <td className="p-3 text-xs max-w-[200px] truncate">{tx.description}</td>
                                <td className="p-3 text-right font-semibold">
                                  <span className={tx.type === 'income' ? 'text-emerald-400' : 'text-red-400'}>
                                    {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount)}
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
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Nhân viên</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Loại</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">Mốc</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Cơ sở</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Tỷ lệ</th>
                        <th className="text-right p-3 text-xs text-[var(--text-muted)]">Hoa hồng</th>
                        <th className="text-left p-3 text-xs text-[var(--text-muted)]">TT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleCommissions.length === 0 ? (
                        <tr><td colSpan={7} className="text-center p-8 text-[var(--text-muted)]">Chưa có hoa hồng</td></tr>
                      ) : visibleCommissions.map(c => (
                        <tr key={c.id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: 'var(--border-subtle)' }}>
                          <td className="p-3 font-medium">{c.user_name || '—'}</td>
                          <td className="p-3 text-xs">{c.type}</td>
                          <td className="p-3 text-xs">{c.milestone}</td>
                          <td className="p-3 text-right text-xs">{formatCurrency(c.base_amount)}</td>
                          <td className="p-3 text-right text-xs">{(c.rate * 100).toFixed(1)}%</td>
                          <td className="p-3 text-right font-semibold text-[#C9A96E]">{formatCurrency(c.commission_amount)}</td>
                          <td className="p-3">
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                              c.status === 'paid' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                            )}>
                              {c.status === 'paid' ? 'Đã trả' : 'Chờ'}
                            </span>
                          </td>
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
                <div className="overflow-x-auto">
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
                          <td className="p-3 text-right text-xs">{formatCurrency(p.base_salary)}</td>
                          <td className="p-3 text-right text-xs text-[#C9A96E]">{formatCurrency(p.commission_total)}</td>
                          <td className="p-3 text-right text-xs text-emerald-400">{formatCurrency(p.bonus)}</td>
                          <td className="p-3 text-right text-xs text-red-400">{formatCurrency(p.deductions)}</td>
                          <td className="p-3 text-right font-semibold">{formatCurrency(p.net_salary)}</td>
                          <td className="p-3">
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                              p.status === 'paid' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                            )}>
                              {p.status === 'paid' ? 'Đã trả' : 'Chờ'}
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
      </div>
    </Sidebar>
  );
}
