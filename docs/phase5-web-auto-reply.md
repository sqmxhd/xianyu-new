# Phase 5-Web：自动回复规则

本阶段在消息入库后接入自动回复规则。

## 已落地范围

- 账户级自动回复开关。
- 默认回复开关和默认回复内容。
- 会话白名单、黑名单和全局冷却时间。
- 关键词规则：
  - 启用/关闭
  - 关键词
  - 包含匹配 / 完全匹配
  - 大小写敏感开关
  - 回复内容
  - 优先级
  - 会话和商品范围
  - 规则冷却时间
- OpenAI 兼容接口：API 地址、模型、服务端密钥、系统提示词和 1-50 条上下文窗口。
- 会话级人工接管，可暂停 30 分钟后恢复自动回复，也可提前手动恢复。
- 自动回复日志：
  - 命中的规则
  - 发送内容
  - 成功/失败
  - 错误原因
- Ant Design 后台新增“回复”按钮，可配置规则和查看日志。

## 数据表

- `xianyu_auto_reply_settings`
- `xianyu_auto_reply_rules`
- `xianyu_auto_reply_logs`

## API

```text
GET    /api/accounts/{account_id}/auto-reply
PUT    /api/accounts/{account_id}/auto-reply

GET    /api/accounts/{account_id}/auto-reply/rules
POST   /api/accounts/{account_id}/auto-reply/rules
PUT    /api/accounts/{account_id}/auto-reply/rules/{rule_id}
DELETE /api/accounts/{account_id}/auto-reply/rules/{rule_id}

GET    /api/accounts/{account_id}/auto-reply/logs
POST   /api/accounts/{account_id}/conversations/{conversation_id}/manual-takeover
```

## 触发条件

只有同时满足以下条件才会自动回复：

1. 收到的是入站消息。
2. 消息类型是文本。
3. 消息已成功入库。
4. 账户自动回复开关已启用。
5. 会话没有处于人工接管、黑名单或冷却状态。
6. 命中关键词规则，或 AI/默认回复已完整配置。
7. 当前账号 runtime 可发送消息，并收到平台成功 ACK。

## 代理边界

自动回复通过当前账号 runtime 的 WS session 发出，因此继续走账号绑定的 SOCKS5/SOCKS5h 代理。

## 当前边界

- 暂不支持图片/商品卡片/订单卡片触发规则。
- 暂不支持失败自动重试。
- AI 提供商当前要求兼容 `/chat/completions` 响应格式。

## 下一阶段建议

Phase 6-Web：自动发货前置能力。该阶段已落地，详见：

- `docs/phase6-web-delivery-preflight.md`

本阶段仍不做平台确认发货动作，先做：

1. 订单/交易消息识别。
2. 商品卡片和订单卡片 parser。
3. 发货模板配置。
4. 人工确认后发送发货内容。
5. 再评估是否接自动发货。
