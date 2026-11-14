"""The cogs, driven with fake Vector messages (no network)."""

import pytest

from conftest import FakeChat, FakeImages, FakeSpeech
from kitsune.channels import matches
from kitsune.errors import ChatError, ImageError

pytest.importorskip("vector")
pytestmark = pytest.mark.bot


class Typing:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class Channel:
    def __init__(self, name, id="chan1"):
        self.name, self.id = name, id

    def typing(self):
        return Typing()


class User:
    def __init__(self, id="u1", name="Lucky", bot=False):
        self.id, self.name, self.display_name, self.bot = id, name, name, bot

    def mentioned_in(self, message):
        return f"@{self.name}" in message.content


class Message:
    def __init__(self, content, channel, author=None):
        self.content, self.channel, self.author = content, channel, author or User()
        self.replies = []

    async def reply(self, content=None, **kw):
        self.replies.append((content, kw))


@pytest.fixture
def bot(config, happy):
    from kitsune.app import KitsuneBot
    from kitsune.avatar import SpriteBank
    from kitsune.services import Services
    from kitsune.storage import ConversationStore

    svc = Services(
        config=config,
        chat=FakeChat(),
        emotion=happy,
        store=ConversationStore(":memory:"),
        sprites=SpriteBank(config.sprites_dir, size=64),
        speech=FakeSpeech(),
        images=FakeImages(),
    )
    b = KitsuneBot(svc)
    b._user = User("kitsune", "Kitsune", bot=True)  # what the client sets on login
    return b


def cogs(bot):
    from kitsune.cogs.chat import Chat
    from kitsune.cogs.images import Images

    return Chat(bot), Images(bot)


def test_channel_matching():
    assert matches(Channel("🤖┊Kitsune Bot"), ["kitsune bot"])
    assert matches(Channel("anything", id="abc"), ["ABC"])
    assert not matches(Channel("☕┊General"), ["kitsune bot"])


async def test_chat_channel_reply_has_video(bot):
    chat, _ = cogs(bot)
    msg = Message("hey kitsune", Channel("🤖┊Kitsune Bot"))
    await chat.on_message(msg)
    text, kw = msg.replies[0]
    assert text is None and kw["file"].filename == "kitsune.mp4"  # video only, like Neku


async def test_ignores_other_channels_bots_and_commands(bot):
    chat, images = cogs(bot)
    for m in (
        Message("hi", Channel("☕┊General")),
        Message("!help", Channel("🤖┊Kitsune Bot")),
        Message("hi", Channel("🤖┊Kitsune Bot"), author=User(bot=True)),
    ):
        await chat.on_message(m)
        await images.on_message(m)
        assert m.replies == []


async def test_mention_anywhere(bot):
    chat, _ = cogs(bot)
    msg = Message("@Kitsune what should I watch?", Channel("☕┊General"))
    await chat.on_message(msg)
    assert msg.replies


async def test_ollama_down_is_friendly(bot):
    bot.pipeline.chat = FakeChat(error=ChatError("refused"))
    chat, _ = cogs(bot)
    msg = Message("hi", Channel("🤖┊Kitsune Bot"))
    await chat.on_message(msg)
    assert "offline" in msg.replies[0][0]


async def test_image_channel_draws(bot):
    _, images = cogs(bot)
    msg = Message("1girl, fox ears, red hair", Channel("🖼️┊Anime Image Generator", id="img"))
    await images.on_message(msg)
    text, kw = msg.replies[0]
    assert "fox ears" in text and len(kw["files"]) == 1
    assert bot.services.images.prompts == ["1girl, fox ears, red hair"]


async def test_image_errors_and_missing_token(bot):
    _, images = cogs(bot)
    bot.services.images = FakeImages(error=ImageError("Insufficient Anlas"))
    msg = Message("1girl", Channel("🖼️┊Anime Image Generator"))
    await images.on_message(msg)
    assert "Anlas" in msg.replies[0][0]
    bot.services.images = None
    msg = Message("1girl", Channel("🖼️┊Anime Image Generator"))
    await images.on_message(msg)
    assert "NOVELAI_TOKEN" in msg.replies[0][0]


async def test_setup_hook_loads_cogs(bot):
    await bot.setup_hook()
    assert {"Chat", "Images", "Utility"} <= set(bot.cogs)
    assert {"kitsune", "imagine", "forget", "mood", "help"} <= {c.name for c in bot.commands}
