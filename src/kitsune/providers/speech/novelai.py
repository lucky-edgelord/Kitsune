"""NovelAI text-to-speech (TTS v2)."""

from __future__ import annotations

from typing import Optional

import httpx

from ...errors import SpeechError

API = "https://api.novelai.net"
MAX_CHARS = 1000  # NovelAI cuts longer text server-side


class NovelAISpeech:
    def __init__(
        self,
        token: str,
        *,
        voice_seed: str = "Aini",
        timeout: float = 120.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not token:
            raise SpeechError("a NovelAI token is required for speech")
        self.voice_seed = voice_seed
        self._http = httpx.AsyncClient(
            base_url=API, timeout=timeout, transport=transport, headers={"Authorization": f"Bearer {token}"}
        )

    async def synthesize(self, text: str) -> bytes:
        body = {"text": text[:MAX_CHARS], "seed": self.voice_seed, "voice": -1, "opus": False, "version": "v2"}
        try:
            r = await self._http.post("/ai/generate-voice", json=body)
        except httpx.HTTPError as e:
            raise SpeechError(f"can't reach NovelAI: {e}") from e
        if r.status_code >= 400:
            raise SpeechError(f"NovelAI TTS returned {r.status_code}: {r.text[:200]}")
        return r.content

    async def aclose(self) -> None:
        await self._http.aclose()
