from . import SkillBase
from core.ollama_client import query_model

class SummarizerSkill(SkillBase):
    name="summarizer"; description="Summarize long texts."
    keywords=["summarize","summarise","tldr","abstract","brief","condense"]
    async def execute(self, task, model, council=False, **kwargs):
        text = task.split(":",1)[-1].strip() if ":" in task else task
        prompt = f"Summarize the following in one paragraph:\n\n{text}"
        return await query_model(model, prompt, system="You are a summarization expert.", temperature=0.3)
