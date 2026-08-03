# Xianyu Auto Reply Admin

Ant Design + FastAPI 的多平台管理后台。

## 当前目标

- 多后台用户：用户名/密码登录、JWT 鉴权、用户管理页面。
- 多闲鱼账户：账户列表、新增/编辑/删除、启动/停止、会话和消息管理。
- 闲鱼扫码登录：服务端维护扫码会话并保存 Cookie，浏览器不接触登录凭据。
- IM 安全验证：单浏览器运行环境、账户级 Profile、绑定代理和内嵌 noVNC 人工处理；风险态不会自动重试。
- 平台账户浏览器：从平台账户列表按需启停后台 VNC 网页，复用账户 Cookie、代理和 Profile，并保留仅本机可访问的 CDP 调试端口；支持安全清理账户 Profile。
- S5 代理池：独立节点增删改查、出站测试、账号绑定；只支持 `socks5/socks5h`，失败不直连兜底。
- 自动回复：关键词规则、默认回复、OpenAI 兼容接口、上下文窗口和会话人工接管。
- 消息服务：平台级 Chatwoot 双向同步、账户独立 Inbox、移动端分组和账户状态提醒。
- 队列：Redis 传递 `task_id`，数据库保存任务 payload、状态和结果。
- 登录页：显示当前访问 IP，并解析 CDN/反代来源头。
- 权限：`admin` 全权限，`operator` 业务读写，`viewer` 只读；写操作进入审计日志。

## 实测启动

```bash
npm run dev
```

首次运行会从 `.env.example` 创建私有的 `.env.local` 并自动生成 JWT 密钥；
只需填写外部 PostgreSQL、Redis 两条连接地址。源码模式仍兼容已有 MySQL。随后
`npm run dev` 会执行完整实测链路：
建库检查、构建 Ant 后台、启动 FastAPI、启动 worker、启动 9001 端口后台预览。

需要热更新开发时使用：

```bash
npm run dev:hot
```

运行后端回归测试：

```bash
npm test
```

## 发布与容器

GitLab 测试、Docker 镜像发布和 Docker Compose 部署说明见
[`docs/packaging.md`](docs/packaging.md)。

本地开发继续使用源码启动，不经过 Docker：

```bash
npm run dev
```

正式 Docker 部署使用 `main` 流水线生成的本项目镜像包。把以下四个文件放在
同一目录后运行脚本：

```bash
chmod +x 开始部署.sh
./开始部署.sh
```

```text
开始部署.sh
compose.all.yml
xianyu-admin-<版本>-linux-amd64.docker.tar.gz
xianyu-admin-<版本>-linux-amd64.docker.tar.gz.sha256
```

同一个项目镜像包既用于首次部署，也用于后续升级。Chatwoot、Redis 和 pgvector
不进入本项目包；部署时可选择在线拉取官方镜像，或导入事先保存的官方
镜像归档。脚本会询问外部端口、URL 和证书方案，并把数据、密钥、证书及配置
固定保存在同级 `XIANYU_DATA`。升级不会覆盖这些内容。在线依赖镜像明确拉取
`linux/amd64`；部署中断后重新选择“开始/继续部署”即可复用已经完成的阶段。
可使用 `./开始部署.sh --doctor` 检查 Docker 平台、镜像和当前部署进度。

只启动一个项目容器并使用已有的外部 PostgreSQL、Redis：

```bash
cp .env.docker.example .env.docker
# 只填写 XIANYU_DATABASE_URL 和 XIANYU_REDIS_URL
docker login 192.168.2.5:5050
docker compose --env-file .env.docker pull
docker compose --env-file .env.docker up -d --wait --remove-orphans
```

一键部署默认建议闲鱼平台使用 `6161`、Chatwoot 使用 `6443`；最终端口和公开
HTTPS 地址均在部署过程中确认。完整部署固定运行 5 个常驻容器：一个闲鱼应用、
Chatwoot 官方 Rails/Sidekiq、共享 PostgreSQL 和共享 Redis。数据库、Redis、API
等内部服务不发布宿主机端口。

`main` 分支自动执行镜像发布及镜像包归档；其他分支和 Git Tag 只运行验证，
不显示发布任务。
Registry 中应用镜像同时发布 `latest`，镜像包和 SHA-256 校验文件保留 14 天。
本地镜像导入、证书和数据目录说明见
[`docs/packaging.md`](docs/packaging.md)。

## 配置文件

- `.env.example`：源码启动模板，只有外部 PostgreSQL、Redis 两项人工必填。
- `.env.docker.example`：Docker 外部 PostgreSQL、Redis 模板，同样只有两项必填。
- `.env.local`、`.env.docker`：实际私有配置，已加入 `.gitignore`，不要提交。
- `compose.yml`：仅项目容器、连接外部 PostgreSQL/Redis 的高级入口。
- `compose.all.yml`：官方依赖与本项目的一键部署定义，由 `开始部署.sh` 管理，不需要手工填写 ENV。

所有参数的中文分类、默认值和风险说明见
[`docs/configuration.md`](docs/configuration.md)。

## 上游约束

`third_party/XianYuApis` 作为独立上游目录保留，不直接修改。项目自有适配层放在 `integrations/xianyu_core`。

## 尚未完成

- 平台确认发货接口。
- 闲鱼商品自动发布执行器；未完成前产品发布入口不在导航中展示。
- 代理节点批量导入和批量分配。
