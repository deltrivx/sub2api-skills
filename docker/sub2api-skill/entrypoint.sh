#!/bin/sh
set -eu

mkdir -p /config /data /data/imports /data/backups

SECRETS_FILE="${SUB2API_BOT_SECRETS_FILE:-/config/sub2api-bot-secrets.json}"
BACKEND="${SUB2API_BOT_BACKEND:-telegram}"

if [ ! -f "${SECRETS_FILE}" ]; then
  if [ "${BACKEND}" = "qq" ]; then
    if [ -z "${QQ_APP_ID:-}" ] || [ -z "${QQ_APP_SECRET:-}" ]; then
      echo "Missing secrets file and QQ_APP_ID/QQ_APP_SECRET are not set" >&2
      exit 1
    fi
    python3 - <<'PY'
import json, os, pathlib
path = pathlib.Path(os.environ.get("SUB2API_BOT_SECRETS_FILE", "/config/sub2api-bot-secrets.json"))
data = {
    "qq_app_id": os.environ.get("QQ_APP_ID", ""),
    "qq_app_secret": os.environ.get("QQ_APP_SECRET", ""),
    "sub2api_admin_email": os.environ.get("SUB2API_ADMIN_EMAIL", ""),
    "sub2api_admin_password_b64": os.environ.get("SUB2API_ADMIN_PASSWORD_B64", ""),
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
path.chmod(0o600)
PY
  elif [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
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
    echo "Missing secrets file and neither TELEGRAM_BOT_TOKEN nor QQ_APP_ID/QQ_APP_SECRET are set" >&2
    echo "Set SUB2API_BOT_BACKEND=telegram|qq and the corresponding credentials." >&2
    exit 1
  fi
fi

echo "[entrypoint] starting backend: ${BACKEND}"
case "${BACKEND}" in
  telegram|tg)
    exec python3 /app/sub2api_telegram_bot.py
    ;;
  qq|qqbot)
    exec python3 /app/sub2api_qq_bot.py
    ;;
  *)
    echo "Unknown SUB2API_BOT_BACKEND='${BACKEND}'. Expected: telegram | qq" >&2
    exit 1
    ;;
esac
