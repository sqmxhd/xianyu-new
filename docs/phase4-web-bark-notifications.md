# Phase 4-Web：Bark 通知

本阶段接入 Bark 通知，作为消息入库后的通知层。

## 已落地范围

- 新增 Bark 全局配置：
  - enabled
  - server_url
  - device_key
  - group
  - sound
  - icon
- 新增账户级通知开关。
- Ant Design 后台新增 Bark 配置卡片。
- 支持保存配置。
- 支持测试发送。
- runtime 收到入站消息并写入 DB 后，触发 Bark 通知。
- Bark 发送失败会写运行事件，不改变账户运行状态。

## 数据表

- `xianyu_bark_config`
- `xianyu_account_notifications`

## API

```text
GET  /api/notifications/bark
PUT  /api/notifications/bark
POST /api/notifications/bark/test

GET  /api/accounts/{account_id}/notification
PUT  /api/accounts/{account_id}/notification
```

## 触发条件

只有同时满足以下条件才会发送 Bark：

1. Bark 全局开关启用。
2. Bark `device_key` 已配置。
3. 账户通知开关启用。
4. runtime 收到的是入站消息。
5. 消息已成功写入数据库。

## 代理边界

Bark 通知不走闲鱼账户 SOCKS5 代理。

原因：

- 账户代理用于闲鱼 WS/MTOP 账号流量，目标是保持账号网络环境一致。
- Bark 是后台通知渠道，不属于闲鱼账号流量。
- 混用账号代理发送 Bark 会增加通知失败面，也会污染账号代理职责。

## 下一阶段建议

Phase 5-Web：自动回复规则。该阶段已落地，详见：

- `docs/phase5-web-auto-reply.md`

建议先做最小规则：

1. 账户级自动回复开关。
2. 关键词匹配。
3. 默认回复。
4. 命中日志。

失败重试和商品维度规则后续再做。
