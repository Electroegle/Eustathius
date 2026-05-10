import asyncio
import shutil
import sys
import traceback

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from rich.columns import Columns
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table

from config_loader import config
from core.agent import EustathiusAgent
from core.benchmark_runner import run_startup_benchmarks
from core.sys_monitor import system_stats
from core.theme import BODY, BRIGHT, DIM_TEXT, MUTED, PRIMARY, console, error, info, ok, rule, thinking, warn

FULL_ASCII = r"""
  _____           _        _   _     _
 | ____|_   _ ___| |_ __ _| |_| |__ (_)_   _ ___
 |  _| | | | / __| __/ _` | __| '_ \| | | | / __|
 | |___| |_| \__ \ || (_| | |_| | | | | |_| \__ \
 |_____|\__,_|___/\__\__,_|\__|_| |_|_|\__,_|___/
""".strip("\n")

NARROW_ASCII = "EUSTATHIUS"
VERSION = "v6.0"
TAGLINE = "Local autonomous AI agent"

COMMANDS = [
    "help", "exit", "quit", "clear",
    "dashboard", "status", "stats", "models", "history", "queue", "config",
    "file read", "file write", "file edit", "file revert",
    "code",
    "council on", "council off",
    "autonomous on", "autonomous off",
    "priority speed", "priority accuracy", "priority balanced",
    "persona default", "persona coder", "persona tutor", "persona creative",
    "reload", "schedule", "unschedule",
    "conversation new", "conversation save", "conversation load",
    "voice on", "voice off", "voice status", "voice test", "voice listen", "voice ask",
    "voice devices", "voice device", "voice rate", "voice volume", "voice say",
    "voice voices", "voice voice", "voice language", "voice input on", "voice input off",
    "voice output on", "voice output off",
    "tools",
]

PT_STYLE = PTStyle.from_dict({
    "": "#a4cfff",
    "prompt": "#4a90e2",
})
PROMPT_STR = [("class:prompt", "eustathius > "), ("", "")]

session: PromptSession | None = None


def get_session() -> PromptSession:
    global session
    if session is None:
        session = PromptSession(
            history=FileHistory(".eustathius_history"),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(COMMANDS, ignore_case=True, sentence=True),
            style=PT_STYLE,
        )
    return session


def print_banner() -> None:
    width = shutil.get_terminal_size().columns
    art = FULL_ASCII if width >= 58 else NARROW_ASCII
    console.print()
    for line in art.splitlines():
        console.print(f"[primary]{line}[/primary]")
    console.print(f"\n[dim_text]  {VERSION}  |  {TAGLINE}[/dim_text]\n")
    console.print(Panel.fit(
        "[body]Type [bright]help[/bright] for commands, [bright]dashboard[/bright] for system state, or enter any task.[/body]",
        border_style=MUTED,
        padding=(0, 2),
    ))
    console.print()


def _state_badge(enabled: bool) -> str:
    return "[ok]ON[/ok]" if enabled else "[dim_text]OFF[/dim_text]"


def _bar(pct: float, width: int = 16) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    bar_str = "#" * filled + "-" * (width - filled)
    colour = "ok" if pct < 70 else ("warn" if pct < 88 else "bad")
    return f"[{colour}]{bar_str}[/{colour}]"


