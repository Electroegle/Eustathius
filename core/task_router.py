from skills.skill_loader import load_skills
from plugins.plugin_loader import load_plugins
SKILLS = load_skills() + load_plugins()
def route_task(task: str):
    tl = task.lower()
    best, best_score = None, 0
    for sk in SKILLS:
        s = sum(1 for kw in sk.keywords if kw in tl)
        if s > best_score: best_score, best = s, sk
    return best or (SKILLS[0] if SKILLS else None)
