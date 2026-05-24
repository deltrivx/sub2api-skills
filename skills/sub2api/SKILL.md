---
name: sub2api
description: Assistant for Sub2API, an open-source AI API gateway platform (https://github.com/Wei-Shaw/sub2api). Use when the user asks about Sub2API, managing accounts, groups, balance, or tokens.
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
| `help` | Answer questions about Sub2API | `docs/help.md` |

### `help` (or no arguments) — Show available actions

| Action | Usage | Description |
| -------- | ------- | ------------- |
| `accounts` | `/sub2api accounts` | List available accounts |
| `groups` | `/sub2api groups` | List user groups |
| `balance` | `/sub2api balance` | Show account balance |
| `tokens` | `/sub2api tokens` | List API tokens |
| `create-token` | `/sub2api create-token <name>` | Create a new API token |
| `help` | `/sub2api help <question>` | Answer questions about Sub2API |
