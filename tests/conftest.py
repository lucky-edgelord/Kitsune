import subprocess
from typing import List, Optional

import numpy as np
import pytest

from kitsune.config import PACKAGE_DIR, Config
from kitsune.moods import Mood

SPRITES = str(PACKAGE_DIR / "assets" / "sprites")


def speech_audio(seconds: float = 2.0) -> bytes:
    """Syllable-like bursts of a tone, as MP3: a stand-in for a voice line."""
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    sig = (0.3 * (np.sin(2 * np.pi * 3.5 * t) > 0.1) * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", "16000", "-ac", "1", "-i", "pipe:0", "-f", "mp3", "pipe:1"],
        input=sig.tobytes(),
        capture_output=True,
        check=True,
    ).stdout


class FakeChat:
    def __init__(self, reply: str = "Hah, of course I watched it!", error: Optional[Exception] = None):
        self.reply, self.error, self.calls = reply, error, []

    async def chat(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.reply

    async def aclose(self):
        pass


class FakeSpeech:
    def __init__(self, error: Optional[Exception] = None):
        self.error, self.texts = error, []

    async def synthesize(self, text):
        self.texts.append(text)
        if self.error:
            raise self.error
        return speech_audio(1.0)

    async def aclose(self):
        pass


class FakeImages:
    def __init__(self, error: Optional[Exception] = None):
        self.error, self.prompts = error, []

    async def generate(self, prompt, *, negative="", seed=None) -> List[bytes]:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return [b"\x89PNG fake"]

    async def aclose(self):
        pass


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(nsec="nsec1test", data_dir=str(tmp_path), novelai_token="pst-test", video_size=128)


@pytest.fixture
def happy():
    from kitsune.providers.emotion import FixedEmotion

    return FixedEmotion(Mood.HAPPY)
