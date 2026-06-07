#!/usr/bin/env python3
"""Sub2API Telegram Bot template.

Features:
- Telegram command menu in Chinese.
- Read-only diagnostics for Sub2API accounts, groups, tokens, usage, errors and logs.
- JSON/TXT account-file import with automatic group matching/creation.
- Confirmation-code guarded control commands.
- No hard-coded secrets: configure through environment variables.
"""

import json
import os
import pathlib
import shlex
import subprocess
import time
import urllib.request

SUB2API_BASE_URL = os.environ.get("SUB2API_BASE_URL", "https://<your-sub2api-host>").rstrip("/")
SUB2API_ADMIN_EMAIL = os.environ.get("SUB2API_ADMIN_EMAIL", "<admin@example.com>")
SUB2API_ADMIN_PASSWORD = os.environ.get("SUB2API_ADMIN_PASSWORD", "<admin-password>")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "<telegram-bot-token>")
ALLOWED_CHAT_IDS = {x.strip() for x in os.environ.get("SUB2API_BOT_ALLOWED_CHAT_IDS", "<telegram-chat-id>").split(",") if x.strip()}
DB_NAME = os.environ.get("SUB2API_DB_NAME", "sub2api")
DB_USER = os.environ.get("SUB2API_DB_USER", "postgres")
OFFSET_FILE = os.environ.get("SUB2API_BOT_OFFSET_FILE", "/tmp/sub2api_bot_offset.txt")
MUTE_FILE = os.environ.get("SUB2API_BOT_MUTE_FILE", "/tmp/sub2api_bot_mute_until.txt")
IMPORT_DIR = os.environ.get("SUB2API_BOT_IMPORT_DIR", "/tmp/sub2api_bot_imports")
PENDING_FILE = os.environ.get("SUB2API_BOT_PENDING_FILE", "/tmp/sub2api_bot_pending_action.json")
MONITOR_STATE_FILE = os.environ.get("SUB2API_MONITOR_STATE_FILE", "/tmp/sub2api_monitor_state.json")
MONITOR_LOG = os.environ.get("SUB2API_MONITOR_LOG", "/tmp/sub2api_monitor.log")
BOT_LOG = os.environ.get("SUB2API_BOT_LOG", "/tmp/sub2api_telegram_bot.log")

COMMANDS = {
    "status": "查看 Sub2API 状态与调度",
    "summary": "查看 Sub2API 运行摘要",
    "overview": "查看 Sub2API 综合仪表盘",
    "health": "检查服务健康状态",
    "accounts": "查看账号列表与调度状态",
    "groups": "查看分组列表",
    "tokens": "查看 API 令牌列表（脱敏）",
    "usage": "查看今日用量统计",
    "errors": "查看最近错误聚合",
    "logs": "查看关键日志摘要",
    "importhelp": "查看账号文件导入说明",
    "backup": "生成本地配置备份",
    "mute": "临时静默通知：/mute 2h",
    "watch": "恢复通知",
    "pending": "查看待确认操作",
    "confirm": "确认执行控制操作",
    "cancel": "取消待确认操作",
    "enable": "启用账号调度：/enable 100",
    "disable": "禁用账号调度：/disable 100",
    "restart": "重启服务：/restart bot|sub2api",
    "setcron": "修改监控频率：/setcron 30m",
    "help": "查看帮助",
}


def log(*args):
    print("[sub2api-bot]", *args, flush=True)


def run(cmd, timeout=20):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def psql(sql, timeout=20):
    cmd = "psql -d " + shlex.quote(DB_NAME) + " -t -A -F '|' -c " + shlex.quote(sql)
    proc = subprocess.run(["su", "-", DB_USER, "-c", cmd], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return proc.stdout.strip()


def tg_call(method, payload=None, timeout=30):
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/" + method
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def send_message(chat_id, text):
    if len(text) > 3900:
        text = text[:3900] + "\n..."
    return tg_call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})


def mask(value):
    if not isinstance(value, str) or len(value) <= 10:
        return "***"
    return value[:6] + "…" + value[-4:]


def yesno(v):
    return "开" if str(v).lower() in ("t", "true", "1", "yes") or v is True else "关"


def cmd_help(_text=""):
    return "Sub2API 助手可用命令：\n" + "\n".join(f"/{k} - {v}" for k, v in COMMANDS.items())


