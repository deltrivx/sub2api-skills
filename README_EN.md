# Sub2API Skills and Telegram Operations Bot

This repository provides an assistant skill for Sub2API and an optional Telegram operations bot template for querying, diagnosing, importing account files, creating local backups, muting notifications, and running confirmation-protected maintenance actions.

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

## 4. Telegram Operations Bot Template

Template files:

- `skills/sub2api/templates/telegram-bot.py`

Supported bot command groups:

### Read-only Diagnostics

- `/status` — combined status, usage, limits and balance
- `/accounts` — account list and routing state
- `/models` — model mappings and recently requested models
- `/channels` — channel and group overview
- `/tokens` — API token quota and usage, with keys masked
- `/debug` — health checks and log summary

### Import and Maintenance

- `/importhelp` — account-file import help
- Send a `.json` or `.txt` account file — analyze, import accounts, match/create groups, and return masked account metadata
- `/backup` — create a local backup
- `/updatecheck` — check whether Sub2API has a newer version

### Confirmation-protected Controls

These commands generate a 5-minute confirmation code before execution:

- `/pending`
- `/confirm <code>`
- `/cancel`
- `/restart bot|sub2api`
- `/update`

## 5. Account JSON Import Format

A single object or an array is supported:

```json
[
  {
    "name": "<account-name>",
    "platform": "openai",
    "group": "<group-name>",
    "type": "api_key",
    "api_key": "***",
    "priority": 50,
    "concurrency": 3
  },
  {
    "name": "<anthropic-account>",
    "provider": "anthropic",
    "group_name": "<anthropic-group>",
    "credentials": {
      "api_key": "***"
    }
  }
]
```

Import behavior:

- Detects `platform/provider/service/type`
- Creates or matches groups automatically
- Writes `accounts` and `account_groups`
- Writes `scheduler_outbox`
- Defaults imported accounts to `schedulable=false`
- Replies with credential field names only, never secret values

## 6. Deployment

```bash
sudo install -m 700 skills/sub2api/templates/telegram-bot.py /opt/sub2api-telegram-bot.py
sudo install -m 600 skills/sub2api/templates/sub2api-bot.env.example /etc/sub2api-bot.env
sudo editor /etc/sub2api-bot.env
sudo systemctl daemon-reload

```


## 7. Disclaimer

This project is an independent community integration for Sub2API. It is not an official Sub2API component unless explicitly adopted by the Sub2API maintainers.

Use it at your own risk. Before using the Telegram bot or monitor in production, review the source code, test it in a non-production environment, and verify that the SQL queries, table names, service names, paths, permissions, and scheduling rules match your own deployment.

This project does not provide legal, financial, compliance, security, or operational guarantees. You are responsible for protecting credentials, complying with your upstream providers' terms, following local laws and regulations, and ensuring that account sharing, quota distribution, API forwarding, billing, and automation behaviors are authorized in your environment.

The templates may perform administrative actions such as toggling account schedulability, restarting services, updating cron entries, importing account credentials into your configured database, and creating local backups. These actions are confirmation-protected where applicable, but you should still restrict bot access, secure environment files, keep backups private, and monitor logs.

All third-party names and trademarks belong to their respective owners. References to Sub2API, OpenAI, Anthropic, Gemini, Telegram, GitHub, or other services are for interoperability and documentation purposes only.

## 8. CI

GitHub Actions validates:

- Python template syntax
- Node script syntax
- JSON files
- Basic sensitive information patterns

## License

MIT
