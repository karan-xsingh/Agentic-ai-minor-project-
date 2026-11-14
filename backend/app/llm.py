"""Provider-agnostic LLM access (Step 2).

An LLM here is just a function:  llm(system_prompt, user_prompt) -> str
Choose the provider with environment variables, no code changes:

    LLM_PROVIDER = gemini | openai | ollama
    LLM_MODEL    = (optional) model name
    GEMINI_API_KEY / OPENAI_API_KEY   (not needed for ollama)
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from typing import Callable

from . import config

LLM = Callable[[str, str], str]

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
    "grok": "",   # set LLM_MODEL (see console.x.ai)
    "groq": "",   # set LLM_MODEL (see console.groq.com)
}


class LLMError(Exception):
    pass


def _post_once(url: str, payload: dict, headers: dict | None = None, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "agentic-analyst/1.0",
                 **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        err = LLMError(f"HTTP {exc.code}: {body[:2000]}")
        err.body = body
        raise err from exc
    except Exception as exc:
        raise LLMError(str(exc)) from exc


RETRY_CODES = ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")


def _post(url: str, payload: dict, headers: dict | None = None, timeout: int = 90) -> dict:
    """Retry temporary provider errors (overload / rate limit) with a growing wait."""
    import time
    waits = [2, 4, 8, 16]
    for attempt in range(len(waits) + 1):
        try:
            return _post_once(url, payload, headers, timeout)
        except LLMError as exc:
            if attempt == len(waits) or not str(exc).startswith(RETRY_CODES):
                raise
            time.sleep(waits[attempt])


def _salvage_failed_generation(body: str):
    """Some models (e.g. gpt-oss on Groq) answer with a pseudo tool-call and the server rejects it
    with tool_use_failed. The intended answer is still in error.failed_generation. Recover it as a
    {"steps": [...]} plan; the tool whitelist is applied afterwards, so this stays safe."""
    try:
        call = json.loads(json.loads(body)["error"]["failed_generation"])
    except Exception:
        return None
    if not isinstance(call, dict):
        return None
    if isinstance(call.get("steps"), list):                      # plan returned bare
        return json.dumps(call)
    args = call.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return None
    if not isinstance(args, dict):
        return None
    if isinstance(args.get("steps"), list):                      # plan wrapped in a pseudo tool-call
        return json.dumps(args)
    name = call.get("name")
    if isinstance(name, str) and name != "commentary":           # model called one of our tools directly
        return json.dumps({"steps": [{"tool": name, "args": args}]})
    return None


def _post_chat(url: str, payload: dict, headers: dict | None = None, timeout: int = 90) -> dict:
    try:
        return _post(url, payload, headers, timeout)
    except LLMError as exc:
        text = _salvage_failed_generation(getattr(exc, "body", ""))
        if text is None:
            raise
        return {"choices": [{"message": {"content": text}}]}


def make_llm(provider: str | None = None, model: str | None = None) -> LLM:
    config.load_env()          # settings saved in backend/.env
    provider = (provider or os.getenv("LLM_PROVIDER", "")).lower()
    if provider not in DEFAULT_MODELS:
        raise LLMError("Set LLM_PROVIDER to one of: gemini, openai, groq, grok, ollama")
    model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
    if not model:
        raise LLMError("Set LLM_MODEL for this provider (e.g. a Grok model name from console.x.ai)")

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set")

        def call(system: str, user: str) -> str:
            data = _post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                {"systemInstruction": {"parts": [{"text": system}]},
                 "contents": [{"role": "user", "parts": [{"text": user}]}],
                 "generationConfig": {"temperature": 0}},
                {"x-goog-api-key": key},
            )
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Unexpected Gemini response: {str(data)[:200]}") from exc
        return call

    if provider in ("openai", "grok", "groq"):
        key_var = {"grok": "XAI_API_KEY", "groq": "GROQ_API_KEY"}.get(provider, "OPENAI_API_KEY")
        base = {"grok": "https://api.x.ai/v1", "groq": "https://api.groq.com/openai/v1"}.get(
            provider, "https://api.openai.com/v1")
        key = os.getenv(key_var)
        if not key:
            raise LLMError(f"{key_var} is not set")

        def call(system: str, user: str) -> str:
            data = _post_chat(
                f"{base}/chat/completions",
                {"model": model, "temperature": 0,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": user}]},
                {"Authorization": f"Bearer {key}"},
            )
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Unexpected OpenAI response: {str(data)[:200]}") from exc
        return call

    def call(system: str, user: str) -> str:  # ollama (local, free)
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        data = _post(f"{host}/api/chat",
                     {"model": model, "stream": False, "options": {"temperature": 0},
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}]}, timeout=300)
        try:
            return data["message"]["content"]
        except KeyError as exc:
            raise LLMError(f"Unexpected Ollama response: {str(data)[:200]}") from exc
    return call
