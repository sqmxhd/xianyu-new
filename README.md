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
- 通知：Bark 配置和账户级通知开关。
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

## 打包与容器

GitLab 三阶段流水线、Linux/Windows 二进制包和 Docker Compose 的说明见
[`docs/packaging.md`](docs/packaging.md)。

本地 Linux 打包：

```bash
bash tools/package/build_linux.sh
```

Docker HTTPS 部署：

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

## 配置文件

- `.env.example`：提交到 git 的模板。
- `.env.local`：本机实际配置，已加入 `.gitignore`，不要提交。

## 上游约束

`third_party/XianYuApis` 作为独立上游目录保留，不直接修改。项目自有适配层放在 `integrations/xianyu_core`。

## 尚未完成

- 平台确认发货接口。
- 闲鱼商品自动发布执行器；未完成前产品发布入口不在导航中展示。
- 代理节点批量导入和批量分配。
