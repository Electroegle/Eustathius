import asyncio, sys, traceback
from rich.console import Console
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from core.agent import EustathiusAgent
from core.sys_monitor import system_stats
from core.logger import logger

console = Console()
COMMANDS = ['help','exit','file','code','priority','stats','models','history','reload','persona']
completer = WordCompleter(COMMANDS, ignore_case=True)
session = PromptSession(history=FileHistory('.eustathius_history'), auto_suggest=AutoSuggestFromHistory(), completer=completer)
agent = None

HELP = """
[bold]Commands:[/bold]
- [cyan]any sentence[/cyan]   Execute task
- [cyan]file <action> <path> [content][/cyan]  read/write/edit/revert
- [cyan]code <python code>[/cyan]   Execute Python sandbox (coming soon)
- [cyan]priority speed|accuracy|balanced[/cyan]
- [cyan]stats[/cyan]               System resources
- [cyan]models[/cyan]              List Ollama models
- [cyan]history[/cyan]             Recent tasks
- [cyan]reload[/cyan]              Reload config.yaml
- [cyan]help[/cyan]                This help
- [cyan]exit[/cyan]                Quit
"""

async def main():
    global agent
    agent = EustathiusAgent()
    await agent.start_background_worker()
    console.print("🤖 [bold green]Eustathius Agent v6.0[/bold green]")
    console.print("Type 'help' for commands.\n")
    while True:
        try:
            cmd = await session.prompt_async("you: ")
            cmd = cmd.strip()
            if not cmd: continue
            if cmd.lower() in ("exit","quit"):
                await agent.shutdown()
                break
            elif cmd.lower() == "help":
                console.print(HELP)
            elif cmd.lower().startswith("file "):
                await agent.handle_file_operation(cmd[5:])
            elif cmd.lower().startswith("code "):
                console.print("Code interpreter not yet implemented in this minimal build.")
            elif cmd.lower().startswith("priority "):
                p = cmd.split()[1].lower()
                if p in ("speed","accuracy","balanced"):
                    agent.priority = p; console.print(f"Priority: [bold]{p}[/bold]")
            elif cmd.lower() == "stats":
                s = system_stats(); console.print(f"CPU: {s['cpu_percent']}% | Memory: {s['memory_percent']}%")
            elif cmd.lower() == "models":
                from core.ollama_client import list_models_async
                models = await list_models_async()
                console.print("Models:", ", ".join(models))
            elif cmd.lower() == "history":
                await agent.show_history()
            elif cmd.lower() == "reload":
                console.print("Reload not implemented in this build.")
            else:
                await agent.run_task(cmd)
        except KeyboardInterrupt:
            await agent.shutdown()
            break
        except Exception as e:
            logger.exception("Main loop error")
            console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited by user.")
    except Exception as e:
        traceback.print_exc()
        print("\nPress Enter to close...")
        input()
