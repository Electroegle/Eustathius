import asyncio
import json
from pathlib import Path

import schedule

from config_loader import config


class Scheduler:
    def __init__(self, callback):
        self.callback = callback
        self.jobs_file = Path(config.get("scheduler",{}).get("job_file","~/.eustathius_scheduled.json")).expanduser()
        self.jobs = json.loads(self.jobs_file.read_text()) if self.jobs_file.exists() else []
        self._running = False

    def add_job(self, interval_min, task):
        self.jobs.append({"interval":interval_min, "task":task})
        schedule.every(interval_min).minutes.do(lambda t=task: asyncio.ensure_future(self.callback(t)))
        self.jobs_file.write_text(json.dumps(self.jobs, indent=2))

    async def run_pending(self):
        while self._running:
            schedule.run_pending()
            await asyncio.sleep(5)

    def start(self):
        self._running = True
        for job in self.jobs:
            schedule.every(job["interval"]).minutes.do(lambda t=job["task"]: asyncio.ensure_future(self.callback(t)))
        return asyncio.create_task(self.run_pending())

    def stop(self): self._running = False
