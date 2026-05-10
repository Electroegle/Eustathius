import re

from config_loader import config
from db.store import get_model_benchmark, get_model_stats

from .ollama_client import ensure_model_available, list_models_async
from .sys_monitor import is_system_under_load, model_fits_in_ram

_MEMORY_FAILED_MODELS = set()
def mark_model_memory_failed(m): _MEMORY_FAILED_MODELS.add(m)

def parse_size(name: str) -> float:
    m = re.search(r'(\d+\.?\d*)\s*b', name.lower())
    return float(m.group(1)) if m else (0.5 if "nano" in name or "tiny" in name else 7.0)

async def select_best_model(priority=None, task_complexity="medium") -> str:
    if not priority: priority = config.get("default_priority", "balanced")
    models = await list_models_async()
    candidates = [m for m in models if m not in _MEMORY_FAILED_MODELS]
    if not candidates: candidates = models
    if not candidates: raise RuntimeError("No models available")

    benchmarks = {}
    for m in candidates:
        tps = get_model_benchmark(m)
        if tps: benchmarks[m] = tps
    if not benchmarks:
        for m in candidates:
            if any(k in m.lower() for k in ["nano","tiny","0.5b","1b","2b"]): tps = 100.0
            elif any(k in m.lower() for k in ["13b","14b","7b"]): tps = 30.0
            else: tps = 20.0
            benchmarks[m] = tps

    available = {m:tps for m,tps in benchmarks.items() if m in candidates}
    if not available: return candidates[0]

    heavy = is_system_under_load(config.get("max_cpu_for_heavy_model",75),
                                 config.get("max_mem_for_heavy_model",80))
    complexity_weights = {"simple":(0.8,0.2),"medium":(0.5,0.5),"complex":(0.2,0.8)}
    w_speed, w_acc = complexity_weights.get(task_complexity, (0.5,0.5))

    stats = get_model_stats()
    reliability = {}
    for m in candidates:
        s = stats.get(m, {"success":0,"total":0})
        reliability[m] = s["success"]/s["total"] if s["total"]>0 else 0.5

    scored = []
    for model, tps in available.items():
        size = parse_size(model)
        if heavy and size > 7: continue
        if not model_fits_in_ram(model): continue   # RAM safety gate
        speed_score = tps / max(available.values())
        acc_score = min(size/70.0, 1.0)
        base = speed_score * w_speed + acc_score * w_acc
        score = base * 0.8 + reliability.get(model,0.5)*0.2
        scored.append((model, score))

    if not scored:
        scored = [(m, tps) for m,tps in available.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]
    scored.sort(key=lambda x: x[1], reverse=True)
    chosen = scored[0][0]
    await ensure_model_available(chosen)
    return chosen
