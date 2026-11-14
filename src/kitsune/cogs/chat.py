"""Talking to Kitsune, only in her chat channel."""

from __future__ import annotations

import logging
from typing import Any

import vector
from vector.ext import commands

from ..channels import is_chat
from ..errors import ChatError

log = logging.getLogger(__name__)


class Chat(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return is_chat(self.bot, ctx.channel)

    async def talk(self, message: Any, text: str) -> None:
        bot = self.bot
        author = message.author
        name = getattr(author, "display_name", None) or getattr(author, "name", "someone")
        async with message.channel.typing():
            try:
                reply = await bot.pipeline.reply(
                    str(message.channel.id), str(author.id), name, text, video=bot.config.talking_video
                )
            except ChatError as e:
                log.warning("chat failed: %s", e)
                await message.reply("🦊 My brain's offline right now (can't reach Ollama). Try again in a bit.")
                return
        if not reply.text:
            return
        if reply.video:  # the words are in the subtitles, so the video goes alone (like Neku)
            await message.reply(file=vector.File(reply.video, filename="kitsune.mp4"))
        else:
            await message.reply(reply.text)

    @commands.Cog.listener()
    async def on_message(self, message: Any) -> None:
        bot = self.bot
        if message.author.bot or message.author == bot.user or not is_chat(bot, message.channel):
            return
        text = (message.content or "").strip()
        if text and not text.startswith(bot.config.prefix):
            await self.talk(message, text)

    @commands.command(name="kitsune", aliases=["kit", "k"])
    async def kitsune(self, ctx: commands.Context, *, text: str = "") -> None:
        """Talk to Kitsune."""
        if not text:
            await ctx.reply(f"Hm? Say something, kit. `{self.bot.config.prefix}kitsune <message>`")
            return
        await self.talk(ctx.message, text)

    @commands.command(name="forget", aliases=["reset"])
    async def forget(self, ctx: commands.Context) -> None:
        """Make Kitsune forget your conversation."""
        n = self.bot.pipeline.store.forget(str(ctx.channel.id), str(ctx.author.id))
        await ctx.reply("🦊 Forgotten. Who are you again?" if n else "🦊 We haven't even talked yet, kit.")


async def setup(bot: Any) -> None:
    await bot.add_cog(Chat(bot))
