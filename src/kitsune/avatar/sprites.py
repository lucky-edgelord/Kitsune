"""Sprite sets: ``<sprites_dir>/<mood>/{open,blink}_{closed,talk}.png``, cropped square on a backdrop."""

from __future__ import annotations

import io
import os
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..moods import Mood

#: frame order; index = (2 if blinking else 0) + (1 if mouth open else 0)
FRAME_NAMES = ("open_closed", "open_talk", "blink_closed", "blink_talk")


def backdrop(size: int) -> Image.Image:
    """A dark backdrop with a soft red glow behind her (her colours)."""
    bg = Image.new("RGB", (size, size), (18, 16, 22))
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).ellipse((-size * 0.2, size * 0.05, size * 1.2, size * 1.3), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, size // 5)))
    return Image.composite(Image.new("RGB", (size, size), (120, 22, 34)), bg, glow)


def square_crop(im: Image.Image, top_fraction: float = 0.02) -> Image.Image:
    """Square crop on the head and shoulders of a portrait sprite."""
    w, h = im.size
    side = min(w, h)
    top = min(round(h * top_fraction), h - side)
    left = (w - side) // 2
    return im.crop((left, top, left + side, top + side))


class SpriteBank:
    """Loads and caches composited RGB frames per mood at one square size."""

    def __init__(self, sprites_dir: str, size: int = 256) -> None:
        self.sprites_dir = sprites_dir
        self.size = size - size % 2
        self._cache: Dict[Mood, List[np.ndarray]] = {}

    def moods(self) -> List[Mood]:
        return [m for m in Mood if os.path.isdir(os.path.join(self.sprites_dir, m.value))]

    def frames(self, mood: Mood) -> List[np.ndarray]:
        if mood not in self._cache:
            folder = os.path.join(self.sprites_dir, mood.value)
            if not os.path.isdir(folder):
                return self.frames(Mood.NEUTRAL) if mood is not Mood.NEUTRAL else self._missing()
            bg = backdrop(self.size).convert("RGBA")
            frames = []
            for name in FRAME_NAMES:
                im = Image.open(os.path.join(folder, f"{name}.png")).convert("RGBA")
                im = square_crop(im).resize((self.size, self.size), Image.LANCZOS)
                canvas = bg.copy()
                canvas.alpha_composite(im)
                frames.append(np.asarray(canvas.convert("RGB")))
            self._cache[mood] = frames
        return self._cache[mood]

    def _missing(self) -> List[np.ndarray]:
        raise FileNotFoundError(f"no sprites in {self.sprites_dir!r} (expected <mood>/{FRAME_NAMES[0]}.png)")

    def still_png(self, mood: Mood) -> bytes:
        buf = io.BytesIO()
        Image.fromarray(self.frames(mood)[0]).save(buf, format="PNG")
        return buf.getvalue()
