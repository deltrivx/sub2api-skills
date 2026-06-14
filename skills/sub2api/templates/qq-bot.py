#!/usr/bin/env python3
"""
Sub2API QQ Bot 传输层（QQ 开放平台 v2 / 频道 & 群机器人 WebSocket Gateway）。

本文件只负责：
  - 从 QQ 开放平台获取 AppAccessToken（https://bots.qq.com/app/getAppAccessToken）
  - 通过 WebSocket Gateway 接收 AT_MESSAGE / C2C_MESSAGE / GROUP_AT_MESSAGE 事件
  - 调用 OpenAPI 回复消息（/messages、/v2/groups/{group_openid}/messages 等）
  - 把消息/文件路由到 bot_core.handle_command
  - 实现 QQBackend 抽象（按钮、立即回复、文件下载）供 bot_core 使用

业务命令（psql、login_sub2api、cmd_status 等）全部在 bot_core.py 中实现，
与 IM 平台解耦，与 telegram-bot.py 共用同一份逻辑。

QQ 文档参考：https://bot.q.qq.com/wiki/develop/api-v2/
  - 凭证：https://bots.qq.com/app/getAppAccessToken （正式/沙箱通用）
  - 正式 OpenAPI：https://api.sgroup.qq.com/
  - 沙箱 OpenAPI：https://sandbox.api.sgroup.qq.com/
  - WebSocket Gateway：wss://api.sgroup.qq.com/websockets （从 /gateway 获取）

敏感配置：全部通过环境变量或 SECRETS_FILE 注入，仓库内只含占位符。
"""
import json, os, time, urllib.request, urllib.error, threading, queue

import bot_core
from bot_core import log, load_secrets, ALLOWED_CHAT_IDS, COMMANDS, handle_command

# OpenAPI 基址。SUB2API_QQ_SANDBOX=1 切换到沙箱。
SANDBOX = str(os.environ.get("SUB2API_QQ_SANDBOX", "")).lower() in ("1", "true", "yes")
OPENAPI_BASE = os.environ.get(
    "SUB2API_QQ_OPENAPI_BASE",
    "https://sandbox.api.sgroup.qq.com" if SANDBOX else "https://api.sgroup.qq.com",
).rstrip("/")
ACCESS_TOKEN_URL = os.environ.get(
    "SUB2API_QQ_ACCESS_TOKEN_URL",
    "https://bots.qq.com/app/getAppAccessToken",
)

# Token 缓存
_token_lock = threading.Lock()
_token_cache = {"access_token": "", "expires_at": 0.0}


def _get_app_access_token():
    """调用 https://bots.qq.com/app/getAppAccessToken 获取 access_token。"""
    with _token_lock:
        now = time.time()
        if _token_cache["access_token"] and _token_cache["expires_at"] - now > 60:
            return _token_cache["access_token"]
        secrets = load_secrets()
        app_id = secrets.get("qq_app_id") or os.environ.get("QQ_APP_ID", "<qq-app-id>")
        app_secret = secrets.get("qq_app_secret") or os.environ.get("QQ_APP_SECRET", "<qq-app-secret>")
        body = json.dumps({"appId": app_id, "clientSecret": app_secret}).encode()
        req = urllib.request.Request(
            ACCESS_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        token = data.get("access_token") or data.get("accessToken") or ""
        expire = int(data.get("expires_in") or data.get("expire") or 7200)
        if not token:
            raise RuntimeError("getAppAccessToken 未返回 access_token: " + json.dumps(data, ensure_ascii=False)[:300])
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + expire
        log("app access token refreshed, expires_in", expire)
        return token


def qq_api(method, path, payload=None, timeout=20, content_type="application/json"):
    """调用 OpenAPI。method GET/POST/PUT。返回解析后的 JSON。"""
    token = _get_app_access_token()
    url = OPENAPI_BASE + path
    data = None
    headers = {"Authorization": "QQBot " + token}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        raise RuntimeError("QQ OpenAPI HTTP %s %s -> %d: %s" % (method, path, e.code, raw[:400]))
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw[:500]}


