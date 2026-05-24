# Setup

## Configuration

Configuration is loaded in the following priority order (higher overrides lower):

1. **Environment variables** (highest priority, recommended)
2. **Skill directory `.env`** (next to SKILL.md)
3. **Project root `.env`** — project-level config

Required variables — recommended to export in your shell profile:

```bash
export SUB2API_BASE_URL=https://your-sub2api-instance.com
export SUB2API_ACCESS_TOKEN=your-access-token
export SUB2API_USER_ID=1
```

Alternatively, create a `.env` file (make sure it's in `.gitignore`). Environment variables are preferred over `.env` files because `.env` files risk accidental commits even with `.gitignore` in place.

### Getting your Access Token

Sub2API uses JWT-based authentication. To get your access token:

1. Open your Sub2API admin panel in a browser
2. Log in with your admin credentials
3. Open browser DevTools → Application → Local Storage
4. Find the key `access_token` and copy its value
5. Export it as `SUB2API_ACCESS_TOKEN`

Or use the login endpoint:

```bash
curl -s -X POST https://your-sub2api-instance.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])"
```

## Mental Model

This skill uses several JavaScript scripts with different responsibilities:

- `scripts/api.js` handles Sub2API management actions such as listing accounts, groups, balance, and token metadata.
- `scripts/sanitize.js` ensures output is clean and free of control sequences.

## Authentication

Every API request uses Bearer token auth with this header:

```text
Authorization: Bearer <SUB2API_ACCESS_TOKEN>
```

## Runtime Detection

The skill ships with plain JavaScript scripts and no external dependencies. Before first use, detect the available JS runtime once and reuse it for the session:

```bash
API_SCRIPT="${CLAUDE_SKILL_DIR}/scripts/api.js"

# Detect runtime (prefer bun > node > deno)
if command -v bun &>/dev/null; then RUNTIME="bun"; \
elif command -v node &>/dev/null; then RUNTIME="node"; \
elif command -v deno &>/dev/null; then RUNTIME="deno run --allow-net --allow-read --allow-env"; \
else echo "ERROR: No JS runtime found (need bun, node, or deno)" >&2; exit 1; fi
```

Use the same runtime for all scripts.

Management API calls:

```bash
$RUNTIME "$API_SCRIPT" <METHOD> <PATH> [JSON_BODY]
```

## Error Handling

- If the API returns a non-success response, display the error message clearly
- If authentication fails (401/403), suggest refreshing the access token (it may have expired)
- If a resource is not found (404), say so clearly
- If the script returns `[CONFIG_MISSING]`, stop retrying and tell the user to set the required environment variables or `.env` values first
