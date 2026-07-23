# Phase 6-Web：自动发货前置能力

本阶段实现发货模板、人工确认发送和发货记录。

## 已落地范围

- 发货模板管理：
  - 新增
  - 编辑
  - 删除
  - 启用/关闭
  - 优先级
- 聊天窗口内人工确认发货：
  - 选择模板
  - 填写接收方用户 ID
  - 填写商品 ID / 买家名
  - 生成发货记录
  - 确认发送
- 发货记录：
  - pending
  - sent
  - failed
  - 错误原因
- 发送链路复用当前账号 runtime 的 WS 文本发送。

## 数据表

- `xianyu_delivery_templates`
- `xianyu_delivery_records`

## API

```text
GET    /api/accounts/{account_id}/delivery/templates
POST   /api/accounts/{account_id}/delivery/templates
PUT    /api/accounts/{account_id}/delivery/templates/{template_id}
DELETE /api/accounts/{account_id}/delivery/templates/{template_id}

GET    /api/accounts/{account_id}/delivery/records
POST   /api/accounts/{account_id}/conversations/{conversation_id}/delivery/prepare
POST   /api/accounts/{account_id}/delivery/records/{record_id}/send
```

## 模板占位符

当前支持：

- `{receiver_user_id}`
- `{conversation_id}`
- `{item_id}`
- `{peer_name}`

## 重要边界

当前阶段不做以下动作：

- 不调用闲鱼平台确认发货/订单 MTOP 接口。
- 不做浏览器自动化发货。
- 不自动识别订单状态后直接发货。
- 不自动确认交易。

当前“发货”只是把模板内容通过闲鱼 WS 文本消息发给买家，并记录审计日志。

## 代理边界

发货内容发送复用账号 runtime 的 WS session，因此继续走账号绑定的 SOCKS5/SOCKS5h。

## 后续状态

Phase 7-Web 已开始落地订单/商品卡片 parser：

1. 从 raw payload 中保守解析商品 ID、订单 ID、交易状态。
2. 在会话中展示商品/订单摘要。
3. parser 不修改 `third_party/XianYuApis`。

下一步建议把发货记录与已解析的商品/订单卡片关联起来，再评估真正的自动发货接口。
