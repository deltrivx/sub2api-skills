#!/usr/bin/env python3
import json, os, time, urllib.request, urllib.error, pathlib, subprocess, shlex, tempfile, zipfile, tarfile, re

SUB2API_URL = os.environ.get("SUB2API_BASE_URL", "https://<your-sub2api-host>").rstrip("/")
SECRETS_FILE = os.environ.get("SUB2API_BOT_SECRETS_FILE", "/etc/sub2api-bot-secrets.json")
OFFSET_FILE = os.environ.get("SUB2API_BOT_OFFSET_FILE", "/tmp/sub2api_telegram_bot_offset.txt")
PENDING_FILE = os.environ.get("SUB2API_BOT_PENDING_FILE", "/tmp/sub2api_bot_pending_action.json")
IMPORT_DIR = os.environ.get("SUB2API_BOT_IMPORT_DIR", "/tmp/sub2api_bot_imports")
IMPORT_MAX_FILE_BYTES = int(os.environ.get("SUB2API_BOT_IMPORT_MAX_FILE_BYTES", str(2*1024*1024)))
IMPORT_MAX_ARCHIVE_BYTES = int(os.environ.get("SUB2API_BOT_IMPORT_MAX_ARCHIVE_BYTES", str(10*1024*1024)))
IMPORT_MAX_ARCHIVE_FILES = int(os.environ.get("SUB2API_BOT_IMPORT_MAX_ARCHIVE_FILES", "500"))
IMPORT_MAX_EXTRACT_BYTES = int(os.environ.get("SUB2API_BOT_IMPORT_MAX_EXTRACT_BYTES", str(20*1024*1024)))
LOG_PREFIX = "[sub2api-bot]"
AUTH_HEADER = "Author" + "ization"
BEARER_PREFIX = "Be" + "arer "
ALLOWED_CHAT_IDS = {x.strip() for x in os.environ.get("SUB2API_BOT_ALLOWED_CHAT_IDS", "<telegram-chat-id>").split(",") if x.strip()}

COMMANDS = {
    "/help": "查看帮助",
    "/status": "综合状态/用量/限流",
    "/accounts": "账号列表与路由状态",
    "/models": "模型与映射信息",
    "/channels": "渠道与分组概览",
    "/tokens": "API 令牌列表（脱敏）",
    "/importhelp": "账号文件/链接/压缩包导入说明",
    "/pending": "查看待确认操作",
    "/confirm": "确认执行控制操作",
    "/cancel": "取消待确认操作",
    "/backup": "生成本地配置备份",
    "/restart": "重启：/restart bot|sub2api",
    "/debug": "健康检查与日志摘要",
    "/update": "检查更新",
    "/checkaccounts": "检测全部账号可用性",
}

def log(*args):
    print(LOG_PREFIX, *args, flush=True)

def load_secrets():
    if pathlib.Path(SECRETS_FILE).exists():
        return json.loads(pathlib.Path(SECRETS_FILE).read_text())
    return {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "<telegram-bot-token>"),
        "sub2api_admin_email": os.environ.get("SUB2API_ADMIN_EMAIL", "<admin@example.com>"),
        "sub2api_admin_password_b64": os.environ.get("SUB2API_ADMIN_PASSWORD_B64", ""),
    }

def tg_call(method, payload=None, timeout=30):
    token = load_secrets()["telegram_bot_token"]
    url = "https://api.telegram.org/bot" + token + "/" + method
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def send_message(chat_id, text, reply_markup=None):
    if len(text) > 3900:
        text = text[:3900] + "\n..."
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_call("sendMessage", payload)

def answer_callback_query(callback_query_id, text=""):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return tg_call("answerCallbackQuery", payload)

def message_text_with_urls(msg):
    text = msg.get("text") or msg.get("caption") or ""
    urls = []
    for ent in (msg.get("entities") or []) + (msg.get("caption_entities") or []):
        if ent.get("type") == "text_link" and ent.get("url"):
            urls.append(ent.get("url"))
    if urls:
        text = (text + " " + " ".join(urls)).strip()
    return text



def run(cmd, timeout=20):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

def docker_enabled():
    return pathlib.Path(os.environ.get("DOCKER_HOST_SOCKET", "/var/run/docker.sock")).exists()

def docker_compose_dir():
    return os.environ.get("SUB2API_DEPLOY_DIR", "/sub2api-compose")

def docker_sub2api_image():
    return os.environ.get("SUB2API_IMAGE", "weishaw/sub2api:latest")

def docker_compose_cmd():
    return os.environ.get("DOCKER_COMPOSE_CMD", "docker compose")

def docker_local_digest(image=None):
    image = image or docker_sub2api_image()
    r = run("docker image inspect " + shlex.quote(image) + " --format '{{json .RepoDigests}}'", timeout=20)
    if r.returncode != 0:
        return ""
    try:
        digests = json.loads(r.stdout.strip())
    except Exception:
        return ""
    for item in digests or []:
        if "@sha256:" in item:
            return item.split("@", 1)[1]
    return ""

def docker_remote_digest(image=None):
    image = image or docker_sub2api_image()
    r = run("docker manifest inspect " + shlex.quote(image), timeout=120)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-500:] or "docker manifest inspect failed")
    data = json.loads(r.stdout)
    if isinstance(data, dict) and data.get("manifests"):
        arch = os.environ.get("SUB2API_IMAGE_ARCH", "amd64")
        os_name = os.environ.get("SUB2API_IMAGE_OS", "linux")
        for item in data.get("manifests") or []:
            platform = item.get("platform") or {}
            if platform.get("architecture") == arch and platform.get("os") == os_name and item.get("digest"):
                return item.get("digest")
        first = data.get("manifests", [{}])[0]
        return first.get("digest", "")
    if data.get("config", {}).get("digest"):
        return data["config"]["digest"]
    return ""

def docker_update_command():
    deploy_dir = docker_compose_dir()
    image = docker_sub2api_image()
    compose = docker_compose_cmd()
    return (
        "set -eu; "
        "cd " + shlex.quote(deploy_dir) + "; "
        "echo '步骤 1/5：拉取官方 sub2api 最新镜像...'; " + compose + " pull sub2api; "
        "echo '步骤 2/5：按官方 docker-compose 重建 sub2api 容器...'; " + compose + " up -d sub2api; "
        "echo '步骤 3/5：等待健康检查...'; "
        "for i in $(seq 1 30); do status=$(docker inspect -f '{{.State.Health.Status}}' sub2api 2>/dev/null || true); [ x$status = xhealthy ] && break; sleep 2; done; "
        "docker ps --format '容器状态：{{.Names}} {{.Image}} {{.Status}}' | grep '^容器状态：sub2api '; "
        "echo '步骤 4/5：清理旧悬空镜像...'; docker image prune -f; "
        "echo '步骤 5/5：更新完成。当前镜像：'; docker image inspect " + shlex.quote(image) + " --format '{{.RepoTags}} {{.Id}}'"
    )

def env_first(*names, default=""):
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default

def psql(sql, timeout=20):
    host = env_first("SUB2API_DB_HOST", "DATABASE_HOST", default="127.0.0.1")
    port = env_first("SUB2API_DB_PORT", "DATABASE_PORT", default="5432")
    user = env_first("SUB2API_DB_USER", "DATABASE_USER", default="postgres")
    dbname = env_first("SUB2API_DB_NAME", "DATABASE_DBNAME", default="sub2api")
    password = env_first("SUB2API_DB_PASSWORD", "DATABASE_PASSWORD")
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    cmd = ["psql", "-h", host, "-p", str(port), "-U", user, "-d", dbname, "-t", "-A", "-F", "|", "-c", sql]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return proc.stdout.strip()

