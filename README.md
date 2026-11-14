# 🦊 Kitsune

A talking fox-girl bot for the Anime community on [Vector](https://vectorapp.io), built on
[vector-sdk-py](https://github.com/lucky-edgelord/vector-sdk-py). Kitsune is the successor to Neku: she chats
through **Ollama**, speaks with **NovelAI** text-to-speech, and replies with a short **lip-synced video** of her Fox
Mafia avatar. Her expression is picked by a **DistilBERT emotion** model. She also generates anime art with
**NovelAI** image generation.

![Kitsune talking](docs/talking.png)

![Her five moods: happy, mad, neutral, sad, shy](docs/moods.png)

## How a reply is made

1. Your message and recent history (per user, per channel, in SQLite) go to Ollama with Kitsune's persona
   ([kitsune/persona.md](kitsune/persona.md)).
2. [`bhadresh-savani/distilbert-base-uncased-emotion`](https://huggingface.co/bhadresh-savani/distilbert-base-uncased-emotion)
   reads her reply: joy/surprise → happy, anger → mad, sadness/fear → sad, love → shy, low confidence → neutral.
3. NovelAI TTS v2 voices the reply.
4. The avatar renderer picks that mood's four frames (eyes open/blinking × mouth closed/talking), opens the mouth
   with the voice's loudness, blinks every few seconds, and encodes a square MP4 (256×256 by default) with ffmpeg.
5. She replies with the text plus the video. Without a NovelAI token she replies with text only.

## Channels and commands

| Where | What happens |
|---|---|
| **🤖┊Kitsune Bot** | Just talk; she answers every message |
| **🖼️┊Anime Image Generator** | Type Danbooru-style tags; she draws them |
| anywhere | `!kitsune <message>` (or mention her) · `!imagine <tags>` |
| | `!forget` clears your chat history · `!mood <happy\|mad\|neutral\|sad\|shy>` · `!help` |

Channels are matched by name (or id), so they keep working if you rename the emoji part.

## Setup

Needs Python 3.10+, ffmpeg, the Rust toolchain (vector-sdk-py builds its native module), an Ollama server, and a
NovelAI subscription.

```bash
git clone https://github.com/lucky-edgelord/Kitsune && cd Kitsune
python -m venv .venv && . .venv/bin/activate
pip install -e ".[emotion]"          # drop [emotion] to skip torch; she'll always look neutral
ollama pull llama3.1                 # or any chat model; set OLLAMA_MODEL
cp .env.example .env                 # fill in VECTOR_NSEC, NOVELAI_TOKEN, ...
python -m kitsune                    # or: kitsune
```

Give Kitsune her **own** Vector account (a fresh nsec) and invite it to the Anime community.

| Setting | Default | |
|---|---|---|
| `VECTOR_NSEC` | (required) | Kitsune's Vector key |
| `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_API_KEY` | `http://localhost:11434`, `llama3.1`, none | key only for ollama.com |
| `NOVELAI_TOKEN` | none | persistent API token; enables voice, video and images |
| `NOVELAI_VOICE_SEED` | `Aini` | any TTS v2 voice or seed (`seedmix:` works) |
| `NOVELAI_IMAGE_MODEL`, `NOVELAI_IMAGE_SIZE` | `nai-diffusion-4-5-full`, `portrait` | |
| `KITSUNE_CHAT_CHANNELS`, `KITSUNE_IMAGE_CHANNELS` | `kitsune bot`, `anime image generator` | name substrings or ids |
| `KITSUNE_VIDEO_SIZE` | `256` | square video size (Neku used 480) |
| `KITSUNE_TALKING_VIDEO` | `true` | `false` for text-only replies |
| `KITSUNE_PREFIX`, `KITSUNE_DATA_DIR` | `!`, `./data` | |

## Layout

```
kitsune/bot.py      Vector bot: channels, commands, reply pipeline
kitsune/llm.py      Ollama chat client
kitsune/emotion.py  DistilBERT emotion -> sprite mood
kitsune/novelai.py  NovelAI TTS (api.novelai.net) and images (novelai-sdk)
kitsune/avatar.py   lip-sync + blink renderer (numpy, Pillow, ffmpeg)
kitsune/memory.py   per-user chat history (SQLite)
assets/sprites/     Fox Mafia sprites: <mood>/{open,blink}_{closed,talk}.png
```

Tests: `pip install -e ".[dev]" && pytest`.

Kitsune is a community project and is not affiliated with Vector, NovelAI, Ollama or Hugging Face.
