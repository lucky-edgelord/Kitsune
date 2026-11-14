from kitsune.moods import Mood
from kitsune.providers.emotion import DistilBertEmotion, label_to_mood


def test_label_mapping():
    assert label_to_mood("joy", 0.9) is Mood.HAPPY
    assert label_to_mood("surprise", 0.9) is Mood.HAPPY
    assert label_to_mood("anger", 0.8) is Mood.MAD
    assert label_to_mood("love", 0.7) is Mood.SHY
    assert label_to_mood("sadness", 0.9) is Mood.SAD
    assert label_to_mood("fear", 0.9) is Mood.SAD
    assert label_to_mood("joy", 0.2) is Mood.NEUTRAL
    assert label_to_mood("???", 0.99) is Mood.NEUTRAL


async def test_detect_uses_pipeline_scores():
    fake = lambda text: [[{"label": "anger", "score": 0.91}, {"label": "joy", "score": 0.05}]]  # noqa: E731
    assert await DistilBertEmotion(pipeline=fake).detect("grr") is Mood.MAD


async def test_detect_never_raises():
    def broken(text):
        raise RuntimeError("model exploded")

    assert await DistilBertEmotion(pipeline=broken).detect("hi") is Mood.NEUTRAL
    assert await DistilBertEmotion(pipeline=broken).detect("") is Mood.NEUTRAL


def test_mood_parse():
    assert Mood.parse(" Happy ") is Mood.HAPPY and Mood.parse("nope") is Mood.NEUTRAL


def test_every_mood_has_a_reaction():
    assert {m.emoji for m in Mood} == {"😄", "😠", "😐", "😢", "😳"}
