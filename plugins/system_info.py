from skills import SkillBase
import psutil, platform

class SystemInfoSkill(SkillBase):
    name="system_info"; description="Report system statistics."
    keywords=["system info","cpu","memory","disk","stats","status"]
    async def execute(self, task, model, council=False, **kwargs):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return (f"CPU: {cpu}%\nMemory: {mem.percent}% used ({mem.used>>20} MB / {mem.total>>20} MB)\n"
                f"Disk: {disk.percent}% used\nOS: {platform.platform()}")