def _chunk_text(text, limit=1800):
    """按段落切分长文本，尽量不破坏 markdown 结构。
    QQ markdown 单条建议 < 2000 字符，这里保守用 1800。"""
    if text is None:
        return []
    text = str(text)
    if len(text) <= limit:
        return [text]
    # 按双换行（段落）切，累积到接近 limit 就输出一段
    paras = text.split("\n\n")
    parts = []
    cur = ""
    for p in paras:
        if len(cur) + len(p) + 2 > limit and cur:
            parts.append(cur)
            cur = p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur:
        parts.append(cur)
    # 如果单段仍超长（如超长表格/代码块），硬切
    final = []
    for p in parts:
        while len(p) > limit:
            final.append(p[:limit])
            p = p[limit:]
        if p:
            final.append(p)
    return final


def _to_markdown(text):
    """把 bot_core 返回的纯文本包装成更友好的 markdown。
    bot_core 的回复格式：
      - 标题行（如"账号列表："、"Sub2API 综合状态："）→ 加粗
      - "- xxx" 列表项 → 保持
      - "key: value" → 保持
      - "/cmd - 说明" → 保持
    这里做一个轻量增强：首行若像标题（以"："结尾或全中文短句）则加粗。"""
    if not text:
        return text
    lines = text.split("\n")
    out = []
    first_non_empty = True
    for line in lines:
        s = line.strip()
        # 首个非空行且像标题（≤30 字、以：结尾 或 是命令说明首行）
        if first_non_empty and s and len(s) <= 40 and (s.endswith("：") or s.endswith(":")):
            out.append("**" + s + "**")
            first_non_empty = False
            continue
        if first_non_empty and s:
            first_non_empty = False
        out.append(line)
    return "\n".join(out)


class QQBackend:
    """实现 bot_core 期望的 Backend 抽象。
    C2C/群聊优先用 markdown（msg_type=2，2026/04 后对所有机器人开放，无需模板）；
    频道仍用纯文本（markdown 需内邀）。
    markdown 发送失败时自动降级为纯文本（msg_type=0）。"""

    def __init__(self, channel_id=None, message_id=None):
        self.channel_id = channel_id
        self.message_id = message_id

    def send_message(self, chat_id, text, buttons=None):
        target = chat_id if chat_id is not None else self.channel_id
        if target is None:
            return None
        suffix = ""
        if buttons == "restart":
            suffix = "\n\n（请直接回复：/restart bot 或 /restart sub2api）"
        full = (text or "") + suffix
        kind = target.partition(":")[0]
        # C2C/群聊用 markdown，频道用纯文本
        use_md = kind in ("c2c", "group")
        md_content = _to_markdown(full) if use_md else full
        for i, part in enumerate(_chunk_text(md_content if use_md else full)):
            # msg_id 只在第一条用（被动回复 5 分钟限制，多段时后续用 event_id 或省略）
            mid = self.message_id if i == 0 else None
            if use_md:
                reply_qq_message(target, part, mid, prefer_markdown=True)
            else:
                reply_qq_message(target, part, mid)
        return None

    def restart_buttons(self):
        return "restart"


# QQ 消息类型常量
MSG_TYPE_TEXT = 0
MSG_TYPE_MARKDOWN = 2  # markdown（自定义 content，2026/04 后单聊/群聊对所有机器人开放）
MSG_TYPE_RICH_MEDIA = 7
MSG_TYPE_ARK = 9  # ark 方块消息


def reply_qq_message(channel_id, content, msg_id=None, msg_type=MSG_TYPE_TEXT, prefer_markdown=False):
    """回复消息。
    channel_id 形如 'channel:xxx'（频道）/ 'group:xxx'（群）/ 'c2c:xxx'（私聊）。
    prefer_markdown=True 时 C2C/群聊优先发 markdown(msg_type=2)，失败降级为纯文本(msg_type=0)。"""
    if not channel_id:
        return None
    kind, _, oid = channel_id.partition(":")
    attempt_md = prefer_markdown and kind in ("c2c", "group") and content

    def _build_payload(mt, body):
        """构造各场景 payload。mt=消息类型, body=内容(markdown 时放 markdown.content)"""
        if kind == "channel":
            if mt == MSG_TYPE_MARKDOWN:
                base = {"markdown": {"content": body}}
            else:
                base = {"content": body}
            if msg_id:
                base["msg_id"] = msg_id
            return base
        if kind == "group":
            p = {"group_openid": oid, "msg_type": mt}
            if mt == MSG_TYPE_MARKDOWN:
                p["markdown"] = {"content": body}
            else:
                p["content"] = body
            if msg_id:
                p["msg_id"] = msg_id
            return p
        if kind == "c2c":
            p = {"msg_type": mt, "openid": oid}
            if mt == MSG_TYPE_MARKDOWN:
                p["markdown"] = {"content": body}
            else:
                p["content"] = body
            if msg_id:
                p["msg_id"] = msg_id
            return p
        return None

    # 尝试 markdown（msg_type=2）
    if attempt_md:
        try:
            payload = _build_payload(MSG_TYPE_MARKDOWN, content)
            if payload:
                resp = qq_api("POST", _endpoint_for(kind, oid), payload)
                if resp is not None:
                    return resp
        except Exception as e:
            log("markdown send failed, fallback to text:", type(e).__name__, str(e)[:150])

    # 降级/默认：纯文本
    try:
        payload = _build_payload(MSG_TYPE_TEXT, content)
        if payload:
            return qq_api("POST", _endpoint_for(kind, oid), payload)
    except Exception as e:
        log("reply_qq_message FAILED", kind, "oid=", oid[:16], type(e).__name__, str(e)[:250])
    return None


