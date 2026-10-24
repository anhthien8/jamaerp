'use client';

/**
 * Sơ đồ mạng lưới công ty (24/10/2026) — học cách BloFin vẽ cây đội nhóm:
 * thẻ phẳng nền tối, viên thuốc đếm người, đường nối mảnh, bấm nút nào mở hồ sơ
 * người đó. Tầng: Công ty → Ban Giám đốc → Phòng ban → Trưởng phòng → Trưởng
 * nhóm/Nhóm → Nhân viên. Mobile: cây dọc thụt lề; desktop: phòng ban xếp lưới.
 */

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { User, Team } from '@/lib/api';
import Avatar from '@/components/ui/Avatar';
import LineIcon from '@/components/ui/LineIcon';
import { capBac, deptLabel, DEPT_ORDER, type RoleStyle } from '@/lib/nhan-su';

interface Props {
  users: User[];
  teams: Team[];
  roleOf: (role?: string | null) => RoleStyle;
}

const VIEN = 'var(--border-subtle)';

function Pill({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <span
      className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap"
      style={accent
        ? { background: 'rgba(201,169,110,0.15)', color: 'var(--gold-400)' }
        : { background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
    >
      {children}
    </span>
  );
}

function NutNguoi({ u, roleOf, noiBat }: { u: User; roleOf: Props['roleOf']; noiBat?: boolean }) {
  const router = useRouter();
  const r = roleOf(u.role);
  return (
    <button
      type="button"
      onClick={() => router.push(`/hr/nhan-vien?id=${u.id}`)}
      title="Mở hồ sơ để xem/sửa"
      className="w-full text-left rounded-xl px-3 py-2.5 flex items-center gap-3 transition-colors active:scale-[0.99]"
      style={{
        background: noiBat ? 'rgba(201,169,110,0.08)' : 'var(--surface-2)',
        border: `1px solid ${noiBat ? 'rgba(201,169,110,0.35)' : VIEN}`,
      }}
    >
      <Avatar name={u.full_name} url={u.avatar_url} className="w-9 h-9 rounded-full text-sm shrink-0" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold truncate text-[var(--text-primary)]">{u.full_name}</span>
        <span className="block text-[11px] truncate" style={{ color: r.color }}>{r.label}</span>
      </span>
      <LineIcon name="arrowRight" size={14} color="var(--text-muted)" />
    </button>
  );
}

/** Nhánh con: đường dọc bên trái + gạch ngang tới từng nút (kiểu cây BloFin). */
function Nhanh({ children }: { children: React.ReactNode[] }) {
  return (
    <div className="ml-4 pl-4 space-y-2 relative" style={{ borderLeft: `1px solid ${VIEN}` }}>
      {children.map((c, i) => (
        <div key={i} className="relative">
          <span className="absolute -left-4 top-5 w-4" style={{ borderTop: `1px solid ${VIEN}` }} />
          {c}
        </div>
      ))}
    </div>
  );
}

function TieuDeTang({ text, n }: { text: string; n: number }) {
  return (
    <p className="text-[11px] uppercase tracking-wide text-[var(--text-muted)] flex items-center gap-2">
      {text} <span className="text-[var(--text-tertiary)]">· {n}</span>
    </p>
  );
}

export default function SoDoCongTy({ users, teams, roleOf }: Props) {
  const [tim, setTim] = useState('');
  const [dong, setDong] = useState<Record<string, boolean>>({});

  const dangLam = useMemo(() => users.filter(u => u.is_active), [users]);
  const q = tim.trim().toLowerCase();
  const khop = (u: User) => !q || u.full_name.toLowerCase().includes(q) || roleOf(u.role).label.toLowerCase().includes(q);

  const bgd = dangLam.filter(u => capBac(u) === 'bgd');
  const conLai = dangLam.filter(u => capBac(u) !== 'bgd');

  const phongBan = useMemo(() => {
    const m: Record<string, User[]> = {};
    for (const u of conLai) {
      const d = (u.department || 'OTHER').toUpperCase();
      (m[d] ||= []).push(u);
    }
    const rank = (d: string) => { const i = DEPT_ORDER.indexOf(d); return i < 0 ? 99 : i; };
    return Object.entries(m).sort((a, b) => rank(a[0]) - rank(b[0]) || b[1].length - a[1].length);
  }, [conLai]);

  const veNguoi = (list: User[], noiBat?: boolean) =>
    list.filter(khop).map(u => <NutNguoi key={u.id} u={u} roleOf={roleOf} noiBat={noiBat} />);

  return (
    <div className="space-y-5">
      {/* Gốc: công ty + chỉ số dạng viên thuốc */}
      <div className="rounded-2xl p-4 sm:p-5" style={{ background: 'var(--surface-1)', border: `1px solid ${VIEN}` }}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
          <div className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(201,169,110,0.15)' }}>
              <LineIcon name="network" size={20} />
            </span>
            <div>
              <p className="text-base font-bold text-[var(--text-primary)]">JAMA HOME</p>
              <p className="text-xs text-[var(--text-muted)]">Sơ đồ mạng lưới nhân sự · bấm vào ai để mở hồ sơ</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill accent>{dangLam.length} đang làm</Pill>
            <Pill>{phongBan.length} phòng ban</Pill>
            <Pill>{teams.length} nhóm</Pill>
          </div>
        </div>
        <div className="mt-3 relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2"><LineIcon name="search" size={14} color="var(--text-muted)" /></span>
          <input
            value={tim}
            onChange={e => setTim(e.target.value)}
            placeholder="Tìm tên hoặc vai trò…"
            autoComplete="off"
            className="w-full pl-9 pr-3 py-2 rounded-full text-sm bg-[var(--surface-2)] border border-[var(--border-subtle)] text-[var(--text-primary)] outline-none"
          />
        </div>
      </div>

      {/* Ban Giám đốc */}
      {bgd.filter(khop).length > 0 && (
        <div className="rounded-2xl p-4" style={{ background: 'var(--surface-1)', border: `1px solid ${VIEN}` }}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-bold text-[var(--text-primary)]">Ban Giám đốc</p>
            <Pill accent>{bgd.length}</Pill>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">{veNguoi(bgd, true)}</div>
        </div>
      )}

      {/* Đường nối xuống các phòng */}
      <div className="flex justify-center -my-2" aria-hidden="true">
        <span className="h-5" style={{ borderLeft: `1px solid ${VIEN}` }} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4 items-start">
        {phongBan.map(([d, nguoi]) => {
          const tp = nguoi.filter(u => capBac(u) === 'tp');
          const duoi = nguoi.filter(u => capBac(u) !== 'tp');
          // Nhóm con thật: ≥2 nhóm có người trong phòng (đo prod 22/09: chỉ KD chia nhóm thật)
          const nhomCo = teams.filter(t => duoi.some(u => u.team_id === t.id));
          const chiaNhom = nhomCo.length >= 2;
          const daDong = dong[d] ?? false;
          const soKhop = nguoi.filter(khop).length;
          if (q && soKhop === 0) return null;

          let than: React.ReactNode[] = [];
          if (chiaNhom) {
            than = nhomCo.map(t => {
              const tv = duoi.filter(u => u.team_id === t.id);
              const truong = tv.find(u => u.id === t.leader_id);
              const thanhVien = tv.filter(u => u.id !== t.leader_id);
              const nodes = [...(truong ? veNguoi([truong], true) : []), ...(thanhVien.filter(khop).length ? [<Nhanh key="tv">{veNguoi(thanhVien)}</Nhanh>] : [])];
              return (
                <div key={t.id} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">{t.name}</span>
                    <Pill>{tv.length}</Pill>
                  </div>
                  {nodes}
                </div>
              );
            });
            const chuaNhom = duoi.filter(u => !u.team_id || !nhomCo.some(t => t.id === u.team_id));
            if (chuaNhom.filter(khop).length) {
              than.push(
                <div key="_chua" className="space-y-2">
                  <TieuDeTang text="Chưa xếp nhóm" n={chuaNhom.length} />
                  {veNguoi(chuaNhom)}
                </div>,
              );
            }
          } else {
            const tn = duoi.filter(u => capBac(u) === 'tn');
            const nv = duoi.filter(u => capBac(u) === 'nv');
            if (tn.filter(khop).length) than.push(<div key="tn" className="space-y-2"><TieuDeTang text="Trưởng nhóm / Chủ trì" n={tn.length} />{veNguoi(tn)}</div>);
            if (nv.filter(khop).length) than.push(<div key="nv" className="space-y-2"><TieuDeTang text="Nhân viên" n={nv.length} />{veNguoi(nv)}</div>);
          }

          return (
            <div key={d} className="rounded-2xl p-4" style={{ background: 'var(--surface-1)', border: `1px solid ${VIEN}` }}>
              <button
                type="button"
                onClick={() => setDong(s => ({ ...s, [d]: !daDong }))}
                className="w-full flex items-center justify-between gap-2"
              >
                <span className="text-sm font-bold text-[var(--text-primary)]">{deptLabel(d)}</span>
                <span className="flex items-center gap-2">
                  <Pill>{nguoi.length} người</Pill>
                  <span style={{ transform: daDong ? 'rotate(-90deg)' : 'none', transition: 'transform .15s' }}>
                    <LineIcon name="chevronDown" size={16} color="var(--text-muted)" />
                  </span>
                </span>
              </button>
              {!daDong && (
                <div className="mt-3 space-y-2">
                  {tp.length > 0 ? veNguoi(tp, true) : (
                    <p className="text-[11px] text-[var(--text-muted)] italic">Chưa có trưởng phòng</p>
                  )}
                  {than.length > 0 && <Nhanh>{than}</Nhanh>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