def cmd_health(_text=""):
    checks = []
    for name, cmd in [("sub2api 服务", "systemctl is-active sub2api"), ("Telegram Bot 服务", "systemctl is-active sub2api-telegram-bot")]:
        r = run(cmd, timeout=8)
        checks.append(f"- {name}: {r.stdout.strip() or r.stderr.strip() or '未知'}")
    try:
        psql("SELECT 1;")
        checks.append("- PostgreSQL: 正常")
    except Exception as exc:
        checks.append("- PostgreSQL: 异常 " + str(exc)[:80])
    try:
        info = tg_call("getMe", timeout=10)
        checks.append("- Telegram API: 正常 " + info.get("result", {}).get("username", ""))
    except Exception as exc:
        checks.append("- Telegram API: 异常 " + str(exc)[:80])
    return "健康检查：\n" + "\n".join(checks)


def cmd_status(_text=""):
    lines = ["Sub2API 状态："]
    try:
        out = psql("SELECT id,name,platform,status,schedulable,priority FROM accounts WHERE deleted_at IS NULL ORDER BY id;")
        for line in out.splitlines():
            aid, name, platform, status, sched, priority = (line.split("|") + [""] * 6)[:6]
            lines.append(f"- #{aid} {name} | {platform} | 状态:{status} | 调度:{yesno(sched)} | 优先级:{priority}")
    except Exception as exc:
        lines.append("账号状态读取失败：" + str(exc)[:120])
    return "\n".join(lines)


def cmd_summary(text=""):
    return cmd_status(text) + "\n\n" + cmd_usage(text) + "\n\n" + cmd_errors(text)


def cmd_overview(text=""):
    return cmd_health(text) + "\n\n" + cmd_summary(text) + "\n\n" + mute_status_line()


def cmd_accounts(_text=""):
    return cmd_status()


def cmd_groups(_text=""):
    out = psql("SELECT id,name,platform,status FROM groups WHERE deleted_at IS NULL ORDER BY id;")
    lines = ["分组列表："]
    for line in out.splitlines():
        gid, name, platform, status = (line.split("|") + [""] * 4)[:4]
        lines.append(f"- #{gid} {name} | {platform} | 状态:{status}")
    return "\n".join(lines)


def cmd_tokens(_text=""):
    out = psql("SELECT id,name,key,status,group_id,quota,quota_used,last_used_at FROM api_keys WHERE deleted_at IS NULL ORDER BY id;")
    lines = ["API 令牌列表（已脱敏）："]
    for line in out.splitlines():
        tid, name, key, status, group_id, quota, used, last = (line.split("|") + [""] * 8)[:8]
        lines.append(f"- #{tid} {name} | {mask(key)} | 状态:{status} | 分组:{group_id} | 额度:{used}/{quota} | 最近:{last or '无'}")
    return "\n".join(lines)


def cmd_usage(_text=""):
    out = psql("SELECT COALESCE(a.name,'unknown'),count(*),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(round(sum(total_cost),6),0) FROM usage_logs u LEFT JOIN accounts a ON a.id=u.account_id WHERE u.created_at >= date_trunc('day', now()) GROUP BY a.name ORDER BY count(*) DESC;")
    lines = ["今日用量统计："]
    if not out:
        return "今日暂无用量记录。"
    for line in out.splitlines():
        name, cnt, in_tok, out_tok, cost = (line.split("|") + [""] * 5)[:5]
        lines.append(f"- {name}: {cnt} 次 | 输入 {in_tok} | 输出 {out_tok} | 成本 {cost}")
    return "\n".join(lines)


def cmd_errors(_text=""):
    out = psql("SELECT COALESCE(a.name,'unknown'),error_type,status_code,count(*) FROM ops_error_logs e LEFT JOIN accounts a ON a.id=e.account_id WHERE e.created_at > now() - interval '24 hours' GROUP BY 1,2,3 ORDER BY count(*) DESC LIMIT 10;")
    lines = ["最近错误聚合："]
    if not out:
        return "最近 24 小时无错误。"
    for line in out.splitlines():
        name, err, code, cnt = (line.split("|") + [""] * 4)[:4]
        lines.append(f"- {name} | {err or 'unknown'} | HTTP:{code or '-'} | {cnt} 次")
    return "\n".join(lines)


def cmd_logs(_text=""):
    sections = []
    for path in (MONITOR_LOG, BOT_LOG):
        r = run("tail -n 30 " + shlex.quote(path) + " 2>/dev/null || true", timeout=8)
        sections.append(path + "：\n" + (r.stdout.strip() or "无"))
    return "\n\n".join(sections)


