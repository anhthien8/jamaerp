'use client';

import { useEffect, useState, useCallback, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import {
  STAGE_CONFIG, formatCurrency, timeAgo, cn,
  formatPricePerSqm, formatDealValue,
  PROPERTY_CLASS_LABELS, PLAN_TYPE_LABELS,
  REGION_OPTIONS, TAG_COLORS,
} from '@/lib/utils';
import { useToast } from '@/components/ui/Toast';
import CreateLeadModal from '@/components/ui/CreateLeadModal';
import { api, Lead, Activity, extractItems } from '@/lib/api';
import { getPermissions, UserRole } from '@/lib/roles';

const PROPERTY_LABELS: Record<string, string> = {
  townhouse: 'Nhà phố', apartment: 'Căn hộ', villa: 'Biệt thự',
  office: 'Văn phòng', shophouse: 'Shophouse', other: 'Khác',
};
const SOURCE_LABELS: Record<string, string> = {
  facebook: 'Facebook', zalo: 'Zalo', website: 'Website',
  referral: 'Giới thiệu', tiktok: 'TikTok', other: 'Khác',
};
const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  urgent: { label: 'Khẩn cấp', color: '#EF4444' },
  high: { label: 'Cao', color: '#F59E0B' },
  medium: { label: 'Trung bình', color: '#3B82F6' },
  low: { label: 'Thấp', color: '#6B7280' },
};
const ACTIVITY_ICONS: Record<string, string> = {
  note: '📝', call: '📞', meeting: '🤝', email: '📧', sms: '💬',
  stage_change: '🔄', assignment: '👤', system: '🤖',
};
const STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design'];
const ALL_STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design', 'lost', 'dormant'];
const OVERDUE_DAYS = 3;

function getLeadTimestamp(lead: Lead) {
  return lead.last_contacted_at || lead.updated_at || lead.created_at;
}

function isOverdueLead(lead: Lead) {
  const timestamp = getLeadTimestamp(lead);
  if (!timestamp || ['signed_design', 'lost'].includes(lead.stage)) return false;
  const ageMs = Date.now() - new Date(timestamp).getTime();
  return ageMs > OVERDUE_DAYS * 24 * 60 * 60 * 1000;
}

function TagBadge({ tag }: { tag: string }) {
  const color = TAG_COLORS[tag] || '#6B7280';
  return (
    <span
      className="inline-flex items-center text-[9px] px-1.5 py-0.5 rounded-full font-medium"
      style={{ background: `${color}20`, color, border: `1px solid ${color}30` }}
    >
      {tag}
    </span>
  );
}

