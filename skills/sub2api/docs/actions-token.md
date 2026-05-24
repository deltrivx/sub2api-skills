## Action: `switch-group`

Change an API token's group membership. Requires token ID and a group name/number.

```bash
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/api-keys/page_size=100"
```

Then use the token ID to update it:

```bash
$RUNTIME "$API_SCRIPT" PUT "/api/v1/admin/api-keys/<token_id>" '{"group_id":<group_id>}'
```

Default groups: 1=Default, 2=ChatGPT, 34=MiMo

---

## Action: `copy-token`

Copy the real API key to the system clipboard. Requires a token ID.

```bash
# First get the keys list to find the token info
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/api-keys/page_size=100"
```

**SECURITY CRITICAL**: Do NOT use `fetch-key.js` or any script to reveal the full key. The `copy-token` action uses clipboard utilities (`pbcopy`, `xclip`, `wl-copy`) to copy the key directly, never showing it in the terminal or conversation.

Use this approach:

```bash
# 1. Fetch the raw response (only in a variable, never printed)
RAW_KEY=$(curl -s -H "Authorization: Bearer $SUB2API_ACCESS_TOKEN" "$SUB2API_BASE_URL/api/v1/admin/api-keys/<token_id>" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['key'])" 2>/dev/null)

# 2. Copy to clipboard directly — never echo
if command -v pbcopy &>/dev/null; then
  echo -n "$RAW_KEY" | pbcopy
  echo "Key copied to clipboard (pbcopy)"
elif command -v xclip &>/dev/null; then
  echo -n "$RAW_KEY" | xclip -selection clipboard
  echo "Key copied to clipboard (xclip)"
elif command -v wl-copy &>/dev/null; then
  echo -n "$RAW_KEY" | wl-copy
  echo "Key copied to clipboard (wl-copy)"
else
  echo "ERROR: No clipboard tool found (need pbcopy, xclip, or wl-copy)"
  exit 1
fi

# 3. Clear the variable
unset RAW_KEY
```

Do NOT print the key value at any point. Report success and clear the variable immediately.

---

## Action: `apply-token`

Securely inject a token key into a config file. Requires a token ID and a file path.

Use `inject-key.js` script if available, or the following approach:

```bash
# 1. First scan the config with --scan
$RUNTIME "$INJECT_SCRIPT" --scan "$FILE_PATH"

# 2. Ask the user to edit the file so the key field contains __SUB2API_TOKEN_<id>__

# 3. Then apply
TOKEN_VALUE=$(curl -s -H "Authorization: Bearer $SUB2API_ACCESS_TOKEN" "$SUB2API_BASE_URL/api/v1/admin/api-keys/<token_id>" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['key'])")
PLACEHOLDER="__SUB2API_TOKEN_<id>__"
sed -i "s/$PLACEHOLDER/$TOKEN_VALUE/g" "$FILE_PATH"
echo "Token applied to $FILE_PATH"
unset TOKEN_VALUE PLACEHOLDER
```

Do NOT print or log the key value.

---

## Action: `exec-token`

Execute a shell command with a token key securely substituted. Requires a token ID and a command.

The command should use the placeholder `__SUB2API_TOKEN_<id>__`. The script fetches the key, substitutes it into the command, executes it, and sanitizes stdout/stderr before returning.

```bash
TOKEN_VALUE=$(curl -s -H "Authorization: Bearer $SUB2API_ACCESS_TOKEN" "$SUB2API_BASE_URL/api/v1/admin/api-keys/<token_id>" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['key'])")
PLACEHOLDER="__SUB2API_TOKEN_<id>__"
# Substitute placeholder with real key
SAFE_CMD=$(echo "$COMMAND" | sed "s/$PLACEHOLDER/$TOKEN_VALUE/g")
# Execute and sanitize output
eval "$SAFE_CMD" 2>&1 | "${SANITIZE_SCRIPT:-cat}"
unset TOKEN_VALUE SAFE_CMD
```

---

## Action: `scan-config`

Safely inspect the structure of a configuration file with secrets redacted.

```bash
# Read the file and redact common secret patterns
cat "$FILE_PATH" | sed -E \
  -e 's/(sk-[A-Za-z0-9]{10,})/sk-***REDACTED***/g' \
  -e 's/(access_token["]?[[:space:]]*[:=]["][^"]{5,})/\1***REDACTED***/g' \
  -e 's/(session_token["]?[[:space:]]*[:=]["][^"]{5,})/\1***REDACTED***/g'
```

Display the structure showing which fields are present, with all key values redacted. Note: this is best-effort and may not catch every secret format.