def cmd_backup(_text=""):
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = f"/root/sub2api_bot_backup_{ts}.tgz"
    run("tar --ignore-failed-read -czf " + shlex.quote(dest) + " /etc/sub2api-bot.env /opt/sub2api-telegram-bot.py /etc/systemd/system/sub2api-telegram-bot.service 2>/dev/null || true", timeout=30)
    return "本地备份已生成：" + dest if pathlib.Path(dest).exists() else "备份失败。"


def parse_duration_to_seconds(s):
    s = (s or "").lower().strip()
    try:
        if s.endswith("h"):
            return int(float(s[:-1]) * 3600)
        if s.endswith("m"):
            return int(float(s[:-1]) * 60)
        if s.endswith("d"):
            return int(float(s[:-1]) * 86400)
        return int(float(s) * 60)
    except Exception:
        return 0


def mute_status_line():
    try:
        until = int(pathlib.Path(MUTE_FILE).read_text().strip())
        if until > int(time.time()):
            return "通知静默: 开，到 " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(until))
    except Exception:
        pass
    return "通知静默: 关"


def cmd_mute(text=""):
    parts = text.split(maxsplit=1)
    seconds = parse_duration_to_seconds(parts[1] if len(parts) > 1 else "")
    if seconds <= 0:
        return mute_status_line() + "\n用法：/mute 30m 或 /mute 2h 或 /mute 1d"
    until = int(time.time()) + seconds
    pathlib.Path(MUTE_FILE).write_text(str(until))
    return "已临时静默通知，到 " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(until))


def cmd_watch(_text=""):
    pathlib.Path(MUTE_FILE).unlink(missing_ok=True)
    return "已恢复通知。\n" + mute_status_line()


def sql_quote(v):
    return "'" + str(v).replace("'", "''") + "'"


def json_sql(v):
    return sql_quote(json.dumps(v, ensure_ascii=False)) + "::jsonb"


def cmd_importhelp(_text=""):
    return "发送 .json/.txt 账号文件即可导入。字段：name、platform/provider、group/group_name、credentials 或 api_key/access_token/refresh_token。导入默认关闭调度，确认后用 /enable <account_id> 开启。"


def normalize_import_item(item, idx=1):
    platform = (item.get("platform") or item.get("provider") or "openai").lower()
    if platform in ("google", "gemini"):
        platform = "gemini"
    if platform in ("claude", "anthropic"):
        platform = "anthropic"
    if platform not in ("openai", "anthropic", "gemini"):
        platform = "openai"
    credentials = dict(item.get("credentials") or {})
    for key in ("api_key", "key", "access_token", "refresh_token", "base_url"):
        if item.get(key):
            credentials[key] = item[key]
    return {
        "name": str(item.get("name") or f"{platform}-import-{idx}")[:100],
        "platform": platform,
        "type": str(item.get("type") or "api_key")[:20],
        "group": str(item.get("group") or item.get("group_name") or platform.capitalize())[:100],
        "credentials": credentials,
        "priority": int(item.get("priority") or 50),
        "concurrency": int(item.get("concurrency") or 3),
    }


def get_or_create_group(name, platform):
    out = psql("SELECT id FROM groups WHERE name=" + sql_quote(name) + " AND deleted_at IS NULL LIMIT 1;")
    if out:
        return int(out.splitlines()[0])
    return int(psql("INSERT INTO groups(name,platform,status) VALUES(" + sql_quote(name) + "," + sql_quote(platform) + ",'active') RETURNING id;").splitlines()[0])


def insert_import_account(acc):
    group_id = get_or_create_group(acc["group"], acc["platform"])
    sql = "INSERT INTO accounts(name,platform,type,credentials,extra,concurrency,priority,status,schedulable) VALUES(" + sql_quote(acc["name"]) + "," + sql_quote(acc["platform"]) + "," + sql_quote(acc["type"]) + "," + json_sql(acc["credentials"]) + ",'{}'::jsonb," + str(acc["concurrency"]) + "," + str(acc["priority"]) + ",'active',false) RETURNING id;"
    account_id = int(psql(sql).splitlines()[0])
    psql(f"INSERT INTO account_groups(account_id,group_id,priority) VALUES({account_id},{group_id},{acc['priority']}) ON CONFLICT (account_id,group_id) DO UPDATE SET priority=EXCLUDED.priority;")
    return account_id, group_id


