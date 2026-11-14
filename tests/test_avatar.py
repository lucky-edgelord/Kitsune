import json
import subprocess
from datetime import timedelta

import numpy as np
import pytest

from conftest import SPRITES, speech_audio
from kitsune.avatar import (
    LOOP,
    NEKU_THRESHOLDS,
    AvatarRenderer,
    SpriteBank,
    audio_analysis,
    blink_track,
    format_timedelta,
    load_audio,
    merge_mp3s,
    mouth_track,
    split_lines,
)
from kitsune.avatar.subtitles import srt_text
from kitsune.errors import RenderError
from kitsune.moods import Mood


def probe(mp4: bytes) -> dict:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            "-i",
            "pipe:0",
        ],
        input=mp4,
        capture_output=True,
    ).stdout
    return json.loads(out)


def test_grid_is_neku_shaped():
    bank = SpriteBank(SPRITES, size=64)
    assert set(bank.moods()) == set(Mood)
    for mood in Mood:
        grid = bank.grid(mood)
        assert len(grid) == 3 and all(len(row) == LOOP for row in grid)
        assert grid[0][0].shape == (64, 64, 3)
        assert not np.array_equal(grid[0][0], grid[2][0])  # closed vs open mouth
        assert not np.array_equal(grid[0][0], grid[0][25])  # a blink inside the loop


def test_audio_analysis_classes():
    classes = audio_analysis(load_audio(speech_audio()))
    assert set(classes) <= {0, 1, 2} and 0 in classes and 2 in classes
    assert set(audio_analysis(np.zeros(22050, dtype=np.float32))) == {0}
    quiet = load_audio(speech_audio()) * 0.05  # relative thresholds still animate a quiet voice
    assert 2 in audio_analysis(quiet) and set(audio_analysis(quiet, thresholds=NEKU_THRESHOLDS)) == {0}


def test_srt_like_neku():
    assert format_timedelta(timedelta(seconds=3661.25)) == "01:01:01,250"
    entries = [(1, timedelta(), timedelta(seconds=1.25), "Hi kit!")]
    assert srt_text(entries) == "1\n00:00:00,000 --> 00:00:01,250\nHi kit!\n\n"
    assert split_lines("Hi kit! Want a rec? Watch Frieren.") == ["Hi kit!", "Want a rec?", "Watch Frieren."]
    assert all(len(x) <= 80 for x in split_lines("word " * 40))


def test_merge_times_each_segment(tmp_path):
    segs = [{"text": "one", "audio": speech_audio(1.0)}, {"text": "two", "audio": speech_audio(1.5)}]
    entries = merge_mp3s(segs, str(tmp_path / "m.wav"), str(tmp_path / "s.srt"), str(tmp_path))
    assert [e[3] for e in entries] == ["one", "two"]
    assert abs(entries[1][1].total_seconds() - entries[0][2].total_seconds()) < 1e-6
    assert 2.3 < entries[1][2].total_seconds() < 2.8
    assert (tmp_path / "s.srt").read_text().startswith("1\n00:00:00,000 --> ")


def test_avatar_video_square_with_audio_and_subtitles():
    segs = [
        {"text": "Hi kit!", "audio": speech_audio(1.0)},
        {"text": "Watch Frieren tonight.", "audio": speech_audio(1.5)},
    ]
    r = AvatarRenderer(SpriteBank(SPRITES, size=256))
    with_subs = r.avatar_video(segs, Mood.HAPPY)
    info = probe(with_subs)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    assert [(s["width"], s["height"]) for s in info["streams"] if s["codec_type"] == "video"] == [(256, 256)]
    assert 2.3 < float(info["format"]["duration"]) < 2.9

    def frame(mp4):
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-vf",
            "select=eq(n\\,8)",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ]
        return np.frombuffer(subprocess.run(cmd, input=mp4, capture_output=True).stdout, np.uint8)

    a, b = frame(with_subs), frame(r.avatar_video(segs, Mood.HAPPY, subtitles=False))
    bottom = slice(len(a) * 3 // 4, len(a))
    assert np.abs(a[bottom].astype(int) - b[bottom].astype(int)).mean() > 1  # subtitles burned in


def test_errors():
    with pytest.raises(RenderError):
        load_audio(b"not audio")
    with pytest.raises(RenderError):
        AvatarRenderer(SpriteBank(SPRITES, size=64)).avatar_video([], Mood.HAPPY)


def test_smooth_lipsync_is_default_and_neku_is_optional():
    import random

    y = load_audio(speech_audio(3))
    mouth = mouth_track(y)
    assert 0.2 < sum(mouth) / len(mouth) < 0.8 and not any(mouth_track(np.zeros(22050, np.float32)))
    blinks = blink_track(24 * 10, rng=random.Random(1))
    assert 2 <= sum(1 for i, b in enumerate(blinks) if b and (i == 0 or not blinks[i - 1])) <= 5
    bank = SpriteBank(SPRITES, size=64)
    smooth_frames, smooth_fps = AvatarRenderer(bank).frames_for(y, Mood.SAD, seed=1)
    neku_frames, neku_fps = AvatarRenderer(bank, lipsync="neku").frames_for(y, Mood.SAD)
    assert (smooth_fps, neku_fps) == (24, 16)
    assert abs(len(smooth_frames) / 24 - len(neku_frames) / 16) < 0.2
