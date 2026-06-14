FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SUB2API_BOT_SECRETS_FILE=/config/sub2api-bot-secrets.json \
    SUB2API_BOT_OFFSET_FILE=/data/sub2api_bot_offset.txt \
    SUB2API_BOT_PENDING_FILE=/data/sub2api_bot_pending_action.json \
    SUB2API_BOT_IMPORT_DIR=/data/imports \
    SUB2API_BOT_BACKUP_DIR=/data/backups \
    SUB2API_BOT_BACKEND=telegram

ARG DOCKER_COMPOSE_VERSION=v2.39.4
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl postgresql-client docker-cli \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# 公共命令模块（传输层无关）
COPY skills/sub2api/templates/bot_core.py /app/bot_core.py
# Telegram 传输层
COPY skills/sub2api/templates/telegram-bot.py /app/sub2api_telegram_bot.py
# QQ 传输层
COPY skills/sub2api/templates/qq-bot.py /app/sub2api_qq_bot.py
COPY docker/sub2api-skill/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/config", "/data"]
ENTRYPOINT ["/entrypoint.sh"]
