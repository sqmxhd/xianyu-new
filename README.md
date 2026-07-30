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
- 队列：Redis 传递 `task_id`，MySQL 保存任务 payload、状态和结果。
- 登录页：显示当前访问 IP，并解析 CDN/反代来源头。
- 权限：`admin` 全权限，`operator` 业务读写，`viewer` 只读；写操作进入审计日志。

## 实测启动

```bash
npm run dev
```

`npm run dev` 会执行完整实测链路：建库检查、构建 Ant 后台、启动 FastAPI、启动 worker、启动 9000 端口后台预览。

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

Docker HTTPS 部署从 GitLab Registry 拉取 `tg` 分支发布的 `latest`：

```bash
cp .env.docker.example .env.docker
docker login 192.168.2.5:5050
docker compose --env-file .env.docker --profile bundled pull
docker compose --env-file .env.docker --profile bundled up -d --wait --remove-orphans
```

使用已有的外部 MySQL 和 Redis：

```bash
cp .env.docker.external.example .env.docker
docker login 192.168.2.5:5050
docker compose --env-file .env.docker pull
docker compose --env-file .env.docker up -d --wait --remove-orphans
```

Docker 网关默认监听宿主机 `0.0.0.0:6161`，公开地址、跨域来源和端口均通过
`.env.docker` 配置，不绑定固定业务网址。生产 Compose 不包含源码构建步骤；
需要切换到固定版本时，把 `XIANYU_IMAGE` 改为版本标签或完整提交 SHA。

## 配置文件

- `.env.example`：提交到 git 的模板。
- `.env.docker.example`：自带独立 MySQL、Redis 容器的完整部署模板。
- `.env.docker.external.example`：接入外部 MySQL、Redis 的部署模板。
- `.env.local`：本机实际配置，已加入 `.gitignore`，不要提交。

## 上游约束

`third_party/XianYuApis` 作为独立上游目录保留，不直接修改。项目自有适配层放在 `integrations/xianyu_core`。

## 尚未完成

- 平台确认发货接口。
- 闲鱼商品自动发布执行器；未完成前产品发布入口不在导航中展示。
- 代理节点批量导入和批量分配。
