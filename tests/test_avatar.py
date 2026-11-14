import json
import random
import subprocess

import numpy as np
import pytest

from conftest import SPRITES, speech_audio
from kitsune.avatar import AvatarRenderer, SpriteBank, blink_track, decode_audio, mouth_track
from kitsune.avatar.sprites import FRAME_NAMES
from kitsune.errors import RenderError
from kitsune.moods import Mood


def test_every_mood_has_all_frames():
    bank = SpriteBank(SPRITES, size=64)
    assert set(bank.moods()) == set(Mood)
    for mood in Mood:
        frames = bank.frames(mood)
        assert len(frames) == len(FRAME_NAMES) and frames[0].shape == (64, 64, 3)


def test_mouth_follows_the_voice():
    mouth = mouth_track(decode_audio(speech_audio()))
    assert 0.2 < sum(mouth) / len(mouth) < 0.8
    assert not any(mouth_track(np.zeros(16000, dtype=np.float32)))


def test_mouth_never_flickers_single_frames():
    mouth = mouth_track(decode_audio(speech_audio(3)))
    runs, cur = [], 1
    for a, b in zip(mouth, mouth[1:]):
        cur = cur + 1 if a == b else (runs.append(cur) or 1)
    assert min(runs) >= 1 and sum(r == 1 for r in runs) <= len(runs) // 3


def test_blinks_every_few_seconds():
    blinks = blink_track(24 * 10, rng=random.Random(1))
    starts = sum(1 for i, b in enumerate(blinks) if b and (i == 0 or not blinks[i - 1]))
    assert 2 <= starts <= 5


def test_renders_square_mp4_with_audio():
    mp4 = AvatarRenderer(SpriteBank(SPRITES, size=256)).render(speech_audio(), Mood.MAD, seed=1)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", "-i", "pipe:0"],
        input=mp4,
        capture_output=True,
    ).stdout
    streams = json.loads(probe)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    assert [(s["width"], s["height"]) for s in streams if s["codec_type"] == "video"] == [(256, 256)]


def test_bad_audio_is_a_render_error():
    with pytest.raises(RenderError):
        decode_audio(b"not audio")
