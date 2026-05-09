import importlib, inspect
from pathlib import Path
from . import SkillBase
def load_skills():
    skills = []
    for f in Path(__file__).parent.glob("*.py"):
        if f.stem.startswith("__") or f.stem=="skill_loader": continue
        mod = importlib.import_module(f"skills.{f.stem}")
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, SkillBase) and obj is not SkillBase:
                skills.append(obj())
    return skills
