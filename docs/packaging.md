# GitLab 镜像发布与离线部署包

## 发布契约

流水线保持两个阶段：

```text
test -> docker
```

所有分支和合并请求运行测试；只有小写 `tg` 分支运行容器发布任务。`main`、功能
分支和 Git Tag 均不发布镜像或版本包。

`tg` 发布内容：

- 应用镜像：完整提交 SHA、`1.0.<pipeline-iid>` 和 `latest`；
- 固定 Chatwoot `v4.16.0` 源码应用本仓库补丁后构建的定制镜像；
- 一个完整 `linux-amd64` 版本包和外部 SHA-256 文件。

版本系列由 `.gitlab-ci.yml` 的 `RELEASE_SERIES` 统一维护，默认 `1.0`；TG 构建把
Pipeline IID 作为修订号，例如：

```text
xianyu-1.0.315-linux-amd64.tar.gz
xianyu-1.0.315-linux-amd64.tar.gz.sha256
开始部署.sh
```

不存在“全量包”和“升级包”两种制品。同一个版本包可以完成首次部署，也可以在
已有部署上升级。

## 完整版本包内容

版本包包含：

- 闲鱼管理平台镜像（API、Worker、前端和两个 HTTPS 网关共用）；
- 定制 Chatwoot Rails/Sidekiq 镜像；
- MySQL 8.4；
- Redis 7.4（闲鱼与 Chatwoot 使用隔离的数据目录和进程）；
- pgvector PostgreSQL 16；
- `compose.all.yml`、`release.env`、`manifest.json` 和内部 `SHA256SUMS`。

压缩包中的镜像统一重标记为离线本地名称，部署机器不需要访问 GitLab Registry、
Docker Hub 或其他镜像仓库。外层 `.sha256` 验证下载文件，内层 `SHA256SUMS`
验证 Compose、清单和每个镜像归档。

GitLab Artifact 保留 14 天。包体包含多个基础服务镜像，项目的 Artifact 大小限制
必须覆盖最终压缩包。

## 首次部署

目标主机仅需要 Linux amd64、Docker Engine、Docker Compose v2 和 OpenSSL。
将三个制品放到同一目录：

```text
开始部署.sh
xianyu-<版本>-linux-amd64.tar.gz
xianyu-<版本>-linux-amd64.tar.gz.sha256
```

执行：

```bash
chmod +x 开始部署.sh
./开始部署.sh
```

选择“首次部署”。脚本会在任何写入前再次确认，并依次完成：

1. 选择同级版本包并验证内外两层 SHA-256；
2. 通过 `docker load` 导入全部镜像，绝不执行 `docker pull`；
3. 设置部署数据根目录；
4. 设置监听 IP、闲鱼平台端口、Chatwoot 端口和两个完整 HTTPS URL；
5. 自动生成应用、MySQL、Redis、PostgreSQL 和 Chatwoot 密钥；
6. 自动生成证书或手动导入证书；
7. 启动并等待完整堆栈健康。

默认建议端口是闲鱼平台 `6161`、Chatwoot `6443`。脚本会检查端口范围、两个
端口冲突和当前监听占用，并在保存前明确列出即将对外开放的端口。Compose 只
发布两个 HTTPS 网关；数据库、缓存、API 和 Worker 不发布宿主机端口。

## 本地化目录

默认部署根目录为脚本同级的 `xianyu-deployment`，也可以在首次部署时改为绝对
路径。目录职责如下：

```text
xianyu-deployment/
├── config/                         # 端口、URL 和启用组件
├── state/                          # 当前版本指针
├── releases/<version>/             # 各版本 Compose 和公开清单
├── secrets/                        # 应用和 Chatwoot 私密密钥
├── certificates/
│   ├── ca/private/                 # 根/中间 CA 私钥，永不挂载到容器
│   ├── ca/certs/
│   ├── trust/                      # 容器信任链
│   ├── xianyu/                     # 平台 fullchain.pem/privkey.pem
│   └── chatwoot/                   # Chatwoot fullchain.pem/privkey.pem
└── data/
    ├── xianyu/
    │   ├── mysql/
    │   ├── redis/
    │   ├── product-images/
    │   ├── contact-avatars/
    │   ├── notification-sounds/
    │   ├── browser-profiles/
    │   ├── fingerprint-chromium/
    │   └── standard-chromium/
    └── chatwoot/
        ├── postgres/
        ├── redis/
        └── storage/
```

这些目录全部通过 Compose bind mount 关联。Docker 升级、镜像清理或重新创建
容器不会删除业务数据。

## 证书管理

首次部署可以选择：

- OpenSSL 自动生成内部根 CA、中间 CA 和网站证书；
- 手动导入根证书以及一套或两套网站证书。

自动生成支持 IP、域名或混合 SAN。根证书 `notAfter` 固定为
`9999-12-31 23:59:59 UTC`，中间证书默认 20 年，网站证书可选 1、3、5、10 年，
最长 10 年。根 CA 私钥仅存放在 `certificates/ca/private`，不会挂载到应用或
Chatwoot 容器。

“证书管理”子菜单支持单独导入根证书、单独更新平台网站证书、单独更新 Chatwoot
网站证书以及查看有效期和 SAN。网站证书必须提供 `fullchain.pem`（叶证书在前，
随后为中间证书）和匹配的 `privkey.pem`。脚本会验证格式、密钥匹配和到期时间。

内部根证书会合并到容器 CA Bundle，供本项目与 Chatwoot 的双向 HTTPS 调用使用；
网站证书目录直接绑定到各自 HTTPS 网关，更新后只需按脚本提示重启网关。

## 升级

把新的版本包和 `.sha256` 放到 `开始部署.sh` 同级目录，选择“安装/升级版本包”。
升级只会：

- 校验并导入新镜像；
- 新建 `releases/<version>`；
- 更新 `state/current-release.env`；
- 使用新版本 Compose 重新协调服务。

升级不会改写 `config`、`secrets`、`certificates` 或 `data`。基础服务镜像引用未
变化时，Compose 不会无意义重建对应容器。系统级业务配置继续由数据库和管理后台
维护。

“只导入版本包”用于预加载镜像，不切换当前版本，也不重启服务。

## 日常操作

唯一入口均为：

```bash
./开始部署.sh
```

菜单支持启动、停止、重启、状态、日志、版本安装/升级、只导入、端口和 URL 修改、
证书管理。停止服务只停止容器，不删除任何本地数据。

`npm run deploy:check` 或 `./开始部署.sh --check` 只检查脚本和同级版本包命名，
不会改动 Docker 或部署目录。

## Runner 约束

容器任务只需要带 `docker` 标签并允许 rootless BuildKit 的 Linux Runner，不再需要
Windows 或原生 Linux 二进制打包 Runner。CI 不安装或覆盖 Runner 的内部根证书；
Registry 和 dependency proxy 信任仍由 Runner/Docker executor 统一提供。

定制 Chatwoot 源码准备任务只安装 `git`，不会重新安装 `ca-certificates`。镜像构建
固定 `v4.16.0` 并在每次 TG 流水线重新应用补丁，补丁失配会立即让任务失败，避免
静默退回官方未定制镜像。

网关普通 API 上传限制为 64 MiB；两个浏览器压缩包端点为 520 MiB，应用层仍限制
压缩包最大 512 MiB，前后端限制保持一致。
