import type { Project } from '@/lib/api';

export const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'Đang thực hiện', color: '#10B981' },
  on_hold: { label: 'Tạm dừng', color: '#F59E0B' },
  completed: { label: 'Hoàn thành', color: '#3B82F6' },
  cancelled: { label: 'Hủy', color: '#EF4444' },
};

export const STAGE_LABELS: Record<string, string> = {
  design: 'Thiết kế',
  quotation: 'Báo giá',
  procurement: 'Thu mua',
  construction: 'Thi công',
  acceptance: 'Nghiệm thu & Bàn giao',
  completed: 'Hoàn thành',
  paused: 'Tạm dừng',
};

export const DEPT_LABELS: Record<string, { label: string; color: string }> = {
  design: { label: 'Thiết kế', color: '#8B5CF6' },
  quotation: { label: 'Báo giá', color: '#F59E0B' },
  procurement: { label: 'Thu mua', color: '#10B981' },
  construction: { label: 'Thi công', color: '#3B82F6' },
  accounting: { label: 'Kế toán', color: '#EC4899' },
  sales: { label: 'Kinh doanh', color: '#F97316' },
};

// Phòng ban của task (viết thường) → phòng ban user (viết HOA) được nhận việc.
// Sửa 05/09 theo cơ cấu THẬT trên prod: dự toán/báo giá (du_toan,
// dutoan_thumua_leader) và thu mua đều nằm ở PURCHASING — bản cũ map báo giá
// sang SALES+DESIGN và thu mua sang OPS nên hiện nhầm người.
export const DEPT_TO_USER_DEPT: Record<string, string[]> = {
  design: ['DESIGN'],
  quotation: ['PURCHASING'],
  procurement: ['PURCHASING'],
  construction: ['OPS'],
  accounting: ['ACCT'],
  sales: ['SALES'],
};

/** Phòng ban hiệu lực của task: `department` nếu có, không thì suy từ `stage`
 *  (task tự sinh khi thắng deal từng để trống department — backfill u01 đã dọn,
 *  nhưng vẫn giữ fallback cho dữ liệu cũ / cache). Nghiệm thu do đội thi công làm. */
export const taskDeptOf = (t: { department?: string | null; stage?: string | null }): string =>
  t.department || (t.stage === 'acceptance' ? 'construction' : t.stage || '');

/** Ai được nhận task phòng ban `dept` — CHỈ người thuộc đúng phòng ban đó.
 *  Không có ngoại lệ nào: chốt 05/09 sau khi user thấy 4 tài khoản Giám đốc (EXEC)
 *  lọt vào mọi dropdown. Supervisor cũng không toàn quyền — trên prod họ thuộc
 *  phòng cụ thể (DESIGN/OPS/PURCHASING/PM). Task không rõ phòng ban → không ai. */
export const canTakeTask = (u: { role?: string; department?: string | null }, dept: string): boolean => {
  const allowed = DEPT_TO_USER_DEPT[dept];
  return !!allowed && allowed.includes((u.department || '').toUpperCase());
};

/** Ô PIC ứng với bộ phận của người đang đăng nhập (22/09/2026).
 *  Luồng chốt: tạo dự án → thông báo trưởng phòng → trưởng phòng gắn PIC cho
 *  BỘ PHẬN MÌNH. «Trưởng phòng Kinh Doanh không thấy/show nhân sự phòng Thiết
 *  Kế» — nên mỗi người chỉ thấy đúng ô của phòng mình. Ban Giám Đốc (admin /
 *  executive) thấy cả 4 ô vì họ điều phối chéo phòng. */
export const PIC_CUA_BO_PHAN: Record<string, string> = {
  OPS: 'pm_id',
  DESIGN: 'designer_id',
  PURCHASING: 'purchasing_id',
  SALES: 'sales_id',
};

export const laBanGiamDoc = (u?: { role?: string } | null): boolean =>
  u?.role === 'admin' || u?.role === 'executive';

// ── Spec 07: thanh tiến độ 5 khối + badge hạn chót ──────────────────────────
export const STAGE_ORDER = ['design', 'quotation', 'procurement', 'construction', 'acceptance', 'paused'] as const;
export const STAGE_SHORT: Record<string, string> = {
  design: 'Thiết kế', quotation: 'Báo giá', procurement: 'Thu mua',
  construction: 'Thi công', acceptance: 'Nghiệm thu',
};

// ── Nhóm người đảm nhận đầu việc + nhãn trễ hạn (13/10/2026) ────────────────

