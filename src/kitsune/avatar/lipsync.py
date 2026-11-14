"""When the mouth is open and when she blinks, one decision per video frame."""

from __future__ import annotations

import random
import subprocess
from typing import List, Optional

import numpy as np

from ..errors import RenderError

FPS = 24
SAMPLE_RATE = 16000


def decode_audio(audio: bytes) -> np.ndarray:
    """Any audio ffmpeg understands -> mono float32 samples at :data:`SAMPLE_RATE`."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1"],
            input=audio,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RenderError("ffmpeg is not installed") from e
    except subprocess.CalledProcessError as e:
        raise RenderError(f"couldn't decode audio: {e.stderr.decode(errors='replace')[-300:]}") from e
    return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def frame_rms(samples: np.ndarray, fps: int = FPS) -> np.ndarray:
    step = SAMPLE_RATE // fps
    n = max(1, int(np.ceil(len(samples) / step)))
    padded = np.zeros(n * step, dtype=np.float32)
    padded[: len(samples)] = samples
    return np.sqrt(np.mean(padded.reshape(n, step) ** 2, axis=1))


def mouth_track(
    samples: np.ndarray,
    fps: int = FPS,
    *,
    hold: int = 2,
    flap_every: int = 7,
    sensitivity: float = 0.35,
    floor: float = 0.015,
) -> List[bool]:
    """Open where the voice is loud relative to its own peaks.

    * ``hold``: minimum frames before switching state, so the mouth flaps instead of flickering.
    * ``flap_every``: in long loud runs, close for one frame every N frames so it reads as speech.
    """
    rms = frame_rms(samples, fps)
    peak = float(np.percentile(rms, 90)) if rms.any() else 0.0
    loud = rms > max(floor, peak * sensitivity)
    out: List[bool] = []
    run = 0
    for want in loud:
        if out and want != out[-1] and run < hold:
            want = out[-1]
        run = run + 1 if out and want == out[-1] else 1
        out.append(bool(want))
    open_run = 0
    for i, is_open in enumerate(out):
        open_run = open_run + 1 if is_open else 0
        if open_run and open_run % flap_every == 0:
            out[i] = False
    return out


def blink_track(
    frames: int, fps: int = FPS, *, rng: Optional[random.Random] = None, length: int = 3, every: tuple = (2.5, 5.0)
) -> List[bool]:
    rng = rng or random.Random()
    out = [False] * frames
    t = int(rng.uniform(1.0, 2.5) * fps)
    while t < frames:
        for i in range(t, min(frames, t + length)):
            out[i] = True
        t += int(rng.uniform(*every) * fps)
    return out
