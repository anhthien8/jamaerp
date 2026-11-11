'use client';

import dynamic from 'next/dynamic';
import MoneyInput from '@/components/ui/MoneyInput';
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import LineIcon from '@/components/ui/LineIcon';
import { STAGE_CONFIG, cn, formatCurrency, formatDealValue, timeAgo, tuyChonKhuVuc } from '@/lib/utils';
import KhaoSatThang from '@/components/leads/KhaoSatThang';
import ThanhThaoTacHangLoat from '@/components/leads/ThanhThaoTacHangLoat';
import BangKanbanLead from '@/components/leads/BangKanbanLead';
import { DATE_PRESETS, dayKey, formatDayKey, resolveDateRange, toDayKey } from '@/lib/date-filter';
import { useToast } from '@/components/ui/Toast';
import CreateLeadModal from '@/components/ui/CreateLeadModal';
import { blobThanhDataUrl, nenAnh } from '@/lib/anh';
import { ALL_STAGES, BOARD_STAGES, KANBAN_PAGE_SIZE, PRIORITY_LABELS, PROPERTY_LABELS, SOURCE_LABELS, isOverdueLead } from '@/components/leads/shared';
import { api, Lead, Activity, User, AISuggestion, AISuggestionHistory, fetchAllPages } from '@/lib/api';
import { canAssignLeads, canWriteCskhNote, isSalesCoordinator, phamViDuLieu } from '@/lib/roles';

const ChiTietLead = dynamic(() => import('@/components/leads/ChiTietLead'), { ssr: false });

// Lognote CSKH — khớp CSKH_ACTIVITY_TYPE backend. Lưu chung bảng activities nên
// mỗi mục tự có ngày giờ + tên người nhập; render ở khối riêng, tách khỏi timeline
// chung để đánh giá chất lượng không bị trôi lẫn giữa hàng chục cuộc gọi.
const CSKH_TYPE = 'cskh';

// ── Lọc theo ngày (double-check lead nhập đúng/đủ) ──────────────────────────
// Backend trả ISO KHÔNG kèm timezone (cột DateTime naive) nên new Date() đọc theo
// giờ máy — đúng bằng cách timeAgo/toLocaleString đang hiển thị ở mọi trang khác.
const DATE_FIELDS: Record<string, { label: string; short: string; pick: (l: Lead) => string | undefined }> = {
  created_at: { label: 'Ngày thêm mới', short: 'Thêm mới', pick: l => l.created_at },
  updated_at: { label: 'Ngày cập nhật', short: 'Cập nhật', pick: l => l.updated_at },
  last_contacted_at: { label: 'Ngày liên hệ cuối', short: 'Liên hệ cuối', pick: l => l.last_contacted_at },
  // 10/11/2026: lọc khách đã khảo sát trong tháng theo NVKD (kèm ô «Phụ trách»)
  survey_date: { label: 'Ngày khảo sát', short: 'Khảo sát', pick: l => l.survey_date ?? undefined },
};
type SortKey = 'newest' | 'updated' | 'budget' | 'ai_score' | 'deal_value';

function getLeadTimestamp(lead: Lead) {
  return lead.last_contacted_at || lead.updated_at || lead.created_at;
}

function formatShortDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('vi-VN');
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

