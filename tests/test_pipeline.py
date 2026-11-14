import pytest

from conftest import SPRITES, FakeChat, FakeSpeech
from kitsune.avatar import AvatarRenderer, SpriteBank
from kitsune.errors import ChatError, SpeechError
from kitsune.moods import Mood
from kitsune.pipeline import ReplyPipeline
from kitsune.storage import ConversationStore


def make(happy, chat=None, speech=None, talk=True, **kw):
    return ReplyPipeline(
        persona="You are Kitsune.",
        chat=chat or FakeChat(),
        emotion=happy,
        store=ConversationStore(":memory:"),
        speech=speech or (FakeSpeech() if talk else None),
        avatar=AvatarRenderer(SpriteBank(SPRITES, size=64)) if talk else None,
        **kw,
    )


class ScriptedChat(FakeChat):
    """Answers chats with 'reply N', and compaction requests with a summary."""

    def __init__(self):
        super().__init__()
        self.n = 0

    async def chat(self, messages):
        self.calls.append(messages)
        if messages[0]["role"] == "user" and "long-term memory" in messages[0]["content"]:
            return "Lucky loves Frieren; Kitsune recommended Dandadan."
        self.n += 1
        return f"reply {self.n}"


async def test_full_reply_has_text_mood_and_video(happy):
    p = make(happy)
    r = await p.reply("u1", "Lucky", "did you watch it?")
    assert r.text == "Hah, of course I watched it!" and r.mood is Mood.HAPPY
    assert r.video and r.video[4:8] == b"ftyp" and r.warning is None
    assert p.speech.texts == ["Hah, of course I watched it!"]  # one TTS call per line
    system = p.chat.calls[0][0]
    assert system["role"] == "system" and "Kitsune" in system["content"] and "Lucky" in system["content"]


async def test_each_user_has_their_own_context(happy):
    p = make(happy, chat=ScriptedChat(), talk=False)
    await p.reply("u1", "Lucky", "hi from lucky")
    await p.reply("u2", "Neo", "hi from neo")
    await p.reply("u1", "Lucky", "again")
    seen = [m["content"] for m in p.chat.calls[-1][1:]]
    assert seen == ["hi from lucky", "reply 1", "again"]


async def test_compacts_after_eight_exchanges(happy):
    p = make(happy, chat=ScriptedChat(), talk=False, compact_after=8, keep_recent=2)
    for i in range(8):
        await p.reply("u1", "Lucky", f"message {i}")
    await p.drain()
    ctx = p.store.context("u1")
    assert ctx.summary.startswith("Lucky loves Frieren")
    assert [m["content"] for m in ctx.turns if m["role"] == "user"] == ["message 6", "message 7"]
    compaction = p.chat.calls[-1][0]["content"]
    assert "Lucky: message 0" in compaction and "Kitsune: reply 1" in compaction and "message 6" not in compaction
    await p.reply("u1", "Lucky", "remember me?")
    system = p.chat.calls[-1][0]["content"]
    assert "What you remember about Lucky" in system and "Frieren" in system
    assert len(p.chat.calls[-1]) == 1 + 4 + 1  # system + 2 kept exchanges + new message


async def test_no_compaction_before_eight(happy):
    p = make(happy, chat=ScriptedChat(), talk=False)
    for i in range(7):
        await p.reply("u1", "Lucky", f"m{i}")
    await p.drain()
    assert p.store.memory("u1") == "" and p.store.context("u1").exchanges == 7


async def test_speech_failure_keeps_the_text(happy):
    p = make(happy, speech=FakeSpeech(error=SpeechError("no anlas")))
    r = await p.reply("u", "L", "hi")
    assert r.text and r.video is None and "no anlas" in r.warning


async def test_text_only_without_speech(happy):
    r = await make(happy, talk=False).reply("u", "L", "hi")
    assert r.text and r.video is None and r.warning is None


async def test_chat_failure_propagates_and_is_not_remembered(happy):
    p = make(happy, chat=FakeChat(error=ChatError("down")))
    with pytest.raises(ChatError):
        await p.reply("u", "L", "hi")
    assert p.store.context("u").turns == []


async def test_do_tts_makes_neku_segments(happy):
    p = make(happy)
    segs = await p.do_tts("Hi kit! Watch Frieren.")
    assert [s["text"] for s in segs] == ["Hi kit!", "Watch Frieren."] and all(s["audio"] for s in segs)
