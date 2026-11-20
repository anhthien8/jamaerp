'use client';

/**
 * Cài app & bật thông báo (/cai-app) — 21/11/2026. Mọi người đã đăng nhập.
 *
 * Đích của tin «Cài JAMA HOME lên điện thoại» (BGĐ nhắc ở /du-lieu-chung) và link trong
 * tin nhắc gửi người chưa bật thông báo máy. Một trang làm trọn 4 bước:
 *   1–3. Cài ra màn hình chính (Android: hộp cài thật nếu trình duyệt cho; iPhone/iPad:
 *        Safari → Chia sẻ → Thêm vào MH chính → mở từ màn hình chính).
 *   4.   Bật thông báo = <BatThongBaoMay /> bản đầy đủ (logic chung lib/thong-bao-may.ts).
 * Đầu trang cho biết máy đang dùng: chạy dạng app hay trình duyệt, thông báo bật hay tắt.
 */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { duongDangNhap } from '@/lib/dang-nhap';
import { useToast } from '@/components/ui/Toast';
import LineIcon from '@/components/ui/LineIcon';
import BatThongBaoMay from '@/components/BatThongBaoMay';
import {
  dangChayDangApp, laAndroid, laIOS, laMayDiDong, laTrinhDuyetNhung, moHopCai, useCoHopCai, useVuaCaiApp,
} from '@/lib/cai-app';
import { useThongBaoMay, type TrangThaiThongBao } from '@/lib/thong-bao-may';

type LoaiMay = 'ios' | 'android' | 'may-tinh';
type ThongTinMay = { loai: LoaiMay; diDong: boolean; dangApp: boolean; nhung: boolean };

const NHAN_THONG_BAO: Record<TrangThaiThongBao, { chu: string; mau: string }> = {
  'dang-tai': { chu: 'Đang kiểm tra…', mau: 'var(--text-muted)' },
  bat: { chu: 'Đã bật', mau: 'var(--success)' },
  tat: { chu: 'Chưa bật', mau: 'var(--warning)' },
  'bi-chan': { chu: 'Đang bị chặn', mau: 'var(--warning)' },
  'can-cai-ios': { chu: 'Cần cài app trước (iPhone/iPad)', mau: 'var(--warning)' },
  'khong-ho-tro': { chu: 'Trình duyệt này chưa hỗ trợ', mau: 'var(--text-muted)' },
  'chua-cau-hinh': { chu: 'Máy chủ chưa bật — báo Admin', mau: 'var(--text-muted)' },
};

const NUT = 'inline-flex items-center justify-center gap-1.5 min-h-[44px] px-4 rounded-full text-sm font-semibold transition-colors disabled:opacity-50';