function LeadsContent() {

  const { user, loading, effectivePermissions } = useAuth();
  const router = useRouter();
  const perms = effectivePermissions;
  // Admin/leader/điều phối KD (CSKH) được gắn/đổi người phụ trách — khớp can_assign_leads() backend.
  const canAssign = canAssignLeads(user);

  // Bulk assign — chọn nhiều lead ở view danh sách rồi giao 1 lượt (POST /leads/bulk/assign
  // + /bulk/stage đã có BE từ Phiên 14/07, FE chưa từng có UI). Backend tự bỏ qua lead
  // ngoài phạm vi người gán (trưởng nhóm chỉ giao lead nhóm mình), trả {updated, skipped}.
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(() => new Set());
  const [bulkAssignOpen, setBulkAssignOpen] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const toggleSelectLead = (id: string) => {
    setSelectedLeadIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const toggleSelectAllVisible = () => {
    setSelectedLeadIds(prev => {
      const visible = filteredByUrl.map(l => l.id);
      const allSelected = visible.length > 0 && visible.every(id => prev.has(id));
      const next = new Set(prev);
      if (allSelected) visible.forEach(id => next.delete(id));
      else visible.forEach(id => next.add(id));
      return next;
    });
  };
  const handleBulkAssign = async (userId: string) => {
    if (selectedLeadIds.size === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.bulkAssignLeads([...selectedLeadIds], userId);
      toast(`Đã giao ${res.updated} lead${res.skipped ? ` (bỏ qua ${res.skipped} ngoài phạm vi)` : ''}`, 'success');
      setSelectedLeadIds(new Set());
      setBulkAssignOpen(false);
      fetchLeads();
    } catch (e) {
      toast(`Lỗi giao hàng loạt: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      setBulkBusy(false);
    }
  };
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  // Kéo thả kanban (feedback beta 22/07) — cột đang được kéo qua để highlight
  const [dragOverStage, setDragOverStage] = useState<string | null>(null);
  // ── Thanh trượt ngang thứ 2 đặt TRÊN bảng kanban ──────────────────────────
  // Hai khối cuộn soi gương nhau: kéo cái nào thì cái kia đi theo. Cờ `dangDongBo`
  // chặn vòng lặp vô tận (set scrollLeft lại bắn onScroll của bên kia).
  const boardRef = useRef<HTMLDivElement | null>(null);
  const topScrollRef = useRef<HTMLDivElement>(null);
  const spacerRef = useRef<HTMLDivElement>(null);
  const dangDongBo = useRef(false);
  const goRoiTheoDoi = useRef<(() => void) | null>(null);

  // Gắn bằng CALLBACK REF, không phải useEffect: bảng kanban chỉ mount SAU khi lead
  // tải xong (lượt render đầu còn ở nhánh "Đang tải"), nên effect theo [viewMode]
  // chạy lúc boardRef còn null rồi không bao giờ chạy lại → thanh trượt rộng sai.
  const ganBang = useCallback((node: HTMLDivElement | null) => {
    goRoiTheoDoi.current?.();
    goRoiTheoDoi.current = null;
    boardRef.current = node;
    if (!node) return;
    const dongBoRong = () => {
      if (spacerRef.current) spacerRef.current.style.width = `${node.scrollWidth}px`;
    };
    dongBoRong();
    const ro = new ResizeObserver(dongBoRong);   // đổi kích thước cửa sổ
    ro.observe(node);
    const mo = new MutationObserver(dongBoRong); // thêm/bớt cột do đổi bộ lọc
    mo.observe(node, { childList: true });
    goRoiTheoDoi.current = () => { ro.disconnect(); mo.disconnect(); };
  }, []);

  const onBoardScroll = useCallback(() => {
    if (dangDongBo.current || !boardRef.current || !topScrollRef.current) return;
    dangDongBo.current = true;
    topScrollRef.current.scrollLeft = boardRef.current.scrollLeft;
    requestAnimationFrame(() => { dangDongBo.current = false; });
  }, []);

  const onTopScroll = useCallback(() => {
    if (dangDongBo.current || !boardRef.current || !topScrollRef.current) return;
    dangDongBo.current = true;
    boardRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    requestAnimationFrame(() => { dangDongBo.current = false; });
  }, []);

  // Ô chọn lý do mất lead trong thẻ chi tiết — bật sẵn khi user kéo vào cột "Mất".
  const [lostPickerOpen, setLostPickerOpen] = useState(false);
  const lostPickerRef = useRef<HTMLDivElement | null>(null);
  // Ngày khảo sát (10/11/2026) — sửa ngay trong khung chi tiết lead.
  const [savingSurvey, setSavingSurvey] = useState(false);
  const handleSurveyDate = async (value: string) => {
    if (!selectedLead || savingSurvey) return;
    const leadId = selectedLead.id;
    setSavingSurvey(true);
    try {
      const updated = await api.updateLead(leadId, { survey_date: value || null });
      const applyPatch = (l: Lead): Lead => ({ ...l, survey_date: updated.survey_date ?? null });
      setSelectedLead(prev => (prev && prev.id === leadId ? applyPatch(prev) : prev));
      setLeads(prev => prev.map(l => (l.id === leadId ? applyPatch(l) : l)));
      toast(value ? 'Đã lưu ngày khảo sát' : 'Đã xoá ngày khảo sát', 'success');
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không lưu được ngày khảo sát'}`, 'error');
    } finally {
      setSavingSurvey(false);
    }
  };

  // ── Bulk stage: đổi giai đoạn hàng loạt (POST /leads/bulk/stage) ──
  // Backend chặn signed_design (side-effect sinh KH+Dự án phải chạy từng lead)
  // và bắt lý do khi vào «Mất» — FE lặp lại 2 luật đó cho chọn trước khi gọi.
  const [bulkStageOpen, setBulkStageOpen] = useState(false);
  const [bulkStageValue, setBulkStageValue] = useState('');
  const [dormantReason, setDormantReason] = useState('');
  const [bulkLostReason, setBulkLostReason] = useState('');
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loadingLeads, setLoadingLeads] = useState(true);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [filterRegion, setFilterRegion] = useState<string>('all');
  // Lọc theo nhân viên KD phụ trách. Danh sách dựng TỪ CHÍNH lead đang tải nên
  // không cần gọi thêm API (sale thường bị 403 ở /users/assignable) và chỉ liệt
  // kê người thực sự đang giữ data trong phạm vi mình xem được.
  const [filterAssignee, setFilterAssignee] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortKey>('newest');
  // Lọc theo ngày tạo/cập nhật/liên hệ — để soát lại lead vừa nhập đã đúng & đủ chưa.
  // Mặc định «Ngày thêm mới»: sale nghĩ theo ngày NHẬN lead, không phải ngày hệ thống sửa bản ghi.
  const [dateField, setDateField] = useState<string>('created_at');
  const [datePreset, setDatePreset] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [newNote, setNewNote] = useState('');
  // Ảnh chờ gửi kèm ghi chú (thay ô dán link Drive, 23/10/2026) — đã nén ≤1600px
  const [anhCho, setAnhCho] = useState<string[]>([]);
  const [dangGuiNote, setDangGuiNote] = useState(false);
  const chonAnhRef = useRef<HTMLInputElement>(null);
  // Lognote CSKH — chỉ Admin CSKH + admin nhập được (backend chặn 403 vai trò khác).
  const [newCskhNote, setNewCskhNote] = useState('');
  const [savingCskh, setSavingCskh] = useState(false);
  const canWriteCskh = canWriteCskhNote(user);
  const [viewMode, setViewMode] = useState<'kanban' | 'list' | 'calendar'>('kanban');
  const [error, setError] = useState<string | null>(null);
  const [calendarDate, setCalendarDate] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [searchQuery, setSearchQuery] = useState('');
  // Số thẻ đang vẽ mỗi cột kanban (thiếu key = KANBAN_PAGE_SIZE). Chỉ giới hạn RENDER,
  // không đụng dữ liệu: header cột và shownCount vẫn đếm đủ.
  const [kanbanVisible, setKanbanVisible] = useState<Record<string, number>>({});
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
      // Phạm vi phía trình duyệt PHẢI soi gương _loc_pham_vi_lead() backend.
      // `leadsScope` không nằm trong ma trận checkbox của vai trò tùy chỉnh (mọi
      // vai trò custom thừa kế 'own' của data_entry), nên bản cũ NÉM BỎ chính số
      // lead backend đã trả đúng. Đây đúng là lỗi user báo với tài khoản Nguyễn
      // Văn Toàn: backend trả 467 lead cả phòng KD, frontend cắt lại còn 141 của
      // đội anh vì `isTeamLead('leader')` ép về 'team' (sửa 22/09).
      const pv = isSalesCoordinator(user?.role, user?.department) ? 'tat_ca' : phamViDuLieu(user);
      let filtered = allLeads;
      if (pv === 'ca_nhan') {
        // Nhân viên: chỉ lead của mình. Nếu vai trò của họ vốn 'all'/'team' theo
        // ma trận thì tôn trọng ma trận, không siết thêm.
        if (perms.leadsScope === 'own') {
          filtered = allLeads.filter(l => l.assigned_to === user?.id);
        }
      } else if (pv === 'nhom') {
        filtered = allLeads.filter(l =>
          (!!user?.team_id && l.team_id === user.team_id) || l.assigned_to === user?.id
        );
      }
      // pv === 'phong_ban' | 'tat_ca': backend đã lọc đúng phạm vi, KHÔNG cắt thêm.
      // Apply client-side filters for region and property_class
      if (filterRegion !== 'all') {
        filtered = filtered.filter(l => l.region === filterRegion);
      }
      setLeads(filtered);
    } catch (e) {
      console.warn('API error, using empty list:', e);
      setError('Không thể tải dữ liệu. Vui lòng thử lại.');
      setLeads([]);
    } finally {
      setLoadingLeads(false);
    }
  }, [filterSource, filterPriority, filterRegion, perms.leadsScope, user, user?.id, user?.team_id, user?.role, user?.department]);

  useEffect(() => {
    if (user) void Promise.resolve().then(fetchLeads);
  }, [user, fetchLeads]);

  // Đổi bộ lọc / từ khóa / sắp xếp / cột đang xem → cụp mọi cột về trang đầu:
  // tập thẻ và thứ tự đã khác, giữ trạng thái «đã hiện thêm» cũ chỉ gây rối.
  // Chỉnh NGAY TRONG RENDER theo "chữ ký bộ lọc" thay vì useEffect — setState đồng
  // bộ trong effect gây render thác (react-hooks/set-state-in-effect) và làm cột
  // nhấp nháy một nhịp ở tập thẻ cũ trước khi cụp.
  const filterSig = [
    searchQuery, filterSource, filterPriority, filterRegion,
    filterAssignee, dateField, datePreset, dateFrom, dateTo, sortBy,
    activeStage, activeQuickFilter,
  ].join('|');
  const [prevFilterSig, setPrevFilterSig] = useState(filterSig);
  if (prevFilterSig !== filterSig) {
    setPrevFilterSig(filterSig);
    setKanbanVisible({});
  }

  const openLeadDetail = async (lead: Lead, options?: { lostPicker?: boolean }) => {
    setSelectedLead(lead);
    // Ô ghi chú luôn sạch khi mở thẻ mới (tránh sót nội dung của lead trước).
    setNewNote('');
    setAnhCho([]);
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
    setAnhCho([]);
    setNewCskhNote('');
    setAssignOpen(false);
    setLostPickerOpen(false);
    setGoiY(null);
    setLichSuGoiY([]);
    // setter ổn định — liệt kê vì React Compiler không suy ra được khi setter được truyền xuống ChiTietLead
  }, [setNewNote, setAnhCho, setNewCskhNote, setAssignOpen, setLostPickerOpen]);

  // Mở thẳng thẻ lead từ link thông báo (/leads?id=…). Đọc xong thì gỡ `id`
  // khỏi URL để bấm lại cùng thông báo vẫn mở được, và đóng thẻ không bật lại.
  const urlLeadId = searchParams.get('id');
  useEffect(() => {
    if (!urlLeadId || loadingLeads) return;
    const conLai = new URLSearchParams(searchParams.toString());
    conLai.delete('id');
    router.replace(conLai.toString() ? `/leads?${conLai}` : '/leads', { scroll: false });
    const coSan = leads.find(l => l.id === urlLeadId);
    if (coSan) { void Promise.resolve().then(() => openLeadDetail(coSan)); return; }
    api.getLead(urlLeadId)
      .then(l => openLeadDetail({
        ...l,
        tags: typeof l.tags === 'string' ? (() => { try { return JSON.parse(l.tags as unknown as string); } catch { return []; } })() : l.tags || [],
      }))
      .catch(() => toast('Không mở được lead này (đã xoá hoặc ngoài phạm vi của bạn)', 'error'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlLeadId, loadingLeads]);

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

  const themAnhCho = async (files: Iterable<File>) => {
    const ds = [...files].filter(f => f.type.startsWith('image/'));
    if (!ds.length) return;
    const conCho = 6 - anhCho.length;
    if (conCho <= 0) { toast('Tối đa 6 ảnh mỗi ghi chú', 'error'); return; }
    const moi: string[] = [];
    for (const f of ds.slice(0, conCho)) {
      const nen = await nenAnh(f);
      if (!nen) { toast(`Không đọc được ảnh «${f.name}» — ảnh HEIC hãy đổi sang JPG`, 'error'); continue; }
      moi.push(await blobThanhDataUrl(nen));
    }
    if (ds.length > conCho) toast('Tối đa 6 ảnh mỗi ghi chú', 'error');
    setAnhCho(prev => [...prev, ...moi]);
  };

  const handleAddNote = async () => {
    if (!selectedLead || dangGuiNote || (!newNote.trim() && !anhCho.length)) return;
    setDangGuiNote(true);
    try {
      const ids: string[] = [];
      for (const dataUrl of anhCho) {
        ids.push((await api.uploadLeadImage(selectedLead.id, dataUrl)).id);
      }
      const content = [newNote.trim(), ...ids.map(id => `🖼 anh:${id}`)].filter(Boolean).join('\n');
      await api.createActivity(selectedLead.id, { type: 'note', content });
      const acts = await api.getActivities(selectedLead.id);
      setActivities(acts);
      setNewNote('');
      setAnhCho([]);
      toast(ids.length ? `Đã thêm ghi chú kèm ${ids.length} ảnh` : 'Đã thêm ghi chú', 'success');
    } catch (e: unknown) {
      toast((e as Error).message || 'Lỗi khi thêm ghi chú', 'error');
    }
    setDangGuiNote(false);
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

  // Hộp xác nhận «Deal đã thắng» — chuyển sang signed_design tự sinh KH+HĐ+19 tasks
  // và KHÔNG lùi được (QC 05/09: kéo nhầm là mất công dọn dữ liệu). Trước đây bắn
  // thẳng API không hỏi.
  const [signedConfirmOpen, setSignedConfirmOpen] = useState(false);
  const [signedTarget, setSignedTarget] = useState<Lead | null>(null);
  const [signedValue, setSignedValue] = useState('');

  const handleStageChange = async (lead: Lead, newStage: string, reasonOverride?: string) => {
    if (newStage === 'lost' && !reasonOverride) {
      toast('Vui lòng chọn lý do mất lead', 'error');
      return;
    }
    // Cửa chặn duy nhất: mọi đường vào signed_design (nút trong thẻ, kéo thả kanban)
    // đều phải qua hộp xác nhận. Hủy = không gọi API.
    if (newStage === 'signed_design' && lead.stage !== 'signed_design') {
      setSignedTarget(lead);
      setSignedValue(lead.design_contract_value ? String(lead.design_contract_value) : '');
      setSignedConfirmOpen(true);
      return;
    }
    // Đang có 1 lượt đổi stage chạy dở → bỏ qua lượt thứ 2 (chặn tạo trùng KH+Dự án).
    await doStageChange(lead, newStage, { reason: reasonOverride });
  };

  // Thân thật của việc đổi giai đoạn — confirm dialog signed_design gọi thẳng vào
  // đây (đi lại handleStageChange sẽ bị hộp xác nhận chặn lần nữa, vòng lặp).
  const doStageChange = async (lead: Lead, newStage: string, opts?: { reason?: string; contractValue?: number }) => {
    if (stageBusy.current) return;
    stageBusy.current = true;
    try {
      // Mọi chuyển giai đoạn (kể cả sang "Mất") đi qua đúng một cửa /stage.
      // Bản cũ dùng updateLead cho nhánh "Mất" — endpoint đó KHÔNG nhận stage nên
      // trả 200 mà lead nằm nguyên cột cũ, user tưởng đã chuyển xong (lỗi 27/08).
      await api.changeStage(lead.id, newStage, {
        lostReason: newStage === 'lost' ? opts?.reason : undefined,
        designContractValue: opts?.contractValue,
        note: newStage === 'dormant' ? (opts?.reason ? `Ngủ đông: ${opts.reason}` : undefined) : undefined,
      });
      toast(`Chuyển ${lead.name} sang ${STAGE_CONFIG[newStage]?.label || newStage}`, 'success');
      // Sort «Mới nhất» xếp lead cũ rất sâu: thẻ vừa chuyển vào cột đông có thể
      // nằm ngoài 25 thẻ đầu → thẻ «biến mất», sale tưởng chuyển hụt. Nới cửa sổ
      // cột đích đủ rộng để thẻ chắc chắn hiện ra; muốn gọn đã có nút «Thu gọn».
      setKanbanVisible(prev => ({
        ...prev,
        [newStage]: Math.max(prev[newStage] ?? KANBAN_PAGE_SIZE, leads.filter(l => l.stage === newStage).length + 1),
      }));
      fetchLeads();
      closeLeadDetail();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Unknown'}`, 'error');
    } finally {
      stageBusy.current = false;
    }
  };

  // Nạp ứng viên phụ trách 1 lần rồi cache (bộ lọc dùng chung nằm ở api.getAssignableSales).
  // Danh sách tỉnh/thành cho ô lọc — gói useMemo vì nó quét toàn bộ lead (619
  // bản ghi trên prod) để nhặt các giá trị cũ; để trong JSX là tính lại mỗi render.
  const danhSachKhuVuc = useMemo(() => tuyChonKhuVuc(leads.map(l => l.region)), [leads]);

  const loadAssignableUsers = async () => {
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
  };

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

  // ── Bulk stage: đổi giai đoạn hàng loạt cho các lead đang chọn (view danh sách) ──
  // Backend chặn signed_design (side-effect sinh KH+Dự án phải chạy từng lead) và
  // bắt lý do khi vào «Mất» — FE lặp lại 2 luật đó để chọn trước khi gọi API.
  const runBulkStage = async () => {
    if (!bulkStageValue || bulkBusy || selectedLeadIds.size === 0) return;
    if (bulkStageValue === 'lost' && !bulkLostReason.trim()) {
      toast('Chọn lý do mất lead trước', 'error');
      return;
    }
    if (bulkStageValue === 'signed_design') return; // đã chặn ở UI, đề phòng gọi tay
    setBulkBusy(true);
    try {
      const res = await api.bulkChangeStage(
        [...selectedLeadIds], bulkStageValue,
        bulkStageValue === 'lost' ? bulkLostReason.trim() : undefined,
      );
      toast(`Đã chuyển ${res.updated} lead${res.skipped ? ` (bỏ qua ${res.skipped} ngoài phạm vi)` : ''}`, res.updated ? 'success' : 'error');
      setSelectedLeadIds(new Set());
      setBulkStageOpen(false);
      setBulkStageValue('');
      setBulkLostReason('');
      fetchLeads();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không rõ'}`, 'error');
    } finally {
      setBulkBusy(false);
    }
  };

  if (loading || !user) return <Sidebar><div className="p-6 space-y-4"><div className="skeleton h-8 w-48 rounded-xl" /><div className="grid grid-cols-5 gap-3">{[1,2,3,4,5].map(i => <div key={i} className="skeleton h-32 rounded-xl" />)}</div></div></Sidebar>;
  if (error) {
    return (
      <Sidebar>
        <div className="p-6 flex items-center justify-center min-h-[60vh]">
          <div className="glass-card p-8 text-center max-w-md">
            <LineIcon name="alert" size={40} className="block mx-auto mb-4" />
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

  // Danh sách NVKD để chọn — dựng từ lead đang có, kèm ô "Chưa phân công".
  const assigneeOptions = (() => {
    const byId = new Map<string, string>();
    let coChuaPhanCong = false;
    for (const l of leads) {
      if (l.assigned_to) byId.set(l.assigned_to, l.assigned_user_name || 'Không rõ tên');
      else coChuaPhanCong = true;
    }
    return {
      items: [...byId.entries()].sort((a, b) => a[1].localeCompare(b[1], 'vi')),
      coChuaPhanCong,
    };
  })();

  const filteredByUrl = sorted.filter(lead => {
    if (activeStage && lead.stage !== activeStage) return false;
    if (activeQuickFilter === 'overdue' && !isOverdueLead(lead)) return false;
    if (filterAssignee !== 'all') {
      if (filterAssignee === 'unassigned') {
        if (lead.assigned_to) return false;
      } else if (lead.assigned_to !== filterAssignee) return false;
    }
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
  const hasFilters = filterSource !== 'all' || filterPriority !== 'all' || filterRegion !== 'all' || hasUrlFilters || searchQuery !== '' || datePreset !== 'all' || filterAssignee !== 'all';
  const activeFilterLabels = [
    activeStage ? `Giai đoạn: ${STAGE_CONFIG[activeStage]?.label || activeStage}` : null,
    activeQuickFilter === 'overdue' ? 'Quá hạn CSKH (ngưỡng theo giai đoạn)' : null,
    filterRegion !== 'all' ? `Tỉnh/thành: ${filterRegion}` : null,
    dateRangeLabel ? `${DATE_FIELDS[dateField]?.label}: ${dateRangeLabel}` : null,
    filterAssignee === 'unassigned'
      ? 'Phụ trách: Chưa phân công'
      : filterAssignee !== 'all'
        ? `Phụ trách: ${assigneeOptions.items.find(([id]) => id === filterAssignee)?.[1] || '—'}`
        : null,
  ].filter(Boolean);

  const clearFilters = () => {
    setFilterSource('all');
    setFilterPriority('all');
    setFilterRegion('all');
    setSearchQuery('');
    setFilterAssignee('all');
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
            <h1 className="text-2xl font-bold">Quy trình ERP</h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                {viewMode === 'list' ? 'Click vào dòng để xem chi tiết' : 'Click vào card để xem chi tiết'} · {shownCount}/{leads.length} leads
              </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap sm:flex-shrink-0">
            <div className="flex rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
              {([
                { mode: 'kanban', icon: 'kanban', label: 'Kanban' },
                { mode: 'list', icon: 'list', label: 'Danh sách' },
                { mode: 'calendar', icon: 'calendar', label: 'Lịch' },
              ] as const).map((v, i, arr) => (
                <button
                  key={v.mode}
                  onClick={() => setViewMode(v.mode)}
                  aria-pressed={viewMode === v.mode}
                  className="px-3 py-1.5 text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5"
                  style={{
                    background: viewMode === v.mode ? 'rgba(201,169,110,0.2)' : 'var(--surface-2)',
                    color: viewMode === v.mode ? 'var(--gold-500)' : 'var(--text-muted)',
                    borderRight: i < arr.length - 1 ? '1px solid var(--border-subtle)' : undefined,
                  }}
                ><LineIcon name={v.icon} size={14} color="currentColor" />{v.label}</button>
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
            <option value="urgent">Khẩn cấp</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
            <option value="low">Thấp</option>
          </select>
          {/* Khu vực = 34 tỉnh/thành sau sáp nhập, KÈM các giá trị cũ đang thực
              sự có trong dữ liệu (96 lead đang lưu tên quận / tên tỉnh trước
              sáp nhập) để vẫn lọc ra được — xem tuyChonKhuVuc.
              Ô «Phân loại» đã bỏ 22/09 cùng lúc với trường ở form tạo Lead:
              không còn đường nhập nên bộ lọc đó thành mồ côi. */}
          <select value={filterRegion} onChange={e => setFilterRegion(e.target.value)} className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none">
            <option value="all">Tất cả tỉnh/thành</option>
            {danhSachKhuVuc.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <select
            value={filterAssignee}
            onChange={e => setFilterAssignee(e.target.value)}
            aria-label="Lọc theo nhân viên kinh doanh phụ trách"
            className="text-xs px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none max-w-[170px]"
            style={filterAssignee !== 'all' ? { borderColor: 'rgba(201,169,110,0.5)', color: '#C9A96E' } : undefined}
          >
            <option value="all">Tất cả nhân viên KD</option>
            {assigneeOptions.coChuaPhanCong && <option value="unassigned">— Chưa phân công —</option>}
            {assigneeOptions.items.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
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

        {/* Chọn mốc «Ngày khảo sát» → hiện bảng khảo sát/chuyển đổi theo NVKD */}
        {dateField === 'survey_date' && <KhaoSatThang />}

        {/* Loading */}
        {loadingLeads ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
            <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            Đang tải...
          </div>
        ) : filteredByUrl.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)]">
            <p className="text-lg mb-2"><LineIcon name="inbox" size={18} className="inline-block align-[-3px] mr-1.5" />Không có lead phù hợp</p>
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
                        {isOverdueLead(lead) && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 ml-1"><LineIcon name="alert" size={10} color="currentColor" className="inline-block align-[-1px] mr-0.5" />Quá hạn</span>}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5"><LineIcon name="smartphone" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{lead.phone || '—'}</p>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold flex-shrink-0" style={{
                      background: `${STAGE_CONFIG[lead.stage]?.color}20`,
                      color: STAGE_CONFIG[lead.stage]?.color,
                    }}>
                      <LineIcon name={STAGE_CONFIG[lead.stage]?.icon || "info"} size={12} color="currentColor" className="inline-block align-[-1px] mr-1" />{STAGE_CONFIG[lead.stage]?.label || lead.stage}
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
                    {canAssign && (
                      <th className="px-3 py-3 w-8">
                        <input
                          type="checkbox"
                          aria-label="Chọn tất cả lead đang hiển thị"
                          checked={filteredByUrl.length > 0 && filteredByUrl.every(l => selectedLeadIds.has(l.id))}
                          onChange={toggleSelectAllVisible}
                          onClick={e => e.stopPropagation()}
                          className="w-4 h-4 cursor-pointer accent-[#C9A96E]"
                        />
                      </th>
                    )}
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
                      {canAssign && (
                        <td className="px-3 py-3 w-8" onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            aria-label={`Chọn ${lead.name}`}
                            checked={selectedLeadIds.has(lead.id)}
                            onChange={() => toggleSelectLead(lead.id)}
                            className="w-4 h-4 cursor-pointer accent-[#C9A96E]"
                          />
                        </td>
                      )}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: PRIORITY_LABELS[lead.priority]?.color || '#6B7280' }} />
                          <div className="min-w-0">
                            <p className="font-medium text-[var(--text-primary)] truncate max-w-[180px]">
                              {lead.name}
                              {isOverdueLead(lead) && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium ml-1"><LineIcon name="alert" size={10} color="currentColor" className="inline-block align-[-1px] mr-0.5" />Quá hạn</span>
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
                          <LineIcon name={STAGE_CONFIG[lead.stage]?.icon || "info"} size={12} color="currentColor" className="inline-block align-[-1px] mr-1" />{STAGE_CONFIG[lead.stage]?.label || lead.stage}
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
          <BangKanbanLead
            topScrollRef={topScrollRef}
            onTopScroll={onTopScroll}
            spacerRef={spacerRef}
            ganBang={ganBang}
            onBoardScroll={onBoardScroll}
            kanban={kanban}
            dragOverStage={dragOverStage}
            setDragOverStage={setDragOverStage}
            leads={leads}
            openLeadDetail={openLeadDetail}
            handleStageChange={handleStageChange}
            kanbanVisible={kanbanVisible}
            toast={toast}
            setKanbanVisible={setKanbanVisible}
          />
        )}
      </div>

      {/* ── Lead Detail Modal ── */}
      {selectedLead && (
        <ChiTietLead
          closeLeadDetail={closeLeadDetail}
          selectedLead={selectedLead}
          canAssign={canAssign}
          assignOpen={assignOpen}
          assigning={assigning}
          loadingUsers={loadingUsers}
          handleAssign={handleAssign}
          assignableUsers={assignableUsers}
          setAssignOpen={setAssignOpen}
          openAssign={openAssign}
          savingSurvey={savingSurvey}
          handleSurveyDate={handleSurveyDate}
          xinGoiY={xinGoiY}
          dangXinGoiY={dangXinGoiY}
          goiY={goiY}
          ghiNhanGoiY={ghiNhanGoiY}
          dangGhiNhan={dangGhiNhan}
          lichSuGoiY={lichSuGoiY}
          cskhNotes={cskhNotes}
          canWriteCskh={canWriteCskh}
          newCskhNote={newCskhNote}
          setNewCskhNote={setNewCskhNote}
          handleAddCskhNote={handleAddCskhNote}
          savingCskh={savingCskh}
          loadingActivities={loadingActivities}
          timelineActivities={timelineActivities}
          setActivities={setActivities}
          toast={toast}
          newNote={newNote}
          setNewNote={setNewNote}
          handleAddNote={handleAddNote}
          themAnhCho={themAnhCho}
          chonAnhRef={chonAnhRef}
          dangGuiNote={dangGuiNote}
          anhCho={anhCho}
          setAnhCho={setAnhCho}
          lostPickerRef={lostPickerRef}
          handleStageChange={handleStageChange}
          lostPickerOpen={lostPickerOpen}
          setLostPickerOpen={setLostPickerOpen}
          dormantReason={dormantReason}
          setDormantReason={setDormantReason}
          doStageChange={doStageChange}
        />
      )}

      {/* Thanh hành động bulk — nổi dưới màn hình khi có lead được chọn ở view danh sách */}
      {canAssign && viewMode === 'list' && selectedLeadIds.size > 0 && (
        <ThanhThaoTacHangLoat
          selectedLeadIds={selectedLeadIds}
          bulkAssignOpen={bulkAssignOpen}
          bulkStageOpen={bulkStageOpen}
          loadAssignableUsers={loadAssignableUsers}
          setBulkAssignOpen={setBulkAssignOpen}
          setBulkStageOpen={setBulkStageOpen}
          setSelectedLeadIds={setSelectedLeadIds}
          bulkBusy={bulkBusy}
          handleBulkAssign={handleBulkAssign}
          loadingUsers={loadingUsers}
          assignableUsers={assignableUsers}
          bulkStageValue={bulkStageValue}
          setBulkStageValue={setBulkStageValue}
          bulkLostReason={bulkLostReason}
          setBulkLostReason={setBulkLostReason}
          runBulkStage={runBulkStage}
        />
      )}

      {signedConfirmOpen && signedTarget && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="signed-confirm-title">
          <div className="absolute inset-0 bg-black/70" onClick={() => { setSignedConfirmOpen(false); setSignedTarget(null); }} />
          <div className="relative w-full max-w-md rounded-2xl p-5 glass-card">
            <h3 id="signed-confirm-title" className="text-base font-bold text-white"><LineIcon name="check" size={16} className="inline-block align-[-2px] mr-1.5" />Xác nhận deal đã thắng</h3>
            <p className="mt-3 text-sm text-[var(--text-secondary)]">Chuyển <strong>{signedTarget.name}</strong> sang «{STAGE_CONFIG.signed_design.label}» sẽ tự động tạo Khách hàng, Hợp đồng và 19 công việc.</p>
            <label className="block mt-3 text-xs text-[var(--text-secondary)]">Giá trị hợp đồng đã ký (đ) — dùng cho doanh số, thưởng, P&amp;L
              <MoneyInput valueDong={signedValue} onChangeDong={setSignedValue} placeholder="VD: 120.000.000" className="mt-1 w-full" />
            </label>
            {!Number(signedValue) && <p className="mt-1 text-[11px] text-[var(--text-muted)]">Bỏ trống thì tạm lấy ngân sách dự kiến, sửa lại sau ở Hợp đồng.</p>}
            <p className="mt-2 text-xs text-amber-400">Thao tác này không thể lùi lại. Chỉ xác nhận khi hợp đồng đã ký.</p>
            <div className="flex justify-end gap-2 mt-5">
              <button className="px-3 py-2 rounded-lg text-xs bg-white/10 text-white" onClick={() => { setSignedConfirmOpen(false); setSignedTarget(null); }}>Hủy</button>
              <button className="px-3 py-2 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-300" onClick={() => { const target = signedTarget; setSignedConfirmOpen(false); setSignedTarget(null); void doStageChange(target, 'signed_design', { contractValue: Number(signedValue) || undefined }); }}>Xác nhận deal thắng</button>
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
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><LineIcon name="hourglass" size={28} /></div>}>
      <LeadsContent />
    </Suspense>
  );
}
