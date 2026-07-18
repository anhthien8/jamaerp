"""Khôi phục database từ file backup zip (jama_backup_*.zip).

Cách dùng (từ thư mục backend/):
    python scripts/restore_backup.py --list                     # liệt kê backup có sẵn
    python scripts/restore_backup.py backups/jama_backup_X.zip  # khôi phục file chỉ định
    python scripts/restore_backup.py --latest                   # khôi phục bản mới nhất

An toàn:
- DB hiện tại được đổi tên thành jama.db.pre-restore-<stamp> trước khi ghi đè
  (muốn hoàn tác: đổi tên ngược lại).
- BẮT BUỘC dừng backend trước khi restore (file đang mở sẽ hỏng snapshot).

PostgreSQL (production Railway): backup zip này CHỈ áp dụng cho SQLite.
Với Postgres dùng: pg_dump để backup, psql < dump.sql để restore — xem
huong-dan-it.html mục sao lưu.
"""

import argparse
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BACKEND_DIR / "backups"
DB_PATH = BACKEND_DIR / "jama.db"


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("jama_backup_*.zip"), reverse=True)


def restore(zip_path: Path) -> None:
    if not zip_path.exists():
        sys.exit(f"Không thấy file: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.endswith(".db")]
        if not members:
            sys.exit(f"Zip không chứa file .db nào: {zip_path.name}")
        member = members[0]

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if DB_PATH.exists():
            safety = DB_PATH.with_name(f"jama.db.pre-restore-{stamp}")
            shutil.move(str(DB_PATH), str(safety))
            print(f"DB hiện tại đã lưu tạm: {safety.name} (hoàn tác = đổi tên ngược lại)")

        tmp = DB_PATH.with_suffix(".restoring")
        with zf.open(member) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        shutil.move(str(tmp), str(DB_PATH))

    print(f"✅ Đã khôi phục {zip_path.name} → jama.db. Khởi động lại backend để dùng.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Khôi phục DB từ backup zip")
    parser.add_argument("zipfile", nargs="?", help="Đường dẫn file backup zip")
    parser.add_argument("--list", action="store_true", help="Liệt kê backup")
    parser.add_argument("--latest", action="store_true", help="Khôi phục bản mới nhất")
    args = parser.parse_args()

    backups = list_backups()
    if args.list:
        if not backups:
            print("(chưa có backup nào trong backend/backups/)")
        for b in backups:
            size = round(b.stat().st_size / (1024 * 1024), 2)
            print(f"  {b.name}  ({size} MB)")
        return

    if args.latest:
        if not backups:
            sys.exit("Chưa có backup nào để khôi phục")
        restore(backups[0])
        return

    if not args.zipfile:
        parser.print_help()
        sys.exit(1)
    restore(Path(args.zipfile))


if __name__ == "__main__":
    main()
