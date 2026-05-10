# Eustathius v6.0 - production push
# Run from D:\NF_uop\  as:  .\scripts\git_push.ps1

Set-Location "$PSScriptRoot\.."

Write-Host "`n Staging all changes..." -ForegroundColor Cyan
git add -A

Write-Host "`n Committing..." -ForegroundColor Cyan
git commit -m @"
release: Eustathius v6.0.0 — production-ready

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
- CHANGELOG.md: initial entry for v6.0.0
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n Nothing to commit, or commit failed." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n Pushing to origin/main..." -ForegroundColor Cyan
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n Done. All changes pushed to GitHub." -ForegroundColor Green
} else {
    Write-Host "`n Push failed. Check your credentials or network." -ForegroundColor Red
}
