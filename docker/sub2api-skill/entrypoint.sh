#!/bin/sh
set -eu

mkdir -p /config /data /data/imports /data/backups

if [ ! -f "${SUB2API_BOT_SECRETS_FILE:-/config/sub2api-bot-secrets.json}" ]; then
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    python3 - <<'PY'
import base64, json, os, pathlib
path = pathlib.Path(os.environ.get("SUB2API_BOT_SECRETS_FILE", "/config/sub2api-bot-secrets.json"))
data = {
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": os.environ.get("SUB2API_BOT_ALLOWED_CHAT_IDS", ""),
    "sub2api_admin_email": os.environ.get("SUB2API_ADMIN_EMAIL", ""),
    "sub2api_admin_password_b64": os.environ.get("SUB2API_ADMIN_PASSWORD_B64", ""),
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
path.chmod(0o600)
PY
  else
    echo "Missing secrets file and TELEGRAM_BOT_TOKEN is not set" >&2
    exit 1
  fi
fi

exec python3 /app/sub2api_telegram_bot.py
