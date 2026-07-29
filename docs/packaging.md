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
archive-amd64
```

Branch pipelines run tests automatically. Container images run automatically
on the default branch and tags, and are optional manual jobs on other branches.
Tagged pipelines also export a checksummed OCI archive.

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
