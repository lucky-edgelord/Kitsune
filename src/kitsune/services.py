"""Build every backend from a :class:`Config`. Swap any of them by passing your own to :class:`Services`."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .avatar import AvatarRenderer, SpriteBank
from .config import Config
from .pipeline import ReplyPipeline
from .providers.emotion import DistilBertEmotion, EmotionDetector
from .providers.images import ImageGenerator, NovelAIImages
from .providers.llm import ChatModel, OllamaChat
from .providers.speech import NovelAISpeech, SpeechSynthesizer
from .storage import ConversationStore

log = logging.getLogger(__name__)


@dataclass
class Services:
    config: Config
    chat: ChatModel
    emotion: EmotionDetector
    store: ConversationStore
    sprites: SpriteBank
    speech: Optional[SpeechSynthesizer] = None
    images: Optional[ImageGenerator] = None

    @classmethod
    def from_config(cls, config: Config) -> Services:
        c = config
        speech = images = None
        if c.has_novelai:
            speech = NovelAISpeech(c.novelai_token, voice_seed=c.voice_seed)
            images = NovelAIImages(c.novelai_token, model=c.image_model, size=c.image_size)
        else:
            log.warning("NOVELAI_TOKEN not set: text-only replies, no image generation")
        return cls(
            config=c,
            chat=OllamaChat(c.ollama_host, c.ollama_model, api_key=c.ollama_api_key),
            emotion=DistilBertEmotion(c.emotion_model, threshold=c.emotion_threshold),
            store=ConversationStore(os.path.join(c.data_dir, "kitsune.db")),
            sprites=SpriteBank(c.sprites_dir, size=c.video_size),
            speech=speech,
            images=images,
        )

    def pipeline(self) -> ReplyPipeline:
        c = self.config
        return ReplyPipeline(
            persona=Path(c.persona_file).read_text(encoding="utf-8").strip(),
            chat=self.chat,
            emotion=self.emotion,
            store=self.store,
            speech=self.speech,
            avatar=AvatarRenderer(self.sprites) if self.speech else None,
            history_turns=c.history_turns,
            max_concurrent=c.max_concurrent_renders,
        )

    async def aclose(self) -> None:
        for svc in (self.chat, self.speech, self.images):
            if svc is not None:
                await svc.aclose()
        self.store.close()
