from core.ollama_client import query_model

from . import SkillBase


class CodingSkill(SkillBase):
    name="coding"; description="Code writer/reviewer"
    keywords=["code","refactor","debug","function","class","script","program"]
    async def execute(self, task, model, council=False, **kwargs):
        system = kwargs.get("system_prompt", "Expert programmer. Output clean code.")
        return await query_model(model, task, system=system, temperature=0.3)
