# GitLab packaging and container delivery

## Pipeline contract

The pipeline has exactly three stages:

```text
test -> binary -> docker
```

Stage names are metadata only. Job and artifact names do not repeat a stage
name:

```text
backend
frontend
portability
linux-x64
windows-x64
image-amd64
archive-amd64
```

Branch pipelines run tests automatically. Native packages and images run
automatically on the default branch and tags, and are optional manual jobs on
other branches. Tagged native packages are also uploaded to the GitLab Generic
Package Registry.

## Required runners

The Linux runner uses the `docker` tag and must allow rootless BuildKit
containers. The Windows runner uses the `windows-x64` tag and the PowerShell
shell executor. Install Python 3 and Node.js 20 or newer on the Windows runner.

PyInstaller builds are native:

- Linux artifacts are built by the Linux runner.
- Windows artifacts are built by the Windows runner.
- Wine-based cross-building is not used.

The Windows package supports the API, worker, frontend, messaging, orders, and
other non-visual operations. The embedded browser/VNC runtime remains a Linux
capability because it depends on Xvfb, x11vnc, fluxbox, and Linux process
inspection. Windows displays an explicit unsupported message for that feature;
use the Docker deployment on Windows when full VNC parity is required.

## GitLab HTTPS and dependency proxy

The GitLab server and registry are HTTPS-only. Do not add
`--insecure-registry`, `GIT_SSL_NO_VERIFY`, `http = true`, or
`insecure = true`.

Install the internal root CA on both runner hosts. Configure GitLab Runner with
the same CA through `tls-ca-file`, and expose it to the Docker executor helper
as `/etc/gitlab-runner/certs/ca.crt`. Restart GitLab Runner and Docker after
changing their trust stores.

CI job images and Dockerfile base images use
`CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX`. BuildKit receives
`CI_SERVER_TLS_CA_FILE` as an explicit CA for both `CI_REGISTRY` and
`CI_DEPENDENCY_PROXY_SERVER`.

The GitLab image dependency proxy is separate from npm and PyPI dependency
handling. npm and Python dependencies use their lock/requirements files and
GitLab CI caches. An internal npm/PyPI registry can be configured at runner or
group-variable level without changing artifact names.

## Native packages

Build locally on the matching operating system:

```bash
bash tools/package/build_linux.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File tools/package/build_windows.ps1
```

Artifacts are written below `artifacts/`:

```text
xianyu-admin-<version>-linux-x64.tar.gz
xianyu-admin-<version>-windows-x64.zip
```

Each archive has a matching `.sha256` file. The extracted distribution contains
one command:

```text
xianyu serve
xianyu worker
xianyu version
xianyu verify
```

Copy `.env.example` to `.env` next to the executable before starting the API or
worker. Real environment files, cookies, browser profiles, TLS private keys,
and downloaded browser binaries are not included in an artifact.

The native archive does not embed a database or a Redis server. Start the API
and worker as separate processes and point both processes at the same external
MySQL and Redis services. SQLite remains useful for tests and diagnostics, but
MySQL is the production database.

## Docker deployment

The same application image is reused by three service containers:

- `api`: FastAPI and the Linux browser/VNC runtime.
- `worker`: background queue tasks.
- `gateway`: built frontend and HTTPS termination.

Database task rows are durable in MySQL. Redis carries task IDs to the worker
and does not replace the database. Neither server runs as a child process in the
application image.

For a self-contained deployment, enable the `bundled` profile through the
provided environment template. MySQL and Redis then run as separate containers:

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker --profile bundled up -d --build
```

To use externally managed MySQL and Redis, use the external template. Its empty
`COMPOSE_PROFILES` value leaves the bundled infrastructure disabled:

```bash
cp .env.docker.external.example .env.docker
docker compose --env-file .env.docker up -d
```

The deployment exposes only the HTTPS gateway. The default host port is `6161`.
`XIANYU_BIND_IP` defaults to `0.0.0.0`, so the gateway accepts traffic on every
IPv4 interface. Change it when a deployment must be restricted to one host
address. MySQL, Redis, and the API are not published to the host.

No public application address is compiled into the image. Same-origin access
does not require a CORS entry. Configure `XIANYU_CORS_ORIGINS` only for
separately hosted frontends. Configure `XIANYU_PUBLIC_BASE_URL` with the actual
externally reachable HTTPS origin when Chatwoot or another webhook consumer
needs an absolute callback URL.

TLS certificates and the internal root CA are bind-mounted at runtime and are
never copied into the image. The mounted certificate must cover the IP address
or DNS name used by clients.

Persistent named volumes contain database data, Redis data, product images,
browser profiles, and managed browser downloads.
