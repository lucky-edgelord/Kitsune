"""The Vector bot: a ``commands.Bot`` that loads Kitsune's cogs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from vector.ext import commands

from .channels import is_hers
from .config import Config
from .pipeline import ReplyPipeline
from .services import Services

log = logging.getLogger(__name__)

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
