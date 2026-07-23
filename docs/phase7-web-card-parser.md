# Phase 7-Web：订单/商品卡片解析

本阶段实现消息 raw payload 的保守解析，把商品卡片和订单卡片抽取成独立记录，并在 Ant 管理后台会话详情中展示。

## 已落地范围

- 新增卡片解析模块：`apps/api/xianyu_admin_api/card_parser.py`
- 消息入库后自动解析 raw payload：
  - 商品卡片：`product`
  - 订单卡片：`order`
- 解析字段：
  - 商品 ID
  - 订单 ID
  - 标题
  - 价格
  - 状态
  - 图片 URL
- 会话详情展示“解析卡片”表格。
- 不修改 `third_party/XianYuApis`。

## 数据表

- `xianyu_message_cards`

表记录与账号、会话、原始消息关联，便于后续发货记录关联订单或商品。

## API

```text
GET /api/accounts/{account_id}/message-cards
GET /api/accounts/{account_id}/conversations/{conversation_id}/cards
```

## Parser 策略

当前 parser 采用保守规则：

- raw payload 会递归遍历 dict/list/JSON 字符串。
- 命中订单 ID 时优先识别为订单卡片。
- 命中商品 ID 且同时存在标题、价格、状态、图片等信号时识别为商品卡片。
- 如果消息本身已有 `item_id`，允许生成最低限度商品卡片。
- 所有原始消息仍保存 raw payload，后续可以根据真实样本增强规则。

## 重要边界

- 当前只做解析和展示。
- 不调用闲鱼订单接口。
- 不确认发货。
- 不做浏览器自动化。
- 不自动根据订单状态触发发货。

## 与代理的关系

parser 是本地入库后的数据处理，不直接访问闲鱼网络。

真正的收发消息仍由账号 runtime 执行，继续走账号绑定 SOCKS5/SOCKS5h。

## 下一阶段建议

Phase 8-Web：发货记录关联商品/订单卡片。

建议先做：

1. 发货表增加 `card_id` / `order_id` 关联。
2. 生成发货记录时允许从已解析卡片中选择商品或订单。
3. 增加订单状态白名单，例如只允许待发货状态进入发货候选。
4. 收集真实订单卡片 raw payload 样本，再增强 parser。
