# Deployment

正式 Docker 一键部署请直接使用 [`packaging.md`](packaging.md) 中的本项目镜像包、
`compose.all.yml` 和 `开始部署.sh`。本页其余内容用于源码安装、开发工作区和
systemd 方式，不是 Docker ALL 堆栈的操作步骤。

## Layout

Recommended production path:

```text
/opt/xianyu
```

源码启动配置：

```text
.env.example  # 中文模板，只提交模板
.env.local    # 实际私有值，由首次启动创建并被 Git 忽略
```

源码模式只需要填写外部 MySQL、Redis 地址，JWT 由 `npm run dev` 首次自动生成。
Docker 配置、ALL 零参数启动和完整参数分类见
[`configuration.md`](configuration.md)。不要提交 `.env.local`、`.env.docker` 或任何
真实密钥，也不要创建用途不明确的 `.env`。

## Install

```bash
sudo apt-get install chromium xvfb x11vnc fluxbox
cd /opt/xianyu
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt
.venv/bin/pip install -r integrations/xianyu_core/requirements.txt
npm install
npm --prefix apps/admin install
npm run build
```

## Database

Create the database before first start:

```sql
CREATE DATABASE xianyu_admin DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The API creates/extends tables on startup using the current lightweight migration layer.

## Services

Create the persistent product image directory before starting the services:

```bash
sudo install -d -o xianyu -g xianyu /opt/xianyu/data/product-images
sudo install -d -o xianyu -g xianyu /opt/xianyu/data/web-notification-sounds
sudo install -d -m 700 -o xianyu -g xianyu /opt/xianyu/data/browser-profiles
sudo install -d -m 755 -o xianyu -g xianyu /opt/xianyu/third_party/fingerprint-chromium
```

Set `XIANYU_PRODUCT_IMAGE_DIR=/opt/xianyu/data/product-images` in the deployment
environment. The API writes uploads there and the queue worker reads the same
files while publishing, so both services must share this directory.

Set
`XIANYU_WEB_NOTIFICATION_SOUND_DIR=/opt/xianyu/data/web-notification-sounds`
for the platform-wide browser message sound. API and worker containers should
mount the same persistent directory so a custom uploaded sound survives image
upgrades.

Set `XIANYU_IM_VERIFICATION_PROFILE_DIR=/opt/xianyu/data/browser-profiles` for
the platform-account, QR-login, and manual IM risk-verification browsers. The
API owns one Xvfb/x11vnc desktop and serializes these sessions globally;
Chromium profiles remain isolated by account under this directory. The VNC
listener binds to loopback and is reachable from the frontend only through an
authenticated one-time WebSocket ticket. Platform-account sessions also keep
CDP on `127.0.0.1` (port `9222` by default); do not publish that port through a
firewall, reverse proxy, or container port mapping. Keep
`XIANYU_IM_VERIFICATION_ALLOW_NO_SANDBOX=false` when the API runs as the
`xianyu` system user. Clearing browser data or deleting an account removes only
that account's directory below `XIANYU_IM_VERIFICATION_PROFILE_DIR`; the API
first stops any matching visual-browser session and the queue worker performs
the account-deletion cleanup.

Set `XIANYU_FINGERPRINT_BROWSER_ROOT=/opt/xianyu/third_party/fingerprint-chromium`
for the versioned Fingerprint Chromium cold configuration. Uploads and official
release downloads are validated and installed under `releases/<version>` from
System Settings. Persist this directory across deployments, but do not commit
downloaded browser binaries or temporary archives to the application repository.

Copy templates:

```bash
sudo cp deploy/systemd/xianyu-api.service /etc/systemd/system/
sudo cp deploy/systemd/xianyu-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xianyu-api xianyu-worker
```

Check:

```bash
systemctl status xianyu-api
systemctl status xianyu-worker
npm run check:internal
```

### Workspace/container service mode

Do not use `npm run start:local` as a long-running deployment command. It is an
interactive development command and keeps all child output attached to the
calling terminal. If that terminal is no longer drained, application logging
can eventually block the single API event loop.

For the current `/workspaces/xianyu` container deployment, build the frontend
and use the detached service manager instead:

```bash
npm run service:deploy
npm run service:status
```

The manager runs API and queue worker in independent process groups, redirects
their output to `data/logs`, rotates each log after 20 MiB, and runs an API
liveness watchdog. Three consecutive `/api/health` failures restart only the
API; a stopped worker is started independently. Runtime PID and health state
are kept below `data/service-runtime`, which is ignored by Git.

Operational commands:

```bash
npm run service:start
npm run service:stop
npm run service:restart
npm run service:status
```

The default thresholds can be overridden without changing the repository:

```text
XIANYU_SERVICE_HEALTH_INTERVAL_SECONDS=10
XIANYU_SERVICE_HEALTH_TIMEOUT_SECONDS=3
XIANYU_SERVICE_HEALTH_FAILURES_BEFORE_RESTART=3
XIANYU_SERVICE_API_START_GRACE_SECONDS=45
XIANYU_SERVICE_LOG_MAX_BYTES=20971520
XIANYU_SERVICE_LOG_KEEP_FILES=5
```

## Nginx

Use `deploy/nginx/xianyu-admin.conf` when serving the built Ant frontend directly.

```bash
sudo cp deploy/nginx/xianyu-admin.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://内网机器IP:9001
```

### Internal HTTPS

For the internal `192.168.2.3` deployment, install the certificate and key
outside the repository under `/etc/xianyu/tls`, then install
`deploy/nginx/xianyu-admin-https.conf`. The HTTPS proxy keeps the existing
admin preview and API processes private behind one origin:

```text
https://192.168.2.3/
https://192.168.2.3:6161/
https://192.168.2.3/api/
```

Nginx serves the built frontend directly from
`/workspaces/xianyu/apps/admin/dist` and terminates TLS on container ports `443`
and `9000`; deployments that publish host port `6161` to container port `9000`
can therefore use the HTTPS `:6161` URL. `vite preview` remains available for
interactive development but is not required by this deployment.

The certificate bundle must contain the leaf and intermediate certificate.
Keep `privkey.pem` mode `0600`; never commit the deployment ZIP or extracted
private key. When Nginx runs on the Docker host, publish the container's
ports 8000 and 9001 on host loopback or update the upstreams to stable Docker
service names.

## Auth bootstrap

Open the web login page. It shows the parsed visitor IP/source. If no admin user exists, the page shows “初始化首个管理员”. After the first user exists, the page only shows username/password login and API requests require JWT.

## Logs and backup

Minimum production checks:

- systemd logs: `journalctl -u xianyu-api -f`, `journalctl -u xianyu-worker -f`
- workspace/container logs: `data/logs/api.log`, `data/logs/worker.log`,
  `data/logs/watchdog.log`
- MySQL backup: dump `xianyu_admin`
- product image backup: include the directory configured by `XIANYU_PRODUCT_IMAGE_DIR`
- custom browser sound backup: include `XIANYU_WEB_NOTIFICATION_SOUND_DIR`
- env backup: store `.env.local` securely outside git
- do not commit `node_modules`, `apps/admin/dist`, `.env.local`, or uploaded image files
