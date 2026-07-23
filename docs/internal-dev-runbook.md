# 内网调试启动方案

## 目标

实测按接近正式部署的方式执行：先构建 Ant 后台，再启动 API、worker、9000 端口后台入口。

```bash
npm run dev
```

启动后访问：

```text
http://内网机器IP:9000
```

## 服务端口

| 服务 | 监听 | 说明 |
|---|---|---|
| Ant 后台 preview | `0.0.0.0:9000` | 内网浏览器访问入口，服务已构建的前端产物 |
| FastAPI | `0.0.0.0:8000` | 由 9000 端口的 `/api` 代理访问 |
| Worker | 本机进程 | 消费 Redis 队列并更新 MySQL 任务状态 |
| MySQL | `192.168.2.3:3306` | 数据库 |
| Redis | `192.168.2.3:6379` | 队列和 worker |

## 配置文件

实际配置：

```text
.env.local
```

唯一模板：

```text
.env.example
```

`.env.local` 已加入 `.gitignore`，不要提交。

当前数据库连接：

```text
mysql+pymysql://root:123456789.@192.168.2.3:3306/xianyu_admin?charset=utf8mb4
```

当前 Redis 连接：

```text
redis://:123456789.@192.168.2.3:6379/0
```

`npm run dev` / `npm run start:local` 会在启动前自动创建数据库。也可以单独执行：

```bash
npm run db:ensure
```

等价 SQL：

```sql
CREATE DATABASE xianyu_admin DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Redis 队列配置

后台页面保存配置：

```text
backend: redis
broker_url: redis://:123456789.@192.168.2.3:6379/0
queue_name: xianyu-admin
```

`.env.local` 同时设置：

```bash
XIANYU_REDIS_URL=redis://:123456789.@192.168.2.3:6379/0
```

## Worker

`npm run dev` / `npm run start:local` 会同时启动 worker。单独调试 worker 时可执行：

```bash
npm run worker:queue
```

只消费一条任务用于调试：

```bash
npm run worker:queue:once
```

任务会先写入 MySQL 的 `xianyu_background_tasks` 表。Redis 只保存 `task_id`，worker 以数据库记录为准更新 `pending/running/success/failed` 状态。

## 启动前准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
pip install -r integrations/xianyu_core/requirements.txt

npm install
npm --prefix apps/admin install
```

## 启动

```bash
npm run dev
```

`npm run dev` 现在就是实测入口，等同 `npm run start:local`。需要前端/后端热更新开发时使用 `npm run dev:hot`。

## 健康检查

启动前可检查 MySQL/Redis：

```bash
npm run check:internal
```

如果 API 尚未启动，`api/health` 会失败，这是预期；启动 `npm run dev` 后再执行应全部通过。

## 安全说明

内网测试也按正式登录链路验证，必须在 `.env.local` 设置：

```text
XIANYU_JWT_SECRET=换成一串随机长密钥
```

登录页会显示当前访问 IP 和解析来源。首次访问后台时，如果系统没有管理员，页面会显示“初始化首个管理员”；已有管理员后只显示用户名/密码登录。除 `/api/health`、`/api/auth/setup-status`、`/api/auth/client-info`、`/api/auth/login`、`/api/auth/bootstrap` 外，所有 API 都要求 `Authorization: Bearer <jwt>`。
