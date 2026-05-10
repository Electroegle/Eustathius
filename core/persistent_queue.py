import json
from pathlib import Path
from config_loader import config

QUEUE_FILE = Path(__file__).parent / ".." / "db" / "task_queue.json"

def save_queue(items):
    with open(QUEUE_FILE, "w") as f: json.dump([{"task":t, "priority":p} for t,p in items], f)

def load_queue():
    if not QUEUE_FILE.exists(): return []
    data = json.loads(QUEUE_FILE.read_text())
    return [(d["task"], d["priority"]) for d in data]

def clear_queue(): QUEUE_FILE.unlink(missing_ok=True) if QUEUE_FILE.exists() else None
