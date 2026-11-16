# Kitsune: build the Rust-backed vector-sdk-py once, then a slim runtime image.
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git pkg-config libssl-dev \
    && curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --wheel-dir /wheels ".[emotion]" --extra-index-url https://download.pytorch.org/whl/cpu

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels \
    && python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab
WORKDIR /app
VOLUME ["/app/data"]
ENV KITSUNE_DATA_DIR=/app/data
CMD ["kitsune", "run"]
