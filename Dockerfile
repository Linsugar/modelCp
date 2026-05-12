FROM python:3.12-slim

ARG VERSION=1.0.0
ARG BUILD_TIME=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

LABEL version="${VERSION}" \
      build_time="${BUILD_TIME}" \
      description="Lottery LLM API"

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY data ./data
COPY main.py .
COPY run.py .

EXPOSE 8549

CMD ["python", "run.py"]
