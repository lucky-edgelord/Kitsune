"""Which channels are Kitsune's chat and image channels (matched by name substring or exact id)."""

from __future__ import annotations

from typing import Any, Sequence


def matches(channel: Any, wanted: Sequence[str]) -> bool:
    name = (getattr(channel, "name", "") or "").lower()
    cid = str(getattr(channel, "id", "")).lower()
    return any(w.lower() == cid or (w.lower() in name) for w in wanted if w)
