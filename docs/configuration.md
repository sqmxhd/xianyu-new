# 配置参数说明

本项目把配置分为主配置、系统生成、次配置和高级配置。首次部署只处理主配置；
没有明确容量测试或故障依据时，不要修改高级配置。

## 配置文件职责

| 文件 | 用途 | 人工必填 |
| --- | --- | --- |
| `.env.local` | 源码启动的私有配置 | 外部 PostgreSQL、Redis 地址 |
| `.env.docker` | Docker 项目容器模式的私有配置 | 外部 PostgreSQL、Redis 地址 |
| `XIANYU_DATA/config/deployment.env` | Docker ALL 部署参数 | 由 `开始部署.sh` 生成 |

`.env.local` 和 `.env.docker` 都不能提交到 Git。不要另外创建含义不明确的
`.env`。`third_party/XianYuApis/.env.dev` 属于上游代码，不是项目部署配置。

## 主配置与自动配置

| 参数 | 分类 | 适用模式 | 说明 |
| --- | --- | --- | --- |
| `XIANYU_DATABASE_URL` | 主配置 | 源码、Docker 外部依赖 | 外部 PostgreSQL 完整连接地址；源码兼容 MySQL |
| `XIANYU_REDIS_URL` | 主配置 | 源码、Docker 外部依赖 | 外部 Redis 完整连接地址 |
| `XIANYU_JWT_SECRET` | 系统生成 | 全部 | 首次生成并持久化，不能在运行后随意更换 |
| `POSTGRES_ROOT_PASSWORD` | 系统生成 | Docker ALL | 共享 PostgreSQL 管理密码 |
| `POSTGRES_PASSWORD` | 系统生成 | Docker ALL | 闲鱼应用数据库用户密码 |
| `REDIS_PASSWORD` | 系统生成 | Docker ALL | Redis 认证密码 |
| `XIANYU_PUBLIC_BASE_URL` | 条件主配置 | 全部 | 外部回调需要固定绝对地址时设置；优先在管理后台配置具体集成 |
| `XIANYU_CHATWOOT_CA_BUNDLE` | 条件主配置 | 源码 | Chatwoot 使用私有 CA 时填写；Docker 自动探测固定 CA 文件 |

ALL 模式不再要求复制 ENV 模板。`开始部署.sh` 询问监听 IP、两个 HTTPS 端口和
两个公开 URL，并把结果写入宿主机部署目录；共享 PostgreSQL、Redis 和应用密钥
都在首次部署时生成。脚本发现已有 PostgreSQL/Redis 数据而原密钥缺失时会拒绝
启动，避免生成新密码破坏旧数据连接。

## 系统内部配置

下列参数由启动方式或容器网络固定，已经从用户模板移除：

| 参数 | 系统处理方式 |
| --- | --- |
| `XIANYU_API_HEALTH_URL` | 源码和单容器 Docker 均使用本机 API |
| `XIANYU_INTERNAL_API_URL` | 源码和单容器 Docker 均使用本机 API |
| `XIANYU_TLS_DIR` | Docker 固定绑定部署目录的 `certificates/xianyu` |
| `XIANYU_INTERNAL_CA_FILE` | Docker 固定绑定部署目录的 `certificates/trust` |
| `XIANYU_DATABASE_HOST/USER/NAME` | ALL 模式固定使用共享 PostgreSQL 和独立账号 |
| `XIANYU_REDIS_HOST` | ALL 模式固定使用 `redis` 服务名 |

Docker 项目模式和 ALL 模式使用相同 Compose 项目名，因此不能在同一主机上把它们
作为两套同名实例同时运行。ALL 模式使用宿主机 `XIANYU_DATA` bind mount，不依赖匿名或命名
卷。

