'use client';

import type { Dispatch, RefObject, SetStateAction } from 'react';
import LineIcon from '@/components/ui/LineIcon';
import { NEEDS_LABELS, STAGE_CONFIG, cn, formatCurrency, formatDealValue, timeAgo } from '@/lib/utils';
import { api } from '@/lib/api';
import { KANBAN_PAGE_SIZE, isOverdueLead, BOARD_STAGES, PROPERTY_LABELS, SOURCE_LABELS, TagBadge } from './shared';
import type { Lead } from '@/lib/api';

/** Bảng Kanban lead theo giai đoạn. */
export default function BangKanbanLead({
  topScrollRef,
  onTopScroll,
  spacerRef,
  ganBang,
  onBoardScroll,
  kanban,
  dragOverStage,
  setDragOverStage,
  leads,
  openLeadDetail,
  handleStageChange,
  kanbanVisible,
  toast,
  setKanbanVisible,
}: {
  topScrollRef: RefObject<HTMLDivElement | null>;
  onTopScroll: () => void;
  spacerRef: RefObject<HTMLDivElement | null>;
  ganBang: (node: HTMLDivElement | null) => void;
  onBoardScroll: () => void;
  kanban: { stage: string; leads: Lead[]; }[];
  dragOverStage: string | null;
  setDragOverStage: Dispatch<SetStateAction<string | null>>;
  leads: Lead[];
  openLeadDetail: (lead: Lead, options?: { lostPicker?: boolean | undefined; } | undefined) => Promise<void>;
  handleStageChange: (lead: Lead, newStage: string, reasonOverride?: string | undefined) => Promise<void>;
  kanbanVisible: Record<string, number>;
  toast: (message: string, type?: "success" | "info" | "warning" | "error" | undefined) => void;
  setKanbanVisible: Dispatch<SetStateAction<Record<string, number>>>;
}) {
  return (
    <div className="relative">
      {/* Thanh trượt ngang ĐẶT TRÊN, dính đầu trang. Cột "Tiếp nhận mới" có thể
          cao vài chục nghìn px nên thanh trượt mặc định nằm dưới đáy khối là
          không với tới được — phải cuộn hết data mới thấy (feedback 29/08). */}
      <div
        ref={topScrollRef}
        onScroll={onTopScroll}
        className="top-scrollbar sticky top-14 lg:top-0 z-20 overflow-x-auto overflow-y-hidden mb-2 rounded"
        style={{ height: 16, background: 'var(--surface-2)' }}
        aria-hidden="true"
      >
        <div ref={spacerRef} style={{ height: 1 }} />
      </div>
      <div
        ref={ganBang}
        onScroll={onBoardScroll}
        className="flex gap-4 overflow-x-auto pb-4 min-w-0"
        style={{ maskImage: 'linear-gradient(to right, transparent 0px, black 12px, black calc(100% - 12px), transparent 100%)', WebkitMaskImage: 'linear-gradient(to right, transparent 0px, black 12px, black calc(100% - 12px), transparent 100%)' }}
      >
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
              {col.leads.slice(0, kanbanVisible[col.stage] ?? KANBAN_PAGE_SIZE).map(lead => (
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
                          <LineIcon name="alert" size={16} className="inline-block align-[-2px] mr-1.5" />Quá hạn
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
                  <p className="text-xs text-[var(--text-muted)] mt-1"><LineIcon name="smartphone" size={12} color="currentColor" className="inline-block align-[-2px] mr-1.5" />{lead.phone}</p>
                  {lead.last_contacted_at && (
                    <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                      <LineIcon name="clock" size={16} className="inline-block align-[-2px] mr-1.5" />{timeAgo(lead.last_contacted_at)}
                    </p>
                  )}
                  {lead.property_type && (
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">
                      <LineIcon name="home" size={16} className="inline-block align-[-2px] mr-1.5" />{PROPERTY_LABELS[lead.property_type] || lead.property_type} {lead.area_sqm ? `· ${lead.area_sqm}m²` : ''}
                    </p>
                  )}
                  {/* Region + Segment line */}
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {lead.region && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                        <LineIcon name="pin" size={16} className="inline-block align-[-2px] mr-1.5" />{lead.region}
                      </span>
                    )}
                    {lead.segment && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-[var(--text-muted)]">
                        <LineIcon name="flag" size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />{NEEDS_LABELS[lead.segment] || lead.segment}
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
              {(() => {
                const shown = Math.min(col.leads.length, kanbanVisible[col.stage] ?? KANBAN_PAGE_SIZE);
                const hidden = col.leads.length - shown;
                if (hidden <= 0 && shown <= KANBAN_PAGE_SIZE) return null;
                return (
                  <div className="flex gap-2 pt-1">
                    {hidden > 0 && (
                      <button
                        onClick={() => setKanbanVisible(prev => ({ ...prev, [col.stage]: shown + KANBAN_PAGE_SIZE }))}
                        className="flex-1 py-2 rounded-lg text-xs font-medium transition-all hover:opacity-80 min-h-[36px]"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px dashed var(--border-subtle)' }}
                      >
                        Hiện thêm {Math.min(hidden, KANBAN_PAGE_SIZE)} thẻ (còn {hidden})
                      </button>
                    )}
                    {shown > KANBAN_PAGE_SIZE && (
                      <button
                        onClick={() => setKanbanVisible(prev => ({ ...prev, [col.stage]: KANBAN_PAGE_SIZE }))}
                        className="py-2 px-3 rounded-lg text-xs font-medium transition-all hover:opacity-80 min-h-[36px]"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
                        title={`Thu về ${KANBAN_PAGE_SIZE} thẻ đầu`}
                      >
                        Thu gọn
                      </button>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
}
