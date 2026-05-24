## Action: `exec-token`

Execute a shell command with a token key securely substituted.

```bash
EXEC_SCRIPT="${CLAUDE_SKILL_DIR}/scripts/exec-token.js"
$RUNTIME "$EXEC_SCRIPT" <token_id> -- <command with __SUB2API_TOKEN_<id>__>
```

The command should contain the placeholder `__SUB2API_TOKEN_<id>__` where `<id>` is the token ID number. The script:
1. Fetches the real key
2. Substitutes the placeholder
3. Executes the command
4. Sanitizes stdout/stderr before returning
5. Clears the key from memory

**Example:**

```bash
# Test a token by making an API call
$RUNTIME "$EXEC_SCRIPT" 1 -- curl -s -H "Authorization: Bearer __SUB2API_TOKEN_1__" https://sub2api.deltrivx.com/v1/chat/completions -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"hi"}]}'
```

The key is passed via environment variable `SUB2API_KEY` as well, so commands can reference `$SUB2API_KEY` instead of the placeholder if preferred.

**SECURITY**: Do NOT print the key. The script handles masking automatically.
