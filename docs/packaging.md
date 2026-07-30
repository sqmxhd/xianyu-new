# GitLab container delivery

## Pipeline contract

The pipeline has exactly two stages:

```text
test -> docker
```

Stage names are metadata only. Job and artifact names do not repeat a stage
name:

```text
backend
frontend
portability
image-amd64
```

Every branch and merge request pipeline runs tests. Container publishing is
restricted to:

- the lowercase `tg` branch, which publishes `latest`, the short commit SHA,
  and the full commit SHA;
- Git tags, which publish the version tag (with an optional leading `v`
  removed) and the full commit SHA.

`main` and feature branches never publish an image. A Git tag does not move
`latest`. The deployment consumes the registry directly, so the pipeline does
not create a downloadable OCI archive.

## Required runner

The container jobs use the `docker` tag and require a runner that allows
rootless BuildKit containers. No native Linux or Windows package runner is
required.

## GitLab HTTPS and dependency proxy

The GitLab server and registry are HTTPS-only. Do not add
`--insecure-registry`, `GIT_SSL_NO_VERIFY`, `http = true`, or
`insecure = true`.

Internal CA trust is owned by GitLab Runner and the Docker executor. CI jobs do
not copy certificates, mutate a container trust store, or consume runner
certificate variables. CI job images and Dockerfile base images use
`CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX`; the runner-provided trust applies to
the registry and dependency proxy.

The GitLab image dependency proxy is separate from npm and PyPI dependency
handling. npm and Python dependencies use their lock/requirements files and
GitLab CI caches. An internal npm/PyPI registry can be configured at runner or
group-variable level without changing artifact names.

## Docker deployment

The same application image is reused by three service containers:

- `api`: FastAPI and the Linux browser/VNC runtime.
- `worker`: background queue tasks.
- `gateway`: built frontend and HTTPS termination.

The image includes the checked offline IP location databases below
`apps/api/xianyu_admin_api/data`. Their sizes and checksums are validated by
the test suite, and the Docker build runs the application resource verifier
before publishing an image.

Database task rows are durable in MySQL. Redis carries task IDs to the worker
and does not replace the database. Neither server runs as a child process in the
application image.

For a self-contained deployment, enable the `bundled` profile through the
provided environment template. MySQL and Redis then run as separate containers:

```bash
cp .env.docker.example .env.docker
docker login 192.168.2.5:5050
docker compose --env-file .env.docker --profile bundled pull
docker compose --env-file .env.docker --profile bundled up -d --wait --remove-orphans
```

To use externally managed MySQL and Redis, use the external template. Its empty
`COMPOSE_PROFILES` value leaves the bundled infrastructure disabled:

```bash
cp .env.docker.external.example .env.docker
docker login 192.168.2.5:5050
docker compose --env-file .env.docker pull
docker compose --env-file .env.docker up -d --wait --remove-orphans
```

The Compose file is an image-only production definition. It never builds from
the local checkout, always checks the registry before starting, and pins the
runtime platform to `linux/amd64`. Local development remains the source-based
`npm run dev` workflow.

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
custom web-notification sounds, browser profiles, and managed browser
downloads. The API and worker share only the application data volumes.

The gateway and API communicate on a frontend network; the API, worker, MySQL,
and Redis communicate on a backend network. The backend network remains a
normal bridge because the worker needs outbound platform access. Container
JSON logs rotate at 20 MiB with five files retained.

Normal API requests keep a 64 MiB gateway limit. Only the two managed-browser
archive upload endpoints accept 520 MiB requests, disable proxy request
buffering, and use a ten-minute upload timeout. The application still enforces
its 512 MiB archive limit. Realtime and VNC streaming locations do not write
per-frame access logs.
