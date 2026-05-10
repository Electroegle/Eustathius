import re
from skills.skill_loader import load_skills
from plugins.plugin_loader import load_plugins

SKILLS = load_skills() + load_plugins()

def route_task(task_text: str):
    """Pick the skill whose keywords match whole words in the task.
    Returns a skill object, or None if none match."""
    task_lower = task_text.lower()

    filesystem_terms = [
        "copy", "move", "mkdir", "make directory", "create directory",
        "create folder", "folder", "directory", "downloads", "downloades",
        "frames", "farames", "key frames",
    ]
    if any(term in task_lower for term in filesystem_terms):
        for skill in SKILLS:
            if skill.name == "filesystem":
                return skill

    best_skill = None
    best_score = 0

    for skill in SKILLS:
        score = 0
        for kw in skill.keywords:
            # Count each occurrence of the keyword as a whole word
            matches = re.findall(r'\b' + re.escape(kw) + r'\b', task_lower)
            score += len(matches)
        if score > best_score:
            best_score = score
            best_skill = skill

    # Fallback: if still nothing, return the first skill
    if best_score == 0 and SKILLS:
        # Prefer "research" if it exists, else the first one
        for s in SKILLS:
            if s.name == "research":
                return s
        return SKILLS[0]
    return best_skill