def print_help() -> None:
    rows = [
        ("<task>", "Run a task with automatic model and skill selection."),
        ("dashboard / status", "Show system, agent, queue, and configuration state."),
        ("stats", "Show CPU, memory, disk I/O, and load details."),
        ("models", "List local Ollama models with benchmark and reliability data."),
        ("history", "Show the latest completed tasks."),
        ("queue", "Show pending background tasks."),
        ("config", "Show the active runtime settings that matter most."),
        ("file read <path>", "Display a file after confirmation."),
        ("file write <path> <content>", "Write a file with backup protection."),
        ("file edit <path> <content>", "Replace file content with backup protection."),
        ("file revert <path>", "Restore a file from one of its backups."),
        ("code <python>", "Execute Python in the local sandbox."),
        ("council on / off", "Toggle multi-model confidence voting."),
        ("autonomous on / off", "Toggle self-debug and retry behavior."),
        ("priority speed|accuracy|balanced", "Set model selection priority."),
        ("persona <name>", "Switch persona: default, coder, tutor, creative."),
        ("schedule <min> <task>", "Run a task every N minutes when scheduler is enabled."),
        ("unschedule", "Remove all scheduled tasks."),
        ("conversation new|save|load [id]", "Manage conversation sessions."),
        ("voice on / off", "Toggle voice features."),
        ("voice status", "Show speech package, device, and voice settings."),
        ("voice test", "Speak a short test phrase."),
        ("voice listen [sec]", "Record and transcribe a short voice note."),
        ("voice ask [sec]", "Record a task and run it through the agent."),
        ("voice devices", "List available microphone devices."),
        ("voice device <index|default>", "Select the microphone for this session."),
        ("voice rate <80-320>", "Set speech speed in words per minute."),
        ("voice volume <0-100>", "Set speech volume for this session."),
        ("voice voices", "List available text-to-speech voices."),
        ("voice voice <index|id>", "Select a text-to-speech voice for this session."),
        ("voice language <code>", "Set speech recognition language, for example en-US."),
        ("voice input on / off", "Toggle microphone transcription."),
        ("voice output on / off", "Toggle spoken responses."),
        ("voice say <text>", "Speak text without running a task."),
        ("tools", "List available tool names."),
        ("reload", "Reload config.yaml."),
        ("clear", "Clear the terminal."),
        ("exit / quit", "Shut down cleanly."),
    ]
    table = Table(
        show_header=True,
        header_style=f"bold {PRIMARY}",
        border_style=MUTED,
        show_lines=False,
        title=f"[dim_text]Eustathius {VERSION} Commands[/dim_text]",
    )
    table.add_column("Command", style=BRIGHT, no_wrap=True, min_width=28)
    table.add_column("Use", style=BODY)
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    console.print(Padding(table, (1, 0)))


def print_stats() -> None:
    s = system_stats()
    load_colour = {"low": "ok", "medium": BRIGHT, "high": "warn", "critical": "bad"}[s.load_level]

    table = Table(show_header=False, border_style=MUTED, show_lines=False, expand=False)
    table.add_column("Metric", style=f"bold {PRIMARY}", no_wrap=True, min_width=13)
    table.add_column("Value", style=BODY)
    table.add_row("CPU", f"{_bar(s.cpu_percent)}  [bright]{s.cpu_percent}%[/bright]")
    table.add_row(
        "Memory",
        f"{_bar(s.ram_percent)}  [bright]{s.ram_percent}%[/bright]  "
        f"[dim_text]{s.ram_used_gb:.1f}/{s.ram_total_gb:.1f} GB[/dim_text]",
    )
    table.add_row("Free RAM", f"[bright]{s.ram_available_gb:.1f} GB[/bright]  [dim_text]safe model headroom {s.safe_model_ram_gb:.1f} GB[/dim_text]")
    table.add_row("Disk I/O", f"[dim_text]read {s.disk_read_mbps:.1f} MB/s | write {s.disk_write_mbps:.1f} MB/s[/dim_text]")
    table.add_row("Load", f"[{load_colour}]{s.load_level.upper()}[/{load_colour}]")
    console.print(Padding(table, (0, 0, 0, 2)))


