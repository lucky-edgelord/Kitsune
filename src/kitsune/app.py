"""The Vector bot: a ``commands.Bot`` that loads Kitsune's cogs."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from vector.ext import commands

from .channels import is_hers
from .config import Config
from .pipeline import ReplyPipeline
from .services import Services
from .text import ensure_punkt

log = logging.getLogger(__name__)

MISSING_AVATAR = object()

COGS = ("kitsune.cogs.chat", "kitsune.cogs.images", "kitsune.cogs.utility")


class KitsuneBot(commands.Bot):
    def __init__(self, services: Services, pipeline: Optional[ReplyPipeline] = None) -> None:
        c = services.config
        super().__init__(command_prefix=c.prefix, data_dir=c.data_dir, help_command=None)
        self.services = services
        self.config = c
        self.pipeline = pipeline or services.pipeline()

    async def setup_hook(self) -> None:
        for ext in COGS:
            await self.load_extension(ext)
        asyncio.get_running_loop().run_in_executor(None, ensure_punkt)  # sentence model: download once, not mid-reply
        warm = getattr(self.services.emotion, "warm_up", None)
        if warm is not None:  # load the emotion model in the background, not on the first message
            asyncio.get_running_loop().run_in_executor(None, warm)

    async def process_commands(self, message: Any) -> None:
        # she ignores every channel except her chat and image channels
        if is_hers(self, message.channel):
            await super().process_commands(message)

    async def on_command_error(self, context: Any, exception: Exception) -> None:
        if isinstance(exception, (commands.CheckFailure, commands.CommandNotFound)):
            return  # wrong channel for that command, or not a command: stay quiet
        await super().on_command_error(context, exception)

    async def on_ready(self) -> None:
        log.info("Kitsune is online as %s", self.user)
        if self.config.set_profile:
            await self.apply_profile()

    async def apply_profile(self) -> None:
        """Set her display name, about text and avatar, only when the name or about differ (no re-upload loop)."""
        c, me = self.config, self.user
        if me is None:
            return
        current = (getattr(me, "display_name", None) or getattr(me, "name", "")) or ""
        about = getattr(getattr(me, "_profile", None), "about", None)
        if current == c.display_name and (about is None or about == c.about):
            return
        try:
            avatar = c.avatar_file if c.avatar_file and os.path.isfile(c.avatar_file) else MISSING_AVATAR
            kwargs = {"username": c.display_name, "about": c.about}
            if avatar is not MISSING_AVATAR:
                kwargs["avatar"] = avatar
            await me.edit(**kwargs)
            log.info("profile set: %s", c.display_name)
        except Exception as e:
            log.warning("couldn't update profile: %s", e)

    async def close(self) -> None:
        await self.services.aclose()
        await super().close()


def create_bot(config: Optional[Config] = None) -> KitsuneBot:
    config = config or Config.from_env()
    return KitsuneBot(Services.from_config(config))


def run(config: Optional[Config] = None) -> None:
    config = config or Config.from_env()
    config.validate()
    create_bot(config).run(config.nsec)
