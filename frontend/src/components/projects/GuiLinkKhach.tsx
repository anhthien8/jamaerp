'use client';

import { useXacNhan } from '@/components/ui/XacNhan';
import { useEffect, useState } from 'react';
import LineIcon from '@/components/ui/LineIcon';
import { useToast } from '@/components/ui/Toast';
import { api } from '@/lib/api';
import type { PortalLink } from '@/lib/api';

/** Số dùng được cho tel:/zalo.me — null khi SĐT trống hoặc đã bị che (xxx***). */
export function soLienLac(phone?: string | null): string | null {
  if (!phone || phone.includes('*')) return null;
  const so = phone.replace(/\D/g, '');
  return so.length >= 9 ? so : null;
}

const NUT = 'inline-flex items-center justify-center gap-1.5 min-h-[40px] px-3 rounded-lg text-xs font-semibold transition-all disabled:opacity-50';
const NUT_CHINH = `${NUT} bg-[var(--gold-500)]/15 text-[var(--gold-500)] hover:bg-[var(--gold-500)]/25`;
const NUT_PHU = `${NUT} text-[var(--text-secondary)] hover:text-[var(--text-primary)]`;
const VIEN_PHU = { border: '1px solid var(--border-default)' };

/**
 * Một chạm gửi link portal cho khách: sao chép tin soạn sẵn rồi mở chat Zalo.
 * Link lấy sẵn lúc mở thẻ (iOS Safari chỉ cho ghi clipboard ngay trong cú chạm),
 * và luôn là link ĐANG CÓ — không xoay token. Người không có quyền thì không hiện gì.
 */
export default function GuiLinkKhach({ layLink, phone, soanTin, nhan, choGoi, choTaoLai }: {
  layLink: () => Promise<PortalLink>;
  phone?: string | null;
  soanTin: (link: string) => string;
  nhan: string;
  choGoi?: boolean;
  choTaoLai?: boolean;
}) {
  const xacNhan = useXacNhan();
  const { toast } = useToast();
  const [pl, setPl] = useState<PortalLink | null>(null);
  const [dangXuLy, setDangXuLy] = useState(false);
  const so = soLienLac(phone);

  useEffect(() => {
    let huy = false;
    layLink().then(d => { if (!huy) setPl(d); }).catch(() => { if (!huy) setPl(null); });
    return () => { huy = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const nutGoi = choGoi && so ? (
    <a href={`tel:${so}`} className={NUT_PHU} style={VIEN_PHU}>
      <LineIcon name="phone" size={14} color="currentColor" />Gọi
    </a>
  ) : null;

  if (!pl) return nutGoi ? <div className="flex flex-wrap gap-2">{nutGoi}</div> : null;

  const link = `${window.location.origin}/portal/${pl.portal_token}`;

  const gui = () => {
    // Không await trước window.open: cả hai phải nằm trong cú chạm của người dùng.
    const chep = navigator.clipboard?.writeText(soanTin(link)) ?? Promise.reject(new Error('no clipboard'));
    if (so) window.open(`https://zalo.me/${so}`, '_blank', 'noopener');
    chep.then(
      () => toast(so ? 'Đã sao chép tin nhắn — dán vào ô chat Zalo vừa mở rồi bấm Gửi' : 'Đã sao chép tin nhắn kèm link — dán vào Zalo để gửi khách', 'success'),
      () => toast(`Không sao chép tự động được — hãy chép tay link: ${link}`, 'error'),
    );
  };

  const chay = async (viec: () => Promise<void>) => {
    setDangXuLy(true);
    try { await viec(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Có lỗi xảy ra', 'error'); }
    finally { setDangXuLy(false); }
  };

  const batLai = async () => {
    if (!await xacNhan('Link theo dõi của khách này đang TẮT (có thể đã được tắt có chủ ý). Bật lại để khách xem được?')) return;
    void chay(async () => {
      const r = await api.setPortalEnabled(pl.customer_id, true);
      setPl({ ...pl, portal_enabled: r.portal_enabled });
      toast('Đã bật lại link theo dõi', 'success');
    });
  };

  const taoLai = async () => {
    if (!await xacNhan('Tạo lại link? Link cũ đã gửi cho khách sẽ hết hiệu lực ngay.')) return;
    void chay(async () => {
      const r = await api.generatePortalLink(pl.customer_id);
      setPl({ ...pl, portal_token: r.portal_token, portal_enabled: true });
      toast('Đã tạo link mới — nhớ gửi lại cho khách', 'success');
    });
  };

  return (
    <div className="space-y-2">
      {!pl.portal_enabled && (
        <p className="text-xs text-[var(--text-muted)]">
          <LineIcon name="alert" size={12} color="currentColor" className="inline-block align-[-2px] mr-1" />
          Link theo dõi đang tắt — khách mở sẽ không xem được.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {nutGoi}
        {pl.portal_enabled ? (
          <button type="button" onClick={gui} className={NUT_CHINH}>
            <LineIcon name="send" size={14} color="currentColor" />{nhan}
          </button>
        ) : (
          <button type="button" onClick={batLai} disabled={dangXuLy} className={NUT_CHINH}>
            <LineIcon name="link" size={14} color="currentColor" />Bật lại link
          </button>
        )}
        {choTaoLai && (
          <button type="button" onClick={taoLai} disabled={dangXuLy} className={NUT_PHU} style={VIEN_PHU}>
            <LineIcon name="refresh" size={14} color="currentColor" />Tạo lại link
          </button>
        )}
      </div>
    </div>
  );
}
