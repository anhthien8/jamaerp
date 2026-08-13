"""Dọn dữ liệu seed mẫu khỏi prod — chạy MỘT LẦN ngày 13/08/2026.

Bối cảnh: audit demo-data 13/08/2026 xác nhận prod còn nguyên bộ bản ghi seed
("Chị Mai/Anh Tuấn/Chị Hương/Anh Minh/Chị Lan") lẫn với dữ liệu thật. Chủ dự án
chốt: XÓA toàn bộ seed nghiệp vụ, GIỮ 9 lead Lark (dữ liệu thật nhập qua seed),
GIỮ users/teams/settings. Backup Telegram đã chạy xong trước khi xóa
(jama-crm-20260813-215258.dump).

Cơ chế: projects/customers/quotations/contracts KHÔNG có API DELETE nên xóa
thẳng qua Postgres (DATABASE_PUBLIC_URL của Railway), một transaction duy nhất.
ID khóa cứng theo kết quả audit — script tự đối chiếu code/tên từng bản ghi
trước khi xóa, lệch là hủy toàn bộ.

Chạy:
    DB_URL=... python -m scripts.cleanup_seed_prod_20260813            # dry-run
    DB_URL=... python -m scripts.cleanup_seed_prod_20260813 --execute  # xóa thật
"""

import asyncio
import os
import sys

import asyncpg

# (id, mã/định danh kỳ vọng) — đối chiếu trước khi xóa, lệch là abort
SEED_PROJECTS = [
    ("6f4cf511-af4f-4d4b-8df7-d8c8ddf294c9", "PRJ-2026-001"),
    ("ad75af1d-0922-45b4-bab6-968edf16cab3", "PRJ-2026-002"),
    ("93920d26-401c-4e37-8d8a-b50a775e4769", "PRJ-2026-003"),
    ("1341b0b3-20af-4ee9-a2c8-95d7bf7768a0", "PRJ-2026-004"),
    ("3d72f89c-df96-4f56-8be4-d7c83ca4bef8", "PRJ-2026-005"),
]
SEED_CUSTOMERS = [
    ("04dc7b8b-10b0-4896-b80d-937b053cde11", "Chị Mai"),
    ("c7f3c311-adb4-4183-ab7b-decced48eaca", "Anh Tuấn"),
    ("d8dcf0b4-7614-4210-afed-70de692ec7a3", "Chị Hương"),
    ("55998438-5090-4dad-ba0f-549f19ac83e3", "Chị Lan"),
    ("8b96cd53-3971-45bc-8d97-1acfbe6e032a", "Công ty TNHH Minh Design"),
]
SEED_TRANSACTIONS = [
    ("25c19538-048c-40dd-8e0d-0d0b8fc87968", "TX-001"),
    ("2061bca5-7a73-4606-9108-0ff4cf245778", "TX-002"),
    ("67eb689e-28ba-41a3-b1d7-83477ba9e16d", "TX-003"),
    ("bb7bf92d-3b96-405d-99ae-3d97041aca86", "TX-004"),
    ("864ecfc8-1ed2-4c84-9b2b-e69ee3e4a9fc", "TX-005"),
    ("d2aece1a-ce0a-4e1b-b6ad-d3c17fe2304a", "TX-006"),
    ("90b5c028-b84d-4b26-bc53-03e64e2975f6", "TX-007"),
    ("f6a8a89b-5dc9-47c8-98c2-e8f64d6204c7", "TX-008"),
    ("62b6d5c0-7297-4dea-bf76-b4fb8378c03b", "TX-009"),
    ("5b177e10-a88f-49f9-bc95-447ce99b0ac5", "TX-010"),
    ("a72c68cd-b9f1-4fc5-ae02-2b669241480d", "TX-011"),
    ("793578aa-45fb-4c2c-a8bf-0d88cffec038", "TX-012"),
]
SEED_QUOTATIONS = [
    ("dd3f8786-4ea6-4381-9701-f1ef6e648826", "BG-2026-001"),
    ("018295a4-2a8e-414d-8197-66c3e57bb556", "BG-2026-002"),
    ("f9c973e3-e84b-42a3-976a-49f71bade94c", "BG-2026-003"),
    ("17d0df0e-9f98-4954-97f5-06ef7d9ec4a4", "BG-2026-004"),
]
SEED_CONTRACTS = [
    ("bb490e98-21cc-4424-a4bd-6f8226a789c8", "HD-2026-001"),
    ("794ac4ef-5bfa-4608-85a8-386b79787230", "HD-2026-002"),
    ("3f6c3370-8904-45fb-b88b-382e76482b7e", "HD-2026-003"),
]
SEED_FIXED_COSTS = [
    ("876d7544-00d2-471c-b706-99d1f29995eb", "Tien mat bang"),
    ("0f0b7356-0879-4f62-8083-495e287cdf45", "Dien nuoc"),
    ("c3d8b118-bb96-4159-a363-aa4e12d1a619", "Internet"),
    ("0dc88c7c-d723-4d5b-ac9e-cda863029b50", "Bao hiem office"),
]
# Kho vật tư prod 100% là mẫu (probe 13/08): 10 vật tư seed.py + 1 bản ghi test
# import tự nhận «bỏ qua». Khóa theo code + tên, không theo id (audit không ghi id).
SEED_MATERIALS = [
    ("VT-001", "Go cong nghiep MDF loi xanh"),
    ("VT-002", "San go Egger 12mm"),
    ("VT-003", "Da granite den An Do"),
    ("VT-004", "Son Dulux noi that cao cap"),
    ("VT-005", "Inox 304 ong vuong 40x40"),
    ("VT-006", "Kinh cuong luc 10mm"),
    ("VT-007", "Den LED panel 600x600"),
    ("VT-008", "Vai sofa nhap Bi"),
    ("VT-009", "Ong PPR nong 25mm"),
    ("VT-010", "Ban le giam chan Blum"),
    ("VT-011", "[TEST] Bản ghi kiểm thử import — bỏ qua"),
]
MATERIAL_CODES = [c for c, _ in SEED_MATERIALS]

