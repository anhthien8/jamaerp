'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import { useToast } from '@/components/ui/Toast';
import { api, Team, User } from '@/lib/api';
import { REGION_OPTIONS, ALL_TAGS, TAG_COLORS, PLAN_TYPE_LABELS } from '@/lib/utils';
import MoneyInput from '@/components/ui/MoneyInput';

interface CreateLeadForm {
  name: string;
  phone: string;
  email: string;
  address: string;
  property_type: string;
  area_sqm: string;
  estimated_budget: string;
  source: string;
  needs: string;
  priority: string;
  property_class: string;
  price_per_sqm: string;
  region: string;
  segment: string;
  plan_type: string;
  tags: string[];
}

const INITIAL: CreateLeadForm = {
  name: '', phone: '', email: '', address: '',
  property_type: 'townhouse', area_sqm: '', estimated_budget: '',
  source: 'zalo', needs: '', priority: 'medium',
  property_class: 'mid_range', price_per_sqm: '', region: '', segment: 'townhouse',
  plan_type: 'none', tags: [],
};

const PROPERTY_OPTIONS = [
  { value: 'townhouse', label: 'Nhà phố' },
  { value: 'apartment', label: 'Căn hộ' },
  { value: 'villa', label: 'Biệt thự' },
  { value: 'shophouse', label: 'Shophouse' },
  { value: 'office', label: 'Văn phòng' },
  { value: 'other', label: 'Khác' },
];

const SOURCE_OPTIONS = [
  { value: 'zalo', label: 'Zalo' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'website', label: 'Website' },
  { value: 'referral', label: 'Giới thiệu' },
  { value: 'other', label: 'Khác' },
];

const PRIORITY_OPTIONS = [
  { value: 'urgent', label: 'Khẩn cấp', color: '#EF4444' },
  { value: 'high', label: 'Cao', color: '#F59E0B' },
  { value: 'medium', label: 'Trung bình', color: '#3B82F6' },
  { value: 'low', label: 'Thấp', color: '#6B7280' },
];

const PROPERTY_CLASS_OPTIONS = [
  { value: 'luxury', label: 'Hạng sang' },
  { value: 'mid_range', label: 'Trung bình' },
  { value: 'budget', label: 'Bình dân' },
];

const SEGMENT_OPTIONS = [
  { value: 'villa', label: 'Biệt thự' },
  { value: 'townhouse', label: 'Nhà phố' },
  { value: 'apartment', label: 'Căn hộ' },
  { value: 'shophouse', label: 'Shophouse' },
  { value: 'office', label: 'Văn phòng' },
];

const PLAN_TYPE_OPTIONS = [
  { value: 'online', label: 'Tư vấn Online' },
  { value: 'offline', label: 'Tư vấn Offline' },
  { value: 'survey', label: 'Khảo sát' },
  { value: 'none', label: 'Chưa có' },
];

export interface CreateLeadInitialData {
  name?: string;
  phone?: string;
  email?: string;
  address?: string;
  needs?: string;
  source?: string;
  property_type?: string;
  area_sqm?: number;
  estimated_budget?: number;
  confidence?: number;
}

