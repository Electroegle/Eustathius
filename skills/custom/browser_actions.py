"""
browser_actions.py
------------------
All browser actions the agent can issue.

Each action function returns a short result string ("ok" / error message)
and takes a Playwright Page plus the parameters the LLM decided on.

Destructive actions (click, type, select, upload, submit) require
confirmation before execution — the caller (browser_agent) handles this.

Action catalogue
----------------
navigate  url                   -- go to a URL
click     target                -- click CSS selector or "x,y" coordinates
hover     target                -- move cursor to element
type      target  value         -- clear + type text into input
append    target  value         -- type without clearing first
select    target  value         -- choose <select> option by label or value
upload    target  value         -- set file-input path
scroll    target  value         -- "up" | "down" | int px; target = "page" | selector
key       value                 -- press a keyboard key (Enter, Tab, Escape...)
wait      value                 -- sleep N seconds
extract   target                -- return inner text of selector (read-only)
back                            -- browser back
done      value                 -- task finished; value = final answer
fail      value                 -- task cannot be completed; value = reason
"""

import asyncio

from playwright.async_api import Page

# Actions that need user confirmation before execution
DESTRUCTIVE = {"click", "type", "append", "select", "upload", "key"}


async def _resolve_target(page: Page, target: str):
    """
    Resolve a target string to a Playwright Locator.
    Supports:
      - CSS selector strings  (default)
      - "x,y" coordinate pairs (returns None; caller uses mouse.click)
      - XPath strings starting with //
    """
    if not target:
        return None, None

    # Coordinate pair: "x,y"
    if "," in target and all(p.strip().lstrip("-").isdigit() for p in target.split(",", 1)):
        x, y = (int(p.strip()) for p in target.split(",", 1))
        return None, (x, y)

    # XPath
    if target.startswith("//"):
        return page.locator(f"xpath={target}").first, None

    # CSS selector
    return page.locator(target).first, None


async def act_navigate(page: Page, url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        return f"navigated to {page.url}"
    except Exception as exc:
        return f"navigate failed: {exc}"


async def act_click(page: Page, target: str) -> str:
    locator, coords = await _resolve_target(page, target)
    try:
        if coords:
            await page.mouse.move(coords[0], coords[1])
            await asyncio.sleep(0.15)
            await page.mouse.click(coords[0], coords[1])
            return f"clicked ({coords[0]},{coords[1]})"
        await locator.scroll_into_view_if_needed(timeout=5_000)
        bbox = await locator.bounding_box()
        if bbox:
            cx, cy = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
            await page.mouse.move(cx, cy)
            await asyncio.sleep(0.1)
        await locator.click(timeout=8_000)
        return f"clicked {target}"
    except Exception as exc:
        return f"click failed ({target}): {exc}"


async def act_hover(page: Page, target: str) -> str:
    locator, coords = await _resolve_target(page, target)
    try:
        if coords:
            await page.mouse.move(coords[0], coords[1])
            return f"hovered ({coords[0]},{coords[1]})"
        bbox = await locator.bounding_box()
        if bbox:
            await page.mouse.move(
                bbox["x"] + bbox["width"] / 2,
                bbox["y"] + bbox["height"] / 2,
            )
        await locator.hover(timeout=5_000)
        return f"hovered {target}"
    except Exception as exc:
        return f"hover failed ({target}): {exc}"


async def act_type(page: Page, target: str, value: str) -> str:
    locator, _ = await _resolve_target(page, target)
    try:
        await locator.scroll_into_view_if_needed(timeout=5_000)
        await locator.click(timeout=5_000)
        await locator.fill("", timeout=3_000)       # clear
        await locator.type(value, delay=40)          # human-speed typing
        return f"typed into {target}"
    except Exception as exc:
        return f"type failed ({target}): {exc}"


async def act_append(page: Page, target: str, value: str) -> str:
    locator, _ = await _resolve_target(page, target)
    try:
        await locator.focus(timeout=5_000)
        await locator.type(value, delay=40)
        return f"appended into {target}"
    except Exception as exc:
        return f"append failed ({target}): {exc}"


async def act_select(page: Page, target: str, value: str) -> str:
    locator, _ = await _resolve_target(page, target)
    try:
        # Try by label first, then by value
        try:
            await locator.select_option(label=value, timeout=5_000)
        except Exception:
            await locator.select_option(value=value, timeout=5_000)
        return f"selected '{value}' in {target}"
    except Exception as exc:
        return f"select failed ({target}): {exc}"


async def act_upload(page: Page, target: str, filepath: str) -> str:
    locator, _ = await _resolve_target(page, target)
    try:
        await locator.set_input_files(filepath, timeout=8_000)
        return f"uploaded {filepath} to {target}"
    except Exception as exc:
        return f"upload failed ({target}): {exc}"


async def act_scroll(page: Page, target: str, value: str) -> str:
    try:
        if target and target.lower() != "page":
            locator, _ = await _resolve_target(page, target)
            await locator.scroll_into_view_if_needed(timeout=5_000)

        direction = value.lower() if isinstance(value, str) else "down"
        if direction == "up":
            await page.mouse.wheel(0, -600)
        elif direction == "down":
            await page.mouse.wheel(0, 600)
        else:
            px = int(value)
            await page.mouse.wheel(0, px)
        return f"scrolled {direction}"
    except Exception as exc:
        return f"scroll failed: {exc}"


async def act_key(page: Page, value: str) -> str:
    try:
        await page.keyboard.press(value)
        return f"pressed {value}"
    except Exception as exc:
        return f"key failed ({value}): {exc}"


async def act_wait(value: str) -> str:
    try:
        secs = max(0.5, min(float(value), 30.0))
        await asyncio.sleep(secs)
        return f"waited {secs}s"
    except Exception:
        await asyncio.sleep(1)
        return "waited 1s"


async def act_extract(page: Page, target: str) -> str:
    locator, _ = await _resolve_target(page, target)
    try:
        text = await locator.inner_text(timeout=5_000)
        return text.strip()[:2000]
    except Exception as exc:
        return f"extract failed ({target}): {exc}"


async def act_back(page: Page) -> str:
    try:
        await page.go_back(wait_until="domcontentloaded", timeout=10_000)
        return "went back"
    except Exception as exc:
        return f"back failed: {exc}"


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def dispatch(page: Page, action: str, target: str | None, value: str | None) -> str:
    """
    Route an action name + params to the correct async function.
    Returns a result string for logging and the next LLM observation.
    """
    t = (target or "").strip()
    v = (value  or "").strip()
    action = action.lower().strip()

    if action == "navigate":  return await act_navigate(page, v or t)
    if action == "click":     return await act_click(page, t)
    if action == "hover":     return await act_hover(page, t)
    if action == "type":      return await act_type(page, t, v)
    if action == "append":    return await act_append(page, t, v)
    if action == "select":    return await act_select(page, t, v)
    if action == "upload":    return await act_upload(page, t, v)
    if action == "scroll":    return await act_scroll(page, t or "page", v or "down")
    if action == "key":       return await act_key(page, v or t)
    if action == "wait":      return await act_wait(v or "1")
    if action == "extract":   return await act_extract(page, t)
    if action == "back":      return await act_back(page)
    if action in ("done", "fail"):
        return v or t   # caller handles terminal actions
    return f"unknown action: {action}"
