import json

import httpx
import pytest

from kitsune.errors import ChatError, ImageError, SpeechError
from kitsune.providers.images import ImageGenerator, NovelAIImages
from kitsune.providers.llm import ChatModel, OllamaChat
from kitsune.providers.speech import NovelAISpeech, SpeechSynthesizer


def recorder(response):
    seen = {}

    def handler(req: httpx.Request):
        seen.update(url=str(req.url), auth=req.headers.get("authorization"), body=json.loads(req.content or b"{}"))
        return response

    return seen, httpx.MockTransport(handler)


async def test_ollama_request_and_reply():
    seen, t = recorder(httpx.Response(200, json={"message": {"role": "assistant", "content": " Hi kit! "}}))
    llm = OllamaChat("http://ollama:11434/", "llama3.1", api_key="k", options={"temperature": 0.8}, transport=t)
    assert isinstance(llm, ChatModel)
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "Hi kit!"
    assert seen["url"] == "http://ollama:11434/api/chat" and seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "llama3.1" and seen["body"]["stream"] is False
    assert seen["body"]["options"] == {"temperature": 0.8}


async def test_ollama_errors():
    _, t = recorder(httpx.Response(404, text="model not found"))
    with pytest.raises(ChatError, match="404"):
        await OllamaChat("http://x", "m", transport=t).chat([])

    def down(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(ChatError, match="can't reach"):
        await OllamaChat("http://x", "m", transport=httpx.MockTransport(down)).chat([])


async def test_novelai_tts_request():
    seen, t = recorder(httpx.Response(200, content=b"ID3audio"))
    tts = NovelAISpeech("pst-x", voice_seed="Aini", transport=t)
    assert isinstance(tts, SpeechSynthesizer)
    assert await tts.synthesize("hello " * 300) == b"ID3audio"
    assert seen["url"] == "https://api.novelai.net/ai/generate-voice" and seen["auth"] == "Bearer pst-x"
    assert seen["body"]["version"] == "v2" and seen["body"]["seed"] == "Aini" and len(seen["body"]["text"]) == 1000


async def test_novelai_tts_error_and_token_required():
    _, t = recorder(httpx.Response(401, text="unauthorized"))
    with pytest.raises(SpeechError, match="401"):
        await NovelAISpeech("pst-bad", transport=t).synthesize("hi")
    with pytest.raises(SpeechError):
        NovelAISpeech("")


async def test_novelai_images_with_fake_sdk():
    from PIL import Image

    class FakeSDK:
        class image:
            params = None

            @classmethod
            async def generate(cls, params):
                cls.params = params
                return [Image.new("RGB", (8, 8), "red")]

    gen = NovelAIImages("pst-x", model="nai-diffusion-4-5-full", client=FakeSDK)
    assert isinstance(gen, ImageGenerator)
    pngs = await gen.generate("1girl, fox ears", seed=7)
    assert pngs[0][:4] == b"\x89PNG"
    p = FakeSDK.image.params
    assert p.prompt == "1girl, fox ears" and p.model == "nai-diffusion-4-5-full" and p.seed == 7
    assert "lowres" in p.negative_prompt


async def test_novelai_images_wraps_sdk_errors():
    class Broken:
        class image:
            @staticmethod
            async def generate(params):
                raise RuntimeError("Insufficient Anlas")

    with pytest.raises(ImageError, match="Anlas"):
        await NovelAIImages("pst-x", client=Broken).generate("1girl")
