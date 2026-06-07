#!/usr/bin/env python3
"""Sub2API realtime monitor template.

Runs a fresh account test through Sub2API's admin test endpoint every time it is
called. Historical scheduled-test records are not used for state decisions.

Announcement policy:
- Normal cron mode publishes announcements only when monitored account status changes.
- ``--force`` performs realtime verification and prints a report, but does not
  publish announcements and does not write the state file.
- ``--announce`` / ``--manual-test`` performs realtime verification and publishes
  a manual test announcement.
- Before a new popup announcement is created, previous active popup announcements
  are downgraded to ``silent`` so the UI only pops the latest message while older
  announcements remain in history.

Configure with environment variables; do not hard-code secrets.
"""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SUB2API_BASE_URL = os.environ.get("SUB2API_BASE_URL", "https://<your-sub2api-host>").rstrip("/")
SUB2API_ADMIN_EMAIL = os.environ.get("SUB2API_ADMIN_EMAIL", "<admin@example.com>")
SUB2API_ADMIN_PASSWORD = os.environ.get("SUB2API_ADMIN_PASSWORD", "<admin-password>")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "<telegram-bot-token>")
TELEGRAM_CHAT_ID = os.environ.get("SUB2API_MONITOR_CHAT_ID", os.environ.get("SUB2API_BOT_ALLOWED_CHAT_IDS", "<telegram-chat-id>").split(",")[0])
STATE_FILE = os.environ.get("SUB2API_MONITOR_STATE_FILE", "/tmp/sub2api_monitor_state.json")
MUTE_FILE = os.environ.get("SUB2API_BOT_MUTE_FILE", "/tmp/sub2api_bot_mute_until.txt")
DB_NAME = os.environ.get("SUB2API_DB_NAME", "sub2api")
DB_USER = os.environ.get("SUB2API_DB_USER", "postgres")
FORCE = "--force" in sys.argv
MANUAL_ANNOUNCE = "--announce" in sys.argv or "--manual-test" in sys.argv

# Example mapping. Replace IDs, names and models with your own environment.
MONITORED_ACCOUNTS = json.loads(os.environ.get(
    "SUB2API_MONITORED_ACCOUNTS",
    '[{"id":100,"name":"South-OpenAI","model":"gpt-5.5"},{"id":99,"name":"South-Anthropic","model":"claude-sonnet-4-6"}]',
))
TOKEN_ROUTER_ACCOUNT_ID = int(os.environ.get("SUB2API_TOKEN_ROUTER_ACCOUNT_ID", "110"))

STATUS_TEXT = {
    "available": "正常",
    "rate_limited": "限流",
    "unavailable": "不可用",
    "unknown": "未知",
}


