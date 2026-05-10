# Eustathius Agent v6.0

Eustathius is a local-first AI agent powered by Ollama. It can route tasks to local skills, use tools, manage conversation memory, work with files, run a Python sandbox, speak responses, and handle multi-step work from a terminal UI.

## Features

- Local Ollama model execution with automatic model selection.
- ReAct-style tool use for tasks that need external tools.
- Local filesystem skill for creating folders, finding files, and safely copying frame/image assets.
- Chroma-backed vector memory with safe metadata handling.
- Conversation sessions, task history, scheduling, and background queue support.
- Optional voice input/output with microphone selection, speech rate, volume, and language controls.
- Rich terminal dashboard for models, stats, queue, config, tools, and voice status.
- Safety checks and confirmation prompts before filesystem writes.

## Requirements

- Python 3.10+
- Ollama installed and running
- At least one local Ollama model, for example:

```bash
ollama pull qwen2.5:7b
```

## Installation

```bash
git clone https://github.com/Electroegle/Eustathius.git
cd Eustathius
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## Common Commands

```text
help                         Show commands
dashboard                    Show system and agent status
models                       Show local Ollama models
stats                        Show CPU, RAM, disk I/O, and load
queue                        Show pending background tasks
config                       Show important runtime settings
tools                        List available tools
voice status                 Show voice setup
voice devices                List microphones
voice test                   Test text-to-speech
voice ask 5                  Record 5 seconds and run the transcription as a task
file read <path>             Read a file after confirmation
file write <path> <content>  Write a file with backup protection
file revert <path>           Restore from backups
```

## Filesystem Tasks

Eustathius includes a deterministic filesystem skill for messy local instructions. For example:

```text
make a directory under downloades folder called new framea and copy key farames stored somewhere in folder ranit/frames
```

The agent normalizes common typos, infers the Downloads folder, finds image/frame files recursively, previews the copy operation, asks for confirmation, and avoids overwriting duplicate filenames.

## Configuration

Runtime settings live in `config.yaml`. Important sections include:

- `memory`: JSON and Chroma memory settings
- `voice`: input/output, language, rate, volume, sample rate, and device settings
- `react`: ReAct planning settings
- `tools`: tool enablement
- `scheduler`: recurring task settings

Runtime data such as logs, conversations, Chroma databases, SQLite databases, and prompt history is intentionally ignored by Git.

## Tests

```bash
python -m pytest
```

The included tests cover filesystem routing/copy behavior and Chroma-safe vector metadata without requiring a live Ollama server.

## Notes

- Start Ollama before launching the agent: `ollama serve`.
- Voice recognition through `speech_recognition` may use an online recognition service depending on backend.
- Filesystem writes always prompt for confirmation.
