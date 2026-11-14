# Architecture

```
Vector message
   │
   ▼
cogs/chat.py ──► ReplyPipeline.reply()                         (pipeline.py)
                   1. ConversationStore.history()               storage/memory.py   (SQLite)
                   2. ChatModel.chat()                          providers/llm       (Ollama)
                   3. EmotionDetector.detect()                  providers/emotion   (DistilBERT → Mood)
                   4. SpeechSynthesizer.synthesize()            providers/speech    (NovelAI TTS v2)
                   5. AvatarRenderer.render(audio, mood)        avatar/             (lip-sync + blink → MP4)
   ◄── Reply(text, mood, video)
cogs/images.py ──► ImageGenerator.generate()                   providers/images    (NovelAI via novelai-sdk)
```

* **`config.py`**: one dataclass, read from the environment / `.env`.
* **`services.py`**: builds every backend from the config. Pass your own objects to `Services(...)` to swap any.
* **`pipeline.py`**: knows nothing about Vector, so it can be reused (a CLI, another chat platform) and tested
  directly. Only an LLM failure is an error; speech and rendering failures fall back to a text reply.
* **`avatar/`**: `sprites.py` crops and composites each mood's four frames once; `lipsync.py` turns audio into
  per-frame mouth and blink tracks; `renderer.py` pipes raw frames and the voice into ffmpeg.
* **`app.py`**: `KitsuneBot` (a vector-sdk-py `commands.Bot`) loads the cogs in `setup_hook` and warms up the
  emotion model in the background.

## The avatar: Neku's pipeline, ported

`avatar/` is a port of Neku's `fgk_neku.py` (`FGKBot.avatar_waifu` and its helpers), with the same steps and names:

| Neku | Kitsune |
|---|---|
| Inworld returns `[{text, audio}]` per sentence | `ReplyPipeline.do_tts`: Ollama reply split into lines, each voiced by NovelAI (Aurae) |
| `merge_base64_mp3s_sox` + `get_duration_ffprobe` + `write_srt_file` | `avatar.merge_mp3s` (sox, or ffmpeg if sox is missing) + the same SRT helpers |
| `audio_analysis` (librosa RMS at 16 fps → 0/1/2) | default: `mouth_track` + `blink_track` at 24 fps (mouth follows syllables, random blinks); `KITSUNE_LIPSYNC=neku` keeps Neku's `audio_analysis` |
| `self.grid` from `vids/0-2.mp4`, `grid[A][i % 32]` | `SpriteBank.grid(mood)`: 3 × 32 frames from the mood's sprites, blink in the loop |
| `create_grid_video` (OpenCV) → ffmpeg mux → `add_vid_subs` | `AvatarRenderer.create_grid_video`: one ffmpeg pass for frames, audio and subtitles |
| `ctx.reply(file=miku.mp4)` | the chat cog replies with just the video |

What changed and why:
* **Per-render temp directories.** Neku wrote to a shared `crockpot/` and ran `rm crockpot/*`, so two people
  talking at once clobbered each other's files.
* **One encode instead of three**, no OpenCV, no librosa/numba: faster and much lighter to install.
* **Relative loudness thresholds.** Neku's 0.1 / 0.125 were tuned to Inworld's audio level; Kitsune's adapt to any
  voice (`NEKU_THRESHOLDS` is still available).
* **Moods.** DistilBERT picks which sprite set fills the grid.
* **Readable subtitles** for phones (bold, outlined, scaled to the video), and all blocking work runs off the event
  loop so the bot stays responsive while rendering.

## Context and memory

Everything is in one SQLite file (`<data_dir>/kitsune.db`):

| table | what |
|---|---|
| `turns` | every message, per user; `compacted = 1` once summarised (kept as logs, not sent to the model) |
| `memories` | one rolling summary per user |
| `replies` | each talking-video reply: message id, user, prompt, reply text, mood |
| `feedback` | 👍 (+1) / 👎 (-1) per rater per reply; `ConversationStore.feedback()` exports them joined with the replies |

The model sees: the main prompt (`persona/kitsune.md`), "what you remember about <name>" (their memory), their
uncompacted turns, and the new message. After a reply, if the user has `compact_after` (8) uncompacted exchanges,
a background task asks the model to fold all but the last `keep_recent` (2) into their memory. Each user's
exchanges are serialised with a per-user lock, so their context stays in order even if they send messages quickly.
