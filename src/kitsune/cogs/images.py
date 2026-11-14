"""NovelAI art: the image channel and ``!imagine``."""

from __future__ import annotations

import logging
from typing import Any

import vector
from vector.ext import commands

from ..channels import matches
from ..errors import ImageError

log = logging.getLogger(__name__)


class Images(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def draw(self, message: Any, prompt: str) -> None:
        images = self.bot.services.images
        prefix = self.bot.config.prefix
        if images is None:
            await message.reply("🦊 Image generation needs a NovelAI token (NOVELAI_TOKEN).")
            return
        prompt = prompt.strip()
        if not prompt:
            await message.reply(f"Give me some tags, kit: `{prefix}imagine 1girl, fox ears, red hair, night city`")
            return
        async with message.channel.typing():
            try:
                pngs = await images.generate(prompt)
            except ImageError as e:
                log.warning("image failed: %s", e)
                await message.reply(f"🦊 NovelAI said no: {e}")
                return
        files = [vector.File(png, filename=f"kitsune_{i}.png") for i, png in enumerate(pngs)]
        await message.reply(f"-# 🖼️ {prompt[:180]}", files=files)

    @commands.Cog.listener()
    async def on_message(self, message: Any) -> None:
        bot = self.bot
        if message.author.bot or message.author == bot.user:
            return
        text = (message.content or "").strip()
        if text and not text.startswith(bot.config.prefix) and matches(message.channel, bot.config.image_channels):
            await self.draw(message, text)

    @commands.command(name="imagine", aliases=["img", "draw"])
    async def imagine(self, ctx: commands.Context, *, prompt: str = "") -> None:
        """Generate an anime image (Danbooru-style tags work best)."""
        await self.draw(ctx.message, prompt)


async def setup(bot: Any) -> None:
    await bot.add_cog(Images(bot))