def tg_download_file(file_id):
    meta = tg_call("getFile", {"file_id": file_id}, timeout=30)
    path = meta.get("result", {}).get("file_path")
    if not path:
        raise RuntimeError("Telegram 未返回 file_path")
    with urllib.request.urlopen("https://api.telegram.org/file/bot" + TELEGRAM_BOT_TOKEN + "/" + path, timeout=60) as resp:
        return resp.read()


def handle_document_message(msg):
    doc = msg.get("document") or {}
    filename = doc.get("file_name") or "account.json"
    if not filename.lower().endswith((".json", ".txt")):
        return "只处理 .json / .txt 账号文件。发送 /importhelp 查看说明。"
    raw = tg_download_file(doc.get("file_id"))
    items = json.loads(raw.decode("utf-8-sig"))
    if isinstance(items, dict):
        items = items.get("accounts") if isinstance(items.get("accounts"), list) else [items]
    pathlib.Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    save_path = pathlib.Path(IMPORT_DIR) / (time.strftime("%Y%m%d-%H%M%S-") + filename.replace("/", "_"))
    save_path.write_bytes(raw)
    imported, skipped = [], []
    for idx, item in enumerate(items, 1):
        try:
            acc = normalize_import_item(item, idx)
            if not acc["credentials"]:
                raise ValueError("缺少凭据字段")
            account_id, group_id = insert_import_account(acc)
            imported.append((account_id, group_id, acc))
        except Exception as exc:
            skipped.append(f"第 {idx} 项失败：{str(exc)[:120]}")
    lines = [f"账号文件分析完成：{filename}", f"导入成功：{len(imported)}，失败/跳过：{len(skipped)}"]
    for account_id, group_id, acc in imported[:20]:
        lines.append(f"- #{account_id} {acc['name']} | {acc['platform']} | 分组:{acc['group']}(#{group_id}) | 调度:关 | 凭据字段:{','.join(acc['credentials'].keys())}")
    lines.extend(skipped[:10])
    lines.append("安全提示：导入账号默认调度关闭，可用 /enable <account_id> 确认开启。")
    return "\n".join(lines)


def pending_load():
    try:
        data = json.loads(pathlib.Path(PENDING_FILE).read_text())
        if int(data.get("expires_at", 0)) >= int(time.time()):
            return data
    except Exception:
        pass
    return None


def make_confirm(summary, command):
    code = str(int(time.time()))[-6:]
    pathlib.Path(PENDING_FILE).write_text(json.dumps({"code": code, "summary": summary, "command": command, "expires_at": int(time.time()) + 300}, ensure_ascii=False))
    return f"需要确认：{summary}\n确认码：{code}\n5 分钟内发送：/confirm {code}\n取消：/cancel"


def cmd_pending(_text=""):
    data = pending_load()
    return "当前没有待确认操作。" if not data else "待确认操作：" + data.get("summary", "") + "\n确认码：" + data.get("code", "")


def cmd_cancel(_text=""):
    pathlib.Path(PENDING_FILE).unlink(missing_ok=True)
    return "已取消待确认操作。"


def cmd_confirm(text=""):
    parts = text.split()
    data = pending_load()
    if len(parts) < 2 or not data or parts[1] != data.get("code"):
        return "没有可确认的操作，或确认码不匹配/已过期。"
    pathlib.Path(PENDING_FILE).unlink(missing_ok=True)
    proc = run(data.get("command", ""), timeout=60)
    return ("已执行：" if proc.returncode == 0 else "执行失败：") + data.get("summary", "") + "\n" + (proc.stdout + proc.stderr)[-1500:]


def account_name(account_id):
    out = psql("SELECT name FROM accounts WHERE id=" + str(int(account_id)) + " AND deleted_at IS NULL LIMIT 1;")
    return out.splitlines()[0] if out else None


def cmd_enable(text=""):
    parts = text.split()
    if len(parts) < 2:
        return "用法：/enable <account_id>"
    name = account_name(parts[1])
    if not name:
        return "未找到账号。"
    sql = "UPDATE accounts SET schedulable=true, updated_at=now() WHERE id=" + str(int(parts[1])) + ";"
    return make_confirm("开启账号调度 #" + parts[1] + " " + name, "su - " + shlex.quote(DB_USER) + " -c " + shlex.quote("psql -d " + shlex.quote(DB_NAME) + " -c " + shlex.quote(sql)))


