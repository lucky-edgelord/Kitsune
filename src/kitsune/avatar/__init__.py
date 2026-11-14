"""Kitsune's talking avatar: Neku's pipeline (``fgk_neku.py``) ported to the Fox Mafia sprites."""

from .lipsync import FPS, NEKU_THRESHOLDS, audio_analysis, load_audio
from .renderer import AvatarRenderer, Segment, merge_mp3s
from .sprites import FRAME_NAMES, LOOP, SpriteBank
from .subtitles import format_timedelta, get_duration_ffprobe, split_lines, write_srt_file

__all__ = [
    "AvatarRenderer",
    "FPS",
    "FRAME_NAMES",
    "LOOP",
    "NEKU_THRESHOLDS",
    "Segment",
    "SpriteBank",
    "audio_analysis",
    "format_timedelta",
    "get_duration_ffprobe",
    "load_audio",
    "merge_mp3s",
    "split_lines",
    "write_srt_file",
]