def login_sub2api():
    import base64 as b64
    secrets = load_secrets()
    email = secrets.get("sub2api_admin_email") or os.environ.get("SUB2API_ADMIN_EMAIL", "<admin@example.com>")
    pw_b64 = secrets.get("sub2api_admin_password_b64") or os.environ.get("SUB2API_ADMIN_PASSWORD_B64", "")
    pw = b64.b64decode(pw_b64).decode() if pw_b64 else ""
    body = json.dumps({"email": email, "password": pw}).encode()
    req = urllib.request.Request(SUB2API_URL + "/api/v1/auth/login", data=body, headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    return data["data"]["access_token"]

def api_get(path):
    token = login_sub2api()
    req = urllib.request.Request(SUB2API_URL + path, headers={AUTH_HEADER: BEARER_PREFIX + token})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

def as_list(resp):
    if isinstance(resp, list):
        return resp
    if not isinstance(resp, dict):
        return []
    data = resp.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "list", "data", "records"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []

def mask(value):
    if not isinstance(value, str):
        return value
    if len(value) <= 10:
        return "***"
    if value.startswith("sk-"):
        return value[:6] + "…" + value[-4:]
    if "." in value and len(value) > 30:
        return value[:8] + "…" + value[-6:]
    return value[:4] + "…" + value[-4:]

def yesno(v):
    return "开" if str(v).lower() in ("t", "true", "1", "yes") or v is True else "关"


def cmd_help():
    return "Sub2API 助手可用命令（精简版）：\n" + "\n".join([f"{k} - {v}" for k, v in COMMANDS.items()])

def cmd_accounts():
    rows = []
    try:
        out = psql("SELECT id,name,platform,status,schedulable,priority,updated_at FROM accounts WHERE deleted_at IS NULL ORDER BY id;")
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) >= 7:
                rows.append(parts[:7])
    except Exception:
        resp = api_get("/api/v1/admin/accounts")
        for a in as_list(resp):
            if not a.get("deleted_at"):
                rows.append([a.get("id"), a.get("name"), a.get("platform"), a.get("status"), a.get("schedulable"), a.get("priority"), a.get("updated_at")])
    if not rows:
        return "未获取到账号列表。"
    lines = ["账号列表："]
    for rid, name, platform, status, sched, priority, updated in rows:
        lines.append(f"- #{rid} {name} | {platform} | 状态:{status} | 调度:{yesno(sched)} | 优先级:{priority}")
    return "\n".join(lines)

def cmd_groups():
    last_err = None
    for path in ("/api/v1/admin/groups/all", "/api/v1/admin/groups?page_size=100", "/api/v1/admin/groups"):
        try:
            rows = as_list(api_get(path))
            if rows:
                lines = ["分组列表："]
                for g in rows:
                    lines.append(f"- #{g.get('id')} {g.get('name') or g.get('group_name')} | 状态:{g.get('status', '未知')}")
                return "\n".join(lines)
        except Exception as e:
            last_err = e
    return "未获取到分组列表。" + ("\n错误: " + str(last_err)[:120] if last_err else "")

def cmd_balance():
    last_err = None
    for path in ("/api/v1/admin/users/1", "/api/v1/admin/users/me", "/api/v1/user/profile"):
        try:
            resp = api_get(path)
            data = resp.get("data", resp) if isinstance(resp, dict) else resp
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict):
                keys = ["email", "username", "role", "balance", "quota", "remaining_quota", "concurrency", "status"]
                lines = ["账户/余额信息："]
                found = False
                for k in keys:
                    if k in data:
                        lines.append(f"- {k}: {data.get(k)}")
                        found = True
                return "\n".join(lines) if found else "账户信息：\n" + json.dumps(data, ensure_ascii=False)[:1200]
        except Exception as e:
            last_err = e
    return "未获取到账户/余额信息。" + ("\n错误: " + str(last_err)[:120] if last_err else "")

def cmd_status():
    runtime = {}
    try:
        out = psql("SELECT id,name,schedulable,rate_limited_at,rate_limit_reset_at,overload_until,temp_unschedulable_until,COALESCE(temp_unschedulable_reason,''),status FROM accounts WHERE deleted_at IS NULL ORDER BY id;")
        for line in out.splitlines():
            parts = (line.split("|") + [""] * 9)[:9]
            rid,name,sched,limited_at,reset_at,overload_until,temp_until,temp_reason,status = parts
            runtime[rid] = {"name": name, "sched": sched, "limited_at": limited_at, "reset_at": reset_at, "overload_until": overload_until, "temp_until": temp_until, "temp_reason": temp_reason, "status": status}
    except Exception:
        runtime = {}
    lines = ["Sub2API 综合状态：", "账户轮询/公告/自动规则：已关闭"]
    if runtime:
        lines.append("")
        lines.append("账号路由状态：")
        for rid in sorted(runtime, key=lambda x: int(x)):
            item = runtime[rid]
            flags = []
            if item.get("limited_at"): flags.append("限流:" + item.get("limited_at"))
            if item.get("reset_at"): flags.append("恢复:" + item.get("reset_at"))
            if item.get("temp_until"): flags.append("临停到:" + item.get("temp_until"))
            suffix = " | " + "；".join(flags) if flags else ""
            lines.append(f"- #{rid} {item['name']}: 状态:{item.get('status') or '未知'} | 路由:{yesno(item['sched'])}{suffix}")
    else:
        lines.append("账号状态读取失败。")
    sections = ["\n".join(lines)]
    for fn in (cmd_usage, cmd_limits, cmd_balance):
        try:
            sections.append(fn())
        except Exception as e:
            sections.append("附加状态读取失败：" + type(e).__name__ + ": " + str(e)[:120])
    return "\n\n".join(sections)

def cmd_health():
    checks = []
    checks.append("- Bot 进程: running")
    docker_socket = pathlib.Path(os.environ.get("DOCKER_HOST_SOCKET", "/var/run/docker.sock"))
    if docker_socket.exists():
        for name, container in [
            ("sub2api 容器", os.environ.get("SUB2API_CONTAINER_NAME", "sub2api")),
            ("Bot 容器", os.environ.get("SUB2API_BOT_CONTAINER_NAME", "sub2api-skill")),
        ]:
            r = run("docker inspect -f '{{.State.Status}}' " + shlex.quote(container), timeout=8)
            checks.append(f"- {name}: {r.stdout.strip() or r.stderr.strip() or '未知'}")
    else:
        checks.append("- Docker 控制: 未挂载 /var/run/docker.sock")
    try:
        psql("SELECT 1;")
        checks.append("- PostgreSQL: 正常")
    except Exception as e:
        checks.append("- PostgreSQL: 异常 " + str(e)[:80])
    try:
        api_get("/api/v1/admin/accounts")
        checks.append("- sub2api HTTP/API: 正常")
    except Exception as e:
        checks.append("- sub2api HTTP/API: 异常 " + str(e)[:80])
    try:
        info = tg_call("getMe", timeout=10)
        checks.append("- Telegram API: 正常 " + info.get("result", {}).get("username", ""))
    except Exception as e:
        checks.append("- Telegram API: 异常 " + str(e)[:80])
    return "健康检查：\n" + "\n".join(checks)

