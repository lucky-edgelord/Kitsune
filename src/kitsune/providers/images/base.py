from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ImageGenerator(Protocol):
    async def generate(self, prompt: str, *, negative: str = "", seed: Optional[int] = None) -> List[bytes]:
        """Return PNG bytes for each image. Raise :class:`kitsune.errors.ImageError` on failure."""

    async def aclose(self) -> None: ...