PROJECT_IDS = [pid for pid, _ in SEED_PROJECTS]


async def verify(conn: asyncpg.Connection) -> None:
    """Đối chiếu từng ID với mã/tên kỳ vọng — lệch bất kỳ dòng nào là abort."""
    checks = [
        ("projects", "code", SEED_PROJECTS),
        ("customers", "name", SEED_CUSTOMERS),
        ("transactions", "code", SEED_TRANSACTIONS),
        ("quotations", "code", SEED_QUOTATIONS),
        ("contracts", "code", SEED_CONTRACTS),
        ("fixed_costs", "category", SEED_FIXED_COSTS),
    ]
    for table, col, expected in checks:
        rows = await conn.fetch(
            f"SELECT id, {col} AS val FROM {table} WHERE id = ANY($1)",
            [i for i, _ in expected],
        )
        got = {r["id"]: r["val"] for r in rows}
        for rid, want in expected:
            if rid not in got:
                raise SystemExit(f"ABORT: {table} {rid} ({want}) không còn trong DB")
            if got[rid] != want:
                raise SystemExit(
                    f"ABORT: {table} {rid} là «{got[rid]}», kỳ vọng «{want}» — ID lệch, không xóa gì cả"
                )
        print(f"  ✓ {table}: {len(expected)}/{len(expected)} bản ghi khớp đúng mã/tên")

    # Kho vật tư: khóa theo code, và toàn bộ kho phải ĐÚNG BẰNG danh sách mẫu —
    # lòi ra vật tư thật nào khác là abort, không xóa kho nữa
    mats = await conn.fetch("SELECT code, name FROM materials ORDER BY code")
    got_mats = {r["code"]: r["name"] for r in mats}
    want_mats = dict(SEED_MATERIALS)
    if got_mats != want_mats:
        raise SystemExit(
            f"ABORT: kho vật tư prod lệch danh sách mẫu — có {sorted(got_mats)} , "
            f"kỳ vọng {sorted(want_mats)}. Có thể đã có vật tư thật, không đụng kho."
        )
    print(f"  ✓ materials: {len(SEED_MATERIALS)}/{len(SEED_MATERIALS)} — toàn kho đều là mẫu/test")


async def report_children(conn: asyncpg.Connection) -> dict:
    """Đếm bản ghi con/liên quan sẽ bị ảnh hưởng, kèm cảnh giới phạm vi."""
    out = {}
    out["tasks"] = await conn.fetchval(
        "SELECT COUNT(*) FROM tasks WHERE project_id = ANY($1)", PROJECT_IDS
    )
    out["task_activities"] = await conn.fetchval(
        "SELECT COUNT(*) FROM task_activities WHERE task_id IN "
        "(SELECT id FROM tasks WHERE project_id = ANY($1))",
        PROJECT_IDS,
    )
    out["commissions"] = await conn.fetchval(
        "SELECT COUNT(*) FROM commissions WHERE project_id = ANY($1)", PROJECT_IDS
    )
    out["material_usages"] = await conn.fetchval(
        "SELECT COUNT(*) FROM material_usages WHERE project_id = ANY($1)", PROJECT_IDS
    )
    out["attendance_records"] = await conn.fetchval(
        "SELECT COUNT(*) FROM attendance_records WHERE project_id = ANY($1)", PROJECT_IDS
    )
    # Giao dịch/báo giá/hợp đồng NGOÀI danh sách seed nhưng trỏ vào dự án seed
    # → nếu >0 nghĩa là có dữ liệu thật gắn nhầm dự án mẫu, phải dừng lại xem tay
    out["stray_transactions"] = await conn.fetchval(
        "SELECT COUNT(*) FROM transactions WHERE project_id = ANY($1) AND NOT (id = ANY($2))",
        PROJECT_IDS, [i for i, _ in SEED_TRANSACTIONS],
    )
    out["stray_quotations"] = await conn.fetchval(
        "SELECT COUNT(*) FROM quotations WHERE project_id = ANY($1) AND NOT (id = ANY($2))",
        PROJECT_IDS, [i for i, _ in SEED_QUOTATIONS],
    )
    out["stray_contracts"] = await conn.fetchval(
        "SELECT COUNT(*) FROM contracts WHERE project_id = ANY($1) AND NOT (id = ANY($2))",
        PROJECT_IDS, [i for i, _ in SEED_CONTRACTS],
    )
    out["leads_total"] = await conn.fetchval("SELECT COUNT(*) FROM leads")
    return out


