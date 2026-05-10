"""
browser.py
----------
BrowserSkill — auto-discovered by Eustathius skill_loader.

Handles tasks that require controlling a real browser:
  login / fill forms, web scraping, UI testing, general browsing.

The skill:
  1. Detects the best installed browser (Chrome → Edge → Firefox → bundled Chromium)
  2. Launches it with Playwright in headed mode (user can watch)
  3. Swaps the OS cursor to a crosshair so it's obvious the agent is in control
  4. Runs the ReAct observe→think→act loop until done, stuck, or failed
  5. Restores the cursor and closes the browser cleanly
  6. Returns a summary string and saves logs/screenshots to logs/browser_sessions/

Keywords that route tasks here
-------------------------------
browse, browser, website, web page, click, fill form, login, sign in,
scrape, extract from website, navigate to, open url, download from,
search on, submit, screenshot site
"""


from playwright.async_api import async_playwright

from core.logger import logger
from core.theme import console, error, info, ok, rule
from skills import SkillBase
from skills.custom.browser_agent import run_agent_loop
from skills.custom.browser_cursor import agent_cursor
from skills.custom.browser_detector import detect_browser
from skills.custom.browser_session import SessionLog


class BrowserSkill(SkillBase):
    name = "browser"
    description = (
        "Controls a real browser to complete tasks: login, fill forms, "
        "scrape data, navigate websites, click elements, and extract information."
    )
    keywords = [
        "browse", "browser", "website", "web page", "webpage",
        "click", "fill form", "login", "sign in", "log in",
        "scrape", "extract from website", "navigate to", "open url",
        "download from", "search on", "submit", "screenshot site",
        "open browser", "go to url", "web scraping",
    ]

    async def execute(
        self,
        task: str,
        model: str,
        council: bool = False,
        **kwargs,
    ) -> str:
        browser_info = detect_browser()
        info(f"Browser: {browser_info.name}")

        log = SessionLog(task)
        result = "[No result]"

        try:
            async with async_playwright() as pw:
                # ── Launch browser ────────────────────────────────────────────
                launch_kwargs: dict = {
                    "headless": False,           # headed — agent must be visible
                    "slow_mo":  80,              # slight delay for visibility
                    "args":     ["--start-maximized"],
                }

                if browser_info.channel:
                    # Use installed browser via channel name
                    browser = await pw.chromium.launch(
                        channel=browser_info.channel, **launch_kwargs
                    ) if browser_info.channel not in ("firefox",) else \
                    await pw.firefox.launch(**{k: v for k, v in launch_kwargs.items() if k != "args"})
                else:
                    # Playwright bundled Chromium
                    browser = await pw.chromium.launch(**launch_kwargs)

                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()

                # ── Swap cursor + run loop ────────────────────────────────────
                rule("browser agent")
                info(f"Task: {task[:100]}")
                info(f"Model: {model}")
                info(f"Session log: {log.path}")
                console.print()

                with agent_cursor():
                    result = await run_agent_loop(page, task, model, log)

                await browser.close()

        except Exception as exc:
            error(f"Browser skill error: {exc}")
            logger.exception("BrowserSkill.execute crashed")
            result = f"[ERROR] {exc}"
        finally:
            log.close(result)
            ok(f"Session saved: {log.path}")

        return result
