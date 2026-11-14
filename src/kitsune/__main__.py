"""Command line: ``kitsune run`` (the bot), ``kitsune render`` (a clip, no Vector needed), ``kitsune check``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from .config import Config
from .errors import KitsuneError
from .moods import Mood


def _render(args: argparse.Namespace, config: Config) -> int:
    from .avatar import AvatarRenderer, SpriteBank

    renderer = AvatarRenderer(SpriteBank(config.sprites_dir, size=args.size or config.video_size))
    if args.audio:
        audio = open(args.audio, "rb").read()
    else:
        from .providers.speech import NovelAISpeech

        speech = NovelAISpeech(config.novelai_token, voice_seed=config.voice_seed)
        audio = asyncio.run(speech.synthesize(args.text))
    mood = Mood.parse(args.mood)
    if args.mood == "auto":
        from .providers.emotion import DistilBertEmotion

        mood = DistilBertEmotion(config.emotion_model).detect_sync(args.text or "")
    with open(args.output, "wb") as f:
        f.write(renderer.render(audio, mood))
    print(f"wrote {args.output} ({mood.value})")
    return 0


def _check(config: Config) -> int:
    import httpx

    ok = True

    def line(good: bool, what: str) -> None:
        nonlocal ok
        ok &= good
        print(("✅ " if good else "❌ ") + what)

    line(bool(config.nsec), "VECTOR_NSEC set")
    try:
        r = httpx.get(
            f"{config.ollama_host}/api/tags",
            timeout=5,
            headers={"Authorization": f"Bearer {config.ollama_api_key}"} if config.ollama_api_key else {},
        )
        models = [m.get("name", "") for m in r.json().get("models", [])]
        line(r.status_code == 200, f"Ollama reachable at {config.ollama_host}")
        line(
            any(m.split(":")[0] == config.ollama_model.split(":")[0] for m in models),
            f"model {config.ollama_model} available",
        )
    except Exception as e:
        line(False, f"Ollama reachable at {config.ollama_host} ({e})")
    line(bool(config.novelai_token), "NOVELAI_TOKEN set (voice, video and images)")
    try:
        import transformers  # noqa: F401

        line(True, "emotion model support installed")
    except ImportError:
        print("⚠️  transformers not installed: install the [emotion] extra for moods")
    from shutil import which

    line(which("ffmpeg") is not None, "ffmpeg installed")
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kitsune", description="Kitsune, the talking fox-girl bot for Vector")
    parser.add_argument("--env", default=".env", help="dotenv file to load (default: .env)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="run the bot (default)")
    sub.add_parser("check", help="check configuration and connectivity")
    r = sub.add_parser("render", help="render a talking clip to a file")
    r.add_argument("text", nargs="?", default="", help="what she says (spoken with NovelAI TTS)")
    r.add_argument("--audio", help="use this audio file instead of TTS")
    r.add_argument("--mood", default="auto", help="happy, mad, neutral, sad, shy, or auto (default)")
    r.add_argument("--size", type=int, default=0)
    r.add_argument("-o", "--output", default="kitsune.mp4")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    config = Config.from_env(args.env)
    try:
        if args.cmd == "check":
            return _check(config)
        if args.cmd == "render":
            if not args.audio and not args.text:
                parser.error("render needs TEXT or --audio")
            return _render(args, config)
        from .app import run

        run(config)
        return 0
    except KitsuneError as e:
        print(f"kitsune: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
