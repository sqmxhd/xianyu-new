# 可选内部 CA 目录

只有 Chatwoot 使用内部私有 CA 签发的 HTTPS 证书时，才需要把根证书放到：

```text
config/ca/internal-root.crt
```

使用公共可信 CA 时保持本目录只有本说明文件即可。真实 CA 文件已被
`.gitignore` 排除，不要提交到 Git。
