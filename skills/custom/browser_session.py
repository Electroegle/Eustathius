"""
browser_session.py
------------------
Logs every browser agent step to a timestamped session folder:
  logs/browser_sessions/<session_id>/
    actions.json        -- full action log with timestamps and results
    step_001.png        -- screenshot before each LLM decision
    step_002.png
    ...

Usage:
    log = SessionLog()
    log.save_screenshot(png_bytes, step=1)
    log.record_action(step=1, action="click", target="#btn", result="ok")
    log.close()
"""

import json
from datetime import datetime
from pathlib import Path

from core.logger import logger

_SESSION_ROOT = Path("logs/browser_sessions")


class SessionLog:
    def __init__(self, task: str):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = _SESSION_ROOT / ts
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._actions: list[dict] = []
        self._task = task
        self._start = datetime.now().isoformat()
        logger.info(f"Browser session started: {self.session_dir}")

    # ── Screenshots ──────────────────────────────────────────────────────────

    def save_screenshot(self, png_bytes: bytes, step: int) -> Path:
        """Write a PNG screenshot for the given step number. Returns the path."""
        path = self.session_dir / f"step_{step:03d}.png"
        path.write_bytes(png_bytes)
        return path

    # ── Action log ───────────────────────────────────────────────────────────

    def record_action(
        self,
        step: int,
        thought: str,
        action: str,
        target: str | None,
        value: str | None,
        result: str,
        url: str = "",
    ) -> None:
        entry = {
            "step":      step,
            "timestamp": datetime.now().isoformat(),
            "url":       url,
            "thought":   thought,
            "action":    action,
            "target":    target,
            "value":     value,
            "result":    result,
        }
        self._actions.append(entry)
        self._flush()

    def _flush(self) -> None:
        """Write actions.json to disk after every step (safe against crashes)."""
        data = {
            "task":       self._task,
            "started_at": self._start,
            "session":    str(self.session_dir),
            "steps":      len(self._actions),
            "actions":    self._actions,
        }
        path = self.session_dir / "actions.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def close(self, final_result: str = "") -> None:
        """Finalise the session log with outcome and duration."""
        duration = (
            datetime.now() - datetime.fromisoformat(self._start)
        ).total_seconds()
        self._actions.append(
            {
                "step":      "final",
                "timestamp": datetime.now().isoformat(),
                "action":    "session_end",
                "result":    final_result,
                "duration_seconds": round(duration, 1),
            }
        )
        self._flush()
        logger.info(
            f"Browser session closed: {len(self._actions)-1} steps, "
            f"{duration:.0f}s — {self.session_dir}"
        )

    @property
    def path(self) -> Path:
        return self.session_dir
