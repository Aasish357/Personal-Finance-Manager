"""
Thin client for a local Ollama server (https://ollama.com).

Talks to Ollama's native POST /api/chat endpoint over plain HTTP -- no vendor
SDK, no API key, and nothing leaves the machine. `httpx` is already a
dependency (FastAPI's test client uses it), so this adds no new packages.

Every function raises `OllamaError` on failure; callers are expected to fall
back to a rule-based reply rather than propagate the error to the user.
"""
from typing import Optional

import httpx

from app.core.config import settings


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable, or returns an unusable response."""


def _url(path: str) -> str:
    return f"{settings.ollama_base_url.rstrip('/')}{path}"


def is_available() -> bool:
    """True if the Ollama server is up. Cheap check, used by the status endpoint."""
    try:
        response = httpx.get(_url("/api/tags"), timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def list_models() -> list[str]:
    """Names of the models pulled locally, e.g. ['llama3:latest', 'phi3:mini']."""
    try:
        response = httpx.get(_url("/api/tags"), timeout=5.0)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise OllamaError(f"Could not list Ollama models: {exc}") from exc


def chat(system_prompt: str, history: list[dict], message: str) -> str:
    """
    Sends a system prompt plus prior turns to the local model and returns its
    reply text. `history` is a list of {'role', 'content'} dicts, which is the
    shape Ollama's chat API expects.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": settings.ollama_temperature,
            # Bounds the reply so a chatty local model cannot stall the endpoint.
            "num_predict": 400,
        },
    }

    try:
        response = httpx.post(
            _url("/api/chat"),
            json=payload,
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        content: Optional[str] = response.json()["message"]["content"]
    except httpx.HTTPStatusError as exc:
        # A 404 here almost always means the configured model is not pulled yet.
        detail = ""
        if exc.response.content:
            try:
                detail = exc.response.json().get("error", "")
            except ValueError:
                detail = exc.response.text
        hint = " -- try `ollama pull` for that model" if exc.response.status_code == 404 else ""
        raise OllamaError(f"Ollama returned {exc.response.status_code}{hint}: {detail}") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise OllamaError(f"Could not reach Ollama at {settings.ollama_base_url}: {exc}") from exc

    if not content or not content.strip():
        raise OllamaError("Ollama returned an empty response.")
    return content.strip()