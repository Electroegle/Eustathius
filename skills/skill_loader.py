import importlib, inspect
from pathlib import Path
from . import SkillBase

def _load_from_dir(pkg_prefix: str, directory: Path) -> list:
    skills = []
    for f in directory.glob("*.py"):
        if f.stem.startswith("__") or "template" in f.stem or f.stem == "skill_loader":
            continue
        try:
            mod = importlib.import_module(f"{pkg_prefix}.{f.stem}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, SkillBase) and obj is not SkillBase:
                    skills.append(obj())
        except Exception as e:
            import logging
            logging.getLogger("eustathius").warning(f"Skill load failed ({f}): {e}")
    return skills

def load_skills() -> list:
    base_dir   = Path(__file__).parent
    custom_dir = base_dir / "custom"
    skills = _load_from_dir("skills", base_dir)
    if custom_dir.exists():
        skills += _load_from_dir("skills.custom", custom_dir)
    return skills
