from . import SkillBase
import httpx, re
from bs4 import BeautifulSoup
from config_loader import config

class WebScraperSkill(SkillBase):
    name="web_scraper"; description="Extract text from a URL."
    keywords=["scrape","fetch url","read website","get webpage","extract text"]
    async def execute(self, task, model, council=False, **kwargs):
        urls = re.findall(r'https?://\S+', task)
        if not urls: return "No URL found."
        url = urls[0]
        headers = {"User-Agent": config.get("web_scraper",{}).get("user_agent","Eustathius/6.0")}
        try:
            async with httpx.AsyncClient(headers=headers) as client:
                resp = await client.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, "lxml")
                for tag in soup(["script","style","nav","footer"]): tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                return text[:5000] if len(text)>5000 else text
        except Exception as e: return f"Scraping error: {e}"
