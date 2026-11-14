"""Kitsune on Vector (vector-sdk-py)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import vector
from vector.ext import commands

from .avatar import Avatar
from .config import Config
from .emotion import EMOTIONS, EmotionClassifier
from .llm import Ollama, OllamaError
from .memory import Memory
from .novelai import NovelAI, NovelAIError

log = logging.getLogger("kitsune")

NEGATIVE = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, cropped, worst quality, jpeg artifacts, signature, watermark"


def _matches(channel: Any, wanted: list) -> bool:
    name = (getattr(channel, "name", "") or "").lower()
    cid = str(getattr(channel, "id", ""))
    return any(w.lower() == cid or w.lower() in name for w in wanted)


class Kitsune:
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.from_env()
        c = self.config
        self.bot = commands.Bot(command_prefix=c.prefix, data_dir=c.data_dir, help_command=None)
        self.memory = Memory(os.path.join(c.data_dir, "kitsune.db"))
        self.llm = Ollama(c.ollama_host, c.ollama_model, c.ollama_api_key)
        self.emotion = EmotionClassifier(c.emotion_model)
        self.avatar = Avatar(c.sprites_dir, size=c.video_size)
        self.nai = NovelAI(c.novelai_token, voice_seed=c.voice_seed, image_model=c.image_model,
                           image_size=c.image_size) if c.novelai_token else None
        self.persona = Path(c.persona_file).read_text(encoding="utf-8").strip()
        self._busy = asyncio.Semaphore(2)     # at most two replies rendering at once
        self._setup()

    # -- talking ---------------------------------------------------------------------------------------------
    async def think(self, channel_id: str, user: Any, text: str) -> str:
        c = self.config
        uid = str(getattr(user, "id", user))
        name = getattr(user, "display_name", None) or getattr(user, "name", "someone")
        messages = [{"role": "system", "content": f"{self.persona}\n\nYou are talking with {name}."}]
        messages += self.memory.history(channel_id, uid, c.history_turns)
        messages.append({"role": "user", "content": text})
        reply = await self.llm.chat(messages)
        self.memory.add(channel_id, uid, "user", text)
        self.memory.add(channel_id, uid, "assistant", reply)
        return reply

    async def respond(self, channel: Any, author: Any, text: str, *, reply_to: Any = None) -> None:
        async with self._busy, channel.typing():
            try:
                reply = await self.think(str(channel.id), author, text)
            except OllamaError as e:
                log.warning("ollama: %s", e)
                await channel.send("🦊 My brain's offline right now (can't reach Ollama). Try again in a bit.")
                return
            if not reply:
                return
            mood = await self.emotion.classify(reply)
            send = reply_to.reply if reply_to is not None else channel.send
            if not (self.config.talking_video and self.nai):
                await send(reply)
                return
            try:
                audio = await self.nai.tts(reply)
                with tempfile.TemporaryDirectory() as tmp:
                    path = await self.avatar.render_async(audio, mood, os.path.join(tmp, "kitsune.mp4"))
                    await send(reply, file=vector.File(path, filename="kitsune.mp4"))
            except (NovelAIError, RuntimeError) as e:
                log.warning("voice/video failed: %s", e)
                await send(reply)

    # -- images ----------------------------------------------------------------------------------------------
    async def imagine(self, channel: Any, prompt: str, *, reply_to: Any = None) -> None:
        send = reply_to.reply if reply_to is not None else channel.send
        if not self.nai:
            await send("🦊 Image generation needs a NovelAI token (NOVELAI_TOKEN).")
            return
        prompt = prompt.strip()
        if not prompt:
            await send(f"Give me some tags, kit: `{self.config.prefix}imagine 1girl, fox ears, red hair, night city`")
            return
        async with self._busy, channel.typing():
            try:
                images = await self.nai.image(prompt, negative=NEGATIVE)
            except NovelAIError as e:
                log.warning("image: %s", e)
                await send(f"🦊 NovelAI said no: {e}")
                return
            files = [vector.File(img, filename=f"kitsune_{i}.png") for i, img in enumerate(images)]
            await send(f"-# 🖼️ {prompt[:180]}", files=files)

    # -- wiring ------------------------------------------------------------------------------------------------
    def _setup(self) -> None:
        bot, c = self.bot, self.config

        @bot.event
        async def on_ready() -> None:
            log.info("Kitsune is online as %s", bot.user)
            asyncio.get_running_loop().run_in_executor(None, self.emotion.classify_sync, "warm up")

        @bot.event
        async def on_message(message: Any) -> None:
            if message.author.bot or message.author == bot.user:
                return
            content = (message.content or "").strip()
            if content.startswith(c.prefix):
                await bot.process_commands(message)
                return
            if not content:
                return
            if _matches(message.channel, c.chat_channels):
                await self.respond(message.channel, message.author, content, reply_to=message)
            elif _matches(message.channel, c.image_channels):
                await self.imagine(message.channel, content, reply_to=message)
            elif bot.user and bot.user.mentioned_in(message):
                await self.respond(message.channel, message.author, content, reply_to=message)

        @bot.command(name="kitsune", aliases=["kit", "k"])
        async def kitsune_cmd(ctx: commands.Context, *, text: str = "") -> None:
            """Talk to Kitsune anywhere."""
            if not text:
                await ctx.send(f"Hm? Say something, kit. `{c.prefix}kitsune <message>`")
                return
            await self.respond(ctx.channel, ctx.author, text, reply_to=ctx.message)

        @bot.command(name="imagine", aliases=["img", "draw"])
        async def imagine_cmd(ctx: commands.Context, *, prompt: str = "") -> None:
            """Generate an anime image with NovelAI (Danbooru-style tags work best)."""
            await self.imagine(ctx.channel, prompt, reply_to=ctx.message)

        @bot.command(name="forget", aliases=["reset"])
        async def forget_cmd(ctx: commands.Context) -> None:
            """Make Kitsune forget your conversation in this channel."""
            n = self.memory.forget(str(ctx.channel.id), str(ctx.author.id))
            await ctx.send("🦊 Forgotten. Who are you again?" if n else "🦊 We haven't even talked yet, kit.")

        @bot.command(name="mood")
        async def mood_cmd(ctx: commands.Context, emotion: str = "happy") -> None:
            """Show one of Kitsune's expressions."""
            emotion = emotion.lower() if emotion.lower() in EMOTIONS else "neutral"
            await ctx.send(f"-# {emotion}", file=vector.File(self.avatar.still(emotion), filename=f"{emotion}.png"))

        @bot.command(name="help")
        async def help_cmd(ctx: commands.Context) -> None:
            p = c.prefix
            await ctx.send(
                "### 🦊 Kitsune\n"
                f"Talk to me in **Kitsune Bot** (just type), or anywhere with `{p}kitsune <message>` or a mention.\n"
                f"Make art in **Anime Image Generator** (just type tags), or anywhere with `{p}imagine <tags>`.\n"
                f"`{p}forget` clears our chat · `{p}mood <happy|mad|neutral|sad|shy>` shows a face")

    def run(self) -> None:
        if not self.config.nsec:
            raise SystemExit("Set VECTOR_NSEC to Kitsune's nsec (in .env or the environment).")
        if not self.nai:
            log.warning("NOVELAI_TOKEN not set: text-only replies and no image generation")
        self.bot.run(self.config.nsec)
