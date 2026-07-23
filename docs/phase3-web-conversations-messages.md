# Phase 3-Web：会话列表与消息收发

本阶段把消息从 runtime 回调接入数据库，并在 Ant Design 后台提供会话和聊天窗口。

## 已落地范围

- 新增数据库表：
  - `xianyu_conversations`
  - `xianyu_messages`
- runtime 收到 `ChatMessageEvent` 后写入消息表。
- 会话表按账号隔离，`conversation_id` 不假设全局唯一。
- 手动发送文本消息接口会调用当前账号的运行中 WS session。
- 发送成功和失败都会写入消息表，便于后台排查。
- Ant Design 后台账户列表新增“会话”按钮。
- 会话抽屉包含：
  - 左侧会话列表
  - 右侧消息列表
  - 文本发送区

## API

```text
GET  /api/accounts/{account_id}/conversations
GET  /api/accounts/{account_id}/conversations/{conversation_id}/messages
POST /api/accounts/{account_id}/conversations/{conversation_id}/send-text
```

发送文本请求体：

```json
{
  "receiver_user_id": "买家用户 ID",
  "text": "要发送的文本"
}
```

## 当前边界

- 只做文本消息发送。
- 图片、商品卡片、订单卡片暂不做结构化解析。
- 非文本消息后端会保留 raw payload，后续可按类型补 parser。
- 会话 unread_count 当前只在收到入站消息时累加，暂未做“打开会话即已读”。
- 前端状态仍为轮询刷新，未接 SSE/WebSocket 推送。

## 下一阶段建议

Phase 4-Web：Bark 通知。该阶段已落地，详见：

- `docs/phase4-web-bark-notifications.md`

原因：

- 消息已经入库，Bark 可以基于“新入站消息”稳定触发。
- 通知失败可以写运行事件。
- 自动回复应在通知之后做，避免还没可观测就开始自动化动作。
