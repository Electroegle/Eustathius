"""
benchmark_runner.py
-------------------
Measures tokens/sec for pulled Ollama models and stores results in SQLite.
Startup runs skip models benchmarked in the last 24 hours.
"""

import asyncio
import time
from datetime import datetime

from rich.padding import Padding
from rich.table import Table

from core.logger import logger
from core.ollama_client import list_models_async, query_model
from core.theme import BRIGHT, MUTED, PRIMARY, console, info, rule, warn
from db.store import get_conn, get_model_benchmark, save_model_benchmark

_BENCH_PROMPT = (
    "List the first 10 prime numbers, one per line. "
    "No explanation, just the numbers."
)
_BENCH_SYSTEM = "You are a concise assistant. Follow instructions exactly."
_BENCH_TOKENS = 80
_BENCH_TIMEOUT = 45
_STALE_HOURS = 24


def _last_benchmark_age_hours(model: str) -> float | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT updated_at FROM model_benchmarks WHERE model_name=?", (model,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        timestamp = datetime.fromisoformat(row[0])
        return (datetime.now() - timestamp).total_seconds() / 3600
    except Exception:
        return None


async def _benchmark_one(model: str) -> float | None:
    start = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            query_model(
                model,
                _BENCH_PROMPT,
                system=_BENCH_SYSTEM,
                temperature=0.0,
                max_tokens=_BENCH_TOKENS,
            ),
            timeout=_BENCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Benchmark timeout: {model}")
        return None
    except Exception as exc:
        logger.warning(f"Benchmark error ({model}): {exc}")
        return None

    elapsed = time.perf_counter() - start
    if elapsed < 0.1 or not response:
        return None

    token_estimate = len(response.split()) * 1.3
    return round(token_estimate / elapsed, 2)


async def run_startup_benchmarks(force: bool = False) -> dict[str, float]:
    models = await list_models_async()
    if not models:
        warn("No Ollama models found; skipping benchmark.")
        return {}

    to_benchmark = []
    for model in models:
        age = _last_benchmark_age_hours(model)
        if force or age is None or age > _STALE_HOURS:
            to_benchmark.append(model)

    if not to_benchmark:
        info("All models benchmarked recently; skipping.")
        return {model: get_model_benchmark(model) or 0.0 for model in models}

    rule("model benchmark")
    console.print(f"[body]Benchmarking [bright]{len(to_benchmark)}[/bright] model(s). Please wait...[/body]\n")

    results: dict[str, float] = {}
    for model in to_benchmark:
        console.print(f"  [dim_text]testing[/dim_text] [{PRIMARY}]{model}[/{PRIMARY}]", end=" ")
        tps = await _benchmark_one(model)
        if tps is None:
            console.print("[bad]failed[/bad]")
            continue
        save_model_benchmark(model, tps)
        results[model] = tps
        console.print(f"[ok]{tps:.1f} tok/s[/ok]")

    if results:
        table = Table(title="Benchmark Results", header_style=f"bold {PRIMARY}", border_style=MUTED, show_lines=False)
        table.add_column("Model", style=BRIGHT, no_wrap=True)
        table.add_column("Tok/s", style="ok", justify="right")
        table.add_column("Tier", style="warn")

        def tier(tps: float) -> str:
            if tps >= 60:
                return "Fast"
            if tps >= 25:
                return "Medium"
            return "Slow"

        for model, tps in sorted(results.items(), key=lambda item: item[1], reverse=True):
            table.add_row(model, f"{tps:.1f}", tier(tps))
        console.print(Padding(table, (1, 0, 0, 2)))

    rule()
    return results


async def get_cached_benchmarks() -> dict[str, float]:
    models = await list_models_async()
    out = {}
    for model in models:
        tps = get_model_benchmark(model)
        out[model] = tps if tps is not None else 0.0
    return out
