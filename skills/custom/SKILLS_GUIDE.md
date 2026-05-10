# Eustathius Custom Skills Guide

## How Skills Work

Skills are the building blocks Eustathius uses to specialise its responses.
When you type a task, `core/task_router.py` keyword-matches your input to
the best skill and passes it to the chosen Ollama model.

---

## Adding a Custom Skill — 3 steps

### 1. Copy the template
```
skills/custom/custom_skill_template.py  →  skills/custom/my_new_skill.py
```

### 2. Fill in four things
```python
class MyNewSkill(SkillBase):
    name        = "my_new_skill"          # unique, snake_case
    description = "One-line description." # used in prompt optimisation
    keywords    = ["word1", "word2"]      # words that route tasks here
    async def execute(self, task, model, council=False, **kwargs) -> str:
        ...
```

### 3. Restart or type `reload`
Eustathius auto-discovers every `SkillBase` subclass in `skills/` and
`skills/custom/` — no registration needed.

---

## Keyword Routing

The router counts whole-word matches between your task text and each skill's
`keywords` list.  The skill with the **most matches wins**.

If no skill matches, the `research` skill is used as a fallback.

Tip: Use specific, non-overlapping keywords for custom skills so they don't
compete with the built-in ones.

---

## Built-in Skills

| Skill file      | Name          | Keywords (sample)                       |
|-----------------|---------------|-----------------------------------------|
| coding.py       | coding        | code, refactor, debug, function, script |
| research.py     | research      | research, find, explain, what, how      |
| summarizer.py   | summarizer    | summarize, summary, tldr, brief         |
| file_search.py  | file_search   | find file, search file, locate          |
| sysadmin.py     | sysadmin      | run, execute, shell, command, process   |
| web_search.py   | web_search    | search web, google, online, latest      |
| web_scraper.py  | web_scraper   | scrape, crawl, fetch url, website       |
| weather.py      | weather       | weather, temperature, forecast          |

---

## Skill execute() Contract

```python
async def execute(self, task: str, model: str, council: bool = False, **kwargs) -> str:
    # task   → user's input string
    # model  → selected Ollama model name
    # kwargs → may contain 'system_prompt' (str)
    # return → the final string response shown to the user
```

Return a plain string.  Raise exceptions only for genuine errors —
the agent's retry loop will catch them and try again with a different model.

---

## Tips

- Keep `temperature` low (0.2–0.4) for factual/coding tasks, higher for creative.
- Use `kwargs.get("system_prompt", self._SYSTEM)` so the agent's persona
  and prompt-optimiser can override your default system prompt.
- Multi-step skills work fine — just `await query_model(...)` multiple times.
- You can import other skills and call their `execute()` to chain them.

---

## Example: A "Translate" Skill

```python
from skills import SkillBase
from core.ollama_client import query_model

class TranslateSkill(SkillBase):
    name        = "translate"
    description = "Translates text to a target language."
    keywords    = ["translate", "translation", "in french", "in spanish", "in arabic"]

    async def execute(self, task, model, council=False, **kwargs):
        system = "You are a professional translator. Output only the translation, no commentary."
        return await query_model(model, task, system=system, temperature=0.2, max_tokens=600)
```

Drop it in `skills/custom/translate.py` and type `reload`.
