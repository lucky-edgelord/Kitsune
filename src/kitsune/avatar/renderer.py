"""Encode a talking clip: sprite frames driven by the lip-sync tracks, muxed with the voice."""

from __future__ import annotations

import asyncio
import os
import random
import subprocess
import tempfile
from typing import Optional

from ..errors import RenderError
from ..moods import Mood
from .lipsync import FPS, blink_track, decode_audio, mouth_track
from .sprites import SpriteBank


class AvatarRenderer:
    def __init__(self, sprites: SpriteBank, *, crf: int = 26, preset: str = "veryfast") -> None:
        self.sprites = sprites
        self.crf = crf
        self.preset = preset

    def render(self, audio: bytes, mood: Mood, *, seed: Optional[int] = None) -> bytes:
        """Return an MP4 (H.264 + AAC) of Kitsune saying ``audio`` with ``mood``."""
        frames = self.sprites.frames(mood)
        mouth = mouth_track(decode_audio(audio))
        blinks = blink_track(len(mouth), rng=random.Random(seed))
        size = frames[0].shape[1]
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "voice")
            out_path = os.path.join(tmp, "kitsune.mp4")
            with open(audio_path, "wb") as f:
                f.write(audio)
            cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{size}x{size}",
                "-r",
                str(FPS),
                "-i",
                "pipe:0",
                "-i",
                audio_path,
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                self.preset,
                "-crf",
                str(self.crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-shortest",
                "-movflags",
                "+faststart",
                out_path,
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert proc.stdin is not None and proc.stderr is not None
            try:
                for m, b in zip(mouth, blinks):
                    proc.stdin.write(frames[(2 if b else 0) + (1 if m else 0)].tobytes())
                proc.stdin.close()
            except BrokenPipeError:
                pass
            err = proc.stderr.read().decode(errors="replace")
            if proc.wait() != 0:
                raise RenderError(f"ffmpeg failed: {err[-400:]}")
            with open(out_path, "rb") as f:
                return f.read()

    async def render_async(self, audio: bytes, mood: Mood, *, seed: Optional[int] = None) -> bytes:
        return await asyncio.to_thread(self.render, audio, mood, seed=seed)
