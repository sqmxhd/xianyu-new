# GitLab 镜像发布与 Docker 部署

## 发布契约

流水线只有 `test -> docker` 两个阶段。`test` 阶段保留 `backend`、`frontend` 和
`portability` 三个并行验证作业；它们不是部署容器。Docker 阶段只处理同一个闲鱼
项目镜像：

- `image-amd64` 推送 Registry 镜像；
- `archive-amd64` 导出同版本的 `linux/amd64` Docker 镜像压缩包。

`main` 分支自动发布完整提交 SHA、`1.0.<pipeline-iid>` 和 `latest`。其他分支、
合并请求和 Git Tag 只执行验证，不显示发布作业。

下载产物为：

```text
xianyu-admin-1.0.315-linux-amd64.docker.tar.gz
xianyu-admin-1.0.315-linux-amd64.docker.tar.gz.sha256
开始部署.sh
compose.all.yml
```

流水线不下载 Chatwoot 源码，也不构建或打包 Chatwoot、PostgreSQL 或 Redis。

## 最终运行结构

完整部署固定为 5 个常驻容器：

```text
xianyu-app               # 前端、FastAPI、Worker、两个 HTTPS 入口
xianyu-database          # 共享 pgvector/PostgreSQL
xianyu-redis             # 共享 Redis
xianyu-chatwoot          # 官方 Chatwoot Rails
xianyu-chatwoot-worker   # 官方 Chatwoot Sidekiq
```

PostgreSQL 中使用 `xianyu_admin`、`chatwoot` 两个数据库和两个独立用户。Redis 的
闲鱼平台使用逻辑库 0，Chatwoot 使用逻辑库 1。数据库、Redis、Rails、API、VNC 和
CDP 都不发布宿主机端口。`xianyu-app` 只发布闲鱼平台和 Chatwoot 两个 HTTPS 端口。

Chatwoot 保持官方 Rails/Sidekiq 两容器结构，使用同一个官方镜像，不制作补丁镜像。
数据库初始化通过 `docker compose run --rm` 临时执行，不留下初始化容器。

## 首次部署

目标主机需要 Linux amd64、Docker Engine、Docker Compose v2 和 OpenSSL。将镜像
压缩包、校验文件、`开始部署.sh` 与 `compose.all.yml` 放在同一目录：

```bash
chmod +x 开始部署.sh
./开始部署.sh
```

脚本会验证并导入项目镜像，选择在线拉取或本地导入官方依赖镜像，创建同级
`XIANYU_DATA`，配置两个 HTTPS 端口和 URL，生成密钥，建立两个 PostgreSQL 数据库，
执行 Chatwoot 官方初始化，最后启动并检查 5 个常驻容器。

首次部署采用可恢复的分阶段流程。URL 输入、依赖镜像下载、证书生成或数据库初始化
中途失败时，再次选择“首次部署”会复用已经导入的版本及现有配置，从失败阶段继续，
不会覆盖证书、密钥或数据。在线依赖镜像拉取会自动重试 3 次。

共享 PostgreSQL 启动时预加载 `pg_stat_statements`。脚本以数据库超级用户在
`chatwoot` 库中预先创建 `pg_stat_statements`、`pg_trgm`、`pgcrypto` 和 `vector`，
再由普通 `chatwoot` 用户执行官方 `db:chatwoot_prepare`，不会授予应用超级用户权限。

默认端口为闲鱼平台 `6161`、Chatwoot `6443`。端口被占用时脚本推荐下一个可用
端口。正式 `docker compose up` 使用 `pull_policy: never`，不会隐式联网。

## 官方依赖镜像

兼容基线：

```text
chatwoot/chatwoot:v4.16.0
redis:7.4-alpine
pgvector/pgvector:pg16
```

在线模式执行 `docker pull`。本地模式选择通过 `docker save` 导出的 `.tar` 或
`.tar.gz` 并执行 `docker load`，然后统一标记为：

```text
xianyu-local/chatwoot:4.16.0
xianyu-local/redis:7.4-alpine
xianyu-local/pgvector:pg16
```

## 本地化目录

```text
XIANYU_DATA/
├── config/                     # 端口、URL、镜像标签
├── state/                      # 当前项目版本
├── releases/                   # 已导入的项目版本记录
├── secrets/                   # 应用、数据库与 Chatwoot 密钥
├── certificates/              # CA、信任链和两个站点证书
├── postgres/                   # 两套系统共用的 PostgreSQL
├── redis/                      # 两套系统共用的 Redis
├── product-images/
├── contact-avatars/
├── notification-sounds/
├── browser-profiles/
├── fingerprint-chromium/
├── standard-chromium/
└── chatwoot/
    └── storage/
```

升级镜像不会覆盖这些目录。

## 版本升级

“安装/升级版本包”按版本号倒序列出脚本同级的镜像包，默认选中最新版本。
脚本会同时校验文件名版本、OCI 镜像版本标签、`linux/amd64` 架构和
镜像 ID。选择当前版本时需要额外确认，用于强制重装同版本镜像。

升级只会强制重建 `xianyu-app`，不重建 PostgreSQL、Redis 和 Chatwoot。
容器通过健康检查后，脚本还会比对运行容器镜像 ID 与目标镜像 ID。
若启动或核验失败，脚本会恢复升级前的版本记录和应用镜像；数据、
配置、证书和密钥始终保留。

## 证书管理

首次部署可以使用 OpenSSL 自动生成内部根 CA、中间 CA 和网站证书，也可以手动导入。
自动生成支持 IP、域名或混合 SAN。根证书有效期固定到 `9999-12-31 23:59:59 UTC`，
网站证书可选 1、3、5、10 年。两套网站证书都由 `xianyu-app` 的 Nginx 使用；根 CA
信任链同时挂载到项目和两个官方 Chatwoot 容器。每次启动前，部署脚本都会重新生成
组合信任链，并校验两套网站证书可读取、私钥匹配、24 小时内不过期、证书链可信，
且 SAN 包含部署配置中的平台/Chatwoot 访问 IP 或域名；任一项不满足都会阻止启动。
内部根证书仍需由管理员安装到访问平台的手机和电脑信任库，容器挂载不会改变客户端
设备的系统信任库。

## 升级和旧 MySQL 数据

项目升级只导入新的 `xianyu-admin-*.docker.tar.gz` 并协调当前堆栈，不修改端口、
URL、证书、密钥和持久化数据。官方依赖镜像通过脚本单独更新。

新 ALL 部署统一使用 PostgreSQL。旧版 MySQL 数据不能通过替换 Compose 文件直接
切换；必须先执行一次性数据迁移并核对记录，再停用旧 MySQL。部署脚本不会自动删除
旧 `mysql/` 目录；检测到旧 MySQL 数据而新 PostgreSQL 仍为空时还会拒绝启动，避免
把空数据库误认为升级后的数据。

## Chatwoot 撤回边界

只运行官方 Chatwoot。网页端和手机端删除已映射的公开客服消息后，Chatwoot 发出
标准 Webhook；本项目调用闲鱼撤回并创建私密原消息快照。不存在定制 Chatwoot
菜单、接口、补丁或镜像。

## Runner 约束

容器任务只需要带 `docker` 标签并支持 rootless BuildKit 的 Linux Runner，不需要
Windows 或原生 Linux 二进制打包 Runner。CI 不安装或覆盖 Runner 的内部根证书。