def _endpoint_for(kind, oid):
    if kind == "channel":
        return "/channels/%s/messages" % oid
    if kind == "group":
        return "/v2/groups/%s/messages" % oid
    if kind == "c2c":
        return "/v2/users/%s/messages" % oid
    return None


# ============ WebSocket Gateway ============
# 使用纯 socket 实现 WS 客户端，避免引入 websocket 依赖。
import socket, hashlib, base64, os as _os, struct, ssl


def _ws_connect(url):
    """建立 WebSocket 连接。返回 (sock, ws_send, ws_recv)。
    ws_send(payload, opcode=1) / ws_recv() -> payload bytes（文本帧）。"""
    if url.startswith("wss://"):
        host_part = url[len("wss://"):]
        default_port = 443
        use_tls = True
    elif url.startswith("ws://"):
        host_part = url[len("ws://"):]
        default_port = 80
        use_tls = False
    else:
        raise ValueError("unsupported gateway url: " + url)
    if "/" in host_part:
        host_port, path = host_part.split("/", 1)
        path = "/" + path
    else:
        host_port = host_part
        path = "/"
    if ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        port = int(port_s)
    else:
        host = host_port
        port = default_port

    raw = socket.create_connection((host, port), timeout=30)
    if use_tls:
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(raw, server_hostname=host)
    else:
        sock = raw

    key = base64.b64encode(_os.urandom(16)).decode()
    req = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "User-Agent: sub2api-qq-bot/1.0\r\n"
        "\r\n"
    ) % (path, host, key)
    sock.sendall(req.encode())
    # 读取握手响应头。注意：握手响应 + 后续 WebSocket 帧可能在同一次 recv 里返回，
    # 必须保留 \r\n\r\n 之后的剩余字节作为 ws_recv 的预读缓冲，否则会丢失第一帧前段。
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("ws handshake closed")
        buf += chunk
    header, leftover = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in header.split(b"\r\n")[0]:
        raise RuntimeError("ws handshake failed: " + header.decode(errors="replace")[:200])
    # leftover 是握手响应之后已读到的 WebSocket 帧起始字节，预存到 _pread
    _pread = [leftover]

    # 启用 TCP keepalive，避免长连接被中间设备/服务端判定为空闲而断开。
    # 不设 read timeout —— 让 ws_recv 阻塞等待，心跳线程独立维持连接活性。
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except Exception:
        pass
    sock.settimeout(None)  # 阻塞模式，靠 keepalive + 心跳维持

    def _recv_exact(n):
        """先消费 _pread 预读缓冲，不够再从 socket 读。"""
        out = b""
        if _pread[0]:
            take = _pread[0][:n]
            _pread[0] = _pread[0][len(take):]
            out = take
        while len(out) < n:
            chunk = sock.recv(n - len(out))
            if not chunk:
                return None
            out += chunk
        return out

    # 启用 TCP keepalive，避免长连接被中间设备/服务端判定为空闲而断开。
    # 不设 read timeout —— 让 ws_recv 阻塞等待，心跳线程独立维持连接活性。
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except Exception:
        pass
    sock.settimeout(None)  # 阻塞模式，靠 keepalive + 心跳维持


    def ws_send(payload, opcode=0x1):
        if isinstance(payload, str):
            payload = payload.encode()
        header = bytes([0x80 | opcode])
        mask = _os.urandom(4)
        length = len(payload)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", length)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        sock.sendall(header + masked)

    def ws_recv():
        """读取一帧（不支持分片重组，QQ 心跳/事件 payload < 64KB）。"""
        h = _recv_exact(2)
        if not h:
            return None
        b1, b2 = h[0], h[1]
        opcode = b1 & 0x0F
        masked = bool(b2 & 0x80)
        length = b2 & 0x7F
        if length == 126:
            ext = _recv_exact(2)
            length = struct.unpack(">H", ext)[0]
        elif length == 127:
            ext = _recv_exact(8)
            length = struct.unpack(">Q", ext)[0]
        mask = _recv_exact(4) if masked else b""
        payload = _recv_exact(length) if length else b""
        if masked and payload:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if opcode == 0x9:  # ping
            ws_send(payload, opcode=0xA)
            return ws_recv()
        if opcode == 0x8:  # close
            return None
        return payload

    return sock, ws_send, ws_recv


