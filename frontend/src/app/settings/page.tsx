'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import { api, AutomationSettings, AISettingsResponse, BackupSettingsResponse } from '@/lib/api';

const AUTOMATION_ROLES = ['admin', 'executive'];

function BackupSection() {
  const [data, setData] = useState<BackupSettingsResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [showGdriveSetup, setShowGdriveSetup] = useState(false);
  const [form, setForm] = useState({
    backup_enabled: true,
    backup_hour: 5,
    backup_retention_days: 180,
    gdrive_client_id: '',
    gdrive_client_secret: '',
  });

  const load = useCallback(() => {
    api.getBackupSettings().then(s => {
      setData(s);
      setForm(f => ({
        ...f,
        backup_enabled: s.backup_enabled === 'true',
        backup_hour: parseInt(s.backup_hour, 10) || 5,
        backup_retention_days: parseInt(s.backup_retention_days, 10) || 180,
      }));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    // Sau khi OAuth Google redirect về ?gdrive=connected|error
    const params = new URLSearchParams(window.location.search);
    const gdrive = params.get('gdrive');
    if (gdrive === 'connected') setMessage('✅ Đã kết nối Google Drive thành công');
    if (gdrive === 'error') setMessage('❌ Kết nối Google Drive thất bại — thử lại');
    if (gdrive) window.history.replaceState(null, '', '/settings');
  }, [load]);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload: Record<string, unknown> = {
        backup_enabled: form.backup_enabled,
        backup_hour: form.backup_hour,
        backup_retention_days: form.backup_retention_days,
      };
      if (form.gdrive_client_id) payload.gdrive_client_id = form.gdrive_client_id;
      if (form.gdrive_client_secret) payload.gdrive_client_secret = form.gdrive_client_secret;
      const updated = await api.updateBackupSettings(payload);
      setData(updated);
      setForm(f => ({ ...f, gdrive_client_secret: '' }));
      setMessage('✅ Đã lưu cài đặt sao lưu');
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi lưu cài đặt'}`);
    } finally {
      setSaving(false);
    }
  }, [form]);

  const backupNow = useCallback(async () => {
    setMessage('⏳ Đang sao lưu...');
    try {
      const res = await api.runBackupNow();
      if (res.status === 'completed') {
        setMessage(`✅ Đã sao lưu: ${res.file} (${res.size_mb} MB)${res.gdrive_uploaded ? ' + Google Drive ☁️' : ''}`);
      } else {
        setMessage(`⚠️ ${res.reason || res.status}`);
      }
      load();
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi sao lưu'}`);
    }
  }, [load]);

  const connectGdrive = useCallback(async () => {
    setMessage('');
    try {
      const { auth_url } = await api.getGdriveAuthUrl();
      window.location.href = auth_url; // sang trang consent của Google
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Chưa cấu hình Client ID/Secret'}`);
      setShowGdriveSetup(true);
    }
  }, []);

  const disconnectGdrive = useCallback(async () => {
    try {
      await api.disconnectGdrive();
      setMessage('✅ Đã ngắt kết nối Google Drive');
      load();
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi'}`);
    }
  }, [load]);

  if (!data) return null;

  const inputCls = 'w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-[#C9A96E]';

  const toggle = (checked: boolean, onChange: (v: boolean) => void) => (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition-colors ${checked ? 'bg-[#C9A96E]' : 'bg-white/10'}`}
      aria-checked={checked}
      role="switch"
    >
      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  );

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold mb-1">💾 Sao lưu dữ liệu tự động</h2>
      <p className="text-xs text-[var(--text-muted)] mb-4">
        Sao lưu toàn bộ database mỗi sáng, lưu local + Google Drive. Tự xóa bản cũ quá thời gian lưu trữ (tối đa {data.max_retention_days} ngày).
      </p>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Sao lưu hàng ngày</p>
            <p className="text-xs text-[var(--text-muted)]">
              {data.last_run
                ? `Lần gần nhất: ${new Date(data.last_run).toLocaleString('vi-VN')} · Đang giữ ${data.local_backup_count} bản local`
                : 'Chưa chạy lần nào'}
            </p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <span className="text-sm text-[var(--text-secondary)]">lúc</span>
            <input
              type="number" min={0} max={23} value={form.backup_hour}
              onChange={e => setForm(f => ({ ...f, backup_hour: Math.max(0, Math.min(23, parseInt(e.target.value, 10) || 0)) }))}
              className="w-20 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-sm text-right focus:outline-none focus:border-[#C9A96E]"
            />
            <span className="text-sm text-[var(--text-secondary)]">giờ sáng</span>
            {toggle(form.backup_enabled, v => setForm(f => ({ ...f, backup_enabled: v })))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Thời gian lưu trữ</p>
            <p className="text-xs text-[var(--text-muted)]">Bản backup cũ hơn sẽ tự xóa (cả local và Google Drive)</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <input
              type="number" min={1} max={data.max_retention_days} value={form.backup_retention_days}
              onChange={e => setForm(f => ({ ...f, backup_retention_days: Math.max(1, Math.min(data.max_retention_days, parseInt(e.target.value, 10) || 1)) }))}
              className="w-20 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-sm text-right focus:outline-none focus:border-[#C9A96E]"
            />
            <span className="text-sm text-[var(--text-secondary)]">ngày (max {data.max_retention_days})</span>
          </div>
        </div>

        <div className="pt-3 border-t border-white/5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm">☁️ Google Drive</p>
              <p className="text-xs text-[var(--text-muted)]">
                {data.gdrive_connected
                  ? `Đã kết nối${data.gdrive_account_email ? `: ${data.gdrive_account_email}` : ''} — backup tự upload vào thư mục JAMA-CRM-Backups`
                  : 'Chưa kết nối — backup chỉ lưu local'}
              </p>
            </div>
            <div className="flex-shrink-0">
              {data.gdrive_connected ? (
                <button onClick={disconnectGdrive} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10">
                  Ngắt kết nối
                </button>
              ) : (
                <button onClick={connectGdrive} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10">
                  🔗 Kết nối Google Drive
                </button>
              )}
            </div>
          </div>

          {!data.gdrive_connected && (
            <button
              onClick={() => setShowGdriveSetup(s => !s)}
              className="mt-2 text-xs text-[var(--text-muted)] underline"
            >
              {showGdriveSetup ? 'Ẩn cấu hình OAuth' : 'Cấu hình OAuth Client (làm 1 lần)'}
            </button>
          )}

          {showGdriveSetup && !data.gdrive_connected && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-[var(--text-muted)]">
                Tạo OAuth Client tại console.cloud.google.com → APIs &amp; Services → Credentials → Create OAuth client ID (Web application).
                Thêm Redirect URI: <span className="font-mono text-[var(--text-secondary)]">[API_BASE_URL]/api/v1/backup/gdrive/callback</span>
              </p>
              <input
                type="text" value={form.gdrive_client_id}
                onChange={e => setForm(f => ({ ...f, gdrive_client_id: e.target.value.trim() }))}
                placeholder={data.gdrive_client_id_set ? 'Client ID (đã lưu — nhập để thay đổi)' : 'Google OAuth Client ID'}
                className={`${inputCls} font-mono text-xs`}
              />
              <input
                type="password" value={form.gdrive_client_secret}
                onChange={e => setForm(f => ({ ...f, gdrive_client_secret: e.target.value.trim() }))}
                placeholder="Google OAuth Client Secret"
                className={inputCls}
              />
              <p className="text-xs text-[var(--text-muted)]">Bấm <b>Lưu cài đặt</b> rồi bấm <b>🔗 Kết nối Google Drive</b>.</p>
            </div>
          )}
        </div>

        {data.local_backups.length > 0 && (
          <div className="pt-3 border-t border-white/5">
            <p className="text-sm mb-2">🗂️ Bản sao lưu gần nhất</p>
            <div className="space-y-1 max-h-36 overflow-y-auto">
              {data.local_backups.map(b => (
                <div key={b.name} className="flex justify-between text-xs text-[var(--text-muted)] font-mono">
                  <span>{b.name}</span>
                  <span>{(b.size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 pt-2 border-t border-white/5 flex-wrap">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-xl bg-[#C9A96E] text-black text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Đang lưu...' : 'Lưu cài đặt'}
          </button>
          <button
            onClick={backupNow}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm hover:bg-white/10"
          >
            💾 Sao lưu ngay
          </button>
          {message && <span className="text-xs text-[var(--text-secondary)]">{message}</span>}
        </div>
      </div>
    </div>
  );
}

function AISettingsSection() {
  const [data, setData] = useState<AISettingsResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({
    llm_model: '',
    llm_api_key: '',
    llm_fallback_model: '',
    llm_fallback_api_key: '',
  });

  useEffect(() => {
    api.getAISettings().then(s => {
      setData(s);
      setForm(f => ({
        ...f,
        llm_model: s.llm_model,
        llm_fallback_model: s.llm_fallback_model,
      }));
    }).catch(() => {});
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload: Record<string, string> = {
        llm_model: form.llm_model,
        llm_fallback_model: form.llm_fallback_model,
      };
      // Chỉ gửi key khi người dùng nhập mới (tránh ghi đè bằng chuỗi rỗng)
      if (form.llm_api_key) payload.llm_api_key = form.llm_api_key;
      if (form.llm_fallback_api_key) payload.llm_fallback_api_key = form.llm_fallback_api_key;

      const updated = await api.updateAISettings(payload);
      setData(updated);
      setForm(f => ({ ...f, llm_api_key: '', llm_fallback_api_key: '' }));
      setMessage('✅ Đã lưu — áp dụng ngay cho toàn bộ AI agents & bot Telegram');
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi lưu cài đặt'}`);
    } finally {
      setSaving(false);
    }
  }, [form]);

  const test = useCallback(async () => {
    setTesting(true);
    setMessage('⏳ Đang test kết nối AI...');
    try {
      const res = await api.testAIConnection();
      if (res.status === 'ok') {
        setMessage(`✅ Model "${res.model}" phản hồi: "${res.reply}"`);
      } else {
        setMessage(`❌ Lỗi kết nối: ${res.detail}`);
      }
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi test'}`);
    } finally {
      setTesting(false);
    }
  }, []);

  if (!data) return null;

  const inputCls = 'w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-[#C9A96E]';

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold mb-1">🧠 Cấu hình AI Model (toàn hệ thống)</h2>
      <p className="text-xs text-[var(--text-muted)] mb-4">
        Áp dụng cho 5 AI agents và toàn bộ bot Telegram của mọi role. Model chính lỗi/hết quota → tự chuyển sang model dự phòng → hết thì dùng rule-based.
      </p>

      <div className="space-y-4">
        <div>
          <label className="text-sm block mb-1">Model chính (khuyến nghị chọn model free)</label>
          <select
            value={data.presets.some(p => p.model === form.llm_model) ? form.llm_model : '_custom'}
            onChange={e => {
              if (e.target.value !== '_custom') setForm(f => ({ ...f, llm_model: e.target.value }));
            }}
            className={inputCls}
          >
            {data.presets.map(p => (
              <option key={p.model} value={p.model}>{p.label}</option>
            ))}
            <option value="_custom">Tùy chỉnh (nhập bên dưới)</option>
          </select>
          <input
            type="text"
            value={form.llm_model}
            onChange={e => setForm(f => ({ ...f, llm_model: e.target.value }))}
            placeholder="vd: groq/llama-3.3-70b-versatile"
            className={`${inputCls} mt-2 font-mono text-xs`}
          />
        </div>

        <div>
          <label className="text-sm block mb-1">
            API Key chính {data.llm_api_key_set && <span className="text-xs text-[var(--text-muted)]">(hiện tại: {data.llm_api_key_masked})</span>}
          </label>
          <input
            type="password"
            value={form.llm_api_key}
            onChange={e => setForm(f => ({ ...f, llm_api_key: e.target.value }))}
            placeholder={data.llm_api_key_set ? 'Nhập key mới để thay đổi' : 'Dán API key (Groq/Gemini/OpenRouter...)'}
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-sm block mb-1">Model dự phòng (fallback)</label>
            <input
              type="text"
              value={form.llm_fallback_model}
              onChange={e => setForm(f => ({ ...f, llm_fallback_model: e.target.value }))}
              placeholder="vd: gemini/gemini-2.0-flash"
              className={`${inputCls} font-mono text-xs`}
            />
          </div>
          <div>
            <label className="text-sm block mb-1">
              API Key dự phòng {data.llm_fallback_api_key_set && <span className="text-xs text-[var(--text-muted)]">({data.llm_fallback_api_key_masked})</span>}
            </label>
            <input
              type="password"
              value={form.llm_fallback_api_key}
              onChange={e => setForm(f => ({ ...f, llm_fallback_api_key: e.target.value }))}
              placeholder="Trống = dùng key chính"
              className={inputCls}
            />
          </div>
        </div>

        <div className="flex items-center gap-2 pt-2 border-t border-white/5 flex-wrap">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-xl bg-[#C9A96E] text-black text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Đang lưu...' : 'Lưu cấu hình AI'}
          </button>
          <button
            onClick={test}
            disabled={testing}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm hover:bg-white/10 disabled:opacity-50"
          >
            🔌 Test kết nối
          </button>
        </div>
        {message && <p className="text-xs text-[var(--text-secondary)]">{message}</p>}
      </div>
    </div>
  );
}

