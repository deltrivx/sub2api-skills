# Telegram Bot Template

`templates/` contains a standalone Telegram operations bot template for Sub2API deployments.

## Files

- `telegram-bot.py` — Telegram polling bot with Chinese command menu.

## Sensitive Data

Do not commit real values. Replace placeholders at deployment time through environment variables or a deployment-local secrets JSON file:

- `SUB2API_BASE_URL`
- `SUB2API_ADMIN_EMAIL`
- `SUB2API_ADMIN_PASSWORD_B64`
- `TELEGRAM_BOT_TOKEN`
- `SUB2API_BOT_ALLOWED_CHAT_IDS`
- `SUB2API_BOT_SECRETS_FILE`
- `SUB2API_DB_NAME` / `SUB2API_DB_USER`
- `SUB2API_DEFAULT_PROXY_ID`
- `SUB2API_UPDATER_SCRIPT`

## Commands

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
- `/update` — check for updates; reply “already up to date” when current, otherwise show confirm/cancel buttons.

## Account Import

Send a `.json` or `.txt` account file to the bot. The file may contain one account object, an array, or an object wrapping an `accounts`, `items`, `data`, or `list` array.

Supported fields include:

- `name`, `account_name`, `label`, `email`
- `platform`, `provider`, `service`
- `group`, `group_name`, `groupName`
- `type`, `account_type`, `auth_type`
- `credentials`
- `api_key`, `key`, `access_token`, `refresh_token`, `base_url`
- `priority`, `concurrency`, `proxy_id`

Imported accounts default to `schedulable=false`. The bot masks secret values and reports credential field names only.

## Control Safety

The following commands generate a confirmation code instead of running immediately:

- `/restart bot|sub2api`
- `/update`

Use `/confirm <code>` within 5 minutes or `/cancel`.


## Archive import safety

The bot can accept `.zip`, `.tar`, `.tar.gz`, and `.tgz` archives. It scans archives in memory, imports only `.json` / `.txt` account files, rejects path traversal entries, and enforces limits for archive size, file count, per-file size, and total extracted bytes.
