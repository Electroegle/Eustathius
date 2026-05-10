# Changelog

All notable changes to Eustathius are recorded here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [6.0.0] — 2025-01-09

### Added
- **Startup benchmark runner** (`core/benchmark_runner.py`): measures tokens/sec for every pulled Ollama model on launch, skips models benchmarked in the last 24 hours, and displays a colour-coded speed-tier table.
- **Rich system monitor** (`core/sys_monitor.py`): typed `SystemStats` dataclass covering CPU %, RAM used/available/total GB, disk read/write MB/s, safe model RAM headroom, and a load-level string (`low|medium|high|critical`).
- **RAM safety gate** in `model_selector.py`: models estimated to exceed available RAM are excluded from selection before scoring, preventing OOM crashes on CPU-only machines.
- **Confidence-weighted LLM council** (`core/council.py`): each councillor model self-rates its answer 0–1, scores are weighted by `confidence × √(answer length)`, winner is shown in a table with a bullet marker.
- **Configurable backup directory** (`fs/backup.py`): all backups go to the path in `config.yaml → backup_dir` (`~/.eustathius_backups` by default) instead of sitting next to the original file. Added `restore_backup_to(backup, target)` and `list_backups(original)`.
- **Interactive file revert** (`fs/file_ops.py`): lists the five most recent backups for a file and prompts the user to choose before restoring.
- **Custom skills folder** (`skills/custom/`): drop any `SkillBase` subclass here; the skill loader discovers it automatically. Includes `custom_skill_template.py` and `SKILLS_GUIDE.md`.
- **Theme module** (`core/theme.py`): single source of truth for the steel-blue palette; shared `Console` instance used everywhere instead of per-module instances.
- **Dashboard command**: side-by-side system and agent state panels.
- **Voice subsystem** (`core/voice_manager.py`): TTS (pyttsx3) and STT (SpeechRecognition + sounddevice) with device selection, rate, volume, language, and input/output toggles.
- **ReAct planner** (`core/react_planner.py`): multi-step tool use for tasks that need external information.
- **Deterministic filesystem skill** (`skills/filesystem.py`): handles messy natural-language folder/copy instructions, normalises typos, previews the operation, and asks for confirmation.
- **Chroma vector memory** (`core/vector_memory.py`): semantic recall across sessions with safe metadata handling.
- **Persistent task queue** with background worker and graceful shutdown save/restore.

### Changed
- `logger.py`: stdout handler removed — Rich owns the terminal; all diagnostics go to `logs/eustathius.log`.
- `config_loader.py`: added validation and clear error messages for missing or malformed `config.yaml`.
- `db/store.py`: SQLite WAL mode enabled; context-manager connections that commit on success and roll back on error; no connection leaks.
- `requirements.txt`: removed duplicate duckduckgo packages, pinned major versions for all dependencies.
- `skill_loader.py`: now scans both `skills/` and `skills/custom/`, with per-file error isolation.
- `model_selector.py`: integrated `model_fits_in_ram()` gate; reliability score contributes 20% of the final rank.
- All console output standardised to theme helpers (`ok`, `info`, `warn`, `error`, `rule`); no raw colour strings in application code.

### Fixed
- Backup files were previously written next to the original file, ignoring `backup_dir` in config.
- `skill_loader.py` crashed the entire agent if any one skill file had a syntax error.
- `model_stats` query returned raw Row objects in some code paths instead of dicts.
- Council mode fell back to "longest answer wins" with no transparency; replaced with scored table.

---

## [5.x] and earlier

Pre-release iterations. No formal changelog kept.
