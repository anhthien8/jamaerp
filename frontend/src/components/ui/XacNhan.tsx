'use client';

/**
 * Hộp xác nhận của app thay `confirm()` của trình duyệt (24/11/2026). Một dòng ở nơi dùng:
 *
 *   const xacNhan = useXacNhan();
 *   if (!(await xacNhan('Xoá dòng này?', { nguyHiem: true }))) return;
 *
 * Hộp của trình duyệt hiện tên miền, chữ nhỏ, không theo theme, và trên iPhone cài lên màn hình chính
 * có lúc không hiện → thao tác «không ăn».
 */

import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import ConfirmDialog from './ConfirmDialog';

type TuyChon = { tieuDe?: string; nut?: string; nguyHiem?: boolean };
type Hoi = TuyChon & { noiDung: string; xong: (dongY: boolean) => void };

const Ctx = createContext<(noiDung: string, tuyChon?: TuyChon) => Promise<boolean>>(async () => false);

export function XacNhanProvider({ children }: { children: ReactNode }) {
  const [hoi, setHoi] = useState<Hoi | null>(null);
  const xacNhan = useCallback((noiDung: string, tuyChon?: TuyChon) => new Promise<boolean>(xong => setHoi({ noiDung, ...tuyChon, xong })), []);
  const tra = (dongY: boolean) => { hoi?.xong(dongY); setHoi(null); };
  return (
    <Ctx.Provider value={xacNhan}>
      {children}
      <ConfirmDialog open={!!hoi} message={hoi?.noiDung || ''} title={hoi?.tieuDe} confirmLabel={hoi?.nut}
        variant={hoi?.nguyHiem ? 'danger' : 'default'} onConfirm={() => tra(true)} onCancel={() => tra(false)} />
    </Ctx.Provider>
  );
}

export const useXacNhan = () => useContext(Ctx);
