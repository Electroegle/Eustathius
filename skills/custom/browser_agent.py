"""
browser_agent.py
----------------
ReAct-style observe → think → act loop for the browser skill.

Each iteration:
  1. Observe  — screenshot + DOM via browser_vision.observe()
  2. Think    — LLM produces a JSON action decision
  3. Confirm  — destructive actions ask the user before executing
  4. Act      — browser_actions.dispatch() carries out the action
  5. Log      — screenshot + action entry written to session log

The loop runs until:
  - LLM returns action "done"  → success
  - LLM returns action "fail"  → task not achievable
  - LLM produces "stuck" 3 times in a row → abort
  - Safety limit of MAX_STEPS steps (soft cap, can be overridden)
"""

import asyncio
import json
import re

import aiohttp
from playwright.async_api import Page
from rich.prompt import Confirm

from core.logger import logger
from core.theme import PRIMARY, console, error, info, ok, rule, warn
from skills.custom.browser_actions import DESTRUCTIVE, dispatch
from skills.custom.browser_session import SessionLog
from skills.custom.browser_vision import observe

OLLAMA_URL  = "http://localhost:11434"
MAX_STEPS   = 50          # hard safety cap ("no limit" means until done/stuck)
STUCK_LIMIT = 3           # abort if same action repeated N times with no change


# ── LLM prompt ────────────────────────────────────────────────────────────────

_SYSTEM = """You are a browser automation agent. At each step you receive:
- The current page URL and title
- A list of interactive elements (CSS selectors, type, label, coordinates)
- A page text excerpt
- Optionally a screenshot (if your model supports vision)
- The task you must complete
- Your action history so far

You must output ONLY a JSON object — no markdown, no explanation:
{
  "thought": "one-sentence reasoning",
  "action":  "navigate|click|hover|type|append|select|upload|scroll|key|wait|extract|back|done|fail",
  "target":  "CSS selector, XPath (//...), or x,y coordinates — null if not needed",
  "value":   "URL for navigate, text for type/key/scroll direction, answer for done/fail — null if not needed"
}

Rules:
- Prefer CSS selectors over coordinates. Use id (#id) or name ([name=x]) when visible.
- For scroll: value = "up" | "down" | integer pixels.
- For key: value = Playwright key name e.g. "Enter", "Tab", "Escape".
- When you have collected the requested data, use action "done" with value = the result.
- If the task is impossible or the page is stuck, use action "fail" with value = reason.
- Never output anything except the JSON object."""


def _build_prompt(task: str, obs, history: list[dict], step: int) -> list[dict]:
    """Build the messages list for the Ollama /api/chat call."""
    history_text = ""
    if history:
        lines = []
        for h in history[-10:]:   # last 10 steps only
            lines.append(f"  step {h['step']}: {h['action']} {h.get('target','')} → {h['result'][:80]}")
        history_text = "\nAction history:\n" + "\n".join(lines)

    user_text = (
        f"Task: {task}\n"
        f"Step: {step}\n\n"
        f"{obs.dom_text}"
        f"{history_text}"
    )

    messages = [{"role": "system", "content": _SYSTEM}]

    if obs.has_vision and obs.screenshot_b64:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text",  "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{obs.screenshot_b64}"}},
            ],
        })
    else:
        messages.append({"role": "user", "content": user_text})

    return messages


