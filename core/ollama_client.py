import asyncio
import json
from typing import Dict, List, Optional

import aiohttp

from core.logger import logger

OLLAMA_URL = "http://localhost:11434"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=180, connect=5)


class ModelMemoryError(Exception):
    pass


async def health_check() -> bool:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(f"{OLLAMA_URL}/") as response:
                return response.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def list_models_async() -> List[str]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{OLLAMA_URL}/api/tags") as response:
                if response.status != 200:
                    logger.error(f"Ollama tags request failed with HTTP {response.status}")
                    return []
                data = await response.json(content_type=None)
                return [model["name"] for model in data.get("models", []) if "name" in model]
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        logger.error(f"Could not list Ollama models: {exc}")
        return []


async def pull_model(model: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ollama",
        "pull",
        model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0


async def ensure_model_available(model: str) -> bool:
    if model in await list_models_async():
        return True
    from config_loader import config

    if config.get("auto_pull_missing_models", True):
        return await pull_model(model)
    return False


def _parse_ollama_error(message: str) -> str:
    if "memory" in message.lower():
        raise ModelMemoryError(message)
    return f"[Ollama Error] {message}"


async def query_model(
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    tools: Optional[List[Dict]] = None,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(f"{OLLAMA_URL}/api/chat", json=payload) as response:
                raw = await response.text()
                content_type = response.headers.get("Content-Type", "")
                if response.status >= 400:
                    return _parse_ollama_error(raw.strip() or f"HTTP {response.status}")

        if "x-ndjson" in content_type:
            return _parse_ndjson(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip()

        if "error" in data:
            return _parse_ollama_error(data["error"])
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"].strip()
        if "response" in data:
            return data["response"].strip()
        return str(data)
    except ModelMemoryError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.error(f"Connection error: {exc}")
        return f"[Connection Error] {exc}"
    except Exception as exc:
        logger.error(f"Query error: {exc}")
        return f"[Error] {exc}"


def _parse_ndjson(raw: str) -> str:
    parts = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "error" in obj:
            return _parse_ollama_error(obj["error"])
        if "message" in obj and "content" in obj["message"]:
            parts.append(obj["message"]["content"])
        elif "response" in obj:
            parts.append(obj["response"])
    return "".join(parts).strip()


async def get_embeddings(model: str, text: str) -> List[float]:
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(f"{OLLAMA_URL}/api/embeddings", json={"model": model, "prompt": text}) as response:
                if response.status != 200:
                    logger.error(f"Ollama embeddings request failed with HTTP {response.status}")
                    return []
                data = await response.json(content_type=None)
                return data.get("embedding", [])
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        logger.error(f"Embedding error: {exc}")
        return []
