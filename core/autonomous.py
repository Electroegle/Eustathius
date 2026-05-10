import asyncio
from rich.prompt import Confirm
from core.ollama_client import query_model
from core.theme import console, rule, info, ok, warn, PRIMARY
from config_loader import config
from core.logger import logger

REVIEW_PROMPT = """Review the solution. If you need user clarification, start with "QUESTION:".
Otherwise, provide improvements as a numbered list. Output "OK" if perfect.
Task: {task}
Solution: {solution}
Critique:"""

IMPROVEMENT_PROMPT = """Improve the solution based on critique.
Task: {task}
Previous: {solution}
Critique: {critique}
Improved:"""

async def autonomous_loop(task, initial, skill, model, max_iter=5):
    cur = initial
    for i in range(max_iter):
        review_model = config.get("autonomous",{}).get("self_review_model", model)
        critique = await query_model(review_model, REVIEW_PROMPT.format(task=task, solution=cur),
                                     temperature=0.2, max_tokens=500)
        logger.info(f"Auto review {i+1}: {critique[:100]}...")
        console.print(f"[dim_text]  review {i+1}  [/dim_text][{PRIMARY}]{critique[:120]}[/{PRIMARY}]")
        if critique.strip().startswith("OK"):
            ok("Solution accepted"); return cur
        if critique.strip().startswith("QUESTION:"):
            q = critique[9:].strip()
            warn(q)
            if Confirm.ask("[dim_text]  Can you answer?[/dim_text]", default=True):
                ans = console.input("[dim_text]  Answer: [/dim_text]")
                cur = await query_model(model, IMPROVEMENT_PROMPT.format(task=task, solution=cur, critique=f"User clarified: {ans}"),
                                        temperature=0.3)
            else: info("Continuing without answer")
        else:
            improved = await query_model(model, IMPROVEMENT_PROMPT.format(task=task, solution=cur, critique=critique),
                                         temperature=0.3)
            if improved == cur: info("No further improvement"); return cur
            cur = improved
    warn("Maximum autonomous iterations reached"); return cur