async def print_models() -> None:
    from core.ollama_client import list_models_async
    from core.sys_monitor import model_fits_in_ram
    from db.store import get_model_benchmark, get_model_stats

    models = await list_models_async()
    if not models:
        warn("No models found. Is Ollama running?")
        return

    stats_map = get_model_stats()
    table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED, show_lines=False)
    table.add_column("Model", style=BRIGHT, no_wrap=True)
    table.add_column("Tok/s", style=DIM_TEXT, justify="right")
    table.add_column("Speed", style=DIM_TEXT, justify="center")
    table.add_column("Reliability", style=DIM_TEXT, justify="center")
    table.add_column("RAM", style=DIM_TEXT, justify="center")

    def speed_tier(tps):
        if tps is None:
            return "[dim_text]n/a[/dim_text]"
        if tps >= 60:
            return "[ok]Fast[/ok]"
        if tps >= 25:
            return f"[{PRIMARY}]Medium[/{PRIMARY}]"
        return "[warn]Slow[/warn]"

    def reliability(model):
        stats = stats_map.get(model, {})
        total = stats.get("total", 0)
        if total == 0:
            return "[dim_text]n/a[/dim_text]"
        pct = round(stats.get("success", 0) / total * 100)
        colour = "ok" if pct >= 80 else ("warn" if pct >= 50 else "bad")
        return f"[{colour}]{pct}%[/{colour}]"

    for model in sorted(models):
        tps = get_model_benchmark(model)
        fits = model_fits_in_ram(model)
        table.add_row(
            model,
            f"{tps:.0f}" if tps else "n/a",
            speed_tier(tps),
            reliability(model),
            "[ok]fits[/ok]" if fits else "[bad]large[/bad]",
        )
    console.print(Padding(table, (0, 0, 0, 2)))


def print_history(limit: int = 10) -> None:
    from db.store import get_recent_tasks

    tasks = get_recent_tasks(limit)
    if not tasks:
        info("No tasks recorded yet.")
        return

    table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED, show_lines=False)
    table.add_column("Time", style=DIM_TEXT, no_wrap=True, width=19)
    table.add_column("Task", style=BODY, no_wrap=False, max_width=58)
    table.add_column("Model", style=PRIMARY, no_wrap=True)
    table.add_column("Status", justify="center")

    for task in tasks:
        status = "[ok]done[/ok]" if task["status"] == "completed" else "[bad]failed[/bad]"
        table.add_row(
            task["timestamp"][:19],
            (task["task_description"] or "")[:58],
            task.get("model_used") or "n/a",
            status,
        )
    console.print(Padding(table, (0, 0, 0, 2)))


def print_config_summary(agent: EustathiusAgent) -> None:
    rows = [
        ("Priority", agent.priority),
        ("Persona", agent.persona),
        ("Council", "enabled" if agent.council_enabled else "disabled"),
        ("Autonomous", "enabled" if agent.autonomous_enabled else "disabled"),
        ("ReAct", "enabled" if agent.react_enabled else "disabled"),
        ("Memory", "enabled" if agent.memory else "disabled"),
        ("Vector memory", "enabled" if agent.vector_memory else "disabled"),
        ("Scheduler", "enabled" if agent.scheduler else "disabled"),
        ("Voice", "enabled" if agent.voice.enabled else "disabled"),
        ("Tools", "enabled" if agent.tools else "disabled"),
        ("Skill timeout", f"{config.get('skill_timeout', 'n/a')} seconds"),
    ]
    table = Table(show_header=False, border_style=MUTED, show_lines=False)
    table.add_column("Setting", style=f"bold {PRIMARY}", no_wrap=True)
    table.add_column("Value", style=BODY)
    for key, value in rows:
        table.add_row(key, str(value))
    console.print(Padding(table, (0, 0, 0, 2)))


def print_queue(agent: EustathiusAgent) -> None:
    pending = list(agent.task_queue._queue)
    if not pending:
        info("No queued background tasks.")
        return
    table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED)
    table.add_column("#", justify="right", style=DIM_TEXT)
    table.add_column("Priority", style=PRIMARY)
    table.add_column("Task", style=BODY)
    for idx, (task, priority) in enumerate(pending, 1):
        table.add_row(str(idx), priority or agent.priority, str(task)[:90])
    console.print(Padding(table, (0, 0, 0, 2)))


