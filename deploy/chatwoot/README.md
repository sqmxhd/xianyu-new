# Chatwoot 官方镜像部署

本项目不再修改或构建 Chatwoot。根目录 `开始部署.sh` 支持两种官方镜像准备方式：

- 从 Docker Hub 拉取固定兼容版本；
- 从脚本同级目录选择由 `docker save` 导出的官方镜像归档。

当前兼容基线为 `chatwoot/chatwoot:v4.16.0`。部署脚本会将在线拉取或本地导入的
镜像统一标记为 `xianyu-local/chatwoot:4.16.0`，根目录 `compose.all.yml` 只使用
这个本地标签，并设置 `pull_policy: never`。

消息撤回使用 Chatwoot 官方能力：客服在 Chatwoot 删除已经映射的公开出站消息后，
Chatwoot 发出 `message_updated` Webhook；本项目识别删除状态、调用闲鱼撤回，并通过
官方消息 API 创建包含原消息内容和撤回结果的私密快照。该链路不需要 Chatwoot 补丁。

官方 Chatwoot 不提供本项目曾经添加的独立“撤回”菜单。网页端和手机端都使用
Chatwoot 原生“删除”操作触发上述链路。
