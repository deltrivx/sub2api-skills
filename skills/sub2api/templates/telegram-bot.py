#!/usr/bin/env python3
"""
Sub2API Telegram Bot 传输层。

本文件只负责：
  - Telegram getUpdates 长轮询主循环
  - Telegram API 调用（sendMessage / answerCallbackQuery / getFile / setMyCommands 等）
  - 把消息/文件路由到 bot_core.handle_command / handle_document_payload
  - 实现 TelegramBackend 抽象（按钮 markup / 立即回复）供 bot_core 使用

业务命令（psql、login_sub2api、cmd_status 等）全部在 bot_core.py 中实现，
与 IM 平台解耦。这样 QQ / 其它后端可以复用同一份业务逻辑。

敏感配置：全部通过环境变量或 SECRETS_FILE 注入，仓库内只含占位符。
"""
import json, os, time, urllib.request, pathlib

import bot_core
from bot_core import log, load_secrets, ALLOWED_CHAT_IDS, COMMANDS, handle_command, handle_document_payload


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


def tg_download_file(file_id):
    meta=tg_call("getFile", {"file_id": file_id}, timeout=30)
    path=meta.get("result",{}).get("file_path")
    if not path: raise RuntimeError("Telegram 未返回 file_path")
    token=load_secrets()["telegram_bot_token"]
    url="https://api.telegram.org/file/bot"+token+"/"+path
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def confirm_markup(code):
    return {"inline_keyboard": [[
        {"text": "确认执行", "callback_data": "confirm:" + code},
        {"text": "取消", "callback_data": "cancel:" + code},
    ]]}


def restart_target_markup():
    return {"inline_keyboard": [[
        {"text": "Bot", "callback_data": "restart_select:bot"},
        {"text": "Sub2API", "callback_data": "restart_select:sub2api"},
    ]]}


class TelegramBackend:
    """实现 bot_core 期望的 Backend 抽象，用于按钮交互和立即回复。
    chat_id 为 None 时使用 _default_chat_id（在 cmd_update 立即提示场景下使用）。"""

    def __init__(self, chat_id=None):
        self._default_chat_id = chat_id

    def send_message(self, chat_id, text, buttons=None):
        cid = chat_id if chat_id is not None else self._default_chat_id
        if cid is None:
            return None
        if buttons == "restart":
            markup = restart_target_markup()
        elif isinstance(buttons, str) and buttons.startswith("confirm:"):
            markup = confirm_markup(buttons.split(":", 1)[1])
        elif buttons is None:
            markup = None
        else:
            markup = buttons
        return send_message(cid, text, markup)

    def restart_buttons(self):
        return "restart"


def handle_document_message(msg):
    doc=msg.get("document") or {}
    file_name=doc.get("file_name") or "account.json"
    mime_type = (doc.get("mime_type") or "").lower()
    raw=tg_download_file(doc.get("file_id"))
    return handle_document_payload(raw, file_name, mime_type)


def get_offset():
    try:
        return int(pathlib.Path(bot_core.OFFSET_FILE).read_text().strip())
    except Exception:
        return None


def set_offset(offset):
    pathlib.Path(bot_core.OFFSET_FILE).write_text(str(offset))


def setup_bot_menu():
    commands = [{"command": "help", "description": "查看帮助"}] + [
        {"command": k[1:], "description": v} for k, v in COMMANDS.items() if k != "/help"
    ]
    tg_call("deleteWebhook", {"drop_pending_updates": False})
    scopes = [
        {"type": "default"},
        {"type": "all_private_chats"},
    ] + [{"type": "chat", "chat_id": int(chat_id) if str(chat_id).isdigit() else chat_id} for chat_id in ALLOWED_CHAT_IDS]
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


def cmd_restart_select(target, chat_id):
    from bot_core import restart_target_command, make_confirm, pending_load
    summary, command = restart_target_command(target)
    if not summary:
        return "不支持的服务。"
    reply = make_confirm("restart", summary, command)
    data = pending_load() or {}
    code = data.get("code", "")
    send_message(chat_id, reply, confirm_markup(code) if code else None)
    return None


def main():
    setup_bot_menu()
    log("started (telegram backend)")
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
                    if data.startswith("restart_select:"):
                        target = data.split(":", 1)[1]
                        answer_callback_query(cb_id, "已选择")
                        cmd_restart_select(target, chat_id)
                    elif data.startswith("confirm:"):
                        code = data.split(":", 1)[1]
                        answer_callback_query(cb_id, "开始执行")
                        send_message(chat_id, handle_command("/confirm " + code, chat_id))
                    elif data.startswith("cancel:"):
                        answer_callback_query(cb_id, "已取消")
                        send_message(chat_id, handle_command("/cancel", chat_id))
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
                backend = TelegramBackend(chat_id)
                reply = None
                if msg.get("document"):
                    doc = msg.get("document") or {}
                    file_name = doc.get("file_name") or ""
                    mime_type = (doc.get("mime_type") or "").lower()
                    if bot_core.is_import_archive_file(file_name, mime_type):
                        send_message(chat_id, "收到压缩文件，开始解压并导入~")
                    elif bot_core.is_import_data_file(file_name, mime_type):
                        send_message(chat_id, "收到账号文件，开始导入~")
                    else:
                        send_message(chat_id, "收到文件，正在检查格式~")
                    reply = handle_document_message(msg)
                elif text.startswith("/"):
                    reply = handle_command(text, chat_id, backend)
                if reply:
                    send_message(chat_id, reply)
        except Exception as e:
            log("loop error", type(e).__name__, str(e)[:300])
            time.sleep(5)


if __name__ == "__main__":
    main()
