import shutil
from pathlib import Path
from datetime import datetime
def create_backup(p: Path) -> Path:
    if not p.exists(): return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    b = p.with_name(f"{p.name}.backup.{ts}")
    shutil.copy2(p, b)
    return b
def restore_backup(b: Path) -> bool:
    if not b.exists(): return False
    orig = b.with_name(b.name.split(".backup.")[0])
    shutil.copy2(b, orig)
    return True
