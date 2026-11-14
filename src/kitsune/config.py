"""Settings, read from the environment (and a ``.env`` file in the working directory, if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _list(name: str, default: str) -> List[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass
class Config:
    # Vector
    nsec: str = ""
    prefix: str = "!"
    data_dir: str = "./data"
    # channels are matched by name (substring, case-insensitive) or exact id
    chat_channels: List[str] = field(default_factory=lambda: ["kitsune bot"])
    image_channels: List[str] = field(default_factory=lambda: ["anime image generator"])
    # Ollama (local by default; set OLLAMA_API_KEY for ollama.com cloud)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_api_key: str = ""
    compact_after: int = 8  # summarise a user's context into memory after this many exchanges
    keep_recent: int = 2  # exchanges kept verbatim after compacting
    # NovelAI
    novelai_token: str = ""
    voice_seed: str = "Aurae"
    image_model: str = "nai-diffusion-4-5-full"
    image_size: str = "portrait"
    # behaviour
    video_size: int = 512  # square talking video
    lipsync: str = "smooth"  # smooth (24 fps, default) or neku (16 fps, 3 mouth levels)
    subtitles: bool = True  # burn the reply into the video as subtitles, like Neku
    talking_video: bool = True  # reply with a lip-synced video (False: text only)
    emotion_model: str = "bhadresh-savani/distilbert-base-uncased-emotion"
    persona_file: str = str(PACKAGE_DIR / "persona" / "kitsune.md")
    sprites_dir: str = str(PACKAGE_DIR / "assets" / "sprites")
    # her Vector profile, applied at startup when it differs (KITSUNE_SET_PROFILE=false to leave it alone)
    set_profile: bool = True
    display_name: str = "Kitsune"
    about: str = "🦊 The Fox Mafia's anime fox-girl. Talk to me in Kitsune Bot, make art in Anime Image Generator."
    avatar_file: str = str(PACKAGE_DIR / "assets" / "avatar.png")
    emotion_threshold: float = 0.45
    max_concurrent_renders: int = 2

    @classmethod
    def from_env(cls, dotenv: str = ".env") -> Config:
        _load_dotenv(dotenv)
        c = cls()
        c.nsec = os.getenv("VECTOR_NSEC", "")
        c.prefix = os.getenv("KITSUNE_PREFIX", c.prefix)
        c.data_dir = os.getenv("KITSUNE_DATA_DIR", c.data_dir)
        c.chat_channels = _list("KITSUNE_CHAT_CHANNELS", ",".join(c.chat_channels))
        c.image_channels = _list("KITSUNE_IMAGE_CHANNELS", ",".join(c.image_channels))
        c.ollama_host = os.getenv("OLLAMA_HOST", c.ollama_host).rstrip("/")
        c.ollama_model = os.getenv("OLLAMA_MODEL", c.ollama_model)
        c.ollama_api_key = os.getenv("OLLAMA_API_KEY", "")
        c.compact_after = int(os.getenv("KITSUNE_COMPACT_AFTER", c.compact_after))
        c.keep_recent = int(os.getenv("KITSUNE_KEEP_RECENT", c.keep_recent))
        c.novelai_token = os.getenv("NOVELAI_TOKEN", "")
        c.voice_seed = os.getenv("NOVELAI_VOICE_SEED", c.voice_seed)
        c.image_model = os.getenv("NOVELAI_IMAGE_MODEL", c.image_model)
        c.image_size = os.getenv("NOVELAI_IMAGE_SIZE", c.image_size)
        c.video_size = int(os.getenv("KITSUNE_VIDEO_SIZE", c.video_size))
        c.lipsync = os.getenv("KITSUNE_LIPSYNC", c.lipsync)
        c.subtitles = _bool("KITSUNE_SUBTITLES", c.subtitles)
        c.talking_video = _bool("KITSUNE_TALKING_VIDEO", c.talking_video)
        c.emotion_model = os.getenv("KITSUNE_EMOTION_MODEL", c.emotion_model)
        c.persona_file = os.getenv("KITSUNE_PERSONA_FILE", c.persona_file)
        c.sprites_dir = os.getenv("KITSUNE_SPRITES_DIR", c.sprites_dir)
        c.set_profile = _bool("KITSUNE_SET_PROFILE", c.set_profile)
        c.display_name = os.getenv("KITSUNE_NAME", c.display_name)
        c.about = os.getenv("KITSUNE_ABOUT", c.about)
        c.avatar_file = os.getenv("KITSUNE_AVATAR", c.avatar_file)
        c.emotion_threshold = float(os.getenv("KITSUNE_EMOTION_THRESHOLD", c.emotion_threshold))
        c.max_concurrent_renders = int(os.getenv("KITSUNE_MAX_CONCURRENT", c.max_concurrent_renders))
        return c

    @property
    def has_novelai(self) -> bool:
        return bool(self.novelai_token)

    def validate(self) -> None:
        from .errors import ConfigError

        if not self.nsec:
            raise ConfigError("VECTOR_NSEC is not set (Kitsune's Vector key, in .env or the environment)")
        if self.video_size < 64 or self.video_size > 1024:
            raise ConfigError("KITSUNE_VIDEO_SIZE must be between 64 and 1024")
