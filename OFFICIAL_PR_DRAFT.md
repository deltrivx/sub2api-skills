# Sub2API 官方仓库 PR 草稿

## PR Title

docs: add community Sub2API assistant skill integration

## PR Body

This PR adds a small community integration note for users who want to manage Sub2API resources through an assistant skill and an optional Telegram operations bot template.

The integration lives in a separate community repository and does not change Sub2API runtime behavior.

### What is included

- Adds a community integration document for `sub2api-skills`.
- Links to the external community repository.
- Documents that the Telegram bot template is optional and self-hosted.
- Includes a security/disclaimer note that users must review the code and avoid committing credentials.

### What is not included

- No Sub2API core code changes.
- No dependency changes.
- No deployment behavior changes.
- No bundled secrets, tokens, private IPs, or real credentials.

### Security note

The linked community project uses placeholders and environment variables for all sensitive configuration. Users remain responsible for reviewing the integration, protecting API keys and Telegram tokens, and ensuring that account routing, quota distribution, automation, and operations comply with their environment and provider terms.

## Suggested file to add to official repository

Path: `docs/community/sub2api-skills.md`

```md
# Sub2API Assistant Skill and Telegram Operations Bot

A community-maintained integration is available for users who want to manage Sub2API resources through an assistant skill and an optional Telegram operations bot template.

Repository: https://github.com/deltrivx/sub2api-skills

## Features

The integration can help with:

- Listing Sub2API accounts, groups, balance and API tokens.
- Managing user API tokens with masked output.
- Copying or applying token values without printing secrets in chat.
- Inspecting local config files with best-effort redaction.
- Optional Telegram-based operations bot templates for status checks, diagnostics, account-file import, local backups, notification mute/watch, and confirmation-protected maintenance actions.

## Installation

```bash
npx skills add https://github.com/deltrivx/sub2api-skills --skill sub2api
```

## Configuration

Use environment variables or local runtime secrets. Do not commit real credentials.

```bash
export SUB2API_BASE_URL="https://<your-sub2api-host>"
export SUB2API_ACCESS_TOKEN="<your-…ken>"
export SUB2API_USER_ID="<your-user-id>"
```

## Disclaimer

This is an independent community integration and is not an official Sub2API component unless explicitly adopted by Sub2API maintainers.

Review the code before use, test it in a non-production environment, and make sure the SQL queries, service names, file paths, permissions, routing rules and automation behavior match your own deployment.

Users are responsible for protecting credentials, complying with upstream provider terms and local laws, and ensuring that account sharing, quota distribution, API forwarding, billing, imports and administrative operations are authorized in their environment.
```

## Optional README link variant

If the official repository prefers a minimal README entry instead of a new docs page, add this under a community/ecosystem section:

```md
### Community integrations

- [sub2api-skills](https://github.com/deltrivx/sub2api-skills) — community assistant skill and optional Telegram operations bot templates for Sub2API account, group, token, diagnostics and maintenance workflows. This is an independent community project; review its disclaimer and security notes before use.
```