function LeadsContent() {

  const { user, loading } = useAuth();
  const router = useRouter();
  const perms = getPermissions((user?.role || 'data_entry') as UserRole);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loadingLeads, setLoadingLeads] = useState(true);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [filterRegion, setFilterRegion] = useState<string>('all');
  const [filterPropertyClass, setFilterPropertyClass] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'newest' | 'budget' | 'ai_score' | 'deal_value'>('newest');
  const [newNote, setNewNote] = useState('');
  const [newNoteLink, setNewNoteLink] = useState('');
  const [viewMode, setViewMode] = useState<'kanban' | 'calendar'>('kanban');
  const [calendarDate, setCalendarDate] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const searchParams = useSearchParams();
  const urlStage = searchParams.get('stage');
  const urlFilter = searchParams.get('filter');
  const activeStage = urlStage && ALL_STAGES.includes(urlStage) ? urlStage : null;
  const activeQuickFilter = urlFilter === 'overdue' ? 'overdue' : null;
  const { toast } = useToast();

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !perms.canViewLeads) router.push('/');
  }, [user, loading, router, perms.canViewLeads]);

  const fetchLeads = useCallback(async () => {
    setLoadingLeads(true);
    try {
      const params: Record<string, string> = {};
      if (filterSource !== 'all') params.source = filterSource;
      if (filterPriority !== 'all') params.priority = filterPriority;
      const allLeads = extractItems(await api.getLeads(params));
      // Normalize tags: backend may return JSON string instead of array
      for (const lead of allLeads) {
        if (typeof lead.tags === 'string') {
          try { lead.tags = JSON.parse(lead.tags); } catch { lead.tags = []; }
        }
      }
      // Apply role-based scope filtering
      let filtered = allLeads;
      if (perms.leadsScope === 'own') {
        filtered = allLeads.filter(l => l.assigned_to === user?.id);
      } else if (perms.leadsScope === 'team') {
        filtered = allLeads.filter(l => l.team_id === user?.team_id || !l.assigned_to);
      }
      // Apply client-side filters for region and property_class
      if (filterRegion !== 'all') {
        filtered = filtered.filter(l => l.region === filterRegion);
      }
      if (filterPropertyClass !== 'all') {
        filtered = filtered.filter(l => l.property_class === filterPropertyClass);
      }
      setLeads(filtered);
    } catch (e) {
      console.warn('API error, using empty list:', e);
      setLeads([]);
    } finally {
      setLoadingLeads(false);
    }
  }, [filterSource, filterPriority, filterRegion, filterPropertyClass, perms.leadsScope, user?.id, user?.team_id]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchLeads);
  }, [user, fetchLeads]);

  const openLeadDetail = async (lead: Lead) => {
    setSelectedLead(lead);
    setActivities([]);
    setLoadingActivities(true);
    try {
      const acts = await api.getActivities(lead.id);
      setActivities(acts);
    } catch {
      setActivities([]);
    } finally {
      setLoadingActivities(false);
    }
  };

  const handleAddNote = async () => {
    if (!selectedLead || !newNote.trim()) return;
    try {
      const content = newNoteLink.trim()
        ? `${newNote.trim()}\n📎 ${newNoteLink.trim()}`
        : newNote.trim();
      await api.createActivity(selectedLead.id, { type: 'note', content });
      const acts = await api.getActivities(selectedLead.id);
      setActivities(acts);
      setNewNote('');
      setNewNoteLink('');
      toast('Đã thêm ghi chú', 'success');
    } catch {
      toast('Lỗi khi thêm ghi chú', 'error');
    }
  };

  const handleStageChange = async (lead: Lead, newStage: string) => {
    try {
      await api.changeStage(lead.id, newStage);
      toast(`Chuyển ${lead.name} sang ${STAGE_CONFIG[newStage]?.label || newStage}`, 'success');
      fetchLeads();
      setSelectedLead(null);
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    }
  };

  if (loading || !user) return null;

  // Sort leads
  const sorted = [...leads];
  if (sortBy === 'budget') sorted.sort((a, b) => (b.estimated_budget || 0) - (a.estimated_budget || 0));
  else if (sortBy === 'ai_score') sorted.sort((a, b) => (b.ai_score || 0) - (a.ai_score || 0));
  else if (sortBy === 'deal_value') sorted.sort((a, b) => (b.deal_value || 0) - (a.deal_value || 0));
  else sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const filteredByUrl = sorted.filter(lead => {
    if (activeStage && lead.stage !== activeStage) return false;
    if (activeQuickFilter === 'overdue' && !isOverdueLead(lead)) return false;
    return true;
  });

  const visibleStages = activeStage && !STAGES.includes(activeStage) ? [activeStage] : STAGES;

  // Group by stage for kanban
  const kanban = visibleStages.map(stage => ({
    stage,
    leads: filteredByUrl.filter(l => l.stage === stage),
  }));

  const hasUrlFilters = Boolean(activeStage || activeQuickFilter);
  const hasFilters = filterSource !== 'all' || filterPriority !== 'all' || filterRegion !== 'all' || filterPropertyClass !== 'all' || hasUrlFilters;
  const activeFilterLabels = [
    activeStage ? `Giai đoạn: ${STAGE_CONFIG[activeStage]?.label || activeStage}` : null,
    activeQuickFilter === 'overdue' ? `Quá hạn CSKH > ${OVERDUE_DAYS} ngày` : null,
    filterRegion !== 'all' ? `Khu vực: ${filterRegion}` : null,
    filterPropertyClass !== 'all' ? PROPERTY_CLASS_LABELS[filterPropertyClass]?.label : null,
  ].filter(Boolean);

  const clearUrlFilters = () => {
    router.push('/leads');
  };

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">🔄 Pipeline CRM</h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Click vào card để xem chi tiết · {filteredByUrl.length}/{leads.length} leads
              </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
              <button
                onClick={() => setViewMode('kanban')}
                className="px-3 py-1.5 text-xs font-medium transition-all"
                style={{
                  background: viewMode === 'kanban' ? 'rgba(201,169,110,0.2)' : 'var(--surface-2)',
                  color: viewMode === 'kanban' ? '#C9A96E' : 'var(--text-muted)',
                  borderRight: '1px solid var(--border-subtle)',
                }}
              >📋 Kanban</button>
              <button
                onClick={() => setViewMode('calendar')}
                className="px-3 py-1.5 text-xs font-medium transition-all"
                style={{
                  background: viewMode === 'calendar' ? 'rgba(201,169,110,0.2)' : 'var(--surface-2)',
                  color: viewMode === 'calendar' ? '#C9A96E' : 'var(--text-muted)',
                }}
              >📅 Lịch</button>
            </div>
            <button
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#C9A96E] to-[#B8935A] text-white text-sm font-medium hover:from-[#D4B97E] hover:to-[#C9A96E] transition-all active:scale-95 whitespace-nowrap"
              onClick={() => setCreateOpen(true)}
            >
              + Thêm Lead
            </button>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2 mb-4 p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
          <span className="text-xs text-[var(--text-muted)] mr-1">Lọc:</span>
          <select value={filterSource} onChange={e => setFilterSource(e.target.value)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="all">Tất cả nguồn</option>
            <option value="zalo">Zalo</option>
            <option value="facebook">Facebook</option>
            <option value="tiktok">TikTok</option>
            <option value="website">Website</option>
            <option value="referral">Giới thiệu</option>
          </select>
          <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="all">Tất cả ưu tiên</option>
            <option value="urgent">🔴 Khẩn cấp</option>
            <option value="high">🟡 Cao</option>
            <option value="medium">🔵 Trung bình</option>
            <option value="low">⚪ Thấp</option>
          </select>
          <select value={filterRegion} onChange={e => setFilterRegion(e.target.value)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="all">Tất cả khu vực</option>
            {REGION_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={filterPropertyClass} onChange={e => setFilterPropertyClass(e.target.value)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="all">Tất cả phân loại</option>
            <option value="luxury">Hạng sang</option>
            <option value="mid_range">Trung bình</option>
            <option value="budget">Bình dân</option>
          </select>
          <span className="text-xs text-[var(--text-muted)] ml-2 mr-1">Sắp xếp:</span>
          <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="newest">Mới nhất</option>
            <option value="budget">Budget cao → thấp</option>
            <option value="deal_value">Deal value cao → thấp</option>
            <option value="ai_score">AI Score cao → thấp</option>
          </select>
          {activeFilterLabels.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 ml-2">
              {activeFilterLabels.map(label => (
                <span key={label} className="text-[10px] px-2 py-1 rounded-full bg-[#C9A96E]/15 text-[#C9A96E] border border-[#C9A96E]/25">
                  {label}
                </span>
              ))}
            </div>
          )}
          {hasFilters && (
            <button onClick={() => { setFilterSource('all'); setFilterPriority('all'); setFilterRegion('all'); setFilterPropertyClass('all'); if (hasUrlFilters) clearUrlFilters(); }} className="text-[10px] px-2 py-1 rounded-lg ml-auto" style={{ background: 'rgba(248,113,113,0.1)', color: '#EF4444' }}>
              ✕ Xóa bộ lọc
            </button>
          )}
        </div>

        {/* Loading */}
        {loadingLeads ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            Đang tải...
          </div>
        ) : filteredByUrl.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)]">
            <p className="text-lg mb-2">📭 Không có lead phù hợp</p>
            <p className="text-sm">Hãy xóa bộ lọc hoặc kiểm tra lại dữ liệu lead</p>
          </div>
        ) : viewMode === 'calendar' ? (
          /* Calendar View */
          (() => {
            const calYear = calendarDate.getFullYear();
            const calMonth = calendarDate.getMonth();
            const monthNames = ['Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8', 'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'];
            const dayNames = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
            const firstDay = new Date(calYear, calMonth, 1);
            const lastDay = new Date(calYear, calMonth + 1, 0);
            // Monday=0 based offset
            let startOffset = firstDay.getDay() - 1;
            if (startOffset < 0) startOffset = 6;
            const totalDays = lastDay.getDate();
            const cells: (number | null)[] = [];
            for (let i = 0; i < startOffset; i++) cells.push(null);
            for (let d = 1; d <= totalDays; d++) cells.push(d);
            while (cells.length % 7 !== 0) cells.push(null);
            // Group leads by date string (YYYY-MM-DD)
            const leadsByDate: Record<string, typeof filteredByUrl> = {};
            filteredByUrl.forEach(lead => {
              const dateStr = lead.last_contacted_at || lead.created_at;
              if (dateStr) {
                const key = dateStr.substring(0, 10);
                if (!leadsByDate[key]) leadsByDate[key] = [];
                leadsByDate[key].push(lead);
              }
            });
            const today = new Date().toISOString().substring(0, 10);
            return (
              <div>
                {/* Calendar header */}
                <div className="flex items-center justify-between mb-4 px-1">
                  <button onClick={() => setCalendarDate(new Date(calYear, calMonth - 1, 1))} className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all hover:opacity-80" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>◀</button>
                  <h2 className="text-lg font-bold text-white">{monthNames[calMonth]} {calYear}</h2>
                  <button onClick={() => setCalendarDate(new Date(calYear, calMonth + 1, 1))} className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all hover:opacity-80" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>▶</button>
                </div>
                {/* Day name headers */}
                <div className="grid grid-cols-7 gap-1 mb-1">
                  {dayNames.map(d => (
                    <div key={d} className="text-center text-[10px] font-semibold py-1" style={{ color: 'var(--text-muted)' }}>{d}</div>
                  ))}
                </div>
                {/* Calendar grid */}
                <div className="grid grid-cols-7 gap-1">
                  {cells.map((day, idx) => {
                    if (day === null) return <div key={`empty-${idx}`} className="rounded-lg min-h-[70px] sm:min-h-[90px]" style={{ background: 'var(--surface-1)', opacity: 0.3 }} />;
                    const dateKey = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                    const dayLeads = leadsByDate[dateKey] || [];
                    const isToday = dateKey === today;
                    return (
                      <div key={`day-${day}`} className="rounded-lg p-1.5 min-h-[70px] sm:min-h-[90px] transition-all" style={{ background: isToday ? 'rgba(201,169,110,0.12)' : 'var(--surface-2)', border: isToday ? '1px solid rgba(201,169,110,0.4)' : '1px solid transparent' }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-xs font-medium ${isToday ? 'text-[#C9A96E] font-bold' : ''}`} style={{ color: isToday ? '#C9A96E' : 'var(--text-secondary)' }}>{day}</span>
                          {dayLeads.length > 0 && (
                            <span className="text-[9px] px-1 py-0.5 rounded-full font-semibold" style={{ background: 'rgba(201,169,110,0.2)', color: '#C9A96E' }}>{dayLeads.length}</span>
                          )}
                        </div>
                        <div className="space-y-0.5">
                          {dayLeads.slice(0, 3).map(lead => (
                            <div key={lead.id} onClick={() => openLeadDetail(lead)} className="text-[9px] sm:text-[10px] px-1 py-0.5 rounded cursor-pointer hover:opacity-80 transition-all truncate" style={{ background: `${PRIORITY_LABELS[lead.priority]?.color || '#6B7280'}20`, color: PRIORITY_LABELS[lead.priority]?.color || '#fff' }} title={`${lead.name} — ${formatDealValue(lead.deal_value)}`}>
                              <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 flex-shrink-0" style={{ background: PRIORITY_LABELS[lead.priority]?.color || '#6B7280', verticalAlign: 'middle' }} />
                              {lead.name.split(' ')[0]}
                              {lead.deal_value ? <span className="hidden sm:inline"> · {formatDealValue(lead.deal_value)}</span> : null}
                            </div>
                          ))}
                          {dayLeads.length > 3 && (
                            <div className="text-[9px] text-center" style={{ color: 'var(--text-muted)' }}>+{dayLeads.length - 3} nữa</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()
        ) : (
          /* Kanban Board */
          <div className="flex gap-4 overflow-x-auto pb-4 min-w-0">
            {kanban.map(col => {
              const config = STAGE_CONFIG[col.stage];
              return (
                <div key={col.stage} className="kanban-column flex-shrink-0">
                  <div className="flex items-center gap-2 mb-3 px-1">
                    <div className="stage-dot" style={{ backgroundColor: config?.color }} />
                    <span className="text-sm font-medium">{config?.label}</span>
                    <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-white/10 text-[var(--text-secondary)]">
                      {col.leads.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {col.leads.map(lead => (
                      <div
                        key={lead.id}
                        onClick={() => openLeadDetail(lead)}
                        className={cn(
                          'glass-card p-3 border-l-2 cursor-pointer hover:bg-white/8 transition-all group',
                          lead.priority === 'urgent' ? 'border-l-red-500' :
                          lead.priority === 'high' ? 'border-l-amber-500' :
                          lead.priority === 'medium' ? 'border-l-blue-500' : 'border-l-gray-500'
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <h3 className="text-sm font-medium text-white group-hover:text-[#C9A96E] transition-colors">
                            {lead.name}
                          </h3>
                          {lead.deal_value ? (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#C9A96E]/15 text-[#C9A96E] font-semibold">
                              {formatDealValue(lead.deal_value)}
                            </span>
                          ) : lead.estimated_budget ? (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#C9A96E]/15 text-[#C9A96E]">
                              {formatCurrency(lead.estimated_budget)}
                            </span>
                          ) : null}
                        </div>
                        <p className="text-xs text-[var(--text-muted)] mt-1">📱 {lead.phone}</p>
                        {lead.property_type && (
                          <p className="text-xs text-[var(--text-muted)] mt-0.5">
                            🏠 {PROPERTY_LABELS[lead.property_type] || lead.property_type} {lead.area_sqm ? `· ${lead.area_sqm}m²` : ''}
                          </p>
                        )}
                        {/* Region + Segment line */}
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          {lead.region && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                              📍 {lead.region}
                            </span>
                          )}
                          {lead.segment && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                              🏷️ {lead.segment}
                            </span>
                          )}
                        </div>
                        {/* Tags — tags may be a JSON string like '["VIP"]' or a real array */}
                        {(() => {
                          const parsedTags = Array.isArray(lead.tags)
                            ? lead.tags
                            : typeof lead.tags === "string" && lead.tags
                              ? (() => { try { return JSON.parse(lead.tags); } catch { return []; } })()
                              : [];
                          return parsedTags.length > 0 ? (
                            <div className="flex gap-1 mt-1.5 flex-wrap">
                              {parsedTags.map((tag: string) => <TagBadge key={tag} tag={tag} />)}
                            </div>
                          ) : null;
                        })()}
                        {lead.ai_score != null && lead.ai_score > 0 && (
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <div className="flex-1 h-1.5 rounded-full bg-white/10">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${lead.ai_score}%`,
                                  backgroundColor: lead.ai_score >= 80 ? '#10B981' : lead.ai_score >= 60 ? '#F59E0B' : '#EF4444',
                                }}
                              />
                            </div>
                            <span className="text-[9px] text-[var(--text-muted)]">AI {lead.ai_score}</span>
                          </div>
                        )}
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {lead.assigned_user_name || '—'}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                            {SOURCE_LABELS[lead.source || ''] || lead.source || '—'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Lead Detail Modal ── */}
      {selectedLead && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]"
          onClick={() => setSelectedLead(null)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-2xl max-h-[78vh] overflow-y-auto rounded-2xl animate-in"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between p-5 border-b" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)' }}>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' }}>
                  <span className="text-lg font-bold text-white">{selectedLead.name.charAt(0)}</span>
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">{selectedLead.name}</h2>
                  <p className="text-xs text-[var(--text-muted)]">{selectedLead.contact_person || selectedLead.name}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="p-2 rounded-lg hover:bg-white/10 transition-colors text-[var(--text-muted)]"
              >
                ✕
              </button>
            </div>

            <div className="p-4 sm:p-5 space-y-5">
              {/* Status bar */}
              <div className="flex flex-wrap gap-2">
                <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                  background: `${STAGE_CONFIG[selectedLead.stage]?.color}20`,
                  color: STAGE_CONFIG[selectedLead.stage]?.color,
                }}>
                  {STAGE_CONFIG[selectedLead.stage]?.emoji} {STAGE_CONFIG[selectedLead.stage]?.label}
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                  background: `${PRIORITY_LABELS[selectedLead.priority]?.color}20`,
                  color: PRIORITY_LABELS[selectedLead.priority]?.color,
                }}>
                  {PRIORITY_LABELS[selectedLead.priority]?.label}
                </span>
                {selectedLead.property_class && PROPERTY_CLASS_LABELS[selectedLead.property_class] && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                    background: `${PROPERTY_CLASS_LABELS[selectedLead.property_class].color}20`,
                    color: PROPERTY_CLASS_LABELS[selectedLead.property_class].color,
                  }}>
                    🏷️ {PROPERTY_CLASS_LABELS[selectedLead.property_class].label}
                  </span>
                )}
                {selectedLead.plan_type && selectedLead.plan_type !== 'none' && PLAN_TYPE_LABELS[selectedLead.plan_type] && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                    background: `${PLAN_TYPE_LABELS[selectedLead.plan_type].color}20`,
                    color: PLAN_TYPE_LABELS[selectedLead.plan_type].color,
                  }}>
                    📋 {PLAN_TYPE_LABELS[selectedLead.plan_type].label}
                  </span>
                )}
                {selectedLead.ai_score != null && selectedLead.ai_score > 0 && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                    background: selectedLead.ai_score >= 80 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
                    color: selectedLead.ai_score >= 80 ? '#10B981' : '#F59E0B',
                  }}>
                    🤖 AI Score: {selectedLead.ai_score}/100
                  </span>
                )}
              </div>

              {/* Tags */}
              {selectedLead.tags && selectedLead.tags.length > 0 && (
                <div className="flex gap-1.5 flex-wrap">
                  {selectedLead.tags.map(tag => <TagBadge key={tag} tag={tag} />)}
                </div>
              )}

              {/* Contact Info */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Thông tin liên hệ</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--text-muted)]">📱</span>
                    <span className="text-white font-medium">{selectedLead.phone}</span>
                  </div>
                  {selectedLead.email && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--text-muted)]">📧</span>
                      <span className="text-white">{selectedLead.email}</span>
                    </div>
                  )}
                  {selectedLead.address && (
                    <div className="flex items-center gap-2 md:col-span-2">
                      <span className="text-[var(--text-muted)]">📍</span>
                      <span className="text-[var(--text-secondary)]">{selectedLead.address}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--text-muted)]">📢</span>
                    <span className="text-[var(--text-secondary)]">Nguồn: {SOURCE_LABELS[selectedLead.source || ''] || selectedLead.source}</span>
                  </div>
                  {selectedLead.region && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--text-muted)]">🗺️</span>
                      <span className="text-[var(--text-secondary)]">Khu vực: {selectedLead.region}</span>
                    </div>
                  )}
                  {selectedLead.assigned_user_name && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--text-muted)]">👤</span>
                      <span className="text-[var(--text-secondary)]">Phụ trách: {selectedLead.assigned_user_name}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Property & Budget */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Nhu cầu & Dự án</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mb-3">
                  <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Loại BĐS</p>
                    <p className="text-sm font-semibold mt-1">{PROPERTY_LABELS[selectedLead.property_type || ''] || selectedLead.property_type || '—'}</p>
                  </div>
                  <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Diện tích</p>
                    <p className="text-sm font-semibold mt-1">{selectedLead.area_sqm || '—'}m²</p>
                  </div>
                  <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Ngân sách</p>
                    <p className="text-sm font-semibold mt-1 text-[#C9A96E]">{formatCurrency(selectedLead.estimated_budget)}</p>
                  </div>
                  <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)]">Deal Value</p>
                    <p className="text-sm font-bold mt-1 text-[#10B981]">{formatDealValue(selectedLead.deal_value)}</p>
                  </div>
                </div>
                {/* New Lark CRM fields grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 mb-3">
                  {selectedLead.segment && (
                    <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                      <p className="text-xs text-[var(--text-muted)]">Phân khúc</p>
                      <p className="text-sm font-semibold mt-1">{selectedLead.segment}</p>
                    </div>
                  )}
                  {selectedLead.price_per_sqm && (
                    <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                      <p className="text-xs text-[var(--text-muted)]">Đơn giá/m²</p>
                      <p className="text-sm font-semibold mt-1 text-[#C9A96E]">{formatPricePerSqm(selectedLead.price_per_sqm)}</p>
                    </div>
                  )}
                  {selectedLead.region && (
                    <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                      <p className="text-xs text-[var(--text-muted)]">Khu vực</p>
                      <p className="text-sm font-semibold mt-1">📍 {selectedLead.region}</p>
                    </div>
                  )}
                </div>
                {selectedLead.needs && (
                  <div className="p-3 rounded-lg text-sm text-[var(--text-secondary)]" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)] mb-1">📋 Yêu cầu chi tiết:</p>
                    {selectedLead.needs}
                  </div>
                )}
              </div>

              {/* Notes */}
              {selectedLead.notes && (
                <div className="glass-card p-4">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Ghi chú nội bộ</h3>
                  <p className="text-sm text-[var(--text-secondary)]">{selectedLead.notes}</p>
                </div>
              )}

              {/* Activity Timeline */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                  Lịch sử hoạt động ({activities.length})
                </h3>
                {loadingActivities ? (
                  <div className="text-center py-4 text-sm text-[var(--text-muted)]">Đang tải...</div>
                ) : activities.length === 0 ? (
                  <div className="text-center py-4 text-sm text-[var(--text-muted)]">Chưa có hoạt động</div>
                ) : (
                  <div className="space-y-3">
                    {[...activities].reverse().map((act, i) => (
                      <div key={act.id || i} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <span className="text-sm">{ACTIVITY_ICONS[act.type] || '📌'}</span>
                          {i < activities.length - 1 && (
                            <div className="w-px flex-1 mt-1" style={{ background: 'var(--border-subtle)' }} />
                          )}
                        </div>
                        <div className="flex-1 pb-3">
                          <div className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">
                            {act.content.split('\n').map((line, li) => {
                              if (line.startsWith('📎')) {
                                const url = line.replace('📎', '').trim();
                                return (
                                  <a key={li} href={url} target="_blank" rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-[#C9A96E] hover:underline text-xs mt-1"
                                  >
                                    📎 {url.replace('https://drive.google.com/', 'drive.google.com/...')}
                                  </a>
                                );
                              }
                              return <span key={li}>{line}{li < act.content.split('\n').length - 1 && <br />}</span>;
                            })}
                          </div>
                          <p className="text-[10px] text-[var(--text-muted)] mt-1">
                            {act.user_name || 'System'} · {new Date(act.created_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add Note */}
                <div className="mt-3 pt-3 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex gap-2">
                    <input
                      value={newNote}
                      onChange={e => setNewNote(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleAddNote()}
                      placeholder="Thêm ghi chú..."
                      className="flex-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-[#C9A96E]"
                    />
                    <button
                      onClick={handleAddNote}
                      disabled={!newNote.trim()}
                      className="px-3 py-2 rounded-lg text-sm font-medium bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 disabled:opacity-30 transition-all"
                    >
                      Gửi
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--text-muted)] text-xs flex-shrink-0">📎</span>
                    <input
                      value={newNoteLink}
                      onChange={e => setNewNoteLink(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleAddNote()}
                      placeholder="Link Google Drive (tùy chọn)..."
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-[#C9A96E]"
                    />
                  </div>
                </div>
              </div>

              {/* Stage Actions */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">Chuyển giai đoạn</h3>
                <div className="flex flex-wrap gap-2">
                  {STAGES.filter(s => s !== selectedLead.stage).map(stage => (
                    <button
                      key={stage}
                      onClick={() => handleStageChange(selectedLead, stage)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
                      style={{
                        background: `${STAGE_CONFIG[stage]?.color}15`,
                        color: STAGE_CONFIG[stage]?.color,
                        border: `1px solid ${STAGE_CONFIG[stage]?.color}30`,
                      }}
                    >
                      {STAGE_CONFIG[stage]?.emoji} {STAGE_CONFIG[stage]?.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Timestamps */}
              <div className="flex justify-between text-[10px] text-[var(--text-disabled)] pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <span>Tạo: {new Date(selectedLead.created_at).toLocaleDateString('vi-VN')}</span>
                <span>Cập nhật: {new Date(selectedLead.updated_at).toLocaleDateString('vi-VN')}</span>
                <span>Liên hệ: {selectedLead.last_contacted_at ? timeAgo(selectedLead.last_contacted_at) : 'Chưa'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Lead Modal */}
      <CreateLeadModal isOpen={createOpen} onClose={() => { setCreateOpen(false); fetchLeads(); }} />
    </Sidebar>
  );
}

export default function LeadsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">⏳</div>}>
      <LeadsContent />
    </Suspense>
  );
}
