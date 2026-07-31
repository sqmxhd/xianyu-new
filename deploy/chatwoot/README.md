# Chatwoot 闲鱼通道定制

当前闲鱼桥接仅支持从 Chatwoot 发送文字和图片。这里的 Chatwoot 4.16
定制补丁提供：

- 隐藏语音录制按钮；
- 文件选择器只接受图片；
- 拦截粘贴、拖拽或绕过 `accept` 限制提交的非图片附件；
- 不影响私密备注附件；
- 不影响闲鱼入站语音的音频卡片和播放；
- 闲鱼托管收件箱的公开客服消息增加“撤回”操作；
- 撤回与 Chatwoot 原生“删除”保持独立；
- 原消息内容和附件保留，并在下方显示撤回状态。

官方 Chatwoot 手机端不会展示 Web 前端新增的“撤回”菜单，只会调用原生
DELETE 接口。闲鱼映射消息删除后，本项目通过 Webhook 调用闲鱼撤回，并使用
本地沉淀的文字、图片和原发送时间创建一条仅客服可见的“原消息”快照；快照
底部显示“闲鱼消息已撤回”或具体失败原因。该链路不需要修改 Chatwoot Nginx。
买家消息、私密备注、未映射消息仍保持 Chatwoot 原生删除行为。

正式离线部署已经把这个定制镜像纳入 `tg` 流水线和统一版本包。目标主机不再需要
单独构建 Chatwoot，也不需要维护第二份 Compose；使用根目录 `开始部署.sh` 即可
同时启动 Chatwoot、Sidekiq、pgvector PostgreSQL、Redis 和 HTTPS 网关。

下面的手工构建方式只保留给补丁开发和本地验证：

```bash
chmod +x build-no-outbound-audio.sh
./build-no-outbound-audio.sh
docker compose -f docker-compose.yml -f compose.no-outbound-audio.yml up -d
```

正式镜像构建完成前，可以先对当前 Chatwoot 账户（ID `3`）关闭原生录音
功能，立即隐藏麦克风按钮：

```bash
docker compose exec -T rails bundle exec rails runner \
  "Account.find(3).disable_features!('voice_recorder')"
```

这个账户开关只隐藏录音按钮；选择、拖拽非图片附件的完整限制仍由上面的
定制镜像提供。

Web 端撤回按钮仅在本项目创建、并带有 `xianyu_account_id` 通道属性的 API
Inbox 中显示。按钮受闲鱼两分钟撤回时限约束；Chatwoot 先显示“撤回中”，
闲鱼平台确认后显示“已撤回”，失败时保留原内容并显示失败原因。删除消息
则先由 Chatwoot 显示原生删除占位，再由 Webhook 追加包含原文字、原图片和
撤回结果的私密快照。快照写入失败时会重试，但不会重复调用闲鱼撤回。

构建脚本固定使用 `v4.16.0`，避免 `latest` 升级后补丁静默失效。升级
Chatwoot 时，应先修改 `CHATWOOT_VERSION` 并验证补丁仍可应用，再构建新镜像。

附件限制会影响该部署中的其他 API Inbox；撤回按钮只影响闲鱼托管
Inbox。原生 WhatsApp、Telegram 等非 API Inbox 不受影响。
