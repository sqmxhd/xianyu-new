# GitLab 镜像发布与 Docker 部署

## 发布契约

流水线保持 `test -> docker` 两个阶段。Docker 阶段只构建闲鱼管理平台自身：

- `image-amd64` 推送 Registry 镜像；
- `archive-amd64` 导出同版本的 `linux/amd64` Docker 镜像压缩包。

`tg` 分支自动发布完整提交 SHA、`1.0.<pipeline-iid>` 和 `latest`。`main`、其他分支、
合并请求和 Git Tag 只执行测试，不创建 Docker 发布任务。

下载产物为：

```text
xianyu-admin-1.0.315-linux-amd64.docker.tar.gz
xianyu-admin-1.0.315-linux-amd64.docker.tar.gz.sha256
开始部署.sh
compose.all.yml
```

流水线不下载 Chatwoot 源码，也不构建或打包 Chatwoot、MySQL、Redis、PostgreSQL。

## 首次部署

目标主机需要 Linux amd64、Docker Engine、Docker Compose v2 和 OpenSSL。将本项目
镜像压缩包、校验文件、`开始部署.sh` 与 `compose.all.yml` 放在同一目录后执行：

```bash
chmod +x 开始部署.sh
./开始部署.sh
```

脚本会：

1. 验证并导入本项目镜像；
2. 选择在线拉取或本地导入官方依赖镜像；
3. 在同级创建 `XIANYU_DATA`；
4. 配置监听 IP、闲鱼 HTTPS 端口，以及启用 Chatwoot 时的 Chatwoot HTTPS 端口；
5. 自动生成应用、数据库和 Chatwoot 密钥；
6. 自动生成或手动导入证书；
7. 使用固定 `xianyu` 容器和网络名称启动服务并等待健康检查。

MySQL、本项目 Redis、Chatwoot PostgreSQL 和 Chatwoot Redis 均使用脚本生成的
独立密码；这些端口不发布到宿主机。

默认端口为闲鱼平台 `6161`、Chatwoot `6443`。默认端口被占用时脚本会推荐下一个
可用端口。Compose 只发布两个 HTTPS 网关；API、数据库、Redis、队列、VNC 和 CDP
都只在容器内部使用。

## 官方依赖镜像

兼容基线：

```text
chatwoot/chatwoot:v4.16.0
mysql:8.4
redis:7.4-alpine
pgvector/pgvector:pg16
```

在线模式使用 `docker pull`。本地模式从脚本同级目录选择通过 `docker save` 导出的
`.tar` 或 `.tar.gz` 文件并执行 `docker load`。两种模式最终都统一标记为：

```text
xianyu-local/chatwoot:4.16.0
xianyu-local/mysql:8.4
xianyu-local/redis:7.4-alpine
xianyu-local/pgvector:pg16
```

Compose 对全部镜像使用 `pull_policy: never`，正式启动阶段不会隐式联网。官方依赖
镜像通过“官方依赖镜像管理”单独更新，不随本项目版本升级。

## 本地化目录

所有持久化内容固定保存到部署文件同级目录：

```text
XIANYU_DATA/
├── config/                     # 端口、URL、镜像标签
├── state/                      # 当前项目版本
├── releases/                  # 已导入的项目版本记录
├── secrets/                   # 应用与 Chatwoot 密钥
├── certificates/              # CA、信任链和两个站点证书
├── mysql/
├── redis/
├── product-images/
├── contact-avatars/
├── notification-sounds/
├── browser-profiles/
├── fingerprint-chromium/
├── standard-chromium/
└── chatwoot/
    ├── postgres/
    ├── redis/
    └── storage/
```

重新创建容器或升级镜像不会删除这些目录。

## 证书管理

首次部署可以使用 OpenSSL 自动生成内部根 CA、中间 CA 和网站证书，也可以手动导入。
自动生成支持 IP、域名或混合 SAN。根证书有效期固定到 `9999-12-31 23:59:59 UTC`，
网站证书可选 1、3、5、10 年。根 CA 私钥只存放在 `XIANYU_DATA/certificates/ca/private`。

## 升级

本项目升级只导入新的 `xianyu-admin-*.docker.tar.gz`，更新当前项目镜像标签并重新协调
服务。它不会修改官方依赖镜像、端口、URL、证书、密钥或持久化数据。

Chatwoot、MySQL、Redis 和 pgvector 使用“官方依赖镜像管理”独立更新。停止服务只
停止当前 `xianyu` Compose 堆栈，不执行全局清理命令。

## Chatwoot 撤回边界

只运行官方 Chatwoot。网页端和手机端删除已映射的公开客服消息后，Chatwoot 发出
标准 `message_updated` Webhook；本项目调用闲鱼撤回，并通过官方消息 API 创建
私密原消息快照。不存在定制 Chatwoot 菜单、接口、补丁或镜像。

## Runner 约束

容器任务只需要带 `docker` 标签并支持 rootless BuildKit 的 Linux Runner，不再需要
Windows 或原生 Linux 二进制打包 Runner。CI 不安装或覆盖 Runner 的内部根证书。
