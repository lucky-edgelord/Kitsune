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


class Ref:
    def __init__(self, message_id, author_id=None, content=None):
        self.message_id, self.author_id, self.content, self.resolved = message_id, author_id, content, None


class Message:
    reference = None

    def __init__(self, content, channel, author=None, reference=None):
        self.content, self.channel, self.author = content, channel, author or User()
        self.reference = reference
        self.guild = Community()
        self.replies = []

    async def reply(self, content=None, **kw):
        self.replies.append((content, kw))
        sent = Message(content or "", self.channel, User("kitsune", "Kitsune", bot=True))
        sent.id = f"sent{len(self.replies)}"
        self.sent_replies = getattr(self, "sent_replies", []) + [sent]
        return sent

    id = "msg"

    async def add_reaction(self, emoji):
        self.reactions = getattr(self, "reactions", []) + [emoji]


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
    assert msg.reactions == ["😄"]  # her mood, on the user's message
    assert msg.sent_replies[0].reactions == ["👍", "👎"]  # feedback buttons on the video


async def test_thumbs_are_stored_as_feedback(bot):
    chat, _ = cogs(bot)
    msg = Message("recommend me something", BOT_CH)
    await chat.on_message(msg)
    video_id = msg.sent_replies[0].id

    class Payload:
        def __init__(self, emoji, user_id, message_id=video_id):
            self.emoji, self.user_id, self.message_id = emoji, user_id, message_id

    await chat.on_raw_reaction_add(Payload("👍", "kitsune"))  # her own reaction is not a vote
    await chat.on_raw_reaction_add(Payload("👍", "u1"))
    await chat.on_raw_reaction_add(Payload("👎", "u2"))
    await chat.on_raw_reaction_add(Payload("😄", "u3"))
    await chat.on_raw_reaction_add(Payload("👍", "u4", message_id="someone-elses-message"))
    rows = bot.pipeline.store.feedback()
    assert sorted((r["rater"], r["rating"]) for r in rows) == [("u1", 1), ("u2", -1)]
    assert rows[0]["prompt"] == "recommend me something" and rows[0]["mood"] == "happy"
    await chat.on_raw_reaction_remove(Payload("👎", "u2"))
    assert [(r["rater"], r["rating"]) for r in bot.pipeline.store.feedback()] == [("u1", 1)]


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
        _, kw = msg.replies[0]
        assert "fox ears" in kw["embed"].description and len(kw["files"]) == 1
        assert kw["embed"].image.url == "attachment://kitsune_0.png"
        assert [f.name for f in kw["embed"].fields] == ["Model", "Size", "Seed"]
        assert msg.sent_replies[0].reactions == ["❤️"]
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
    assert {"kitsune", "image", "forget", "memory", "mood", "help"} <= {c.name for c in bot.commands}


async def test_replies_to_her_include_what_she_said(bot):
    chat, _ = cogs(bot)
    first = Message("recommend me something", BOT_CH)
    await chat.on_message(first)
    video_id = first.sent_replies[0].id
    reply = Message("why that one?", BOT_CH, reference=Ref(video_id))
    await chat.on_message(reply)
    assert reply.sent_replies  # replies trigger her
    last_user_msg = bot.pipeline.chat.calls[-1][-1]["content"]
    assert 'Replying to what you said: "Hah, of course I watched it!"' in last_user_msg
    assert last_user_msg.endswith("why that one?")


async def test_reply_to_her_unlogged_message_uses_quoted_text(bot):
    chat, _ = cogs(bot)
    msg = Message("lol", BOT_CH, reference=Ref("old", author_id="kitsune", content="I'm the best fox"))
    await chat.on_message(msg)
    assert "I'm the best fox" in bot.pipeline.chat.calls[-1][-1]["content"]


async def test_reply_to_someone_else_is_just_a_message(bot):
    chat, _ = cogs(bot)
    msg = Message("agreed", BOT_CH, reference=Ref("x", author_id="u9", content="Naruto rules"))
    await chat.on_message(msg)
    assert bot.pipeline.chat.calls[-1][-1]["content"] == "agreed"
