import asyncio, sys
from rich.prompt import Prompt, Confirm
from rich.table import Table
from pathlib import Path
from core.theme import console, rule, info, ok, warn, error, PRIMARY, MUTED
from config_loader import config
from core.logger import logger
from .model_selector import select_best_model, mark_model_memory_failed
from .ollama_client import query_model, ensure_model_available, health_check, ModelMemoryError
from .council import council_query
from .task_router import route_task
from db.store import add_task, get_recent_tasks, record_model_result
from fs.file_ops import read_file, write_file, edit_file, revert_file
from .memory_manager import MemoryManager
from .vector_memory import VectorMemory
from .task_decomposer import decompose_task
from .autonomous import autonomous_loop
from .skill_chain import skill_chain
from .persistent_queue import save_queue, load_queue
from .prompt_optimizer import PromptOptimizer
from .scheduler import Scheduler
from .safety_filter import SafetyFilter
from .conversation import ConversationManager
from .react_planner import react_loop
from .tools_registry import create_default_tools
from .voice_manager import VoiceManager

class EustathiusAgent:
    def __init__(self):
        self.priority = config.get("default_priority", "balanced")
        self.council_enabled = config.get("council_enabled", False)
        self.memory = MemoryManager() if config["memory"].get("enabled") else None
        self.vector_memory = VectorMemory() if config["memory"].get("use_chroma") else None
        self.task_queue = asyncio.Queue()
        self.bg_tasks = []
        self.autonomous_enabled = config.get("autonomous",{}).get("enabled", False)
        self.prompt_optimizer = PromptOptimizer()
        self.scheduler = Scheduler(self._scheduled_task_callback) if config.get("scheduler",{}).get("enabled") else None
        self.safety = SafetyFilter()
        self.conversation = ConversationManager()
        self.tools = create_default_tools() if config.get("tools",{}).get("enabled", True) else None
        self.voice = VoiceManager()
        self.persona = "default"
        self.react_enabled = config.get("react",{}).get("enabled", True)
        for task_text, priority in load_queue(): self.task_queue.put_nowait((task_text, priority))

    async def _scheduled_task_callback(self, task): await self._execute_task(task, self.priority)

    async def process_queue(self):
        while True:
            task_desc, prio = await self.task_queue.get()
            try: await self._execute_task(task_desc, prio or self.priority)
            except Exception as e: logger.error(f"Queue task failed: {e}")
            self.task_queue.task_done()

    async def start_background_worker(self):
        if not await health_check():
            error("Ollama is not running. Start it with: ollama serve")
            sys.exit(1)
        task = asyncio.create_task(self.process_queue())
        self.bg_tasks.append(task)
        if self.scheduler: self.bg_tasks.append(self.scheduler.start())
        self.conversation.new_session()

    async def _inject_memory_context(self, task: str) -> str:
        contexts = []
        if self.memory:
            for mem, sim in self.memory.retrieve_relevant(task, 3):
                contexts.append(f"User: {mem['user']}\nAssistant: {mem['assistant']}")
        if self.vector_memory:
            for doc in self.vector_memory.search(task, 2): contexts.append(f"Remembered: {doc}")
        if self.conversation.history:
            recent = self.conversation.history[-6:]
            contexts.append("\n".join(f"{m['role']}: {m['content']}" for m in recent))
        return "\n".join(contexts) + "\n\n[Current task]\n" + task if contexts else task

    def _get_system_prompt(self, skill) -> str:
        persona_text = config["personas"].get(self.persona, config["personas"]["default"])
        optimized = self.prompt_optimizer.get_optimized_prompt(skill.name, skill.description or "")
        return persona_text + "\n" + optimized

    async def _execute_task(self, task_text, priority):
        enhanced_task = await self._inject_memory_context(task_text)
        rule("task")
        console.print(f"[dim_text]  {task_text[:90]}[/dim_text]")

        routed_skill = route_task(task_text) or route_task("explain")
        if routed_skill and routed_skill.name == "filesystem":
            result = await self._execute_single_task(task_text, priority)
        elif self.react_enabled and ("?" in task_text or len(task_text.split()) > 10):
            model = await select_best_model(priority)
            system = self._get_system_prompt(routed_skill)
            result = await react_loop(task_text, model, self.tools, system=system,
                                      max_steps=config.get("react",{}).get("max_steps",5))
        else:
            result = await self._execute_pipeline(enhanced_task, priority)

        ok_flag, filtered = self.safety.check(result)
        if not ok_flag:
            warn("Output blocked by safety filter")
            result = "[Blocked]"

        self.conversation.add_exchange(task_text, result)
        if self.memory: self.memory.add_interaction(task_text, result)
        if self.vector_memory: self.vector_memory.add_memory(f"Task: {task_text} | Result: {result}")
        self.conversation.save_session()

        rule("result")
        console.print(f"[body]{result}[/body]")
        rule()
        await self.voice.speak(result)

    async def _execute_pipeline(self, task_text, priority):
        if config.get("task_decomposer",{}).get("enabled") and len(task_text.split()) > 10:
            subtasks = await decompose_task(task_text)
            if subtasks and len(subtasks) > 1:
                info(f"Decomposed into {len(subtasks)} subtask(s)")
                results = []
                for i, sub in enumerate(subtasks, 1):
                    rule(f"subtask {i}/{len(subtasks)}")
                    results.append(await self._execute_single_task(sub, priority))
                return "\n".join(f"{i}. {r}" for i, r in enumerate(results, 1))
        return await self._execute_single_task(task_text, priority)

    async def _execute_single_task(self, task_text, priority):
        for attempt in range(1, 4):
            rule(f"attempt {attempt}/3")
            skill = route_task(task_text) or route_task("explain")
            if skill.name == "filesystem":
                model = "local"
                console.print(f"[dim_text]  model   [/dim_text][bright]{model}[/bright]")
                console.print(f"[dim_text]  skill   [/dim_text][{PRIMARY}]{skill.name}[/{PRIMARY}]")
                try:
                    result = await skill.execute(task_text, model)
                except Exception as e:
                    result = f"Error: {e}"
                rule("draft")
                console.print(f"[body]{result}[/body]")
                add_task(task_text, skill.name, model, priority, result, "completed" if "error" not in result.lower() else "failed")
                return result

            try: model = await select_best_model(priority)
            except Exception as e: error(f"Model selection failed: {e}"); return "Aborted."
            console.print(f"[dim_text]  model   [/dim_text][bright]{model}[/bright]")
            console.print(f"[dim_text]  skill   [/dim_text][{PRIMARY}]{skill.name}[/{PRIMARY}]")
            system = self._get_system_prompt(skill)
            try:
                if self.council_enabled:
                    from .ollama_client import list_models_async
                    models = await list_models_async()
                    if len(models) > 3:
                        from .model_selector import get_cached_benchmarks
                        bench = await get_cached_benchmarks()
                        sorted_models = sorted(bench.items(), key=lambda x: x[1], reverse=True)
                        models = [m for m, _ in sorted_models[:3]]
                    council_res = await asyncio.wait_for(council_query(models, task_text, system=system),
                                                        timeout=config["skill_timeout"])
                    result = council_res["final_answer"]
                else:
                    result = await asyncio.wait_for(skill.execute(task_text, model, system_prompt=system),
                                                    timeout=config["skill_timeout"])
            except ModelMemoryError:
                logger.warning(f"Model {model} out of memory, skipping.")
                warn(f"{model} exceeds available RAM; skipping")
                mark_model_memory_failed(model)
                continue
            except asyncio.TimeoutError:
                result = "Task timed out."
                record_model_result(model, False)
            except Exception as e:
                result = f"Error: {e}"
                record_model_result(model, False)

            is_success = "error" not in result.lower()
            record_model_result(model, is_success)

            if self.autonomous_enabled and not is_success:
                info("Autonomous self-improvement running...")
                improved = await autonomous_loop(task_text, result, skill, model,
                                                 config.get("autonomous",{}).get("max_iterations",5))
                if improved != result:
                    add_task(task_text, skill.name, model, priority, improved, "completed")
                    return improved

            rule("draft")
            console.print(f"[body]{result}[/body]")
            if Confirm.ask("[dim_text]  Accept this result?[/dim_text]", default=True):
                add_task(task_text, skill.name, model, priority, result, "completed")
                return result
            else:
                hint = Prompt.ask("[dim_text]  Improvement hint (Enter to retry)[/dim_text]")
                if hint:
                    task_text = f"{task_text}\n\nAdditional instructions: {hint}"
                    self.prompt_optimizer.update_from_feedback(skill.name, system, hint)
                new_prio = Prompt.ask("[dim_text]  Priority? speed|accuracy|balanced (Enter to keep)[/dim_text]", default="")
                if new_prio in ("speed","accuracy","balanced"): self.priority = new_prio
                continue
        return "Incomplete after retries."

    async def run_task(self, task_text, background=False, priority=None):
        if background:
            self.task_queue.put_nowait((task_text, priority))
            save_queue([(t,p) for t,p in (list(self.task_queue._queue))])  # approximate
            info("Queued for background processing.")
        else:
            await self._execute_task(task_text, priority or self.priority)

    async def handle_file_operation(self, command: str):
        parts = command.strip().split(maxsplit=2)
        if len(parts) < 2:
            error("Usage: read|write|edit|revert <path> [content]")
            return
        action, path = parts[0].lower(), Path(parts[1])
        if action == "read":
            content = read_file(path)
            if content: console.print(content)
        elif action == "write":
            if len(parts) < 3:
                error("Content required.")
                return
            write_file(path, parts[2])
        elif action == "edit":
            if len(parts) < 3:
                error("Content required.")
                return
            edit_file(path, parts[2])
        elif action == "revert": revert_file(path)
        else: error("Unknown file action.")

    async def run_code_interpreter(self, code: str) -> str:
        if not config.get("code_interpreter",{}).get("enabled", True): return "Code interpreter disabled."
        try:
            proc = await asyncio.create_subprocess_exec(sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.cwd()))
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=config["code_interpreter"]["timeout"])
            return stdout.decode() + ("\n" + stderr.decode() if stderr else "")
        except asyncio.TimeoutError: return "Execution timed out."
        except Exception as e: return f"Error: {e}"

    async def reload_config(self):
        import importlib, config_loader
        importlib.reload(config_loader)
        from config_loader import config as new_config
        self.priority = new_config.get("default_priority", "balanced")
        ok("Configuration reloaded")

    async def set_persona(self, name):
        if name in config["personas"]:
            self.persona = name
            ok(f"Persona set to {name}")
        else:
            error(f"Unknown persona. Options: {list(config['personas'].keys())}")

    async def show_history(self):
        tasks = get_recent_tasks(15)
        if not tasks:
            info("No tasks yet.")
            return
        table = Table(show_header=True)
        table.add_column("Time"); table.add_column("Description"); table.add_column("Model"); table.add_column("Status")
        for t in tasks:
            table.add_row(t["timestamp"][:19], t["task_description"][:60], t["model_used"],
                          "done" if t["status"]=="completed" else "failed")
        console.print(table)

    async def shutdown(self):
        all_items = list(self.task_queue._queue)
        save_queue([(t,p) for t,p in all_items])
        self.conversation.save_session()
        for t in self.bg_tasks: t.cancel()
        logger.info("Eustathius shut down.")
