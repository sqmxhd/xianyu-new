# Xianyu Admin API

Phase 1-15 Web 后端，提供账户、SOCKS5 代理、批量启动/停止、运行状态、运行事件、会话、消息、商品/订单卡片解析、Bark 通知、自动回复、发货前置、商品草稿、任务队列、安全鉴权和审计日志。

## 数据库

使用 `.env.local` 配置数据库。当前实测使用 MySQL：

```bash
export XIANYU_DATABASE_URL='mysql+pymysql://user:password@mysql-host:3306/xianyu_admin?charset=utf8mb4'
```

服务启动时会自动创建基础表：

- `xianyu_accounts`
- `xianyu_runtime_status`
- `xianyu_runtime_events`
- `xianyu_conversations`
- `xianyu_messages`
- `xianyu_message_cards`
- `xianyu_bark_config`
- `xianyu_account_notifications`
- `xianyu_auto_reply_settings`
- `xianyu_auto_reply_rules`
- `xianyu_auto_reply_logs`
- `xianyu_delivery_templates`
- `xianyu_delivery_records`
- `xianyu_delivery_automation_settings`
- `xianyu_product_drafts`
- `xianyu_product_publish_tasks`
- `xianyu_background_tasks`
- `xianyu_audit_logs`

## 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
pip install -r integrations/xianyu_core/requirements.txt
npm run start:api
```

说明：

- `apps/api/requirements.txt` 是后台 API 依赖。
- `integrations/xianyu_core/requirements.txt` 是真实闲鱼连接依赖。
- `XIANYU_DATABASE_URL` 使用 MySQL。
- 必须设置 `XIANYU_JWT_SECRET`，用于用户名/密码登录后的 JWT 签名。
- 设置 `XIANYU_CORS_ORIGINS` 可覆盖后台允许的 CORS 来源，多个来源用逗号分隔。
- `third_party/XianYuApis` 不在这里修改。

## 安全鉴权

内网调试和生产部署都使用同一套正式登录链路。

除 `/api/health`、`/api/auth/setup-status`、`/api/auth/client-info`、`/api/auth/login`、`/api/auth/bootstrap` 外，所有 `/api/*` 请求都需要：

```text
Authorization: Bearer <jwt>
```

首次部署时，用户表为空才允许调用 `/api/auth/bootstrap` 初始化首个管理员。

登录页访问来源解析优先级：

```text
CF-Connecting-IP -> True-Client-IP -> X-Real-IP -> X-Forwarded-For -> remote_addr
```

## 消息接口

```text
GET  /api/accounts/{account_id}/conversations
GET  /api/accounts/{account_id}/conversations/{conversation_id}/messages
GET  /api/accounts/{account_id}/message-cards
GET  /api/accounts/{account_id}/conversations/{conversation_id}/cards
POST /api/accounts/{account_id}/conversations/{conversation_id}/send-text
```

说明：

- 所有会话和消息接口都带 `account_id`，避免多账户串数据。
- 当前文本消息已接入。
- 商品卡片、订单卡片会从 raw payload 中保守解析，并落入 `xianyu_message_cards`。
- 非文本消息仍保留 raw payload，便于后续根据真实样本增强 parser。

## 卡片解析接口

```text
GET /api/accounts/{account_id}/message-cards
GET /api/accounts/{account_id}/conversations/{conversation_id}/cards
```

说明：

- 当前支持解析 `product` 和 `order` 两类卡片。
- 解析字段包括商品 ID、订单 ID、标题、价格、状态、图片 URL。
- parser 不改 `third_party/XianYuApis`，只在本项目消息入库后处理 raw payload。
- 解析规则保持保守，避免把普通文本误判为订单。

## Bark 通知接口

```text
GET  /api/notifications/bark
PUT  /api/notifications/bark
POST /api/notifications/bark/test
GET  /api/accounts/{account_id}/notification
PUT  /api/accounts/{account_id}/notification
```

触发条件：

- Bark 全局配置已启用。
- Bark device key 已配置。
- 账户级通知开关已启用。
- runtime 收到入站消息并成功入库。

说明：

- Bark 通知是后台通知渠道，不走闲鱼账户 SOCKS5 代理。
- 闲鱼 WS/MTOP 收发消息仍走账户绑定的 SOCKS5/SOCKS5h 代理。

## 自动回复接口

```text
GET    /api/accounts/{account_id}/auto-reply
PUT    /api/accounts/{account_id}/auto-reply
GET    /api/accounts/{account_id}/auto-reply/rules
POST   /api/accounts/{account_id}/auto-reply/rules
PUT    /api/accounts/{account_id}/auto-reply/rules/{rule_id}
DELETE /api/accounts/{account_id}/auto-reply/rules/{rule_id}
GET    /api/accounts/{account_id}/auto-reply/logs
```

说明：

- 只处理入站文本消息。
- 规则按 `priority` 从小到大匹配，先命中先回复。
- 支持包含匹配和完全匹配。
- 自动回复通过当前账号 runtime 的 WS session 发送，继续走账号绑定 SOCKS5/SOCKS5h。
- 发送成功/失败都会写入自动回复日志。

## 发货前置接口

```text
GET    /api/accounts/{account_id}/delivery/templates
POST   /api/accounts/{account_id}/delivery/templates
PUT    /api/accounts/{account_id}/delivery/templates/{template_id}
DELETE /api/accounts/{account_id}/delivery/templates/{template_id}

GET    /api/accounts/{account_id}/delivery/records
GET    /api/accounts/{account_id}/delivery/automation
PUT    /api/accounts/{account_id}/delivery/automation
POST   /api/accounts/{account_id}/delivery/records/{record_id}/preflight
POST   /api/accounts/{account_id}/conversations/{conversation_id}/delivery/prepare
POST   /api/accounts/{account_id}/delivery/records/{record_id}/send
```

说明：

- 当前只做发货内容通过 WS 文本发送给买家。
- 发货记录可关联商品/订单卡片，并做状态白名单和防重复检查。
- 不调用闲鱼平台确认发货/订单 MTOP 接口。
- 不做浏览器自动化。
- 发送成功/失败都会写发货记录。
- 发货发送继续走账号绑定 SOCKS5/SOCKS5h。

## 商品发布接口

```text
GET    /api/accounts/{account_id}/products/drafts
POST   /api/accounts/{account_id}/products/drafts
PUT    /api/accounts/{account_id}/products/drafts/{draft_id}
DELETE /api/accounts/{account_id}/products/drafts/{draft_id}

GET    /api/accounts/{account_id}/products/publish-tasks
POST   /api/accounts/{account_id}/products/publish-tasks
```

说明：

- 当前只做商品草稿和发布任务管理。
- `platform_api` / `browser_automation` 发布执行器尚未接入。

## 任务队列与审计接口

```text
GET /api/tasks
POST /api/tasks

GET /api/audit-logs
```

说明：

- 后台任务固定使用 `XIANYU_REDIS_URL` 对应的 Redis 和服务端队列名，不提供运行时关闭或改名接口。
- Redis 队列只传递 `task_id`，MySQL 的 `xianyu_background_tasks` 仍是任务 payload、状态和结果的数据源。
- Worker 会扫描 MySQL 中遗漏投递的待执行任务，避免 Redis 消息丢失后任务永久滞留。
- POST/PUT/DELETE API 会自动写审计日志。
