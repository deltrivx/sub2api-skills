#!/bin/sh
set -eu

mkdir -p /config /data /data/imports /data/backups

SECRETS_FILE="${SUB2API_BOT_SECRETS_FILE:-/config/sub2api-bot-secrets.json}"
BACKEND="${SUB2API_BOT_BACKEND:-telegram}"

# 如果 secrets 文件不存在，按后端类型生成。
# both 模式需要同时有 QQ 和 Telegram 凭据。
if [ ! -f "${SECRETS_FILE}" ]; then
  case "${BACKEND}" in
    qq|qqbot)
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
      ;;
    telegram|tg)
      if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "Missing secrets file and TELEGRAM_BOT_TOKEN is not set" >&2
        exit 1
      fi
      python3 - <<'PY'
import json, os, pathlib
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
      ;;
    both)
      # both 模式：secrets 同时含 QQ + Telegram 字段
      if [ -z "${QQ_APP_ID:-}" ] || [ -z "${QQ_APP_SECRET:-}" ]; then
        echo "[both] Missing QQ_APP_ID/QQ_APP_SECRET" >&2
        exit 1
      fi
      if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "[both] Missing TELEGRAM_BOT_TOKEN" >&2
        exit 1
      fi
      python3 - <<'PY'
import json, os, pathlib
path = pathlib.Path(os.environ.get("SUB2API_BOT_SECRETS_FILE", "/config/sub2api-bot-secrets.json"))
data = {
    "qq_app_id": os.environ.get("QQ_APP_ID", ""),
    "qq_app_secret": os.environ.get("QQ_APP_SECRET", ""),
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": os.environ.get("SUB2API_BOT_ALLOWED_CHAT_IDS", ""),
    "sub2api_admin_email": os.environ.get("SUB2API_ADMIN_EMAIL", ""),
    "sub2api_admin_password_b64": os.environ.get("SUB2API_ADMIN_PASSWORD_B64", ""),
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
path.chmod(0o600)
PY
      ;;
    *)
      echo "Unknown SUB2API_BOT_BACKEND='${BACKEND}'. Expected: telegram | qq | both" >&2
      exit 1
      ;;
  esac
fi

echo "[entrypoint] starting backend: ${BACKEND}"

# 单后端模式用 exec 替换进程（保持 PID 1 语义）
case "${BACKEND}" in
  telegram|tg)
    exec python3 /app/sub2api_telegram_bot.py
    ;;
  qq|qqbot)
    exec python3 /app/sub2api_qq_bot.py
    ;;
  both)
    # 双后端模式：同时启动 QQ 和 Telegram 两个进程。
    # 用 wait -n 等任一进程退出，然后整体退出（容器重启策略会拉起）。
    # 注意：POSIX sh 不支持 wait -n，busybox sh 也不一定支持，这里用 trap + 后台 PID。
    echo "[entrypoint] launching QQ backend..."
    python3 /app/sub2api_qq_bot.py &
    QQ_PID=$!
    echo "[entrypoint] QQ backend pid: ${QQ_PID}"

    echo "[entrypoint] launching Telegram backend..."
    python3 /app/sub2api_telegram_bot.py &
    TG_PID=$!
    echo "[entrypoint] Telegram backend pid: ${TG_PID}"

    # 信号转发：收到 SIGTERM/SIGINT 时杀掉两个子进程
    trap 'echo "[entrypoint] received signal, stopping both backends"; kill ${QQ_PID} ${TG_PID} 2>/dev/null; exit 0' TERM INT

    # 等待任一进程退出
    while kill -0 ${QQ_PID} 2>/dev/null && kill -0 ${TG_PID} 2>/dev/null; do
      sleep 2
    done

    # 有一个挂了，杀掉另一个并退出（容器 restart=always 会重启）
    if ! kill -0 ${QQ_PID} 2>/dev/null; then
      echo "[entrypoint] QQ backend exited, stopping Telegram"
    else
      echo "[entrypoint] Telegram backend exited, stopping QQ"
    fi
    kill ${QQ_PID} ${TG_PID} 2>/dev/null || true
    wait ${QQ_PID} ${TG_PID} 2>/dev/null || true
    echo "[entrypoint] both backends stopped, container will restart"
    exit 1
    ;;
  *)
    echo "Unknown SUB2API_BOT_BACKEND='${BACKEND}'. Expected: telegram | qq | both" >&2
    exit 1
    ;;
esac
