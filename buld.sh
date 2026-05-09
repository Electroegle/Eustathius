#!/bin/bash
# Eustathius Agent – Minimal, correct build (no deletion)
set -e

mkdir -p core fs skills db plugins logs memory_db conversations

# ---------- requirements.txt ----------
cat > requirements.txt << 'EOF'
ollama>=0.1.0
psutil>=5.9.0
httpx>=0.24.0
rich>=13.0.0
aiofiles>=23.0.0
sentence-transformers>=2.2.0
speechrecognition>=3.8.0
sounddevice>=0.4.6
pyyaml>=6.0
prompt_toolkit>=3.0.0
chromadb>=0.4.0
watchdog>=3.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
EOF

# ---------- config.yaml ----------
cat > config.yaml << 'EOF'
default_priority: balanced
council_enabled: false
max_cpu_for_heavy_model: 75
max_mem_for_heavy_model: 80
skill_timeout: 120
log_level: INFO
log_file: logs/eustathius.log
memory:
  enabled: false
autonomous:
  enabled: false
personas:
  default: "You are Eustathius, a masterful and resourceful AI assistant."
  coder: "You are an expert software engineer. Provide clean, optimal code with explanations."
auto_pull_missing_models: true
react:
  enabled: false
tools:
  enabled: false
EOF

# ---------- config_loader.py ----------
cat > config_loader.py << 'EOF'
import yaml
from pathlib import Path
_config_path = Path(__file__).parent / "config.yaml"
_cfg = None
def load_config():
    global _cfg
    if _cfg is None:
        with open(_config_path) as f:
            _cfg = yaml.safe_load(f)
    return _cfg
config = load_config()
EOF

# ---------- core/sys_monitor.py ----------
cat > core/sys_monitor.py << 'EOF'
import psutil
def get_cpu_percent(): return psutil.cpu_percent(interval=0.1)
def get_memory_percent(): return psutil.virtual_memory().percent
def is_system_under_load(cpu=80, mem=85): return get_cpu_percent()>cpu or get_memory_percent()>mem
def system_stats(): return {"cpu_percent": get_cpu_percent(), "memory_percent": get_memory_percent()}
EOF

# ---------- core/logger.py ----------
cat > core/logger.py << 'EOF'
import logging, sys
from pathlib import Path
from config_loader import config
LOG_FILE = Path(config.get("log_file", "logs/eustathius.log"))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
logging.basicConfig(level=level,format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE),logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Eustathius")
EOF

# ---------- core/ollama_client.py (critical NDJSON + memory fix) ----------
cat > core/ollama_client.py << 'EOF'
import asyncio, aiohttp, json
from typing import List, Optional
from core.logger import logger

OLLAMA_URL = "http://localhost:11434"

class ModelMemoryError(Exception): pass

async def health_check() -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{OLLAMA_URL}/") as r: return r.status == 200
    except: return False

async def list_models_async() -> List[str]:
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{OLLAMA_URL}/api/tags") as r:
            data = await r.json()
            return [m["name"] for m in data.get("models", [])]

async def query_model(model: str, prompt: str, system="", temperature=0.7, max_tokens=1000) -> str:
    payload = {"model": model, "messages": [{"role":"system","content":system},{"role":"user","content":prompt}],
               "options": {"temperature":temperature,"num_predict":max_tokens},"stream":False}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                raw = await resp.text()
                ctype = resp.headers.get("Content-Type","")
        # NDJSON detection
        if "x-ndjson" in ctype or raw.strip().startswith("{"):
            lines = raw.strip().splitlines()
            parts = []
            for line in lines:
                if not line.strip(): continue
                try:
                    obj = json.loads(line)
                    if "error" in obj:
                        err = obj["error"]
                        logger.error(f"Ollama error: {err}")
                        if "memory" in err.lower(): raise ModelMemoryError(err)
                        return f"[Ollama Error] {err}"
                    if "message" in obj and "content" in obj["message"]:
                        parts.append(obj["message"]["content"])
                    elif "response" in obj:
                        parts.append(obj["response"])
                except json.JSONDecodeError: pass
            if parts: return "".join(parts).strip()
        data = json.loads(raw)
        if "error" in data:
            err = data["error"]
            if "memory" in err.lower(): raise ModelMemoryError(err)
            return f"[Ollama Error] {err}"
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"].strip()
        if "response" in data: return data["response"].strip()
        return str(data)
    except ModelMemoryError: raise
    except aiohttp.ClientError as e:
        logger.error(f"Connection error: {e}"); return f"[Connection Error] {e}"
    except Exception as e:
        logger.error(f"Query error: {e}"); return f"[Error] {e}"
EOF

