class SkillBase:
    name: str = "base"
    description: str = ""
    keywords: list = []
    async def execute(self, task, model, council=False, **kwargs) -> str: raise NotImplementedError
