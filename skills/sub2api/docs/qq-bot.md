# QQ Bot Template

`templates/` ships an additional QQ operations bot template for Sub2API deployments, alongside the original Telegram bot. Both backends share the same business logic via `bot_core.py` — only the transport layer differs.

## Files

- `bot_core.py` — transport-agnostic command handlers (psql, login, `cmd_status`, `cmd_accounts`, import, confirm, backup, restart, update, …). Imported by both backends.
- `telegram-bot.py` — Telegram long-polling transport.
- `qq-bot.py` — QQ Open Platform v2 WebSocket Gateway transport.

## QQ Bot Endpoints

QQ Open Platform v2 endpoints used by the bot:

| Purpose | URL |
| --- | --- |
| AppAccessToken (auth) | `https://bots.qq.com/app/getAppAccessToken` |
| OpenAPI (production) | `https://api.sgroup.qq.com/` |
| OpenAPI (sandbox) | `https://sandbox.api.sgroup.qq.com/` |
| WebSocket Gateway | `wss://api.sgroup.qq.com/websockets` (auto-discovered via `/gateway`) |

Reference: <https://bot.q.qq.com/wiki/develop/api-v2/>

## Sensitive Data

Do not commit real values. Replace placeholders at deployment time through environment variables or a deployment-local secrets JSON file:

- `QQ_APP_ID`
- `QQ_APP_SECRET`
- `SUB2API_BASE_URL`
- `SUB2API_ADMIN_EMAIL`
- `SUB2API_ADMIN_PASSWORD_B64`
- `SUB2API_BOT_ALLOWED_CHAT_IDS`
- `SUB2API_BOT_SECRETS_FILE`
- `SUB2API_DB_NAME` / `SUB2API_DB_USER`
- `SUB2API_DEFAULT_PROXY_ID`
- `SUB2API_UPDATER_SCRIPT`

## Commands

QQ Bot uses the same command set as the Telegram bot. In channels / groups, mention the bot first, then send the command; in C2C (private), send the command directly.

- `/help` — show help.
- `/status` — combined status, usage, limits and balance.
- `/accounts` — account list and routing state.
- `/models` — model mappings and recently requested models.
- `/channels` — channel and group overview.
- `/tokens` — API token quota and usage, with keys masked.
- `/importhelp` — account file import instructions.
- `/pending` — show pending confirmation-protected operation.
- `/confirm <code>` — execute pending operation.
- `/cancel` — cancel pending operation.
- `/backup` — create a local backup.
- `/restart bot|sub2api` — restart a service after confirmation.
- `/debug` — health checks and log summary.
- `/update` — check for updates; reply “already up to date” when current, otherwise ask for confirmation.

## Whitelist Format

`SUB2API_BOT_ALLOWED_CHAT_IDS` accepts a comma-separated list. QQ entries may be:

- `channel:<channel_id>` — QQ guild channel
- `group:<group_openid>` — QQ group
- `c2c:<user_openid>` — QQ C2C (private)
- Bare openid / channel id is also accepted.

## Transport Notes

- The QQ bot subscribes to `PUBLIC_GUILD_MESSAGES` (1<<30), `GROUP_AT_MESSAGE` (1<<25), `INTERACTION` (1<<26) and `DIRECT_MESSAGE` (1<<12) intents. Intents requiring private-domain approval (e.g. all-channel message content) are intentionally **not** subscribed by default.
- Button-based confirm/restart UIs require a reviewed keyboard template on the QQ platform. The QQ backend falls back to text-based confirmation codes (`/confirm <code>`), so the confirmation-protected controls remain safe.
- File/account import over QQ requires a media-upload flow (`msg_type=7`); the current template focuses on the command surface and will reject unsupported attachments with a clear message.

## Account Import

Same JSON/TXT format and archive rules as the Telegram bot — see [`telegram-bot.md`](telegram-bot.md). When QQ media upload is wired in, the same `bot_core.handle_document_payload` is reused end-to-end.

## Control Safety

Same confirmation-code model as the Telegram bot. `/restart bot|sub2api` and `/update` produce a 6-digit confirmation code; send `/confirm <code>` within 5 minutes, or `/cancel`.
