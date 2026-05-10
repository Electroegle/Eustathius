from core.ollama_client import query_model

from . import SkillBase


class ResearchSkill(SkillBase):
    name="research"; description="General knowledge assistant."
    keywords=["explain","what is","how to","tell me","research"]
    async def execute(self, task, model, council=False, **kwargs):
        system = kwargs.get("system_prompt", "You are a helpful assistant.")
        return await query_model(model, task, system=system, temperature=0.7)
