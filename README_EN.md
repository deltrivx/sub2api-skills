# Sub2API Skills and Telegram Operations Bot

This repository provides an assistant skill for Sub2API, a Telegram operations bot template, and an optional Docker sidecar deployment. It is designed to add diagnostics, account import, backup, restart, and update workflows without modifying the official Sub2API image or container.

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

Template file:

- `skills/sub2api/templates/telegram-bot.py`

The bot supports both host-level deployments and Docker sidecar deployments. Host-level deployment is suitable when Sub2API runs as a binary, systemd service, or another local host service. Docker sidecar deployment is suitable for Docker-based Sub2API installations and keeps the official Sub2API image and container clean.

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
- `/checkaccounts` — checks account availability, then provides soft-delete / hard-delete buttons with a second confirmation step

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
SUB2API_BASE_URL=http://127.0.0.1:<sub2api-port>
SUB2API_BOT_ALLOWED_CHAT_IDS=<telegram-chat-id>
TELEGRAM_BOT_TOKEN=<telegram-bot-token>
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

All third-party names and trademarks belong to their respective owners. References to Sub2API, OpenAI, Anthropic, Gemini, Telegram, GitHub, Docker, or other services are for interoperability and documentation purposes only.

## License

MIT
