# Chatwoot 接入

系统设置中的“消息服务”维护一份平台级 Chatwoot 配置。每个账户是否参与同步由
平台账户页的 `Chat` 开关控制；客户、会话和消息 ID 按“平台 + 平台账户”独立
映射，不会跨平台或跨账户复用。

系统只支持管理员服务账号托管模式。保存 Chatwoot 地址和管理员服务账号令牌后，
系统会自动识别 Chatwoot 账户 ID，并为每个开启 `Chat` 的平台账户创建独立的
API Inbox（例如
`🟢 [闲鱼] 账号名称`），并附加稳定的账号标签和自定义属性。Chatwoot 联系人标题
使用 `平台｜真实完整账号名称`，买家入站消息使用 `买家名称：原始消息`；因此官方
手机端的标题、消息预览和推送通知可以同时辨识平台账号与客户。

## 配置项

- Chatwoot 地址：Chatwoot 实例根地址，例如 `http://chatwoot.example:3000`
- Chatwoot 管理员 Access Token：从 Chatwoot 个人资料页复制；账号必须具有
  `administrator` 权限。令牌在数据库中加密保存，并按管理要求在仅管理员可访问
  的连接参数页面明文回显；配置查询响应禁止缓存
- Chatwoot 平台账户 ID：保存时通过 `/api/v1/profile` 自动识别，只读展示
- Webhook 地址：由 `XIANYU_PUBLIC_BASE_URL` 和固定回调路径自动生成，只读展示
- Inbox identifier 和 Webhook 签名秘密：创建/读取每个账户的官方 API Inbox 时
  自动获取并按账户加密保存，不在平台配置页手工填写
- 账户状态提醒：平台级总开关；Cookie 确认失效立即发送，IM 普通掉线按配置的
  延迟时间再次确认后发送

项目向 Chatwoot 账户级 API 发送兼容 Nginx 默认配置的
`api-access-token` 请求头。Rack/Chatwoot 会将其识别为官方文档中的
`api_access_token`；这样无需在反向代理额外开启 `underscores_in_headers`。

系统会把生成的 Webhook 地址自动写入每个托管 API Inbox，并固定关闭客户端身份
HMAC 校验（`hmac_mandatory=false`）。平台不接收手工 Webhook Secret、客户端
HMAC Token、Inbox identifier、回调地址或 Chatwoot 账户 ID。

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
- 手机端和电脑端原生删除后，Webhook 使用本地消息记录恢复一条仅客服可见的
  私密快照：正文包含原发送时间、原文字和原图片，底部显示“闲鱼消息已撤回”
  或具体失败原因。Chatwoot 原生的“此消息已被删除”占位仍会保留
- 快照通过 Chatwoot 消息 ID 幂等关联；图片或快照写入失败时后台重试快照，
  已确认的闲鱼撤回不会重复执行。该链路不依赖 Chatwoot Nginx 反向代理
- 本项目只支持官方 Chatwoot：网页端和手机端均通过原生“删除”触发闲鱼撤回，
  不依赖定制菜单、定制接口或定制镜像
- Chatwoot 客服回复后，会话进入永久人工接管；Chatwoot resolved 后释放接管
- Chatwoot 坐席在电脑端或手机端查看会话后，本项目清除所有启用用户在该会话上的
  个人未查看标记，但保留闲鱼平台返回的原始未读基线，也不会清除“待回复”状态
- 闲鱼账号名称和 ID 写入客户、会话自定义属性，账号在线状态写入已映射会话
- 配置服务账号令牌后，系统自动维护每账号独立 Inbox、账号标签、自定义属性，
  并将本系统发出的消息、撤回和账户状态完整回写 Chatwoot
- 每个账号 Inbox 内维护一条独立的“账户状态”系统会话；异常以 incoming 事件消息
  发送，从而使用 Chatwoot 官方手机端通知。重复异常会去重，已发送异常恢复后才
  补发在线恢复消息；该系统会话不映射闲鱼客户，客服回复不会发送到闲鱼

账号标签只追加系统管理的标签，不会覆盖客服手工添加的标签。账号重命名时，联系人
标题、独立 Inbox 名称和账号标签会由后台任务幂等更新。买家真实名称同时保存在
联系人自定义属性中，不参与联系人标题截断。开启账号专属 Inbox 后，
本地已有映射若指向其他 Inbox，会在当前账户的托管 Inbox 中幂等重建；后续新消息
只进入托管 Inbox，不存在全局共享 Inbox 回退路径。

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
消息和自定义属性链路。管理页分别记录管理员凭据、消息推送、Webhook、Inbox 和
标签健康状态，并以黄色“部分功能异常”显示仅标签失败的降级；某个子链路成功不会
覆盖其他子链路仍存在的错误。页面提供“重新同步账户结构”操作，用于重试 Inbox、
标签和自定义属性对账。

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

出站语音拦截提示和撤回提示依赖自动识别的 Chatwoot 账户 ID 与管理员服务账号
令牌；配置保存前会验证这两项，不再提供缺少凭据的兼容运行模式。

## 凭据边界

每个托管 Inbox 的 Webhook 签名秘密和服务账号令牌均使用服务端密钥派生密钥加密
存储。管理 API 只返回“服务账号令牌已配置”状态，不明文回填令牌或 Inbox 秘密。
生产使用前应轮换曾经出现在聊天记录、日志或截图中的密钥，并使用独立管理员服务
账号，不要复用日常个人账号令牌。
