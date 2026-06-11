FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SUB2API_BOT_SECRETS_FILE=/config/sub2api-bot-secrets.json \
    SUB2API_BOT_OFFSET_FILE=/data/sub2api_telegram_bot_offset.txt \
    SUB2API_BOT_PENDING_FILE=/data/sub2api_bot_pending_action.json \
    SUB2API_BOT_IMPORT_DIR=/data/imports \
    SUB2API_BOT_BACKUP_DIR=/data/backups

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl postgresql-client docker-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY skills/sub2api/templates/telegram-bot.py /app/sub2api_telegram_bot.py
COPY docker/sub2api-skill/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/config", "/data"]
ENTRYPOINT ["/entrypoint.sh"]
