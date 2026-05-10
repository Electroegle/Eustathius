"""
council.py  (confidence-weighted replacement)
----------------------------------------------
Runs a multi-model debate and selects the best final answer using:

  1. Independent answers from each councillor model
  2. Confidence self-rating (0.0–1.0) from each model
  3. Optional debate round: models see each other's answers and revise
  4. Weighted voting: longer × confident answers win ties

Flow:
    Round 0  →  all models answer independently
    Round 1+ →  each model refines after seeing peers (debate_rounds config)
    Final    →  highest confidence-weighted model wins; tie → longest answer
"""

import asyncio

from rich.padding import Padding
from rich.table import Table

from config_loader import config
from core.logger import logger
from core.ollama_client import query_model
from core.theme import BRIGHT, DIM_TEXT, MUTED, PRIMARY, console
from db.store import add_council_session

# ── Prompts ──────────────────────────────────────────────────────────────────

_CONFIDENCE_PROMPT = (
    "Rate your previous answer's confidence from 0.0 (completely unsure) "
    "to 1.0 (completely certain). Output ONLY the decimal number, nothing else."
)

_REFINEMENT_PROMPT = (
    "You are in a council debate. Other models gave these answers:\n"
    "{other_answers}\n\n"
    "Your original answer:\n{own_answer}\n\n"
    "If you see a better answer or can improve yours, do so now. "
    "Otherwise, repeat your original answer unchanged."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_confidence(model: str, answer: str, system: str) -> float:
    """Ask a model to self-rate its confidence. Returns 0.5 on parse failure."""
    prompt = f"Your answer was:\n{answer}\n\n{_CONFIDENCE_PROMPT}"
    try:
        raw = await asyncio.wait_for(
            query_model(model, prompt, system=system, temperature=0.0, max_tokens=10),
            timeout=15,
        )
        return max(0.0, min(1.0, float(raw.strip())))
    except Exception:
        return 0.5


async def _debate_round(model: str, own: str, others: dict[str, str], system: str) -> str:
    """One refinement step — model sees peers' answers."""
    peer_text = "\n\n".join(
        f"[{m}]: {a}" for m, a in others.items() if m != model
    )
    prompt = _REFINEMENT_PROMPT.format(other_answers=peer_text, own_answer=own)
    try:
        return await asyncio.wait_for(
            query_model(model, prompt, system=system, temperature=0.4, max_tokens=1200),
            timeout=60,
        )
    except Exception:
        return own   # keep original on failure


# ── Public API ────────────────────────────────────────────────────────────────

async def council_query(
    models: list[str],
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
) -> dict:
    """
    Run a full council session.

    Returns:
        {
            "models": [...],
            "prompt": ...,
            "answers": {model: answer},
            "confidence": {model: float},
            "final_answer": str,
            "winner": str,
        }
    """
    cfg_council = config.get("council_voting", {})
    debate_rounds = cfg_council.get("debate_rounds", 1)
    use_confidence = cfg_council.get("use_confidence", True)

    # ── Round 0: independent answers ─────────────────────────────────────────
    console.print(f"[dim_text]  council  {len(models)} models answering…[/dim_text]")
    tasks = [
        asyncio.wait_for(
            query_model(m, prompt, system, temperature, max_tokens=1200),
            timeout=90,
        )
        for m in models
    ]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    answers: dict[str, str] = {}
    for m, resp in zip(models, raw):
        if isinstance(resp, Exception):
            logger.warning(f"Council: {m} failed round 0 — {resp}")
            answers[m] = ""
        else:
            answers[m] = resp

    # ── Debate rounds ─────────────────────────────────────────────────────────
    for r in range(debate_rounds):
        console.print(f"[dim_text]  debate round {r+1}/{debate_rounds}…[/dim_text]")
        refined = await asyncio.gather(*[
            _debate_round(m, answers[m], answers, system)
            for m in models
        ])
        answers = {m: a for m, a in zip(models, refined)}

    # ── Confidence scoring ────────────────────────────────────────────────────
    confidence: dict[str, float] = {}
    if use_confidence:
        conf_tasks = [
            _get_confidence(m, answers[m], system)
            for m in models
            if answers[m]
        ]
        conf_values = await asyncio.gather(*conf_tasks)
        valid_models = [m for m in models if answers[m]]
        confidence = {m: c for m, c in zip(valid_models, conf_values)}
    else:
        confidence = {m: 0.5 for m in models if answers[m]}

    # ── Winner selection ──────────────────────────────────────────────────────
    valid = {m: a for m, a in answers.items() if a.strip()}
    if not valid:
        final, winner = "Council: all models failed.", models[0] if models else "none"
    else:
        # Score = confidence × sqrt(len) — rewards confident AND thorough answers
        import math
        scored = {
            m: confidence.get(m, 0.5) * math.sqrt(len(a))
            for m, a in valid.items()
        }
        winner = max(scored, key=scored.__getitem__)
        final  = valid[winner]

    # ── Pretty table ──────────────────────────────────────────────────────────
    table = Table(show_header=True, header_style=f"bold {PRIMARY}",
              border_style=MUTED, show_lines=False)
    table.add_column("Model",      style=BRIGHT,    no_wrap=True)
    table.add_column("Confidence", style=DIM_TEXT,  justify="center")
    table.add_column("Preview",    style=DIM_TEXT)
    for m in models:
        conf_str = f"{confidence.get(m, '—'):.2f}" if m in confidence else "—"
        preview  = (answers.get(m, "") or "")[:60].replace("\n", " ")
        star     = " ●" if m == winner else ""
        table.add_row(m + star, conf_str, preview)
    console.print(Padding(table, (0, 0, 0, 2)))

    session = {
        "models":       models,
        "prompt":       prompt,
        "answers":      answers,
        "confidence":   confidence,
        "final_answer": final,
        "winner":       winner,
    }
    add_council_session(session)
    return session
