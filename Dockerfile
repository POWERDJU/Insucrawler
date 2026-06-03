FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENABLE_ARTICLE_BODY_FETCH=false \
    ENABLE_GEMINI_GROUNDING=false \
    EXCLUSIVE_RIGHT_EXTRACTION_DEFAULT_MODE=enqueue_only

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p data logs

EXPOSE 8000

CMD ["python", "scripts/start_web.py"]
