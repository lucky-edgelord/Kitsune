import asyncio
import json
import subprocess
from pathlib import Path

import httpx
import numpy as np
import pytest

from kitsune.avatar import Avatar
from kitsune.emotion import to_sprite
from kitsune.llm import Ollama, OllamaError
from kitsune.memory import Memory
from kitsune.novelai import NovelAI

SPRITES = str(Path(__file__).resolve().parent.parent / "assets" / "sprites")


def speech_mp3(seconds=2.0):
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    sig = (0.3 * (np.sin(2 * np.pi * 3.5 * t) > 0.1) * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    return subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", "16000", "-ac", "1", "-i", "pipe:0",
                           "-f", "mp3", "pipe:1"], input=sig.tobytes(), capture_output=True, check=True).stdout


def test_sprites_complete():
    for e in ("happy", "mad", "neutral", "sad", "shy"):
        for f in ("open_closed", "open_talk", "blink_closed", "blink_talk"):
            assert (Path(SPRITES) / e / f"{f}.png").is_file()


def test_emotion_mapping():
    assert to_sprite("joy", 0.9) == "happy"
    assert to_sprite("anger", 0.8) == "mad"
    assert to_sprite("love", 0.7) == "shy"
    assert to_sprite("sadness", 0.9) == "sad"
    assert to_sprite("joy", 0.2) == "neutral"


def test_mouth_follows_audio_and_blinks():
    a = Avatar(SPRITES)
    mouth = a.mouth_track(a.decode(speech_mp3()))
    assert 0.2 < sum(mouth) / len(mouth) < 0.8
    silent = a.mouth_track(np.zeros(16000, dtype=np.float32))
    assert not any(silent)
    import random
    blinks = a.blink_track(24 * 10, rng=random.Random(1))
    assert 2 <= sum(blinks) // 3 <= 5


def test_render_square_video(tmp_path):
    out = Avatar(SPRITES, size=256).render(speech_mp3(), "mad", str(tmp_path / "k.mp4"), seed=1)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                            "-of", "json", out], capture_output=True, text=True).stdout
    streams = json.loads(probe)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    assert [(s["width"], s["height"]) for s in streams if s["codec_type"] == "video"] == [(256, 256)]


def test_memory_roundtrip():
    m = Memory(":memory:")
    for i in range(5):
        m.add("c", "u", "user", f"q{i}")
        m.add("c", "u", "assistant", f"a{i}")
    h = m.history("c", "u", 2)
    assert [x["content"] for x in h] == ["q3", "a3", "q4", "a4"]
    assert m.forget("c", "u") == 10 and m.history("c", "u", 2) == []


async def test_ollama_chat_request():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content), path=req.url.path, auth=req.headers.get("authorization"))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": " Hi kit! "}})

    o = Ollama("http://x", "llama3.1", api_key="k")
    o.http = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer k"})
    assert await o.chat([{"role": "user", "content": "hi"}]) == "Hi kit!"
    assert seen["path"] == "/api/chat" and seen["model"] == "llama3.1" and seen["stream"] is False
    assert seen["auth"] == "Bearer k"
    o.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    with pytest.raises(OllamaError):
        await o.chat([{"role": "user", "content": "hi"}])


async def test_novelai_tts_request():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content), url=str(req.url))
        return httpx.Response(200, content=b"ID3fake")

    n = NovelAI("pst-x", voice_seed="Aini")
    n.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await n.tts("hello " * 300) == b"ID3fake"
    assert seen["url"] == "https://api.novelai.net/ai/generate-voice"
    assert seen["version"] == "v2" and seen["seed"] == "Aini" and len(seen["text"]) == 1000


class FakeChannel:
    id = "chan"
    name = "🤖┊Kitsune Bot"

    def __init__(self):
        self.sent = []

    def typing(self):
        class T:
            async def __aenter__(s): return s
            async def __aexit__(s, *a): return False
        return T()

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))


async def test_respond_flow(tmp_path, monkeypatch):
    from kitsune.bot import Kitsune
    from kitsune.config import Config

    cfg = Config(data_dir=str(tmp_path), novelai_token="pst-x", video_size=128)
    k = Kitsune(cfg)

    async def chat(messages):
        assert messages[0]["role"] == "system" and "Kitsune" in messages[0]["content"]
        return "Hah, of course I watched it!"

    async def tts(text, seed=None):
        return speech_mp3(1.0)

    async def classify(text):
        return "happy"

    monkeypatch.setattr(k.llm, "chat", chat)
    monkeypatch.setattr(k.nai, "tts", tts)
    monkeypatch.setattr(k.emotion, "classify", classify)
    ch = FakeChannel()
    await k.respond(ch, type("U", (), {"id": "u1", "name": "Lucky"})(), "did you watch it?")
    text, kw = ch.sent[-1]
    assert text == "Hah, of course I watched it!" and kw["file"].filename == "kitsune.mp4"
    assert k.memory.history("chan", "u1", 5)[-1]["content"] == text
