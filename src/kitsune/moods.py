"""Kitsune's expressions: one sprite set per mood."""

from __future__ import annotations

from enum import Enum


class Mood(str, Enum):
    HAPPY = "happy"
    MAD = "mad"
    NEUTRAL = "neutral"
    SAD = "sad"
    SHY = "shy"

    @classmethod
    def parse(cls, value: str, default: Mood | None = None) -> Mood:
        try:
            return cls(value.strip().lower())
        except ValueError:
            return default or cls.NEUTRAL
