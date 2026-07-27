# Chatwoot 接入

系统设置中的“消息服务”维护一份平台级 Chatwoot 配置。每个账户是否参与同步由
平台账户页的 `Chat` 开关控制；客户、会话和消息 ID 按“平台 + 平台账户”独立
映射，不会跨平台或跨账户复用。

未配置专用服务账号令牌时，既有 API Inbox 作为兼容入口继续使用。配置管理员服务
账号令牌后，系统会为每个开启 `Chat` 的平台账户创建独立的 API Inbox（例如
`🟢 [闲鱼] 账号名称`），并附加稳定的账号标签和自定义属性。Chatwoot 联系人标题
使用 `平台｜真实完整账号名称`，买家入站消息使用 `买家名称：原始消息`；因此官方
手机端的标题、消息预览和推送通知可以同时辨识平台账号与客户。

## 配置项

- Chatwoot 地址：Chatwoot 实例根地址，例如 `http://chatwoot.example:3000`
- 收件箱标识符：API Inbox 的 identifier
- Webhook 地址：Chatwoot 回调本系统时使用的完整地址，可按反向代理入口修改
- Webhook 秘密：API Inbox 生成的签名密钥
- 客户端身份 HMAC Token：可选，仅在 API Inbox 开启身份验证时填写
- Chatwoot 平台账户 ID：账号分组、标签和状态回写必填；收到通过验证的 Webhook
  后可自动识别
- 专用服务账号令牌：账号分组、标签、自定义属性和状态回写必填，需使用具备
  Chatwoot 管理员权限的专用服务账号令牌

项目向 Chatwoot 账户级 API 发送兼容 Nginx 默认配置的
`api-access-token` 请求头。Rack/Chatwoot 会将其识别为官方文档中的
`api_access_token`；这样无需在反向代理额外开启 `underscores_in_headers`。

保存后复制页面中的 Webhook 地址，填入 Chatwoot API Inbox 的 Webhook URL。
该地址可直接编辑并持久化，但必须指向本项目的回调端点，不能填写 Chatwoot 自己的
根地址。

内网 HTTPS 部署应配置 `XIANYU_PUBLIC_BASE_URL`，使管理 API 返回稳定的完整
Webhook 地址，不依赖管理员当前浏览器访问的端口。若 Chatwoot 和本项目使用内部
CA，还应通过 `XIANYU_CHATWOOT_CA_BUNDLE` 指定用于校验 Chatwoot HTTPS 证书的
根证书文件。

`XIANYU_CHATWOOT_READ_SYNC_INTERVAL_SECONDS` 控制 Chatwoot 坐席已查看状态的
兜底同步周期，默认 20 秒、最小 10 秒。系统只查询本地仍有用户级未查看的已映射
会话，不会轮询全部历史会话。

Chatwoot 默认拒绝向私网 IP 发起 Webhook。仅将地址从 HTTP 改为 HTTPS 不会放开
该限制；内网部署还需在 Chatwoot Web 与 Sidekiq 运行环境安装对应根证书，并设置
`SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true`。本部署使用的回调地址为：

```text
https://192.168.2.3:6161/api/integrations/chatwoot/webhook
```

关闭某个账户的 `Chat` 开关会立即停止该账户的新消息、客服回复和状态同步，但不会
删除既有映射；历史客户仍保留账号名称后缀，重新开启后可继续沿用。平台级“启用
同步”是总开关。

Webhook 使用 Chatwoot 的 `X-Chatwoot-Timestamp`、`X-Chatwoot-Signature` 和
`X-Chatwoot-Delivery` 请求头。系统会校验 HMAC-SHA256、拒绝超过五分钟的请求，
并按 delivery ID 去重。

## 同步范围

- 闲鱼入站文本、图片和语音同步为 Chatwoot incoming 消息；发送给 Chatwoot 的
  展示副本使用 `买家名称：原始消息`，本地原始消息内容保持不变
- Chatwoot 客服公开文本和图片通过后台任务发送到闲鱼
- Chatwoot 客服发送语音时不会转发到闲鱼；系统会追加一条仅客服可见的
  “闲鱼通道暂不支持从 Chatwoot 发送语音，本条未发送”提示
- 在闲鱼托管会话中，删除已映射的公开客服消息会调用闲鱼撤回；买家消息、
  私密备注、系统消息和无映射消息仍只执行 Chatwoot 本地删除
