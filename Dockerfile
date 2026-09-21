FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn gemini_code:app --host 0.0.0.0 --port ${PORT:-8000}"]