function AutomationSection() {
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({
    followup_reminder_days: 3,
    lead_recall_days: 7,
    lead_recall_enabled: true,
    payment_reminder_days: 3,
    bod_report_enabled: true,
    bod_report_hour: 8,
    telegram_group_chat_id: '',
    group_briefing_enabled: true,
  });

  useEffect(() => {
    api.getAutomationSettings().then(s => {
      setSettings(s);
      setForm({
        followup_reminder_days: parseInt(s.followup_reminder_days, 10) || 3,
        lead_recall_days: parseInt(s.lead_recall_days, 10) || 7,
        lead_recall_enabled: s.lead_recall_enabled === 'true',
        payment_reminder_days: parseInt(s.payment_reminder_days, 10) || 3,
        bod_report_enabled: s.bod_report_enabled === 'true',
        bod_report_hour: parseInt(s.bod_report_hour, 10) || 8,
        telegram_group_chat_id: s.telegram_group_chat_id || '',
        group_briefing_enabled: s.group_briefing_enabled !== 'false',
      });
    }).catch(() => {});
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage('');
    try {
      await api.updateAutomationSettings(form);
      setMessage('✅ Đã lưu cài đặt');
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi lưu cài đặt'}`);
    } finally {
      setSaving(false);
    }
  }, [form]);

  const runNow = useCallback(async () => {
    setMessage('⏳ Đang chạy automation...');
    try {
      await api.runAutomation('all');
      setMessage('✅ Đã chạy automation (nhắc CSKH, thu hồi lead, nhắc thanh toán)');
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi'}`);
    }
  }, []);

  const sendReport = useCallback(async () => {
    setMessage('⏳ Đang gửi báo cáo...');
    try {
      await api.sendBodReport('daily');
      setMessage('✅ Đã gửi báo cáo ngày cho BOD');
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi'}`);
    }
  }, []);

  const sendGroupBriefing = useCallback(async () => {
    setMessage('⏳ Đang gửi briefing vào nhóm...');
    try {
      const res = await api.sendGroupBriefing();
      if (res.status === 'completed') setMessage('✅ Đã gửi briefing vào nhóm Telegram');
      else setMessage(`⚠️ Không gửi được: ${res.reason || res.status} — kiểm tra Chat ID nhóm & bot đã vào nhóm chưa`);
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : 'Lỗi'}`);
    }
  }, []);

  if (!settings) return null;

  const numInput = (value: number, onChange: (v: number) => void, min: number, max: number) => (
    <input
      type="number"
      min={min}
      max={max}
      value={value}
      onChange={e => onChange(Math.max(min, Math.min(max, parseInt(e.target.value, 10) || min)))}
      className="w-20 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-sm text-right focus:outline-none focus:border-[#C9A96E]"
    />
  );

  const toggle = (checked: boolean, onChange: (v: boolean) => void) => (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition-colors ${checked ? 'bg-[#C9A96E]' : 'bg-white/10'}`}
      aria-checked={checked}
      role="switch"
    >
      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  );

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold mb-1">🤖 Tự động hóa CSKH & Báo cáo</h2>
      <p className="text-xs text-[var(--text-muted)] mb-4">
        Hệ thống tự động nhắc chăm sóc khách hàng, thu hồi lead quá hạn và gửi báo cáo BOD hàng ngày.
      </p>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Nhắc chăm sóc KH sau</p>
            <p className="text-xs text-[var(--text-muted)]">Gửi nhắc nhở khi lead chưa được liên hệ</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {numInput(form.followup_reminder_days, v => setForm(f => ({ ...f, followup_reminder_days: v })), 1, 90)}
            <span className="text-sm text-[var(--text-secondary)]">ngày</span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Thu hồi lead quá hạn</p>
            <p className="text-xs text-[var(--text-muted)]">Tự động chuyển lead cho sale khác khi quá hạn chăm sóc</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {numInput(form.lead_recall_days, v => setForm(f => ({ ...f, lead_recall_days: v })), 1, 90)}
            <span className="text-sm text-[var(--text-secondary)]">ngày</span>
            {toggle(form.lead_recall_enabled, v => setForm(f => ({ ...f, lead_recall_enabled: v })))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Nhắc thanh toán hợp đồng</p>
            <p className="text-xs text-[var(--text-muted)]">Nhắc kế toán các đợt thanh toán còn pending</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {numInput(form.payment_reminder_days, v => setForm(f => ({ ...f, payment_reminder_days: v })), 1, 90)}
            <span className="text-sm text-[var(--text-secondary)]">ngày sau ký</span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm">Báo cáo BOD tự động</p>
            <p className="text-xs text-[var(--text-muted)]">Gửi hàng ngày · thứ Hai (tuần) · mùng 1 (tháng) qua Telegram</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <span className="text-sm text-[var(--text-secondary)]">lúc</span>
            {numInput(form.bod_report_hour, v => setForm(f => ({ ...f, bod_report_hour: v })), 0, 23)}
            <span className="text-sm text-[var(--text-secondary)]">giờ</span>
            {toggle(form.bod_report_enabled, v => setForm(f => ({ ...f, bod_report_enabled: v })))}
          </div>
        </div>

        <div className="pt-3 border-t border-white/5">
          <div className="flex items-center justify-between gap-4 mb-2">
            <div>
              <p className="text-sm">📢 Nhóm Telegram công ty</p>
              <p className="text-xs text-[var(--text-muted)]">
                Bot gửi briefing công việc hàng ngày vào nhóm (không kèm số liệu tài chính)
              </p>
            </div>
            {toggle(form.group_briefing_enabled, v => setForm(f => ({ ...f, group_briefing_enabled: v })))}
          </div>
          <input
            type="text"
            value={form.telegram_group_chat_id}
            onChange={e => setForm(f => ({ ...f, telegram_group_chat_id: e.target.value.trim() }))}
            placeholder="Chat ID nhóm, vd: -1001234567890 (gõ /id trong nhóm để lấy)"
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-mono focus:outline-none focus:border-[#C9A96E]"
          />
        </div>

        <div className="flex items-center gap-2 pt-2 border-t border-white/5 flex-wrap">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-xl bg-[#C9A96E] text-black text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Đang lưu...' : 'Lưu cài đặt'}
          </button>
          <button
            onClick={runNow}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm hover:bg-white/10"
          >
            ▶️ Chạy ngay
          </button>
          <button
            onClick={sendReport}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm hover:bg-white/10"
          >
            📊 Gửi báo cáo ngày
          </button>
          <button
            onClick={sendGroupBriefing}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm hover:bg-white/10"
          >
            📢 Gửi briefing nhóm
          </button>
          {message && <span className="text-xs text-[var(--text-secondary)]">{message}</span>}
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <Sidebar>
      <div className="p-6 animate-in">
        <h1 className="text-2xl font-bold mb-6">⚙️ Cài đặt</h1>

        <div className="max-w-2xl space-y-6">
          {/* Profile */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">Thông tin cá nhân</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#C9A96E] to-[#1A535C] flex items-center justify-center">
                  <span className="text-2xl font-bold text-white">{user.full_name?.charAt(0)}</span>
                </div>
                <div>
                  <p className="font-semibold text-lg">{user.full_name}</p>
                  <p className="text-sm text-[var(--text-secondary)]">{user.email}</p>
                  <p className="text-xs text-[var(--text-muted)] capitalize mt-0.5">
                    {user.role} · {user.department}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* AI Model config — admin only */}
          {user.role === 'admin' && <AISettingsSection />}

          {/* Backup — admin only */}
          {user.role === 'admin' && <BackupSection />}

          {/* Automation — admin/executive only */}
          {AUTOMATION_ROLES.includes(user.role) && <AutomationSection />}

          {/* Telegram */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">🤖 Telegram Bot</h2>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">Telegram ID</span>
                <span className="text-sm font-mono">
                  {user.telegram_user_id || '— Chưa liên kết'}
                </span>
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Liên kết Telegram để nhận briefing hàng ngày và nhập lead qua bot.
              </p>
            </div>
          </div>

          {/* System */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">Hệ thống</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Phiên bản</span>
                <span className="font-mono">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Backend</span>
                <span className="font-mono">FastAPI</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">AI Model</span>
                <span className="font-mono text-xs">Cấu hình tại mục &quot;Cấu hình AI Model&quot;</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Sidebar>
  );
}
