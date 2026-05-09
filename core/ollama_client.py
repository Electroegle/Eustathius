import asyncio, aiohttp, json
from typing import List, Optional
from core.logger import logger

OLLAMA_URL = "http://localhost:11434"

class ModelMemoryError(Exception): pass

async def health_check() -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{OLLAMA_URL}/") as r: return r.status == 200
    except: return False

async def list_models_async() -> List[str]:
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{OLLAMA_URL}/api/tags") as r:
            data = await r.json()
            return [m["name"] for m in data.get("models", [])]

async def query_model(model: str, prompt: str, system="", temperature=0.7, max_tokens=1000) -> str:
    payload = {"model": model, "messages": [{"role":"system","content":system},{"role":"user","content":prompt}],
               "options": {"temperature":temperature,"num_predict":max_tokens},"stream":False}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                raw = await resp.text()
                ctype = resp.headers.get("Content-Type","")
        # NDJSON detection
        if "x-ndjson" in ctype or raw.strip().startswith("{"):
            lines = raw.strip().splitlines()
            parts = []
            for line in lines:
                if not line.strip(): continue
                try:
                    obj = json.loads(line)
                    if "error" in obj:
                        err = obj["error"]
                        logger.error(f"Ollama error: {err}")
                        if "memory" in err.lower(): raise ModelMemoryError(err)
                        return f"[Ollama Error] {err}"
                    if "message" in obj and "content" in obj["message"]:
                        parts.append(obj["message"]["content"])
                    elif "response" in obj:
                        parts.append(obj["response"])
                except json.JSONDecodeError: pass
            if parts: return "".join(parts).strip()
        data = json.loads(raw)
        if "error" in data:
            err = data["error"]
            if "memory" in err.lower(): raise ModelMemoryError(err)
            return f"[Ollama Error] {err}"
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"].strip()
        if "response" in data: return data["response"].strip()
        return str(data)
    except ModelMemoryError: raise
    except aiohttp.ClientError as e:
        logger.error(f"Connection error: {e}"); return f"[Connection Error] {e}"
    except Exception as e:
        logger.error(f"Query error: {e}"); return f"[Error] {e}"