- 官方 Chatwoot 的按钮名称仍为“删除”，且删除后不会保留原消息；系统会追加一条
  仅客服可见的私密备注，明确提示闲鱼撤回成功或失败
- 使用支持 `xianyu_recall` 的定制 Chatwoot 时，明确的“撤回”操作仍会保留原消息，
  并在原消息上回写撤回状态
- Chatwoot 客服回复后，会话进入永久人工接管；Chatwoot resolved 后释放接管
- Chatwoot 坐席在电脑端或手机端查看会话后，本项目清除所有启用用户在该会话上的
  个人未查看标记，但保留闲鱼平台返回的原始未读基线，也不会清除“待回复”状态
- 闲鱼账号名称和 ID 写入客户、会话自定义属性，账号在线状态写入已映射会话
- 配置服务账号令牌后，系统自动维护每账号独立 Inbox、账号标签、自定义属性，
  并将本系统发出的消息、撤回和账户状态完整回写 Chatwoot

账号标签只追加系统管理的标签，不会覆盖客服手工添加的标签。账号重命名时，联系人
标题、独立 Inbox 名称和账号标签会由后台任务幂等更新。买家真实名称同时保存在
联系人自定义属性中，不参与联系人标题截断。开启账号专属 Inbox 后，
旧共享 Inbox 中已有本地映射的会话会在专属 Inbox 中幂等重建映射，旧会话标记为
resolved 并保留历史记录；后续新消息只进入专属 Inbox，不再回退到旧共享 Inbox。

系统启动时及每 15 分钟执行一次对账，修复遗漏的账号 Inbox、客户身份、会话映射和
在线状态。新会话创建时会立即写入平台、平台账号、客户、原始会话和账号当前在线
状态。账号状态变化时，系统同步会话属性，并更新 Inbox 名称前的状态标识：`🟢`
在线、`🟡` 连接中、`🔴` 离线或异常。

Chatwoot 不会为坐席打开会话稳定发送独立的已读 Webhook，因此系统会先利用已有
Webhook 载荷中的 `unread_count` 和 `agent_last_seen_at` 快速判断，再以默认
20 秒的轻量轮询兜底。只有 Chatwoot 未读为零且最后查看时间覆盖本地最新买家消息
时才会清除本项目个人未查看；旧事件不会误清之后收到的新消息。

创建独立 Inbox 后，系统会确保用于集成的 Chatwoot 管理员账号已加入该 Inbox，
并将新会话明确分配给该账号，保证其可在官方手机端默认的“我的会话”中看到。如果
Chatwoot 标签接口异常，系统会将配置标记为降级，但不会回滚或阻断 Inbox 分组、
消息和自定义属性链路。

图片下载限制为 10 MB。系统使用 `XIANYU_CHATWOOT_CA_BUNDLE` 校验所配置
Chatwoot 主机的 HTTPS 证书，并为 ActiveStorage 手动处理最多三次重定向。每一跳
都会重新校验协议、目标主机和私网地址；禁止 HTTPS 降级到 HTTP，也不会放行其他
未授权私网目标。最终响应必须是 `image/*`。

闲鱼语音以 AMR 格式到达。系统只允许从受信任的 `aliyuncs.com` 媒体域名下载，
自动将已知的 HTTP 媒体地址升级为 HTTPS，限制原始语音不超过 20 MB，并校验
AMR 文件头。Worker 将原始 `.amr` 文件直接上传 Chatwoot，不做服务端转码；
Chatwoot 是否原生播放取决于其版本和访问浏览器。本项目管理网页通过按需加载的
浏览器端 AMR 解码器播放语音，并通过鉴权接口读取原始文件，不向浏览器暴露闲鱼
媒体地址。

出站语音拦截提示和撤回提示都依赖 Chatwoot 平台账户 ID 与专用服务账号令牌；
缺少这两项时系统仍会阻止不受支持的语音发送，但无法在 Chatwoot 会话中追加私密
提示。

## 凭据边界

Webhook 秘密、客户端 HMAC Token 和服务账号令牌均使用服务端密钥派生密钥加密
存储。平台管理员配置页面会通过受保护的管理 API 明文回填这些凭据，便于直接检查和
修改。生产使用前应轮换曾经出现在聊天记录、日志或截图中的密钥，并为完整回写创建
权限最小化的专用服务账号，不要复用日常个人账号令牌。
