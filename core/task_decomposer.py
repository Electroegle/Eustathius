from config_loader import config

from .ollama_client import query_model

DECOMPOSE_PROMPT = """Break user request into a numbered list of independent subtasks (max {max_subtasks}). Output only the list.
User request: {user_request}
Subtasks:"""

async def decompose_task(user_request: str) -> list:
    max_sub = config.get("task_decomposer",{}).get("max_subtasks",5)
    resp = await query_model("qwen:0.5b", DECOMPOSE_PROMPT.format(max_subtasks=max_sub, user_request=user_request),
                             temperature=0.2, max_tokens=200)
    subtasks = []
    for line in resp.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            task = line.split(".",1)[-1].strip()
            if task: subtasks.append(task)
    return subtasks
