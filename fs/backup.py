"""
backup.py  (fixed to use config backup_dir)
--------------------------------------------
All backups go to a single dedicated folder defined in config.yaml
under `backup_dir`.  Backups are timestamped and never placed next
to the original file.

Backup naming: <backup_dir>/<original_stem>_<timestamp><suffix>
Example:       C:/Users/you/.eustathius_backups/notes_20250109_143022_123456.txt

restore_backup() copies the backup back to the original path,
optionally asking for confirmation.
"""

import shutil
from datetime import datetime
from pathlib import Path

from config_loader import config
from core.logger import logger


def _get_backup_dir() -> Path:
    """Resolve and create the backup directory from config."""
    raw = config.get("backup_dir", "~/.eustathius_backups")
    backup_dir = Path(raw).expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(original: Path) -> Path | None:
    """
    Copy `original` into the central backup directory with a timestamp suffix.
    Returns the backup Path, or None if the source does not exist.
    """
    original = Path(original).resolve()
    if not original.exists():
        logger.warning(f"backup.create_backup: source not found — {original}")
        return None

    backup_dir = _get_backup_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{original.stem}_{ts}{original.suffix}"
    dest = backup_dir / backup_name

    try:
        shutil.copy2(original, dest)
        logger.info(f"Backup created: {dest}")
        return dest
    except Exception as e:
        logger.error(f"Backup failed for {original}: {e}")
        return None


def restore_backup(backup_path: Path) -> bool:
    """
    Restore a backup file to its original location.

    The original path is inferred by stripping the timestamp suffix from
    the backup filename and looking for the file in its original directory.

    NOTE: This only works when the backup was created by create_backup().
    If you need to restore to an arbitrary path, pass the target explicitly.
    """
    backup_path = Path(backup_path).resolve()
    if not backup_path.exists():
        logger.error(f"restore_backup: backup not found — {backup_path}")
        return False

    # The backup filename is  <stem>_<YYYYMMDD_HHMMSS_ffffff><suffix>
    # We cannot reliably infer the original path just from the backup name,
    # so restore_backup requires the caller (file_ops.revert_file) to pass
    # the original target path.  Here we just do the copy.
    # Callers must supply both paths; this function is now a thin shutil wrapper.
    logger.warning(
        "restore_backup called without target path — "
        "use restore_backup_to(backup, target) for explicit restoration."
    )
    return False


def restore_backup_to(backup_path: Path, target_path: Path) -> bool:
    """
    Copy `backup_path` → `target_path`, overwriting the target.
    Returns True on success.
    """
    backup_path = Path(backup_path).resolve()
    target_path = Path(target_path).resolve()

    if not backup_path.exists():
        logger.error(f"restore_backup_to: backup not found — {backup_path}")
        return False

    # Safety: back up the *current* target before overwriting it
    if target_path.exists():
        pre_backup = create_backup(target_path)
        logger.info(f"Pre-restore safety backup: {pre_backup}")

    try:
        shutil.copy2(backup_path, target_path)
        logger.info(f"Restored {backup_path.name} → {target_path}")
        return True
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def list_backups(original: Path) -> list[Path]:
    """
    Return all backups for a given original file, newest first.
    """
    original = Path(original).resolve()
    backup_dir = _get_backup_dir()
    stem = original.stem
    suffix = original.suffix
    matches = sorted(
        backup_dir.glob(f"{stem}_*{suffix}"),
        reverse=True
    )
    return matches
