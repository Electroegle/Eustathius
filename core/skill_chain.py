from core.task_router import SKILLS


class SkillChain:
    def __init__(self): self._skills = {s.name: s for s in SKILLS}
    async def execute_skill(self, skill_name, task, model, council=False, **kwargs):
        skill = self._skills.get(skill_name)
        if not skill: return f"Skill '{skill_name}' not found."
        return await skill.execute(task, model, council, **kwargs)

skill_chain = SkillChain()