async def _call_llm(model: str, messages: list[dict]) -> dict:
    """Call Ollama and parse the JSON action from the response."""
    payload = {
        "model":   model,
        "messages": messages,
        "options": {"temperature": 0.2, "num_predict": 300},
        "stream":  False,
    }
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60)
    ) as session:
        async with session.post(f"{OLLAMA_URL}/api/chat", json=payload) as resp:
            raw = await resp.text()

    # Extract the message content
    try:
        data = json.loads(raw)
        content = data.get("message", {}).get("content", raw)
    except json.JSONDecodeError:
        content = raw

    # Parse JSON from content (handle markdown fences)
    content = re.sub(r"```(?:json)?", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Best-effort: try to find a JSON object in the text
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        logger.warning(f"LLM returned non-JSON: {content[:200]}")
        return {"thought": content[:100], "action": "wait", "target": None, "value": "2"}


def _confirm_destructive(action: str, target: str | None, value: str | None) -> bool:
    """Ask the user before executing a destructive action."""
    desc = action
    if target:
        desc += f" on [{target}]"
    if value and action not in ("type", "append"):
        desc += f" value={value}"
    return Confirm.ask(
        f"[warn]  Agent wants to {desc}. Allow?[/warn]",
        default=True,
    )


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_agent_loop(
    page:  Page,
    task:  str,
    model: str,
    log:   SessionLog,
) -> str:
    """
    Run the observe→think→act loop until done, fail, or stuck.
    Returns the final result string.
    """
    history: list[dict] = []
    stuck_counter  = 0
    last_action_sig = ""

    for step in range(1, MAX_STEPS + 1):
        rule(f"browser step {step}")

        # ── Observe ──────────────────────────────────────────────────────────
        obs = await observe(page, model)
        if obs.screenshot_bytes:
            log.save_screenshot(obs.screenshot_bytes, step)

        info(f"URL: {obs.url}")
        info(f"Page: {obs.title}")
        if obs.has_vision:
            info("Vision: screenshot sent to model")
        else:
            info("Vision: DOM-only (model has no vision capability)")

        # ── Think ─────────────────────────────────────────────────────────────
        messages = _build_prompt(task, obs, history, step)
        try:
            decision = await _call_llm(model, messages)
        except Exception as exc:
            error(f"LLM call failed: {exc}")
            await asyncio.sleep(2)
            continue

        action  = decision.get("action",  "wait").lower()
        target  = decision.get("target")
        value   = decision.get("value")
        thought = decision.get("thought", "")

        console.print(f"[dim_text]  thought [/dim_text][{PRIMARY}]{thought}[/{PRIMARY}]")
        console.print(f"[dim_text]  action  [/dim_text][bright]{action}[/bright]"
                      + (f"  target=[{PRIMARY}]{target}[/{PRIMARY}]" if target else "")
                      + (f"  value=[dim_text]{str(value)[:60]}[/dim_text]" if value else ""))

        # ── Terminal actions ─────────────────────────────────────────────────
        if action == "done":
            final = value or "Task complete."
            ok(f"Done: {final[:120]}")
            log.record_action(step, thought, action, target, value, final, obs.url)
            return final

        if action == "fail":
            reason = value or "Agent could not complete the task."
            warn(f"Agent failed: {reason[:120]}")
            log.record_action(step, thought, action, target, value, reason, obs.url)
            return f"[FAILED] {reason}"

        # ── Stuck detection ──────────────────────────────────────────────────
        sig = f"{action}:{target}:{value}"
        if sig == last_action_sig:
            stuck_counter += 1
            warn(f"Repeated action {stuck_counter}/{STUCK_LIMIT}")
            if stuck_counter >= STUCK_LIMIT:
                msg = "Agent stuck — same action repeated with no progress."
                warn(msg)
                log.record_action(step, thought, "fail", None, None, msg, obs.url)
                return f"[STUCK] {msg}"
        else:
            stuck_counter = 0
            last_action_sig = sig

        # ── Confirm destructive ───────────────────────────────────────────────
        if action in DESTRUCTIVE:
            if not _confirm_destructive(action, target, value):
                info("Action skipped by user.")
                log.record_action(step, thought, action, target, value, "skipped by user", obs.url)
                continue

        # ── Act ───────────────────────────────────────────────────────────────
        result = await dispatch(page, action, target, value)
        info(f"Result: {result[:100]}")
        log.record_action(step, thought, action, target, value, result, obs.url)
        history.append({"step": step, "action": action,
                        "target": target, "value": value, "result": result})

        # Brief pause between steps — looks more natural and lets pages settle
        await asyncio.sleep(0.6)

    return "[LIMIT] Reached maximum step count without completing the task."
