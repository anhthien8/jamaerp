'use client';

import { useEffect, useState, useCallback, useRef, Suspense } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import {
  STAGE_CONFIG, formatCurrency, timeAgo, cn,
  formatPricePerSqm, formatDealValue,
  PROPERTY_CLASS_LABELS, PLAN_TYPE_LABELS,
  REGION_OPTIONS, TAG_COLORS,
} from '@/lib/utils';
import { useToast } from '@/components/ui/Toast';
import CreateLeadModal from '@/components/ui/CreateLeadModal';
import { api, Lead, Activity, User, AISuggestion, AISuggestionHistory, fetchAllPages } from '@/lib/api';
import { getPermissions, canAssignLeads, canWriteCskhNote, isSalesCoordinator, UserRole } from '@/lib/roles';

const PROPERTY_LABELS: Record<string, string> = {
  townhouse: 'Nhà phố', apartment: 'Căn hộ', villa: 'Biệt thự',
  office: 'Văn phòng', shophouse: 'Shophouse', other: 'Khác',
};
const SOURCE_LABELS: Record<string, string> = {
  facebook: 'Facebook', zalo: 'Zalo', website: 'Website',
  referral: 'Giới thiệu', tiktok: 'TikTok', other: 'Khác',
};
const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  urgent: { label: 'Khẩn cấp', color: 'var(--danger)' },
  high: { label: 'Cao', color: 'var(--warning)' },
  medium: { label: 'Trung bình', color: 'var(--info)' },
  low: { label: 'Thấp', color: '#6B7280' },
};
const ACTIVITY_ICONS: Record<string, string> = {
  note: '📝', call: '📞', meeting: '🤝', email: '📧', sms: '💬',
  stage_change: '🔄', assignment: '👤', system: '🤖', cskh: '🎧',
};
// Lognote CSKH — khớp CSKH_ACTIVITY_TYPE backend. Lưu chung bảng activities nên
// mỗi mục tự có ngày giờ + tên người nhập; render ở khối riêng, tách khỏi timeline
// chung để đánh giá chất lượng không bị trôi lẫn giữa hàng chục cuộc gọi.
const CSKH_TYPE = 'cskh';
const STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design'];
// Cột hiển thị trên bảng kanban. KHÁC STAGES vì "Mất" phải có mặt để kiểm soát lead rơi,
// nhưng không được nằm trong STAGES: chuyển sang "Mất" bắt buộc kèm lý do, mà các nút
// "Chuyển giai đoạn" trong thẻ chi tiết lại bắn thẳng handleStageChange không lý do.
const BOARD_STAGES = [...STAGES, 'lost'];
const ALL_STAGES = ['new', 'interested', 'survey_scheduled', 'potential', 'signed_design', 'lost', 'dormant'];
const OVERDUE_DAYS = 3;
const LOST_REASONS = [
  'Ngân sách không phù hợp',
  'Đã chọn đối thủ',
  'Không phản hồi',
  'Thay đổi kế hoạch',
  'Lý do khác',
];

// ── Lọc theo ngày (double-check lead nhập đúng/đủ) ──────────────────────────
// Backend trả ISO KHÔNG kèm timezone (cột DateTime naive) nên new Date() đọc theo
// giờ máy — đúng bằng cách timeAgo/toLocaleString đang hiển thị ở mọi trang khác.
const DATE_FIELDS: Record<string, { label: string; short: string; pick: (l: Lead) => string | undefined }> = {
  updated_at: { label: 'Ngày cập nhật', short: 'Cập nhật', pick: l => l.updated_at },
  created_at: { label: 'Ngày thêm mới', short: 'Thêm mới', pick: l => l.created_at },
  last_contacted_at: { label: 'Ngày liên hệ cuối', short: 'Liên hệ cuối', pick: l => l.last_contacted_at },
};
const DATE_PRESETS: { value: string; label: string }[] = [
  { value: 'all', label: 'Mọi lúc' },
  { value: 'today', label: 'Hôm nay' },
  { value: 'yesterday', label: 'Hôm qua' },
  { value: '7d', label: '7 ngày qua' },
  { value: '30d', label: '30 ngày qua' },
  { value: 'this_month', label: 'Tháng này' },
  { value: 'custom', label: 'Tùy chọn…' },
];

function dayKey(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function toDayKey(value?: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : dayKey(d);
}

function daysAgoKey(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return dayKey(d);
}

function formatDayKey(key: string): string {
  const [y, m, d] = key.split('-');
  return `${d}/${m}/${y}`;
}

/** Đổi preset + 2 ô ngày tùy chọn thành khoảng [from, to] dạng YYYY-MM-DD. null = không lọc. */
function resolveDateRange(preset: string, from: string, to: string): { from: string; to: string } | null {
  const today = dayKey(new Date());
  switch (preset) {
    case 'today': return { from: today, to: today };
    case 'yesterday': { const y = daysAgoKey(1); return { from: y, to: y }; }
    case '7d': return { from: daysAgoKey(6), to: today };
    case '30d': return { from: daysAgoKey(29), to: today };
    case 'this_month': { const n = new Date(); return { from: dayKey(new Date(n.getFullYear(), n.getMonth(), 1)), to: today }; }
    case 'custom': {
      if (!from && !to) return null;
      // Nhập ngược (từ > đến) thì tự đảo, khỏi ra bảng trống mà không hiểu vì sao.
      if (from && to && from > to) return { from: to, to: from };
      return { from: from || '0000-01-01', to: to || '9999-12-31' };
    }
    default: return null;
  }
}

type SortKey = 'newest' | 'updated' | 'budget' | 'ai_score' | 'deal_value';

function getLeadTimestamp(lead: Lead) {
  return lead.last_contacted_at || lead.updated_at || lead.created_at;
}

function formatShortDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('vi-VN');
}

/** Ngày giờ đầy đủ CÓ năm — lognote CSKH trải nhiều tháng, thiếu năm là đọc nhầm. */
function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** Ô tiêu đề bảng bấm được để đổi kiểu sắp xếp (dùng chung state với select "Sắp xếp"). */
function SortableTh({ label, sortKey, sortBy, setSortBy, align = 'left' }: {
  label: string;
  sortKey: SortKey;
  sortBy: SortKey;
  setSortBy: (key: SortKey) => void;
  align?: 'left' | 'right';
}) {
  const active = sortBy === sortKey;
  return (
    <th className={cn('px-4 py-3 font-medium whitespace-nowrap', align === 'right' ? 'text-right' : 'text-left')}
      style={{ color: active ? '#C9A96E' : 'var(--text-tertiary)' }}>
      <button
        onClick={() => setSortBy(sortKey)}
        className="inline-flex items-center gap-1 hover:text-[#C9A96E] transition-colors"
        title={`Sắp xếp theo ${label.toLowerCase()}`}
      >
        {label}
        <span className={cn('text-[9px]', !active && 'opacity-30')}>▼</span>
      </button>
    </th>
  );
}

