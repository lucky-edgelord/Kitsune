"""Help and expressions."""

from __future__ import annotations

from typing import Any

import vector
from vector.ext import commands

from ..channels import is_chat, is_hers
from ..moods import Mood


class Utility(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return is_hers(self.bot, ctx.channel)

    @commands.command(name="mood", aliases=["face"])
    async def mood(self, ctx: commands.Context, mood: str = "happy") -> None:
        """Show one of Kitsune's expressions."""
        m = Mood.parse(mood)
        if not is_chat(self.bot, ctx.channel):  # her face stays in her channel
            return
        png = self.bot.services.sprites.still_png(m)
        await ctx.send(f"-# {m.value}", file=vector.File(png, filename=f"{m.value}.png"))

    @commands.command(name="help")
    async def help(self, ctx: commands.Context) -> None:
        p = self.bot.config.prefix
        moods = "|".join(m.value for m in Mood)
        await ctx.send(
            "### 🦊 Kitsune\n"
            f"Talk to me here in **Kitsune Bot**: just type, or `{p}kitsune <message>`.\n"
            f"Make art in **Anime Image Generator**: type a prompt, or `{p}image <prompt>`.\n"
            f"`{p}forget` clears our chat · `{p}mood <{moods}>` shows a face"
        )


async def setup(bot: Any) -> None:
    await bot.add_cog(Utility(bot))