async def main() -> None:
    execute = "--execute" in sys.argv
    dsn = os.environ.get("DB_URL")
    if not dsn:
        raise SystemExit("Thiếu biến môi trường DB_URL (DATABASE_PUBLIC_URL của Railway)")

    conn = await asyncpg.connect(dsn)
    try:
        print("=== Đối chiếu ID seed với DB prod ===")
        await verify(conn)

        print("\n=== Bản ghi liên quan ===")
        info = await report_children(conn)
        for k, v in info.items():
            print(f"  {k}: {v}")

        if info["stray_transactions"] or info["stray_quotations"] or info["stray_contracts"]:
            raise SystemExit(
                "ABORT: có giao dịch/báo giá/hợp đồng NGOÀI seed đang trỏ vào dự án seed "
                "— có thể là dữ liệu thật gắn nhầm, cần xem tay trước khi xóa"
            )

        if not execute:
            print("\nDRY-RUN — chưa xóa gì. Chạy lại với --execute để xóa thật.")
            return

        print("\n=== XÓA (một transaction) ===")
        async with conn.transaction():
            counts = {}
            counts["task_activities"] = await conn.execute(
                "DELETE FROM task_activities WHERE task_id IN "
                "(SELECT id FROM tasks WHERE project_id = ANY($1))", PROJECT_IDS)
            counts["tasks"] = await conn.execute(
                "DELETE FROM tasks WHERE project_id = ANY($1)", PROJECT_IDS)
            counts["contracts"] = await conn.execute(
                "DELETE FROM contracts WHERE id = ANY($1)", [i for i, _ in SEED_CONTRACTS])
            counts["quotations"] = await conn.execute(
                "DELETE FROM quotations WHERE id = ANY($1)", [i for i, _ in SEED_QUOTATIONS])
            counts["commissions"] = await conn.execute(
                "DELETE FROM commissions WHERE project_id = ANY($1)", PROJECT_IDS)
            counts["transactions"] = await conn.execute(
                "DELETE FROM transactions WHERE id = ANY($1)", [i for i, _ in SEED_TRANSACTIONS])
            counts["material_usages"] = await conn.execute(
                "DELETE FROM material_usages WHERE project_id = ANY($1) OR material_id IN "
                "(SELECT id FROM materials WHERE code = ANY($2))",
                PROJECT_IDS, MATERIAL_CODES)
            counts["materials"] = await conn.execute(
                "DELETE FROM materials WHERE code = ANY($1)", MATERIAL_CODES)
            # Giờ công là dữ liệu thật của nhân sự — chỉ gỡ liên kết, không xóa
            counts["attendance_records (SET NULL)"] = await conn.execute(
                "UPDATE attendance_records SET project_id = NULL WHERE project_id = ANY($1)",
                PROJECT_IDS)
            counts["projects"] = await conn.execute(
                "DELETE FROM projects WHERE id = ANY($1)", PROJECT_IDS)
            counts["customers"] = await conn.execute(
                "DELETE FROM customers WHERE id = ANY($1)", [i for i, _ in SEED_CUSTOMERS])
            counts["fixed_costs"] = await conn.execute(
                "DELETE FROM fixed_costs WHERE id = ANY($1)", [i for i, _ in SEED_FIXED_COSTS])

            for k, v in counts.items():
                print(f"  {k}: {v}")

            leads_after = await conn.fetchval("SELECT COUNT(*) FROM leads")
            if leads_after != info["leads_total"]:
                raise SystemExit(
                    f"ABORT-ROLLBACK: leads đổi từ {info['leads_total']} → {leads_after}!"
                )
            print(f"  ✓ leads giữ nguyên: {leads_after}")

        print("\nXONG — đã commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
