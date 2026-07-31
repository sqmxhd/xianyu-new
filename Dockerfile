# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE_PREFIX=docker.io/library

FROM ${BASE_IMAGE_PREFIX}/node:20.19.2-bookworm-slim AS frontend
WORKDIR /src/apps/admin
COPY apps/admin/package.json apps/admin/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY apps/admin/ ./
RUN npm run build

FROM ${BASE_IMAGE_PREFIX}/python:3.13-slim-bookworm AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/xianyu-venv
COPY apps/api/requirements.txt /tmp/requirements/api.txt
COPY integrations/xianyu_core/requirements.txt /tmp/requirements/core.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/xianyu-venv/bin/python -m pip install --upgrade pip && \
    /opt/xianyu-venv/bin/python -m pip install \
      -r /tmp/requirements/api.txt \
      -r /tmp/requirements/core.txt

FROM ${BASE_IMAGE_PREFIX}/python:3.13-slim-bookworm AS runtime
ARG BUILD_VERSION=development
ARG BUILD_COMMIT=unknown
LABEL org.opencontainers.image.title="xianyu-admin" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${BUILD_COMMIT}"

ENV PATH="/opt/xianyu-venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh:en_US:en \
    LC_ALL=zh_CN.UTF-8 \
    XIANYU_PRODUCT_IMAGE_DIR=/data/product-images \
    XIANYU_CONTACT_AVATAR_DIR=/data/contact-avatars \
    XIANYU_WEB_NOTIFICATION_SOUND_DIR=/data/web-notification-sounds \
    XIANYU_IM_VERIFICATION_PROFILE_DIR=/data/browser-profiles \
    XIANYU_FINGERPRINT_BROWSER_ROOT=/data/fingerprint-chromium \
    XIANYU_STANDARD_BROWSER_ROOT=/data/standard-chromium \
    XIANYU_IM_VERIFICATION_BROWSER_PATH=/usr/bin/chromium \
    XIANYU_IM_VERIFICATION_ALLOW_NO_SANDBOX=false \
    XIANYU_ADMIN_DIST_DIR=/app/apps/admin/dist

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      chromium \
      fluxbox \
      fonts-noto-cjk \
      locales \
      nginx-light \
      tini \
      x11vnc \
      xvfb && \
    sed -i 's/^# *zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen && \
    groupadd --gid 10001 xianyu && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin xianyu && \
    mkdir -p \
      /data/product-images \
      /data/contact-avatars \
      /data/web-notification-sounds \
      /data/browser-profiles \
      /data/fingerprint-chromium \
      /data/standard-chromium \
      /var/cache/nginx/xianyu \
      /var/lib/nginx/xianyu && \
    chown -R xianyu:xianyu /data /var/cache/nginx/xianyu /var/lib/nginx/xianyu && \
    rm -rf /var/lib/apt/lists/*

COPY --from=dependencies /opt/xianyu-venv /opt/xianyu-venv
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY apps/ /app/apps/
COPY integrations/ /app/integrations/
COPY third_party/XianYuApis/ /app/third_party/XianYuApis/
COPY tools/ /app/tools/
COPY deploy/nginx/xianyu-container.conf /app/deploy/nginx/xianyu-container.conf
COPY deploy/nginx/chatwoot-container.conf /app/deploy/nginx/chatwoot-container.conf
COPY .env.example README.md /app/
COPY --from=frontend /src/apps/admin/dist /app/apps/admin/dist

RUN python -m tools.package.entry verify

EXPOSE 8000 8443
VOLUME ["/data/product-images", "/data/contact-avatars", "/data/web-notification-sounds", "/data/browser-profiles", "/data/fingerprint-chromium", "/data/standard-chromium"]

ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/tools/container_entry.py"]
CMD ["api"]
