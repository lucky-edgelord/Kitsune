"""Chat with Ollama (local server or ollama.com)."""

from __future__ import annotations

from typing import Dict, List, Optional

import httpx


class OllamaError(RuntimeError):
    pass


class Ollama:
    def __init__(self, host: str, model: str, api_key: str = "", timeout: float = 120.0) -> None:
        self.host = host.rstrip("/")
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.http = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def chat(self, messages: List[Dict[str, str]], *, options: Optional[dict] = None) -> str:
        body = {"model": self.model, "messages": messages, "stream": False}
        if options:
            body["options"] = options
        try:
            r = await self.http.post(f"{self.host}/api/chat", json=body)
        except httpx.HTTPError as e:
            raise OllamaError(f"can't reach Ollama at {self.host}: {e}") from e
        if r.status_code != 200:
            raise OllamaError(f"Ollama returned {r.status_code}: {r.text[:200]}")
        return (r.json().get("message") or {}).get("content", "").strip()

    async def close(self) -> None:
        await self.http.aclose()