/** Nhóm người đảm nhận của một đầu việc. `assignee_ids` là nguồn sự thật; rơi về
 *  `assigned_to` cho dữ liệu/cache cũ chưa có nhóm. */
export const nhomDamNhan = (t: { assignee_ids?: string[]; assigned_to?: string }): string[] =>
  t.assignee_ids?.length ? t.assignee_ids : (t.assigned_to ? [t.assigned_to] : []);

/** Tên gọi ngắn để badge không tràn hàng — người Việt gọi nhau bằng tên cuối. */
export const tenNgan = (full?: string): string => full?.trim().split(/\s+/).pop() || '✓';

/** Nhãn trễ của đầu việc. Hạn thoả thuận (`due_date`) ưu tiên hơn chuẩn nội bộ
 *  (`sla_due_at`): trễ cả hai thì chỉ hiện một nhãn, đúng như quy tắc gửi thông
 *  báo ở backend (app/services/task_sla.py). */
export function nhanTreHan(t: { status: string; due_date?: string; sla_due_at?: string }):
  { text: string; color: string; bg: string } | null {
  if (t.status === 'done' || t.status === 'completed') return null;
  const dHan = daysLeft(t.due_date);
  if (dHan !== null && dHan < 0) {
    return { text: `Quá hạn ${-dHan}n`, color: '#F87171', bg: 'rgba(248,113,113,0.18)' };
  }
  const dSla = daysLeft(t.sla_due_at);
  if (dSla !== null && dSla < 0) {
    return { text: `Vượt SLA ${-dSla}n`, color: '#FB923C', bg: 'rgba(251,146,60,0.18)' };
  }
  if (dHan !== null && dHan <= 2) {
    return { text: `Còn ${dHan}n`, color: '#FBBF24', bg: 'rgba(251,191,36,0.15)' };
  }
  return null;
}

/** `datetime-local` cần 'YYYY-MM-DDTHH:mm'; API trả ISO có giây + timezone. */
export const choOInputNgay = (iso?: string): string => (iso ? iso.slice(0, 10) : '');

export function daysLeft(target?: string | null): number | null {
  if (!target) return null;
  const end = new Date(target).getTime();
  if (Number.isNaN(end)) return null;
  return Math.ceil((end - Date.now()) / 86_400_000);
}

export function DeadlineBadge({ project }: { project: Project }) {
  if (project.status === 'completed' || project.status === 'cancelled') return null;
  const d = daysLeft(project.target_end_date);
  if (d === null) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-medium" style={{ background: 'rgba(107,114,128,0.15)', color: '#9CA3AF' }}>Chưa đặt hạn</span>;
  }
  if (d < 0) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(248,113,113,0.18)', color: '#F87171' }}><span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle" style={{ background: 'currentColor' }} />Quá hạn {-d} ngày</span>;
  }
  if (d <= 14) {
    return <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(251,146,60,0.18)', color: '#FB923C' }}><span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle" style={{ background: 'currentColor' }} />Còn {d} ngày</span>;
  }
  return <span className="text-[9px] px-1.5 py-0.5 rounded font-medium" style={{ background: 'rgba(107,114,128,0.12)', color: '#9CA3AF' }}>Còn {d} ngày</span>;
}

export function StageBlocks({ project }: { project: Project }) {
  const progress = project.stage_progress;
  if (!progress) return null;
  return (
    <div className="flex gap-1 mb-2" aria-label="Tiến độ theo giai đoạn">
      {STAGE_ORDER.map(stage => {
        const cell = progress[stage];
        const total = cell?.total ?? 0;
        const done = cell?.done ?? 0;
        let bg = 'var(--surface-3)'; // chưa bắt đầu
        if (total > 0 && done >= total) bg = '#10B981';       // xong
        else if (done > 0 || project.stage === stage) bg = '#F59E0B'; // đang làm
        return (
          <div
            key={stage}
            className="h-1.5 flex-1 rounded-full"
            style={{ background: bg }}
            title={`${STAGE_SHORT[stage]}: ${done}/${total} việc`}
          />
        );
      })}
    </div>
  );
}

export const taskStatusConfig: Record<string, { label: string; color: string; icon: string }> = {
  done: { label: 'Xong', color: '#10B981', icon: 'check' },
  in_progress: { label: 'Đang làm', color: '#F59E0B', icon: 'refresh' },
  not_started: { label: 'Chưa bắt đầu', color: '#6B7280', icon: 'hourglass' },
  todo: { label: 'Chờ', color: '#6B7280', icon: 'hourglass' },
  completed: { label: 'Hoàn thành', color: '#3B82F6', icon: 'check' },
};
