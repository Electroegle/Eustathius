from skills import SkillBase
from pathlib import Path
def load_plugins():
    plugins = []
    for f in Path(__file__).parent.glob("*.py"):
        if f.stem.startswith("__") or f.stem=="plugin_loader": continue
        # skip to avoid import errors; you can add later
    return plugins
