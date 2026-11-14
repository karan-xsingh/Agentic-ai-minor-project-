"""Reads settings (LLM provider, model, API key) from backend/.env so they never need retyping.

The .env file is plain text, one setting per line:

    LLM_PROVIDER=groq
    GROQ_API_KEY=your-key
    LLM_MODEL=openai/gpt-oss-120b

Values in .env win over anything already set in the terminal or in Windows, which avoids
confusing leftovers from earlier sessions. The file is ignored by git so the key is not published.
"""
from __future__ import annotations
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:                      # trailing comment on an unquoted value
            value = value.split(" #", 1)[0].rstrip()
        if key.strip():
            values[key.strip()] = value
    return values


def load_env(path: Path | None = None) -> list[str]:
    """Apply the .env file to the process environment. Returns the names that were set."""
    path = Path(path) if path else ENV_FILE
    if not path.is_file():
        return []
    values = parse_env(path.read_text(encoding="utf-8-sig"))   # utf-8-sig: Notepad may add a BOM
    for key, value in values.items():
        os.environ[key] = value
    return list(values)
