"""Help and expressions."""

from __future__ import annotations

from typing import Any

import vector
from vector.ext import commands

from ..moods import Mood


class Utility(commands.Cog):
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    @commands.command(name="mood", aliases=["face"])
    async def mood(self, ctx: commands.Context, mood: str = "happy") -> None:
        """Show one of Kitsune's expressions."""
        m = Mood.parse(mood)
        png = self.bot.services.sprites.still_png(m)
        await ctx.send(f"-# {m.value}", file=vector.File(png, filename=f"{m.value}.png"))

    @commands.command(name="help")
    async def help(self, ctx: commands.Context) -> None:
        p = self.bot.config.prefix
        moods = "|".join(m.value for m in Mood)
        await ctx.send(
            "### 🦊 Kitsune\n"
            f"Talk to me in **Kitsune Bot** (just type), or anywhere with `{p}kitsune <message>` or a mention.\n"
            f"Make art in **Anime Image Generator** (just type tags), or anywhere with `{p}imagine <tags>`.\n"
            f"`{p}forget` clears our chat · `{p}mood <{moods}>` shows a face"
        )


async def setup(bot: Any) -> None:
    await bot.add_cog(Utility(bot))