export default function CreateLeadModal({ isOpen, onClose, initialData, canAssign }: { isOpen: boolean; onClose: () => void; initialData?: CreateLeadInitialData | null; canAssign?: boolean }) {
  const buildInitial = (): CreateLeadForm => {
    if (!initialData) return INITIAL;
    return {
      name: initialData.name || '',
      phone: initialData.phone || '',
      email: initialData.email || '',
      address: initialData.address || '',
      property_type: initialData.property_type || 'townhouse',
      area_sqm: initialData.area_sqm ? String(initialData.area_sqm) : '',
      estimated_budget: initialData.estimated_budget ? String(initialData.estimated_budget) : '',
      source: initialData.source || 'zalo',
      needs: initialData.needs || '',
      priority: 'medium',
      property_class: 'mid_range',
      price_per_sqm: '',
      region: '',
      segment: 'townhouse',
      plan_type: 'none',
      tags: [],
    };
  };
  const [form, setForm] = useState<CreateLeadForm>(buildInitial);
  const [errors, setErrors] = useState<Partial<Record<keyof CreateLeadForm, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  // ── Giao data: chọn TRƯỞNG NHÓM trước, rồi mới chọn nhân viên trong nhóm đó ──
  // (yêu cầu 27/08/2026 — trước đây là một danh sách phẳng, không phân biệt đội
  // nhóm nên CSKH dễ giao nhầm sang quân của trưởng nhóm khác).
  // Chỉ admin/leader/điều phối KD (canAssign); bỏ trống cả hai = người tạo tự phụ trách.
  const [teamId, setTeamId] = useState('');
  const [assignedTo, setAssignedTo] = useState('');
  const [salesUsers, setSalesUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  // Cờ "đã bắn request" để ref (không phải state): setState đồng bộ ngay trong thân
  // useEffect bị react-hooks/set-state-in-effect chặn.
  const assignLoadStarted = useRef(false);
  const [assignLoaded, setAssignLoaded] = useState(false);
  useEffect(() => {
    if (!isOpen || !canAssign || assignLoadStarted.current) return;
    assignLoadStarted.current = true;
    Promise.all([api.getAssignableSales(), api.getTeams()])
      .then(([users, teamList]) => {
        setSalesUsers(users);
        setTeams(teamList);
      })
      .catch(() => toast('Lỗi tải danh sách đội nhóm / nhân viên KD', 'error'))
      .finally(() => setAssignLoaded(true));
  }, [isOpen, canAssign, toast]);
  const loadingAssign = Boolean(canAssign) && !assignLoaded;

  const selectedTeam = useMemo(() => teams.find(t => t.id === teamId) || null, [teams, teamId]);
  // Nhân viên trong đội đã chọn. Trưởng nhóm cũng nằm trong đội nên hiện luôn ở
  // đây (có nhãn) — CSKH vẫn giao thẳng cho trưởng nhóm được nếu muốn.
  const teamMembers = useMemo(
    () => salesUsers.filter(u => u.team_id === teamId),
    [salesUsers, teamId],
  );
  // Đổi đội thì bỏ người đã chọn của đội cũ, tránh giao nhầm chéo đội.
  const handleTeamChange = (nextTeamId: string) => {
    setTeamId(nextTeamId);
    setAssignedTo('');
  };
  // Chọn đội mà không chọn ai = giao cho trưởng nhóm để họ tự chia tiếp
  // (đúng luồng CSKH → trưởng nhóm → sale đã chốt 14/08).
  const resolvedAssignee = assignedTo || (teamId ? selectedTeam?.leader_id || '' : '');

  const set = (key: keyof CreateLeadForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm(prev => ({ ...prev, [key]: e.target.value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  };

  const computedDealValue = useMemo(() => {
    const pps = form.price_per_sqm ? Number(form.price_per_sqm) : 0;
    const area = form.area_sqm ? Number(form.area_sqm) : 0;
    return pps > 0 && area > 0 ? pps * area : 0;
  }, [form.price_per_sqm, form.area_sqm]);

  const toggleTag = (tag: string) => {
    setForm(prev => ({
      ...prev,
      tags: prev.tags.includes(tag) ? prev.tags.filter(t => t !== tag) : [...prev.tags, tag],
    }));
  };

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.name.trim()) errs.name = 'Vui lòng nhập tên KH';
    if (!form.phone.trim()) errs.phone = 'Vui lòng nhập SĐT';
    else if (!/^0\d{9}$/.test(form.phone.trim())) errs.phone = 'SĐT không hợp lệ (10 số, bắt đầu 0)';
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = 'Email không hợp lệ';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    // Đội chưa có trưởng nhóm thì không có ai để rơi về — bắt chọn người cụ thể,
    // đừng lặng lẽ gán ngược cho người đang tạo.
    if (teamId && !resolvedAssignee) {
      toast('Đội này chưa có trưởng nhóm — chọn một nhân viên cụ thể để giao data', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await api.createLead({
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email || undefined,
        address: form.address || undefined,
        property_type: form.property_type,
        area_sqm: form.area_sqm ? Number(form.area_sqm) : undefined,
        estimated_budget: form.estimated_budget ? Number(form.estimated_budget) : undefined,
        source: form.source,
        needs: form.needs || undefined,
        priority: form.priority,
        property_class: form.property_class as 'luxury' | 'mid_range' | 'budget' | undefined,
        price_per_sqm: form.price_per_sqm ? Number(form.price_per_sqm) : undefined,
        region: form.region || undefined,
        segment: form.segment || undefined,
        plan_type: form.plan_type as 'online' | 'offline' | 'survey' | 'none' | undefined,
        tags: form.tags.length > 0 ? form.tags : undefined,
        deal_value: computedDealValue > 0 ? computedDealValue : undefined,
        assigned_to: resolvedAssignee || undefined,
      });
      const assignedName = resolvedAssignee
        ? salesUsers.find(u => u.id === resolvedAssignee)?.full_name
          || (resolvedAssignee === selectedTeam?.leader_id ? selectedTeam?.leader_name || '' : '')
        : '';
      toast(
        assignedName
          ? `Đã tạo Lead "${form.name}" và giao cho ${assignedName}!`
          : `Đã tạo Lead "${form.name}" thành công!`,
        'success',
      );
      setForm(INITIAL);
      setTeamId('');
      setAssignedTo('');
      setErrors({});
      onClose();
    } catch (e) {
      toast(`Lỗi: ${e instanceof Error ? e.message : 'Không tạo được lead'}`, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Reset toàn bộ form + lỗi về mặc định khi đóng, để lần mở sau luôn sạch.
  const handleClose = () => {
    setForm(buildInitial());
    setTeamId('');
    setAssignedTo('');
    setErrors({});
    setSubmitting(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[8vh]" onClick={handleClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl animate-in"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b" style={{ background: 'var(--surface-1)', borderColor: 'var(--border-subtle)' }}>
          <div>
            <h2 className="text-lg font-bold text-white">➕ Tạo Lead mới</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">Thêm khách hàng tiềm năng</p>
          </div>
          <button onClick={handleClose} aria-label="Đóng cửa sổ tạo lead" className="p-2 rounded-lg hover:bg-white/10 transition-colors text-[var(--text-muted)]">✕</button>
        </div>

        <div className="p-5 space-y-4">
          {/* Name + Phone */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tên khách hàng *" error={errors.name}>
              <input value={form.name} onChange={set('name')} placeholder="VD: Chị Mai" className="input" />
            </Field>
            <Field label="Số điện thoại *" error={errors.phone}>
              <input value={form.phone} onChange={set('phone')} placeholder="0901234567" inputMode="tel" className="input" />
            </Field>
          </div>

          {/* Email + Address */}
          <Field label="Email" error={errors.email}>
            <input value={form.email} onChange={set('email')} placeholder="email@example.com" className="input" />
          </Field>
          <Field label="Địa chỉ">
            <input value={form.address} onChange={set('address')} placeholder="123 Nguyễn Văn Linh, Q7" className="input" />
          </Field>

          {/* Property type + Area */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Loại BĐS">
              <select value={form.property_type} onChange={set('property_type')} className="input">
                {PROPERTY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="Diện tích (m²)">
              <input value={form.area_sqm} onChange={set('area_sqm')} placeholder="120" type="number" className="input" />
            </Field>
          </div>

          {/* Budget + Source */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Ngân sách (nghìn đồng)">
              <MoneyInput
                valueDong={form.estimated_budget}
                onChangeDong={v => setForm(f => ({ ...f, estimated_budget: v }))}
                placeholder="VD: 500000 = 500 triệu"
                className="input pr-24"
              />
            </Field>
            <Field label="Nguồn lead">
              <select value={form.source} onChange={set('source')} className="input">
                {SOURCE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
          </div>

          {/* Giao data theo đội — chỉ admin/leader/điều phối KD (CSKH) thấy khối này.
              Bước 1 chọn trưởng nhóm, bước 2 chọn nhân viên TRONG nhóm đó. */}
          {canAssign && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Trưởng nhóm phụ trách">
                <select
                  value={teamId}
                  onChange={e => handleTeamChange(e.target.value)}
                  className="input"
                  data-qc="assign-team-on-create"
                  disabled={loadingAssign}
                >
                  <option value="">{loadingAssign ? 'Đang tải...' : '— Tôi tự phụ trách —'}</option>
                  {teams.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.leader_name ? `${t.leader_name} — ${t.name}` : `${t.name} (chưa có trưởng nhóm)`}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Nhân viên kinh doanh">
                <select
                  value={assignedTo}
                  onChange={e => setAssignedTo(e.target.value)}
                  className="input"
                  data-qc="assign-on-create"
                  disabled={!teamId}
                >
                  <option value="">
                    {!teamId
                      ? '— Chọn trưởng nhóm trước —'
                      : selectedTeam?.leader_id
                        ? '— Giao cho trưởng nhóm chia tiếp —'
                        : '— Chọn nhân viên —'}
                  </option>
                  {teamMembers.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}{u.id === selectedTeam?.leader_id ? ' (Trưởng nhóm)' : ''}
                    </option>
                  ))}
                </select>
              </Field>
              {teamId && (
                <p className="sm:col-span-2 -mt-1 text-[11px] text-[var(--text-muted)]">
                  {teamMembers.length === 0
                    ? '⚠️ Đội này chưa có thành viên nào — xếp người vào đội ở trang Tài khoản trước.'
                    : assignedTo
                      ? `Data sẽ vào thẳng ${teamMembers.find(u => u.id === assignedTo)?.full_name || 'nhân viên đã chọn'}.`
                      : selectedTeam?.leader_id
                        ? `Chưa chọn nhân viên → data giao cho ${selectedTeam.leader_name || 'trưởng nhóm'} để chia tiếp trong nhóm.`
                        : '⚠️ Đội này chưa có trưởng nhóm — phải chọn một nhân viên cụ thể.'}
                </p>
              )}
            </div>
          )}

          {/* ── NEW: Lark CRM Fields ── */}

          {/* Property Class + Price per sqm */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Phân loại">
              <select value={form.property_class} onChange={set('property_class')} className="input">
                {PROPERTY_CLASS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="Đơn giá/m² (nghìn đồng)">
              <MoneyInput
                valueDong={form.price_per_sqm}
                onChangeDong={v => setForm(f => ({ ...f, price_per_sqm: v }))}
                placeholder="VD: 12000 = 12 triệu/m²"
                className="input pr-24"
              />
            </Field>
          </div>

          {/* Region + Segment */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Khu vực">
              <select value={form.region} onChange={set('region')} className="input">
                <option value="">Chọn khu vực</option>
                {REGION_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </Field>
            <Field label="Phân khúc">
              <select value={form.segment} onChange={set('segment')} className="input">
                {SEGMENT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
          </div>

          {/* Plan Type */}
          <Field label="Kế hoạch">
            <div className="flex gap-2 flex-wrap">
              {PLAN_TYPE_OPTIONS.map(p => {
                const pColor = PLAN_TYPE_LABELS[p.value]?.color || '#6B7280';
                return (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setForm(prev => ({ ...prev, plan_type: p.value }))}
                    className="flex-1 min-w-[100px] py-2 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: form.plan_type === p.value ? `${pColor}20` : 'var(--surface-2)',
                      color: form.plan_type === p.value ? pColor : 'var(--text-tertiary)',
                      border: `1px solid ${form.plan_type === p.value ? `${pColor}40` : 'var(--border-subtle)'}`,
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </Field>

          {/* Tags */}
          <Field label="Tags">
            <div className="flex gap-2 flex-wrap">
              {ALL_TAGS.map(tag => {
                const selected = form.tags.includes(tag);
                const color = TAG_COLORS[tag] || '#6B7280';
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                    style={{
                      background: selected ? `${color}25` : 'var(--surface-2)',
                      color: selected ? color : 'var(--text-tertiary)',
                      border: `1px solid ${selected ? `${color}50` : 'var(--border-subtle)'}`,
                    }}
                  >
                    {selected ? '✓ ' : ''}{tag}
                  </button>
                );
              })}
            </div>
          </Field>

          {/* Deal Value Auto-calc Preview */}
          {computedDealValue > 0 && (
            <div className="px-3 py-2 rounded-lg flex items-center justify-between" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
              <span className="text-xs text-[var(--text-muted)]">💰 Deal Value (tự tính):</span>
              <span className="text-sm font-bold text-[#C9A96E]">
                {computedDealValue >= 1_000_000_000
                  ? `${(computedDealValue / 1_000_000_000).toFixed(2).replace(/0+$/, '').replace(/\.$/, '')} tỷ`
                  : `${(computedDealValue / 1_000_000).toFixed(0)} triệu`}
              </span>
            </div>
          )}

          {/* Priority */}
          <Field label="Mức ưu tiên">
            <div className="flex gap-2">
              {PRIORITY_OPTIONS.map(p => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setForm(prev => ({ ...prev, priority: p.value }))}
                  className="flex-1 py-2 rounded-lg text-xs font-medium transition-all"
                  style={{
                    background: form.priority === p.value ? `${p.color}20` : 'var(--surface-2)',
                    color: form.priority === p.value ? p.color : 'var(--text-tertiary)',
                    border: `1px solid ${form.priority === p.value ? `${p.color}40` : 'var(--border-subtle)'}`,
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </Field>

          {/* Needs */}
          <Field label="Nhu cầu chi tiết">
            <textarea
              value={form.needs}
              onChange={set('needs')}
              placeholder="VD: Thiết kế nội thất nhà phố 3 tầng, phong cách hiện đại..."
              className="input"
              rows={3}
              style={{ resize: 'vertical', minHeight: 80 }}
            />
          </Field>

          {/* Submit */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={handleClose}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
            >
              Hủy
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-95 disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, var(--gold-500), var(--gold-600))', color: 'white' }}
            >
              {submitting ? 'Đang tạo...' : '✅ Tạo Lead'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">{label}</label>
      {children}
      {error && <p className="text-[10px] text-[#EF4444] mt-1">{error}</p>}
    </div>
  );
}
