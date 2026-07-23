# 阶段 0：闲鱼消息核心整合方案

本文档固定当前阶段的实施边界：先做登录、账号、代理、收发消息、会话列表和 Bark 通知；自动发货和商品发布后置。

## 目标

第一阶段系统需要具备：

- 多账号管理。
- 每个账号绑定独立 SOCKS5/SOCKS5h 代理。
- 账号启停、在线状态、错误状态。
- WebSocket 收消息和发消息。
- 会话列表与消息记录。
- Bark 通知渠道。

暂不做：

- 自动发货。
- 商品发布。
- 复杂 AI 回复。
- HTTP 代理。

## 上游边界

`third_party/XianYuApis` 是上游协议代码，保持原样，不在该目录内修改源码。后续更新上游时直接进入该目录拉取或替换。

项目自有代码放在：

```text
integrations/xianyu_core/
```

业务层只能依赖 `integrations.xianyu_core` 暴露的模型与接口，不能直接依赖上游的 `goofish_live.py`、`goofish_apis.py`、`utils` 或 `message`。

原因：

- 上游当前是协议 demo 形态，不是稳定业务库。
- 上游存在顶层 `utils`、`message` 包名，直接导入容易和项目包冲突。
- 不改上游能降低后续更新冲突。

## 代理策略

只支持 SOCKS5/SOCKS5h，不支持 HTTP 代理。

默认推荐：

```text
socks5h://user:pass@host:port
```

`socks5h` 表示 DNS 解析也走代理。账号启用代理后，不允许静默直连；代理不可用时账号进入 `proxy_failed` 或 `error` 状态。

代理覆盖范围：

- WebSocket 收消息。
- WebSocket 发消息。
- Token 获取与刷新。
- 图片上传。
- 商品详情、订单相关 MTOP 请求。
- 后续自动发货确认接口。
- 后续商品发布相关接口或浏览器上下文。

注意：不支持 HTTP 代理不代表不用 HTTPS/MTOP 接口。闲鱼平台确认发货、Token、图片上传等能力本身就是 HTTP/HTTPS 接口，但这些请求必须通过账号 SOCKS 代理出站。

## GuDong 自动发货实现判断

`GuDong2003/xianyu-auto-reply-fix` 的自动发货主流程不是浏览器点击。

已确认的实现方式：

- 发货内容发送给买家：走 WebSocket 消息发送。
- 平台确认发货：走 MTOP HTTP 接口 `mtop.taobao.idle.logistic.consign.dummy`。
- 免拼发货：走 MTOP HTTP 接口 `mtop.idle.groupon.activity.seller.freeshipping`。
- 浏览器自动化主要用于登录、滑块、Cookie 刷新和风控恢复。

因此后续迁移自动发货时，应先抽取规则、库存、防重复、发送、确认、日志、通知，不应直接搬浏览器逻辑。

## 本地讨论记录补充

`临时文件/讨论` 中记录的是对 `wss-cntaobao.dingtalk.com` 的本地 WSS 调试，包含浏览器握手、消息帧和独立 WebSocket 客户端尝试。

结论纳入设计：

- 101 Switching Protocols 只说明 WebSocket 握手成功，不代表业务认证完成。
- 独立 WebSocket 工具如果缺少初始化、认证、绑定帧，发送业务消息会被服务端拒绝。
- 当前主线仍以 XianYuApis 的闲鱼/Goofish 协议实现为基础，浏览器抓包记录作为协议排查参考。

## 账号生命周期

账号启动：

```text
读取账号配置
  ↓
读取账号代理
  ↓
构造 socks5h 代理 URL
  ↓
创建账号会话
  ↓
通过代理建立 WebSocket
  ↓
获取/刷新 token
  ↓
发送初始化/注册帧
  ↓
启动心跳与消息循环
  ↓
状态改为 online
```

账号断线：

```text
连接异常
  ↓
状态改为 reconnecting
  ↓
按退避策略重连
  ↓
代理失败则进入 proxy_failed
  ↓
认证失败则进入 auth_expired
  ↓
超过阈值触发 Bark 通知
```

账号停止：

```text
停止心跳
  ↓
关闭 WebSocket
  ↓
取消后台任务
  ↓
状态改为 stopped
```

## 消息流程

收消息：

```text
WebSocket 原始帧
  ↓
ACK
  ↓
decrypt / parse
  ↓
转换为 ChatMessageEvent
  ↓
消息去重
  ↓
写入 chat_messages
  ↓
更新 chat_sessions
  ↓
触发 Bark 通知
  ↓
后续自动回复模块消费事件
```

发消息：

```text
后台选择会话
  ↓
调用 XianyuCoreClient.send_text
  ↓
通过账号当前 WebSocket 发送
  ↓
写入 outbound 消息
  ↓
等待发送响应或异常
  ↓
更新 send_status
```

## 第一阶段数据模型

建议最小表：

```text
accounts
account_proxies
chat_sessions
chat_messages
notification_channels
notification_events
```

关键字段：

```text
accounts:
  account_id, nickname, cookie, enabled, status,
  last_online_at, last_message_at, last_error, proxy_id

account_proxies:
  account_id, scheme, host, port, username, password,
  enabled, last_check_status, last_check_at

chat_sessions:
  account_id, conversation_id, peer_user_id, peer_name,
  item_id, last_message, last_message_at, unread_count

chat_messages:
  account_id, conversation_id, message_id, peer_user_id,
  direction, message_type, content, raw_payload, send_status

notification_channels:
  type, name, enabled, config_json
```

## Bark 通知

第一版只做 Bark。

配置：

```json
{
  "server": "https://api.day.app",
  "key": "xxxx",
  "group": "xianyu",
  "sound": "bell"
}
```

触发场景：

- 新买家消息。
- 账号上线。
- 账号掉线。
- 代理不可用。
- Cookie/Token 失效。
- 发送消息失败。

## 阶段计划

### 阶段 1：单账号收发消息

- 单账号 Cookie 启动。
- SOCKS5h WebSocket 连接。
- Token 获取。
- 心跳。
- ACK。
- 收文本消息。
- 发文本消息。
- 消息落库。

### 阶段 2：多账号与代理

- 多账号任务管理器。
- 每账号代理配置。
- 代理连通性测试。
- 独立启停。
- 账号状态隔离。
- 失败重连。

### 阶段 3：后台与通知

- 账号列表。
- 代理管理页面。
- 会话列表。
- 消息历史。
- 手动发送文本。
- Bark 通知配置。

### 阶段 4：自动回复

- 默认回复。
- 关键词回复。
- 账号级开关。
- 防重复回复。

### 阶段 5：自动发货

- 发货规则。
- 卡密/文本/图片发货内容。
- WebSocket 发货内容发送。
- MTOP 确认发货。
- 发货日志。
- 防重复锁。
- Bark 通知。

### 阶段 6：商品发布

- 素材库。
- 图片上传。
- 地址与类目。
- 发布流程。
- 发布日志。
- 风控处理。

## 当前阶段交付物

已创建：

- `third_party/XianYuApis`：上游协议目录。
- `third_party/README.md`：上游目录规则。
- `integrations/xianyu_core`：项目自有适配层骨架。

下一步应实现：

- `XianyuApis` 隔离导入。
- `XianyuCoreClient` 具体实现。
- 单账号 SOCKS5h WebSocket 收发消息验证。
