import importlib
import inspect
from pathlib import Path

from skills import SkillBase


def load_plugins():
    plugins = []
    plugin_dir = Path(__file__).parent
    for f in plugin_dir.glob("*.py"):
        if f.stem.startswith("__") or f.stem == "plugin_loader": continue
        try:
            mod = importlib.import_module(f"plugins.{f.stem}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, SkillBase) and obj is not SkillBase:
                    plugins.append(obj())
        except Exception as e: print(f"Plugin {f.stem} failed: {e}")
    return plugins
