'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import LineIcon from '@/components/ui/LineIcon';
import { useAuth } from '@/lib/auth';
import { dangChayDangApp, laIOS, laMayDiDong, moHopCai, useCoHopCai, useVuaCaiApp } from '@/lib/cai-app';

/**
 * InstallBanner — thanh «Cài JAMA HOME lên điện thoại» (22/07, làm lại 23/10/2026).
 * - Bấm cả thanh là cài: Android/Samsung (Chrome, Samsung Internet) gọi hộp cài THẬT qua
 *   beforeinstallprompt; iOS/iPadOS không có API → mở bảng hướng dẫn 3 bước có hình nút.
 * - Trang đăng nhập: hiện NGAY, sát đáy (không có thanh menu dưới), kể cả khi trước đó
 *   đã bấm «Để sau» ở trong app — đây là lúc người mới mở web lần đầu.
 * - Trong app: «Để sau» ẩn 7 ngày (bản cũ ẩn vĩnh viễn nên nhân viên lỡ bấm là mất luôn).
 * - Ẩn hẳn khi đang chạy dạng app (standalone) hoặc trên máy tính.
 * - 21/11/2026: /doi-chieu (đích của tin nhắc, có thanh nút dính đáy) KHÔNG ẩn nữa mà hiện
 *   ở ĐẦU TRANG, trong dòng nội dung (bản `trongTrang` gắn ở AppShell, ngay trên nội dung
 *   trang) — không `fixed` nên không đè tiêu đề «Đối chiếu …» / ô «Chọn phòng», cuộn là qua.
 *   /cai-app thì ẩn (trang đó đã có nút cài). Hộp cài thật bắt chung ở lib/cai-app.ts.
 *   Link «Xem hướng dẫn» (→ /cai-app, trang cần đăng nhập) chỉ hiện cho người ĐÃ đăng nhập
 *   ở trang trong app — không hiện cho khách ở /portal, /bao-gia hay ở /login.
 */

const KEY_HOAN = 'jama_install_snooze_until';
const KEY_AN_PHIEN = 'jama_install_an_phien';
const BAY_NGAY = 7 * 24 * 60 * 60 * 1000;

/** Trang có thanh nút dính ở đáy → banner nằm ở đầu trang (trong dòng nội dung) thay vì đáy. */
const TRANG_BANNER_TREN = ['/doi-chieu'];
/** Trang không có khung app (khớp KHONG_KHUNG ở components/layout/Sidebar.tsx). */
const TRANG_NGOAI_APP = ['/login', '/portal', '/bao-gia'];

/**
 * `trongTrang`: bản vẽ trong dòng nội dung, AppShell gắn ở đầu <main> — chỉ hiện ở
 * TRANG_BANNER_TREN. Bản mặc định (root layout) là thanh `fixed` ở đáy, ẩn ở các trang đó.
 */
