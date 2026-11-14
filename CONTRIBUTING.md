# Contributing

```bash
pip install -e ".[dev,emotion]"   # needs ffmpeg and a Rust toolchain (for vector-sdk-py)
pytest -q
ruff check src tests && ruff format src tests
```

* Tests never touch the network: providers take an `httpx` transport or a fake client, and the bot tests drive the
  cogs with fake messages (see `tests/conftest.py`).
* **New backend?** Implement the Protocol in `providers/<kind>/base.py` (e.g. a different LLM or TTS), add it to
  that package's `__init__`, and build it in `Services.from_config`.
* **New feature?** Add a cog in `src/kitsune/cogs/` with an `async def setup(bot)` and list it in `app.COGS`.
* **New expression?** Add `assets/sprites/<mood>/{open,blink}_{closed,talk}.png` and a `Mood` member.
