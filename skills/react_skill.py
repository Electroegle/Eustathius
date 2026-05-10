
from . import SkillBase


class ReactSkill(SkillBase):
    name="react"; description="Use ReAct reasoning with tools."
    keywords=["plan","reason","think step by step","agent","tool"]
    async def execute(self, task, model, council=False, **kwargs):
        return "ReAct reasoning is handled by the main agent loop."
