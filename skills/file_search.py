from . import SkillBase
from pathlib import Path
from rich.prompt import Prompt

class FileSearchSkill(SkillBase):
    name="file_search"; description="Find files by name pattern."
    keywords=["find file","search file","locate","grep"]
    async def execute(self, task, model, council=False, **kwargs):
        directory = Prompt.ask("Directory", default=".")
        pattern = Prompt.ask("Pattern (e.g., *.py)")
        try:
            matches = list(Path(directory).rglob(pattern))
            return "\n".join(str(m) for m in matches[:20]) if matches else "No files found."
        except Exception as e: return f"Error: {e}"
