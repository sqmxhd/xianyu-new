# Phase 2-Web：持久化与运行事件

本阶段把 Phase 1 的内存状态切到数据库，并补充运行事件日志。

## 已落地范围

- 支持 `XIANYU_DATABASE_URL` 配置数据库。
- 默认使用本地 SQLite，方便开发。
- 生产可切到 MySQL：

```bash
export XIANYU_DATABASE_URL='mysql+pymysql://user:password@mysql-host:3306/xianyu_admin?charset=utf8mb4'
```

- 自动创建基础表：
  - `xianyu_accounts`
  - `xianyu_runtime_status`
  - `xianyu_runtime_events`
- 账户、Cookie、代理配置、运行状态已持久化。
- 每次状态变化会写入运行事件。
- Ant Design 后台新增“事件”按钮，可查看单个账户的运行事件。

## 当前边界

- Cookie 仍是明文存储。后续进入真实生产前，应增加加密存储或密钥管理。
- 当前 runtime 仍是单 API 进程内运行。多进程部署时，需要引入 worker 归属和分布式锁。
- 前端状态刷新仍是 3 秒轮询。后续可升级为 SSE/WebSocket。
- 队列尚未接入消息处理流，等消息列表和自动回复阶段再接入更合理。

## 下一阶段建议

Phase 3-Web：会话列表与消息收发。该阶段已开始落地，详见：

- `docs/phase3-web-conversations-messages.md`

优先级：

1. 新增 `xianyu_conversations`、`xianyu_messages` 表。
2. runtime 收到消息后写 DB。
3. 后台新增会话列表和聊天窗口。
4. 后台支持手动发送文本消息。
5. Bark 通知可在消息入库后接入。
