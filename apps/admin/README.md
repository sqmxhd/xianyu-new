# Xianyu Ant Design Admin

真实 Ant Design / Ant Design 组件后台，不是仿样式页面。

## 启动

先启动后端 API：

```bash
uvicorn apps.api.xianyu_admin_api.main:app --reload --host 127.0.0.1 --port 8000
```

再启动前端：

```bash
cd apps/admin
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

当前实现范围：

- 账户列表
- 新增/编辑/删除账户
- 账户级 SOCKS5 / SOCKS5h 代理配置
- 代理连通性测试
- 启动/停止账户
- 运行状态展示

未在本阶段实现：

- MySQL 持久化
- 会话列表
- 消息列表
- Bark 通知
- 自动回复
- 自动发货
- 商品发布
