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
    def __init__(self, name, id=None):
        self.name, self.id, self.sent = name, id or name, []
        self.mention = f"#{name}"

    def typing(self):
        return Typing()

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))


BOT_CH = Channel("🤖┊Kitsune Bot")
ART_CH = Channel("🖼️┊Anime Image Generator")
GENERAL = Channel("☕┊General")


class Community:
    text_channels = [GENERAL, BOT_CH, ART_CH]


class User:
    def __init__(self, id="u1", name="Lucky", bot=False):
        self.id, self.name, self.display_name, self.bot = id, name, name, bot

    @property
    def mention(self):
        return f"@{self.name}"

    def mentioned_in(self, message):
        return f"@{self.name}" in message.content


class Message:
    def __init__(self, content, channel, author=None):
        self.content, self.channel, self.author = content, channel, author or User()
        self.guild = Community()
        self.replies = []

    async def reply(self, content=None, **kw):
        self.replies.append((content, kw))


@pytest.fixture(autouse=True)
def clean_channels():
    for ch in (BOT_CH, ART_CH, GENERAL):
        ch.sent.clear()


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
    msg = Message("hey kitsune", BOT_CH)
    await chat.on_message(msg)
    text, kw = msg.replies[0]
    assert text is None and kw["file"].filename == "kitsune.mp4"  # video only, like Neku


async def test_ignores_every_other_channel(bot):
    chat, images = cogs(bot)
    for m in (
        Message("hi", GENERAL),
        Message("@Kitsune hi", GENERAL),
        Message("1girl, fox ears", GENERAL),
        Message("!help", BOT_CH),
        Message("hi", BOT_CH, author=User(bot=True)),
    ):
        await chat.on_message(m)
        await images.on_message(m)
        assert m.replies == []
    assert BOT_CH.sent == ART_CH.sent == GENERAL.sent == []


async def test_commands_only_in_her_channels(bot):
    await bot.setup_hook()
    called = []

    async def fake_super(message):
        called.append(message.content)

    import vector.ext.commands as c

    original = c.Bot.process_commands
    c.Bot.process_commands = lambda self, m: fake_super(m)
    try:
        for ch in (GENERAL, BOT_CH, ART_CH):
            await bot.process_commands(Message("!image cat", ch))
    finally:
        c.Bot.process_commands = original
    assert called == ["!image cat", "!image cat"]  # general ignored before parsing


async def test_cog_checks_split_the_channels(bot):
    from kitsune.cogs.chat import Chat
    from kitsune.cogs.images import Images

    class Ctx:
        def __init__(self, channel):
            self.channel = channel

    chat, images = Chat(bot), Images(bot)
    assert await chat.cog_check(Ctx(BOT_CH)) and not await chat.cog_check(Ctx(ART_CH))
    assert await images.cog_check(Ctx(ART_CH)) and not await images.cog_check(Ctx(BOT_CH))
    assert not await chat.cog_check(Ctx(GENERAL)) and not await images.cog_check(Ctx(GENERAL))


async def test_ollama_down_is_friendly(bot):
    bot.pipeline.chat = FakeChat(error=ChatError("refused"))
    chat, _ = cogs(bot)
    msg = Message("hi", BOT_CH)
    await chat.on_message(msg)
    assert "offline" in msg.replies[0][0]


async def test_image_channel_draws(bot):
    _, images = cogs(bot)
    for text in ("1girl, fox ears, red hair",):
        msg = Message(text, ART_CH)
        await images.on_message(msg)
        reply, kw = msg.replies[0]
        assert "fox ears" in reply and len(kw["files"]) == 1
    msg = Message("!image 1girl, kitsune", ART_CH)
    await images.draw(msg, "1girl, kitsune")
    assert len(msg.replies[0][1]["files"]) == 1
    assert bot.services.images.prompts == ["1girl, fox ears, red hair", "1girl, kitsune"]


async def test_image_errors_and_missing_token(bot):
    _, images = cogs(bot)
    bot.services.images = FakeImages(error=ImageError("Insufficient Anlas"))
    msg = Message("1girl", ART_CH)
    await images.on_message(msg)
    assert "Anlas" in msg.replies[0][0]
    bot.services.images = None
    msg = Message("1girl", ART_CH)
    await images.on_message(msg)
    assert "NOVELAI_TOKEN" in msg.replies[0][0]


async def test_setup_hook_loads_cogs(bot):
    await bot.setup_hook()
    assert {"Chat", "Images", "Utility"} <= set(bot.cogs)
    assert {"kitsune", "image", "forget", "mood", "help"} <= {c.name for c in bot.commands}