def run(cmd: str, timeout: int = 20):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def psql(sql: str, timeout: int = 20) -> str:
    cmd = "psql -d " + shlex.quote(DB_NAME) + " -t -A -F '|' -c " + shlex.quote(sql)
    proc = subprocess.run(["su", "-", DB_USER, "-c", cmd], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return proc.stdout.strip()


def quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def auth_headers(token: str, extra: dict | None = None) -> dict:
    headers = {"Authorization": "Bearer " + token}
    if extra:
        headers.update(extra)
    return headers


def api_post(path: str, token: str | None, payload: dict, timeout: int = 60, raw: bool = False):
    data = json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers.update(auth_headers(token))
    req = urllib.request.Request(SUB2API_BASE_URL + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode(errors="replace")
        if raw:
            return text
        return json.loads(text)


def login() -> str:
    if SUB2API_ADMIN_PASSWORD.startswith("<"):
        raise RuntimeError("SUB2API_ADMIN_PASSWORD is not configured")
    data = api_post("/api/v1/auth/login", None, {"email": SUB2API_ADMIN_EMAIL, "password": SUB2API_ADMIN_PASSWORD}, timeout=30)
    payload = data.get("data", data) if isinstance(data, dict) else {}
    token = payload.get("access_token") or payload.get("token")
    if not token:
        raise RuntimeError("Sub2API login did not return an access token")
    return token


def normalize_status(status: str, error: str = "") -> str:
    text = (str(status or "") + " " + str(error or "")).lower()
    if status == "success":
        return "available"
    if "rate limit" in text or "ratelimit" in text or "429" in text or "quota" in text or "额度" in text:
        return "rate_limited"
    return "unavailable"


def parse_result_time(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.astimezone()
            return dt
        except Exception:
            continue
    return None


def realtime_test_account(token: str, account_id: int, account_info: dict):
    """Run Sub2API's realtime account test endpoint.

    This mirrors the admin UI's account test flow and avoids relying on stale
    scheduled-test history.
    """
    model = account_info.get("model") or ""
    started = time.time()
    latest = {"status": "unknown", "created_at": datetime.now().astimezone().isoformat(), "latency_ms": 0, "error_message": ""}
    try:
        text = api_post(
            "/api/v1/admin/accounts/" + str(int(account_id)) + "/test",
            token,
            {"model_id": model, "prompt": "ping"},
            timeout=120,
            raw=True,
        )
        latest["latency_ms"] = int((time.time() - started) * 1000)
        latest["raw_response"] = text[-1200:]
        lower = text.lower()
        if '"type":"error"' in lower or "api returned 429" in lower or "rate limit" in lower or "quota" in lower or "额度" in text:
            latest["status"] = "failed"
            latest["error_message"] = text[-1000:]
            return normalize_status(latest["status"], latest["error_message"]), latest
        if "error" in lower and ("failed" in lower or "invalid" in lower or "unauthorized" in lower):
            latest["status"] = "failed"
            latest["error_message"] = text[-1000:]
            return normalize_status(latest["status"], latest["error_message"]), latest
        latest["status"] = "success"
        return "available", latest
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:1200]
        latest["latency_ms"] = int((time.time() - started) * 1000)
        latest["status"] = "failed"
        latest["error_message"] = "HTTP " + str(exc.code) + ": " + body
        return normalize_status(latest["status"], latest["error_message"]), latest
    except Exception as exc:
        latest["latency_ms"] = int((time.time() - started) * 1000)
        latest["status"] = "failed"
        latest["error_message"] = type(exc).__name__ + ": " + str(exc)[:500]
        return "unavailable", latest


def get_account_runtime_override(account_id: int, latest: dict):
    """Prefer newer runtime limiter fields over a realtime/scheduled result."""
    out = psql(
        "SELECT status, schedulable, rate_limited_at, rate_limit_reset_at, overload_until, "
        "temp_unschedulable_until, COALESCE(temp_unschedulable_reason,'') FROM accounts "
        "WHERE id = %d AND deleted_at IS NULL;" % int(account_id)
    )
    if not out:
        return None, ""
    status, schedulable, limited_at, reset_at, overload_until, temp_until, temp_reason = (out.splitlines()[0].split("|") + [""] * 7)[:7]
    if status and status != "active":
        return "unavailable", "账号状态为 " + status

    now = datetime.now().astimezone()
    result_time = parse_result_time(latest.get("created_at"))

    def ts(value):
        return parse_result_time(value) if value else None

    reset_dt = ts(reset_at)
    overload_dt = ts(overload_until)
    temp_dt = ts(temp_until)
    limited_dt = ts(limited_at)

    if reset_dt and reset_dt > now:
        return "rate_limited", "账号 rate_limit_reset_at 尚未到期: " + reset_at
    if overload_dt and overload_dt > now:
        return "rate_limited", "账号 overload_until 尚未到期: " + overload_until
    if temp_dt and temp_dt > now:
        return "rate_limited", "账号 temp_unschedulable_until 尚未到期: " + temp_until + (" " + temp_reason if temp_reason else "")
    if limited_dt and result_time and limited_dt > result_time:
        return "rate_limited", "账号 rate_limited_at 新于本次测试: " + limited_at
    if limited_dt and str(schedulable).lower() not in ("t", "true", "1"):
        return "rate_limited", "账号已被标记限流: " + limited_at
    return None, ""


def check_account_status(token: str, account: dict):
    account_id = int(account["id"])
    current_status, latest = realtime_test_account(token, account_id, account)
    latest = dict(latest or {})
    latest["source"] = "realtime_account_test"
    override_status, override_reason = get_account_runtime_override(account_id, latest)
    if override_status:
        latest["runtime_override_reason"] = override_reason
        if override_reason:
            old_error = latest.get("error_message", "") or ""
            latest["error_message"] = old_error + ("; " if old_error else "") + override_reason
        current_status = override_status
    return current_status, latest


def set_schedulable(account_id: int, enabled: bool):
    value = "true" if enabled else "false"
    psql("UPDATE accounts SET schedulable=" + value + ", updated_at=now() WHERE id=" + str(int(account_id)) + " AND deleted_at IS NULL;")
    psql("INSERT INTO scheduler_outbox(event_type,account_id,payload) VALUES('account_changed'," + str(int(account_id)) + ",'{\"source\":\"monitor\"}'::jsonb);")


def current_schedulable(account_id: int) -> bool:
    out = psql("SELECT schedulable FROM accounts WHERE id=" + str(int(account_id)) + " AND deleted_at IS NULL LIMIT 1;")
    return out == "t"


def silence_existing_popups():
    try:
        psql("UPDATE announcements SET notify_mode = 'silent', updated_at = now() WHERE status = 'active' AND notify_mode = 'popup';")
    except Exception as exc:
        print("old popup downgrade failed, continue:", str(exc)[:120])


def publish_announcement(title: str, content: str, notify_mode: str = "popup"):
    if notify_mode == "popup":
        silence_existing_popups()
    sql = "INSERT INTO announcements(title,content,status,notify_mode) VALUES(" + quote(title) + "," + quote(content) + ",'active'," + quote(notify_mode) + ") RETURNING id;"
    out = psql(sql)
    return out.splitlines()[0] if out else "?"


def muted() -> bool:
    try:
        until = int(pathlib.Path(MUTE_FILE).read_text().strip())
        return until > int(time.time())
    except Exception:
        return False


def send_telegram(title: str, content: str) -> bool:
    if muted():
        print("Telegram muted, skip push")
        return False
    if TELEGRAM_BOT_TOKEN.startswith("<") or TELEGRAM_CHAT_ID.startswith("<"):
        print("Telegram not configured, skip push")
        return False
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    text = title + "\n\n" + content
    if len(text) > 3900:
        text = text[:3900] + "\n..."
    body = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return bool(json.loads(resp.read().decode()).get("ok"))


def load_state() -> dict:
    try:
        return json.loads(pathlib.Path(STATE_FILE).read_text())
    except Exception:
        return {}


def save_state(state: dict):
    pathlib.Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main() -> int:
    token = login()
    state = load_state()
    reports = []
    statuses = {}
    total_report = []

    print("=== 账号状态监控 ===")
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("模式:", "手动测试公告" if MANUAL_ANNOUNCE else ("手动检测" if FORCE else "静默监控"))

    for account in MONITORED_ACCOUNTS:
        account_id = int(account["id"])
        current_status, latest = check_account_status(token, account)
        statuses[account_id] = current_status
        previous = (state.get(str(account_id)) or {}).get("status")
        latency = latest.get("latency_ms", 0)
        print("  " + account["name"] + ": " + STATUS_TEXT.get(current_status, current_status) + " (延迟=" + str(latency) + "ms, source=realtime)")
        if previous is not None and previous != current_status:
            print("    >> 状态变化:", STATUS_TEXT.get(previous, previous), "->", STATUS_TEXT.get(current_status, current_status))
        if not FORCE or MANUAL_ANNOUNCE:
            state[str(account_id)] = {"status": current_status, "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "latency_ms": latency}
        if MANUAL_ANNOUNCE or ((not FORCE) and previous is not None and previous != current_status):
            reports.append((account, previous, current_status, latest))

    # Example routing rule. Adjust account IDs for your own deployment.
    if 100 in statuses:
        openai_ok = statuses[100] == "available"
        if current_schedulable(100) != openai_ok:
            set_schedulable(100, openai_ok)
            total_report.append("- South-OpenAI: " + ("开启" if openai_ok else "关闭"))
        if current_schedulable(TOKEN_ROUTER_ACCOUNT_ID) == openai_ok:
            set_schedulable(TOKEN_ROUTER_ACCOUNT_ID, not openai_ok)
            total_report.append("- TokenRouter: " + ("开启" if not openai_ok else "关闭"))
    if 99 in statuses:
        anth_ok = statuses[99] == "available"
        if current_schedulable(99) != anth_ok:
            set_schedulable(99, anth_ok)
            total_report.append("- South-Anthropic: " + ("开启" if anth_ok else "关闭"))

    for account, previous, current_status, latest in reports:
        title = ("✅" if current_status == "available" else "⚠️") + " [Sub2API] " + account["name"] + " 当前" + STATUS_TEXT.get(current_status, current_status)
        content = (
            "账号：" + account["name"] + "\n"
            "状态：" + STATUS_TEXT.get(current_status, current_status) + "\n"
            "上次：" + str(STATUS_TEXT.get(previous, previous)) + "\n"
            "验证：实时账号测试\n"
            "延迟：" + str(latest.get("latency_ms", 0)) + "ms\n"
            "时间：" + time.strftime("%Y-%m-%d %H:%M:%S")
        )
        if total_report:
            content += "\n\n调度：\n" + "\n".join(total_report)
        announcement_id = publish_announcement(title, content, "popup")
        print("announcement", announcement_id, title)
        send_telegram(title, content)

    if not reports:
        print("no status change; no announcement")
    if not FORCE or MANUAL_ANNOUNCE:
        save_state(state)
    else:
        print("manual detection mode: state file not updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