# ---------- core/model_selector.py (memory blacklist) ----------
cat > core/model_selector.py << 'EOF'
import re
from .ollama_client import list_models_async, ModelMemoryError
from .sys_monitor import is_system_under_load
from config_loader import config
from core.logger import logger

_MEM_BLACKLIST = set()
def mark_model_memory_failed(m): _MEM_BLACKLIST.add(m)

def parse_size(name: str) -> float:
    m = re.search(r'(\d+\.?\d*)\s*b', name.lower())
    return float(m.group(1)) if m else (0.5 if "nano" in name or "tiny" in name else 7.0)

async def select_best_model(priority=None) -> str:
    if not priority: priority = config.get("default_priority", "balanced")
    models = await list_models_async()
    candidates = [m for m in models if m not in _MEM_BLACKLIST] or models
    if not candidates: raise RuntimeError("No models available")
    # simple scoring: prefer small models under load
    heavy = is_system_under_load(config.get("max_cpu_for_heavy_model",75),
                                 config.get("max_mem_for_heavy_model",80))
    def score(m):
        s = parse_size(m)
        if heavy and s > 7: return -1e9
        return -s if priority=="speed" else s
    candidates.sort(key=score, reverse=(priority=="accuracy"))
    return candidates[0]
EOF

# ---------- core/task_router.py ----------
cat > core/task_router.py << 'EOF'
from skills.skill_loader import load_skills
from plugins.plugin_loader import load_plugins
SKILLS = load_skills() + load_plugins()
def route_task(task: str):
    tl = task.lower()
    best, best_score = None, 0
    for sk in SKILLS:
        s = sum(1 for kw in sk.keywords if kw in tl)
        if s > best_score: best_score, best = s, sk
    return best or (SKILLS[0] if SKILLS else None)
EOF

# ---------- core/agent.py (simplified, with memory error handling) ----------
cat > core/agent.py << 'EOF'
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
EOF

