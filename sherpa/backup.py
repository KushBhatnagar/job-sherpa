"""Backups of the database to a folder outside the repo.

The database is gitignored (personal data, and a binary that changes every run),
so your application history has no other copy. This writes timestamped copies
to SHERPA_BACKUP_DIR (set in .env), e.g. a synced cloud-drive folder.

Weekly without a scheduler: every `sherpa` command calls auto_backup() first, and it
only does work when the newest backup is older than BACKUP_EVERY_DAYS. If the
tool isn't being used, the database isn't changing, so nothing is missed.

Copies use SQLite's online backup API rather than a file copy, so a backup taken
mid-write is still a consistent database, and each copy is integrity-checked.
"""
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import paths
from .config import load_env

BACKUP_EVERY_DAYS = 7
DEFAULT_KEEP = 8  # ~two months of weekly copies
PREFIX = "sherpa-"
STAMP = "%Y-%m-%d_%H%M%S"


class BackupNotConfigured(Exception):
    pass


def backup_dir() -> Path | None:
    value = load_env().get("SHERPA_BACKUP_DIR", "").strip()
    return Path(value).expanduser() if value else None


def _keep() -> int:
    try:
        return max(1, int(load_env().get("SHERPA_BACKUP_KEEP", DEFAULT_KEEP)))
    except ValueError:
        return DEFAULT_KEEP


def list_backups(dest: Path) -> list[Path]:
    """Oldest first. The timestamp in the name sorts chronologically."""
    if not dest.is_dir():
        return []
    return sorted(dest.glob(f"{PREFIX}*.db"))


def _stamp_of(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem[len(PREFIX):], STAMP)
    except ValueError:
        return None


def make_backup(dest: Path | None = None) -> Path:
    dest = dest or backup_dir()
    if dest is None:
        raise BackupNotConfigured(
            "SHERPA_BACKUP_DIR is not set — add it to .env (see .env.example).")
    if not dest.parent.is_dir():
        # Don't mkdir -p into a path whose parent is missing: that usually means
        # a cloud drive isn't mounted, and we'd silently create a stray tree.
        raise FileNotFoundError(f"Backup folder's parent doesn't exist: {dest.parent}")
    dest.mkdir(exist_ok=True)

    target = dest / f"{PREFIX}{datetime.now().strftime(STAMP)}.db"
    src = sqlite3.connect(paths.db_path())
    out = sqlite3.connect(target)
    try:
        src.backup(out)
        result = out.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        out.close()
        src.close()
    if result != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Backup failed its integrity check ({result}); nothing kept.")

    for old in list_backups(dest)[:-_keep()]:
        old.unlink(missing_ok=True)
    return target


def auto_backup() -> None:
    """Called before every sherpa command. Never raises — a backup problem must not
    stop the actual work, it just gets reported."""
    try:
        dest = backup_dir()
        if dest is None or not paths.db_path().exists():
            return
        backups = list_backups(dest)
        newest = _stamp_of(backups[-1]) if backups else None
        if newest and datetime.now() - newest < timedelta(days=BACKUP_EVERY_DAYS):
            return
        path = make_backup(dest)
        print(f"[weekly backup] saved {path.name} -> {dest}", file=sys.stderr)
    except Exception as e:
        print(f"[weekly backup] skipped: {e}", file=sys.stderr)
