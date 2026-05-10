from . import SkillBase
import httpx
from config_loader import config

class WebSearchSkill(SkillBase):
    name = "web_search"
    description = "Search the web using DuckDuckGo (no API key needed)."
    keywords = ["search", "google", "internet", "find online", "look up", "web", "ddg"]

    async def execute(self, task, model, council=False, **kwargs):
        cfg = config.get("web_search", {})
        if not cfg.get("enabled", False):
            return "Web search is disabled. Enable it in config.yaml."

        query = task.lower().replace("search", "").replace("google", "").strip()
        if not query:
            return "Please specify what you want to search for."

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1
                    }
                )
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    return abstract
                related = data.get("RelatedTopics", [])
                if related:
                    return "\n".join(t.get("Text", "") for t in related[:3])
                return "No results found."
            except Exception as e:
                return f"Search error: {e}"
