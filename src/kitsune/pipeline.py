"""The reply pipeline: think -> feel -> speak -> animate. Independent of Vector, so it is easy to test and reuse."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from .avatar import AvatarRenderer, split_lines
from .errors import ProviderError, RenderError
from .moods import Mood
from .providers.emotion import EmotionDetector
from .providers.llm import ChatModel
from .providers.speech import SpeechSynthesizer
from .storage import ConversationStore

log = logging.getLogger(__name__)


@dataclass
class Reply:
    text: str
    mood: Mood
    video: Optional[bytes] = None  # MP4, when speech and rendering succeeded
    warning: Optional[str] = None  # why there is no video, if one was expected


class ReplyPipeline:
    def __init__(
        self,
        *,
        persona: str,
        chat: ChatModel,
        emotion: EmotionDetector,
        store: ConversationStore,
        speech: Optional[SpeechSynthesizer] = None,
        avatar: Optional[AvatarRenderer] = None,
        history_turns: int = 12,
        subtitles: bool = True,
        max_concurrent: int = 2,
    ) -> None:
        self.persona = persona
        self.chat = chat
        self.emotion = emotion
        self.store = store
        self.speech = speech
        self.avatar = avatar
        self.history_turns = history_turns
        self.subtitles = subtitles
        self._slots = asyncio.Semaphore(max_concurrent)

    @property
    def can_talk(self) -> bool:
        return self.speech is not None and self.avatar is not None

    def system_prompt(self, user_name: str) -> str:
        return f"{self.persona}\n\nYou are talking with {user_name}."

    async def think(self, chat_id: str, user_id: str, user_name: str, text: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt(user_name)}]
        messages += self.store.history(chat_id, user_id, self.history_turns)
        messages.append({"role": "user", "content": text})
        reply = await self.chat.chat(messages)
        if reply:
            self.store.append(
                chat_id, user_id, {"role": "user", "content": text}, {"role": "assistant", "content": reply}
            )
        return reply

    async def reply(self, chat_id: str, user_id: str, user_name: str, text: str, *, video: bool = True) -> Reply:
        """Raises :class:`~kitsune.errors.ChatError` if the LLM fails; speech/render failures only drop the video."""
        async with self._slots:
            answer = await self.think(chat_id, user_id, user_name, text)
            mood = await self.emotion.detect(answer) if answer else Mood.NEUTRAL
            result = Reply(answer, mood)
            if not (answer and video and self.can_talk):
                return result
            try:
                result.video = await self.speak(answer, mood)
            except (ProviderError, RenderError) as e:
                log.warning("no video for this reply: %s", e)
                result.warning = str(e)
            return result

    async def do_tts(self, text: str) -> list:
        """Voice each line separately: the ``[{"text", "audio"}]`` segments Neku got from Inworld."""
        assert self.speech is not None
        lines = split_lines(text) or [text]
        audios = await asyncio.gather(*(self.speech.synthesize(line) for line in lines))
        return [{"text": line, "audio": audio} for line, audio in zip(lines, audios)]

    async def speak(self, text: str, mood: Mood) -> bytes:
        """Neku's ``avatar_waifu``: segments -> merged voice + SRT -> volume classes -> grid video with subtitles."""
        assert self.avatar is not None
        segments = await self.do_tts(text)
        return await self.avatar.avatar_video_async(segments, mood, subtitles=self.subtitles)
