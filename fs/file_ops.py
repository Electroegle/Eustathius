from pathlib import Path
from .backup import create_backup, restore_backup
from rich.prompt import Confirm
def ask_permission(action, path): return Confirm.ask(f"🔐 Allow {action} on {path}?", default=False)
def read_file(path):
    if not path.exists(): print("File not found."); return None
    if not ask_permission("read", path): return None
    try: return path.read_text(encoding="utf-8")
    except Exception as e: print(f"Read error: {e}"); return None
def write_file(path, content):
    if path.exists():
        if not ask_permission("overwrite", path): return False
        bak = create_backup(path); print(f"Backup: {bak}")
    try: path.write_text(content, encoding="utf-8"); print(f"Written: {path}"); return True
    except Exception as e: print(f"Write error: {e}"); return False
def edit_file(path, new_content):
    if not path.exists(): print("File not found."); return False
    if not ask_permission("edit", path): return False
    bak = create_backup(path)
    try: path.write_text(new_content, encoding="utf-8"); print(f"Edited: {path} (backup {bak})"); return True
    except Exception as e: print(f"Edit error: {e}"); return False
def revert_file(backup_path):
    if not ask_permission("revert", backup_path): return False
    return restore_backup(backup_path)
