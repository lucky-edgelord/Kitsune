"""Sentence splitting: NLTK Punkt when its data is installed, a punctuation split otherwise."""

import pytest

import kitsune.text as text


@pytest.fixture(autouse=True)
def fresh():
    text._tokenize = None
    yield
    text._tokenize = None


def test_fallback_when_model_missing(monkeypatch, caplog):
    def boom():
        raise LookupError("punkt_tab not found")

    monkeypatch.setattr(text, "_punkt", boom)
    assert text.ensure_punkt() is False
    assert "splitting on punctuation" in caplog.text
    assert text.sentences("Hi kit! Want a rec? Watch Frieren.") == ["Hi kit!", "Want a rec?", "Watch Frieren."]
    assert text.ensure_punkt() is False  # decided once, no repeated warnings or downloads


def test_newlines_always_split(monkeypatch):
    monkeypatch.setattr(text, "_punkt", lambda: (_ for _ in ()).throw(LookupError()))
    assert text.sentences("one thing\n\nanother thing") == ["one thing", "another thing"]


def test_punkt_handles_abbreviations():
    pytest.importorskip("nltk")
    if not text.ensure_punkt():
        pytest.skip("punkt_tab isn't installed (python -m nltk.downloader punkt_tab)")
    got = text.sentences("I met Mr. Smith at 3.5 p.m. today, e.g. near the shrine. He waved! Did you see?")
    assert got == ["I met Mr. Smith at 3.5 p.m. today, e.g. near the shrine.", "He waved!", "Did you see?"]
