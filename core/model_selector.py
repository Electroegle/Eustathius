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
