"""
file_ops.py
-----------
Filesystem operations for Eustathius.

Every write path asks for confirmation and creates a timestamped backup before
changing existing content.
"""

from pathlib import Path

from rich.prompt import Confirm

from core.theme import console, error, info, ok, warn
from .backup import create_backup, list_backups, restore_backup_to


def ask_permission(action: str, path: Path) -> bool:
    return Confirm.ask(f"[warn]Allow {action} on[/warn] [bright]{path}[/bright]?", default=False)


def read_file(path: Path) -> str | None:
    path = Path(path).resolve()
    if not path.exists():
        error(f"File not found: {path}")
        return None
    if not path.is_file():
        error(f"Not a file: {path}")
        return None
    if not ask_permission("read", path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        error(f"Read error: {exc}")
        return None


def write_file(path: Path, content: str) -> bool:
    path = Path(path).resolve()
    if path.exists():
        if path.is_dir():
            error(f"Cannot overwrite a directory: {path}")
            return False
        if not ask_permission("overwrite", path):
            return False
        backup = create_backup(path)
        if backup:
            info(f"Backup saved: {backup}")
    elif not ask_permission("create", path):
        return False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        ok(f"Written: {path}")
        return True
    except Exception as exc:
        error(f"Write error: {exc}")
        return False


def edit_file(path: Path, new_content: str) -> bool:
    path = Path(path).resolve()
    if not path.exists():
        error(f"File not found: {path}")
        return False
    if path.is_dir():
        error(f"Cannot edit a directory: {path}")
        return False
    if not ask_permission("edit", path):
        return False

    backup = create_backup(path)
    if not backup:
        error("Could not create backup; edit aborted for safety.")
        return False
    info(f"Backup saved: {backup}")

    try:
        path.write_text(new_content, encoding="utf-8")
        ok(f"Edited: {path}")
        return True
    except Exception as exc:
        error(f"Edit error: {exc}")
        return False


def revert_file(original_path: Path, backup_path: Path | None = None) -> bool:
    """
    Revert original_path to a previous backup.

    If backup_path is given, restores that specific backup. Otherwise, lists the
    five most recent backups and lets the user choose.
    """
    original_path = Path(original_path).resolve()

    if backup_path:
        backup_path = Path(backup_path).resolve()
        if not ask_permission("revert", original_path):
            return False
        return restore_backup_to(backup_path, original_path)

    backups = list_backups(original_path)
    if not backups:
        warn(f"No backups found for {original_path}")
        return False

    console.print(f"[label]Available backups for[/label] [bright]{original_path.name}[/bright]:")
    for idx, backup in enumerate(backups[:5], 1):
        console.print(f"  [{idx}] {backup.name}")

    try:
        choice = int(console.input("Choose backup number (0 to cancel): "))
    except ValueError:
        choice = 0

    if choice < 1 or choice > min(5, len(backups)):
        info("Revert cancelled.")
        return False

    chosen = backups[choice - 1]
    if not ask_permission("revert", original_path):
        return False
    return restore_backup_to(chosen, original_path)
