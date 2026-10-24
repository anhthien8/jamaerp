'use client';

/**
 * Sơ đồ mạng lưới dạng cây có thể kéo/phóng (24/10/2026) — dùng thư viện
 * d3-org-chart (github.com/bumbeishvili/org-chart, MIT). Thư viện chỉ tải khi
 * mở tab này (import động) nên không làm nặng các trang khác.
 * Cây: JAMA HOME → Ban Giám đốc / từng phòng → Trưởng phòng → Nhóm → Nhân viên.
 * Bấm thẻ người → mở Hồ sơ 360°; bấm thẻ phòng/nhóm → mở/thu nhánh.
 * Tài khoản đang đăng nhập viền vàng + nhãn «Bạn», mở sẵn nhánh và căn giữa.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { User, Team } from '@/lib/api';
import { mediaUrl } from '@/lib/api';
import LineIcon from '@/components/ui/LineIcon';
import { capBac, deptLabel, DEPT_ORDER, type RoleStyle } from '@/lib/nhan-su';

interface Props {
  users: User[];
  teams: Team[];
  roleOf: (role?: string | null) => RoleStyle;
  meId?: string;
  tim: string;
}

interface Nut {
  id: string;
  parentId: string | null;
  loai: 'cty' | 'nhom' | 'nguoi';
  ten: string;
  phu: string;
  mau?: string;
  anh?: string;
  so?: number;
  laToi?: boolean;
}

const esc = (s: string) =>
  s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));

function dungCay(users: User[], teams: Team[], roleOf: Props['roleOf'], meId?: string): Nut[] {
  const dangLam = users.filter(u => u.is_active);
  const ds: Nut[] = [{ id: 'cty', parentId: null, loai: 'cty', ten: 'JAMA HOME', phu: `${dangLam.length} người đang làm` }];
  const nguoi = (u: User, cha: string) => {
    const r = roleOf(u.role);
    ds.push({
      id: u.id, parentId: cha, loai: 'nguoi', ten: u.full_name, phu: r.label, mau: r.color,
      anh: u.avatar_url ? mediaUrl(u.avatar_url) : undefined, laToi: u.id === meId,
    });
  };
  const nhom = (id: string, cha: string, ten: string, so: number) =>
    ds.push({ id, parentId: cha, loai: 'nhom', ten, phu: `${so} người`, so });

  const bgd = dangLam.filter(u => capBac(u) === 'bgd');
  if (bgd.length) {
    nhom('g:bgd', 'cty', 'Ban Giám đốc', bgd.length);
    bgd.forEach(u => nguoi(u, 'g:bgd'));
  }

  const theoPhong: Record<string, User[]> = {};
  for (const u of dangLam) {
    if (capBac(u) === 'bgd') continue;
    (theoPhong[(u.department || 'OTHER').toUpperCase()] ||= []).push(u);
  }
  const rank = (d: string) => { const i = DEPT_ORDER.indexOf(d); return i < 0 ? 99 : i; };
  for (const [d, list] of Object.entries(theoPhong).sort((a, b) => rank(a[0]) - rank(b[0]))) {
    const pid = `g:${d}`;
    nhom(pid, 'cty', deptLabel(d), list.length);
    const tp = list.filter(u => capBac(u) === 'tp');
    tp.forEach(u => nguoi(u, pid));
    const goc = tp[0]?.id ?? pid; // cấp dưới treo vào trưởng phòng đầu tiên
    const duoi = list.filter(u => capBac(u) !== 'tp');
    const nhomCo = teams.filter(t => duoi.some(u => u.team_id === t.id));
    if (nhomCo.length >= 2) {
      for (const t of nhomCo) {
        const tv = duoi.filter(u => u.team_id === t.id);
        const tid = `t:${t.id}`;
        nhom(tid, goc, t.name, tv.length);
        const truong = tv.find(u => u.id === t.leader_id);
        if (truong) nguoi(truong, tid);
        tv.filter(u => u !== truong).forEach(u => nguoi(u, truong?.id ?? tid));
      }
      duoi.filter(u => !nhomCo.some(t => t.id === u.team_id)).forEach(u => nguoi(u, goc));
    } else {
      const tn = duoi.filter(u => capBac(u) === 'tn');
      tn.forEach(u => nguoi(u, goc));
      // Nhân viên treo vào trưởng nhóm khi phòng chỉ có đúng 1 trưởng nhóm
      duoi.filter(u => capBac(u) === 'nv').forEach(u => nguoi(u, tn.length === 1 ? tn[0].id : goc));
    }
  }
  return ds;
}

function noiDung(n: Nut, w: number, h: number): string {
  const vien = n.laToi ? '2px solid var(--gold-500)' : '1px solid var(--border-subtle)';
  const khung = `width:${w}px;height:${h}px;box-sizing:border-box;border-radius:14px;border:${vien};display:flex;align-items:center;gap:10px;padding:0 12px;font-family:inherit;overflow:hidden;`;
  if (n.loai === 'nguoi') {
    const chu = esc(n.ten.trim().split(/\s+/).pop()?.charAt(0).toUpperCase() || '?');
    const anh = n.anh
      ? `<img src="${esc(n.anh)}" alt="" style="width:40px;height:40px;border-radius:999px;object-fit:cover;flex-shrink:0" />`
      : `<div style="width:40px;height:40px;border-radius:999px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;background:linear-gradient(135deg,var(--navy-600),var(--navy-700))">${chu}</div>`;
    const ban = n.laToi
      ? `<span style="margin-left:6px;padding:1px 6px;border-radius:999px;font-size:10px;font-weight:700;background:var(--gold-500);color:#000">Bạn</span>`
      : '';
    const nen = n.laToi ? 'color-mix(in srgb, var(--gold-500) 14%, var(--surface-2))' : 'var(--surface-2)';
    return `<div style="${khung}background:${nen}">${anh}<div style="min-width:0;flex:1">
      <div style="font-size:13px;font-weight:600;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(n.ten)}${ban}</div>
      <div style="font-size:11px;color:${esc(n.mau || 'var(--text-muted)')};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(n.phu)}</div>
    </div></div>`;
  }
  const laCty = n.loai === 'cty';
  return `<div style="${khung}justify-content:center;flex-direction:column;gap:2px;background:${laCty ? 'color-mix(in srgb, var(--gold-500) 18%, var(--surface-2))' : 'var(--surface-3)'};border:1px solid ${laCty ? 'var(--gold-500)' : 'var(--border-strong, var(--border-subtle))'}">
    <div style="font-size:${laCty ? 15 : 13}px;font-weight:700;color:${laCty ? 'var(--gold-400)' : 'var(--text-primary)'};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%">${esc(n.ten)}</div>
    <div style="font-size:11px;color:var(--text-muted)">${esc(n.phu)}</div>
  </div>`;
}

export default function SoDoMangLuoi({ users, teams, roleOf, meId, tim }: Props) {
  const router = useRouter();
  const khungRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  const [loi, setLoi] = useState(false);
  const [dangTai, setDangTai] = useState(true);

  // roleOf đổi danh tính mỗi lần render → so theo nội dung để không vẽ lại cây liên tục
  const json = JSON.stringify(dungCay(users, teams, roleOf, meId));
  const data = useMemo<Nut[]>(() => JSON.parse(json), [json]);
  const coToi = !!meId && data.some(n => n.id === meId);

  useEffect(() => {
    let huy = false;
    const el = khungRef.current;
    if (!el) return;
    import('d3-org-chart')
      .then(({ OrgChart }) => {
        if (huy) return;
        const W = 236, H = 64;
        const chart = chartRef.current ?? new OrgChart();
        chartRef.current = chart;
        chart
          .container(el)
          .svgHeight(el.clientHeight || 560)
          .data(data.map(n => ({ ...n })))
          .nodeId((d: Nut) => d.id)
          .parentNodeId((d: Nut) => d.parentId)
          .nodeWidth(() => W)
          .nodeHeight(() => H)
          .childrenMargin(() => 44)
          .compactMarginBetween(() => 24)
          .compactMarginPair(() => 40)
          .siblingsMargin(() => 16)
          .neighbourMargin(() => 40)
          .initialExpandLevel(2)
          .scaleExtent([0.2, 2.5])
          .duration(250)
          .linkUpdate(function (this: SVGPathElement, d: { data: { _upToTheRootHighlighted?: boolean } }) {
            const sang = d.data._upToTheRootHighlighted;
            this.style.stroke = sang ? 'var(--gold-500)' : 'var(--text-muted)';
            this.style.strokeOpacity = sang ? '1' : '0.45';
            this.style.strokeWidth = sang ? '2.5' : '1.2';
          })
          .nodeUpdate(function (this: SVGGElement, d: { data: { _highlighted?: boolean; _upToTheRootHighlighted?: boolean } }) {
            const r = this.querySelector('.node-rect') as SVGRectElement | null;
            if (!r) return;
            const sang = d.data._highlighted || d.data._upToTheRootHighlighted;
            r.style.stroke = sang ? 'var(--gold-500)' : 'none';
            r.style.strokeWidth = sang ? '4' : '0';
          })
          .buttonContent(({ node }: { node: { children?: unknown[]; data: { _directSubordinates?: number } } }) =>
            `<div style="margin:auto;width:26px;height:18px;border-radius:999px;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;background:var(--surface-3);color:var(--text-secondary);border:1px solid var(--border-subtle)">${node.children ? '−' : node.data._directSubordinates ?? '+'}</div>`)
          .nodeContent((d: { data: Nut; width: number; height: number }) => noiDung(d.data, d.width, d.height))
          .onNodeClick((d: { data: Nut }) => {
            if (d.data.loai === 'nguoi') router.push(`/hr/nhan-vien?id=${d.data.id}`);
          })
          .render();
        if (coToi) chart.setExpanded(meId).setCentered(meId).render();
        else chart.fit();
        setDangTai(false);
      })
      .catch(() => { if (!huy) { setLoi(true); setDangTai(false); } });
    return () => { huy = true; };
  }, [data, coToi, meId, router]);

  // Tìm tên → tô sáng + căn giữa người khớp đầu tiên
  useEffect(() => {
    const chart = chartRef.current;
    const q = tim.trim().toLowerCase();
    if (!chart || dangTai) return;
    chart.clearHighlighting();
    if (!q) return;
    const n = data.find(x => x.loai === 'nguoi' && x.ten.toLowerCase().includes(q));
    if (n) chart.setUpToTheRootHighlighted(n.id).setCentered(n.id).render();
  }, [tim, data, dangTai]);

  const nut = (icon: Parameters<typeof LineIcon>[0]['name'], nhan: string, fn: () => void) => (
    <button
      type="button"
      onClick={fn}
      className="px-3 min-h-[40px] rounded-full text-xs font-semibold inline-flex items-center gap-1.5"
      style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <LineIcon name={icon} size={14} /> {nhan}
    </button>
  );

  if (loi) {
    return <p className="p-6 text-center text-sm text-[var(--text-muted)]">Không tải được sơ đồ dạng cây — dùng «Dạng thẻ» bên cạnh.</p>;
  }

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)' }}>
      <div className="flex flex-wrap gap-2 p-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {coToi && nut('user', 'Tìm tôi', () => chartRef.current?.clearHighlighting().setExpanded(meId).setCentered(meId).render())}
        {nut('compass', 'Vừa màn hình', () => chartRef.current?.fit())}
        {nut('layers', 'Mở hết', () => chartRef.current?.expandAll().fit())}
        {nut('chevronDown', 'Thu gọn', () => chartRef.current?.collapseAll().fit())}
        <span className="ml-auto self-center text-[11px] text-[var(--text-muted)] hidden sm:inline">Kéo để di chuyển · cuộn/chụm 2 ngón để phóng to</span>
      </div>
      <div
        ref={khungRef}
        className="relative w-full h-[68vh] min-h-[420px] touch-none"
        style={{ background: 'radial-gradient(circle at 1px 1px, var(--border-subtle) 1px, transparent 0) 0 0 / 22px 22px' }}
      >
        {dangTai && <p className="absolute inset-0 flex items-center justify-center text-sm text-[var(--text-muted)]">Đang vẽ sơ đồ…</p>}
      </div>
    </div>
  );
}
