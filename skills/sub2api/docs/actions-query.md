## Action: `accounts`

List available accounts (both active and inactive).

```bash
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/accounts?page_size=100"
```

Display the response as a formatted table with columns: ID, Name, Platform, Status, Priority, Last Used.

---

## Action: `groups`

List user groups.

```bash
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/groups/page_size=100"
```

Display the groups as a list with ID, Name, and Status.

---

## Action: `balance`

Show account balance and user info.

```bash
$RUNTIME "$API_SCRIPT" GET "/api/v1/admin/users/1"
```

From the response, extract and display:
- Email
- Username
- Role
- Balance (quota remaining)
- Concurrency limit
- Status
