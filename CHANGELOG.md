# Changelog

## 0.2.0
- Restructured into a `src/` package with swappable providers (LLM, speech, images, emotion) behind Protocols.
- `ReplyPipeline` (think → feel → speak → animate) separated from the Vector bot; features are cogs.
- CLI: `kitsune run | check | render`.
- Square 256×256 talking video by default (`KITSUNE_VIDEO_SIZE`).
- Tests per module, CI (ruff + pytest), Dockerfile and docker-compose with Ollama.

## 0.1.0
- First version: Ollama chat, DistilBERT moods, NovelAI voice and images, lip-synced Fox Mafia avatar.
