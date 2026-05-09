import asyncio, sys
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
from config_loader import config
from core.logger import logger
from .model_selector import select_best_model, mark_model_memory_failed
from .ollama_client import query_model, health_check, ModelMemoryError
from .task_router import route_task
from db.store import add_task, get_recent_tasks
from fs.file_ops import read_file, write_file, edit_file, revert_file
from skills import SkillBase

console = Console()

class EustathiusAgent:
    def __init__(self):
        self.priority = config.get("default_priority", "balanced")
        self.persona = "default"
    async def start_background_worker(self):
        if not await health_check():
            console.print("[red]Ollama is not running![/red]")
            sys.exit(1)
    def _system_prompt(self, skill) -> str:
        return config["personas"].get(self.persona, config["personas"]["default"])
    async def _execute_single_task(self, task_text, priority):
        for attempt in range(1,4):
            console.rule(f"Attempt {attempt}")
            try: model = await select_best_model(priority)
            except Exception as e: console.print(f"[red]Model selection failed: {e}[/red]"); return "Aborted."
            console.print(f"🤖 Model: [bold cyan]{model}[/bold cyan]")
            skill = route_task(task_text) or route_task("explain")
            console.print(f"🎯 Skill: [bold yellow]{skill.name}[/bold yellow]")
            system = self._system_prompt(skill)
            try:
                result = await asyncio.wait_for(skill.execute(task_text, model, system_prompt=system),
                                                timeout=config.get("skill_timeout",120))
            except ModelMemoryError:
                logger.warning(f"Model {model} out of memory, skipping.")
                console.print(f"[yellow]Model {model} requires more RAM. Skipping.[/yellow]")
                mark_model_memory_failed(model)
                continue
            except Exception as e:
                result = f"Error: {e}"
            console.print(Panel(result, title="Draft Result"))
            if Confirm.ask("✅ Satisfactory?", default=True):
                add_task(task_text, skill.name, model, priority, result, "completed")
                return result
            else:
                hint = Prompt.ask("💡 How to improve? (Enter to retry)")
                if hint: task_text = f"{task_text}\n\nAdditional instructions: {hint}"
                new_prio = Prompt.ask("⚡ Priority? [speed/accuracy/balanced] (Enter to keep)", default="")
                if new_prio in ("speed","accuracy","balanced"): self.priority = new_prio
                continue
        return "Incomplete after retries."
    async def run_task(self, task_text, background=False, priority=None):
        await self._execute_single_task(task_text, priority or self.priority)
    async def handle_file_operation(self, cmd):
        parts = cmd.strip().split(maxsplit=2)
        if len(parts)<2: console.print("Usage: read|write|edit|revert <path> [content]"); return
        action, path = parts[0].lower(), Path(parts[1])
        if action=="read":
            c = read_file(path)
            if c: console.print(c)
        elif action=="write":
            if len(parts)<3: console.print("Content required."); return
            write_file(path, parts[2])
        elif action=="edit":
            if len(parts)<3: console.print("Content required."); return
            edit_file(path, parts[2])
        elif action=="revert": revert_file(path)
        else: console.print("Unknown action.")
    async def show_history(self):
        tasks = get_recent_tasks(15)
        if not tasks: console.print("[dim]No tasks yet.[/dim]"); return
        table = Table(show_header=True)
        table.add_column("Time"); table.add_column("Description"); table.add_column("Model"); table.add_column("Status")
        for t in tasks:
            table.add_row(t["timestamp"][:19], t["task_description"][:60], t["model_used"],
                          "✅" if t["status"]=="completed" else "❌")
        console.print(table)
    async def shutdown(self):
        logger.info("Eustathius shut down.")
