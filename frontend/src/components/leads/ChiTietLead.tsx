'use client';

import type { Dispatch, RefObject, SetStateAction } from 'react';
import LineIcon from '@/components/ui/LineIcon';
import { NEEDS_LABELS, NGAN_SACH_LABELS, PLAN_TYPE_LABELS, PROPERTY_CLASS_LABELS, STAGE_CONFIG, formatCurrency, formatDealValue, formatPricePerSqm, timeAgo } from '@/lib/utils';
import { toDayKey } from '@/lib/date-filter';
import { AnhLead, DONG_ANH } from '@/components/ui/AnhGhiChuLead';
import { api } from '@/lib/api';
import { PRIORITY_LABELS, TagBadge, SOURCE_LABELS, PROPERTY_LABELS, formatDateTime, ACTIVITY_ICONS, STAGES } from './shared';
import LostReasonSelector from './LostReasonSelector';
import type { Lead, User, AISuggestion, AISuggestionHistory, Activity } from '@/lib/api';

/** Modal chi tiết lead. */
export default function ChiTietLead({
  closeLeadDetail,
  selectedLead,
  canAssign,
  assignOpen,
  assigning,
  loadingUsers,
  handleAssign,
  assignableUsers,
  setAssignOpen,
  openAssign,
  savingSurvey,
  handleSurveyDate,
  xinGoiY,
  dangXinGoiY,
  goiY,
  ghiNhanGoiY,
  dangGhiNhan,
  lichSuGoiY,
  cskhNotes,
  canWriteCskh,
  newCskhNote,
  setNewCskhNote,
  handleAddCskhNote,
  savingCskh,
  loadingActivities,
  timelineActivities,
  setActivities,
  toast,
  newNote,
  setNewNote,
  handleAddNote,
  themAnhCho,
  chonAnhRef,
  dangGuiNote,
  anhCho,
  setAnhCho,
  lostPickerRef,
  handleStageChange,
  lostPickerOpen,
  setLostPickerOpen,
  dormantReason,
  setDormantReason,
  doStageChange,
}: {
  closeLeadDetail: () => void;
  selectedLead: Lead;
  canAssign: boolean;
  assignOpen: boolean;
  assigning: boolean;
  loadingUsers: boolean;
  handleAssign: (userId: string) => Promise<void>;
  assignableUsers: User[];
  setAssignOpen: Dispatch<SetStateAction<boolean>>;
  openAssign: () => void;
  savingSurvey: boolean;
  handleSurveyDate: (value: string) => Promise<void>;
  xinGoiY: () => Promise<void>;
  dangXinGoiY: boolean;
  goiY: AISuggestion | null;
  ghiNhanGoiY: (outcome: "done" | "skipped") => Promise<void>;
  dangGhiNhan: boolean;
  lichSuGoiY: AISuggestionHistory[];
  cskhNotes: Activity[];
  canWriteCskh: boolean;
  newCskhNote: string;
  setNewCskhNote: Dispatch<SetStateAction<string>>;
  handleAddCskhNote: () => Promise<void>;
  savingCskh: boolean;
  loadingActivities: boolean;
  timelineActivities: Activity[];
  setActivities: Dispatch<SetStateAction<Activity[]>>;
  toast: (message: string, type?: "success" | "info" | "warning" | "error" | undefined) => void;
  newNote: string;
  setNewNote: Dispatch<SetStateAction<string>>;
  handleAddNote: () => Promise<void>;
  themAnhCho: (files: Iterable<File>) => Promise<void>;
  chonAnhRef: RefObject<HTMLInputElement | null>;
  dangGuiNote: boolean;
  anhCho: string[];
  setAnhCho: Dispatch<SetStateAction<string[]>>;
  lostPickerRef: RefObject<HTMLDivElement | null>;
  handleStageChange: (lead: Lead, newStage: string, reasonOverride?: string | undefined) => Promise<void>;
  lostPickerOpen: boolean;
  setLostPickerOpen: Dispatch<SetStateAction<boolean>>;
  dormantReason: string;
  setDormantReason: Dispatch<SetStateAction<string>>;
  doStageChange: (lead: Lead, newStage: string, opts?: { reason?: string | undefined; contractValue?: number | undefined; } | undefined) => Promise<void>;
}) {
  return (
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
              <LineIcon name={STAGE_CONFIG[selectedLead.stage]?.icon || "info"} size={12} color="currentColor" className="inline-block align-[-1px] mr-1" />{STAGE_CONFIG[selectedLead.stage]?.label}
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
                <LineIcon name="flag" size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />{PROPERTY_CLASS_LABELS[selectedLead.property_class].label}
              </span>
            )}
            {selectedLead.plan_type && selectedLead.plan_type !== 'none' && PLAN_TYPE_LABELS[selectedLead.plan_type] && (
              <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                background: `${PLAN_TYPE_LABELS[selectedLead.plan_type].color}20`,
                color: PLAN_TYPE_LABELS[selectedLead.plan_type].color,
              }}>
                <LineIcon name="clipboard" size={16} className="inline-block align-[-2px] mr-1.5" />{PLAN_TYPE_LABELS[selectedLead.plan_type].label}
              </span>
            )}
            {selectedLead.ai_score != null && selectedLead.ai_score > 0 && (
              <span className="text-xs px-2.5 py-1 rounded-full font-semibold" style={{
                background: selectedLead.ai_score >= 80 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
                color: selectedLead.ai_score >= 80 ? '#10B981' : '#F59E0B',
              }}>
                <LineIcon name="robot" size={16} className="inline-block align-[-2px] mr-1.5" />AI Score: {selectedLead.ai_score}/100
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
                <LineIcon name="smartphone" size={16} color="currentColor" className="text-[var(--text-muted)]" />
                <span className="text-white font-medium">{selectedLead.phone}</span>
              </div>
              {selectedLead.email && (
                <div className="flex items-center gap-2">
                  <LineIcon name="mail" size={16} color="currentColor" className="text-[var(--text-muted)]" />
                  <span className="text-white">{selectedLead.email}</span>
                </div>
              )}
              {selectedLead.address && (
                <div className="flex items-center gap-2 md:col-span-2">
                  <LineIcon name="pin" size={16} color="currentColor" className="text-[var(--text-muted)]" />
                  <span className="text-[var(--text-secondary)]">{selectedLead.address}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <LineIcon name="megaphone" size={16} color="currentColor" className="text-[var(--text-muted)]" />
                <span className="text-[var(--text-secondary)]">Nguồn: {SOURCE_LABELS[selectedLead.source || ''] || selectedLead.source}</span>
              </div>
              {selectedLead.region && (
                <div className="flex items-center gap-2">
                  <LineIcon name="globe" size={16} color="currentColor" className="text-[var(--text-muted)]" />
                  <span className="text-[var(--text-secondary)]">Khu vực: {selectedLead.region}</span>
                </div>
              )}
              {/* Phụ trách — LUÔN hiển thị; admin/leader gắn/đổi nhân viên KD ngay tại đây */}
              <div className="flex items-center gap-2 flex-wrap sm:col-span-2">
                <LineIcon name="user" size={16} color="currentColor" className="text-[var(--text-muted)]" />
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
                      <LineIcon name="edit" size={16} className="inline-block align-[-2px] mr-1.5" />Đổi
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
                {/* Ưu tiên MỨC (sale nào cũng chọn được ngay), số chính xác
                    hiện thêm bên dưới nếu khách đã nói rõ (chốt 22/09). */}
                <p className="text-sm font-semibold mt-1 text-[#C9A96E]">
                  {selectedLead.ngan_sach_khoang
                    ? NGAN_SACH_LABELS[selectedLead.ngan_sach_khoang] || selectedLead.ngan_sach_khoang
                    : formatCurrency(selectedLead.estimated_budget)}
                </p>
                {selectedLead.ngan_sach_khoang && !!selectedLead.estimated_budget && (
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                    {formatCurrency(selectedLead.estimated_budget)}
                  </p>
                )}
              </div>
              <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                <p className="text-xs text-[var(--text-muted)]">Giá trị hợp đồng</p>
                <p className="text-sm font-bold mt-1 text-[#10B981]">{formatDealValue(selectedLead.deal_value)}</p>
              </div>
            </div>
            {/* Ngày khảo sát — nền cho báo cáo khảo sát/chuyển đổi của NVKD */}
            <div className="flex flex-wrap items-center gap-2 mb-3 p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
              <label htmlFor="ngay-khao-sat" className="text-xs text-[var(--text-muted)]">Ngày khảo sát</label>
              <input
                id="ngay-khao-sat"
                type="date"
                disabled={savingSurvey}
                value={selectedLead.survey_date ? toDayKey(selectedLead.survey_date) || '' : ''}
                onChange={e => void handleSurveyDate(e.target.value)}
                className="text-sm px-2 py-1.5 rounded-lg bg-[var(--surface-3)] text-[var(--text-primary)] border border-[var(--border-subtle)] outline-none"
              />
              {!selectedLead.survey_date && <span className="text-xs text-[var(--text-muted)]">Chưa khảo sát</span>}
            </div>
            {/* New Lark CRM fields grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 mb-3">
              {selectedLead.segment && (
                <div className="p-3 rounded-lg text-center" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-xs text-[var(--text-muted)]">Nhu cầu</p>
                  <p className="text-sm font-semibold mt-1">{NEEDS_LABELS[selectedLead.segment] || selectedLead.segment}</p>
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
                  <p className="text-sm font-semibold mt-1"><LineIcon name="pin" size={14} className="inline-block align-[-2px] mr-1.5" />{selectedLead.region}</p>
                </div>
              )}
            </div>
            {selectedLead.needs && (
              <div className="p-3 rounded-lg text-sm text-[var(--text-secondary)]" style={{ background: 'var(--surface-2)' }}>
                <p className="text-xs text-[var(--text-muted)] mb-1"><LineIcon name="clipboard" size={16} className="inline-block align-[-2px] mr-1.5" />Yêu cầu chi tiết:</p>
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
                <LineIcon name="robot" size={16} className="inline-block align-[-2px] mr-1.5" />Gợi ý AI
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
                    <p className="text-[10px] text-[var(--text-muted)] mb-1"><LineIcon name="message" size={16} className="inline-block align-[-2px] mr-1.5" />Mẫu tin nhắn:</p>
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
                      <LineIcon name="check" size={16} className="inline-block align-[-2px] mr-1.5" />Đã làm
                    </button>
                    <button
                      onClick={() => ghiNhanGoiY('skipped')}
                      disabled={dangGhiNhan}
                      className="flex-1 px-3 py-2 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-secondary)] border border-white/10 hover:border-[#C9A96E] hover:text-[#C9A96E] disabled:opacity-40 transition-all min-h-[36px]"
                    >
                      <LineIcon name="arrowRight" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Bỏ qua
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
                      <LineIcon name={ls.outcome === 'done' ? 'check' : ls.outcome === 'skipped' ? 'arrowRight' : 'hourglass'} size={14} />
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
                <LineIcon name="users" size={14} className="inline-block align-[-2px] mr-1.5" />CSKH — Đánh giá chất lượng chăm sóc ({cskhNotes.length})
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
                      <LineIcon name="users" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{note.user_name || 'Admin CSKH'} · {formatDateTime(note.created_at)}
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
                      <LineIcon name={ACTIVITY_ICONS[act.type] || 'pin'} size={16} className="shrink-0" />
                      {i < timelineActivities.length - 1 && (
                        <div className="w-px flex-1 mt-1" style={{ background: 'var(--border-subtle)' }} />
                      )}
                    </div>
                    <div className="flex-1 pb-3">
                      <div className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">
                        {(act.content || '').split('\n').filter(l => !DONG_ANH.test(l)).map((line, li, chu) => {
                          if (line.startsWith('📎')) {
                            const url = line.replace('📎', '').trim();
                            return (
                              <a key={li} href={url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-[#C9A96E] hover:underline text-xs mt-1"
                              >
                                <LineIcon name="link" size={12} color="currentColor" />{url.replace('https://drive.google.com/', 'drive.google.com/...')}
                              </a>
                            );
                          }
                          return <span key={li}>{line}{li < chu.length - 1 && <br />}</span>;
                        })}
                      </div>
                      {(() => {
                        const anhIds = (act.content || '').split('\n').map(l => l.match(DONG_ANH)?.[1]).filter((x): x is string => !!x);
                        return anhIds.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-1.5">
                            {anhIds.map(id => <AnhLead key={id} leadId={selectedLead.id} anhId={id} />)}
                          </div>
                        );
                      })()}
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
                  onPaste={e => {
                    const files = [...e.clipboardData.files].filter(f => f.type.startsWith('image/'));
                    if (files.length) { e.preventDefault(); themAnhCho(files); }
                  }}
                  placeholder="Thêm ghi chú (dán ảnh được)..."
                  className="flex-1 px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-[#C9A96E]"
                />
                <input
                  ref={chonAnhRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={e => { if (e.target.files) themAnhCho(e.target.files); e.target.value = ''; }}
                />
                <button
                  type="button"
                  onClick={() => chonAnhRef.current?.click()}
                  disabled={dangGuiNote || anhCho.length >= 6}
                  title="Đính ảnh (tối đa 6)"
                  aria-label="Đính ảnh"
                  className="px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-[var(--text-secondary)] hover:border-[#C9A96E] hover:text-[#C9A96E] disabled:opacity-30 transition-all"
                >
                  <LineIcon name="camera" size={16} color="currentColor" />
                </button>
                <button
                  onClick={handleAddNote}
                  disabled={dangGuiNote || (!newNote.trim() && !anhCho.length)}
                  className="px-3 py-2 rounded-lg text-sm font-medium bg-[#C9A96E]/20 text-[#C9A96E] hover:bg-[#C9A96E]/30 disabled:opacity-30 transition-all"
                >
                  {dangGuiNote ? '...' : 'Gửi'}
                </button>
              </div>
              {anhCho.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {anhCho.map((src, i) => (
                    <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border border-white/10">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt={`Ảnh chờ gửi ${i + 1}`} className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() => setAnhCho(prev => prev.filter((_, j) => j !== i))}
                        disabled={dangGuiNote}
                        aria-label="Bỏ ảnh này"
                        className="absolute top-0.5 right-0.5 w-7 h-7 rounded-full bg-black/70 text-white text-base leading-none"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
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
                  <LineIcon name={STAGE_CONFIG[stage]?.icon || "info"} size={12} color="currentColor" className="inline-block align-[-1px] mr-1" />{STAGE_CONFIG[stage]?.label}
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
            {/* Ngủ đông — trạng thái dormant có ở backend từ đầu nhưng không có đường vào UI
                (QC 05/09: nút chỉ validate, không tạo được). Khách im lặng dài hạn ≠ mất hẳn.
                Lý do là tuỳ chọn nhưng nên ghi: backend lưu activity type stage_change
                kèm note, giúp leader hiểu tại sao lead bị cất đi. */}
            {selectedLead.stage !== 'dormant' && selectedLead.stage !== 'lost' && selectedLead.stage !== 'signed_design' && (
              <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                {!dormantReason ? (
                  <button
                    onClick={() => setDormantReason('__pending__')}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
                    style={{ background: 'rgba(107,114,128,0.12)', color: '#9CA3AF', border: '1px solid rgba(107,114,128,0.3)' }}
                    title="Khách tạm im lặng nhưng chưa mất — cất vào Ngủ đông, sau này đánh thức lại được"
                  >
                    <LineIcon name="moon" size={14} color="currentColor" className="inline-block align-[-2px] mr-1.5" />Chuyển sang Ngủ đông
                  </button>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-gray-400">Lý do ngủ đông (tuỳ chọn):</p>
                    <input
                      value={dormantReason === '__pending__' ? '' : dormantReason}
                      onChange={e => setDormantReason(e.target.value || '__pending__')}
                      placeholder="VD: Khách đi nước ngoài 3 tháng, liên hệ lại tháng 10"
                      className="w-full px-3 py-1.5 rounded-lg text-xs bg-white/5 border border-white/10 text-white placeholder-white/30 outline-none focus:border-gray-400"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          void doStageChange(selectedLead, 'dormant', { reason: dormantReason === '__pending__' ? undefined : dormantReason.trim() || undefined });
                          setDormantReason('');
                        }}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-500/20 text-gray-300 hover:bg-gray-500/30 transition-all"
                      >
                        Xác nhận Ngủ đông
                      </button>
                      <button
                        onClick={() => setDormantReason('')}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-[var(--text-muted)] hover:bg-white/10 transition-all"
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                )}
              </div>
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
  );
}
