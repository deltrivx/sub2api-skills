# sub2api-skills

Skills for managing [Sub2API](https://github.com/Wei-Shaw/sub2api) (open-source AI API gateway) resources — accounts, groups, tokens and balance.

## Installation

```bash
npx skills add https://github.com/deltrivx/sub2api-skills --skill sub2api
```

## Configuration

Set the following variables before using the skill. Recommended: export as environment variables (e.g. in your shell profile):

```bash
export SUB2API_BASE_URL=https://sub2api.deltrivx.com
export SUB2API_ACCESS_TOKEN=your-access-token
export SUB2API_USER_ID=1
```

Alternatively, create a `.env` file in the project root or the skill directory. Make sure `.env` is in your `.gitignore`.

## Usage

| Action | Usage | Description |
| ------ | ----- | ----------- |
| `accounts` | `/sub2api accounts` | List available accounts |
| `groups` | `/sub2api groups` | List user groups |
| `balance` | `/sub2api balance` | Show account balance |
| `tokens` | `/sub2api tokens` | List API tokens |
| `create-token` | `/sub2api create-token <name>` | Create a new API token |
| `help` | `/sub2api help <question>` | Answer questions about Sub2API |

## Requirements

- Bun (preferred), Node.js >= 18, or Deno

## License

MIT
