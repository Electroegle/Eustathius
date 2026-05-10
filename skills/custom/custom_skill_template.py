"""
custom_skill_template.py
------------------------
Copy this file, rename it, and drop it in  skills/custom/
Eustathius will auto-discover it on the next start (or 'reload').

Requirements
------------
1. Import SkillBase from skills (the parent package)
2. Set class attributes: name, description, keywords
3. Implement async execute(task, model, council=False, **kwargs) -> str

The skill_loader recursively finds every SkillBase subclass in both
skills/ and skills/custom/ so no registration is needed.
"""

import os
import sys

# Allow importing from the project root when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.ollama_client import query_model
from skills import SkillBase


class MyCustomSkill(SkillBase):
    # ── Identity ────────────────────────────────────────────────────────────
    name        = "my_skill"          # unique snake_case identifier
    description = "Does something amazing with the given task."
    keywords    = ["amazing", "custom", "my"]   # words that route tasks here

    # ── Optional system prompt ───────────────────────────────────────────────
    _SYSTEM = (
        "You are a specialist assistant. "
        "Answer concisely and accurately."
    )

    # ── Main entry point ─────────────────────────────────────────────────────
    async def execute(self, task: str, model: str, council: bool = False, **kwargs) -> str:
        """
        `task`    – the user's raw input string
        `model`   – the Ollama model name chosen by model_selector
        `council` – True if council mode is active (you can ignore this or handle it)
        `kwargs`  – may contain 'system_prompt' (str) from agent._get_system_prompt()
        """
        system = kwargs.get("system_prompt", self._SYSTEM)

        # ── Example: just call the model ─────────────────────────────────────
        response = await query_model(
            model,
            task,
            system=system,
            temperature=0.5,
            max_tokens=800,
        )
        return response

        # ── Example: multi-step logic ─────────────────────────────────────────
        # step1 = await query_model(model, f"Plan for: {task}", system=system)
        # step2 = await query_model(model, f"Execute plan:\n{step1}", system=system)
        # return step2