def cmd_disable(text=""):
    parts = text.split()
    if len(parts) < 2:
        return "用法：/disable <account_id>"
    name = account_name(parts[1])
    if not name:
        return "未找到账号。"
    sql = "UPDATE accounts SET schedulable=false, updated_at=now() WHERE id=" + str(int(parts[1])) + ";"
    return make_confirm("关闭账号调度 #" + parts[1] + " " + name, "su - " + shlex.quote(DB_USER) + " -c " + shlex.quote("psql -d " + shlex.quote(DB_NAME) + " -c " + shlex.quote(sql)))


def cmd_restart(text=""):
    target = (text.split()[1].lower() if len(text.split()) > 1 else "")
    if target == "bot":
        return make_confirm("重启 Telegram Bot 服务", "systemctl restart sub2api-telegram-bot")
    if target == "sub2api":
        return make_confirm("重启 sub2api 服务", "systemctl restart sub2api")
    return "用法：/restart bot 或 /restart sub2api"


def cmd_setcron(text=""):
    value = (text.split()[1].lower() if len(text.split()) > 1 else "")
    mapping = {"15m": "*/15 * * * *", "30m": "0,30 * * * *", "1h": "0 * * * *"}
    if value not in mapping:
        return "用法：/setcron 15m|30m|1h"
    line = mapping[value] + " /usr/bin/python3 /opt/sub2api-monitor.py >> " + MONITOR_LOG + " 2>&1"
    cmd = "(crontab -l 2>/dev/null | grep -v '/opt/sub2api-monitor.py'; echo " + shlex.quote(line) + ") | crontab -"
    return make_confirm("修改监控频率为 " + value, cmd)


HANDLERS = {
    "help": cmd_help,
    "start": cmd_help,
    "health": cmd_health,
    "status": cmd_status,
    "summary": cmd_summary,
    "overview": cmd_overview,
    "accounts": cmd_accounts,
    "groups": cmd_groups,
    "tokens": cmd_tokens,
    "usage": cmd_usage,
    "errors": cmd_errors,
    "logs": cmd_logs,
    "backup": cmd_backup,
    "mute": cmd_mute,
    "watch": cmd_watch,
    "importhelp": cmd_importhelp,
    "pending": cmd_pending,
    "cancel": cmd_cancel,
    "confirm": cmd_confirm,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "restart": cmd_restart,
    "setcron": cmd_setcron,
}


def handle_command(text):
    command = text.strip().split()[0].split("@", 1)[0].lstrip("/").lower()
    return HANDLERS.get(command, cmd_help)(text)


def get_offset():
    try:
        return int(pathlib.Path(OFFSET_FILE).read_text().strip())
    except Exception:
        return None


def set_offset(offset):
    pathlib.Path(OFFSET_FILE).write_text(str(offset))


def setup_bot_menu():
    commands = [{"command": key, "description": desc} for key, desc in COMMANDS.items()]
    tg_call("deleteWebhook", {"drop_pending_updates": False})
    tg_call("setMyCommands", {"commands": commands, "scope": {"type": "default"}})
    tg_call("setMyDescription", {"description": "Sub2API 助手：状态监控、账号文件导入、用量成本、告警日志、备份静默与确认式运维。"})
    tg_call("setMyShortDescription", {"short_description": "Sub2API 管理与监控助手"})
    tg_call("setChatMenuButton", {"menu_button": {"type": "commands"}})
    for chat_id in ALLOWED_CHAT_IDS:
        if chat_id.startswith("<"):
            continue
        tg_call("setMyCommands", {"commands": commands, "scope": {"type": "chat", "chat_id": chat_id}})
        tg_call("setChatMenuButton", {"chat_id": chat_id, "menu_button": {"type": "commands"}})


def main():
    setup_bot_menu()
    log("started")
    while True:
        try:
            payload = {"timeout": 25, "allowed_updates": ["message"]}
            offset = get_offset()
            if offset is not None:
                payload["offset"] = offset
            for update in tg_call("getUpdates", payload, timeout=35).get("result", []):
                set_offset(update["update_id"] + 1)
                msg = update.get("message") or {}
                chat_id = str((msg.get("chat") or {}).get("id"))
                if chat_id not in ALLOWED_CHAT_IDS:
                    log("ignore unauthorized chat", chat_id)
                    continue
                reply = handle_document_message(msg) if msg.get("document") else None
                text = msg.get("text") or ""
                if reply is None and text.startswith("/"):
                    reply = handle_command(text)
                if reply:
                    send_message(chat_id, reply)
        except Exception as exc:
            log("loop error", type(exc).__name__, str(exc)[:300])
            time.sleep(5)


if __name__ == "__main__":
    main()
