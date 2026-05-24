## Action: `apply-token` / `scan-config`

Securely work with configuration files that need API keys.

### `scan-config`

Inspect the structure of a config file with secrets redacted:

```bash
INJECT_SCRIPT="${CLAUDE_SKILL_DIR}/scripts/inject-key.js"
$RUNTIME "$INJECT_SCRIPT" --scan "<file_path>"
```

This reads the file and replaces known secret patterns (sk- keys, JWT tokens, password fields) with `***REDACTED***`. Use this before modifying any config file that may contain credentials.

**SECURITY**: Do NOT read config files directly with `cat` or other tools. Always use `--scan` first.

### `apply-token`

Securely inject a token key into a config file. Requires a token ID and a file path.

```bash
INJECT_SCRIPT="${CLAUDE_SKILL_DIR}/scripts/inject-key.js"
$RUNTIME "$INJECT_SCRIPT" <token_id> "<file_path>"
```

**Workflow:**
1. First scan the file: `--scan <file_path>`
2. Edit the file so the key field contains `__SUB2API_TOKEN_<id>__`
3. Run `apply-token <token_id> <file_path>` to inject the real key
4. Trust the success message — do NOT reopen the file to verify

The script atomically replaces the placeholder and writes the result. The key value is never shown.
