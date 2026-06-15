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
      # both 模式：secrets 同时含 QQ + Telegram 字段。
      # 容错：QQ 和 Telegram 凭据任一缺失不致命（只警告），让可用后端继续启动。
      if [ -z "${QQ_APP_ID:-}" ] || [ -z "${QQ_APP_SECRET:-}" ]; then
        echo "[both] WARNING: QQ_APP_ID/QQ_APP_SECRET missing — QQ backend will fail but Telegram continues" >&2
      fi
      if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "[both] WARNING: TELEGRAM_BOT_TOKEN missing — Telegram backend will fail but QQ continues" >&2
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
    # 容错 + 自愈策略：任一进程退出不杀另一个，且自动重启退出的后端。
    # 重启采用指数退避（10s -> 20s -> 40s ... 上限 300s），避免网络抖动时疯狂重连。
    # 成功运行超过 60s 后退避计数器重置为初始值。
    MAX_BACKOFF=300
    MIN_BACKOFF=10

    # 初始化两个后端
    # 注意：不能用 PID=$(func) 命令替换启动——命令替换会阻塞到所有继承其 stdout
    # 的子进程（含后台 &）退出。必须内联启动 + stdout 重定向，让 $! 立即返回。
    echo "[entrypoint] launching QQ backend..."
    python3 /app/sub2api_qq_bot.py &
    QQ_PID=$!
    echo "[entrypoint] QQ backend pid: ${QQ_PID}"
    QQ_BACKOFF=${MIN_BACKOFF}
    QQ_START=$(date +%s)

    echo "[entrypoint] launching Telegram backend..."
    python3 /app/sub2api_telegram_bot.py &
    TG_PID=$!
    echo "[entrypoint] Telegram backend pid: ${TG_PID}"
    TG_BACKOFF=${MIN_BACKOFF}
    TG_START=$(date +%s)

    # 信号转发：收到 SIGTERM/SIGINT 时杀掉两个子进程
    trap 'echo "[entrypoint] received signal, stopping both backends"; kill ${QQ_PID} ${TG_PID} 2>/dev/null; exit 0' TERM INT

    # 主循环：监控两个进程，退出则自动重启（带退避）
    qq_alive=1
    tg_alive=1
    while [ $qq_alive -eq 1 ] || [ $tg_alive -eq 1 ]; do
      sleep 3
      now=$(date +%s)

      # 检查 QQ backend
      if [ $qq_alive -eq 1 ] && ! kill -0 ${QQ_PID} 2>/dev/null; then
        ran=$((now - QQ_START))
        echo "[entrypoint] QQ backend exited after ${ran}s (was alive >=60s? $([ $ran -ge 60 ] && echo yes || echo no); restarting in ${QQ_BACKOFF}s)"
        sleep ${QQ_BACKOFF}
        echo "[entrypoint] relaunching QQ backend..."
        python3 /app/sub2api_qq_bot.py &
        QQ_PID=$!
        QQ_START=$(date +%s)
        echo "[entrypoint] QQ backend pid: ${QQ_PID}"
        # 退避加倍（上限）
        QQ_BACKOFF=$((QQ_BACKOFF * 2))
        [ $QQ_BACKOFF -gt $MAX_BACKOFF ] && QQ_BACKOFF=$MAX_BACKOFF
      elif [ $qq_alive -eq 1 ] && [ $((now - QQ_START)) -ge 60 ]; then
        # 稳定运行超过 60s，重置退避
        QQ_BACKOFF=${MIN_BACKOFF}
        QQ_START=$now
      fi

      # 检查 Telegram backend
      if [ $tg_alive -eq 1 ] && ! kill -0 ${TG_PID} 2>/dev/null; then
        ran=$((now - TG_START))
        echo "[entrypoint] Telegram backend exited after ${ran}s (was alive >=60s? $([ $ran -ge 60 ] && echo yes || echo no); restarting in ${TG_BACKOFF}s)"
        sleep ${TG_BACKOFF}
        echo "[entrypoint] relaunching Telegram backend..."
        python3 /app/sub2api_telegram_bot.py &
        TG_PID=$!
        TG_START=$(date +%s)
        echo "[entrypoint] Telegram backend pid: ${TG_PID}"
        # 退避加倍（上限）
        TG_BACKOFF=$((TG_BACKOFF * 2))
        [ $TG_BACKOFF -gt $MAX_BACKOFF ] && TG_BACKOFF=$MAX_BACKOFF
      elif [ $tg_alive -eq 1 ] && [ $((now - TG_START)) -ge 60 ]; then
        # 稳定运行超过 60s，重置退避
        TG_BACKOFF=${MIN_BACKOFF}
        TG_START=$now
      fi
    done
    echo "[entrypoint] both backends exited, container will restart"
    exit 1
    ;;
  *)
    echo "Unknown SUB2API_BOT_BACKEND='${BACKEND}'. Expected: telegram | qq | both" >&2
    exit 1
    ;;
esac
