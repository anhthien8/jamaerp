'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Transaction, AccountingSummary, Commission, PayrollEntry, extractItems } from '@/lib/api';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { getPermissions, UserRole } from '@/lib/roles';

type Tab = 'overview' | 'transactions' | 'commissions' | 'payroll';

function AccessDenied() {
  const router = useRouter();
  return (
    <Sidebar>
      <div className="p-6 flex items-center justify-center min-h-[60vh] animate-in">
        <div className="glass-card p-12 text-center max-w-md">
          <span className="text-5xl block mb-4">🔒</span>
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">Không có quyền truy cập</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Bạn không có quyền truy cập trang này.
          </p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2.5 rounded-xl text-sm font-medium transition-all"
            style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))', color: '#fff' }}
          >
            Quay về Dashboard
          </button>
        </div>
      </div>
    </Sidebar>
  );
}

export default function AccountingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('overview');
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
  const [periodFilter, setPeriodFilter] = useState('all');

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
      setError('Không thể tải dữ liệu kế toán. Vui lòng thử lại.');
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchData);
  }, [user, fetchData]);

  if (loading || !user) return null;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <span className="text-4xl block mb-4">⚠️</span>
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); fetchData(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }


  const perms = getPermissions(user.role as UserRole);
  if (!perms.canViewAccounting) return <AccessDenied />;

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
                    <p className="text-xs text-[var(--text-muted)] mb-1">💵 Tổng thu</p>
                    <p className="text-xl font-bold text-emerald-400">{formatCurrency(filteredIncome)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-red-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1">💸 Tổng chi</p>
                    <p className="text-xl font-bold text-red-400">{formatCurrency(filteredExpense)}</p>
                  </div>
                  <div className="glass-card p-5 border-l-2 border-l-blue-500">
                    <p className="text-xs text-[var(--text-muted)] mb-1">📈 Lợi nhuận</p>
                    <p className={cn('text-xl font-bold', (filteredIncome - filteredExpense) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {formatCurrency(filteredIncome - filteredExpense)}
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
                        {summary.total_income > 0 ? ((summary.total_expense / summary.total_income) * 100).toFixed(1) : '0'}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-[var(--text-secondary)]">Số giao dịch tháng này</span>
                      <span className="text-sm font-semibold text-blue-400">{transactions.length}</span>
                    </div>
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

                    {/* Export CSV */}
                    <button
                      onClick={() => {
                        const filtered = transactions
                          .filter(tx => txType === 'all' || tx.type === txType)
                          .filter(tx => txCategory === 'all' || tx.category === txCategory)
                          .filter(tx => txSearch === '' || tx.description.toLowerCase().includes(txSearch.toLowerCase()) || tx.code.toLowerCase().includes(txSearch.toLowerCase()))
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
                          tx.category,
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
                      📥 Export CSV
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
                        {cat === 'all' ? 'Tất cả danh mục' : cat}
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
                  const filteredTx = transactions
                    .filter(tx => txType === 'all' || tx.type === txType)
                    .filter(tx => txCategory === 'all' || tx.category === txCategory)
                    .filter(tx => txSearch === '' || tx.description.toLowerCase().includes(txSearch.toLowerCase()) || tx.code.toLowerCase().includes(txSearch.toLowerCase()))
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
                            <p className="text-xs text-[var(--text-primary)] mb-1 truncate">{tx.description}</p>
                            <div className="flex items-center justify-between">
                              <span className={cn('text-xs px-2 py-0.5 rounded', tx.type === 'income' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                                {tx.type === 'income' ? '↑ Thu' : '↓ Chi'} · {tx.category}
                              </span>
                              <span className={cn('text-sm font-semibold', tx.type === 'income' ? 'text-emerald-400' : 'text-red-400')}>
                                {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount)}
                              </span>
                            </div>
                            <p className="text-[10px] text-[var(--text-muted)] mt-1">{formatDate(tx.date)}</p>
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
                {/* Mobile card view */}
                <div className="md:hidden p-3 space-y-2">
                  {visibleCommissions.length === 0 ? (
                    <p className="text-center p-4 text-[var(--text-muted)]">Chưa có hoa hồng</p>
                  ) : visibleCommissions.map(c => (
                    <div key={c.id} className="p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-[var(--text-primary)]">{c.user_name || '—'}</span>
                        <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                          (c.status === 'paid' || c.status === 'approved') ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                        )}>
                          {(c.status === 'paid' || c.status === 'approved') ? 'Đã trả' : 'Chờ'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] text-[var(--text-muted)]">{c.type}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">·</span>
                        <span className="text-[10px] text-[var(--text-muted)]">{c.milestone}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-[var(--text-muted)]">Cơ sở: {formatCurrency(c.base_amount)} · {(c.rate * 100).toFixed(1)}%</span>
                        <span className="text-sm font-semibold text-[#C9A96E]">{formatCurrency(c.commission_amount)}</span>
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
                              (c.status === 'paid' || c.status === 'approved') ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                            )}>
                              {(c.status === 'paid' || c.status === 'approved') ? 'Đã trả' : 'Chờ'}
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
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Lương CB</span><span className="text-[var(--text-secondary)]">{formatCurrency(p.base_salary)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Hoa hồng</span><span className="text-[#C9A96E]">{formatCurrency(p.commission_total)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Thưởng</span><span className="text-emerald-400">{formatCurrency(p.bonus)}</span></div>
                        <div className="flex justify-between"><span className="text-[var(--text-muted)]">Khấu trừ</span><span className="text-red-400">{formatCurrency(p.deductions)}</span></div>
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                        <span className="text-[10px] text-[var(--text-muted)]">Thực lĩnh</span>
                        <span className="text-sm font-semibold text-[var(--text-primary)]">{formatCurrency(p.net_salary)}</span>
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
                          <td className="p-3 text-right text-xs">{formatCurrency(p.base_salary)}</td>
                          <td className="p-3 text-right text-xs text-[#C9A96E]">{formatCurrency(p.commission_total)}</td>
                          <td className="p-3 text-right text-xs text-emerald-400">{formatCurrency(p.bonus)}</td>
                          <td className="p-3 text-right text-xs text-red-400">{formatCurrency(p.deductions)}</td>
                          <td className="p-3 text-right font-semibold">{formatCurrency(p.net_salary)}</td>
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
      </div>
    </Sidebar>
  );
}