def print_voice_status(agent: EustathiusAgent) -> None:
    status = agent.voice.status()
    rows = [
        ("Voice", "enabled" if status["enabled"] else "disabled"),
        ("Input", "enabled" if status["input_enabled"] else "disabled"),
        ("Output", "enabled" if status["output_enabled"] else "disabled"),
        ("TTS engine", "ready" if status["tts_engine"] else "not ready"),
        ("pyttsx3", "installed" if status["pyttsx3"] else "missing"),
        ("speech_recognition", "installed" if status["speech_recognition"] else "missing"),
        ("sounddevice", "installed" if status["sounddevice"] else "missing"),
        ("Input device", "default" if status["input_device_index"] is None else str(status["input_device_index"])),
        ("Language", status["language"]),
        ("Listen time", f"{status['listen_seconds']:g} seconds"),
        ("Sample rate", f"{status['sample_rate']} Hz"),
        ("Speech rate", f"{status['rate']} wpm"),
        ("Volume", f"{round(status['volume'] * 100)}%"),
    ]
    table = Table(show_header=False, border_style=MUTED, show_lines=False)
    table.add_column("Setting", style=f"bold {PRIMARY}", no_wrap=True)
    table.add_column("Value", style=BODY)
    for key, value in rows:
        table.add_row(key, str(value))
    console.print(Padding(table, (0, 0, 0, 2)))


def print_voice_devices(agent: EustathiusAgent) -> None:
    devices = agent.voice.list_input_devices()
    if not devices:
        warn("No microphone devices found, or sounddevice is unavailable.")
        return
    table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED)
    table.add_column("Index", justify="right", style=DIM_TEXT)
    table.add_column("Device", style=BODY)
    table.add_column("Channels", justify="right", style=DIM_TEXT)
    table.add_column("Rate", justify="right", style=DIM_TEXT)
    table.add_column("Default", justify="center")
    for device in devices:
        table.add_row(
            str(device.index),
            device.name,
            str(device.channels),
            str(device.samplerate),
            "[ok]yes[/ok]" if device.is_default else "",
        )
    console.print(Padding(table, (0, 0, 0, 2)))


def print_output_voices(agent: EustathiusAgent) -> None:
    voices = agent.voice.list_output_voices()
    if not voices:
        warn("No output voices found, or pyttsx3 is unavailable.")
        return
    table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED)
    table.add_column("Index", justify="right", style=DIM_TEXT)
    table.add_column("Name", style=BODY)
    table.add_column("Id", style=DIM_TEXT)
    for voice in voices:
        table.add_row(voice["index"], voice["name"], voice["id"])
    console.print(Padding(table, (0, 0, 0, 2)))


