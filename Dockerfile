# cvforge API + web UI. In Docker use the "openai" provider (Ollama, OpenRouter, OpenAI...) —
# host CLIs like `claude -p` are not available inside the container.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 poppler-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
# mount your cvforge.toml + candidates/ here
WORKDIR /data
EXPOSE 8765
CMD ["cvforge", "serve", "--host", "0.0.0.0", "--port", "8765"]
