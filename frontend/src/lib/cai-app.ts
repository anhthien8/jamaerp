/**
 * Cài JAMA HOME lên điện thoại (PWA) — phần dùng chung cho InstallBanner, trang /cai-app
 * và các chỗ nhắc bật thông báo (21/11/2026).
 *
 * Trình duyệt chỉ bắn `beforeinstallprompt` MỘT lần mỗi lần tải trang. Trước đây chỉ
 * InstallBanner bắt sự kiện này nên trang /cai-app (mở bằng điều hướng trong app) không
 * bao giờ có hộp cài thật. Nay bắt 1 lần ngay khi mô-đun được nạp, ai cần thì đọc qua
 * `useCoHopCai()` / `moHopCai()`.
 */

import { useSyncExternalStore } from 'react';

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let hopCai: BeforeInstallPromptEvent | null = null;
let vuaCai = false;
const nguoiNghe = new Set<() => void>();

function baoDoi() {
  for (const f of nguoiNghe) f();
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault(); // tự hiện nút cài của JAMA thay cho thanh mặc định của trình duyệt
    hopCai = e as BeforeInstallPromptEvent;
    baoDoi();
  });
  window.addEventListener('appinstalled', () => {
    hopCai = null;
    vuaCai = true;
    baoDoi();
  });
}

function dangKy(f: () => void) {
  nguoiNghe.add(f);
  return () => { nguoiNghe.delete(f); };
}

/** Trình duyệt đang cho hộp cài thật (Android Chrome / Samsung Internet, Chrome–Edge máy tính). */
export function useCoHopCai(): boolean {
  return useSyncExternalStore(dangKy, () => hopCai !== null, () => false);
}

/** Vừa cài xong trong lần mở trang này (sự kiện `appinstalled`). */
export function useVuaCaiApp(): boolean {
  return useSyncExternalStore(dangKy, () => vuaCai, () => false);
}

/** Mở hộp cài thật. 'khong-co' = trình duyệt chưa cho (iPhone/iPad, đã cài, hoặc chưa đủ điều kiện). */
export async function moHopCai(): Promise<'accepted' | 'dismissed' | 'khong-co'> {
  const ev = hopCai;
  if (!ev) return 'khong-co';
  hopCai = null; // mỗi sự kiện chỉ gọi prompt() được 1 lần
  baoDoi();
  await ev.prompt();
  const kq = await ev.userChoice;
  return kq.outcome;
}

export function laIOS(): boolean {
  const ua = navigator.userAgent;
  // iPadOS 13+ tự xưng «Macintosh» — nhận ra bằng màn cảm ứng.
  return /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
}

export function laAndroid(): boolean {
  return /Android/i.test(navigator.userAgent);
}

export function laMayDiDong(): boolean {
  return laIOS() || /Android|Mobi/i.test(navigator.userAgent);
}

/** Đang chạy dạng app đã cài (mở từ icon ngoài màn hình chính). */
export function dangChayDangApp(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/** Trình duyệt nhúng trong Zalo / Telegram / Facebook / Messenger / Instagram — không cài app
 *  được ở đây, cũng không có phiên đăng nhập của Chrome/Safari. Tin nhắc «Nhắc trưởng phòng»
 *  và «Cài app» đi qua Telegram nên link hay mở ở trình duyệt riêng của Telegram
 *  (Android ghi «Telegram-Android» trong user agent; bản iOS dùng khung Safari thì không nhận ra được). */
export function laTrinhDuyetNhung(): boolean {
  return /Zalo|FBAN|FBAV|FB_IAB|Messenger|Instagram|Line\/|Telegram/i.test(navigator.userAgent);
}
