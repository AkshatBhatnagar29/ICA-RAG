FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libreoffice \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --no-dev
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY data/samples ./data/samples
COPY templates ./templates
COPY alembic.ini .
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
