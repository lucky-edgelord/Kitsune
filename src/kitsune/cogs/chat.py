"""Talking to Kitsune: her channel, mentions and ``!kitsune``."""

from __future__ import annotations

import logging
from typing import Any

import vector
from vector.ext import commands

from ..channels import matches
from ..errors import ChatError

log = logging.getLogger(__name__)


class Chat(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def talk(self, message: Any, text: str) -> None:
        bot, pipeline = self.bot, self.bot.pipeline
        author = message.author
        name = getattr(author, "display_name", None) or getattr(author, "name", "someone")
        async with message.channel.typing():
            try:
                reply = await pipeline.reply(
                    str(message.channel.id), str(author.id), name, text, video=bot.config.talking_video
                )
            except ChatError as e:
                log.warning("chat failed: %s", e)
                await message.reply("🦊 My brain's offline right now (can't reach Ollama). Try again in a bit.")
                return
        if not reply.text:
            return
        if reply.video:
            await message.reply(reply.text, file=vector.File(reply.video, filename="kitsune.mp4"))
        else:
            await message.reply(reply.text)

    @commands.Cog.listener()
    async def on_message(self, message: Any) -> None:
        bot = self.bot
        if message.author.bot or message.author == bot.user:
            return
        text = (message.content or "").strip()
        if not text or text.startswith(bot.config.prefix):
            return
        if matches(message.channel, bot.config.chat_channels) or (bot.user and bot.user.mentioned_in(message)):
            await self.talk(message, text)

    @commands.command(name="kitsune", aliases=["kit", "k"])
    async def kitsune(self, ctx: commands.Context, *, text: str = "") -> None:
        """Talk to Kitsune from any channel."""
        if not text:
            await ctx.reply(f"Hm? Say something, kit. `{self.bot.config.prefix}kitsune <message>`")
            return
        await self.talk(ctx.message, text)

    @commands.command(name="forget", aliases=["reset"])
    async def forget(self, ctx: commands.Context) -> None:
        """Make Kitsune forget your conversation in this channel."""
        n = self.bot.pipeline.store.forget(str(ctx.channel.id), str(ctx.author.id))
        await ctx.reply("🦊 Forgotten. Who are you again?" if n else "🦊 We haven't even talked yet, kit.")


async def setup(bot: Any) -> None:
    await bot.add_cog(Chat(bot))