async def handle_voice_command(agent: EustathiusAgent, cmd: str) -> None:
    parts = cmd.split(maxsplit=2)
    action = parts[1].lower() if len(parts) > 1 else "status"
    value = parts[2].strip() if len(parts) > 2 else ""

    if action == "on":
        if agent.voice.enable():
            ok("Voice enabled")
    elif action == "off":
        agent.voice.disable()
        info("Voice disabled")
    elif action == "input":
        if value.lower() == "on":
            agent.voice.set_input_enabled(True)
            ok("Voice input enabled")
        elif value.lower() == "off":
            agent.voice.set_input_enabled(False)
            info("Voice input disabled")
        else:
            error("Usage: voice input on|off")
    elif action == "output":
        if value.lower() == "on":
            if agent.voice.set_output_enabled(True):
                ok("Voice output enabled")
        elif value.lower() == "off":
            agent.voice.set_output_enabled(False)
            info("Voice output disabled")
        else:
            error("Usage: voice output on|off")
    elif action == "status":
        print_voice_status(agent)
    elif action == "devices":
        print_voice_devices(agent)
    elif action == "voices":
        print_output_voices(agent)
    elif action == "voice":
        if not value:
            error("Usage: voice voice <index|id>")
            return
        if agent.voice.set_voice(value):
            ok("Output voice updated")
        else:
            error("Could not select that output voice.")
    elif action == "device":
        if not value:
            error("Usage: voice device <index|default>")
            return
        if value.lower() == "default":
            agent.voice.set_input_device(None)
            ok("Voice input device set to default")
            return
        try:
            agent.voice.set_input_device(int(value))
            ok(f"Voice input device set to {value}")
        except ValueError:
            error("Device index must be a number or 'default'.")
    elif action == "rate":
        try:
            agent.voice.set_rate(int(value))
            ok(f"Speech rate set to {agent.voice.rate} wpm")
        except ValueError:
            error("Usage: voice rate <80-320>")
    elif action == "volume":
        try:
            raw = float(value)
            agent.voice.set_volume(raw / 100 if raw > 1 else raw)
            ok(f"Speech volume set to {round(agent.voice.volume * 100)}%")
        except ValueError:
            error("Usage: voice volume <0-100>")
    elif action == "language":
        if not value:
            error("Usage: voice language <code>")
            return
        agent.voice.set_language(value)
        ok(f"Speech recognition language set to {agent.voice.language}")
    elif action == "test":
        agent.voice.enable()
        spoken = await agent.voice.speak("Eustathius voice output is ready.")
        if spoken:
            ok("Voice test complete")
    elif action == "say":
        if not value:
            error("Usage: voice say <text>")
            return
        agent.voice.enable()
        await agent.voice.speak(value)
    elif action in ("listen", "dictate"):
        seconds = _parse_voice_seconds(value)
        if value and seconds is None:
            return
        agent.voice.enable()
        text = await agent.voice.listen(duration=seconds)
        if text:
            console.print(f"[body]{text}[/body]")
    elif action == "ask":
        seconds = _parse_voice_seconds(value)
        if value and seconds is None:
            return
        agent.voice.enable()
        text = await agent.voice.listen(duration=seconds)
        if text:
            thinking()
            await agent.run_task(text)
    else:
        error("Usage: voice on|off|status|test|listen|ask|devices|device|voices|voice|rate|volume|language|say")


def _parse_voice_seconds(value: str) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        error("Seconds must be a number.")
        return None
    return max(1.0, min(seconds, 30.0))


def print_dashboard(agent: EustathiusAgent) -> None:
    s = system_stats()
    system_table = Table.grid(padding=(0, 2))
    system_table.add_column(style=f"bold {PRIMARY}")
    system_table.add_column(style=BODY)
    system_table.add_row("CPU", f"{s.cpu_percent}%")
    system_table.add_row("Memory", f"{s.ram_percent}% ({s.ram_available_gb:.1f} GB free)")
    system_table.add_row("Load", s.load_level.upper())
    system_table.add_row("Queue", str(agent.task_queue.qsize()))

    agent_table = Table.grid(padding=(0, 2))
    agent_table.add_column(style=f"bold {PRIMARY}")
    agent_table.add_column(style=BODY)
    agent_table.add_row("Priority", agent.priority)
    agent_table.add_row("Persona", agent.persona)
    agent_table.add_row("Council", _state_badge(agent.council_enabled))
    agent_table.add_row("Autonomous", _state_badge(agent.autonomous_enabled))
    agent_table.add_row("Voice", _state_badge(agent.voice.enabled))

    panels = [
        Panel(system_table, title="[bright]System[/bright]", border_style=MUTED, padding=(1, 2)),
        Panel(agent_table, title="[bright]Agent[/bright]", border_style=MUTED, padding=(1, 2)),
    ]
    console.print(Padding(Columns(panels, equal=True, expand=True), (0, 0, 1, 0)))
    print_stats()


