# Changelog

## 0.3.0
- `!image <prompt>`. Kitsune ignores every channel except her chat channel (videos) and image channel (art).
- The avatar is now a port of Neku's pipeline: per-sentence TTS segments, ffprobe-timed SRT, sox/ffmpeg merge,
  16 fps volume classes and the `grid[class][i % 32]` frame grid, with burned-in subtitles. Replies are video only.
- Lip-sync: the smoother 24 fps mouth/blink tracks are the default; `KITSUNE_LIPSYNC=neku` uses Neku's 16 fps classes.
- Voice Aurae, 512×512 by default, bold readable subtitles.
- Fix: replies used the old renderer, so live videos had no subtitles.

## 0.2.0
- Restructured into a `src/` package with swappable providers (LLM, speech, images, emotion) behind Protocols.
- `ReplyPipeline` (think → feel → speak → animate) separated from the Vector bot; features are cogs.
- CLI: `kitsune run | check | render`.
- Square 256×256 talking video by default (`KITSUNE_VIDEO_SIZE`).
- Tests per module, CI (ruff + pytest), Dockerfile and docker-compose with Ollama.

## 0.1.0
- First version: Ollama chat, DistilBERT moods, NovelAI voice and images, lip-synced Fox Mafia avatar.