# ---------- db/store.py ----------
cat > db/store.py << 'EOF'
import sqlite3, json
from datetime import datetime
from pathlib import Path
DB_PATH = Path(__file__).parent / "eustathius.db"
def get_conn():
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row; return conn
def init():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, task_description TEXT, skill_used TEXT,
        model_used TEXT, priority TEXT, result TEXT, status TEXT
    );
    """)
    conn.commit(); conn.close()
init()
def add_task(desc, skill, model, prio, result, status):
    conn = get_conn()
    conn.execute("INSERT INTO tasks VALUES (NULL,?,?,?,?,?,?,?)",
                 (datetime.now().isoformat(), desc, skill, model, prio, result, status))
    conn.commit(); conn.close()
def get_recent_tasks(limit=10):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
EOF

# ---------- fs/backup.py & file_ops.py (basic) ----------
cat > fs/backup.py << 'EOF'
import shutil
from pathlib import Path
from datetime import datetime
def create_backup(p: Path) -> Path:
    if not p.exists(): return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    b = p.with_name(f"{p.name}.backup.{ts}")
    shutil.copy2(p, b)
    return b
def restore_backup(b: Path) -> bool:
    if not b.exists(): return False
    orig = b.with_name(b.name.split(".backup.")[0])
    shutil.copy2(b, orig)
    return True
EOF

cat > fs/file_ops.py << 'EOF'
from pathlib import Path
from .backup import create_backup, restore_backup
from rich.prompt import Confirm
def ask_permission(action, path): return Confirm.ask(f"🔐 Allow {action} on {path}?", default=False)
def read_file(path):
    if not path.exists(): print("File not found."); return None
    if not ask_permission("read", path): return None
    try: return path.read_text(encoding="utf-8")
    except Exception as e: print(f"Read error: {e}"); return None
def write_file(path, content):
    if path.exists():
        if not ask_permission("overwrite", path): return False
        bak = create_backup(path); print(f"Backup: {bak}")
    try: path.write_text(content, encoding="utf-8"); print(f"Written: {path}"); return True
    except Exception as e: print(f"Write error: {e}"); return False
def edit_file(path, new_content):
    if not path.exists(): print("File not found."); return False
    if not ask_permission("edit", path): return False
    bak = create_backup(path)
    try: path.write_text(new_content, encoding="utf-8"); print(f"Edited: {path} (backup {bak})"); return True
    except Exception as e: print(f"Edit error: {e}"); return False
def revert_file(backup_path):
    if not ask_permission("revert", backup_path): return False
    return restore_backup(backup_path)
EOF

# ---------- skills ----------
cat > skills/__init__.py << 'EOF'
class SkillBase:
    name: str = "base"
    description: str = ""
    keywords: list = []
    async def execute(self, task, model, council=False, **kwargs) -> str: raise NotImplementedError
EOF

cat > skills/skill_loader.py << 'EOF'
import importlib, inspect
from pathlib import Path
from . import SkillBase
def load_skills():
    skills = []
    for f in Path(__file__).parent.glob("*.py"):
        if f.stem.startswith("__") or f.stem=="skill_loader": continue
        mod = importlib.import_module(f"skills.{f.stem}")
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, SkillBase) and obj is not SkillBase:
                skills.append(obj())
    return skills
EOF

cat > skills/research.py << 'EOF'
from . import SkillBase
from core.ollama_client import query_model
class ResearchSkill(SkillBase):
    name="research"; description="General knowledge assistant."
    keywords=["explain","what is","how to","tell me","research"]
    async def execute(self, task, model, council=False, **kwargs):
        system = kwargs.get("system_prompt", "You are a helpful assistant.")
        return await query_model(model, task, system=system, temperature=0.7)
EOF

cat > skills/coding.py << 'EOF'
from . import SkillBase
from core.ollama_client import query_model
class CodingSkill(SkillBase):
    name="coding"; description="Code writer/reviewer"
    keywords=["code","refactor","debug","function","class","script","program"]
    async def execute(self, task, model, council=False, **kwargs):
        system = kwargs.get("system_prompt", "Expert programmer. Output clean code.")
        return await query_model(model, task, system=system, temperature=0.3)
EOF

# ---------- plugins (empty but valid) ----------
cat > plugins/__init__.py << 'EOF'
EOF
cat > plugins/plugin_loader.py << 'EOF'
from skills import SkillBase
from pathlib import Path
def load_plugins():
    plugins = []
    for f in Path(__file__).parent.glob("*.py"):
        if f.stem.startswith("__") or f.stem=="plugin_loader": continue
        # skip to avoid import errors; you can add later
    return plugins
EOF

# ---------- main.py (error handler so window stays open) ----------
cat > main.py << 'EOF'
import asyncio, sys, traceback
from rich.console import Console
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from core.agent import EustathiusAgent
from core.sys_monitor import system_stats
from core.logger import logger

console = Console()
COMMANDS = ['help','exit','file','code','priority','stats','models','history','reload','persona']
completer = WordCompleter(COMMANDS, ignore_case=True)
session = PromptSession(history=FileHistory('.eustathius_history'), auto_suggest=AutoSuggestFromHistory(), completer=completer)
agent = None

HELP = """
[bold]Commands:[/bold]
- [cyan]any sentence[/cyan]   Execute task
- [cyan]file <action> <path> [content][/cyan]  read/write/edit/revert
- [cyan]code <python code>[/cyan]   Execute Python sandbox (coming soon)
- [cyan]priority speed|accuracy|balanced[/cyan]
- [cyan]stats[/cyan]               System resources
- [cyan]models[/cyan]              List Ollama models
- [cyan]history[/cyan]             Recent tasks
- [cyan]reload[/cyan]              Reload config.yaml
- [cyan]help[/cyan]                This help
- [cyan]exit[/cyan]                Quit
"""

async def main():
    global agent
    agent = EustathiusAgent()
    await agent.start_background_worker()
    console.print("🤖 [bold green]Eustathius Agent v6.0[/bold green]")
    console.print("Type 'help' for commands.\n")
    while True:
        try:
            cmd = await session.prompt_async("you: ")
            cmd = cmd.strip()
            if not cmd: continue
            if cmd.lower() in ("exit","quit"):
                await agent.shutdown()
                break
            elif cmd.lower() == "help":
                console.print(HELP)
            elif cmd.lower().startswith("file "):
                await agent.handle_file_operation(cmd[5:])
            elif cmd.lower().startswith("code "):
                console.print("Code interpreter not yet implemented in this minimal build.")
            elif cmd.lower().startswith("priority "):
                p = cmd.split()[1].lower()
                if p in ("speed","accuracy","balanced"):
                    agent.priority = p; console.print(f"Priority: [bold]{p}[/bold]")
            elif cmd.lower() == "stats":
                s = system_stats(); console.print(f"CPU: {s['cpu_percent']}% | Memory: {s['memory_percent']}%")
            elif cmd.lower() == "models":
                from core.ollama_client import list_models_async
                models = await list_models_async()
                console.print("Models:", ", ".join(models))
            elif cmd.lower() == "history":
                await agent.show_history()
            elif cmd.lower() == "reload":
                console.print("Reload not implemented in this build.")
            else:
                await agent.run_task(cmd)
        except KeyboardInterrupt:
            await agent.shutdown()
            break
        except Exception as e:
            logger.exception("Main loop error")
            console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited by user.")
    except Exception as e:
        traceback.print_exc()
        print("\nPress Enter to close...")
        input()
EOF

echo "✅ Eustathius Agent built successfully."
echo "Now run: cd eustathius_agent_clean && pip install -r requirements.txt && python main.py"