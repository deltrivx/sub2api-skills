---
name: sub2api
description: Assistant for Sub2API, an open-source AI API gateway platform (https://github.com/Wei-Shaw/sub2api). Use when the user asks about Sub2API, managing accounts, groups, balance, tokens, or the optional Telegram operations bot template.
---

# SKILL: sub2api

Sub2API ([GitHub](https://github.com/Wei-Shaw/sub2api)) is an open-source AI API gateway platform.
It aggregates multiple OpenAI accounts behind a unified API, and provides account, token, group, and balance management.

## Security Guidelines

1. Do not expose any access token value in chat, files, code, logs, or command arguments.
2. All Sub2API management API calls should go through the provided scripts (`api.js`) rather than using `curl`, `wget`, `fetch`, or other HTTP clients directly.
3. Do not read `.env` files or environment variables containing credentials.
4. After `create-token`, do not make any follow-up call to retrieve or list the key. Report success and tell the user to use the token from the response.
5. Do not modify the security scripts to disable masking or redirect output.
6. Telegram Bot templates must keep secrets in environment files or runtime secrets, never hard-coded in repository files.
7. Imported account files may contain API keys or refresh tokens. Store them only in the configured Sub2API database/runtime target and never echo values back; report field names only.
8. Control operations such as restart/update must use confirmation-code or button-based confirmation protection.

## How to Execute

1. **First invocation only** — read `${CLAUDE_SKILL_DIR}/docs/setup.md` for configuration, auth headers, and runtime detection.
2. Match the action from the table below.
3. Read the corresponding doc file for detailed steps.
4. If no arguments or unrecognized action, show the help table below.
5. If the user asks about Sub2API (what it is, how to use a command, or any API usage question) — read `${CLAUDE_SKILL_DIR}/docs/help.md` and follow the instructions there.

## Actions

| Action | Description | Details |
| -------- | ------------- | --------- |
| `accounts` | List available accounts | `docs/actions-query.md` |
| `groups` | List user groups | `docs/actions-query.md` |
| `balance` | Show account balance | `docs/actions-query.md` |
| `tokens` | List API tokens | `docs/actions-token.md` |
| `create-token` | Create a new API token | `docs/actions-token.md` |
| `switch-group` | Change a token's group | `docs/actions-token.md` |
| `copy-token` | Copy real key to clipboard (never shown) | `docs/actions-token.md` |
| `apply-token` | Apply token key to a config file securely | `docs/actions-config.md` |
| `exec-token` | Execute a command with the token key securely substituted | `docs/actions-exec.md` |
| `scan-config` | Inspect config structure with best-effort secret redaction | `docs/actions-config.md` |
| `help` | Answer questions about Sub2API | `docs/help.md` |

## Optional Telegram Bot Template

This repository also ships a deployment template under `templates/` for a Telegram-based Sub2API operations bot. It is not enabled automatically by the skill.

Template capabilities include:

- Chinese Telegram command menu.
- Comprehensive Sub2API status, account routing, usage, limits, balance, model, channel and token diagnostics.
- JSON/TXT account-file import with automatic group matching/creation and account testing.
- Safe reporting of imported account metadata without printing secrets.
- Confirmation-code guarded restart/update controls.
- Local backup and debug/log summary commands.
- Secrets are loaded from environment variables or a deployment-local secrets JSON file; no real deployment values should be committed.

Supported bot commands:

- `/help` — show help.
- `/status` — combined status, usage, limits and balance.
- `/accounts` — account list and routing state.
- `/models` — model mappings and recently requested models.
- `/channels` — channel and group overview.
- `/tokens` — API token quota and usage, with keys masked.
- `/importhelp` — account file import instructions.
- `/pending` / `/confirm` / `/cancel` — confirmation workflow.
- `/backup` — local deployment backup.
- `/restart bot|sub2api` — confirmation-protected service restart.
- `/debug` — health checks and log summary.
- `/update` — check for updates; if a new version exists, show confirm/cancel buttons before applying.

### `help` (or no arguments) — Show available actions

| Action | Usage | Description |
| -------- | ------- | ------------- |
| `accounts` | `/sub2api accounts` | List available accounts |
| `groups` | `/sub2api groups` | List user groups |
| `balance` | `/sub2api balance` | Show account balance |
| `tokens` | `/sub2api tokens` | List API tokens |
| `create-token` | `/sub2api create-token <name>` | Create a new API token |
| `switch-group` | `/sub2api switch-group <token_id> <group>` | Change a token's group |
| `copy-token` | `/sub2api copy-token <token_id>` | Copy real key to clipboard (never shown) |
| `apply-token` | `/sub2api apply-token <token_id> <file_path>` | Apply token key to a config file securely |
| `exec-token` | `/sub2api exec-token <token_id> <command...>` | Execute a command with the token key securely substituted |
| `scan-config` | `/sub2api scan-config <file_path>` | Inspect config structure with best-effort secret redaction |
| `help` | `/sub2api help <question>` | Answer questions about Sub2API |
