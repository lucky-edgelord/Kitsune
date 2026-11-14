"""NovelAI art, only in the image channel: type a prompt or use ``!image <prompt>``."""

from __future__ import annotations

import logging
from typing import Any

import vector
from vector.ext import commands

from ..channels import is_image
from ..errors import ImageError

log = logging.getLogger(__name__)


def art_embed(prompt: str, pngs: list, model: str, author: Any = None) -> dict:
    """vector-sdk-py's faux embed: prompt card, the image, then a footer (sent as separate messages)."""
    name = getattr(author, "display_name", None) or getattr(author, "name", None)
    embed = vector.Embed(title="🖼️ Kitsune's art", description=prompt[:400])
    embed.set_image(url="attachment://kitsune_0.png")
    embed.set_footer(text=f"NovelAI · {model}" + (f" · for {name}" if name else ""))
    embed.timestamp = vector.utils.utcnow()
    files = [vector.File(png, filename=f"kitsune_{i}.png") for i, png in enumerate(pngs)]
    return {"embed": embed, "files": files}


class Images(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return is_image(self.bot, ctx.channel)

    async def draw(self, message: Any, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt:
            p = self.bot.config.prefix
            await message.reply(f"Give me a prompt, kit: `{p}image 1girl, fox ears, red hair, night city`")
            return
        images = self.bot.services.images
        if images is None:
            await message.reply("🦊 Image generation needs a NovelAI token (NOVELAI_TOKEN).")
            return
        async with message.channel.typing():
            try:
                pngs = await images.generate(prompt)
            except ImageError as e:
                log.warning("image failed: %s", e)
                await message.reply(f"🦊 NovelAI said no: {e}")
                return
        await message.reply(**art_embed(prompt, pngs, self.bot.config.image_model, message.author))

    @commands.Cog.listener()
    async def on_message(self, message: Any) -> None:
        bot = self.bot
        if message.author.bot or message.author == bot.user or not is_image(bot, message.channel):
            return
        text = (message.content or "").strip()
        if text and not text.startswith(bot.config.prefix):
            await self.draw(message, text)

    @commands.command(name="image", aliases=["imagine", "img", "draw"])
    async def image(self, ctx: commands.Context, *, prompt: str = "") -> None:
        """Generate anime art with NovelAI."""
        await self.draw(ctx.message, prompt)


async def setup(bot: Any) -> None:
    await bot.add_cog(Images(bot))
