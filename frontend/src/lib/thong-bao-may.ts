/**
 * Thông báo đẩy trên máy đang dùng (Web Push) — logic dùng chung (tách 21/11/2026 từ
 * components/BatThongBaoMay.tsx để banner «Bật thông báo» trong app, trang /cai-app và
 * khung chuông dùng lại, không chép code).
 *
 * Trạng thái được giữ CHUNG cho mọi chỗ đang hiện (store nhỏ trong mô-đun): bật ở trang
 * /cai-app thì banner nhắc và khung chuông cũng đổi theo ngay.
 */

import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { api } from '@/lib/api';
import { dangChayDangApp, laIOS } from '@/lib/cai-app';

export type TrangThaiThongBao = 'dang-tai' | 'khong-ho-tro' | 'can-cai-ios' | 'chua-cau-hinh' | 'bi-chan' | 'tat' | 'bat';

function base64UrlToUint8Array(base64: string) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function dangKySW() {
  return navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' });
}

/** Trình duyệt có đủ API thông báo đẩy không (iPhone/iPad chỉ có khi mở từ màn hình chính, iOS 16.4+). */
export function hoTroThongBaoDay(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

/** Đọc trạng thái thật của máy. Đã bật thì gửi lại đăng ký để máy luôn gắn đúng người đang đăng nhập. */
export async function docTrangThaiThongBao(): Promise<TrangThaiThongBao> {
  if (!hoTroThongBaoDay()) return laIOS() && !dangChayDangApp() ? 'can-cai-ios' : 'khong-ho-tro';
  try {
    const k = await api.pushPublicKey();
    if (!k.enabled || !k.public_key) return 'chua-cau-hinh';
  } catch {
    return 'chua-cau-hinh';
  }
  if (Notification.permission === 'denied') return 'bi-chan';
  const reg = await navigator.serviceWorker.getRegistration('/');
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (sub) {
    api.pushSubscribe(sub.toJSON()).catch(() => {});
    return 'bat';
  }
  return 'tat';
}

/** Xin quyền + đăng ký nhận thông báo đẩy. Ném lỗi khi trình duyệt / máy chủ từ chối. */
export async function batThongBao(): Promise<TrangThaiThongBao> {
  const quyen = await Notification.requestPermission();
  if (quyen !== 'granted') return quyen === 'denied' ? 'bi-chan' : 'tat';
  const { public_key } = await api.pushPublicKey();
  if (!public_key) return 'chua-cau-hinh';
  const reg = await dangKySW();
  await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: base64UrlToUint8Array(public_key),
  });
  await api.pushSubscribe(sub.toJSON());
  return 'bat';
}

/** Gỡ đăng ký trên máy này (máy chủ xoá luôn để khỏi đẩy vào máy đã tắt). */
export async function tatThongBao(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration('/');
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (sub) {
    await api.pushUnsubscribe(sub.endpoint).catch(() => {});
    await sub.unsubscribe();
  }
}

// ── Store trạng thái dùng chung ──────────────────────────────────────────
let ttChung: TrangThaiThongBao = 'dang-tai';
const ngheTT = new Set<() => void>();
let dangKiem: Promise<void> | null = null;

function datTT(t: TrangThaiThongBao) {
  ttChung = t;
  for (const f of ngheTT) f();
}

function dangKyTT(f: () => void) {
  ngheTT.add(f);
  return () => { ngheTT.delete(f); };
}

/** Kiểm lại trạng thái; nhiều chỗ gọi cùng lúc thì chỉ chạy 1 lượt. */
export function kiemTraThongBao(): Promise<void> {
  if (!dangKiem) {
    dangKiem = docTrangThaiThongBao()
      .then(datTT, () => datTT('khong-ho-tro'))
      .finally(() => { dangKiem = null; });
  }
  return dangKiem;
}

/** Hook cho mọi chỗ hiện / bật / tắt thông báo trên máy này. */
export function useThongBaoMay() {
  const tt = useSyncExternalStore(dangKyTT, () => ttChung, () => 'dang-tai' as TrangThaiThongBao);
  const [dangLam, setDangLam] = useState(false);
  const [loi, setLoi] = useState('');

  useEffect(() => {
    void kiemTraThongBao();
  }, []);

  const bat = useCallback(async (): Promise<TrangThaiThongBao | null> => {
    setDangLam(true);
    setLoi('');
    try {
      const t = await batThongBao();
      datTT(t);
      return t;
    } catch (e) {
      setLoi(e instanceof Error ? e.message : 'Không bật được thông báo');
      return null;
    } finally {
      setDangLam(false);
    }
  }, []);

  const tat = useCallback(async () => {
    setDangLam(true);
    setLoi('');
    try {
      await tatThongBao();
      datTT('tat');
    } finally {
      setDangLam(false);
    }
  }, []);

  return { tt, dangLam, loi, setLoi, bat, tat };
}
