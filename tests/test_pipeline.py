import pytest

from conftest import SPRITES, FakeChat, FakeSpeech
from kitsune.avatar import AvatarRenderer, SpriteBank
from kitsune.errors import ChatError, SpeechError
from kitsune.moods import Mood
from kitsune.pipeline import ReplyPipeline
from kitsune.storage import ConversationStore


def make(happy, chat=None, speech=None, talk=True):
    return ReplyPipeline(
        persona="You are Kitsune.",
        chat=chat or FakeChat(),
        emotion=happy,
        store=ConversationStore(":memory:"),
        speech=speech or (FakeSpeech() if talk else None),
        avatar=AvatarRenderer(SpriteBank(SPRITES, size=64)) if talk else None,
        history_turns=3,
    )


async def test_full_reply_has_text_mood_and_video(happy):
    p = make(happy)
    r = await p.reply("chan", "u1", "Lucky", "did you watch it?")
    assert r.text == "Hah, of course I watched it!" and r.mood is Mood.HAPPY
    assert r.video and r.video[4:8] == b"ftyp" and r.warning is None
    assert p.speech.texts == ["Hah, of course I watched it!"]  # one TTS call per line
    system = p.chat.calls[0][0]
    assert system["role"] == "system" and "Kitsune" in system["content"] and "Lucky" in system["content"]


async def test_history_is_sent_back(happy):
    p = make(happy, talk=False)
    await p.reply("c", "u", "L", "first")
    await p.reply("c", "u", "L", "second")
    msgs = p.chat.calls[-1]
    assert [m["content"] for m in msgs[1:]] == ["first", "Hah, of course I watched it!", "second"]


async def test_speech_failure_keeps_the_text(happy):
    p = make(happy, speech=FakeSpeech(error=SpeechError("no anlas")))
    r = await p.reply("c", "u", "L", "hi")
    assert r.text and r.video is None and "no anlas" in r.warning


async def test_text_only_without_speech(happy):
    r = await make(happy, talk=False).reply("c", "u", "L", "hi")
    assert r.text and r.video is None and r.warning is None


async def test_chat_failure_propagates_and_is_not_remembered(happy):
    p = make(happy, chat=FakeChat(error=ChatError("down")))
    with pytest.raises(ChatError):
        await p.reply("c", "u", "L", "hi")
    assert p.store.history("c", "u", 5) == []


async def test_do_tts_makes_neku_segments(happy):
    p = make(happy)
    segs = await p.do_tts("Hi kit! Watch Frieren.")
    assert [s["text"] for s in segs] == ["Hi kit!", "Watch Frieren."] and all(s["audio"] for s in segs)
