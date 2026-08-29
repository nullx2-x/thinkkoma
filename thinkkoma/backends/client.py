from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_llm_json(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", text.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON was not an object")
    return payload


def backend_name() -> str:
    return os.environ.get("THINKKOMA_BACKEND", "heuristic").strip().lower() or "heuristic"


def llm_enabled() -> bool:
    return backend_name() in {"ollama", "openai", "local"}


def _endpoint() -> tuple[str, str, str]:
    name = backend_name()
    if name in {"ollama", "local"}:
        host = os.environ.get("THINKKOMA_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        base = os.environ.get("OPENAI_BASE_URL", f"{host}/v1").rstrip("/")
        model = os.environ.get("THINKKOMA_MODEL", "llama3.2")
        raw_key = os.environ.get("OPENAI_API_KEY", os.environ.get("THINKKOMA_API_KEY", "ollama"))
        key = raw_key.strip() or "ollama"
        return base, model, key
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("THINKKOMA_MODEL", "gpt-4.1-mini")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return base, model, key


def chat_completion(
    messages: list[dict[str, str]],
    *,
    timeout: float = 60.0,
    opener=urllib.request.urlopen,
) -> str | None:
    if not llm_enabled():
        return None
    base, model, key = _endpoint()
    if backend_name() == "openai" and not key:
        return None
    payload = {"model": model, "temperature": 0, "messages": messages}
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, json.JSONDecodeError, OSError):
        return None
