"""Minimal Ollama client (local, free). https://github.com/ollama/ollama/blob/main/docs/api.md"""

from __future__ import annotations

import json
import re
from typing import Any

import requests


class LLMError(RuntimeError):
    pass


class Ollama:
    def __init__(self, model: str, host: str = "http://localhost:11434", timeout: int = 600):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=3)
            return r.ok
        except requests.RequestException:
            return False

    def chat(self, prompt: str, system: str = "", json_mode: bool = False,
             temperature: float = 0.5) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        if json_mode:
            body["format"] = "json"
        try:
            r = requests.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(
                f"Cannot reach Ollama at {self.host}. Is it running? (ollama serve)\n{e}"
            ) from e
        if r.status_code == 404:
            raise LLMError(f"Model '{self.model}' not found. Run: ollama pull {self.model}")
        if not r.ok:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")

    def chat_json(self, prompt: str, system: str = "", temperature: float = 0.4,
                  retries: int = 1) -> Any:
        """Ask for JSON; retry once with a stricter reminder if parsing fails."""
        last = ""
        for attempt in range(retries + 1):
            p = prompt if attempt == 0 else (
                prompt + "\n\nYour previous answer was not valid JSON. "
                "Reply with ONE valid JSON object only, no comments, no markdown."
            )
            last = self.chat(p, system=system, json_mode=True, temperature=temperature)
            data = parse_json(last)
            if data is not None:
                return data
        raise LLMError(f"Model did not return valid JSON. Last answer:\n{last[:500]}")


def parse_json(text: str) -> Any:
    """Parse JSON even if wrapped in ```json fences or surrounded by chatter."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None
