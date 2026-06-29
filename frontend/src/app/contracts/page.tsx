'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, Contract, extractItems } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Nháp', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
  approved: { label: 'Duyệt', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  sent: { label: 'Đã gửi', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
  signed: { label: 'Ký HĐ', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  completed: { label: 'Hoàn thành', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
  cancelled: { label: 'Hủy', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
};

function fmtVND(n?: number) {
  if (!n) return '—';
  return new Intl.NumberFormat('vi-VN').format(n) + ' ₫';
}

function calcTimeLeft(signedDate?: string, workingDays?: number): { daysLeft: number; pct: number; label: string } | null {
  if (!signedDate || !workingDays) return null;
  const start = new Date(signedDate);
  const end = new Date(start);
  end.setDate(end.getDate() + workingDays);
  const now = new Date();
  const totalMs = end.getTime() - start.getTime();
  const elapsedMs = now.getTime() - start.getTime();
  const daysLeft = Math.max(0, Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
  const pct = Math.min(100, Math.max(0, (elapsedMs / totalMs) * 100));
  return { daysLeft, pct, label: daysLeft > 0 ? `${daysLeft} ngày còn lại` : 'Quá hạn' };
}

export default function ContractsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [selected, setSelected] = useState<Contract | null>(null);
  const [paymentModal, setPaymentModal] = useState<{ contractId: string; idx: number } | null>(null);
  const [proofUrl, setProofUrl] = useState('');
  const [proofPreview, setProofPreview] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [viewProof, setViewProof] = useState<string | null>(null);
  const [confirmChecked, setConfirmChecked] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const data = extractItems(await api.getContracts());
      setContracts(data);
    } catch { toast('Không thể tải hợp đồng', 'error'); } finally {
      setLoadingData(false);
    }
  }, [toast]);

  useEffect(() => { if (user) void Promise.resolve().then(load); }, [user, load]);

  if (loading || !user) return null;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setProofPreview(reader.result as string);
        setProofUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handlePaymentConfirm = async () => {
    if (!paymentModal || !confirmChecked) return;
    try {
      const updated = await api.updatePayment(paymentModal.contractId, paymentModal.idx, proofUrl || undefined);
      setContracts(prev => prev.map(c => c.id === updated.id ? updated : c));
      setSelected(updated);
      setPaymentModal(null);
      setProofUrl('');
      setProofPreview('');
      setConfirmChecked(false);
      toast('Xác nhận thanh toán thành công!', 'success');
    } catch { toast('Xác nhận thanh toán thất bại', 'error'); }
  };

  const openPaymentModal = (contractId: string, idx: number) => {
    setPaymentModal({ contractId, idx });
    setProofUrl('');
    setProofPreview('');
    setConfirmChecked(false);
  };

  return (
    <Sidebar>
      <div className="p-6 space-y-6 animate-in">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Hợp đồng</h1>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">{contracts.length} hợp đồng</p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Tổng HĐ', value: contracts.length, icon: '📄' },
            { label: 'Đã ký', value: contracts.filter(c => c.status === 'signed').length, icon: '✅' },
            { label: 'Tổng giá trị', value: fmtVND(contracts.reduce((s, c) => s + (c.total_value || 0), 0)), icon: '💰' },
            { label: 'Nháp', value: contracts.filter(c => c.status === 'draft').length, icon: '📝' },
          ].map(card => (
            <div key={card.label} className="rounded-2xl p-4" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{card.icon}</span>
                <span className="text-xs text-[var(--text-muted)]">{card.label}</span>
              </div>
              <p className="text-xl font-bold text-[var(--text-primary)]">{card.value}</p>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
          {loadingData ? (
            <div className="p-12 text-center text-[var(--text-muted)]">Đang tải...</div>
          ) : contracts.length === 0 ? (
            <div className="p-12 text-center text-[var(--text-muted)]">Chưa có hợp đồng nào</div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Mã HĐ</th>
                  <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Tiêu đề</th>
                  <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Trạng thái</th>
                  <th className="text-right px-5 py-3 text-[var(--text-tertiary)] font-medium">Giá trị</th>
                  <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Thanh toán</th>
                  <th className="text-left px-5 py-3 text-[var(--text-tertiary)] font-medium">Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map(c => {
                  const st = STATUS_MAP[c.status] || STATUS_MAP.draft;
                  const paid = c.payment_terms?.installments?.filter(i => i.status === 'paid').length || 0;
                  const total = c.payment_terms?.installments?.length || 0;
                  const timeLeft = calcTimeLeft(c.signed_date, c.working_days);
                  return (
                    <tr
                      key={c.id}
                      className="cursor-pointer transition-colors"
                      style={{ borderBottom: '1px solid var(--border-subtle)' }}
                      onClick={() => setSelected(c)}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td className="px-5 py-3.5 font-mono text-xs text-[var(--gold-400)]">{c.code}</td>
                      <td className="px-5 py-3.5 font-medium text-[var(--text-primary)]">{c.title}</td>
                      <td className="px-5 py-3.5">
                        <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                      </td>
                      <td className="px-5 py-3.5 text-right text-[var(--text-secondary)]">{fmtVND(c.total_value)}</td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-[var(--surface-3)]">
                            <div className="h-full rounded-full" style={{ width: `${total > 0 ? (paid/total)*100 : 0}%`, background: 'var(--gold-500)' }} />
                          </div>
                          <span className="text-xs text-[var(--text-muted)]">{paid}/{total}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        {timeLeft ? (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-[var(--surface-3)]">
                              <div className="h-full rounded-full" style={{
                                width: `${timeLeft.pct}%`,
                                background: timeLeft.daysLeft <= 7 ? '#f87171' : timeLeft.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                              }} />
                            </div>
                            <span className="text-xs text-[var(--text-muted)] whitespace-nowrap">{timeLeft.label}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-[var(--text-muted)]">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>

        {/* Detail modal */}
        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center pt-[6vh] px-4" onClick={() => setSelected(null)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative w-full max-w-2xl mx-4 rounded-2xl p-4 sm:p-6 max-h-[80vh] overflow-y-auto" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <button onClick={() => setSelected(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-[rgba(255,255,255,0.05)]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
              <h2 className="text-xl font-bold text-[var(--text-primary)] mb-1">{selected.title}</h2>
              <p className="text-sm font-mono text-[var(--gold-400)] mb-4">{selected.code}</p>

              {/* Time left bar */}
              {(() => {
                const tl = calcTimeLeft(selected.signed_date, selected.working_days);
                if (!tl) return null;
                return (
                  <div className="rounded-xl p-4 mb-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-[var(--text-muted)]">⏱ Tiến độ thi công</span>
                      <span className="text-sm font-semibold" style={{
                        color: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                      }}>{tl.label}</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-[var(--surface-3)]">
                      <div className="h-full rounded-full transition-all" style={{
                        width: `${tl.pct}%`,
                        background: tl.daysLeft <= 7 ? '#f87171' : tl.daysLeft <= 30 ? '#fbbf24' : '#34d399',
                      }} />
                    </div>
                    <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1">
                      <span>Ngày ký: {selected.signed_date ? new Date(selected.signed_date).toLocaleDateString('vi-VN') : '—'}</span>
                      <span>{selected.working_days} ngày thi công</span>
                    </div>
                  </div>
                );
              })()}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-4 mb-6">
                {[
                  ['Trạng thái', STATUS_MAP[selected.status]?.label || selected.status],
                  ['Giá trị', fmtVND(selected.total_value)],
                  ['Ngày ký', selected.signed_date ? new Date(selected.signed_date).toLocaleDateString('vi-VN') : '—'],
                  ['Số ngày thi công', selected.working_days ? `${selected.working_days} ngày` : '—'],
                ].map(([label, value]) => (
                  <div key={label as string} className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{value}</p>
                  </div>
                ))}
              </div>

              {/* Payment terms */}
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Tiến độ thanh toán</h3>
              <div className="space-y-2">
                {selected.payment_terms?.installments?.map((inst, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl px-4 py-3 cursor-pointer transition-all hover:scale-[1.005]"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                    onClick={() => {
                      if (inst.proof_image) {
                        setViewProof(inst.proof_image);
                      }
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm" style={{
                          background: inst.status === 'paid' ? 'rgba(52,211,153,0.15)' : 'rgba(148,163,184,0.1)',
                          color: inst.status === 'paid' ? '#34d399' : '#94a3b8',
                        }}>
                          {inst.status === 'paid' ? '✓' : idx + 1}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-[var(--text-primary)]">{inst.name}</p>
                          <p className="text-xs text-[var(--text-muted)]">{inst.percentage}% — {fmtVND(selected.total_value ? selected.total_value * inst.percentage / 100 : 0)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {inst.status === 'paid' && inst.proof_image && (
                          <span className="text-xs px-2 py-1 rounded-lg" style={{ background: 'rgba(96,165,250,0.1)', color: '#60a5fa' }}>
                            📷 Có sao kê
                          </span>
                        )}
                        {inst.status === 'pending' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); openPaymentModal(selected.id, idx); }}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                            style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)' }}
                          >
                            Xác nhận TT
                          </button>
                        )}
                        {inst.status === 'paid' && (
                          <span className="text-xs font-medium" style={{ color: '#34d399' }}>
                            Đã thanh toán {inst.paid_date ? `(${new Date(inst.paid_date).toLocaleDateString('vi-VN')})` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Payment proof upload modal */}
        {paymentModal && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center pt-[8vh] px-4" onClick={() => setPaymentModal(null)}>
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
            <div className="relative w-full max-w-md mx-4 rounded-2xl p-4 sm:p-6" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              <button onClick={() => setPaymentModal(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-[rgba(255,255,255,0.05)]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
              <h3 className="text-lg font-bold text-[var(--text-primary)] mb-1">Xác nhận thanh toán</h3>
              <p className="text-sm text-[var(--text-muted)] mb-4">Upload hình sao kê ngân hàng để làm bằng chứng (không bắt buộc)</p>

              {/* File upload */}
              <div
                className="rounded-xl p-6 mb-4 text-center cursor-pointer transition-all hover:border-[var(--gold-500)]"
                style={{ background: 'var(--surface-2)', border: '2px dashed var(--border-subtle)' }}
                onClick={() => fileRef.current?.click()}
              >
                <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileSelect} />
                {proofPreview ? (
                  <img src={proofPreview} alt="Sao kê" className="max-h-48 mx-auto rounded-lg" />
                ) : (
                  <>
                    <svg className="mx-auto mb-2" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    <p className="text-sm text-[var(--text-muted)]">Click để chọn ảnh sao kê</p>
                    <p className="text-xs text-[var(--text-disabled)] mt-1">PNG, JPG tối đa 5MB</p>
                  </>
                )}
              </div>

              {/* URL input as alternative */}
              <div className="mb-4">
                <label className="text-xs text-[var(--text-muted)] mb-1 block">Hoặc dán link ảnh</label>
                <input
                  type="url"
                  placeholder="https://drive.google.com/..."
                  value={proofUrl.startsWith('data:') ? '' : proofUrl}
                  onChange={e => { setProofUrl(e.target.value); setProofPreview(e.target.value); }}
                  className="w-full px-3 py-2 rounded-xl text-sm"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                />
              </div>

              {/* Confirm checkbox */}
              <label className="flex items-center gap-2 mb-4 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={confirmChecked}
                  onChange={e => setConfirmChecked(e.target.checked)}
                  className="w-4 h-4 rounded accent-[var(--gold-500)]"
                />
                <span className="text-sm text-[var(--text-secondary)]">Tôi xác nhận đợt thanh toán này đã được thanh toán</span>
              </label>

              <button
                onClick={handlePaymentConfirm}
                disabled={!confirmChecked}
                className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40"
                style={{ background: confirmChecked ? 'linear-gradient(135deg, var(--gold-500), var(--gold-700))' : 'var(--surface-3)', color: 'white' }}
              >
                ✅ Xác nhận đã thanh toán
              </button>
            </div>
          </div>
        )}

        {/* View proof modal */}
        {viewProof && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center pt-[8vh] px-4" onClick={() => setViewProof(null)}>
            <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <div className="relative max-w-2xl mx-4" onClick={e => e.stopPropagation()}>
              <button onClick={() => setViewProof(null)} className="absolute -top-10 right-0 p-1 rounded-lg text-white hover:bg-white/10">
                ✕ Đóng
              </button>
              <img src={viewProof} alt="Sao kê thanh toán" className="max-h-[80vh] rounded-2xl border" style={{ borderColor: 'var(--border-subtle)' }} />
            </div>
          </div>
        )}
      </div>
    </Sidebar>
  );
}
