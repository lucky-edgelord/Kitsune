"""Talking to Kitsune, only in her chat channel.

Every talking-video reply gets 👍 and 👎; votes are stored with the prompt, reply and mood (``feedback`` table).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import vector
from vector.ext import commands

from ..channels import is_chat
from ..errors import ChatError

log = logging.getLogger(__name__)

THUMBS = {"👍": 1, "👎": -1}


class Chat(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return is_chat(self.bot, ctx.channel)

    def replied_to_her(self, message: Any) -> Optional[str]:
        """If ``message`` replies to one of Kitsune's messages, what she said there ('' if unknown)."""
        ref = getattr(message, "reference", None)
        if ref is None or not getattr(ref, "message_id", None):
            return None
        me = str(getattr(self.bot.user, "id", ""))
        said = self.bot.pipeline.store.reply_text(str(ref.message_id))
        if said is not None:
            return said
        resolved = getattr(ref, "resolved", None)
        author = str(getattr(ref, "author_id", None) or getattr(getattr(resolved, "author", None), "id", ""))
        if me and author == me:
            return getattr(ref, "content", None) or getattr(resolved, "content", None) or ""
        return None

    async def talk(self, message: Any, text: str) -> None:
        bot = self.bot
        said = self.replied_to_her(message)
        if said:  # she knows which of her lines you're answering
            text = f'(Replying to what you said: "{said[:300]}")\n{text}'
        author = message.author
        name = getattr(author, "display_name", None) or getattr(author, "name", "someone")

        async def react(mood: Any) -> None:  # her mood, as a reaction on the user's message
            await message.add_reaction(mood.emoji)

        async with message.channel.typing():
            try:
                reply = await bot.pipeline.reply(
                    str(author.id),
                    name,
                    text,
                    channel=str(message.channel.id),
                    video=bot.config.talking_video,
                    on_mood=react,
                )
            except ChatError as e:
                log.warning("chat failed: %s", e)
                await message.reply("🦊 My brain's offline right now (can't reach Ollama). Try again in a bit.")
                return
        if not reply.text:
            return
        if reply.video:  # the words are in the subtitles, so the video goes alone (like Neku)
            sent = await message.reply(file=vector.File(reply.video, filename="kitsune.mp4"))
        else:
            sent = await message.reply(reply.text)
        if sent is not None and getattr(sent, "id", None):
            bot.pipeline.store.log_reply(
                str(sent.id), str(author.id), text, reply.text, reply.mood.value, channel=str(message.channel.id)
            )
            for emoji in THUMBS:
                try:
                    await sent.add_reaction(emoji)
                except Exception as e:  # reactions are a nicety, never a failure
                    log.debug("couldn't add %s: %s", emoji, e)

    # -- messages --------------------------------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: Any) -> None:
        bot = self.bot
        if message.author.bot or message.author == bot.user or not is_chat(bot, message.channel):
            return
        text = (message.content or "").strip()
        # in her channel every message reaches her, replies included (with the line they answer as context);
        # commands go to the command system
        if text and not text.startswith(bot.config.prefix):
            await self.talk(message, text)

    # -- feedback --------------------------------------------------------------------------------------------
    def _vote(self, payload: Any) -> Any:
        me = getattr(self.bot.user, "id", None)
        if payload.emoji not in THUMBS or str(payload.user_id) == str(me):
            return None
        return THUMBS[payload.emoji]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: Any) -> None:
        rating = self._vote(payload)
        if rating is not None and self.bot.pipeline.store.rate(str(payload.message_id), str(payload.user_id), rating):
            log.info("feedback %+d on %s from %s", rating, payload.message_id, payload.user_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: Any) -> None:
        rating = self._vote(payload)
        if rating is not None:
            self.bot.pipeline.store.unrate(str(payload.message_id), str(payload.user_id), rating)

    # -- commands --------------------------------------------------------------------------------------------
    @commands.command(name="kitsune", aliases=["kit", "k"])
    async def kitsune(self, ctx: commands.Context, *, text: str = "") -> None:
        """Talk to Kitsune."""
        if not text:
            await ctx.reply(f"Hm? Say something, kit. `{self.bot.config.prefix}kitsune <message>`")
            return
        await self.talk(ctx.message, text)

    @commands.command(name="forget", aliases=["reset"])
    async def forget(self, ctx: commands.Context) -> None:
        """Make Kitsune forget your conversation and her memory of you."""
        n = self.bot.pipeline.store.forget(str(ctx.author.id))
        await ctx.reply("🦊 Forgotten. Who are you again?" if n else "🦊 We haven't even talked yet, kit.")

    @commands.command(name="memory")
    async def memory(self, ctx: commands.Context) -> None:
        """What Kitsune remembers about you."""
        summary = self.bot.pipeline.store.memory(str(ctx.author.id))
        await ctx.reply(
            f"🦊 What I remember about you:\n> {summary}" if summary else "🦊 Nothing yet, kit. Talk to me!"
        )


async def setup(bot: Any) -> None:
    await bot.add_cog(Chat(bot))
