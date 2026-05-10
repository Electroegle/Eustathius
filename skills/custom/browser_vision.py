"""
browser_vision.py
-----------------
Handles two concerns:

1. OBSERVATION — captures what the agent currently sees:
   - Screenshot (PNG bytes via Playwright)
   - DOM summary (interactive elements + visible text via JS)

2. VISION ROUTING — decides whether to send the screenshot to the LLM:
   - Queries Ollama /api/show to check if the current model has vision capability
   - If yes: screenshot is base64-encoded and included in the LLM message
   - If no: DOM text only (no image)

The result is an Observation dataclass consumed by the agent loop.
"""

import base64
from dataclasses import dataclass

import aiohttp
from playwright.async_api import Page

from core.logger import logger

OLLAMA_URL = "http://localhost:11434"

# ── DOM extractor (runs inside the browser via page.evaluate) ─────────────────

_DOM_SCRIPT = """
() => {
    const MAX_TEXT = 2000;

    // Interactive elements
    const interactive = [];
    const selectors = 'a[href], button, input, select, textarea, [role="button"], [onclick]';
    document.querySelectorAll(selectors).forEach((el, i) => {
        if (i >= 60) return;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return;
        const tag  = el.tagName.toLowerCase();
        const id   = el.id ? '#' + el.id : '';
        const cls  = el.className && typeof el.className === 'string'
                     ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '';
        const label = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').slice(0,60).trim();
        const type  = el.type || el.tagName.toLowerCase();
        interactive.push({ selector: tag + id + cls, type, label, x: Math.round(rect.x + rect.width/2), y: Math.round(rect.y + rect.height/2) });
    });

    // Visible text (headings + paragraphs)
    let text = '';
    document.querySelectorAll('h1,h2,h3,h4,p,li,td,th,label,span,div').forEach(el => {
        if (text.length > MAX_TEXT) return;
        const t = (el.innerText || '').trim();
        if (t && t.length > 5 && t.length < 300) text += t + '\\n';
    });

    // Forms
    const forms = [];
    document.querySelectorAll('form').forEach(f => {
        const inputs = [];
        f.querySelectorAll('input,select,textarea').forEach(inp => {
            inputs.push({ name: inp.name || inp.id, type: inp.type, placeholder: inp.placeholder });
        });
        forms.push({ action: f.action, method: f.method, inputs });
    });

    return {
        title: document.title,
        url: window.location.href,
        interactive: interactive.slice(0, 50),
        text: text.slice(0, MAX_TEXT),
        forms
    };
}
"""


@dataclass
class Observation:
    url: str
    title: str
    dom: dict                         # raw JS result
    dom_text: str                     # formatted for LLM prompt
    screenshot_bytes: bytes | None    # PNG, or None if capture failed
    has_vision: bool                  # whether LLM can see the screenshot
    screenshot_b64: str | None = None # base64 if has_vision


# ── Vision capability check ───────────────────────────────────────────────────

_vision_cache: dict[str, bool] = {}


async def model_has_vision(model: str) -> bool:
    """
    Ask Ollama /api/show whether this model supports vision (has a CLIP projector).
    Result is cached per model name for the session.
    """
    if model in _vision_cache:
        return _vision_cache[model]

    # Fast name-based heuristic first (avoids an API call for obvious cases)
    vision_keywords = {"llava", "bakllava", "moondream", "minicpm-v",
                       "cogvlm", "internvl", "qwen-vl", "phi3-vision",
                       "llava-phi3", "llava-llama3"}
    name_lower = model.lower().replace(":", "-")
    if any(k in name_lower for k in vision_keywords):
        _vision_cache[model] = True
        return True

    # Definitive check via Ollama API
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=8)
        ) as session:
            async with session.post(
                f"{OLLAMA_URL}/api/show", json={"name": model}
            ) as resp:
                if resp.status != 200:
                    _vision_cache[model] = False
                    return False
                data = await resp.json(content_type=None)
                families = data.get("details", {}).get("families", [])
                has = any(f in {"clip", "vision"} for f in families)
                _vision_cache[model] = has
                logger.info(f"Vision check {model}: {'yes' if has else 'no'} (families={families})")
                return has
    except Exception as exc:
        logger.warning(f"Vision check failed for {model}: {exc}")
        _vision_cache[model] = False
        return False


# ── DOM formatter ─────────────────────────────────────────────────────────────

def _format_dom(dom: dict) -> str:
    lines = [f"Title: {dom.get('title', '')}", f"URL:   {dom.get('url', '')}"]

    interactive = dom.get("interactive", [])
    if interactive:
        lines.append("\n[Interactive elements]")
        for el in interactive[:30]:
            label = f' "{el["label"]}"' if el.get("label") else ""
            coord = f" @({el['x']},{el['y']})" if el.get("x") else ""
            lines.append(f"  {el['selector']}  [{el['type']}]{label}{coord}")

    forms = dom.get("forms", [])
    if forms:
        lines.append("\n[Forms]")
        for form in forms:
            lines.append(f"  action={form.get('action','')} method={form.get('method','')}")
            for inp in form.get("inputs", []):
                lines.append(f"    input name={inp.get('name','')} type={inp.get('type','')} placeholder={inp.get('placeholder','')}")

    text = dom.get("text", "").strip()
    if text:
        lines.append("\n[Page text excerpt]")
        lines.append(text[:1000])

    return "\n".join(lines)


# ── Main observe function ─────────────────────────────────────────────────────

async def observe(page: Page, model: str) -> Observation:
    """Capture screenshot + DOM and determine whether to send vision to LLM."""

    # Screenshot
    try:
        png_bytes = await page.screenshot(type="png", full_page=False)
    except Exception as exc:
        logger.warning(f"Screenshot failed: {exc}")
        png_bytes = None

    # DOM
    try:
        dom = await page.evaluate(_DOM_SCRIPT)
    except Exception as exc:
        logger.warning(f"DOM extraction failed: {exc}")
        dom = {"title": "", "url": page.url, "interactive": [], "text": "", "forms": []}

    dom_text = _format_dom(dom)

    # Vision routing
    has_vision = (png_bytes is not None) and await model_has_vision(model)
    b64 = base64.b64encode(png_bytes).decode() if has_vision and png_bytes else None

    return Observation(
        url=dom.get("url", page.url),
        title=dom.get("title", ""),
        dom=dom,
        dom_text=dom_text,
        screenshot_bytes=png_bytes,
        has_vision=has_vision,
        screenshot_b64=b64,
    )
