"""Kitsune's talking avatar: sprite sets, lip-sync timing and the video renderer."""

from .lipsync import FPS, SAMPLE_RATE, blink_track, decode_audio, mouth_track
from .renderer import AvatarRenderer
from .sprites import FRAME_NAMES, SpriteBank

__all__ = [
    "AvatarRenderer",
    "FPS",
    "FRAME_NAMES",
    "SAMPLE_RATE",
    "SpriteBank",
    "blink_track",
    "decode_audio",
    "mouth_track",
]
