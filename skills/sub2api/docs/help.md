# Sub2API Help

## What is Sub2API?

Sub2API is an open-source AI API gateway that aggregates multiple upstream accounts (OpenAI, Anthropic, etc.) behind a single OpenAI-compatible API endpoint. It provides account management, token management, group-based access control, usage tracking, and OAuth-based credential management.

GitHub: https://github.com/Wei-Shaw/sub2api

## Deployment

Sub2API supports two deployment methods:

**Docker Compose (recommended for most users):**
- All-in-one setup with PostgreSQL + Redis
- Auto-setup via `AUTO_SETUP=true` environment variable
- No manual configuration needed

**Binary Installation:**
- Download the latest release binary
- Run `install.sh` or manually set up systemd service
- Complete the Setup Wizard in the browser at port 8080
- Config file at `/etc/sub2api/config.yaml`

## Key Concepts

### Accounts (上游账号)
Upstream AI provider accounts (OpenAI Plus, etc.) configured with OAuth credentials. Each account has:
- `access_token` / `session_token` — OAuth credentials
- `plan_type` — Free or Plus
- `proxy_id` — Optional proxy binding
- `concurrency` — Max concurrent requests (default: 3)
- `priority` — Scheduling priority (lower = higher priority)
- `status` — active / paused / error

### Groups (分组)
Logical groups that organize accounts. Account groups control:
- Which accounts a token can use
- Model access permissions
- Rate limiting and pricing

### API Tokens (API 令牌)
Keys used by downstream clients to access the gateway. Each token:
- Belongs to a user
- Belongs to a group
- Has masked display (e.g., `sk-reHR**********OspA`)
- Supports status toggling (active/paused)

### OpenAI Account Types

OpenAI Plus accounts have limit configurations:
- **5-hour window:** Codex quota resets every 5 hours
- **7-day window:** Codex quota resets every 7 days
- Accounts can have `codex_5h_used_percent` and `codex_7d_used_percent` usage tracking

## API Endpoints

The gateway exposes a standard OpenAI-compatible chat completions endpoint:

```
POST /v1/chat/completions
Authorization: Bearer sk-<token>
Content-Type: application/json

{"model": "gpt-5.5", "messages": [...]}
```

Common models:
- `gpt-5.5` — Latest GPT model
- `gpt-5.4` / `gpt-5.4-mini`
- `gpt-5.2`
- `gpt-5.3-codex` — Codex-specific model
- `mimo-v2.5` / `mimo-v2.5-pro`
- `o1` / `o3` / `o1-pro` / `o4-mini`
- `gpt-4.1` / `gpt-4.1-mini` / `gpt-4.1-nano`

## Common Issues

### "No available accounts"
All accounts in the requested group are either overloaded, rate-limited, or currently in use. Wait and retry.

### Authentication failures
Tokens expire periodically. Refresh your access token via login endpoint and update `SUB2API_ACCESS_TOKEN`.

### Account overloads
OpenAI Plus accounts have usage limits. The gateway tracks 5-hour and 7-day windows for Codex usage. Account rotation happens automatically.

## Model Mapping

Sub2API supports model name remapping via `model_mapping` in account credentials or channel configuration. For example:
```json
{
  "gpt-5.5": "gpt-5.5",
  "gpt-5.4": "gpt-5.4",
  "mimo-v2.5": "mimo-v2.5"
}
```
