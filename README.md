# Eustathius v6.0

A local-first autonomous AI agent powered by [Ollama](https://ollama.com).  
Eustathius selects the best available model for every task, manages its own retries, keeps conversation memory, and exposes a clean single-colour terminal UI.

---

## Features

| Category | What it does |
|---|---|
| **Model selection** | Benchmarks every pulled model at startup and picks the fastest safe fit for each task — weighted by RAM headroom, reliability history, and your priority setting |
| **LLM council** | Optionally runs multiple models in parallel, has them debate, and confidence-votes the winner |
| **Autonomous loop** | Self-reviews and rewrites its own output up to N times until it rates itself "OK" |
| **ReAct planning** | Multi-step tool use: search, shell, file read, weather, and custom tools |
| **Task decomposer** | Splits complex tasks into subtasks and rejoins the results |
| **Skills** | Routing to specialised handlers: coding, research, summariser, web search/scrape, sysadmin, filesystem, weather, and any custom skill you drop into `skills/custom/` |
| **File operations** | Read, write, edit, and revert files — every write creates a timestamped backup and requires confirmation |
| **Voice** | Optional TTS output (pyttsx3) and speech-to-text input (SpeechRecognition + sounddevice) |
| **Vector memory** | Chroma-backed semantic memory across sessions |
| **Conversation sessions** | Named sessions saved to disk and restored on demand |
| **Scheduler** | Run any task on a recurring interval |
| **Dashboard** | Live CPU / RAM / disk I/O, model benchmark table, queue, config, and voice status |

---

## Requirements

- Python 3.10 or later
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- At least one pulled model, for example:

```bash
ollama pull qwen2.5:7b
```

---

## Installation

```bash
git clone https://github.com/Electroegle/Eustathius.git
cd Eustathius
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

---

## Quick-start commands

```
help                             Show all commands
dashboard                        System + agent status at a glance
stats                            CPU, RAM, disk I/O, load level
models                           Local models with benchmark scores and reliability
history                          10 most recent tasks
queue                            Pending background tasks
config                           Active runtime settings

file read   <path>               Display a file (confirmation required)
file write  <path> <content>     Write a file (backup created)
file edit   <path> <content>     Replace file content (backup created)
file revert <path>               Choose and restore a backup

code <python>                    Execute Python in the local sandbox
council on / off                 Multi-model confidence voting
autonomous on / off              Self-debug and retry loop
priority speed|accuracy|balanced Model selection weighting
persona default|coder|tutor|creative
                                 Switch agent persona
schedule <min> <task>            Run a task every N minutes
unschedule                       Remove all scheduled tasks
conversation new|save|load [id]  Manage named conversation sessions
reload                           Reload config.yaml without restarting
clear                            Clear the terminal

voice on / off                   Enable or disable all voice features
voice status                     Show TTS + STT configuration
voice test                       Speak a short phrase to verify TTS
voice listen [sec]               Transcribe microphone input
voice ask [sec]                  Transcribe then run as a task
voice devices                    List microphone devices
voice device <index|default>     Select microphone
voice voices                     List TTS voices
voice voice <index|id>           Select TTS voice
voice rate <wpm>                 Speech speed (80 – 320)
voice volume <0-100>             Speech volume
voice language <code>            Recognition language (default: en-US)
voice input on / off             Toggle STT only
voice output on / off            Toggle TTS only
voice say <text>                 Speak text without running a task

tools                            List active tool names
exit / quit                      Shutdown cleanly
```

---

## Custom skills

Drop any Python file into `skills/custom/` and Eustathius picks it up on the next start or `reload`.  
Use `skills/custom/custom_skill_template.py` as your starting point.  
See `skills/custom/SKILLS_GUIDE.md` for the full reference.

---

## Configuration

All settings are in `config.yaml`. Key sections:

| Section | Controls |
|---|---|
| `memory` | Chroma vector store, history depth, consolidation |
| `autonomous` | Retry limit, self-review model override |
| `council_voting` | Confidence scoring, debate rounds |
| `react` | ReAct step limit, verbose logging |
| `voice` | TTS engine, device, rate, volume, language, sample rate |
| `scheduler` | Enable, job file path |
| `personas` | Prompt text for each persona |
| `safety` | LLM-based output filter |
| `backup_dir` | Where timestamped file backups are stored |

---

## Tests

```bash
python -m pytest
```

Tests cover filesystem skill routing and copy behaviour, task router keyword matching, and Chroma vector memory metadata safety — none require a live Ollama server.

---

## Logs

Runtime logs go to `logs/eustathius.log` (path and level set in `config.yaml`).  
Nothing is printed to stdout — Rich owns the terminal.

---

## Project layout

```
Eustathius/
├── main.py                 Entry point and CLI loop
├── config.yaml             All runtime settings
├── config_loader.py        Config loading with validation
├── core/
│   ├── agent.py            Main agent orchestrator
│   ├── model_selector.py   RAM-safe, benchmark-weighted model picker
│   ├── benchmark_runner.py Startup token/s benchmarker
│   ├── sys_monitor.py      CPU, RAM, disk I/O stats
│   ├── council.py          Multi-model confidence voting
│   ├── autonomous.py       Self-review and improvement loop
│   ├── react_planner.py    ReAct multi-step tool planner
│   ├── task_decomposer.py  Subtask splitting
│   ├── task_router.py      Keyword-based skill router
│   ├── theme.py            Single-colour terminal palette
│   └── ...
├── skills/
│   ├── builtin/            Coding, research, summariser, web, sysadmin, weather
│   ├── filesystem.py       Deterministic file/folder operations skill
│   └── custom/             Drop your own skills here
├── fs/
│   ├── file_ops.py         Read / write / edit / revert with backup
│   └── backup.py           Timestamped backup management
├── db/
│   └── store.py            SQLite (WAL mode) for tasks, benchmarks, stats
└── tests/                  pytest suite
```
