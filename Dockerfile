FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements.lock requirements-dev.txt ./
RUN pip install -r requirements.txt -c requirements.lock

COPY . .

RUN useradd --create-home --uid 1000 app && mkdir -p /data/uploads && chown -R app /data
USER app

EXPOSE 8000
CMD ["sh", "scripts/start.sh"]
