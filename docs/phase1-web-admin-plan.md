# Phase 1-Web：Ant Design 后台管理计划

本阶段替代命令行式验证，使用真实 Ant Design 后台作为主要验收入口。

## 已落地范围

- `apps/api`：FastAPI 后端 API
- `apps/admin`：React + Ant Design 后台
- 账户新增、编辑、删除
- 账户级 SOCKS5 / SOCKS5h 代理配置
- 代理地址 TCP 连通性测试
- 账户启动 / 停止接口
- 运行状态展示

## 架构边界

```text
apps/admin
  Ant Design 后台
    |
    v
apps/api
  FastAPI 管理服务
    |
    v
integrations/xianyu_core
  项目自有适配层
    |
    v
third_party/XianYuApis
  上游协议核心，保持独立，不直接修改
```

## 当前限制

- 真实闲鱼连接依赖 `integrations/xianyu_core/requirements.txt`。
- Cookie 需要从后台录入，缺失 Cookie 时启动会进入 `auth_expired`。
- 代理测试当前验证代理地址 TCP 可连接，不代表目标站点请求一定成功。

## Phase 2 更新

账户、代理配置、运行状态已经在 Phase 2 切到数据库持久化。详见：

- `docs/phase2-web-persistence-runtime.md`

## 下一阶段

Phase 2-Web 应该接 MySQL 持久化和多账户运行管理：

- 账户表
- 代理配置表或账户内嵌代理字段
- runtime 状态表
- runtime event 日志表
- 多账户 worker 管理
- 状态变更推送到前端

Phase 3-Web 再接会话列表与消息收发。
