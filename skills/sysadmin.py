from . import SkillBase
from core.ollama_client import query_model
import asyncio

class SysAdminSkill(SkillBase):
    name="sysadmin"; description="Execute safe shell commands."
    keywords=["shell","command","run","execute","system","admin","process","kill"]
    async def execute(self, task, model, council=False, **kwargs):
        system = "Suggest a safe Windows command. Output only the command."
        cmd = await query_model(model, task, system=system, temperature=0.2, max_tokens=200)
        from rich.prompt import Confirm
        if not Confirm.ask(f"Run [bold]{cmd}[/bold]?", default=False): return "Command rejected."
        try:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            return stdout.decode() + stderr.decode()
        except Exception as e: return f"Error: {e}"
