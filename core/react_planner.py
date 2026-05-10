import asyncio
from core.ollama_client import query_model
from config_loader import config
from core.logger import logger

REASONING_PROMPT = """You are a problem-solving agent. You have access to these tools:
{tools}

Use search only for information that must come from the web. For local files,
folders, command execution, or operating-system work, use local tools or answer
with a concrete local plan. If you need a tool, output exactly one line:
TOOL: tool_name arguments
Otherwise, give the final answer.
Task: {task}
{history}
Step:"""

async def react_loop(task, model, tools_registry, system="", max_steps=5):
    steps = []
    history = ""
    for i in range(max_steps):
        tool_list = tools_registry.describe() if tools_registry else "none"
        prompt = REASONING_PROMPT.format(tools=tool_list, task=task, history=history)
        response = await query_model(model, prompt, system=system, temperature=0.3, max_tokens=1000)
        steps.append(response)
        if response.strip().startswith("TOOL:"):
            tool_call = response[5:].strip()
            parts = tool_call.split(maxsplit=1)
            tool_name = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            result = await tools_registry.execute(tool_name, args)
            history += f"\nStep {i+1}: Called {tool_name}({args}). Result: {result}\n"
        else:
            return response.strip()
    return "\n".join(steps)
