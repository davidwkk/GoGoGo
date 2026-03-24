FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

ENV UV_PROJECT_ENVIRONMENT="/venv"

RUN uv venv /venv
RUN uv sync --no-install-project --frozen

ENV VIRTUAL_ENV="/venv"
ENV PATH="/venv/bin:$PATH"

COPY . .
RUN mkdir -p logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
