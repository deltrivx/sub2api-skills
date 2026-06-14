# Sub2API Skills 与 Telegram / QQ 运维机器人

这个仓库提供 Sub2API 的助手 Skill、Telegram 与 QQ 双后端运维机器人模板，以及可选的 Docker sidecar 部署方案。它适合在不修改 Sub2API 官方镜像和官方容器的前提下，为 Sub2API 增加查询、诊断、账号导入、备份、重启和更新等运维能力。

两个机器人共享同一份业务逻辑（`bot_core.py`），只切换传输层：

- Telegram Bot（`telegram-bot.py`）：基于 `getUpdates` 长轮询。
- QQ Bot（`qq-bot.py`）：基于 [QQ 开放平台 v2](https://bot.q.qq.com/wiki/develop/api-v2/) 的 WebSocket Gateway，支持频道 @、群 @、C2C 私聊消息。

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

## 四、Telegram 运维机器人

模板位置：

- 公共命令模块：`skills/sub2api/templates/bot_core.py`（与传输层无关，Telegram 与 QQ 共用）
- Telegram 传输层：`skills/sub2api/templates/telegram-bot.py`

机器人支持系统级部署和 Docker sidecar 部署。系统级部署适合直接运行在 Sub2API 所在主机；Docker sidecar 部署适合 Docker 版 Sub2API，独立运行在旁路容器中，不修改官方镜像和官方容器。

## 4.5、QQ 运维机器人

QQ Bot 模板与 Telegram 共用 `bot_core.py` 的全部业务命令，仅传输层不同。

- QQ 传输层：`skills/sub2api/templates/qq-bot.py`
- QQ 文档：[`skills/sub2api/docs/qq-bot.md`](skills/sub2api/docs/qq-bot.md)

QQ Bot 使用的官方端点：

| 用途 | URL |
| --- | --- |
| 获取调用凭证 | `https://bots.qq.com/app/getAppAccessToken` |
| OpenAPI（正式） | `https://api.sgroup.qq.com/` |
| OpenAPI（沙箱） | `https://sandbox.api.sgroup.qq.com/` |
| WebSocket Gateway | `wss://api.sgroup.qq.com/websockets`（通过 `/gateway` 自动发现） |

QQ Bot 默认订阅公开频道 @ 消息、群 @ 消息、C2C 私聊和交互事件；按钮类确认 UI 在 QQ 平台需要审核模板，因此 QQ 后端回退到与 Telegram 相同的 `/confirm <code>` 文字确认码，控制命令的安全性保持一致。

### 4.6、QQ Bot 沙箱与使用场景

QQ 机器人默认处于**沙箱环境**（未发布上线），需要在 [QQ 开放平台 → 沙箱配置](https://q.qq.com/qqbot/#/developer/sandbox) 里把测试对象加进去，机器人才能与它们收发消息：

- **消息列表（C2C 私聊）**：沙箱配置页"添加成员"，成员的 QQ 消息列表里就会出现机器人，可直接私聊发命令。
- **QQ 群**：沙箱配置页选择一个测试群（管理员须为群主/管理员，群成员 ≤ 20），群主在"设置 → 群机器人"里添加机器人。
- **QQ 频道**：同理绑定一个测试频道。

在"功能配置 → 指令"里添加指令时，**使用场景**勾选项受沙箱配置约束：未在沙箱配置的对象，对应场景会被禁用（`usescene-item-forbit`），指令无法保存。建议至少先在沙箱配置里加一个测试成员解锁"消息列表"场景。

### 4.7、QQ Bot 富文本回复

QQ Bot 在 C2C 私聊和群聊场景下，回复优先使用 **Markdown 消息**（`msg_type=2`）。自 2026/04/23 起，单聊/群聊的自定义 Markdown 已对所有机器人开放，无需单独申请模板（参考 [Markdown 消息文档](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/markdown.html)）。

- 回复内容的首行若像标题（以"："结尾的短句），会自动加粗。
- 长回复按段落切分，避免破坏 Markdown 结构。
- 若 Markdown 发送失败（如命中频控、内容被拦截），自动降级为纯文本（`msg_type=0`），保证可达性。
- 频道场景的 Markdown 需要内邀开通，因此频道后端仍使用纯文本。

### 4.8、双后端模式（QQ + Telegram 同时运行）

设置 `SUB2API_BOT_BACKEND=both` 可以在**单个容器内同时运行 QQ Bot 和 Telegram Bot**，共享同一份 `bot_core.py` 业务逻辑和 Sub2API 后端。

工作方式：

- `entrypoint.sh` 在 `both` 模式下后台启动 `sub2api_qq_bot.py` 和 `sub2api_telegram_bot.py` 两个进程。
- **容错**：任一进程退出不会立即拖垮另一个。例如 Telegram 因网络问题退出时，QQ 继续服务；反之亦然。只有两个进程都退出时容器才会重启（`restart: always`）。
- `SUB2API_BOT_SECRETS_FILE` 在 `both` 模式下同时包含 `qq_app_id`/`qq_app_secret` 和 `telegram_bot_token`。
- 白名单 `SUB2API_BOT_ALLOWED_CHAT_IDS` 同时列出两类 id，逗号分隔。Telegram 的 `setup_bot_menu` 会自动跳过非数字的 QQ openid，避免对 Telegram API 产生 400 错误。

适用场景：

- 希望一个容器同时覆盖 QQ 和 Telegram 用户，减少资源占用。
- 两边命令完全一致（`/help`、`/status`、`/accounts` 等），因为共享 `bot_core.py`。
- 若只想要单一后端，仍可使用 `telegram` 或 `qq`。

### 查询与诊断

- `/status`：综合状态、用量、限流和余额
- `/accounts`：账号列表与路由状态
- `/models`：模型与映射信息
- `/channels`：渠道与分组概览
- `/tokens`：API 令牌列表、额度与用量，Key 脱敏
- `/debug`：健康检查与日志摘要

### 导入与维护

- `/importhelp`：查看账号文件导入说明
- 发送 `.json` / `.txt` 账号文件，或 `.zip` / `.tar` / `.tar.gz` / `.tgz` 压缩包：自动安全解压、扫描账号文件、创建/匹配分组、导入账号并报告账号信息
- `/backup`：生成本地配置备份

### 带确认保护的控制命令

以下命令会先确认再执行：

- `/pending`：查看待确认操作
- `/confirm <code>`：确认执行
- `/cancel`：取消待确认操作
- `/restart`：先弹出 `Bot` / `Sub2API` 选择按钮，再进入确认/取消
- `/restart bot|sub2api`：直接指定目标并进入确认
- `/update`：先立即提示正在检测更新；系统级部署走本机 updater，Docker 部署比对官方镜像后再决定是否提示确认/取消

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
- 压缩包只处理其中的 `.json` / `.txt`，自动忽略其他文件，并限制文件数量、单文件大小和解压总量
- 自动创建或匹配分组
- 自动写入 `accounts` 与 `account_groups`
- 自动写入 `scheduler_outbox`
- 默认 `schedulable=false`，确认无误后再按部署策略开启调度
- 回复中只展示凭据字段名，不展示明文凭据

## 六、系统级部署 Telegram Bot

系统级部署适合 Sub2API 以二进制、systemd 或其他主机服务方式运行的环境。

1. 复制模板和环境变量示例：

```bash
sudo install -m 700 skills/sub2api/templates/telegram-bot.py /opt/sub2api-telegram-bot.py
sudo install -m 600 docker/sub2api-skill/sub2api-skill.env.example /etc/sub2api-bot.env
```

2. 编辑环境变量：

```bash
sudo editor /etc/sub2api-bot.env
```

3. 创建 systemd 服务并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sub2api-telegram-bot
```

系统级 `/update` 会调用 `SUB2API_UPDATER_SCRIPT` 指定的更新脚本；如果检测到已是最新版，会直接提示“已是最新版”。

## 七、Docker sidecar 部署

Docker sidecar 部署适合 Docker 版 Sub2API。它使用独立镜像和独立目录运行 Telegram Bot，不修改 `weishaw/sub2api:latest` 官方镜像，也不向官方 Sub2API 容器写入文件。

镜像：

```text
ghcr.io/deltrivx/sub2api-skill:latest
```

推荐目录结构：

```text
<docker-root>/sub2api/
  docker-compose.yml
  data/
<docker-root>/sub2api-skill/
  docker-compose.yml
  .env
  config/sub2api-bot-secrets.json
  data/
```

复制示例文件：

```bash
mkdir -p sub2api-skill/config sub2api-skill/data
cp docker/sub2api-skill/docker-compose.yml sub2api-skill/docker-compose.yml
cp docker/sub2api-skill/sub2api-skill.env.example sub2api-skill/.env
```

编辑 `sub2api-skill/.env`，至少配置：

```env
# 选择后端：telegram | qq | both
SUB2API_BOT_BACKEND=telegram

SUB2API_BASE_URL=http://127.0.0.1:<sub2api-port>
SUB2API_BOT_ALLOWED_CHAT_IDS=<chat-id>
SUB2API_ADMIN_EMAIL=<admin-email>
SUB2API_ADMIN_PASSWORD_B64=<base64-admin-password>
DATABASE_HOST=127.0.0.1
DATABASE_PORT=<postgres-port>
DATABASE_USER=<postgres-user>
DATABASE_PASSWORD=<postgres-password>
DATABASE_DBNAME=sub2api
SUB2API_DEPLOY_DIR=/sub2api-compose
SUB2API_IMAGE=weishaw/sub2api:latest
DOCKER_COMPOSE_CMD=docker compose
```

`SUB2API_BOT_BACKEND` 选择启动哪个后端：

- `telegram`：还需要 `TELEGRAM_BOT_TOKEN=<telegram-bot-token>`，`SUB2API_BOT_ALLOWED_CHAT_IDS` 用 Telegram chat_id。
- `qq`：还需要 `QQ_APP_ID=<qq-app-id>` 和 `QQ_APP_SECRET=<qq-app-secret>`（在 [q.qq.com](https://q.qq.com) 创建机器人后获取），`SUB2API_BOT_ALLOWED_CHAT_IDS` 用 `channel:<channel_id>` / `group:<group_openid>` / `c2c:<user_openid>` 或裸 openid。沙箱调试可设 `SUB2API_QQ_SANDBOX=1`。
- `both`：同时运行 Telegram + QQ 双后端（详见 4.8 节）。需要同时配置 `TELEGRAM_BOT_TOKEN` 和 `QQ_APP_ID`/`QQ_APP_SECRET`，`SUB2API_BOT_ALLOWED_CHAT_IDS` 用逗号分隔列出 Telegram 数字 chat_id 和 QQ openid（如 `8646289271,72A938D331BF51525291207DE760F5FD`）。

如果 Telegram 访问需要代理，可以同时配置：

```env
HTTP_PROXY=http://<proxy-host>:<proxy-port>
HTTPS_PROXY=http://<proxy-host>:<proxy-port>
NO_PROXY=localhost,127.0.0.1,*.local
http_proxy=http://<proxy-host>:<proxy-port>
https_proxy=http://<proxy-host>:<proxy-port>
no_proxy=localhost,127.0.0.1,*.local
```

启动：

```bash
cd sub2api-skill
docker compose up -d
```

Docker sidecar 的关键挂载：

- `./config:/config`：保存 Bot secrets
- `./data:/data`：保存 offset、待确认操作、导入缓存和备份
- `<docker-root>/sub2api/data:/sub2api-data:ro`：只读访问 Sub2API 数据目录
- `<docker-root>/sub2api:/sub2api-compose:ro`：只读访问官方 Sub2API compose 目录，用于 `/update` 按官方 compose 重建
- `/var/run/docker.sock:/var/run/docker.sock`：允许 Bot 执行受确认保护的 Docker 重启/更新动作

Docker 版 `/update` 行为：

1. 立即回复“正在检测 Docker 版 Sub2API 镜像更新，请稍等…”
2. 比对本地 `weishaw/sub2api:latest` 与远端官方镜像 digest
3. 如果一致，回复“已是最新版”
4. 如果有更新，弹出确认/取消按钮
5. 确认后执行 `docker compose pull sub2api`
6. 使用官方 Sub2API `docker-compose.yml` 重建 `sub2api` 服务
7. 等待健康检查并清理旧悬空镜像

## 八、安全原则

- 不提交真实 Token、密码、JWT、API Key、Chat ID、数据库地址或内网地址
- 所有敏感配置通过环境变量或本地 secrets 文件传入
- Bot 只允许 `SUB2API_BOT_ALLOWED_CHAT_IDS` 中的聊天使用
- 所有控制命令必须确认码或按钮确认
- 导入账号默认关闭调度
- 日志和回复默认脱敏
- Docker sidecar 默认不修改官方 Sub2API 镜像；更新动作只在确认后通过官方 compose 执行

## 九、CI 与镜像构建

仓库包含 GitHub Actions：

- Python 模板语法检查
- Node 脚本语法检查
- JSON 文件校验
- README/模板敏感信息占位符检查
- Docker sidecar 镜像构建并推送到 GHCR

## 十、免责声明

本项目是面向 Sub2API 的独立社区集成与运维模板，并非 Sub2API 官方组件，除非后续被 Sub2API 官方维护者明确接纳或合并。

请自行评估风险后使用。生产环境部署前，请先阅读源码，在非生产环境测试，并确认 SQL 查询、表名、服务名、文件路径、权限模型、调度规则和告警策略符合你的实际部署。

本项目不提供法律、财务、合规、安全或运维层面的保证。使用者需要自行负责：

- 妥善保护 API Key、Refresh Token、Telegram Token、QQ AppID/AppSecret、数据库凭据和管理密码；
- 遵守上游服务商条款、本地法律法规和平台规则；
- 确认账号共享、额度分发、API 转发、计费统计、自动化导入和运维操作均已获得授权；
- 限制 Telegram Bot 可访问的 Chat ID、QQ Bot 可访问的 channel/group/user 白名单，并保护环境变量文件和备份文件；
- 对 `/restart`、`/update`、账号导入和备份等管理动作的结果负责。

模板中的控制命令已设计为确认保护，但这不能替代完善的权限隔离、日志审计、备份保护和生产变更流程。任何因部署、配置、误操作、凭据泄露、上游封禁、计费异常或第三方服务变化造成的损失，由使用者自行承担。

所有第三方名称和商标均归其各自所有者所有。本文档中提到 Sub2API、OpenAI、Anthropic、Gemini、Telegram、QQ、腾讯、GitHub、Docker 等，仅用于兼容性说明和使用文档。

## English README

English documentation: [`README_EN.md`](README_EN.md)

## License

MIT
