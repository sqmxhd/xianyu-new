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

在运行 Chatwoot Docker Compose 的主机上，将本目录复制过去后执行：

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

撤回按钮仅在本项目创建、并带有 `xianyu_account_id` 通道属性的 API
Inbox 中显示。按钮受闲鱼两分钟撤回时限约束；Chatwoot 先显示“撤回中”，
闲鱼平台确认后显示“已撤回”，失败时保留原内容并显示失败原因。删除消息
仍只执行 Chatwoot 删除，不会触发闲鱼撤回。

构建脚本固定使用 `v4.16.0`，避免 `latest` 升级后补丁静默失效。升级
Chatwoot 时，应先修改 `CHATWOOT_VERSION` 并验证补丁仍可应用，再构建新镜像。

附件限制会影响该部署中的其他 API Inbox；撤回按钮只影响闲鱼托管
Inbox。原生 WhatsApp、Telegram 等非 API Inbox 不受影响。
