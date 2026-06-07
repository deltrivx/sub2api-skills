# Sub2API Skills 与 Telegram 运维机器人

这个仓库提供 Sub2API 的助手 Skill，以及一套可选的 Telegram 运维机器人模板，用于查询、诊断、导入账号文件、备份、静默通知和带确认码的低风险运维控制。

> 安全说明：仓库内所有地址、Token、密码、Chat ID、账号 Key 均使用占位符或环境变量。请不要把真实凭据提交到 GitHub。

## 一、安装 Skill

```bash
npx skills add https://github.com/deltrivx/sub2api-skills --skill sub2api
```

## 二、Skill 环境变量

推荐通过环境变量配置，不要写入仓库：

```bash
export SUB2API_BASE_URL="https://<your-sub2api-host>"
export SUB2API_ACCESS_TOKEN="<your-sub2api-access-token>"
export SUB2API_USER_ID="<your-user-id>"
```

也可以在本地创建 `.env`，但必须确保 `.env` 不被提交。

## 三、Skill 支持能力

| Action | 用法 | 说明 |
| --- | --- | --- |
| `accounts` | `/sub2api accounts` | 查看账号列表 |
| `groups` | `/sub2api groups` | 查看分组列表 |
| `balance` | `/sub2api balance` | 查看余额/账户信息 |
| `tokens` | `/sub2api tokens` | 查看 API 令牌，默认脱敏 |
| `create-token` | `/sub2api create-token <name>` | 创建 API 令牌 |
| `switch-group` | `/sub2api switch-group <token_id> <group>` | 切换令牌分组 |
| `copy-token` | `/sub2api copy-token <token_id>` | 复制真实 Key 到剪贴板，不在聊天中显示 |
| `apply-token` | `/sub2api apply-token <token_id> <file>` | 安全写入配置文件 |
| `exec-token` | `/sub2api exec-token <token_id> -- <cmd>` | 临时注入令牌执行命令 |
| `scan-config` | `/sub2api scan-config <file>` | 扫描配置并脱敏展示 |
| `help` | `/sub2api help <question>` | 查询 Sub2API 使用说明 |

## 四、Telegram 运维机器人模板

模板位置：

- `skills/sub2api/templates/telegram-bot.py`
- `skills/sub2api/templates/south-monitor.py`
- `skills/sub2api/templates/sub2api-telegram-bot.service`
- `skills/sub2api/templates/sub2api-bot.env.example`

机器人菜单支持：

### 查询与诊断

- `/status`：查看 Sub2API 状态与调度
- `/summary`：查看 Sub2API 运行摘要
- `/overview`：查看综合仪表盘
- `/health`：检查服务健康状态
- `/plans`：查看定时测试计划
- `/history`：查看测试历史
- `/announcements`：查看公告
- `/logs`：查看关键日志
- `/models`：查看模型与映射
- `/usage`：查看今日用量
- `/limits`：查看限流/冷却状态
- `/routing`：查看路由策略
- `/errors`：查看错误聚合
- `/config`：查看监控配置摘要
- `/keys`：查看令牌额度与过期状态，Key 脱敏
- `/channels`：查看渠道配置
- `/monitors`：查看通道监控器
- `/alerts`：查看告警事件
- `/ops`：查看系统运行指标
- `/queue`：查看调度事件队列
- `/costs`：查看成本趋势
- `/latency`：查看延迟统计
- `/top`：查看高频账号、模型、令牌、IP

### 导入与维护

- `/importhelp`：查看账号文件导入说明
- 发送 `.json` / `.txt` 账号文件：自动分析、创建/匹配分组、导入账号并报告账号信息
- `/backup`：生成本地配置备份
- `/mute 30m|2h|1d`：临时静默 Telegram 推送
- `/watch`：恢复通知

### 带确认码的控制命令

以下命令不会立即执行，会生成 5 分钟有效确认码：

- `/pending`：查看待确认操作
- `/confirm <code>`：确认执行
- `/cancel`：取消待确认操作
- `/enable <account_id>`：启用账号调度
- `/disable <account_id>`：禁用账号调度
- `/restart bot|sub2api`：重启服务
- `/setcron 15m|30m|1h`：修改监控频率

## 五、账号 JSON 导入格式

支持单个对象或数组：

```json
[
  {
    "name": "<account-name>",
    "platform": "openai",
    "group": "<group-name>",
    "type": "api_key",
    "api_key": "<api-key>",
    "priority": 50,
    "concurrency": 3
  },
  {
    "name": "<anthropic-account>",
    "provider": "anthropic",
    "group_name": "<anthropic-group>",
    "credentials": {
      "api_key": "<api-key>"
    }
  }
]
```

导入策略：

- 自动识别 `platform/provider/service/type`
- 自动创建或匹配分组
- 自动写入 `accounts` 与 `account_groups`
- 自动写入 `scheduler_outbox`
- 默认 `schedulable=false`，确认无误后再 `/enable <account_id>`
- 回复中只展示凭据字段名，不展示明文凭据

## 六、部署 Telegram Bot

1. 复制模板：

```bash
sudo install -m 700 skills/sub2api/templates/telegram-bot.py /opt/sub2api-telegram-bot.py
sudo install -m 600 skills/sub2api/templates/sub2api-bot.env.example /etc/sub2api-bot.env
sudo install -m 644 skills/sub2api/templates/sub2api-telegram-bot.service /etc/systemd/system/sub2api-telegram-bot.service
```

2. 编辑环境变量：

```bash
sudo editor /etc/sub2api-bot.env
```

3. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sub2api-telegram-bot.service
sudo systemctl status sub2api-telegram-bot.service --no-pager
```

## 七、安全原则

- 不提交真实 Token、密码、JWT、API Key、Chat ID、数据库地址或内网地址
- 所有敏感配置通过环境变量或本地 secrets 文件传入
- Bot 只允许 `SUB2API_BOT_ALLOWED_CHAT_IDS` 中的聊天使用
- 所有控制命令必须确认码确认
- 导入账号默认关闭调度
- 日志和回复默认脱敏

## 八、CI

仓库包含 GitHub Actions：

- Python 模板语法检查
- Node 脚本语法检查
- README/模板敏感信息占位符检查

推送到 GitHub 后会自动触发构建。

## License

MIT