def tail_file(path, n=25):
    r = run(f"tail -n {int(n)} {shlex.quote(path)} 2>/dev/null || true", timeout=8)
    return r.stdout.strip()

def cmd_logs():
    sections = []
    sections.append("sub2api_telegram_bot.log：\n" + (tail_file("/tmp/sub2api_telegram_bot.log", 20) or "无"))
    r = run("journalctl -u sub2api --no-pager -n 15 2>/dev/null", timeout=12)
    sections.append("sub2api journal：\n" + (r.stdout.strip() or "无"))
    return "\n\n".join(sections)


def cmd_debug():
    return "\n\n".join([cmd_health(), "关键日志摘要：", cmd_logs()])

def cmd_models():
    lines = ["模型与映射信息："]
    try:
        out = psql("SELECT id,name,platform,credentials->'model_mapping' FROM accounts WHERE deleted_at IS NULL ORDER BY id;")
        for line in out.splitlines():
            aid, name, platform, mapping = (line.split("|", 3) + [""] * 4)[:4]
            lines.append(f"- #{aid} {name} | {platform} | 映射:{mapping[:180] if mapping and mapping not in ('null','{}') else '无/默认'}")
    except Exception as e:
        lines.append("账号模型映射读取失败：" + str(e)[:120])
    try:
        out = psql("SELECT DISTINCT COALESCE(NULLIF(requested_model,''), NULLIF(model,''), NULLIF(upstream_model,'')) AS m FROM usage_logs WHERE created_at > now() - interval '7 days' ORDER BY m LIMIT 30;")
        models = [x for x in out.splitlines() if x]
        if models:
            lines += ["", "近 7 日实际请求模型："] + ["- " + m for m in models]
    except Exception as e:
        lines.append("实际请求模型读取失败：" + str(e)[:120])
    return "\n".join(lines)

def cmd_usage():
    lines = ["今日用量统计："]
    try:
        out = psql("SELECT COALESCE(a.name,'unknown'),count(*),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(round(sum(total_cost),6),0),COALESCE(round(avg(duration_ms)),0) FROM usage_logs u LEFT JOIN accounts a ON a.id=u.account_id WHERE u.created_at >= date_trunc('day', now()) GROUP BY a.name ORDER BY count(*) DESC;")
        if out:
            for line in out.splitlines():
                name, cnt, in_tok, out_tok, cost, avg_ms = (line.split("|") + [""] * 6)[:6]
                lines.append(f"- {name}: {cnt} 次 | 输入 {in_tok} | 输出 {out_tok} | 成本 {cost} | 平均 {avg_ms}ms")
        else:
            lines.append("- 今日暂无 usage_logs 记录")
    except Exception as e:
        lines.append("读取失败：" + str(e)[:160])
    return "\n".join(lines)

def cmd_limits():
    out = psql("SELECT id,name,status,schedulable,rate_limited_at,rate_limit_reset_at,overload_until,temp_unschedulable_until,COALESCE(temp_unschedulable_reason,'') FROM accounts WHERE deleted_at IS NULL ORDER BY id;")
    lines = ["限流与冷却状态："]
    for line in out.splitlines():
        aid,name,status,sched,rl,reset,overload,temp_until,reason = (line.split("|") + [""] * 9)[:9]
        flags=[]
        if rl: flags.append("限流于 " + rl)
        if reset: flags.append("重置 " + reset)
        if overload: flags.append("过载到 " + overload)
        if temp_until: flags.append("临时停调到 " + temp_until)
        if reason: flags.append("原因 " + reason[:60])
        lines.append(f"- #{aid} {name}: 状态:{status} 调度:{yesno(sched)}" + (" | " + "；".join(flags) if flags else " | 无限流/冷却标记"))
    return "\n".join(lines)

def cmd_keys():
    out = psql("SELECT k.id,k.name,COALESCE(g.name,''),k.status,k.quota,k.quota_used,k.usage_5h,k.usage_1d,k.usage_7d,k.expires_at,k.last_used_at,k.key FROM api_keys k LEFT JOIN groups g ON g.id=k.group_id WHERE k.deleted_at IS NULL ORDER BY k.id;")
    lines = ["令牌额度与过期状态（key 已脱敏）："]
    if not out: return "未找到有效令牌。"
    for line in out.splitlines():
        kid,name,group,status,quota,used,u5,u1,u7,expires,last,key = (line.split("|") + [""] * 12)[:12]
        lines.append(f"- #{kid} {name} {mask(key)} | 组:{group or '无'} | 状态:{status} | 额度:{used}/{quota} | 5h:{u5} 1d:{u1} 7d:{u7} | 过期:{expires or '无'} | 最近:{last or '无'}")
    return "\n".join(lines)

def cmd_channels():
    out = psql("SELECT c.id,c.name,c.status,c.restrict_models,c.billing_model_source,count(cg.group_id) FROM channels c LEFT JOIN channel_groups cg ON cg.channel_id=c.id GROUP BY c.id,c.name,c.status,c.restrict_models,c.billing_model_source ORDER BY c.id;")
    lines = ["渠道配置摘要："]
    if out:
        for line in out.splitlines():
            cid,name,status,restrict,source,gcnt = (line.split("|") + [""] * 6)[:6]
            lines.append(f"- #{cid} {name} | 状态:{status} | 限制模型:{yesno(restrict)} | 计费源:{source} | 绑定分组:{gcnt}")
    else:
        lines.append("- 未找到渠道。")
    try:
        lines += ["", cmd_groups()]
    except Exception as e:
        lines += ["", "分组读取失败：" + str(e)[:120]]
    return "\n".join(lines)

def cmd_latency():
    out = psql("SELECT COALESCE(a.name,'unknown'),count(*),COALESCE(round(avg(duration_ms)),0),percentile_disc(0.5) within group (order by duration_ms),percentile_disc(0.95) within group (order by duration_ms),max(duration_ms),COALESCE(round(avg(first_token_ms)),0) FROM usage_logs u LEFT JOIN accounts a ON a.id=u.account_id WHERE u.created_at > now() - interval '24 hours' AND duration_ms IS NOT NULL GROUP BY a.name ORDER BY count(*) DESC LIMIT 10;")
    lines = ["近 24 小时延迟统计："]
    if not out: return "暂无延迟数据。"
    for line in out.splitlines():
        name,cnt,avg,p50,p95,maxv,ttft = (line.split("|") + [""] * 7)[:7]
        lines.append(f"- {name}: {cnt} 次 | avg:{avg}ms p50:{p50}ms p95:{p95}ms max:{maxv}ms TTFT:{ttft}ms")
    return "\n".join(lines)

def cmd_top():
    lines = ["高频统计（近 24 小时）："]
    queries = [("账号", "SELECT COALESCE(a.name,'unknown'),count(*) FROM usage_logs u LEFT JOIN accounts a ON a.id=u.account_id WHERE u.created_at > now() - interval '24 hours' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"),("模型", "SELECT COALESCE(requested_model,model),count(*) FROM usage_logs WHERE created_at > now() - interval '24 hours' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"),("令牌", "SELECT COALESCE(k.name,'unknown'),count(*) FROM usage_logs u LEFT JOIN api_keys k ON k.id=u.api_key_id WHERE u.created_at > now() - interval '24 hours' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;"),("IP", "SELECT COALESCE(ip_address,'unknown'),count(*) FROM usage_logs WHERE created_at > now() - interval '24 hours' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;")]
    for title, sql in queries:
        lines += ["", title + "："]
        out = psql(sql)
        if out:
            for line in out.splitlines():
                k,c = (line.split("|") + [""] * 2)[:2]
                lines.append(f"- {k}: {c}")
        else:
            lines.append("- 无")
    return "\n".join(lines)

