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

## Lip-sync

The voice is decoded to 16 kHz mono and split into one window per video frame (24 fps). A frame's mouth is open when
its RMS loudness is above 35% of the clip's 90th-percentile loudness. Switching state needs a two-frame hold (so it
flaps rather than flickers), and long open runs close for a frame every seven frames so it reads as syllables.
Blinks last three frames, every 2.5–5 seconds.
