# Changelog

## 0.4.1
- Replies are split into spoken lines/subtitles with NLTK's Punkt sentence model instead of a punctuation regex
  ("Mr. Smith", "e.g." and "3.5" no longer break a line). The `punkt_tab` data is downloaded once at startup (baked into
  the Docker image); if it can't be had, a warning is logged and the old punctuation split is used. `kitsune check`
  reports it.

## 0.4.0
- Per-user context in SQLite with compaction into a rolling memory after 8 exchanges (last 2 kept verbatim).
- 👍/👎 on every talking video, stored with the prompt, reply and mood for future logs/training.
- Her mood as a reaction on the user's message. A fuller main prompt. `!memory`.
- Replies to her videos give her the line being answered as context.
- Her Vector profile (name Kitsune, about text, avatar) is applied at startup.
- NovelAI TTS retries server errors and limits parallel requests.

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
