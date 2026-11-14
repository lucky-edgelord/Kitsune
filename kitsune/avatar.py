"""Lip-synced talking video from the Fox Mafia sprites.

Each emotion has four frames: eyes open / blinking x mouth closed / talking. The mouth follows the loudness of the
voice (RMS per video frame, with a short hold so it doesn't flicker), and she blinks every few seconds.
"""

from __future__ import annotations

import asyncio
import os
import random
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

FRAMES = ("open_closed", "open_talk", "blink_closed", "blink_talk")
FPS = 24
SAMPLE_RATE = 16000


def _background(size: Tuple[int, int]) -> Image.Image:
    """A soft dark backdrop with a red glow behind her (her colours)."""
    w, h = size
    bg = Image.new("RGB", size, (18, 16, 22))
    glow = Image.new("L", size, 0)
    ImageDraw.Draw(glow).ellipse((-w * 0.2, h * 0.05, w * 1.2, h * 1.3), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(w // 5))
    red = Image.new("RGB", size, (120, 22, 34))
    return Image.composite(red, bg, glow)


class Avatar:
    def __init__(self, sprites_dir: str, *, size: int = 256) -> None:
        self.sprites_dir = sprites_dir
        self.size = size - size % 2      # square video, like Neku (which used 480x480)
        self._cache: Dict[str, List[np.ndarray]] = {}

    def frames(self, emotion: str) -> List[np.ndarray]:
        if emotion not in self._cache:
            folder = os.path.join(self.sprites_dir, emotion)
            if not os.path.isdir(folder):
                folder = os.path.join(self.sprites_dir, "neutral")
            out = []
            for name in FRAMES:
                im = Image.open(os.path.join(folder, f"{name}.png")).convert("RGBA")
                w, h = im.size
                side = min(w, h)
                top = round(h * 0.02)                       # square crop on head and shoulders
                im = im.crop(((w - side) // 2, top, (w - side) // 2 + side, top + side))
                im = im.resize((self.size, self.size), Image.LANCZOS)
                bg = _background(im.size).convert("RGBA")
                bg.alpha_composite(im)
                out.append(np.asarray(bg.convert("RGB")))
            self._cache[emotion] = out
        return self._cache[emotion]

    def still(self, emotion: str) -> bytes:
        """A PNG of her current expression (used when there's no voice)."""
        import io

        buf = io.BytesIO()
        Image.fromarray(self.frames(emotion)[0]).save(buf, format="PNG")
        return buf.getvalue()

    # -- timing ------------------------------------------------------------------------------------------
    @staticmethod
    def decode(audio: bytes) -> np.ndarray:
        """Any audio ffmpeg understands -> mono float32 samples at 16 kHz."""
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SAMPLE_RATE),
                            "-f", "s16le", "pipe:1"], input=audio, capture_output=True, check=True)
        return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0

    @staticmethod
    def mouth_track(samples: np.ndarray, fps: int = FPS, hold: int = 2) -> List[bool]:
        """True where the mouth is open, one entry per video frame."""
        step = SAMPLE_RATE // fps
        n = max(1, int(np.ceil(len(samples) / step)))
        rms = np.array([np.sqrt(np.mean(samples[i * step:(i + 1) * step] ** 2)) if len(samples[i * step:(i + 1) * step]) else 0.0
                        for i in range(n)])
        loud = np.percentile(rms, 90) if rms.any() else 0.0
        threshold = max(0.015, loud * 0.35)
        raw = rms > threshold
        out: List[bool] = []
        open_for = closed_for = hold
        for r in raw:
            # require a short hold before switching, so the mouth flaps instead of flickering
            if r and (out and not out[-1]) and closed_for < hold:
                r = False
            if not r and (out and out[-1]) and open_for < hold:
                r = True
            if out and r == out[-1]:
                open_for, closed_for = (open_for + 1, 0) if r else (0, closed_for + 1)
            else:
                open_for, closed_for = (1, 0) if r else (0, 1)
            out.append(bool(r))
        # in long loud stretches, close briefly every few frames so it reads as speech, not a held "ah"
        run = 0
        for i, r in enumerate(out):
            run = run + 1 if r else 0
            if run and run % 7 == 0:
                out[i] = False
        return out

    @staticmethod
    def blink_track(n: int, fps: int = FPS, rng: Optional[random.Random] = None) -> List[bool]:
        rng = rng or random.Random()
        out = [False] * n
        t = int(rng.uniform(1.0, 2.5) * fps)
        while t < n:
            for i in range(t, min(n, t + 3)):
                out[i] = True
            t += int(rng.uniform(2.5, 5.0) * fps)
        return out

    # -- rendering -------------------------------------------------------------------------------------------
    def render(self, audio: bytes, emotion: str, out_path: str, *, seed: Optional[int] = None) -> str:
        frames = self.frames(emotion)
        samples = self.decode(audio)
        mouth = self.mouth_track(samples)
        blink = self.blink_track(len(mouth), rng=random.Random(seed))
        h, w, _ = frames[0].shape
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as a:
            a.write(audio)
            audio_path = a.name
        try:
            cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                   "-r", str(FPS), "-i", "pipe:0", "-i", audio_path, "-map", "0:v", "-map", "1:a",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out_path]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert p.stdin is not None
            for m, b in zip(mouth, blink):
                p.stdin.write(frames[(2 if b else 0) + (1 if m else 0)].tobytes())
            p.stdin.close()
            err = p.stderr.read().decode() if p.stderr else ""
            if p.wait() != 0:
                raise RuntimeError(f"ffmpeg failed: {err[-400:]}")
        finally:
            os.unlink(audio_path)
        return out_path

    async def render_async(self, audio: bytes, emotion: str, out_path: str) -> str:
        return await asyncio.to_thread(self.render, audio, emotion, out_path)
