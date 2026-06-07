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
- `/force`：手动触发实时检测，不发公告、不写巡检状态
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
- `/force`：手动实时检测 South/监控账号状态，不创建公告，也不消费下一次巡检状态变化
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

## 七、巡检与公告逻辑

监控模板每次运行都会通过 Sub2API 后台实时账号测试接口重新验证账号状态：

```text
POST /api/v1/admin/accounts/{id}/test
```

因此状态报告不依赖旧的 `scheduled_test_results` 历史记录。历史记录只适合做审计或人工排查，不作为当前可用性判断来源。

公告策略：

- 定时巡检：只有发现账号状态变化且需要自动调整调度/路由时才创建公告。
- 如果状态变化对应的调度已经被你或其他自动化提前调整到目标状态，巡检只静默更新状态，不创建公告、不推 Telegram。
- Telegram `/force`：只做实时检测并返回报告，不创建公告、不写状态文件、不消费下一次巡检状态变化。
- 显式手动公告测试：运行监控脚本时使用 `--announce` 或 `--manual-test`。
- 新 popup 公告创建前，会将旧的 active popup 公告降级为 `silent`，旧公告保留在公告历史中，但界面只弹最新一条。

## 八、免责声明

本项目是面向 Sub2API 的独立社区集成与运维模板，并非 Sub2API 官方组件，除非后续被 Sub2API 官方维护者明确接纳或合并。

请自行评估风险后使用。生产环境部署前，请先阅读源码，在非生产环境测试，并确认 SQL 查询、表名、服务名、文件路径、权限模型、调度规则和告警策略符合你的实际部署。

本项目不提供法律、财务、合规、安全或运维层面的保证。使用者需要自行负责：

- 妥善保护 API Key、Refresh Token、Telegram Token、数据库凭据和管理密码；
- 遵守上游服务商条款、本地法律法规和平台规则；
- 确认账号共享、额度分发、API 转发、计费统计、自动化导入和运维操作均已获得授权；
- 限制 Telegram Bot 可访问的 Chat ID，并保护环境变量文件和备份文件；
- 对 `/enable`、`/disable`、`/restart`、`/setcron`、账号导入和备份等管理动作的结果负责。

模板中的控制命令已设计为确认码保护，但这不能替代完善的权限隔离、日志审计、备份保护和生产变更流程。任何因部署、配置、误操作、凭据泄露、上游封禁、计费异常或第三方服务变化造成的损失，由使用者自行承担。

所有第三方名称和商标均归其各自所有者所有。本文档中提到 Sub2API、OpenAI、Anthropic、Gemini、Telegram、GitHub 等，仅用于兼容性说明和使用文档。

## 九、安全原则

- 不提交真实 Token、密码、JWT、API Key、Chat ID、数据库地址或内网地址
- 所有敏感配置通过环境变量或本地 secrets 文件传入
- Bot 只允许 `SUB2API_BOT_ALLOWED_CHAT_IDS` 中的聊天使用
- 所有控制命令必须确认码确认
- 导入账号默认关闭调度
- 日志和回复默认脱敏

## 十、英文备用 README

英文版备用文档见：[`README_EN.md`](README_EN.md)

## 十一、CI

仓库包含 GitHub Actions：

- Python 模板语法检查
- Node 脚本语法检查
- README/模板敏感信息占位符检查

推送到 GitHub 后会自动触发构建。

## License

MIT
