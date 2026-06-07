# Telegram Bot Template

`templates/` contains a standalone Telegram operations bot template for Sub2API deployments.

## Files

- `telegram-bot.py` — Telegram polling bot with Chinese command menu.
- `south-monitor.py` — optional realtime monitor. It calls Sub2API's admin account test endpoint on every run instead of relying on historical scheduled-test records.
- `sub2api-telegram-bot.service` — systemd unit.
- `sub2api-bot.env.example` — environment configuration example.

## Sensitive Data

Do not commit real values. Replace placeholders at deployment time:

- `<your-sub2api-host>`
- `<admin@example.com>`
- `<admin-password>`
- `<telegram-bot-token>`
- `<telegram-chat-id>`
- `<proxy-host>` / `<proxy-port>`

## Realtime Verification

The monitor template uses realtime account tests for every report:

```text
POST /api/v1/admin/accounts/{id}/test
```

Historical `scheduled_test_results` are not used for current state decisions.

Modes:

- Cron/default: write state and create announcements only on status changes.
- `/force` / `--force`: run realtime verification only; do not create announcements and do not update state.
- `--announce` / `--manual-test`: run realtime verification and create a manual popup announcement.

Popup behavior:

- Before a new popup announcement is created, previous active popup announcements are changed to `silent`.
- Old announcements remain in history, but the UI should only pop the latest one.

## Account Import

Send a `.json` or `.txt` file to the bot. The file may contain one account object or an array.

Supported fields:

- `name`
- `platform` / `provider`: `openai`, `anthropic`, `gemini`
- `group` / `group_name`
- `type`
- `credentials`
- `api_key`, `key`, `access_token`, `refresh_token`, `base_url`
- `priority`
- `concurrency`

Imported accounts default to `schedulable=false`. Use `/enable <account_id>` after checking the report.

## Control Safety

The following commands generate a confirmation code instead of running immediately:

- `/enable <account_id>`
- `/disable <account_id>`
- `/restart bot|sub2api`
- `/setcron 15m|30m|1h`

Use `/confirm <code>` within 5 minutes or `/cancel`.
