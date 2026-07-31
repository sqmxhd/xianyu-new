# HTTPS 证书目录

启动 Docker 网关前，把证书放到本目录并使用以下固定文件名：

- `fullchain.pem`：服务器证书和中间证书链。
- `privkey.pem`：服务器私钥，建议宿主机权限设置为 `0600`。

证书和私钥已被 `.gitignore` 排除，严禁提交到 Git。
