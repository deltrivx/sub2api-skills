## Action: `tokens`

List all API tokens (keys are masked for security).

```bash
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/api-keys?page_size=100"
```

Display the response as a formatted table with columns: ID, Name, Key (masked), Status, User ID.

---

## Action: `create-token`

Create a new API token. Requires a name as the first argument.

```bash
$RUNTIME "$API_SCRIPT" POST "/api/v1/admin/api-keys" '{"name":"<name>","user_id":1,"group_id":2}'
```

Replace `<name>` with the provided token name. Default to user_id=1 (admin) and group_id=2 (ChatGPT group).

After creation:
- Display the response showing the new token's details
- The key will be shown in the response only once
- Do NOT make any follow-up API call to retrieve the key again