async def main():
    agent = EustathiusAgent()
    await agent.start_background_worker()

    print_banner()
    await run_startup_benchmarks()
    console.print()

    while True:
        try:
            user_input = await get_session().prompt_async(PROMPT_STR)
        except (KeyboardInterrupt, EOFError):
            break

        cmd = user_input.strip()
        if not cmd:
            continue

        low = cmd.lower()

        if low in ("exit", "quit"):
            break
        if low == "clear":
            console.clear()
            print_banner()
        elif low == "help":
            print_help()
        elif low in ("dashboard", "status"):
            print_dashboard(agent)
        elif low == "stats":
            print_stats()
        elif low == "models":
            await print_models()
        elif low == "history":
            print_history()
        elif low == "queue":
            print_queue(agent)
        elif low == "config":
            print_config_summary(agent)
        elif low.startswith("file "):
            await agent.handle_file_operation(cmd[5:])
        elif low.startswith("code "):
            res = await agent.run_code_interpreter(cmd[5:])
            rule("output")
            console.print(f"[body]{res or '(no output)'}[/body]")
            rule()
        elif low == "code":
            error("Usage: code <python>")
        elif low == "council on":
            agent.council_enabled = True
            ok("Council mode enabled")
        elif low == "council off":
            agent.council_enabled = False
            info("Council mode disabled")
        elif low == "autonomous on":
            agent.autonomous_enabled = True
            ok("Autonomous mode enabled")
        elif low == "autonomous off":
            agent.autonomous_enabled = False
            info("Autonomous mode disabled")
        elif low.startswith("priority"):
            parts = low.split()
            if len(parts) == 2 and parts[1] in ("speed", "accuracy", "balanced"):
                agent.priority = parts[1]
                ok(f"Priority set to {parts[1]}")
            else:
                error("Usage: priority speed|accuracy|balanced")
        elif low.startswith("persona"):
            parts = cmd.split(maxsplit=1)
            if len(parts) == 2:
                await agent.set_persona(parts[1].strip())
            else:
                error("Usage: persona default|coder|tutor|creative")
        elif low == "reload":
            await agent.reload_config()
        elif low.startswith("schedule "):
            parts = cmd.split(maxsplit=2)
            if len(parts) < 3:
                error("Usage: schedule <minutes> <task>")
                continue
            try:
                mins = int(parts[1])
                if mins < 1:
                    raise ValueError
            except ValueError:
                error("Schedule interval must be a positive number of minutes.")
                continue
            if agent.scheduler:
                agent.scheduler.add_job(mins, parts[2])
                ok(f"Scheduled every {mins} minute(s)")
            else:
                warn("Scheduler is disabled in config.yaml")
        elif low == "schedule":
            error("Usage: schedule <minutes> <task>")
        elif low == "unschedule":
            if agent.scheduler:
                agent.scheduler.jobs = []
                agent.scheduler.jobs_file.write_text("[]", encoding="utf-8")
                ok("All scheduled tasks removed")
            else:
                warn("Scheduler is disabled")
        elif low.startswith("conversation "):
            parts = cmd.split(maxsplit=2)
            action = parts[1].lower() if len(parts) > 1 else ""
            if action == "new":
                sid = agent.conversation.new_session()
                ok(f"New conversation: {sid}")
            elif action == "save":
                agent.conversation.save_session()
                ok("Conversation saved")
            elif action == "load":
                if len(parts) > 2:
                    loaded = agent.conversation.load_session(parts[2])
                    ok(f"Loaded conversation: {parts[2]}") if loaded else error("Session not found")
                else:
                    sessions = agent.conversation.list_sessions()
                    if sessions:
                        for session_id in sessions:
                            info(session_id)
                    else:
                        info("No saved sessions")
            else:
                error("Usage: conversation new|save|load [id]")
        elif low.startswith("voice"):
            await handle_voice_command(agent, cmd)
        elif low == "tools":
            if agent.tools:
                table = Table(show_header=True, header_style=f"bold {PRIMARY}", border_style=MUTED)
                table.add_column("Tool", style=BRIGHT)
                for name in agent.tools.list_names():
                    table.add_row(name)
                console.print(Padding(table, (0, 0, 0, 2)))
            else:
                warn("Tool system is disabled")
        else:
            thinking()
            try:
                await agent.run_task(cmd)
            except Exception as exc:
                error(str(exc))

    console.print()
    rule()
    info("Shutting down...")
    await agent.shutdown()
    info("Goodbye.")
    console.print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
    except Exception:
        traceback.print_exc()
        print("\nPress Enter to close...")
        input()
