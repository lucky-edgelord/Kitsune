"""Kitsune's two channels. She ignores every other channel completely.

* chat channel(s): talking videos, ``!kitsune``, ``!forget``, ``!mood``
* image channel(s): art from typed prompts and ``!image``

Channels are matched by name substring (case-insensitive) or exact id, so renaming the emoji part keeps working.
"""

from __future__ import annotations

from typing import Any, Sequence


def matches(channel: Any, wanted: Sequence[str]) -> bool:
    name = (getattr(channel, "name", "") or "").lower()
    cid = str(getattr(channel, "id", "")).lower()
    return any(w.lower() == cid or (w.lower() in name) for w in wanted if w)


def is_chat(bot: Any, channel: Any) -> bool:
    return matches(channel, bot.config.chat_channels)


def is_image(bot: Any, channel: Any) -> bool:
    return matches(channel, bot.config.image_channels)


def is_hers(bot: Any, channel: Any) -> bool:
    return is_chat(bot, channel) or is_image(bot, channel)