_SEQ = [0]
_SEQ_LOCK = threading.Lock()


def _next_seq():
    with _SEQ_LOCK:
        _SEQ[0] = (_SEQ[0] + 1) % 65535
        if _SEQ[0] == 0:
            _SEQ[0] = 1
        return _SEQ[0]


def _identify(ws_send):
    secrets = load_secrets()
    token = _get_app_access_token()
    app_id = int(secrets.get("qq_app_id") or os.environ.get("QQ_APP_ID", "0") or "0")
    payload = {
        "op": 2,
        "d": {
            "token": "QQBot " + token,
            "intents": _intents(),
            "shard": [0, 1],
            "properties": {
                "$os": "linux",
                "$browser": "sub2api-qq-bot",
                "$device": "sub2api-qq-bot",
            },
        },
    }
    if app_id:
        payload["d"]["app_id"] = app_id
    ws_send(json.dumps(payload))


def _intents():
    """订阅意图位掩码：
    GUILD_MESSAGES(1<<9) 频道消息（需私域）、PUBLIC_GUILD_MESSAGES(1<<30) 频道@消息、
    DIRECT_MESSAGE(1<<12) 私信、INTERACTION(1<<26) 交互、GROUP_AT_MESSAGE(1<<25) 群@消息、
    C2C_GROUP_AT_MESSAGES(1<<25)。
    默认订阅公开频道 @ + 群 @ + C2C + 交互（无需白名单的）。"""
    return (1 << 30) | (1 << 25) | (1 << 26) | (1 << 12)


def _send_heartbeat(ws_send, seq):
    ws_send(json.dumps({"op": 1, "d": seq}))


def _dispatch(payload, ws_send):
    """处理服务端事件（op=0 Dispatch）。"""
    t = payload.get("t")
    d = payload.get("d") or {}
    s = payload.get("s")
    log("dispatch event", t, "seq", s)
    if t in ("AT_MESSAGE", "MESSAGE_AUDIT_REJECT", "GROUP_AT_MESSAGE", "C2C_MESSAGE_CREATE", "AT_MESSAGE_CREATE"):
        _handle_message_event(t, d)
    elif t == "READY":
        log("qq bot ready", json.dumps(d.get("user", {}).get("id", ""), ensure_ascii=False)[:100])
    elif t == "RESUMED":
        log("qq bot resumed")


def _handle_message_event(event_type, d):
    """处理收到的消息事件，路由到 bot_core。"""
    raw_content = (d.get("content") or "").strip()
    content = _strip_at_mention(raw_content)
    msg_id = d.get("id") or d.get("message_id") or ""

    if event_type in ("AT_MESSAGE", "AT_MESSAGE_CREATE"):
        channel_id = d.get("channel_id") or ""
        target = "channel:" + channel_id
        author = d.get("author") or {}
        user_id = author.get("id") or author.get("member_openid") or ""
    elif event_type == "GROUP_AT_MESSAGE":
        group_openid = d.get("group_openid") or ""
        target = "group:" + group_openid
        author = d.get("author") or {}
        user_id = author.get("member_openid") or author.get("id") or ""
    elif event_type == "C2C_MESSAGE_CREATE":
        author = d.get("author") or {}
        user_openid = author.get("user_openid") or d.get("user_openid") or ""
        target = "c2c:" + user_openid
        user_id = user_openid
    else:
        return

    log("msg event", event_type, "target=", target, "user=", user_id[:16], "content=", repr(content[:60]), "msg_id=", msg_id[:24])

    # 白名单校验
    if ALLOWED_CHAT_IDS and target not in ALLOWED_CHAT_IDS and user_id not in ALLOWED_CHAT_IDS:
        log("ignore unauthorized qq chat", target, user_id)
        return

    # 只处理命令（以 / 开头）
    if not content.startswith("/"):
        log("skip non-command:", repr(content[:40]))
        return

    backend = QQBackend(target, msg_id)
    try:
        reply = handle_command(content, target, backend)
    except Exception as e:
        log("handle_command error", type(e).__name__, str(e)[:200])
        reply = "执行失败：" + type(e).__name__ + ": " + str(e)[:300]
    if reply:
        log("sending reply, len=", len(reply))
        backend.send_message(target, reply)
    else:
        log("no reply returned from handle_command")