export default function InstallBanner({ trongTrang = false }: { trongTrang?: boolean }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const laTrangLogin = pathname === '/login';
  const oTren = TRANG_BANNER_TREN.includes(pathname);
  const moiXemHuongDan = !!user && !TRANG_NGOAI_APP.some(p => pathname.startsWith(p));
  const [sanSang, setSanSang] = useState(false); // đủ điều kiện hiện (mobile, chưa cài)
  const [hoan, setHoan] = useState(false);
  const [anPhienNay, setAnPhienNay] = useState(false);
  const [moHuongDan, setMoHuongDan] = useState(false);
  const [ios, setIos] = useState(false);
  const coHopCai = useCoHopCai();
  const vuaCai = useVuaCaiApp();

  useEffect(() => {
    if (dangChayDangApp() || !laMayDiDong()) return;
    void Promise.resolve().then(() => {
      setIos(laIOS());
      setSanSang(true);
    });
  }, []);

  // Đọc lại «Để sau» mỗi lần đổi trang: có 2 bản (đầu trang /doi-chieu và đáy các trang khác),
  // bấm «Để sau» ở bản này thì bản kia cũng phải ẩn khi chuyển trang.
  useEffect(() => {
    void Promise.resolve().then(() => {
      setHoan(Number(localStorage.getItem(KEY_HOAN) || 0) > Date.now());
      setAnPhienNay(sessionStorage.getItem(KEY_AN_PHIEN) === '1');
    });
  }, [pathname]);

  const deSau = () => {
    setHoan(true);
    setAnPhienNay(true);
    localStorage.setItem(KEY_HOAN, String(Date.now() + BAY_NGAY));
    sessionStorage.setItem(KEY_AN_PHIEN, '1');
  };

  const cai = async () => {
    const kq = await moHopCai();
    if (kq === 'accepted') setSanSang(false);
    else if (kq === 'khong-co') setMoHuongDan(true); // iOS, hoặc trình duyệt chưa cho hộp cài → hướng dẫn tay
  };

  if (oTren !== trongTrang) return null; // mỗi trang chỉ 1 bản: đầu trang hoặc đáy
  if (!sanSang || vuaCai || pathname === '/cai-app') return null;
  // Trang đăng nhập bỏ qua «Để sau» 7 ngày, chỉ ẩn khi vừa bấm «Để sau» trong phiên này.
  if (laTrangLogin ? anPhienNay : hoan) return null;

  return (
    <>
      <div
        className={trongTrang
          // Trong dòng nội dung, ngay trên trang — đẩy nội dung xuống chứ không đè.
          ? 'mx-4 mt-3 px-3 py-3 rounded-2xl animate-in'
          : `fixed left-0 right-0 z-[45] px-3 pt-3 animate-in ${laTrangLogin ? 'bottom-0' : 'bottom-16'}`}
        style={trongTrang
          ? { background: '#14161C', border: '1px solid rgba(201,169,110,0.35)' }
          : {
            paddingBottom: laTrangLogin ? 'calc(12px + env(safe-area-inset-bottom))' : 12,
            background: '#14161C',
            borderTop: '1px solid rgba(201,169,110,0.35)',
          }}
      >
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={() => void cai()}
            className="flex-1 min-w-0 flex items-center gap-3 text-left"
            aria-label="Lưu JAMA HOME thành app trên màn hình chính"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon-192.png" alt="" className="w-11 h-11 rounded-xl flex-shrink-0" style={{ border: '1px solid rgba(201,169,110,0.3)' }} />
            <span className="flex-1 min-w-0">
              <span className="block text-[13px] font-semibold text-white">Cài JAMA HOME lên điện thoại</span>
              <span className="block text-[11px] leading-snug" style={{ color: '#B8B0A0' }}>
                Có icon ngoài màn hình chính, nhận nhắc việc ngay trên máy
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={() => void cai()}
            className="flex-shrink-0 text-[13px] font-semibold px-4 rounded-full"
            style={{ background: '#C9A96E', color: '#0B0D11', minHeight: 44 }}
          >
            {coHopCai ? 'Cài đặt' : 'Thêm'}
          </button>
          <button
            type="button"
            onClick={deSau}
            className="flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center"
            style={{ border: '1px solid rgba(255,255,255,0.12)' }}
            aria-label="Để sau"
          >
            <LineIcon name="x" size={16} color="#B8B0A0" />
          </button>
        </div>
      </div>

      {moHuongDan && (
        <div className="fixed inset-0 z-[110] flex items-end justify-center" onClick={() => setMoHuongDan(false)}>
          <div className="absolute inset-0 bg-black/60" />
          <div
            className="relative w-full max-w-lg rounded-t-3xl p-5 animate-slideUpSheet"
            style={{ background: '#14161C', borderTop: '1px solid rgba(201,169,110,0.35)', paddingBottom: 'calc(20px + env(safe-area-inset-bottom))' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 rounded-full mx-auto mb-4" style={{ background: 'rgba(255,255,255,0.2)' }} />
            <p className="text-base font-semibold text-white mb-4">Thêm JAMA HOME ra màn hình chính</p>
            <ol className="space-y-3 text-sm" style={{ color: '#D8D2C4' }}>
              {ios ? (
                <>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>1</span>
                    <span>Bấm nút <b className="text-white">Chia sẻ</b>{' '}
                      <svg className="inline -mt-1" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4DA3FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>
                      {' '}ở thanh dưới (iPhone) hoặc góc trên (iPad) của Safari</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>2</span>
                    <span>Kéo xuống, chọn <b className="text-white">Thêm vào MH chính</b> ⊞</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>3</span>
                    <span>Bấm <b className="text-white">Thêm</b> ở góc phải — icon JAMA HOME hiện ngoài màn hình</span>
                  </li>
                  <li className="text-xs pt-1" style={{ color: '#8E8778' }}>Đang mở bằng Zalo/Chrome? Chọn «Mở bằng Safari» trước rồi làm như trên.</li>
                </>
              ) : (
                <>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>1</span>
                    <span>Bấm nút <b className="text-white">⋮</b> (Chrome) hoặc <b className="text-white">≡</b> (Samsung Internet) ở góc màn hình</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>2</span>
                    <span>Chọn <b className="text-white">Thêm vào màn hình chính</b> / <b className="text-white">Cài đặt ứng dụng</b></span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ background: '#C9A96E', color: '#0B0D11' }}>3</span>
                    <span>Bấm <b className="text-white">Thêm</b> — icon JAMA HOME hiện ngoài màn hình</span>
                  </li>
                </>
              )}
            </ol>
            {/* Trang /cai-app cần đăng nhập → chỉ mời người đã đăng nhập đang ở trong app
                (khách ở /portal, /bao-gia hay người ở /login bấm vào sẽ bị đá về trang đăng nhập). */}
            {moiXemHuongDan && (
              <Link
                href="/cai-app"
                onClick={() => setMoHuongDan(false)}
                className="mt-4 flex items-center justify-center gap-1.5 w-full rounded-full text-sm font-medium"
                style={{ color: '#C9A96E', border: '1px solid rgba(201,169,110,0.35)', minHeight: 44 }}
              >
                <LineIcon name="compass" size={16} color="currentColor" />
                Xem hướng dẫn
              </Link>
            )}
            <button
              type="button"
              onClick={() => setMoHuongDan(false)}
              className={`w-full ${moiXemHuongDan ? 'mt-3' : 'mt-5'} rounded-full text-sm font-semibold`}
              style={{ background: '#C9A96E', color: '#0B0D11', minHeight: 44 }}
            >
              Đã hiểu
            </button>
          </div>
        </div>
      )}
      <style>{`
        @keyframes slideUpSheet { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .animate-slideUpSheet { animation: slideUpSheet 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
      `}</style>
    </>
  );
}
