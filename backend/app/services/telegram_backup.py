"""Backup offsite via Telegram Bot — send DB + uploads as ZIP file.

Free, no OAuth needed. Telegram Bot API limit: 50MB per file.
"""

import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/tmp/jama-backups")


def create_backup_zip(db_path: str = "jama.db", upload_dirs: list[str] | None = None) -> str | None:
    """Create a ZIP file containing the database and optional upload directories.

    Returns the path to the created ZIP file, or None on failure.
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_path = BACKUP_DIR / f"jama_backup_{date_str}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add database
            if os.path.exists(db_path):
                zf.write(db_path, f"db/{os.path.basename(db_path)}")

            # Add upload directories
            if upload_dirs:
                for upload_dir in upload_dirs:
                    if os.path.isdir(upload_dir):
                        for root, _dirs, files in os.walk(upload_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(upload_dir))
                                zf.write(file_path, arcname)

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        logger.info("Backup created: %s (%.1f MB)", zip_path, size_mb)
        return str(zip_path)
    except Exception as e:
        logger.error("Backup creation failed: %s", e)
        return None


async def send_backup_via_telegram(zip_path: str, bot_token: str, chat_id: int) -> bool:
    """Send the backup ZIP file via Telegram Bot API.

    Telegram Bot API limit: 50MB per file.
    Returns True on success, False on failure.
    """
    import httpx

    file_size = os.path.getsize(zip_path)
    if file_size > 50 * 1024 * 1024:
        logger.warning(
            "Backup file too large for Telegram (%.1f MB > 50 MB)",
            file_size / 1024 / 1024,
        )
        return False

    try:
        filename = os.path.basename(zip_path)
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

        with open(zip_path, "rb") as f:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": (
                            f"Backup JAMA CRM — "
                            f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}\n"
                            f"File: {filename}\n"
                            f"Size: {file_size / 1024 / 1024:.1f} MB"
                        ),
                    },
                    files={"document": (filename, f, "application/zip")},
                )

                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("ok"):
                        logger.info("Backup sent to Telegram chat %s", chat_id)
                        return True

                logger.error(
                    "Telegram send failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False


def cleanup_old_backups(keep_days: int = 7) -> int:
    """Remove backup files older than keep_days. Returns count of deleted files."""
    if not BACKUP_DIR.exists():
        return 0

    cutoff = datetime.now().timestamp() - (keep_days * 86400)
    deleted = 0

    for f in BACKUP_DIR.glob("jama_backup_*.zip"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1

    return deleted