export default function CaiAppPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [may, setMay] = useState<ThongTinMay | null>(null);
  const [tab, setTab] = useState<LoaiMay | null>(null);
  const coHopCai = useCoHopCai();
  const vuaCai = useVuaCaiApp();
  const { tt } = useThongBaoMay();

  useEffect(() => {
    if (!loading && !user) router.push(duongDangNhap());
  }, [user, loading, router]);

  useEffect(() => {
    void Promise.resolve().then(() => {
      const loai: LoaiMay = laIOS() ? 'ios' : laAndroid() ? 'android' : 'may-tinh';
      setMay({ loai, diDong: laMayDiDong(), dangApp: dangChayDangApp(), nhung: laTrinhDuyetNhung() });
    });
  }, []);

  const caiNgay = async () => {
    const kq = await moHopCai();
    if (kq === 'accepted') toast('Đã cài — từ nay mở JAMA HOME bằng icon ngoài màn hình chính', 'success');
    else if (kq === 'khong-co') toast('Trình duyệt chưa cho cài tự động — làm theo 3 bước bên dưới', 'info');
  };

  if (loading || !user) return null;

  // Tab hướng dẫn: mặc định theo máy đang dùng (máy tính → Android, hay gặp nhất ở công ty).
  const tabHien: Exclude<LoaiMay, 'may-tinh'> = tab === 'ios' || tab === 'android'
    ? tab
    : may?.loai === 'ios' ? 'ios' : 'android';
  const daSanSang = !!may?.dangApp && tt === 'bat';
  const nhanTB = NHAN_THONG_BAO[tt];

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-3xl animate-in">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2.5">
          <LineIcon name="smartphone" size={22} />
          Cài app <span className="gold-gradient">&amp; bật thông báo</span>
        </h1>
        <p className="text-sm mt-1 text-[var(--text-secondary)]">
          Cài JAMA HOME ra màn hình chính điện thoại (mở 1 chạm như Zalo), rồi bật thông báo để việc được giao,
          nhắc hạn, tin của Ban giám đốc hiện lên máy ngay — kể cả khi không mở app. Mất khoảng 1 phút.
        </p>
      </div>

      {/* ── Máy đang dùng ─────────────────────────────────────────── */}
      <section className="glass-card p-5">
        <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Máy bạn đang dùng</h2>
        {daSanSang ? (
          <p className="flex items-start gap-2 text-sm mb-3" style={{ color: 'var(--success)' }}>
            <LineIcon name="check" size={18} color="currentColor" className="mt-0.5" />
            Máy này đã sẵn sàng: đang mở dạng app và đã bật thông báo. Không cần làm gì thêm.
          </p>
        ) : null}
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div className="rounded-2xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
            <dt className="text-[11px] text-[var(--text-muted)]">Đang mở bằng</dt>
            <dd className="font-semibold mt-0.5" style={{ color: may?.dangApp || vuaCai ? 'var(--success)' : 'var(--text-primary)' }}>
              {!may ? 'Đang kiểm tra…'
                : may.dangApp ? 'App JAMA HOME (đã cài)'
                : vuaCai ? 'Vừa cài xong — mở bằng icon ngoài màn hình chính'
                : may.nhung ? 'Trình duyệt trong Zalo/Telegram/Facebook'
                : 'Trình duyệt'}
            </dd>
          </div>
          <div className="rounded-2xl p-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
            <dt className="text-[11px] text-[var(--text-muted)]">Thông báo trên máy này</dt>
            <dd className="font-semibold mt-0.5" style={{ color: nhanTB.mau }}>{nhanTB.chu}</dd>
          </div>
        </dl>

        {may?.nhung && !may.dangApp && (
          <p className="mt-3 text-xs leading-relaxed px-3 py-2.5 rounded-xl flex items-start gap-2"
            style={{ background: 'var(--warning-bg)', color: 'var(--text-secondary)' }}>
            <LineIcon name="alert" size={16} color="var(--warning)" className="mt-0.5" />
            <span>
              Trình duyệt bên trong Zalo/Telegram/Facebook không cài app được. Bấm nút <b className="text-[var(--text-primary)]">⋯</b> hoặc <b className="text-[var(--text-primary)]">⋮</b> góc trên
              → <b className="text-[var(--text-primary)]">Mở bằng trình duyệt</b> ({may.loai === 'ios' ? 'Safari' : 'Chrome'}) rồi làm theo các bước dưới.
            </span>
          </p>
        )}

        {coHopCai && !may?.dangApp && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => void caiNgay()} className={NUT}
              style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}>
              <LineIcon name="download" size={16} color="currentColor" />
              Cài ngay
            </button>
            <span className="text-[11px] text-[var(--text-muted)]">Trình duyệt này cài được tự động — bấm rồi chọn «Cài đặt».</span>
          </div>
        )}
      </section>

      {/* ── Bước 1–3: cài ra màn hình chính ───────────────────────── */}
      {may && !may.dangApp && (
        <section className="glass-card p-5">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Bước 1–3: Cài ra màn hình chính</h2>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5 mb-3">Chọn loại điện thoại của bạn.</p>
          <div role="tablist" aria-label="Loại điện thoại" className="flex gap-2 mb-4">
            {([['android', 'Android / Samsung'], ['ios', 'iPhone / iPad']] as const).map(([k, nhan]) => (
              <button key={k} type="button" role="tab" aria-selected={tabHien === k} onClick={() => setTab(k)}
                className="flex-1 min-h-[44px] px-3 rounded-full text-xs font-semibold transition-colors"
                style={tabHien === k
                  ? { background: 'var(--gold-500)', color: 'var(--surface-0)' }
                  : { background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
                {nhan}
              </button>
            ))}
          </div>

          {tabHien === 'android' ? (
            <ol className="space-y-3">
              <Buoc so={1}>
                Mở <b>crm.jamahome.vn</b> bằng <b>Chrome</b> hoặc <b>Samsung Internet</b> (không mở trong Zalo/Telegram/Facebook).
              </Buoc>
              <Buoc so={2}>
                Bấm nút <b>⋮</b> (Chrome, góc trên phải) hoặc <b>≡</b> (Samsung Internet, góc dưới phải) → chọn
                {' '}<b>Cài đặt ứng dụng</b> hoặc <b>Thêm vào màn hình chính</b>.
              </Buoc>
              <Buoc so={3}>
                Bấm <b>Cài đặt</b> / <b>Thêm</b>. Icon <b>JAMA HOME</b> hiện ngoài màn hình chính — từ nay mở app bằng icon này.
              </Buoc>
            </ol>
          ) : (
            <ol className="space-y-3">
              <Buoc so={1}>
                Mở <b>crm.jamahome.vn</b> bằng <b>Safari</b>. Đang ở Zalo/Telegram/Chrome thì chọn «Mở bằng Safari» trước.
              </Buoc>
              <Buoc so={2}>
                Bấm nút <b>Chia sẻ</b>{' '}
                <LineIcon name="upload" size={16} color="var(--info)" className="inline -mt-1" />
                {' '}(thanh dưới trên iPhone, góc trên trên iPad) → kéo xuống chọn <b>Thêm vào MH chính</b> → bấm <b>Thêm</b>.
              </Buoc>
              <Buoc so={3}>
                Đóng Safari, mở <b>JAMA HOME</b> từ icon ngoài màn hình chính. iPhone/iPad chỉ nhận được thông báo
                khi mở từ icon này (iOS 16.4 trở lên).
              </Buoc>
            </ol>
          )}
          {may.loai === 'may-tinh' && (
            <p className="text-[11px] text-[var(--text-muted)] mt-4">
              Trên máy tính: Chrome/Edge có biểu tượng cài ở cuối thanh địa chỉ. Không cài cũng được — bật thông báo ở bước 4 là đủ.
            </p>
          )}
        </section>
      )}

      {/* ── Bước 4: bật thông báo ─────────────────────────────────── */}
      <div>
        <p className="text-xs font-semibold text-[var(--text-secondary)] mb-2 px-1">Bước 4: Bật thông báo</p>
        <BatThongBaoMay />
      </div>

      <section className="glass-card p-5 text-xs leading-relaxed text-[var(--text-secondary)] space-y-2">
        <p className="flex items-start gap-2">
          <LineIcon name="bell" size={16} className="mt-0.5" />
          <span>
            Đang mở app: thông báo mới hiện thành <b className="text-[var(--text-primary)]">ô nhỏ trên cùng màn hình</b> (bấm «Mở» để tới thẳng việc đó).
            Không mở app: thông báo hiện như tin nhắn của điện thoại.
          </span>
        </p>
        <p className="flex items-start gap-2">
          <LineIcon name="info" size={16} className="mt-0.5" />
          <span>Mỗi máy (điện thoại, máy tính bảng, laptop) bật riêng một lần. Đổi máy hoặc cài lại app thì bật lại.</span>
        </p>
      </section>
    </div>
  );
}

function Buoc({ so, children }: { so: number; children: ReactNode }) {
  return (
    <li className="flex items-start gap-3 text-sm text-[var(--text-secondary)] [&_b]:text-[var(--text-primary)]">
      <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
        style={{ background: 'var(--gold-500)', color: 'var(--surface-0)' }}>{so}</span>
      <span className="pt-0.5 leading-relaxed">{children}</span>
    </li>
  );
}
