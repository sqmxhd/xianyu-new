# 阶段 1：单账号 WebSocket 收发消息探针

本阶段交付一个最小可运行探针，用于验证：

- Cookie 账号能否连接闲鱼 WebSocket。
- SOCKS5h 代理能否用于 WebSocket。
- Token 获取请求是否使用同一个 SOCKS5h 代理。
- 能否收到并解析文本消息。
- 能否向指定会话发送一条文本消息。

不包含：

- 数据库。
- 后台管理页面。
- 多账号任务调度。
- 自动回复。
- 自动发货。

## 文件

```text
integrations/xianyu_core/client.py
integrations/xianyu_core/upstream.py
integrations/xianyu_core/requirements.txt
tools/xianyu_core_probe.py
```

## 安装依赖

建议使用 Python 3.11+ 虚拟环境。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r integrations/xianyu_core/requirements.txt
```

还需要 Node.js 18+，因为 XianYuApis 的签名 JS 通过 PyExecJS 调用。

## 监听账号消息

建议通过环境变量传 Cookie，避免进入 shell 历史：

```bash
export XIANYU_COOKIE='unb=...; _m_h5_tk=...'
python tools/xianyu_core_probe.py listen \
  --account-id test-account \
  --cookie-env XIANYU_COOKIE \
  --proxy-url socks5h://127.0.0.1:1080
```

不走代理时省略 `--proxy-url`。生产设计不建议已配置代理的账号直连；当前探针允许直连只是为了本地排查。

## 发送文本消息

需要先知道会话 ID 和接收方用户 ID：

```bash
python tools/xianyu_core_probe.py send-text \
  --account-id test-account \
  --cookie-env XIANYU_COOKIE \
  --proxy-url socks5h://127.0.0.1:1080 \
  --conversation-id 123456789 \
  --receiver-id 987654321 \
  --text '你好'
```

输出包括：

- `state`：账号连接状态。
- `message`：收到的标准化消息事件。
- `send_result`：发送结果。

## 代理行为

阶段 1 使用 `websockets>=16` 的显式 `proxy=` 参数。官方文档说明，`connect()` 支持显式 `proxy` 参数，SOCKS 代理需要 `python-socks[asyncio]`。

同时，适配器会把同一个 SOCKS5h URL 注入到上游 `requests.Session.proxies`：

```text
http  -> socks5h://...
https -> socks5h://...
```

这样 Token 获取/刷新等 MTOP 请求与 WebSocket 使用同一个出口。

## 当前限制

- 只标准化基础文本消息。
- 图片、卡片、订单消息只是保留在 `raw_payload` 中，后续单独解析。
- `send-text` 需要手动提供会话 ID 和接收方用户 ID。
- 未实现重连策略；当前连接异常后结束探针。
- 未落库，所有输出打印到 stdout。

## 后续进入阶段 2 前的验收

- 无代理直连能上线并收到消息。
- 使用 SOCKS5h 能上线并收到消息。
- 断开 SOCKS5h 后账号不应静默直连。
- 能发送一条文本消息到指定会话。
- Token 获取失败时能看到明确错误。