def cmd_backup():
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = pathlib.Path(os.environ.get("SUB2API_BOT_BACKUP_DIR", "/data/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = str(backup_dir / f"sub2api_bot_backup_{ts}.tgz")
    targets = os.environ.get("SUB2API_BOT_BACKUP_TARGETS", "/config /data")
    cmd = "tar --warning=no-file-changed --ignore-failed-read -czf " + shlex.quote(dest) + " " + targets + " 2>/dev/null"
    run(cmd, timeout=30)
    if pathlib.Path(dest).exists():
        return "本地备份已生成：" + dest
    return "备份失败。"

def sql_quote(v):
    return "'" + str(v).replace("'", "''") + "'"

def json_sql(v):
    return sql_quote(json.dumps(v, ensure_ascii=False)) + "::jsonb"

def safe_int(s):
    try:
        return int(str(s).strip())
    except Exception:
        return None

def get_account_name_by_id(account_id):
    out = psql("SELECT name FROM accounts WHERE id=" + str(int(account_id)) + " AND deleted_at IS NULL LIMIT 1;")
    return out.splitlines()[0] if out else None

def pending_load():
    try:
        data=json.loads(pathlib.Path(PENDING_FILE).read_text())
        if int(data.get("expires_at",0)) >= int(time.time()):
            return data
    except Exception:
        pass
    return None

def pending_save(action):
    pathlib.Path(PENDING_FILE).write_text(json.dumps(action, ensure_ascii=False))

def pending_clear():
    try: pathlib.Path(PENDING_FILE).unlink()
    except FileNotFoundError: pass

def make_confirm(action, summary, command):
    code = str(int(time.time()))[-6:]
    data = {"code": code, "action": action, "summary": summary, "command": command, "expires_at": int(time.time()) + 300}
    pending_save(data)
    return "需要确认：" + summary + "\n确认码：" + code + "\n5 分钟内发送：/confirm " + code + "\n取消：/cancel"

def confirm_markup(code):
    return {"inline_keyboard": [[
        {"text": "确认", "callback_data": "confirm:" + str(code)},
        {"text": "取消", "callback_data": "cancel:" + str(code)},
    ]]}

def cmd_pending():
    p = pending_load()
    if not p: return "当前没有待确认操作。"
    return "待确认操作：" + p.get("summary", "") + "\n确认码：" + p.get("code", "") + "\n过期时间：" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(p.get("expires_at",0))))

def cmd_cancel():
    pending_clear()
    return "已取消待确认操作。"

def cmd_confirm(text):
    parts = text.split()
    if len(parts) < 2: return cmd_pending()
    p = pending_load()
    if not p: return "没有可确认的操作，或确认码已过期。"
    if parts[1].strip() != p.get("code"):
        return "确认码不匹配。"
    if p.get("kind") == "account_cleanup" and p.get("stage") == "await_first_confirm":
        return cmd_account_cleanup_first_confirm(p)
    command = p.get("command") or ""
    summary = p.get("summary") or ""
    pending_clear()
    if not command:
        return "待确认操作无命令，已取消。"
    r = run(command, timeout=60)
    ok = (r.returncode == 0)
    return ("已执行：" if ok else "执行失败：") + summary + "\n" + ((r.stdout + r.stderr).strip()[-1500:] or "无输出")

def restart_target_command(target):
    if target in ("bot", "telegram", "telegram-bot"):
        return "重启 Telegram Bot 容器", "kill -TERM 1"
    if target in ("sub2api", "api"):
        container = os.environ.get("SUB2API_CONTAINER_NAME", "sub2api")
        if docker_enabled():
            return "重启 sub2api 容器", "docker restart " + shlex.quote(container)
        return "重启 sub2api 服务", "systemctl restart sub2api && systemctl is-active sub2api"
    return None, None

def restart_target_markup():
    return {"inline_keyboard": [[
        {"text": "Bot", "callback_data": "restart_select:bot"},
        {"text": "Sub2API", "callback_data": "restart_select:sub2api"},
    ]]}

def cmd_restart(text, chat_id=None):
    parts=text.split()
    if len(parts)<2:
        if chat_id:
            send_message(chat_id, "请选择要重启的服务：", restart_target_markup())
            return None
        return "请选择要重启的服务：Bot / Sub2API"
    summary, command = restart_target_command(parts[1].lower())
    if summary and command:
        return make_confirm("restart", summary, command)
    return "不支持的服务。可选：bot / sub2api"

def cmd_restart_select(target, chat_id):
    summary, command = restart_target_command(target)
    if not summary:
        return "不支持的服务。"
    reply = make_confirm("restart", summary, command)
    data = pending_load() or {}
    code = data.get("code", "")
    send_message(chat_id, reply, confirm_markup(code) if code else None)
    return None


def cmd_importhelp():
    return "账号文件导入说明：\n- 直接给机器人发送 .json/.txt 文件，或 .zip/.tar/.tar.gz/.tgz 压缩包。\n- 压缩包会自动安全解压，只导入其中的 .json/.txt 文件，忽略其他文件。\n- 支持单个对象、数组，或 accounts/items/data/list 包裹数组。\n- 会自动识别 openai/anthropic/gemini，Codex/ChatGPT OAuth 会按 OpenAI OAuth 导入。\n- 会优先复用已有同平台分组，例如 OpenAI/Anthropic/Google。\n- 敏感字段不会在回复中明文显示；导入默认 schedulable=false，后续可按部署策略启用调度。"

def detect_import_platform(item):
    candidates=[]
    for k in ("platform","provider","service","type","account_type","auth_type","model","name","group","group_name","groupName"):
        if item.get(k): candidates.append(str(item.get(k)))
    creds=item.get("credentials") if isinstance(item.get("credentials"), dict) else {}
    for k in ("platform","provider","service","model","base_url","endpoint"):
        if creds.get(k): candidates.append(str(creds.get(k)))
    blob=" ".join(candidates).lower()
    if any(x in blob for x in ("gemini","google","generativelanguage")): return "gemini"
    if any(x in blob for x in ("anthropic","claude")): return "anthropic"
    if any(x in blob for x in ("openai","chatgpt","codex","gpt","oai")): return "openai"
    if any(item.get(k) for k in ("access_token","accessToken","refresh_token","refreshToken")): return "openai"
    return "openai"

def infer_import_type(item):
    explicit=item.get("account_type") or item.get("auth_type")
    if explicit:
        typ=str(explicit).lower()
    elif any(item.get(k) for k in ("access_token","accessToken","refresh_token","refreshToken")):
        typ="oauth"
    else:
        typ="apikey"
    if typ in ("api_key","key","openai","anthropic","gemini","codex","chatgpt"):
        typ="apikey"
    if typ == "apikey" and any(item.get(k) for k in ("access_token","accessToken","refresh_token","refreshToken")):
        typ="oauth"
    return typ