## 次配置

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `XIANYU_IMAGE` | 当前项目版本 | 由本项目镜像包导入后写入，不允许人工改为远程 `latest` |
| `XIANYU_BIND_IP` | `0.0.0.0` | HTTPS 网关宿主机监听地址 |
| `XIANYU_HTTPS_PORT` | `6161` | HTTPS 网关宿主机端口 |
| `XIANYU_CORS_ORIGINS` | 同源 | 独立前端跨域访问时设置 |
| `VITE_API_BASE_URL` | 空 | 源码前端直接访问独立 API 时设置 |
| `XIANYU_ACCESS_TOKEN_EXPIRES_MINUTES` | `1440` | 管理员访问令牌有效期；前端会在到期前自动刷新 |
| `XIANYU_ADMIN_SESSION_EXPIRES_DAYS` | `365` | 管理员滑动登录会话有效期；正常使用会自动顺延 |
| `XIANYU_TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | 可信直接反向代理列表 |
| `XIANYU_IM_VERIFICATION_ALLOW_NO_SANDBOX` | `false` | 隔离的 Root 开发环境运行 Chromium 时使用 |

## Cookie 与同步高级配置

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `XIANYU_COOKIE_RENEWAL_ENABLED` | `true` | 启用 Cookie 定期维护 |
| `XIANYU_COOKIE_RENEWAL_INTERVAL_HOURS` | `1` | 常规续期周期，小时 |
| `XIANYU_COOKIE_KEEPALIVE_INTERVAL_SECONDS` | `600` | Cookie 轻量检查周期 |
| `XIANYU_COOKIE_KEEPALIVE_RECHECK_MIN_SECONDS` | `15` | 失败确认最短等待时间 |
| `XIANYU_COOKIE_KEEPALIVE_RECHECK_MAX_SECONDS` | `30` | 失败确认最长等待时间 |
| `XIANYU_COOKIE_RENEWAL_SCAN_SECONDS` | `60` | 续期调度扫描周期 |
| `XIANYU_COOKIE_RENEWAL_MANUAL_COOLDOWN_SECONDS` | `3600` | 手动续期成功后的冷却时间 |
| `XIANYU_CONVERSATION_SYNC_INTERVAL_SECONDS` | `180` | 会话增量同步周期 |
| `XIANYU_CHATWOOT_RECONCILE_INTERVAL_SECONDS` | `900` | Chatwoot 对账周期，最低 300 秒 |
| `XIANYU_CHATWOOT_READ_SYNC_INTERVAL_SECONDS` | `20` | Chatwoot 已读同步周期 |
| `XIANYU_CONVERSATION_FULL_SYNC_MAX_PAGES` | `50` | 首次会话全量同步最大页数 |

## 并发与队列高级配置

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `XIANYU_QR_LOGIN_WORKERS` | `2` | QR 登录阻塞工作线程数 |
| `XIANYU_QR_LOGIN_MAX_ACTIVE_SESSIONS` | `4` | 最大并行 QR 会话数 |
| `XIANYU_DB_BLOCKING_WORKERS` / `XIANYU_DB_BLOCKING_QUEUE` | `6` / `64` | 数据库阻塞任务池和队列 |
| `XIANYU_PLATFORM_BLOCKING_WORKERS` / `XIANYU_PLATFORM_BLOCKING_QUEUE` | `8` / `40` | 平台请求任务池和队列 |
| `XIANYU_MEDIA_BLOCKING_WORKERS` / `XIANYU_MEDIA_BLOCKING_QUEUE` | `3` / `12` | 媒体处理任务池和队列 |
| `XIANYU_EXTERNAL_BLOCKING_WORKERS` / `XIANYU_EXTERNAL_BLOCKING_QUEUE` | `4` / `20` | 外部集成任务池和队列 |
| `XIANYU_BROWSER_BLOCKING_WORKERS` / `XIANYU_BROWSER_BLOCKING_QUEUE` | `2` / `8` | 浏览器阻塞任务池和队列 |
| `XIANYU_RUNTIME_START_CONCURRENCY` | `3` | 账户运行时启动并发 |
| `XIANYU_RUNTIME_START_JITTER_SECONDS` | `3` | 账户启动随机错峰时间 |
| `XIANYU_CONVERSATION_SYNC_CONCURRENCY` | `3` | 会话同步账户并发 |
| `XIANYU_COOKIE_RENEWAL_CONCURRENCY` | `2` | Cookie 维护账户并发 |
| `XIANYU_WORKER_CONCURRENCY` | `4` | 后台任务并发数 |
| `XIANYU_WORKER_LEASE_SECONDS` | `120` | 后台任务租约时间 |
| `XIANYU_WORKER_LEASE_RENEW_SECONDS` | `30` | 后台任务续租周期 |
| `XIANYU_EVENT_LOOP_MONITOR_INTERVAL_SECONDS` | `1` | API 事件循环监控周期 |
| `XIANYU_EVENT_LOOP_LAG_WARNING_SECONDS` | `0.5` | 事件循环延迟告警阈值 |

## 浏览器高级配置

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `XIANYU_IM_VERIFICATION_BROWSER_ENABLED` | `true` | 启用可视化浏览器能力 |
| `XIANYU_IM_VERIFICATION_BROWSER_PATH` | 自动发现 | 系统 Chromium 路径 |
| `XIANYU_FINGERPRINT_BROWSER_ROOT` | 运行目录默认值 | 指纹浏览器版本目录 |
| `XIANYU_STANDARD_BROWSER_ROOT` | 运行目录默认值 | 标准浏览器版本目录 |
| `XIANYU_FINGERPRINT_BROWSER_DOWNLOAD_TIMEOUT_SECONDS` | `600` | 浏览器包下载超时 |
| `XIANYU_FINGERPRINT_BROWSER_MAX_ARCHIVE_BYTES` | `536870912` | 浏览器压缩包上限 512 MiB |
| `XIANYU_FINGERPRINT_BROWSER_MAX_EXTRACTED_BYTES` | `1073741824` | 解压后上限 1 GiB |
| `XIANYU_IM_VERIFICATION_PROFILE_DIR` | 运行目录默认值 | 账户浏览器 Profile 根目录 |
| `XIANYU_IM_VERIFICATION_DISPLAY` | `:99` | Xvfb 显示编号 |
| `XIANYU_IM_VERIFICATION_VNC_PORT` | `5901` | 内部 VNC 端口，不对公网发布 |
| `XIANYU_IM_VERIFICATION_SESSION_SECONDS` | `600` | 人工验证会话时长 |
| `XIANYU_ACCOUNT_BROWSER_IDLE_SECONDS` | `1800` | 账户浏览器空闲关闭时间 |
| `XIANYU_ACCOUNT_BROWSER_MAX_SESSION_SECONDS` | `28800` | 账户浏览器绝对最长时长 |
| `XIANYU_ACCOUNT_BROWSER_MAX_SESSIONS` | `3` | 最大可视化浏览器会话数 |
| `XIANYU_ACCOUNT_BROWSER_CDP_ENABLED` | `true` | 启用本机 CDP |
| `XIANYU_ACCOUNT_BROWSER_CDP_PORT` | `9222` | 本机 CDP 端口，禁止对公网发布 |
| `XIANYU_BROWSER_FINGERPRINT_PROBE_STUN_URL` | 空 | 可选自托管 STUN 探测地址 |
| `XIANYU_BROWSER_FINGERPRINT_PROXY_EXIT_TTL_SECONDS` | `600` | 代理出口结果缓存时间 |

## 路径和资源高级配置

源码部署可以覆盖下列路径；Docker 镜像已经使用固定持久化目录，通常不应覆盖：

- `XIANYU_PRODUCT_IMAGE_DIR`
- `XIANYU_CONTACT_AVATAR_DIR`
- `XIANYU_WEB_NOTIFICATION_SOUND_DIR`
- `XIANYU_IP2REGION_DB_PATH`
- `XIANYU_GEOIP_DB_PATH`
- `XIANYU_PROXY_IP_CHECK_URLS`

修改 `XIANYU_JWT_SECRET` 会让现有登录令牌失效，并使使用旧密钥加密的敏感验证数据
无法解密。修改或删除 Docker 自动密钥前必须先完成明确的迁移，不能把删除密钥卷
当作普通重启操作。
