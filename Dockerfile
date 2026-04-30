FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY data ./data
COPY main.py .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8000}"]