def default_group_name(platform):
    return {"openai":"OpenAI", "anthropic":"Anthropic", "gemini":"Google"}.get(platform, platform.capitalize())

def preferred_group_id(platform, requested_name=""):
    names=[]
    if requested_name: names.append(str(requested_name))
    names.append(default_group_name(platform))
    seen=[]
    for name in names:
        low=name.lower()
        if low not in seen:
            seen.append(low)
            out=psql("SELECT id,name FROM groups WHERE lower(name)="+sql_quote(low)+" AND deleted_at IS NULL LIMIT 1;")
            if out:
                gid,gname=(out.splitlines()[0].split("|",1)+[name])[:2]
                return int(gid), gname, False
    out=psql("SELECT id,name FROM groups WHERE platform="+sql_quote(platform)+" AND deleted_at IS NULL ORDER BY id LIMIT 1;")
    if out:
        gid,gname=(out.splitlines()[0].split("|",1)+[default_group_name(platform)])[:2]
        return int(gid), gname, False
    name=default_group_name(platform)
    out=psql("INSERT INTO groups(name,platform,status) VALUES("+sql_quote(name)+","+sql_quote(platform)+",'active') RETURNING id,name;")
    gid,gname=(out.splitlines()[0].split("|",1)+[name])[:2]
    return int(gid), gname, True

def default_proxy_id(platform, typ, explicit_proxy):
    explicit=safe_int(explicit_proxy)
    if explicit is not None: return explicit
    if platform == "openai" and typ == "oauth":
        out=psql("SELECT proxy_id FROM accounts WHERE proxy_id IS NOT NULL AND deleted_at IS NULL ORDER BY CASE WHEN platform='openai' THEN 0 ELSE 1 END, id LIMIT 1;")
        return safe_int(out) if out else safe_int(os.environ.get("SUB2API_DEFAULT_PROXY_ID", ""))
    return None

def normalize_import_item(item, idx=1):
    if not isinstance(item, dict): return None
    platform=detect_import_platform(item)
    typ=infer_import_type(item)
    name=item.get("name") or item.get("account_name") or item.get("label") or item.get("email") or (platform+"-import-"+str(idx))
    requested_group=item.get("group") or item.get("group_name") or item.get("groupName") or ""
    creds={}
    if isinstance(item.get("credentials"), dict): creds.update(item.get("credentials"))
    for k in ("api_key","apiKey","key","access_token","accessToken","refresh_token","refreshToken","model_mapping","endpoint","base_url","baseUrl","expires_at","workspace_id","account_id","chatgpt_account_id"):
        if k in item and item.get(k) not in (None,""):
            nk={"apiKey":"api_key","accessToken":"access_token","refreshToken":"refresh_token","baseUrl":"base_url"}.get(k,k)
            creds[nk]=item.get(k)
    extra={}
    if isinstance(item.get("extra"), dict): extra.update(item.get("extra"))
    for k in ("concurrency","priority","rate_multiplier","notes","email"):
        if k in item: extra[k]=item.get(k)
    proxy_id=default_proxy_id(platform, typ, item.get("proxy_id") or item.get("proxyId"))
    gid,gname,created_group=preferred_group_id(platform, requested_group)
    return {"name":str(name)[:100],"platform":platform,"type":str(typ)[:20],"group":gname,"group_id":gid,"group_created":created_group,"credentials":creds,"extra":extra,"proxy_id":proxy_id,"priority":safe_int(item.get("priority")) or 50,"concurrency":safe_int(item.get("concurrency")) or 3}

def insert_import_account(acc):
    proxy_sql="NULL" if acc.get("proxy_id") is None else str(int(acc["proxy_id"]))
    sql="INSERT INTO accounts(name,platform,type,credentials,extra,concurrency,priority,status,schedulable,proxy_id) VALUES("+sql_quote(acc['name'])+","+sql_quote(acc['platform'])+","+sql_quote(acc['type'])+","+json_sql(acc['credentials'])+","+json_sql(acc['extra'])+","+str(acc['concurrency'])+","+str(acc['priority'])+",'active',false,"+proxy_sql+") RETURNING id;"
    out=psql(sql)
    aid=int(out.splitlines()[0])
    gid=int(acc["group_id"])
    psql("INSERT INTO account_groups(account_id,group_id,priority) VALUES("+str(aid)+","+str(gid)+","+str(acc['priority'])+") ON CONFLICT (account_id,group_id) DO UPDATE SET priority=EXCLUDED.priority;")
    return aid,gid

