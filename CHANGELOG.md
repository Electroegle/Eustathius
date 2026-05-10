# Changelog

All notable changes to Eustathius are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [6.1.0] — 2025-01-09

### Added — Browser Skill

New skill: `skills/custom/browser.py` — auto-discovered by the skill loader.
Controls a real browser with vision, DOM inspection, and OS-level cursor swap.

**`skills/custom/browser_detector.py`**
Auto-detects installed browsers on Windows (Chrome → Edge → Firefox → bundled
Chromium fallback). Returns a `BrowserInfo` dataclass with Playwright channel
or executable path.

**`skills/custom/browser_vision.py`**
Captures screenshots via Playwright and extracts a structured DOM summary
(interactive elements, forms, visible text) via in-page JavaScript.
Queries Ollama `/api/show` to check whether the active model has vision
capability (CLIP projector / `families` includes "clip" or "vision").
If yes, sends screenshot as base64 alongside the DOM text. If no, sends
DOM text only — no vision requirement for basic browsing tasks.

**`skills/custom/browser_actions.py`**
Full action catalogue: `navigate`, `click`, `hover`, `type`, `append`,
`select`, `upload`, `scroll`, `key`, `wait`, `extract`, `back`, `done`, `fail`.
CSS selectors, XPath, and `x,y` coordinate targets all supported.
Clicks use real mouse movement (Playwright `page.mouse.move` + `click`)
so the motion is visible to the user.

**`skills/custom/browser_agent.py`**
ReAct observe→think→act loop. Each step:
- Observes the page (screenshot + DOM)
- Calls the LLM for a JSON action decision
- Detects stuck state (same action repeated ≥3 times)
- Asks for confirmation before destructive actions (click, type, upload)
- Dispatches the action and records the result
- Continues until `done`, `fail`, stuck, or the 50-step safety cap

**`skills/custom/browser_cursor.py`**
Swaps the Windows system cursor to a crosshair (`IDC_CROSS`) while the
agent is active. Uses `ctypes` only — no third-party dependency. Restores
via `SystemParametersInfo(SPI_SETCURSORS)` on exit. Wrapped in a context
manager; cursor swap failure is non-fatal.

**`skills/custom/browser_session.py`**
Logs every step to `logs/browser_sessions/<timestamp>/`:
- `step_NNN.png` — screenshot before each LLM decision
- `actions.json` — full action log (thought, action, target, value, result,
  URL, timestamp) flushed to disk after every step.

**`tests/test_browser_skill.py`**
Unit tests covering detector fallback, session log file creation, vision
routing heuristics, cursor context manager resilience, and action dispatcher
edge cases. No live browser or Ollama server required.

### Changed
- `requirements.txt`: added `playwright>=1.44` and `pytest-asyncio>=0.23`
- `pyproject.toml`: added `asyncio_mode = "auto"` for pytest-asyncio
- `config.yaml`: added `browser_skill` section with all tunable parameters

### Installation note
After `pip install -r requirements.txt`, run once:
```
playwright install
```
This downloads the browser binaries Playwright needs as fallback.

---

## [6.0.0] — 2025-01-09

### Added
- Startup benchmark runner, typed sys monitor, RAM safety gate in model selector
- Confidence-weighted LLM council with debate rounds
- Central backup directory, interactive file revert
- Custom skills folder with template and guide
- Single-colour theme module (steel blue palette)
- Dashboard, stats, models, history, queue, config, and voice commands
- Voice subsystem (TTS + STT), ReAct planner, filesystem skill, Chroma memory

### Changed
- Logger: file-only, no stdout pollution
- Config loader: YAML validation with clear error messages
- DB store: WAL mode, context-manager connections
- Requirements: pinned versions, duplicates removed

### Fixed
- Backups written next to original file instead of backup_dir
- Skill loader crashed on syntax error in any skill file
- Council fell back to longest-answer with no transparency