function PlainTh({ label, align = 'left' }: { label: string; align?: 'left' | 'right' }) {
  return (
    <th className={cn('px-4 py-3 font-medium whitespace-nowrap text-[var(--text-tertiary)]', align === 'right' ? 'text-right' : 'text-left')}>
      {label}
    </th>
  );
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
      className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-full font-medium"
      style={{ background: `${color}20`, color, border: `1px solid ${color}30` }}
    >
      {tag}
    </span>
  );
}

// Ô chọn lý do mất lead. Trạng thái mở do trang mẹ giữ để kéo thẻ vào cột "Mất"
// hoặc chọn "Mất" ở dropdown nhanh có thể bật sẵn ô này thay vì bắt user tự dò.
function LostReasonSelector({ isOpen, setIsOpen, onConfirm, onCancel }: {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [selectedReason, setSelectedReason] = useState('');
  const [customReason, setCustomReason] = useState('');

  const handleConfirm = () => {
    const reason = selectedReason === 'Lý do khác' ? customReason.trim() : selectedReason;
    if (!reason) return;
    onConfirm(reason);
    setIsOpen(false);
    setSelectedReason('');
    setCustomReason('');
  };

  return (
    <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
          style={{
            background: 'rgba(239,68,68,0.1)',
            color: '#EF4444',
            border: '1px solid rgba(239,68,68,0.3)',
          }}
        >
          🚫 Chuyển sang Mất lead
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-red-400">Chọn lý do mất lead:</p>
          <div className="flex flex-wrap gap-1.5">
            {LOST_REASONS.map(reason => (
              <button
                key={reason}
                onClick={() => setSelectedReason(reason)}
                className="px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all"
                style={{
                  background: selectedReason === reason ? 'rgba(239,68,68,0.25)' : 'var(--surface-2)',
                  color: selectedReason === reason ? '#EF4444' : 'var(--text-secondary)',
                  border: `1px solid ${selectedReason === reason ? 'rgba(239,68,68,0.4)' : 'var(--border-subtle)'}`,
                }}
              >
                {reason}
              </button>
            ))}
          </div>
          {selectedReason === 'Lý do khác' && (
            <input
              value={customReason}
              onChange={e => setCustomReason(e.target.value)}
              placeholder="Nhập lý do cụ thể..."
              className="w-full px-3 py-1.5 rounded-lg text-xs bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-red-400"
            />
          )}
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={!selectedReason || (selectedReason === 'Lý do khác' && !customReason.trim())}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 disabled:opacity-30 transition-all"
            >
              Xác nhận mất lead
            </button>
            <button
              onClick={() => { setIsOpen(false); setSelectedReason(''); setCustomReason(''); onCancel(); }}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
            >
              Hủy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function LeadsContent() {

  const { user, loading } = useAuth();
  const router = useRouter();
  const perms = getPermissions((user?.role || 'data_entry') as UserRole);
  // Admin/leader/điều phối KD (CSKH) được gắn/đổi người phụ trách — khớp can_assign_leads() backend.
  const canAssign = canAssignLeads(user);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  // Kéo thả kanban (feedback beta 22/07) — cột đang được kéo qua để highlight
  const [dragOverStage, setDragOverStage] = useState<string | null>(null);
  // Ô chọn lý do mất lead trong thẻ chi tiết — bật sẵn khi user kéo vào cột "Mất".
  const [lostPickerOpen, setLostPickerOpen] = useState(false);
  const lostPickerRef = useRef<HTMLDivElement | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loadingLeads, setLoadingLeads] = useState(true);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [filterRegion, setFilterRegion] = useState<string>('all');
  const [filterPropertyClass, setFilterPropertyClass] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortKey>('newest');
  // Lọc theo ngày tạo/cập nhật/liên hệ — để soát lại lead vừa nhập đã đúng & đủ chưa.
  const [dateField, setDateField] = useState<string>('updated_at');
  const [datePreset, setDatePreset] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [newNote, setNewNote] = useState('');
  const [newNoteLink, setNewNoteLink] = useState('');
  // Lognote CSKH — chỉ Admin CSKH + admin nhập được (backend chặn 403 vai trò khác).
  const [newCskhNote, setNewCskhNote] = useState('');
  const [savingCskh, setSavingCskh] = useState(false);
  const canWriteCskh = canWriteCskhNote(user);
  const [viewMode, setViewMode] = useState<'kanban' | 'list' | 'calendar'>('kanban');
  const [error, setError] = useState<string | null>(null);
  const [calendarDate, setCalendarDate] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [searchQuery, setSearchQuery] = useState('');
  const searchParams = useSearchParams();
  const urlStage = searchParams.get('stage');
  const urlFilter = searchParams.get('filter');
  const activeStage = urlStage && ALL_STAGES.includes(urlStage) ? urlStage : null;
  const activeQuickFilter = urlFilter === 'overdue' ? 'overdue' : null;
  const { toast } = useToast();
  // Khóa chống double-click / double-drop khi đang gọi API đổi stage:
  // vào "Deal đã thắng" (signed_design) mà bắn 2 lần sẽ tạo TRÙNG Khách hàng + Dự án.
  const stageBusy = useRef(false);
  // ── Gắn/đổi nhân viên kinh doanh phụ trách (admin + leader; backend chặn 403 role khác) ──
  const [assignableUsers, setAssignableUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const usersLoaded = useRef(false);
  // ── Gợi ý AI (Sales Co-Pilot) ──
  // Chỉ gọi khi sale bấm nút: mỗi lượt là một lượt LLM, mở thẻ lead mà tự chạy thì
  // vừa tốn quota vừa nhiễu. Lịch sử thì tải sẵn vì chỉ là một truy vấn bảng.
  const [goiY, setGoiY] = useState<AISuggestion | null>(null);
  const [lichSuGoiY, setLichSuGoiY] = useState<AISuggestionHistory[]>([]);
  const [dangXinGoiY, setDangXinGoiY] = useState(false);
  const [dangGhiNhan, setDangGhiNhan] = useState(false);

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
      // Lấy đủ mọi trang: trang này lọc/sắp xếp phía trình duyệt nên chỉ nhận 50 lead
      // đầu là ra kết quả sai mà không ai biết (xem chú thích fetchAllPages).
      const allLeads = (await fetchAllPages(p => api.getLeads(p), params)).map(lead => ({
        ...lead,
        tags: typeof lead.tags === 'string' ? (() => { try { return JSON.parse(lead.tags); } catch { return []; } })() : lead.tags || [],
      }));
      // Apply role-based scope filtering.
      // Điều phối KD (CSKH — vai trò tùy chỉnh bộ phận KD) phải thấy TẤT CẢ để phân chia,
      // dù leadsScope của vai trò custom fallback về 'own' của data_entry.
      const scope = isSalesCoordinator(user?.role, user?.department) ? 'all' : perms.leadsScope;
      let filtered = allLeads;
      if (scope === 'own') {
        filtered = allLeads.filter(l => l.assigned_to === user?.id);
      } else if (scope === 'team') {
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
      setError('Không thể tải dữ liệu. Vui lòng thử lại.');
      setLeads([]);
    } finally {
      setLoadingLeads(false);
    }
  }, [filterSource, filterPriority, filterRegion, filterPropertyClass, perms.leadsScope, user?.id, user?.team_id, user?.role, user?.department]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchLeads);
  }, [user, fetchLeads]);

  const openLeadDetail = async (lead: Lead, options?: { lostPicker?: boolean }) => {
    setSelectedLead(lead);
    // Ô ghi chú luôn sạch khi mở thẻ mới (tránh sót nội dung của lead trước).
    setNewNote('');
    setNewNoteLink('');
    setNewCskhNote('');
    setLostPickerOpen(Boolean(options?.lostPicker));
    setAssignOpen(false);
    setActivities([]);
    setGoiY(null);
    setLichSuGoiY([]);
    setLoadingActivities(true);
    try {
      const acts = await api.getActivities(lead.id);
      setActivities(acts);
    } catch {
      setActivities([]);
    } finally {
      setLoadingActivities(false);
    }
    // Lịch sử gợi ý hỏng thì thôi, không được kéo cả thẻ lead chết theo
    try {
      const ls = await api.getSuggestionHistory(lead.id);
      setLichSuGoiY(ls.items || []);
    } catch {
      setLichSuGoiY([]);
    }
  };

  // Đóng thẻ lead: reset luôn ô ghi chú để lần mở sau không dính nội dung cũ.
  const closeLeadDetail = useCallback(() => {
    setSelectedLead(null);
    setNewNote('');
    setNewNoteLink('');
    setNewCskhNote('');
    setAssignOpen(false);
    setLostPickerOpen(false);
    setGoiY(null);
    setLichSuGoiY([]);
  }, []);

  // Ô chọn lý do nằm cuối thẻ chi tiết (thẻ có thể cuộn) — bật sẵn mà không cuộn tới
  // thì user bấm "Mất" xong tưởng không có gì xảy ra.
  useEffect(() => {
    if (!lostPickerOpen || !selectedLead) return;
    const id = window.setTimeout(() => {
      lostPickerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
    return () => window.clearTimeout(id);
  }, [lostPickerOpen, selectedLead]);

  // Xin Co-Pilot một gợi ý mới. Backend tự đọc lại các gợi ý cũ + phản hồi của sale
  // nên không lặp lại việc đã làm/đã bỏ qua.
  const xinGoiY = async () => {
    if (!selectedLead || dangXinGoiY) return;
    setDangXinGoiY(true);
    try {
      const res = await api.suggestAction(selectedLead.id);
      setGoiY(res);
      if (res.lich_su) setLichSuGoiY(res.lich_su);
    } catch {
      toast('Không lấy được gợi ý', 'error');
    } finally {
      setDangXinGoiY(false);
    }
  };

  // Sale bấm "Đã làm" / "Bỏ qua" — đây chính là thứ nuôi bộ nhớ cho lượt sau.
  const ghiNhanGoiY = async (outcome: 'done' | 'skipped') => {
    if (!goiY?.run_id || dangGhiNhan) return;
    setDangGhiNhan(true);
    try {
      await api.markSuggestionOutcome(goiY.run_id, outcome);
      const ls = await api.getSuggestionHistory(selectedLead!.id);
      setLichSuGoiY(ls.items || []);
      setGoiY(null);
      toast(outcome === 'done' ? 'Đã ghi nhận: đã làm' : 'Đã ghi nhận: bỏ qua', 'success');
    } catch {
      toast('Lỗi khi ghi nhận', 'error');
    } finally {
      setDangGhiNhan(false);
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

  // Ghi một mục lognote CSKH. Backend đóng dấu ngày giờ + tên người nhập, và cố ý
  // KHÔNG cập nhật "liên hệ lần cuối" của lead (đây là gọi kiểm tra, không phải chăm khách).
  const handleAddCskhNote = async () => {
    if (!selectedLead || !newCskhNote.trim() || savingCskh) return;
    setSavingCskh(true);
    try {
      await api.createActivity(selectedLead.id, { type: CSKH_TYPE, content: newCskhNote.trim() });
      setActivities(await api.getActivities(selectedLead.id));
      setNewCskhNote('');
      toast('Đã lưu đánh giá CSKH', 'success');
    } catch (e) {
      toast(`Lỗi khi lưu đánh giá: ${e instanceof Error ? e.message : 'Không rõ'}`, 'error');
    } finally {
      setSavingCskh(false);
    }
  };

  const handleStageChange = async (lead: Lead, newStage: string, reasonOverride?: string) => {
    if (newStage === 'lost' && !reasonOverride) {
      toast('Vui lòng chọn lý do mất lead', 'error');
      return;
    }
    // Đang có 1 lượt đổi stage chạy dở → bỏ qua lượt thứ 2 (chặn tạo trùng KH+Dự án).
    if (stageBusy.current) return;
    stageBusy.current = true;
    try {
      if (newStage === 'lost' && reasonOverride) {
        await api.updateLead(lead.id, { stage: newStage, lost_reason: reasonOverride });
      } else {
        await api.changeStage(lead.id, newStage);
      }
      toast(`Chuyển ${lead.name} sang ${STAGE_CONFIG[newStage]?.label || newStage}`, 'success');
      fetchLeads();
      closeLeadDetail();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      stageBusy.current = false;
    }
  };

  // Nạp ứng viên phụ trách 1 lần rồi cache (bộ lọc dùng chung nằm ở api.getAssignableSales).
  const loadAssignableUsers = useCallback(async () => {
    if (usersLoaded.current) return;
    setLoadingUsers(true);
    try {
      setAssignableUsers(await api.getAssignableSales());
      usersLoaded.current = true;
    } catch (e) {
      toast(`Lỗi tải danh sách nhân viên: ${e instanceof Error ? e.message : 'Không rõ'}`, 'error');
    } finally {
      setLoadingUsers(false);
    }
  }, [toast]);

  const openAssign = () => {
    setAssignOpen(true);
    void loadAssignableUsers();
  };

  // Giao/đổi người phụ trách: gọi API rồi cập nhật selectedLead + danh sách/kanban tại chỗ.
  const handleAssign = async (userId: string) => {
    if (!selectedLead || !userId || userId === selectedLead.assigned_to || assigning) return;
    const leadId = selectedLead.id;
    setAssigning(true);
    try {
      const updated = await api.assignLead(leadId, userId);
      const picked = assignableUsers.find(u => u.id === userId);
      const newName = updated.assigned_user_name || picked?.full_name || '';
      const newTeam = updated.team_id ?? picked?.team_id;
      const applyPatch = (l: Lead): Lead => ({
        ...l,
        assigned_to: userId,
        assigned_user_name: newName || l.assigned_user_name,
        ...(newTeam !== undefined ? { team_id: newTeam } : {}),
      });
      setSelectedLead(prev => (prev && prev.id === leadId ? applyPatch(prev) : prev));
      setLeads(prev => prev.map(l => (l.id === leadId ? applyPatch(l) : l)));
      setAssignOpen(false);
      toast(`Đã giao lead cho ${newName || 'nhân viên'}`, 'success');
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không thể giao lead'}`, 'error');
    } finally {
      setAssigning(false);
    }
  };

  if (loading || !user) return <Sidebar><div className="p-6 space-y-4"><div className="skeleton h-8 w-48 rounded-xl" /><div className="grid grid-cols-5 gap-3">{[1,2,3,4,5].map(i => <div key={i} className="skeleton h-32 rounded-xl" />)}</div></div></Sidebar>;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <span className="text-4xl block mb-4">⚠️</span>
            <p className="text-[var(--text-primary)] mb-2">{error}</p>
            <button onClick={() => { setError(null); fetchLeads(); }} className="mt-3 px-4 py-2 rounded-xl bg-[var(--gold-500)] text-white text-sm">Thử lại</button>
          </div>
        </div>
      </Sidebar>
    );
  }


  // Sort leads
  const sorted = [...leads];
  if (sortBy === 'budget') sorted.sort((a, b) => (b.estimated_budget || 0) - (a.estimated_budget || 0));
  else if (sortBy === 'ai_score') sorted.sort((a, b) => (b.ai_score || 0) - (a.ai_score || 0));
  else if (sortBy === 'deal_value') sorted.sort((a, b) => (b.deal_value || 0) - (a.deal_value || 0));
  else if (sortBy === 'updated') sorted.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
  else sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const dateRange = resolveDateRange(datePreset, dateFrom, dateTo);

  const filteredByUrl = sorted.filter(lead => {
    if (activeStage && lead.stage !== activeStage) return false;
    if (activeQuickFilter === 'overdue' && !isOverdueLead(lead)) return false;
    if (dateRange) {
      // Lead chưa có mốc ngày đang lọc (vd chưa liên hệ lần nào) coi như không khớp.
      const key = toDayKey(DATE_FIELDS[dateField]?.pick(lead));
      if (!key || key < dateRange.from || key > dateRange.to) return false;
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!lead.name.toLowerCase().includes(q) && !(lead.phone || '').includes(q)
        && !(lead.email || '').toLowerCase().includes(q) && !(lead.address || '').toLowerCase().includes(q)
        && !(lead.property_type || '').toLowerCase().includes(q) && !(lead.needs || '').toLowerCase().includes(q)
        && !(lead.region || '').toLowerCase().includes(q) && !(lead.channel || '').toLowerCase().includes(q)) return false;
    }
    return true;
  });

  // Vào bằng deep-link ?stage=... thì chỉ dựng đúng cột đó, khỏi bày 5 cột rỗng.
  const visibleStages = activeStage ? [activeStage] : BOARD_STAGES;

  // Group by stage for kanban
  const kanban = visibleStages.map(stage => ({
    stage,
    leads: filteredByUrl.filter(l => l.stage === stage),
  }));

  // Số hiển thị phải khớp thứ đang thực sự vẽ ra: kanban bỏ qua lead ngoài các cột
  // (vd "Ngủ đông"), còn bảng/lịch thì vẽ hết.
  const shownCount = viewMode === 'kanban'
    ? kanban.reduce((sum, col) => sum + col.leads.length, 0)
    : filteredByUrl.length;

  // Khoảng để mở một đầu thì ghi "từ …" / "đến …", đừng in ra mốc bù 01/01/0000.
  const dateRangeLabel = dateRange
    ? (datePreset === 'custom'
      ? (!dateTo ? `từ ${formatDayKey(dateRange.from)}`
        : !dateFrom ? `đến ${formatDayKey(dateRange.to)}`
          : `${formatDayKey(dateRange.from)} → ${formatDayKey(dateRange.to)}`)
      : DATE_PRESETS.find(p => p.value === datePreset)?.label || '')
    : null;

  // Lognote CSKH tách khỏi timeline chung: mỗi bên một khối riêng trong thẻ chi tiết,
  // để đánh giá chất lượng không trôi lẫn giữa hàng chục cuộc gọi/ghi chú thường ngày.
  const cskhNotes = activities.filter(a => a.type === CSKH_TYPE);
  const timelineActivities = activities.filter(a => a.type !== CSKH_TYPE);

  const hasUrlFilters = Boolean(activeStage || activeQuickFilter);
  const hasFilters = filterSource !== 'all' || filterPriority !== 'all' || filterRegion !== 'all' || filterPropertyClass !== 'all' || hasUrlFilters || searchQuery !== '' || datePreset !== 'all';
  const activeFilterLabels = [
    activeStage ? `Giai đoạn: ${STAGE_CONFIG[activeStage]?.label || activeStage}` : null,
    activeQuickFilter === 'overdue' ? `Quá hạn CSKH > ${OVERDUE_DAYS} ngày` : null,
    filterRegion !== 'all' ? `Khu vực: ${filterRegion}` : null,
    filterPropertyClass !== 'all' ? PROPERTY_CLASS_LABELS[filterPropertyClass]?.label : null,
    dateRangeLabel ? `${DATE_FIELDS[dateField]?.label}: ${dateRangeLabel}` : null,
  ].filter(Boolean);

  const clearFilters = () => {
    setFilterSource('all');
    setFilterPriority('all');
    setFilterRegion('all');
    setFilterPropertyClass('all');
    setSearchQuery('');
    setDatePreset('all');
    setDateFrom('');
    setDateTo('');
    if (hasUrlFilters) router.push('/leads');
  };

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <h1 className="text-2xl font-bold">Quy trình CRM</h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                {viewMode === 'list' ? 'Click vào dòng để xem chi tiết' : 'Click vào card để xem chi tiết'} · {shownCount}/{leads.length} leads
              </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap sm:flex-shrink-0">
            <div className="flex rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
              {([
                { mode: 'kanban', label: '📋 Kanban' },
                { mode: 'list', label: '📊 Danh sách' },
                { mode: 'calendar', label: '📅 Lịch' },
              ] as const).map((v, i, arr) => (
                <button
                  key={v.mode}
                  onClick={() => setViewMode(v.mode)}
                  aria-pressed={viewMode === v.mode}
                  className="px-3 py-1.5 text-xs font-medium transition-all whitespace-nowrap"
                  style={{
                    background: viewMode === v.mode ? 'rgba(201,169,110,0.2)' : 'var(--surface-2)',
                    color: viewMode === v.mode ? '#C9A96E' : 'var(--text-muted)',
                    borderRight: i < arr.length - 1 ? '1px solid var(--border-subtle)' : undefined,
                  }}
                >{v.label}</button>
              ))}
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
          {/* Search input */}
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input
              type="text"
              placeholder="Tìm tên, SĐT..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none w-40"
            />
          </div>
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
          {/* Lọc theo ngày — soát lại lead vừa thêm/vừa sửa đã nhập đúng & đủ chưa */}
          <span className="text-xs text-[var(--text-muted)] ml-2 mr-1">Ngày:</span>
          <select
            value={dateField}
            onChange={e => setDateField(e.target.value)}
            aria-label="Lọc theo mốc ngày"
            className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
          >
            {Object.entries(DATE_FIELDS).map(([key, f]) => (
              <option key={key} value={key}>{f.label}</option>
            ))}
          </select>
          <select
            value={datePreset}
            onChange={e => setDatePreset(e.target.value)}
            aria-label="Khoảng thời gian"
            className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
            style={datePreset !== 'all' ? { borderColor: 'rgba(201,169,110,0.5)', color: '#C9A96E' } : undefined}
          >
            {DATE_PRESETS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          {datePreset === 'custom' && (
            <div className="flex items-center gap-1">
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                aria-label="Từ ngày"
                className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
              />
              <span className="text-xs text-[var(--text-muted)]">→</span>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                aria-label="Đến ngày"
                className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none"
              />
            </div>
          )}
          <span className="text-xs text-[var(--text-muted)] ml-2 mr-1">Sắp xếp:</span>
          <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="newest">Mới nhất</option>
            <option value="updated">Cập nhật gần nhất</option>
            <option value="budget">Ngân sách cao → thấp</option>
            <option value="deal_value">Giá trị hợp đồng cao → thấp</option>
            <option value="ai_score">Điểm AI cao → thấp</option>
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
            <button onClick={clearFilters} className="text-[10px] px-2 py-1 rounded-lg ml-auto" style={{ background: 'rgba(248,113,113,0.1)', color: '#EF4444' }}>
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
        ) : viewMode === 'list' ? (
          /* ── List / Table View ── */
          <div className="glass-card overflow-hidden">
            {/* Mobile: mỗi lead một dòng gọn, bảng ngang không dùng được trên điện thoại */}
            <div className="md:hidden">
              {filteredByUrl.map(lead => (
                <div
                  key={lead.id}
                  onClick={() => openLeadDetail(lead)}
                  className="p-3 cursor-pointer active:bg-white/5 transition-colors"
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {lead.name}
                        {isOverdueLead(lead) && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 ml-1">⚠️ Quá hạn</span>}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5">📱 {lead.phone || '—'}</p>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold flex-shrink-0" style={{
                      background: `${STAGE_CONFIG[lead.stage]?.color}20`,
                      color: STAGE_CONFIG[lead.stage]?.color,
                    }}>
                      {STAGE_CONFIG[lead.stage]?.emoji} {STAGE_CONFIG[lead.stage]?.label || lead.stage}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-1.5 text-[10px] text-[var(--text-muted)]">
                    <span>{lead.assigned_user_name || 'Chưa phân công'}</span>
                    <span>{DATE_FIELDS[dateField]?.short}: {formatShortDate(DATE_FIELDS[dateField]?.pick(lead))}</span>
                    {lead.deal_value ? <span className="text-[#C9A96E] font-semibold">{formatDealValue(lead.deal_value)}</span> : null}
                  </div>
                </div>
              ))}
            </div>
            {/* Desktop: bảng cuộn ngang */}
            <div className="hidden md:block table-scroll">
              <table className="w-full text-sm min-w-[1180px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <PlainTh label="Khách hàng" />
                    <PlainTh label="Giai đoạn" />
                    <PlainTh label="Ưu tiên" />
                    <PlainTh label="Bất động sản" />
                    <SortableTh label="Ngân sách" sortKey="budget" sortBy={sortBy} setSortBy={setSortBy} align="right" />
                    <SortableTh label="Giá trị HĐ" sortKey="deal_value" sortBy={sortBy} setSortBy={setSortBy} align="right" />
                    <SortableTh label="AI" sortKey="ai_score" sortBy={sortBy} setSortBy={setSortBy} align="right" />
                    <PlainTh label="Nguồn" />
                    <PlainTh label="Phụ trách" />
                    <SortableTh label="Thêm mới" sortKey="newest" sortBy={sortBy} setSortBy={setSortBy} />
                    <SortableTh label="Cập nhật" sortKey="updated" sortBy={sortBy} setSortBy={setSortBy} />
                    <PlainTh label="Gọi" align="right" />
                  </tr>
                </thead>
                <tbody>
                  {filteredByUrl.map(lead => (
                    <tr
                      key={lead.id}
                      onClick={() => openLeadDetail(lead)}
                      className="cursor-pointer transition-colors hover:bg-white/5"
                      style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: PRIORITY_LABELS[lead.priority]?.color || '#6B7280' }} />
                          <div className="min-w-0">
                            <p className="font-medium text-[var(--text-primary)] truncate max-w-[180px]">
                              {lead.name}
                              {isOverdueLead(lead) && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium ml-1">⚠️ Quá hạn</span>
                              )}
                            </p>
                            <p className="text-xs text-[var(--text-muted)]">{lead.phone || '—'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[11px] px-2 py-1 rounded-full font-semibold whitespace-nowrap" style={{
                          background: `${STAGE_CONFIG[lead.stage]?.color}20`,
                          color: STAGE_CONFIG[lead.stage]?.color,
                        }}>
                          {STAGE_CONFIG[lead.stage]?.emoji} {STAGE_CONFIG[lead.stage]?.label || lead.stage}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap" style={{ color: PRIORITY_LABELS[lead.priority]?.color || 'var(--text-secondary)' }}>
                        {PRIORITY_LABELS[lead.priority]?.label || '—'}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] whitespace-nowrap">
                        {PROPERTY_LABELS[lead.property_type || ''] || lead.property_type || '—'}
                        {lead.area_sqm ? <span className="text-[var(--text-muted)]"> · {lead.area_sqm}m²</span> : null}
                      </td>
                      <td className="px-4 py-3 text-right text-[var(--text-secondary)] whitespace-nowrap">
                        {lead.estimated_budget ? formatCurrency(lead.estimated_budget) : '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-[#10B981] whitespace-nowrap">
                        {formatDealValue(lead.deal_value)}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        {lead.ai_score != null && lead.ai_score > 0 ? (
                          <span style={{ color: lead.ai_score >= 80 ? '#10B981' : lead.ai_score >= 60 ? '#F59E0B' : '#EF4444' }}>
                            {lead.ai_score}
                          </span>
                        ) : <span className="text-[var(--text-muted)]">—</span>}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] whitespace-nowrap">
                        {SOURCE_LABELS[lead.source || ''] || lead.source || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {lead.assigned_user_name
                          ? <span className="text-[var(--text-secondary)]">{lead.assigned_user_name}</span>
                          : <span style={{ color: '#F59E0B' }}>Chưa phân công</span>}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] whitespace-nowrap">{formatShortDate(lead.created_at)}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <p className="text-[var(--text-secondary)]">{formatShortDate(lead.updated_at)}</p>
                        <p className="text-[10px] text-[var(--text-muted)]">{timeAgo(lead.updated_at)}</p>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <a
                          href={lead.phone ? `tel:${lead.phone}` : undefined}
                          className="inline-flex items-center justify-center p-2 rounded-lg hover:bg-white/10 transition-colors text-[var(--text-muted)] hover:text-[#C9A96E]"
                          title={lead.phone ? `Gọi ${lead.phone}` : 'Chưa có SĐT'}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!lead.phone) { e.preventDefault(); return; }
                            api.createActivity(lead.id, { type: 'call', content: `📞 Gọi ${lead.phone} lúc ${new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}` })
                              .then(() => toast('Đang gọi + đã ghi nhận', 'success'))
                              .catch(() => {});
                          }}
                        >
                          <LineIcon name="phone" size={16} color="currentColor" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                              {lead.name?.split(' ')[0] || '—'}
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
          <div className="relative">
            <div className="flex gap-4 overflow-x-auto pb-4 min-w-0" style={{ maskImage: 'linear-gradient(to right, transparent 0px, black 12px, black calc(100% - 12px), transparent 100%)', WebkitMaskImage: 'linear-gradient(to right, transparent 0px, black 12px, black calc(100% - 12px), transparent 100%)' }}>
            {kanban.map(col => {
              const config = STAGE_CONFIG[col.stage];
              return (
                <div
                  key={col.stage}
                  className={cn('kanban-column flex-shrink-0 rounded-xl transition-colors', dragOverStage === col.stage && 'bg-white/5 ring-1 ring-[var(--gold-500)]')}
                  onDragOver={e => { e.preventDefault(); if (dragOverStage !== col.stage) setDragOverStage(col.stage); }}
                  onDragLeave={() => setDragOverStage(s => (s === col.stage ? null : s))}
                  onDrop={e => {
                    e.preventDefault();
                    setDragOverStage(null);
                    const leadId = e.dataTransfer.getData('text/lead-id');
                    const lead = leads.find(l => l.id === leadId);
                    if (!lead || lead.stage === col.stage) return;
                    // "Mất" bắt buộc có lý do → mở thẳng thẻ lead với ô chọn lý do bật sẵn.
                    if (col.stage === 'lost') { void openLeadDetail(lead, { lostPicker: true }); return; }
                    handleStageChange(lead, col.stage);
                  }}
                >
                  <div className="flex items-center gap-2 mb-3 px-1">
                    <div className="stage-dot" style={{ backgroundColor: config?.color }} />
                    <span className="text-sm font-medium">{config?.label}</span>
                    {col.stage === 'lost' && (
                      <span className="text-[10px] text-[var(--text-muted)]" title="Kéo thẻ vào đây sẽ mở ô chọn lý do mất lead">
                        (cần lý do)
                      </span>
                    )}
                    <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-white/10 text-[var(--text-secondary)]">
                      {col.leads.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {col.leads.map(lead => (
                      <div
                        key={lead.id}
                        draggable={lead.stage !== 'signed_design'}
                        onDragStart={e => { e.dataTransfer.setData('text/lead-id', lead.id); e.dataTransfer.effectAllowed = 'move'; }}
                        onClick={() => openLeadDetail(lead)}
                        title={lead.stage === 'signed_design' ? 'Deal đã thắng — đã tạo Khách hàng + Dự án, không kéo lùi được' : 'Kéo thả sang cột khác để đổi trạng thái'}
                        className={cn(
                          'glass-card p-3 border-l-2 cursor-pointer hover:bg-white/8 transition-all group',
                          lead.stage !== 'signed_design' && 'cursor-grab active:cursor-grabbing',
                          lead.priority === 'urgent' ? 'border-l-red-500' :
                          lead.priority === 'high' ? 'border-l-amber-500' :
                          lead.priority === 'medium' ? 'border-l-blue-500' : 'border-l-gray-500'
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <h3 className="text-sm font-medium text-white group-hover:text-[#C9A96E] transition-colors">
                            {lead.name}
                            {isOverdueLead(lead) && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium ml-1">
                                ⚠️ Quá hạn
                              </span>
                            )}
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
                        {lead.last_contacted_at && (
                          <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                            🕐 {timeAgo(lead.last_contacted_at)}
                          </p>
                        )}
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
                          <div className="flex items-center gap-1">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                              {SOURCE_LABELS[lead.source || ''] || lead.source || '—'}
                            </span>
                            {/* Quick stage change */}
                            <select
                              className="text-[9px] px-1 py-0.5 rounded bg-white/5 border border-white/10 text-[var(--text-muted)] max-w-[80px] truncate cursor-pointer"
                              value={lead.stage}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                e.stopPropagation();
                                const newStage = e.target.value;
                                if (newStage === 'lost') {
                                  // Mở thẻ chi tiết kèm ô chọn lý do — đổi thẳng sẽ bị chặn.
                                  void openLeadDetail(lead, { lostPicker: true });
                                } else {
                                  handleStageChange(lead, newStage);
                                }
                              }}
                            >
                              {/* Lead ở giai đoạn ngoài bảng (vd "Ngủ đông") vẫn phải có option
                                  của chính nó, không thì ô select hiện trống. */}
                              {(BOARD_STAGES.includes(lead.stage) ? BOARD_STAGES : [...BOARD_STAGES, lead.stage]).map(s => (
                                <option key={s} value={s}>{STAGE_CONFIG[s]?.label || s}</option>
                              ))}
                            </select>
                            <a
                              href={lead.phone ? `tel:${lead.phone}` : undefined}
                              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-[var(--text-muted)] hover:text-[#C9A96E] min-w-[36px] min-h-[36px] flex items-center justify-center"
                              title={lead.phone ? `Gọi ${lead.phone}` : 'Chưa có SĐT'}
                              onClick={(e) => {
                                e.stopPropagation();
                                if (!lead.phone) { e.preventDefault(); return; }
                                // Bấm là GỌI THẬT (tel:) + tự ghi nhận cuộc gọi (spec 08 §2.1)
                                api.createActivity(lead.id, { type: 'call', content: `📞 Gọi ${lead.phone} lúc ${new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}` })
                                  .then(() => toast('Đang gọi + đã ghi nhận', 'success'))
                                  .catch(() => {});
                              }}
                            >
                              <LineIcon name="phone" size={16} color="currentColor" />
                            </a>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            </div>
          </div>
        )}
      </div>

      {/* ── Lead Detail Modal ── */}
      {selectedLead && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]"
          onClick={closeLeadDetail}
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
                  <span className="text-lg font-bold text-white">{selectedLead.name?.charAt(0) || '?'}</span>
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">{selectedLead.name}</h2>
                  <p className="text-xs text-[var(--text-muted)]">{selectedLead.contact_person || selectedLead.name}</p>
                </div>
              </div>
              <button
                onClick={closeLeadDetail}
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
                  {/* Phụ trách — LUÔN hiển thị; admin/leader gắn/đổi nhân viên KD ngay tại đây */}
                  <div className="flex items-center gap-2 flex-wrap sm:col-span-2">
                    <span className="text-[var(--text-muted)]">👤</span>
                    <span className="text-[var(--text-secondary)]">
                      Phụ trách:{' '}
                      {selectedLead.assigned_user_name ? (
                        <span className="text-white font-medium">{selectedLead.assigned_user_name}</span>
                      ) : (
                        <span style={{ color: '#F59E0B' }}>Chưa phân công</span>
                      )}
                    </span>
                    {canAssign && (
                      assignOpen ? (
                        <div className="flex items-center gap-1.5">
                          <select
                            value={selectedLead.assigned_to || ''}
                            disabled={assigning || loadingUsers}
                            onChange={e => handleAssign(e.target.value)}
                            className="min-w-0 text-xs px-2 py-1 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none max-w-[180px] disabled:opacity-50"
                          >
                            <option value="" disabled>{loadingUsers ? 'Đang tải...' : '— Chọn nhân viên —'}</option>
                            {/* Người phụ trách hiện tại ngoài danh sách ứng viên (inactive/role khác) — giữ option ẩn để select không trống */}
                            {selectedLead.assigned_to && !assignableUsers.some(u => u.id === selectedLead.assigned_to) && (
                              <option value={selectedLead.assigned_to} hidden>{selectedLead.assigned_user_name || 'Người hiện tại'}</option>
                            )}
                            {assignableUsers.map(u => (
                              <option key={u.id} value={u.id}>{u.full_name}</option>
                            ))}
                          </select>
                          <button
                            onClick={() => setAssignOpen(false)}
                            disabled={assigning}
                            className="flex-shrink-0 text-[11px] px-2 py-1 rounded-lg text-[var(--text-muted)] hover:bg-white/10 transition-all disabled:opacity-50"
                          >
                            {assigning ? 'Đang lưu...' : 'Hủy'}
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={openAssign}
                          className="text-[11px] px-2 py-1 rounded-lg font-medium transition-all hover:opacity-80"
                          style={{ background: 'rgba(201,169,110,0.15)', color: '#C9A96E', border: '1px solid rgba(201,169,110,0.3)' }}
                        >
                          ✏️ Đổi
                        </button>
                      )
                    )}
                  </div>
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
                    <p className="text-xs text-[var(--text-muted)]">Giá trị hợp đồng</p>
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

              {/* ── Gợi ý AI (Sales Co-Pilot) ── */}
              {/* Có bộ nhớ: gợi ý nào sale đã "Đã làm"/"Bỏ qua" thì lượt sau không nhắc lại */}
              <div className="glass-card p-4">
                <div className="flex items-center justify-between mb-3 gap-2">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                    🤖 Gợi ý AI
                  </h3>
                  <button
                    onClick={xinGoiY}
                    disabled={dangXinGoiY}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 disabled:opacity-40 transition-all min-h-[36px]"
                  >
                    {dangXinGoiY ? 'Đang nghĩ...' : goiY ? 'Xin gợi ý khác' : 'Xin gợi ý'}
                  </button>
                </div>

                {goiY ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{
                          background: `${PRIORITY_LABELS[goiY.priority]?.color || 'var(--info)'}20`,
                          color: PRIORITY_LABELS[goiY.priority]?.color || 'var(--info)',
                        }}
                      >
                        {PRIORITY_LABELS[goiY.priority]?.label || goiY.priority}
                      </span>
                      {/* Nói thẳng bản này do đâu ra, khỏi ai tưởng bộ luật là AI */}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-[var(--text-muted)] border border-white/10">
                        {goiY.source === 'llm' ? 'AI viết' : 'Theo bộ luật'}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-white">{goiY.action}</p>
                    <p className="text-xs text-[var(--text-secondary)]">{goiY.reason}</p>
                    {goiY.message_template && (
                      <div className="p-3 rounded-lg text-xs text-[var(--text-secondary)] whitespace-pre-wrap" style={{ background: 'var(--surface-2)' }}>
                        <p className="text-[10px] text-[var(--text-muted)] mb-1">💬 Mẫu tin nhắn:</p>
                        {goiY.message_template}
                      </div>
                    )}
                    {goiY.run_id && (
                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => ghiNhanGoiY('done')}
                          disabled={dangGhiNhan}
                          className="flex-1 px-3 py-2 rounded-lg text-xs font-medium bg-[#10B981]/15 text-[#10B981] hover:bg-[#10B981]/25 disabled:opacity-40 transition-all min-h-[36px]"
                        >
                          ✅ Đã làm
                        </button>
                        <button
                          onClick={() => ghiNhanGoiY('skipped')}
                          disabled={dangGhiNhan}
                          className="flex-1 px-3 py-2 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] border border-white/10 hover:border-[#C9A96E] hover:text-[#C9A96E] disabled:opacity-40 transition-all min-h-[36px]"
                        >
                          ⏭️ Bỏ qua
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">
                    Bấm “Xin gợi ý” để Co-Pilot đề xuất việc nên làm tiếp với khách này.
                  </p>
                )}

                {lichSuGoiY.length > 0 && (
                  <div className="mt-3 pt-3 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
                    <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide">
                      Đã gợi ý trước đó ({lichSuGoiY.length})
                    </p>
                    {lichSuGoiY.map(ls => (
                      <div key={ls.run_id} className="flex items-start gap-2 text-xs">
                        <span className="flex-shrink-0">
                          {ls.outcome === 'done' ? '✅' : ls.outcome === 'skipped' ? '⏭️' : '⏳'}
                        </span>
                        <div className="flex-1">
                          <p className="text-[var(--text-secondary)]">{ls.action}</p>
                          <p className="text-[10px] text-[var(--text-muted)]">
                            {ls.outcome === 'done' ? 'Đã làm' : ls.outcome === 'skipped' ? 'Bỏ qua' : 'Chưa phản hồi'}
                            {ls.created_at && ` · ${new Date(ls.created_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* ── CSKH — đánh giá chất lượng chăm sóc của team KD ── */}
              {/* Lognote: mỗi lần Admin CSKH gọi lại khách là một mục mới có ngày giờ
                  + tên người nhập. Ai xem được lead đều ĐỌC được; chỉ CSKH/admin ghi. */}
              <div className="glass-card p-4">
                <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                    🎧 CSKH — Đánh giá chất lượng chăm sóc ({cskhNotes.length})
                  </h3>
                  {cskhNotes[0] && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      Cập nhật gần nhất: {formatDateTime(cskhNotes[0].created_at)}
                    </span>
                  )}
                </div>

                {canWriteCskh ? (
                  <div className="space-y-2">
                    <textarea
                      value={newCskhNote}
                      onChange={e => setNewCskhNote(e.target.value)}
                      rows={3}
                      placeholder="Gọi lại khách để đánh giá chất lượng chăm sóc của team KD. VD: Khách khen bạn Mai tư vấn nhiệt tình, nhưng phàn nàn 3 ngày chưa nhận được báo giá."
                      className="w-full px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-[#C9A96E] resize-y"
                    />
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[10px] text-[var(--text-muted)]">
                        Mục đã lưu không sửa/xóa được — hệ thống tự đóng dấu ngày giờ và tên bạn.
                      </p>
                      <button
                        onClick={handleAddCskhNote}
                        disabled={!newCskhNote.trim() || savingCskh}
                        className="flex-shrink-0 px-3 py-2 rounded-lg text-xs font-medium bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 disabled:opacity-30 transition-all min-h-[36px]"
                      >
                        {savingCskh ? 'Đang lưu...' : 'Lưu đánh giá'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">
                    Chỉ Admin CSKH và quản trị viên ghi được mục mới. Bạn vẫn xem đầy đủ các đánh giá bên dưới.
                  </p>
                )}

                {loadingActivities ? (
                  <div className="text-center py-4 text-sm text-[var(--text-muted)]">Đang tải...</div>
                ) : cskhNotes.length === 0 ? (
                  <p className="text-xs text-[var(--text-muted)] mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                    Chưa có đánh giá CSKH nào cho khách này.
                  </p>
                ) : (
                  <div className="mt-3 pt-3 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
                    {cskhNotes.map(note => (
                      <div key={note.id} className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">{note.content}</p>
                        <p className="text-[10px] text-[var(--text-muted)] mt-1.5">
                          🎧 {note.user_name || 'Admin CSKH'} · {formatDateTime(note.created_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Activity Timeline */}
              <div className="glass-card p-4">
                <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                  Lịch sử hoạt động ({timelineActivities.length})
                </h3>
                {loadingActivities ? (
                  <div className="text-center py-4 text-sm text-[var(--text-muted)]">Đang tải...</div>
                ) : timelineActivities.length === 0 ? (
                  <div className="text-center py-4 text-sm text-[var(--text-muted)]">Chưa có hoạt động</div>
                ) : (
                  <div className="space-y-3">
                    {[...timelineActivities].reverse().map((act, i) => (
                      <div key={act.id || i} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <span className="text-sm">{ACTIVITY_ICONS[act.type] || '📌'}</span>
                          {i < timelineActivities.length - 1 && (
                            <div className="w-px flex-1 mt-1" style={{ background: 'var(--border-subtle)' }} />
                          )}
                        </div>
                        <div className="flex-1 pb-3">
                          <div className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">
                            {(act.content || '').split('\n').map((line, li) => {
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
                              return <span key={li}>{line}{li < (act.content || '').split('\n').length - 1 && <br />}</span>;
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
                  {/* Chip ghi chú 1 chạm — sales trên xe ngại gõ dấu (spec 08 §2.1, H8) */}
                  <div className="flex gap-1.5 flex-wrap">
                    {['📵 Không nghe máy', '🔁 Hẹn gọi lại', '📤 Đã gửi báo giá', '📅 Hẹn khảo sát'].map(chip => (
                      <button
                        key={chip}
                        onClick={async () => {
                          if (!selectedLead) return;
                          try {
                            await api.createActivity(selectedLead.id, { type: 'call', content: chip });
                            const acts = await api.getActivities(selectedLead.id);
                            setActivities(acts);
                            toast('Đã ghi nhận', 'success');
                          } catch { toast('Lỗi khi ghi nhận', 'error'); }
                        }}
                        className="px-2.5 py-1.5 rounded-full text-xs font-medium transition-all min-h-[36px] bg-white/5 border border-white/10 text-[var(--text-secondary)] hover:border-[#C9A96E] hover:text-[#C9A96E]"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
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

              {/* Lost Reason (shown when stage is lost) */}
              {selectedLead.stage === 'lost' && selectedLead.lost_reason && (
                <div className="glass-card p-4">
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Lý do mất lead</h3>
                  <p className="text-sm text-red-400">{selectedLead.lost_reason}</p>
                </div>
              )}

              {/* Stage Actions */}
              <div className="glass-card p-4" ref={lostPickerRef}>
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
                {/* Lost reason selector — visible before confirming lost */}
                {selectedLead.stage !== 'lost' && (
                  <LostReasonSelector
                    isOpen={lostPickerOpen}
                    setIsOpen={setLostPickerOpen}
                    onConfirm={(reason) => {
                      handleStageChange(selectedLead, 'lost', reason);
                    }}
                    onCancel={() => {}}
                  />
                )}
              </div>

              {/* Timestamps */}
              <div className="flex justify-between text-[10px] text-[var(--text-disabled)] pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <span>Tạo: {new Date(selectedLead.created_at).toLocaleDateString('vi-VN')}</span>
                <span>Cập nhật: {new Date(selectedLead.updated_at).toLocaleDateString('vi-VN')}</span>
                <span>Liên hệ: {selectedLead.last_contacted_at ? timeAgo(selectedLead.last_contacted_at) : 'Chưa'}</span>
                {selectedLead.lost_reason && <span className="text-red-400">Mất: {selectedLead.lost_reason}</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Lead Modal */}
      <CreateLeadModal isOpen={createOpen} onClose={() => { setCreateOpen(false); fetchLeads(); }} canAssign={canAssign} />
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