def test_import_account(account_id):
    try:
        token=login_sub2api()
        data=json.dumps({}).encode()
        req=urllib.request.Request(SUB2API_URL+"/api/v1/admin/accounts/"+str(int(account_id))+"/test", data=data, headers={AUTH_HEADER: BEARER_PREFIX + token, "Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=45) as r:
            raw=r.read().decode(errors="replace")
        text=raw.strip()
        lower=text.lower()
        if '"type":"error"' in lower or '"error"' in lower or 'unsupported' in lower:
            return "不可用", text[:180]
        if 'success' in lower or 'ok' in lower or 'pong' in lower or 'data:' in lower:
            return "可用", text[:180]
        return "未知", text[:180] or "空响应"
    except Exception as e:
        return "测试失败", type(e).__name__+": "+str(e)[:160]

def parse_import_payload(raw):
    text=raw.decode('utf-8-sig', errors='replace').strip()
    data=json.loads(text)
    if isinstance(data, dict):
        for key in ("accounts","items","data","list"):
            if isinstance(data.get(key), list): return data[key]
        return [data]
    if isinstance(data, list): return data
    return []

def is_import_data_file(name, mime_type=""):
    low=(name or "").lower()
    mt=(mime_type or "").lower()
    return low.endswith((".json", ".txt")) or mt in ("application/json", "text/plain") or "+json" in mt

def is_import_archive_file(name, mime_type=""):
    low=(name or "").lower()
    mt=(mime_type or "").lower()
    return low.endswith((".zip", ".tar", ".tar.gz", ".tgz")) or mt in ("application/zip", "application/x-zip-compressed", "application/x-tar", "application/gzip", "application/x-gzip")

def safe_archive_member_name(name):
    if not name:
        return None
    # Normalize ZIP/TAR internal paths without writing them to disk.
    pure=pathlib.PurePosixPath(str(name).replace('\\','/'))
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        return None
    return pure.name

def extract_import_files_from_archive(raw, file_name):
    if len(raw) > IMPORT_MAX_ARCHIVE_BYTES:
        raise ValueError("压缩包超过大小限制")
    entries=[]
    total=0
    low=(file_name or "").lower()
    bio=tempfile.SpooledTemporaryFile(max_size=IMPORT_MAX_ARCHIVE_BYTES)
    bio.write(raw); bio.seek(0)
    if low.endswith(".zip") or zipfile.is_zipfile(bio):
        bio.seek(0)
        with zipfile.ZipFile(bio) as zf:
            infos=[x for x in zf.infolist() if not x.is_dir()]
            if len(infos) > IMPORT_MAX_ARCHIVE_FILES:
                raise ValueError("压缩包文件数量超过限制")
            for info in infos:
                base=safe_archive_member_name(info.filename)
                if not base or not is_import_data_file(base):
                    continue
                if info.file_size > IMPORT_MAX_FILE_BYTES:
                    entries.append((base, None, "文件超过单个导入限制"))
                    continue
                total += info.file_size
                if total > IMPORT_MAX_EXTRACT_BYTES:
                    raise ValueError("压缩包解压总量超过限制")
                entries.append((base, zf.read(info), None))
        return entries
    bio.seek(0)
    mode='r:gz' if low.endswith((".tar.gz", ".tgz")) else 'r:*'
    with tarfile.open(fileobj=bio, mode=mode) as tf:
        members=[m for m in tf.getmembers() if m.isfile()]
        if len(members) > IMPORT_MAX_ARCHIVE_FILES:
            raise ValueError("压缩包文件数量超过限制")
        for m in members:
            base=safe_archive_member_name(m.name)
            if not base or not is_import_data_file(base):
                continue
            if m.size > IMPORT_MAX_FILE_BYTES:
                entries.append((base, None, "文件超过单个导入限制"))
                continue
            total += m.size
            if total > IMPORT_MAX_EXTRACT_BYTES:
                raise ValueError("压缩包解压总量超过限制")
            f=tf.extractfile(m)
            if f:
                entries.append((base, f.read(), None))
    return entries

def import_items_from_raw(raw, source_name):
    try:
        items=parse_import_payload(raw)
    except Exception as e:
        return [], [source_name+" 解析失败："+type(e).__name__+": "+str(e)[:160]]
    imported=[]; skipped=[]
    for i,item in enumerate(items,1):
        acc=normalize_import_item(item,i)
        if not acc or not acc.get("credentials"):
            skipped.append(source_name+" 第 "+str(i)+" 项：缺少 credentials/api_key/access_token 等凭据字段")
            continue
        try:
            aid,gid=insert_import_account(acc)
            status,detail=test_import_account(aid)
            imported.append((source_name,aid,gid,acc,status,detail))
        except Exception as e:
            skipped.append(source_name+" 第 "+str(i)+" 项导入失败："+str(e)[:180])
    return imported, skipped

def tg_download_file(file_id):
    meta=tg_call("getFile", {"file_id": file_id}, timeout=30)
    path=meta.get("result",{}).get("file_path")
    if not path: raise RuntimeError("Telegram 未返回 file_path")
    token=load_secrets()["telegram_bot_token"]
    url="https://api.telegram.org/file/bot"+token+"/"+path
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()

def handle_document_message(msg):
    doc=msg.get("document") or {}
    file_name=doc.get("file_name") or "account.json"
    size=int(doc.get("file_size") or 0)
    mime_type = (doc.get("mime_type") or "").lower()
    is_archive=is_import_archive_file(file_name, mime_type)
    is_data=is_import_data_file(file_name, mime_type)
    if is_archive:
        if size > IMPORT_MAX_ARCHIVE_BYTES:
            return "压缩包太大，请控制在 "+str(IMPORT_MAX_ARCHIVE_BYTES//1024//1024)+"MB 内。"
    elif is_data:
        if size > IMPORT_MAX_FILE_BYTES:
            return "文件太大，账号导入文件请控制在 "+str(IMPORT_MAX_FILE_BYTES//1024//1024)+"MB 内。"
    else:
        return "只处理 .json/.txt 账号文件，或 .zip/.tar/.tar.gz/.tgz 压缩包。发送 /importhelp 查看格式说明。"
    raw=tg_download_file(doc.get("file_id"))
    pathlib.Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    save_path=pathlib.Path(IMPORT_DIR)/(time.strftime("%Y%m%d-%H%M%S-")+file_name.replace('/','_'))
    save_path.write_bytes(raw)

    imported=[]; skipped=[]; sources=[]
    if is_archive:
        try:
            extracted=extract_import_files_from_archive(raw, file_name)
        except Exception as e:
            return "压缩包解压失败："+type(e).__name__+": "+str(e)[:200]
        if not extracted:
            return "压缩包内未找到 .json/.txt 账号文件。"
        for inner_name, inner_raw, err in extracted:
            sources.append(inner_name)
            if err:
                skipped.append(inner_name+"："+err)
                continue
            pathlib.Path(IMPORT_DIR, time.strftime("%Y%m%d-%H%M%S-")+file_name.replace('/','_')+"-"+inner_name.replace('/','_')).write_bytes(inner_raw)
            ok,bad=import_items_from_raw(inner_raw, inner_name)
            imported.extend(ok); skipped.extend(bad)
    else:
        sources.append(file_name)
        ok,bad=import_items_from_raw(raw, file_name)
        imported.extend(ok); skipped.extend(bad)

    title="压缩包分析完成："+file_name if is_archive else "账号文件分析完成："+file_name
    lines=[title, "识别文件："+str(len(sources)), "导入成功："+str(len(imported))+"，跳过/失败："+str(len(skipped))]
    for source,aid,gid,acc,status,detail in imported[:20]:
        cred_keys=','.join(sorted([str(k) for k in acc['credentials'].keys()]))
        proxy_text=(" | 代理:#"+str(acc['proxy_id'])) if acc.get('proxy_id') is not None else " | 代理:无"
        group_text=acc['group']+"(#"+str(gid)+")"+(" 新建" if acc.get('group_created') else " 复用")
        source_text=(" | 来源:"+source) if is_archive else ""
        lines.append(f"- #{aid} {acc['name']} | {acc['platform']}/{acc['type']} | 分组:{group_text}{proxy_text} | 调度:关 | 测试:{status} | 凭据字段:{cred_keys}{source_text}")
        if status != "可用": lines.append("  测试详情："+detail)
    if len(imported) > 20:
        lines.append("其余成功项已省略："+str(len(imported)-20))
    if skipped:
        lines.append("失败/跳过：")
        lines.extend(["- "+x for x in skipped[:10]])
        if len(skipped) > 10:
            lines.append("其余失败项已省略："+str(len(skipped)-10))
    lines.append("安全提示：导入账号默认调度关闭；只有测试可用后才建议按部署策略开启调度。")
    return "\n".join(lines)


def account_candidate_sql():
    return """SELECT DISTINCT a.id,a.name
FROM accounts a
WHERE a.deleted_at IS NULL
ORDER BY a.id;"""

def account_candidate_ids():
    out=psql(account_candidate_sql())
    items=[]
    for line in out.splitlines() if out else []:
        aid,name=(line.split("|",1)+[""])[:2]
        sid=safe_int(aid)
        if sid is not None:
            items.append((sid,name))
    return items

def is_bad_account_status(status, detail):
    text=((status or "")+" "+(detail or "")).lower()
    if status == "可用":
        return False
    bad_words=("invalid_grant","expired","expire","unauthorized","401","403","deactivated","revoked","refresh token","unsupported","forbidden","invalid_request","access_denied","测试失败","不可用","error","failed")
    return True if any(x in text for x in bad_words) else status != "可用"

def account_cleanup_pending_load():
    p=pending_load()
    if p and p.get("kind") == "account_cleanup":
        return p
    return None

def account_cleanup_pending_save(data):
    pending_save(data)

def cleanup_code(prefix=""):
    return (prefix + str(int(time.time()))[-6:])[-8:]

def cmd_checkaccounts(text="", chat_id=None):
    candidates=account_candidate_ids()
    if not candidates:
        return "没有找到可检测账号。"
    ok=[]; bad=[]
    lines=["账号可用性检测完成："]
    for aid,name in candidates:
        status,detail=test_import_account(aid)
        if is_bad_account_status(status, detail):
            bad.append({"id": aid, "name": name, "status": status, "detail": detail[:220]})
        else:
            ok.append(aid)
    data={"kind":"account_cleanup","stage":"checked","created_at":int(time.time()),"expires_at":int(time.time())+600,"bad_account_ids":[x["id"] for x in bad],"bad":bad,"summary":{"checked":len(candidates),"ok":len(ok),"bad":len(bad)}}
    account_cleanup_pending_save(data)
    lines += ["", "检测范围：全部账号", "检测账号："+str(len(candidates)), "可用："+str(len(ok)), "不可用/异常："+str(len(bad))]
    markup=None
    if bad:
        lines += ["", "不可用账号："]
        for x in bad[:30]:
            detail=(x.get("detail") or "").replace("\n"," ")[:120]
            lines.append("- #"+str(x["id"])+" "+x.get("name","")+" | "+x.get("status","")+((" | "+detail) if detail else ""))
        if len(bad) > 30:
            lines.append("其余省略："+str(len(bad)-30))
        markup={"inline_keyboard":[
            [{"text":"软删除（可恢复）","callback_data":"account_cleanup:soft"}],
            [{"text":"硬删除（不可恢复）","callback_data":"account_cleanup:hard"}],
            [{"text":"取消","callback_data":"cancel:account_cleanup"}],
        ]}
    else:
        lines.append("未发现需要清理的不可用账号。")
    msg="\n".join(lines)
    if chat_id and markup:
        send_message(chat_id, msg, markup)
        return None
    return msg

def verify_account_ids(ids):
    ids=[int(x) for x in ids if safe_int(x) is not None]
    if not ids:
        return []
    idlist=",".join(str(x) for x in sorted(set(ids)))
    sql="""SELECT DISTINCT a.id
FROM accounts a
WHERE a.deleted_at IS NULL
  AND a.id IN ("""+idlist+") ORDER BY a.id;"
    out=psql(sql)
    return [int(x.strip()) for x in out.splitlines() if x.strip().isdigit()] if out else []

def cmd_cleanaccounts(text):
    parts=text.split()
    if len(parts) < 2 or parts[1].lower() not in ("soft","hard"):
        return "用法：/cleanaccounts soft 或 /cleanaccounts hard。请先执行 /checkaccounts。"
    return cmd_cleanaccounts_mode(parts[1].lower(), button=False)

def cmd_cleanaccounts_mode(mode, button=False):
    if mode not in ("soft","hard"):
        return "未知清理方式。"
    p=account_cleanup_pending_load()
    if not p or p.get("stage") != "checked":
        return "没有可清理的检测结果，或已过期。请先执行 /checkaccounts。"
    ids=verify_account_ids(p.get("bad_account_ids",[]))
    if not ids:
        pending_clear()
        return "没有仍符合条件的不可用账号。"
    code=cleanup_code()
    p.update({"stage":"await_first_confirm","mode":mode,"code":code,"account_ids":ids,"expires_at":int(time.time())+600})
    account_cleanup_pending_save(p)
    if mode == "soft":
        summary="准备软删除 "+str(len(ids))+" 个不可用账号。\n软删除会关闭调度、置为 inactive、写入 deleted_at，记录可恢复。"
    else:
        summary="⚠️ 准备硬删除 "+str(len(ids))+" 个不可用账号。\n硬删除会删除账号及分组绑定记录，不可恢复。"
    text=summary
    if button:
        return text, {"inline_keyboard":[
            [{"text":"确认继续","callback_data":"account_first:"+code}],
            [{"text":"取消","callback_data":"cancel:account_cleanup"}],
        ]}
    return text+"\n第一次确认：/confirm "+code+"\n取消：/cancel"

def account_second_confirm_markup():
    p=account_cleanup_pending_load()
    if not p or p.get("stage") != "await_second_confirm":
        return None
    mode=p.get("mode")
    code=p.get("second_code") or ""
    if mode == "soft":
        cb="account_second:soft:"+code
        text="最终确认软删除"
    else:
        cb="account_second:hard:"+code
        text="最终确认硬删除"
    return {"inline_keyboard":[
        [{"text":text,"callback_data":cb}],
        [{"text":"取消","callback_data":"cancel:account_cleanup"}],
    ]}

def cmd_account_cleanup_first_confirm(p):
    mode=p.get("mode")
    ids=verify_account_ids(p.get("account_ids") or p.get("bad_account_ids",[]))
    if not ids:
        pending_clear()
        return "没有仍符合条件的账号，已取消。"
    second=cleanup_code("s" if mode=="soft" else "h")
    p.update({"stage":"await_second_confirm","second_code":second,"account_ids":ids,"expires_at":int(time.time())+600})
    account_cleanup_pending_save(p)
    if mode == "soft":
        return "二次确认软删除：\n即将软删除 "+str(len(ids))+" 个不可用账号。"
    return "⚠️ 二次确认硬删除：\n即将硬删除 "+str(len(ids))+" 个不可用账号，该操作不可恢复。"

def cmd_confirm_account_cleanup(text, mode):
    parts=text.split()
    if len(parts)<2:
        return "缺少二次确认码。"
    p=account_cleanup_pending_load()
    if not p or p.get("stage") != "await_second_confirm" or p.get("mode") != mode:
        return "没有对应的二次确认操作，或已过期。"
    if parts[1].strip() != p.get("second_code"):
        return "二次确认码不匹配。"
    ids=verify_account_ids(p.get("account_ids",[]))
    pending_clear()
    if not ids:
        return "没有仍符合条件的账号，未执行。"
    idlist=",".join(str(x) for x in ids)
    if mode == "soft":
        sql="UPDATE accounts SET status='inactive', schedulable=false, deleted_at=now(), updated_at=now(), error_message=COALESCE(error_message,'disabled by account cleanup') WHERE deleted_at IS NULL AND id IN ("+idlist+");"
        psql(sql)
        return "已软删除不可用账号："+str(len(ids))+" 个。\n正常账号未处理。"
    # Hard delete: remove common child bindings first. Keep best-effort for optional tables.
    psql("DELETE FROM account_groups WHERE account_id IN ("+idlist+");")
    try:
        psql("DELETE FROM scheduler_outbox WHERE account_id IN ("+idlist+");")
    except Exception:
        pass
    psql("DELETE FROM accounts WHERE id IN ("+idlist+");")
    return "已硬删除不可用账号："+str(len(ids))+" 个。\n正常账号未处理。"

def update_script():
    return os.environ.get("SUB2API_UPDATER_SCRIPT", "/opt/sub2api/bot/sub2api_updater.py")

def cmd_update(chat_id=None):
    if docker_enabled() and pathlib.Path(docker_compose_dir()).exists():
        image = docker_sub2api_image()
        try:
            local = docker_local_digest(image)
            remote = docker_remote_digest(image)
        except Exception as e:
            return "检测 Docker 镜像更新失败：" + type(e).__name__ + ": " + str(e)[:300]
        if local and remote and local == remote:
            return "已是最新版。\n当前镜像：" + image + "\nDigest：" + local
        detail = "检测到 Docker 镜像可更新。\n当前 Digest：" + (local or "未知") + "\n远端 Digest：" + (remote or "未知")
        reply = make_confirm("update", "更新 Sub2API Docker 容器。\n" + detail, docker_update_command())
        data = pending_load() or {}
        code = data.get("code", "")
        if chat_id and code:
            send_message(chat_id, reply, confirm_markup(code))
            return None
        return reply
    script = update_script()
    r = run(script + " check", timeout=120)
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        return "检测更新失败：\n" + out[-2000:]
    if "状态：已是最新" in out or "已是最新" in out or "already up" in out.lower() or "up to date" in out.lower():
        return "已是最新版。\n" + out
    reply = make_confirm("update", "更新 Sub2API 到最新版。\n" + out, script + " apply")
    data = pending_load() or {}
    code = data.get("code", "")
    if chat_id and code:
        send_message(chat_id, reply, confirm_markup(code))
        return None
    return reply



def handle_command(text, chat_id="0"):
    cmd = text.strip().split()[0].split("@", 1)[0].lower()
    try:
        if cmd in ("/start", "/help"):
            return cmd_help()
        if cmd == "/status": return cmd_status()
        if cmd == "/accounts": return cmd_accounts()
        if cmd == "/models": return cmd_models()
        if cmd == "/channels": return cmd_channels()
        if cmd == "/tokens": return cmd_keys()
        if cmd == "/importhelp": return cmd_importhelp()
        if cmd == "/pending": return cmd_pending()
        if cmd == "/confirm": return cmd_confirm(text)
        if cmd == "/cancel": return cmd_cancel()
        if cmd == "/backup": return cmd_backup()
        if cmd == "/restart": return cmd_restart(text, chat_id)
        if cmd == "/debug": return cmd_debug()
        if cmd == "/update": return cmd_update(chat_id)
        if cmd == "/checkaccounts": return cmd_checkaccounts(text, chat_id)
        if cmd == "/cleanaccounts": return cmd_cleanaccounts(text)
        if cmd in ("/confirm_soft_delete", "/confirm-soft-delete"): return cmd_confirm_account_cleanup(text, "soft")
        if cmd in ("/confirm_hard_delete", "/confirm-hard-delete"): return cmd_confirm_account_cleanup(text, "hard")
        return "未知命令。\n\n" + cmd_help()
    except Exception as e:
        return "执行失败：" + type(e).__name__ + ": " + str(e)[:300]

def get_offset():
    try:
        return int(pathlib.Path(OFFSET_FILE).read_text().strip())
    except Exception:
        return None

def set_offset(offset):
    pathlib.Path(OFFSET_FILE).write_text(str(offset))

def setup_bot_menu():
    commands = [{"command": "help", "description": "查看帮助"}] + [
        {"command": k[1:], "description": v} for k, v in COMMANDS.items() if k != "/help"
    ]
    tg_call("deleteWebhook", {"drop_pending_updates": False})
    scopes = [
        {"type": "default"},
        {"type": "all_private_chats"},
    ] + [{"type": "chat", "chat_id": int(chat_id) if str(chat_id).isdigit() else chat_id} for chat_id in ALLOWED_CHAT_IDS]
    # Do not clear commands on every start; overwrite them to avoid empty menus when network hiccups.
    for scope in scopes:
        for payload in ({"commands": commands, "scope": scope}, {"commands": commands, "scope": scope, "language_code": "zh"}):
            try:
                tg_call("setMyCommands", payload)
            except Exception as e:
                log("setMyCommands failed", scope, type(e).__name__, str(e)[:120])
    tg_call("setMyDescription", {"description": "Sub2API 助手：精简命令，覆盖状态、账号、模型、渠道、令牌、导入、备份、调试和更新。"})
    tg_call("setMyShortDescription", {"short_description": "Sub2API 管理助手"})
    tg_call("setChatMenuButton", {"menu_button": {"type": "commands"}})
    for chat_id in ALLOWED_CHAT_IDS:
        tg_call("setChatMenuButton", {"chat_id": int(chat_id) if str(chat_id).isdigit() else chat_id, "menu_button": {"type": "commands"}})

def main():
    setup_bot_menu()
    log("started")
    while True:
        try:
            payload = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            offset = get_offset()
            if offset is not None:
                payload["offset"] = offset
            res = tg_call("getUpdates", payload, timeout=35)
            for upd in res.get("result", []):
                set_offset(upd["update_id"] + 1)
                cb = upd.get("callback_query") or {}
                if cb:
                    cb_id = cb.get("id")
                    data = cb.get("data") or ""
                    msg = cb.get("message") or {}
                    chat_id = str(((msg.get("chat") or {}).get("id")))
                    if chat_id not in ALLOWED_CHAT_IDS:
                        log("ignore unauthorized callback", chat_id)
                        continue
                    if data.startswith("account_cleanup:"):
                        mode=data.split(":",1)[1]
                        answer_callback_query(cb_id, "已选择" + ("软删除" if mode=="soft" else "硬删除"))
                        res=cmd_cleanaccounts_mode(mode, button=True)
                        if isinstance(res, tuple):
                            send_message(chat_id, res[0], res[1])
                        else:
                            send_message(chat_id, res)
                    elif data.startswith("account_first:"):
                        code=data.split(":",1)[1]
                        answer_callback_query(cb_id, "已确认，等待二次确认")
                        reply=cmd_confirm("/confirm " + code)
                        send_message(chat_id, reply, account_second_confirm_markup())
                    elif data.startswith("account_second:"):
                        _,mode,code=data.split(":",2)
                        answer_callback_query(cb_id, "开始执行")
                        if mode == "soft":
                            send_message(chat_id, cmd_confirm_account_cleanup("/confirm_soft_delete " + code, "soft"))
                        else:
                            send_message(chat_id, cmd_confirm_account_cleanup("/confirm_hard_delete " + code, "hard"))
                    elif data.startswith("restart_select:"):
                        target = data.split(":", 1)[1]
                        answer_callback_query(cb_id, "已选择")
                        cmd_restart_select(target, chat_id)
                    elif data.startswith("confirm:"):
                        code = data.split(":", 1)[1]
                        answer_callback_query(cb_id, "开始执行")
                        send_message(chat_id, cmd_confirm("/confirm " + code))
                    elif data.startswith("cancel:"):
                        answer_callback_query(cb_id, "已取消")
                        send_message(chat_id, cmd_cancel())
                    else:
                        answer_callback_query(cb_id, "未知操作")
                    continue
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = str(chat.get("id"))
                text = message_text_with_urls(msg)
                if chat_id not in ALLOWED_CHAT_IDS:
                    log("ignore unauthorized chat", chat_id)
                    continue
                reply = None
                if msg.get("document"):
                    doc = msg.get("document") or {}
                    file_name = doc.get("file_name") or ""
                    mime_type = (doc.get("mime_type") or "").lower()
                    if is_import_archive_file(file_name, mime_type):
                        send_message(chat_id, "收到压缩文件，开始解压并导入~")
                    elif is_import_data_file(file_name, mime_type):
                        send_message(chat_id, "收到账号文件，开始导入~")
                    else:
                        send_message(chat_id, "收到文件，正在检查格式~")
                    reply = handle_document_message(msg)
                elif text.startswith("/"):
                    cmd = text.strip().split()[0].split("@", 1)[0].lower()
                    if cmd == "/checkaccounts":
                        send_message(chat_id, "收到指令，开始检测失效账号~")
                    reply = handle_command(text, chat_id)
                if reply:
                    send_message(chat_id, reply)
        except Exception as e:
            log("loop error", type(e).__name__, str(e)[:300])
            time.sleep(5)

if __name__ == "__main__":
    main()
