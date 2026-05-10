@echo off
:: Eustathius v6.0 — production push script
:: Run from D:\NF_uop with: scripts\git_push.bat

cd /d "%~dp0.."

echo.
echo  Staging all changes...
git add -A

echo.
echo  Committing...
git commit -m "release: Eustathius v6.0.0 — production-ready

Core changes
- benchmark_runner: startup token/s benchmarker with 24h cache
- sys_monitor: typed SystemStats dataclass (CPU/RAM/disk/load)
- model_selector: RAM safety gate via model_fits_in_ram()
- council: confidence-weighted voting (confidence x sqrt(len))
- logger: file-only handler, removed stdout pollution
- config_loader: YAML validation with clear error messages
- db/store: WAL mode, context-manager connections, no leaks

File system
- backup: central backup_dir from config, restore_backup_to()
- file_ops: interactive revert with backup list and user choice

Skills
- skills/custom/ folder with template, guide, and __init__.py
- skill_loader: scans skills/custom/, per-file error isolation

UI
- theme: single steel-blue palette, shared Console instance
- main: dashboard, stats, models, history, queue, config, voice
- All console output through theme helpers (ok/info/warn/error/rule)

Packaging
- requirements.txt: pinned major versions, duplicates removed
- pyproject.toml: project metadata and ruff config added
- .gitignore: backup dir, scheduled jobs, prompt cache
- README.md: full feature reference and command table
- CHANGELOG.md: initial entry for v6.0.0"

echo.
echo  Pushing to origin/main...
git push origin main

echo.
echo  Done.
pause
