"""Neku's ``audio_analysis``: one mouth class per video frame from the voice's loudness.

Neku (``fgk_neku.py``) loaded the voice with librosa and classed each 1/16 s frame by RMS: ``0`` closed below 0.1,
``1`` half below 0.125, ``2`` open above. Those absolute thresholds were tuned to Inworld's audio level.

Improvements here:
* decoding goes through ffmpeg (no librosa / numba stack),
* thresholds are relative to the clip's own loudness by default, so any TTS voice or volume works
  (pass ``thresholds=NEKU_THRESHOLDS`` for Neku's exact behaviour),
* a 3-frame median smooths single-frame flicker.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional, Sequence, Tuple

import numpy as np

from ..errors import RenderError

FPS = 16  # Neku's frame rate
SAMPLE_RATE = 22050  # librosa's default, as Neku used
NEKU_THRESHOLDS: Tuple[float, float] = (0.1, 0.125)


def load_audio(audio: bytes) -> np.ndarray:
    """Any audio ffmpeg understands -> mono float32 samples (librosa.load equivalent)."""
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


def frame_rms(y: np.ndarray, fps: int = FPS) -> np.ndarray:
    frame_samples = int(SAMPLE_RATE / fps)
    n = max(1, int(np.ceil(len(y) / frame_samples)))
    padded = np.zeros(n * frame_samples, dtype=np.float32)
    padded[: len(y)] = y
    return np.sqrt(np.mean(padded.reshape(n, frame_samples) ** 2, axis=1))


def relative_thresholds(
    rms: np.ndarray, half: float = 0.3, full: float = 0.6, floor: float = 0.003
) -> Tuple[float, float]:
    peak = float(np.percentile(rms, 90)) if rms.any() else 0.0
    return max(floor, peak * half), max(floor * 1.25, peak * full)


def audio_analysis(
    y: np.ndarray, fps: int = FPS, thresholds: Optional[Sequence[float]] = None, smooth: bool = True
) -> List[int]:
    """Volume class per frame: 0 = mouth closed, 1 = half open, 2 = open."""
    rms = frame_rms(y, fps)
    t1, t2 = thresholds or relative_thresholds(rms)
    volume_class = np.where(rms < t1, 0, np.where(rms < t2, 1, 2))
    if smooth and len(volume_class) >= 3:
        padded = np.pad(volume_class, 1, mode="edge")
        volume_class = np.median(np.stack([padded[:-2], padded[1:-1], padded[2:]]), axis=0).astype(int)
    return [int(v) for v in volume_class]