def _strip_at_mention(text):
    """移除 QQ @机器人 前缀。"""
    if not text:
        return text
    import re
    # 频道：<@!123456> 或 <@123456>
    text = re.sub(r"^<@!?[0-9]+>\s*", "", text)
    # 群/私信：<qqbot-at-user id="..." /> 或 <@user openid=...>
    text = re.sub(r"^<qqbot-at-user[^>]*/>\s*", "", text)
    text = re.sub(r"^<@\S+>\s*", "", text)
    return text.strip()


def main():
    log("started (qq backend, sandbox=%s, openapi=%s)" % (SANDBOX, OPENAPI_BASE))
    backoff = 5
    while True:
        try:
            gateway = os.environ.get("SUB2API_QQ_GATEWAY", "")
            if not gateway:
                # 通过 OpenAPI 获取 WSS 地址
                gw_info = qq_api("GET", "/gateway")
                gateway = gw_info.get("url") or "wss://api.sgroup.qq.com/websockets"
            log("connecting qq gateway", gateway)
            sock, ws_send, ws_recv = _ws_connect(gateway)

            # 1) Hello (op=10)
            hello_raw = ws_recv()
            log("hello_raw len=", len(hello_raw) if hello_raw else 0, "head=", (hello_raw[:80] if hello_raw else b""))
            if not hello_raw:
                raise RuntimeError("gateway closed before hello")
            try:
                hello = json.loads(hello_raw.decode(errors="replace"))
            except Exception as e:
                log("hello json parse error", type(e).__name__, "raw_hex=", hello_raw[:80].hex())
                raise
            heartbeat_interval = (hello.get("d") or {}).get("heartbeat_interval", 30000)
            log("hello heartbeat_interval", heartbeat_interval)

            # 2) Identify (op=2)
            _identify(ws_send)

            # 3) 启动心跳线程
            last_seq = [None]
            stop_heartbeat = threading.Event()

            def heartbeat_loop():
                while not stop_heartbeat.is_set():
                    if stop_heartbeat.wait(heartbeat_interval / 1000.0):
                        break
                    try:
                        _send_heartbeat(ws_send, last_seq[0])
                    except Exception as e:
                        log("heartbeat error", type(e).__name__, str(e)[:120])
                        return

            hb = threading.Thread(target=heartbeat_loop, daemon=True)
            hb.start()

            # 4) 事件循环
            while True:
                raw = ws_recv()
                if raw is None:
                    raise RuntimeError("gateway connection closed")
                try:
                    payload = json.loads(raw.decode(errors="replace"))
                except Exception as e:
                    log("ws frame json parse error", type(e).__name__, "len=", len(raw), "head=", raw[:40])
                    continue
                op = payload.get("op")
                if "s" in payload and payload.get("s") is not None:
                    last_seq[0] = payload.get("s")
                if op == 0:  # Dispatch
                    _dispatch(payload, ws_send)
                elif op == 11:  # Heartbeat ACK
                    pass  # 心跳 ack 不打印，减少日志噪音
                elif op == 10:  # Re Hello (不应出现)
                    pass
                elif op == 9:  # Invalid Session -> re-identify
                    log("invalid session, re-identifying")
                    _identify(ws_send)
                elif op == 1:  # Server->Client heartbeat (rare)
                    _send_heartbeat(ws_send, last_seq[0])
                else:
                    log("unknown op", op, json.dumps(payload, ensure_ascii=False)[:200])

            stop_heartbeat.set()
            sock.close()
            backoff = 5
        except Exception as e:
            log("qq gateway loop error", type(e).__name__, str(e)[:300])
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    main()
