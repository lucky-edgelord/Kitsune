"""NovelAI art, only in the image channel: type a prompt or use ``!image <prompt>``."""

from __future__ import annotations

import logging
import random
from typing import Any

import vector
from vector.ext import commands

from ..channels import is_image
from ..errors import ImageError

log = logging.getLogger(__name__)


MODEL_NAMES = {
    "nai-diffusion-4-5-full": "NAI V4.5 Full",
    "nai-diffusion-4-5-curated": "NAI V4.5 Curated",
    "nai-diffusion-4-full": "NAI V4 Full",
    "nai-diffusion-5-full": "NAI V5 Full",
    "nai-diffusion-5-curated": "NAI V5 Curated",
}


def art_embed(prompt: str, pngs: list, model: str, size: str, seed: int, author: Any = None) -> dict:
    """vector-sdk-py's faux embed (the Embed v7 look): author line, title, prompt, a fields table, the image,
    and a footer with just the time."""
    name = getattr(author, "display_name", None) or getattr(author, "name", None)
    embed = vector.Embed(title="Kitsune's art", description=prompt[:400])
    embed.set_author(name=f"🦊 for {name}" if name else "🦊 Kitsune")
    embed.add_field(name="Model", value=MODEL_NAMES.get(model, model), inline=True)
    embed.add_field(name="Size", value=str(size).title(), inline=True)
    embed.add_field(name="Seed", value=str(seed), inline=True)
    embed.set_image(url="attachment://kitsune_0.png")
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
            seed = random.randint(0, 2**32 - 1)
            try:
                pngs = await images.generate(prompt, seed=seed)
            except ImageError as e:
                log.warning("image failed: %s", e)
                await message.reply(f"🦊 NovelAI said no: {e}")
                return
        c = self.bot.config
        sent = await message.reply(**art_embed(prompt, pngs, c.image_model, c.image_size, seed, message.author))
        try:
            await sent.add_reaction("❤️")
        except Exception as e:  # a reaction is a nicety, never a failure
            log.debug("couldn't react: %s", e)

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
