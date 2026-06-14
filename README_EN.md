# Sub2API Skills and Telegram / QQ Operations Bots

This repository provides an assistant skill for Sub2API, **dual-backend** operations bot templates (Telegram **and** QQ), and an optional Docker sidecar deployment. It is designed to add diagnostics, account import, backup, restart, and update workflows without modifying the official Sub2API image or container.

Both bots share one business-logic module (`bot_core.py`) — only the transport differs:

- Telegram bot (`telegram-bot.py`): long-polling via `getUpdates`.
- QQ bot (`qq-bot.py`): WebSocket Gateway of the [QQ Open Platform v2](https://bot.q.qq.com/wiki/develop/api-v2/), supporting guild channel `@`, group `@`, and C2C private messages.

> Security notice: all URLs, tokens, passwords, chat IDs, and account keys in this repository are placeholders or environment variables. Do not commit real credentials to GitHub.

## 1. Installation

```bash
npx skills add https://github.com/deltrivx/sub2api-skills --skill sub2api
```

## 2. Skill Configuration

Use environment variables. Avoid committing `.env` files.

```bash
export SUB2API_BASE_URL="https://<your-sub2api-host>"
export SUB2API_ACCESS_TOKEN="<your-token>"
export SUB2API_USER_ID="<your-user-id>"
```

## 3. Skill Actions

| Action | Usage | Description |
| --- | --- | --- |
| `accounts` | `/sub2api accounts` | List accounts |
| `groups` | `/sub2api groups` | List groups |
| `balance` | `/sub2api balance` | Show balance/account information |
| `tokens` | `/sub2api tokens` | List API tokens with masking |
| `create-token` | `/sub2api create-token <name>` | Create an API token |
| `switch-group` | `/sub2api switch-group <token_id> <group>` | Switch a token to another group |
| `copy-token` | `/sub2api copy-token <token_id>` | Copy the real key to clipboard without showing it in chat |
| `apply-token` | `/sub2api apply-token <token_id> <file>` | Safely inject a key into a config file |
| `exec-token` | `/sub2api exec-token <token_id> -- <cmd>` | Run a command with a temporary injected key |
| `scan-config` | `/sub2api scan-config <file>` | Inspect config files with best-effort redaction |
| `help` | `/sub2api help <question>` | Ask usage questions about Sub2API |

## 4. Telegram Operations Bot

Template files:

- Transport-agnostic business logic: `skills/sub2api/templates/bot_core.py` (shared with QQ)
- Telegram transport: `skills/sub2api/templates/telegram-bot.py`

The bot supports both host-level deployments and Docker sidecar deployments. Host-level deployment is suitable when Sub2API runs as a binary, systemd service, or another local host service. Docker sidecar deployment is suitable for Docker-based Sub2API installations and keeps the official Sub2API image and container clean.

### 4.1. QQ Operations Bot

The QQ bot reuses every business command from `bot_core.py` — only the transport differs.

- QQ transport: `skills/sub2api/templates/qq-bot.py`
- QQ docs: [`skills/sub2api/docs/qq-bot.md`](skills/sub2api/docs/qq-bot.md)

QQ Open Platform v2 endpoints used:

| Purpose | URL |
| --- | --- |
| AppAccessToken (auth) | `https://bots.qq.com/app/getAppAccessToken` |
| OpenAPI (production) | `https://api.sgroup.qq.com/` |
| OpenAPI (sandbox) | `https://sandbox.api.sgroup.qq.com/` |
| WebSocket Gateway | `wss://api.sgroup.qq.com/websockets` (auto-discovered via `/gateway`) |

Reference: <https://bot.q.qq.com/wiki/develop/api-v2/>

The QQ backend subscribes to public guild-channel `@` messages, group `@` messages, C2C private messages, and interaction events. Inline-keyboard confirmation UIs require a reviewed keyboard template on the QQ platform, so the QQ backend falls back to the same `/confirm <code>` text confirmation codes as Telegram — control-command safety is identical.

### 4.1.1 QQ Bot Sandbox and Usage Scenarios

QQ bots start in the **sandbox environment** (not yet published). You must register test targets under [QQ Open Platform → Sandbox configuration](https://q.qq.com/qqbot/#/developer/sandbox) before the bot can exchange messages with them:

- **Message list (C2C private chat)**: add a member on the sandbox page; the bot then appears in that member's QQ message list and accepts direct commands.
- **QQ group**: select a test group (admin must be the group owner/admin, ≤ 20 members); the owner adds the bot via "Settings → Group bots".
- **QQ guild channel**: bind a test channel the same way.

When adding commands under "Function configuration → Commands", the **usage scenario** checkboxes are gated by the sandbox config: any scenario whose target was not configured in the sandbox is disabled (`usescene-item-forbit`) and the command cannot be saved. Configure at least one test member to unlock the "Message list" scenario first.

### 4.1.2 QQ Bot Rich-text Replies

In C2C and group scenarios, the QQ backend prefers **Markdown messages** (`msg_type=2`). Since 2026/04/23, custom Markdown is available to all bots in private/group chats without a separate template approval (see [Markdown message docs](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/markdown.html)).

- If the first line of a reply looks like a title (a short line ending with `：` or `:`), it is automatically bolded.
- Long replies are split by paragraph to preserve Markdown structure.
- If Markdown delivery fails (rate limit, content filtered), the backend falls back to plain text (`msg_type=0`) so reachability is preserved.
- Guild-channel Markdown requires an invite-gated approval, so the channel backend still uses plain text.

### 4.1.3 Dual-backend Mode (QQ + Telegram simultaneously)

Set `SUB2API_BOT_BACKEND=both` to run **both the QQ Bot and the Telegram Bot in a single container**, sharing the same `bot_core.py` business logic and Sub2API backend.

How it works:

- In `both` mode, `entrypoint.sh` launches `sub2api_qq_bot.py` and `sub2api_telegram_bot.py` as two background processes.
- **Fault tolerance**: either process exiting does not immediately kill the other. For example, if Telegram exits due to a network issue, QQ keeps serving, and vice versa. The container only restarts (`restart: always`) when both processes have exited.
- `SUB2API_BOT_SECRETS_FILE` in `both` mode contains both `qq_app_id`/`qq_app_secret` and `telegram_bot_token`.
- The whitelist `SUB2API_BOT_ALLOWED_CHAT_IDS` lists both kinds of IDs, comma-separated. Telegram's `setup_bot_menu` automatically skips non-numeric QQ openids, avoiding 400 errors against the Telegram API.

Use cases:

- Cover both QQ and Telegram users from a single container, reducing resource usage.
- Commands are identical on both sides (`/help`, `/status`, `/accounts`, …) because they share `bot_core.py`.
- Single-backend mode (`telegram` or `qq`) is still available if you only need one.

### Read-only Diagnostics

- `/status` — combined status, usage, limits, and balance
- `/accounts` — account list and routing state
- `/models` — model mappings and recently requested models
- `/channels` — channel and group overview
- `/tokens` — API token quota and usage with masked keys
- `/debug` — health checks and log summary

### Import and Maintenance

- `/importhelp` — account-file import help
- Send `.json` / `.txt` files, or `.zip` / `.tar` / `.tar.gz` / `.tgz` archives — safely extract, scan account files, match or create groups, import accounts, and return masked metadata
- `/backup` — create a local backup

### Confirmation-protected Controls

These commands require confirmation before execution:

- `/pending` — show pending operation
- `/confirm <code>` — confirm operation
- `/cancel` — cancel operation
- `/restart` — first shows `Bot` / `Sub2API` buttons, then confirm/cancel buttons
- `/restart bot|sub2api` — directly selects a target and asks for confirmation
- `/update` — immediately sends an update-check notice; host-level deployments use the configured updater, while Docker deployments compare the official image digest before asking for confirmation

## 5. Account JSON Import Format

A single object or an array is supported:

```json
[
  {
    "name": "<account-name>",
    "platform": "openai",
    "group": "<group-name>",
    "type": "api_key",
    "api_key": "<api-key>",
    "priority": 50,
    "concurrency": 3
  },
  {
    "name": "<anthropic-account>",
    "provider": "anthropic",
    "group_name": "<anthropic-group>",
    "credentials": {
      "api_key": "<api-key>"
    }
  }
]
```

Import behavior:

- Detects `platform/provider/service/type`
- Processes only `.json` / `.txt` files inside archives, with file count, single-file size, and extracted-size limits
- Creates or matches groups automatically
- Writes `accounts` and `account_groups`
- Writes `scheduler_outbox`
- Defaults imported accounts to `schedulable=false`
- Replies with credential field names only, never secret values

## 6. Host-level Bot Deployment

Host-level deployment is suitable when Sub2API runs directly on the host.

```bash
sudo install -m 700 skills/sub2api/templates/telegram-bot.py /opt/sub2api-telegram-bot.py
sudo install -m 600 docker/sub2api-skill/sub2api-skill.env.example /etc/sub2api-bot.env
sudo editor /etc/sub2api-bot.env
sudo systemctl daemon-reload
sudo systemctl enable --now sub2api-telegram-bot
```

For host-level deployments, `/update` calls the script configured by `SUB2API_UPDATER_SCRIPT`. If no update is available, it replies that the installation is already up to date.

## 7. Docker Sidecar Deployment

Docker sidecar deployment is intended for Docker-based Sub2API installations. The bot runs as a separate container and does not write files into the official `weishaw/sub2api:latest` image or container.

Image:

```text
ghcr.io/deltrivx/sub2api-skill:latest
```

Recommended layout:

```text
<docker-root>/sub2api/
  docker-compose.yml
  data/
<docker-root>/sub2api-skill/
  docker-compose.yml
  .env
  config/sub2api-bot-secrets.json
  data/
```

Copy the example files:

```bash
mkdir -p sub2api-skill/config sub2api-skill/data
cp docker/sub2api-skill/docker-compose.yml sub2api-skill/docker-compose.yml
cp docker/sub2api-skill/sub2api-skill.env.example sub2api-skill/.env
```

Edit `sub2api-skill/.env` and set at least:

```env
# Choose backend: telegram | qq | both
SUB2API_BOT_BACKEND=telegram

SUB2API_BASE_URL=http://127.0.0.1:<sub2api-port>
SUB2API_BOT_ALLOWED_CHAT_IDS=<chat-id>
SUB2API_ADMIN_EMAIL=<admin-email>
SUB2API_ADMIN_PASSWORD_B64=<base64-admin-password>
DATABASE_HOST=127.0.0.1
DATABASE_PORT=<postgres-port>
DATABASE_USER=<postgres-user>
DATABASE_PASSWORD=<postgres-password>
DATABASE_DBNAME=sub2api
SUB2API_DEPLOY_DIR=/sub2api-compose
SUB2API_IMAGE=weishaw/sub2api:latest
DOCKER_COMPOSE_CMD=docker compose
```

`SUB2API_BOT_BACKEND` selects which backend starts:

- `telegram`: also set `TELEGRAM_BOT_TOKEN=<telegram-bot-token>`; `SUB2API_BOT_ALLOWED_CHAT_IDS` uses Telegram chat IDs.
- `qq`: also set `QQ_APP_ID=<qq-app-id>` and `QQ_APP_SECRET=<qq-app-secret>` (from [q.qq.com](https://q.qq.com)); `SUB2API_BOT_ALLOWED_CHAT_IDS` uses `channel:<channel_id>` / `group:<group_openid>` / `c2c:<user_openid>` or a bare openid. Set `SUB2API_QQ_SANDBOX=1` for sandbox testing.
- `both`: runs Telegram + QQ simultaneously in one container (see section 4.1.3). Set both `TELEGRAM_BOT_TOKEN` and `QQ_APP_ID`/`QQ_APP_SECRET`; `SUB2API_BOT_ALLOWED_CHAT_IDS` is a comma-separated list of Telegram numeric chat IDs and QQ openids (e.g. `8646289271,72A938D331BF51525291207DE760F5FD`).

If Telegram access requires a proxy, set both upper-case and lower-case proxy variables:

```env
HTTP_PROXY=http://<proxy-host>:<proxy-port>
HTTPS_PROXY=http://<proxy-host>:<proxy-port>
NO_PROXY=localhost,127.0.0.1,*.local
http_proxy=http://<proxy-host>:<proxy-port>
https_proxy=http://<proxy-host>:<proxy-port>
no_proxy=localhost,127.0.0.1,*.local
```

Start the sidecar:

```bash
cd sub2api-skill
docker compose up -d
```

Important mounts:

- `./config:/config` — bot secrets
- `./data:/data` — offsets, pending operations, import cache, and backups
- `<docker-root>/sub2api/data:/sub2api-data:ro` — read-only access to Sub2API data
- `<docker-root>/sub2api:/sub2api-compose:ro` — read-only access to the official Sub2API compose directory for `/update`
- `/var/run/docker.sock:/var/run/docker.sock` — allows confirmation-protected Docker restart and update actions

Docker `/update` behavior:

1. Immediately replies that it is checking the Docker image update
2. Compares local `weishaw/sub2api:latest` with the remote official image digest
3. Replies “already up to date” if they match
4. Shows confirm/cancel buttons if an update is available
5. On confirmation, runs `docker compose pull sub2api`
6. Recreates the `sub2api` service using the official Sub2API `docker-compose.yml`
7. Waits for the health check and prunes dangling old images

## 8. Security Principles

- Do not commit real tokens, passwords, JWTs, API keys, chat IDs, database addresses, or private network addresses
- Pass sensitive values through environment variables or local secrets files
- Restrict bot access with `SUB2API_BOT_ALLOWED_CHAT_IDS`
- Require confirmation codes or buttons for all control commands
- Keep imported accounts unscheduled by default
- Redact secrets in logs and replies by default
- The Docker sidecar does not modify the official Sub2API image; confirmed update actions use the official compose file

## 9. CI and Image Build

GitHub Actions validates:

- Python template syntax
- Node script syntax
- JSON files
- Basic sensitive information patterns
- Docker sidecar image build and GHCR push

## 10. Disclaimer

This project is an independent community integration for Sub2API. It is not an official Sub2API component unless explicitly adopted by the Sub2API maintainers.

Use it at your own risk. Before using the Telegram bot in production, review the source code, test it in a non-production environment, and verify that SQL queries, table names, service names, paths, permissions, and scheduling rules match your deployment.

This project does not provide legal, financial, compliance, security, or operational guarantees. You are responsible for protecting credentials, complying with upstream provider terms, following local laws and regulations, and ensuring that account sharing, quota distribution, API forwarding, billing, and automation are authorized in your environment.

The templates may perform administrative actions such as restarting services or containers, updating Docker images, importing account credentials into your configured database, and creating local backups. These actions are confirmation-protected where applicable, but you should still restrict bot access, secure environment files, keep backups private, and monitor logs.

All third-party names and trademarks belong to their respective owners. References to Sub2API, OpenAI, Anthropic, Gemini, Telegram, QQ, Tencent, GitHub, Docker, or other services are for interoperability and documentation purposes only.

## License

MIT
