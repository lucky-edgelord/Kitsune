"""Pick Kitsune's expression with DistilBERT emotion (Hugging Face).

The model labels text as sadness, joy, love, anger, fear or surprise; those map onto the five Fox Mafia sprite
sets. Low-confidence results fall back to ``neutral``. If ``transformers`` isn't installed, everything is neutral.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

log = logging.getLogger("kitsune.emotion")

EMOTIONS = ("happy", "mad", "neutral", "sad", "shy")

LABEL_TO_SPRITE: Dict[str, str] = {
    "joy": "happy",
    "surprise": "happy",
    "love": "shy",
    "anger": "mad",
    "sadness": "sad",
    "fear": "sad",
}


def to_sprite(label: str, score: float, threshold: float = 0.45) -> str:
    if score < threshold:
        return "neutral"
    return LABEL_TO_SPRITE.get(label.lower(), "neutral")


class EmotionClassifier:
    def __init__(self, model: str, threshold: float = 0.45) -> None:
        self.model = model
        self.threshold = threshold
        self._pipe: Optional[Any] = None
        self._failed = False

    def _load(self) -> Optional[Any]:
        if self._pipe is None and not self._failed:
            try:
                from transformers import pipeline

                self._pipe = pipeline("text-classification", model=self.model, top_k=None)
                log.info("loaded emotion model %s", self.model)
            except Exception as e:  # missing extra, no network...
                log.warning("emotion model unavailable (%s); Kitsune will stay neutral", e)
                self._failed = True
        return self._pipe

    def classify_sync(self, text: str) -> str:
        pipe = self._load()
        if pipe is None or not text.strip():
            return "neutral"
        scores = pipe(text[:512])
        if scores and isinstance(scores[0], list):
            scores = scores[0]
        best = max(scores, key=lambda s: s["score"])
        return to_sprite(best["label"], float(best["score"]), self.threshold)

    async def classify(self, text: str) -> str:
        return await asyncio.to_thread(self.classify_sync, text)
