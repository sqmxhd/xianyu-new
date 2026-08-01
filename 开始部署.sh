#!/usr/bin/env bash
set -Eeuo pipefail

# 闲鱼管理平台 Docker 部署入口。
# 本项目镜像从同级压缩包导入；官方依赖镜像可在线拉取或从本地归档导入。

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DEPLOY_ROOT="$SCRIPT_DIR/XIANYU_DATA"
COMPOSE_FILE="$SCRIPT_DIR/compose.all.yml"
PACKAGE_GLOB="xianyu-admin-*-linux-amd64.docker.tar.gz"
COMPOSE_PROJECT_NAME="xianyu"

info() { printf '\033[1;34m[信息]\033[0m %s\n' "$*"; }
success() { printf '\033[1;32m[完成]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[注意]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }

pause() {
  printf '\n按回车键继续...'
  read -r _ || true
}

confirm() {
  local prompt="$1" answer
  read -r -p "$prompt [y/N] " answer || return 1
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"
}

ensure_dependencies() {
  require_command docker
  require_command openssl
  require_command tar
  require_command gzip
  require_command sha256sum
  docker compose version >/dev/null 2>&1 || fail "需要 Docker Compose v2（docker compose）"
  [ -f "$COMPOSE_FILE" ] || fail "缺少 Docker 配置文件：$COMPOSE_FILE"
}

ensure_layout() {
  local directory
  for directory in \
    config state releases logs \
    secrets/xianyu \
    certificates/ca/private certificates/ca/certs certificates/trust \
    certificates/xianyu certificates/chatwoot \
    mysql redis product-images contact-avatars notification-sounds \
    browser-profiles fingerprint-chromium standard-chromium \
    chatwoot/postgres chatwoot/redis chatwoot/storage
  do
    mkdir -p "$DEPLOY_ROOT/$directory"
  done
  chmod 700 "$DEPLOY_ROOT/secrets" "$DEPLOY_ROOT/secrets/xianyu" \
    "$DEPLOY_ROOT/certificates/ca/private"
}

random_secret() {
  openssl rand -hex "${1:-48}"
}

ensure_chatwoot_secrets() {
  local target="$DEPLOY_ROOT/secrets/chatwoot.env" temporary redis_password
  if [ -s "$target" ]; then
    if ! grep -q '^REDIS_URL=' "$target"; then
      redis_password="$(sed -n 's/^REDIS_PASSWORD=//p' "$target" | tail -n 1)"
      [ -n "$redis_password" ] || fail "Chatwoot 密钥文件缺少 REDIS_PASSWORD"
      [[ "$redis_password" =~ ^[A-Fa-f0-9]+$ ]] ||
        fail "Chatwoot REDIS_PASSWORD 不是脚本生成的安全格式，无法自动升级"
      printf '\nREDIS_URL=redis://:%s@chatwoot-redis:6379\n' "$redis_password" >> "$target"
      chmod 600 "$target"
      success "已补齐 Chatwoot Redis 认证地址"
    fi
    return 0
  fi
  temporary="$target.tmp.$$"
  umask 077
  redis_password="$(random_secret 32)"
  {
    printf 'POSTGRES_PASSWORD=%s\n' "$(random_secret 32)"
    printf 'REDIS_PASSWORD=%s\n' "$redis_password"
    printf 'REDIS_URL=redis://:%s@chatwoot-redis:6379\n' "$redis_password"
    printf 'SECRET_KEY_BASE=%s\n' "$(random_secret 64)"
    printf 'ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY=%s\n' "$(random_secret 32)"
    printf 'ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY=%s\n' "$(random_secret 32)"
    printf 'ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT=%s\n' "$(random_secret 32)"
  } > "$temporary"
  chmod 600 "$temporary"
  mv -f "$temporary" "$target"
  success "已生成 Chatwoot 数据库和应用密钥"
}

validate_port() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

validate_bind_ip() {
  local address="$1" octet
  local -a octets
  [[ "$address" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
  IFS='.' read -r -a octets <<< "$address"
  for octet in "${octets[@]}"; do
    [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
  done
}

validate_https_url() {
  [[ "$1" =~ ^https://[^[:space:]#]+$ ]]
}

port_is_busy() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -H -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"; then
      return 0
    fi
  fi
  docker ps --format '{{.Ports}}' 2>/dev/null | grep -Eq ":${port}->"
}

available_port() {
  local candidate="$1" reserved="${2:-}"
  while [ "$candidate" -le 65535 ]; do
    if [ "$candidate" != "$reserved" ] && ! port_is_busy "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
    candidate=$((candidate + 1))
  done
  fail "没有找到可用的宿主机端口"
}

read_config_value() {
  local name="$1" file="$DEPLOY_ROOT/config/deployment.env"
  [ -f "$file" ] || return 0
  sed -n "s/^${name}=//p" "$file" | tail -n 1
}

prompt_value() {
  local prompt="$1" default_value="$2" result
  read -r -p "$prompt [$default_value]: " result
  printf '%s\n' "${result:-$default_value}"
}

configure_deployment() {
  local bind_ip xianyu_port chatwoot_port
  local xianyu_url chatwoot_url enable_chatwoot old_xianyu_port old_chatwoot_port target
  local chatwoot_default chatwoot_choice suggested_xianyu_port suggested_chatwoot_port

  old_xianyu_port="$(read_config_value XIANYU_HTTPS_PORT)"
  old_chatwoot_port="$(read_config_value CHATWOOT_HTTPS_PORT)"
  bind_ip="$(prompt_value '对外监听 IP' "$(read_config_value XIANYU_BIND_IP || true)")"
  bind_ip="${bind_ip:-0.0.0.0}"
  validate_bind_ip "$bind_ip" || fail "监听 IP 格式不正确：$bind_ip"

  enable_chatwoot="$(read_config_value COMPOSE_PROFILES || true)"
  if [ "$enable_chatwoot" = chatwoot ]; then
    chatwoot_default=1
  else
    chatwoot_default=2
  fi
  printf '内置官方 Chatwoot：1) 启用  2) 不启用\n'
  chatwoot_choice="$(prompt_value '请选择' "$chatwoot_default")"
  case "$chatwoot_choice" in
    1) enable_chatwoot=chatwoot ;;
    2) enable_chatwoot= ;;
    *) fail "Chatwoot 选择无效" ;;
  esac

  if [ -n "$old_xianyu_port" ]; then
    suggested_xianyu_port="$old_xianyu_port"
  else
    suggested_xianyu_port="$(available_port 6161)"
  fi
  xianyu_port="$(prompt_value '闲鱼管理平台 HTTPS 端口' "$suggested_xianyu_port")"
  validate_port "$xianyu_port" || fail "闲鱼平台端口必须为 1-65535"
  if [ "$xianyu_port" != "$old_xianyu_port" ] && port_is_busy "$xianyu_port"; then
    fail "端口 $xianyu_port 已被占用"
  fi

  chatwoot_port="${old_chatwoot_port:-6443}"
  if [ "$enable_chatwoot" = chatwoot ]; then
    if [ -n "$old_chatwoot_port" ]; then
      suggested_chatwoot_port="$old_chatwoot_port"
    else
      suggested_chatwoot_port="$(available_port 6443 "$xianyu_port")"
    fi
    chatwoot_port="$(prompt_value 'Chatwoot HTTPS 端口' "$suggested_chatwoot_port")"
    validate_port "$chatwoot_port" || fail "Chatwoot 端口必须为 1-65535"
    [ "$chatwoot_port" != "$xianyu_port" ] || fail "两个 HTTPS 端口不能相同"
    if [ "$chatwoot_port" != "$old_chatwoot_port" ] && port_is_busy "$chatwoot_port"; then
      fail "端口 $chatwoot_port 已被占用"
    fi
  fi

  xianyu_url="$(prompt_value '浏览器访问闲鱼管理平台的完整地址' "$(read_config_value XIANYU_PUBLIC_BASE_URL || true)")"
  xianyu_url="${xianyu_url:-https://127.0.0.1:$xianyu_port}"
  validate_https_url "$xianyu_url" || fail "平台地址必须是完整 HTTPS URL"

  chatwoot_url="$(read_config_value CHATWOOT_PUBLIC_BASE_URL || true)"
  if [ "$enable_chatwoot" = chatwoot ]; then
    chatwoot_url="$(prompt_value '浏览器访问 Chatwoot 的完整地址' "$chatwoot_url")"
    chatwoot_url="${chatwoot_url:-https://127.0.0.1:$chatwoot_port}"
    validate_https_url "$chatwoot_url" || fail "Chatwoot 地址必须是完整 HTTPS URL"
  else
    chatwoot_url="${chatwoot_url:-https://127.0.0.1:$chatwoot_port}"
  fi

  printf '\n即将对外开放：\n'
  printf '  闲鱼管理平台：%s:%s -> %s\n' "$bind_ip" "$xianyu_port" "$xianyu_url"
  if [ "$enable_chatwoot" = chatwoot ]; then
    printf '  Chatwoot：%s:%s -> %s\n' "$bind_ip" "$chatwoot_port" "$chatwoot_url"
  else
    printf '  Chatwoot：本次不启动\n'
  fi
  confirm "确认保存以上端口和地址配置？" || fail "已取消配置修改"

  target="$DEPLOY_ROOT/config/deployment.env"
  umask 077
  {
    printf '# 此文件由“开始部署.sh”维护。升级版本包不会覆盖。\n'
    printf 'DEPLOY_ROOT=%s\n' "$DEPLOY_ROOT"
    printf 'COMPOSE_PROJECT_NAME=%s\n' "$COMPOSE_PROJECT_NAME"
    printf 'COMPOSE_PROFILES=%s\n' "$enable_chatwoot"
    printf 'XIANYU_BIND_IP=%s\n' "$bind_ip"
    printf 'XIANYU_HTTPS_PORT=%s\n' "$xianyu_port"
    printf 'XIANYU_PUBLIC_BASE_URL=%s\n' "$xianyu_url"
    printf 'XIANYU_CORS_ORIGINS=%s\n' "$xianyu_url"
    printf 'CHATWOOT_BIND_IP=%s\n' "$bind_ip"
    printf 'CHATWOOT_HTTPS_PORT=%s\n' "$chatwoot_port"
    printf 'CHATWOOT_PUBLIC_BASE_URL=%s\n' "$chatwoot_url"
    printf 'CHATWOOT_ENABLE_ACCOUNT_SIGNUP=true\n'
  } > "$target.tmp.$$"
  chmod 600 "$target.tmp.$$"
  mv -f "$target.tmp.$$" "$target"
  success "部署参数已保存到 $target"
}

list_packages() {
  local packages=()
  shopt -s nullglob
  packages=("$SCRIPT_DIR"/$PACKAGE_GLOB)
  shopt -u nullglob
  printf '%s\n' "${packages[@]}"
}

select_package() {
  local packages=() index choice
  while IFS= read -r choice; do
    [ -n "$choice" ] && packages+=("$choice")
  done < <(list_packages)
  [ "${#packages[@]}" -gt 0 ] || fail "脚本同级目录未找到 $PACKAGE_GLOB"
  printf '\n可用版本包：\n' >&2
  for index in "${!packages[@]}"; do
    printf '  %d) %s\n' "$((index + 1))" "$(basename -- "${packages[$index]}")" >&2
  done
  read -r -p "请选择版本 [1]: " choice
  choice="${choice:-1}"
  validate_port "$choice" || fail "选择无效"
  [ "$choice" -le "${#packages[@]}" ] || fail "选择无效"
  printf '%s\n' "${packages[$((choice - 1))]}"
}

verify_outer_checksum() {
  local package="$1" sidecar="$package.sha256"
  [ -f "$sidecar" ] || fail "缺少版本包校验文件：$(basename -- "$sidecar")"
  (
    cd -- "$(dirname -- "$package")"
    sha256sum -c -- "$(basename -- "$sidecar")"
  ) || fail "版本包 SHA-256 校验失败"
}

import_package() {
  local package="$1" activate="${2:-true}" filename version source_image target_image
  local release_dir architecture
  verify_outer_checksum "$package"
  filename="$(basename -- "$package")"
  version="${filename#xianyu-admin-}"
  version="${version%-linux-amd64.docker.tar.gz}"
  [[ "$version" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || fail "无法从文件名识别项目版本"
  source_image="xianyu/xianyu-admin:$version"
  target_image="xianyu-local/admin:$version"

  info "正在导入闲鱼管理平台镜像 $version"
  gzip -dc -- "$package" | docker load
  docker image inspect "$source_image" >/dev/null 2>&1 ||
    fail "镜像包未包含预期标签：$source_image"
  architecture="$(docker image inspect --format '{{.Architecture}}' "$source_image")"
  [ "$architecture" = amd64 ] || fail "项目镜像架构不是 linux/amd64：$architecture"
  docker tag "$source_image" "$target_image"

  ensure_layout
  release_dir="$DEPLOY_ROOT/releases/$version"
  mkdir -p "$release_dir"
  {
    printf 'RELEASE_VERSION=%s\n' "$version"
    printf 'XIANYU_IMAGE=%s\n' "$target_image"
  } > "$release_dir/release.env.tmp.$$"
  chmod 600 "$release_dir/release.env.tmp.$$"
  mv -f "$release_dir/release.env.tmp.$$" "$release_dir/release.env"
  if [ "$activate" = true ]; then
    install -m 600 "$release_dir/release.env" "$DEPLOY_ROOT/state/current-release.env"
  fi
  if [ "$activate" = true ]; then
    success "版本 $version 已导入并设为当前版本"
  else
    success "版本 $version 已导入，当前运行版本未切换"
  fi
}

select_dependency_archive() {
  local label="$1" hint="$2" files=() file choice index
  declare -A seen=()
  shopt -s nullglob nocaseglob
  for file in \
    "$SCRIPT_DIR"/*"$hint"*.docker.tar.gz \
    "$SCRIPT_DIR"/*"$hint"*.tar.gz \
    "$SCRIPT_DIR"/*"$hint"*.docker.tar \
    "$SCRIPT_DIR"/*"$hint"*.tar
  do
    if [ -f "$file" ] && [ -z "${seen[$file]:-}" ]; then
      files+=("$file")
      seen[$file]=1
    fi
  done
  shopt -u nullglob nocaseglob
  printf '\n%s 本地镜像包：\n' "$label" >&2
  for index in "${!files[@]}"; do
    printf '  %d) %s\n' "$((index + 1))" "$(basename -- "${files[$index]}")" >&2
  done
  printf '  0) 手动输入文件路径\n' >&2
  read -r -p '请选择: ' choice
  if [ "${choice:-0}" = 0 ]; then
    read -r -p "$label 镜像包路径: " file
    [ -f "$file" ] || fail "文件不存在：$file"
    printf '%s\n' "$file"
    return 0
  fi
  validate_port "$choice" || fail "选择无效"
  [ "$choice" -le "${#files[@]}" ] || fail "选择无效"
  printf '%s\n' "${files[$((choice - 1))]}"
}

load_docker_archive() {
  local archive="$1"
  info "正在导入 $(basename -- "$archive")"
  case "$archive" in
    *.gz|*.tgz) gzip -dc -- "$archive" | docker load ;;
    *) docker load --input "$archive" ;;
  esac
}

prepare_official_image() {
  local mode="$1" label="$2" hint="$3" source_image="$4" target_image="$5" archive
  if [ "$mode" = online ]; then
    info "正在拉取 $label：$source_image"
    docker pull "$source_image"
  else
    archive="$(select_dependency_archive "$label" "$hint")"
    load_docker_archive "$archive"
  fi
  docker image inspect "$source_image" >/dev/null 2>&1 ||
    fail "$label 镜像包未包含预期官方标签：$source_image"
  [ "$(docker image inspect --format '{{.Architecture}}' "$source_image")" = amd64 ] ||
    fail "$label 镜像不是 linux/amd64"
  docker tag "$source_image" "$target_image"
  success "$label 已准备：$target_image"
}

prepare_dependency_images() {
  local mode="${1:-}" choice enabled target="$DEPLOY_ROOT/config/images.env"
  if [ -z "$mode" ]; then
    printf '\n官方依赖镜像来源：\n'
    printf '  1) 在线拉取官方镜像\n'
    printf '  2) 导入本地官方镜像包\n'
    read -r -p '请选择 [1]: ' choice
    case "${choice:-1}" in
      1) mode=online ;;
      2) mode=offline ;;
      *) fail "依赖镜像来源选择无效" ;;
    esac
  fi

  prepare_official_image "$mode" MySQL mysql mysql:8.4 xianyu-local/mysql:8.4
  prepare_official_image "$mode" Redis redis redis:7.4-alpine xianyu-local/redis:7.4-alpine
  enabled="$(read_config_value COMPOSE_PROFILES || true)"
  if [ "$enabled" = chatwoot ]; then
    prepare_official_image "$mode" Chatwoot chatwoot chatwoot/chatwoot:v4.16.0 xianyu-local/chatwoot:4.16.0
    prepare_official_image "$mode" pgvector pgvector pgvector/pgvector:pg16 xianyu-local/pgvector:pg16
  fi

  umask 077
  {
    printf '# 官方镜像由“开始部署.sh”拉取或导入后统一标记。\n'
    printf 'MYSQL_IMAGE=xianyu-local/mysql:8.4\n'
    printf 'REDIS_IMAGE=xianyu-local/redis:7.4-alpine\n'
    printf 'CHATWOOT_IMAGE=xianyu-local/chatwoot:4.16.0\n'
    printf 'CHATWOOT_POSTGRES_IMAGE=xianyu-local/pgvector:pg16\n'
    printf 'CHATWOOT_REDIS_IMAGE=xianyu-local/redis:7.4-alpine\n'
  } > "$target.tmp.$$"
  chmod 600 "$target.tmp.$$"
  mv -f "$target.tmp.$$" "$target"
}

current_version() {
  local file="$DEPLOY_ROOT/state/current-release.env"
  [ -f "$file" ] || return 0
  sed -n 's/^RELEASE_VERSION=//p' "$file" | tail -n 1
}

compose() {
  local version release_file images_file profile
  local -a compose_args
  version="$(current_version)"
  [ -n "$version" ] || fail "尚未安装版本包"
  release_file="$DEPLOY_ROOT/state/current-release.env"
  images_file="$DEPLOY_ROOT/config/images.env"
  [ -f "$DEPLOY_ROOT/config/deployment.env" ] || fail "尚未完成部署配置"
  [ -f "$images_file" ] || fail "尚未准备官方依赖镜像"
  [ -f "$COMPOSE_FILE" ] || fail "Compose 文件不存在：$COMPOSE_FILE"
  compose_args=(
    --project-name "$COMPOSE_PROJECT_NAME"
    --env-file "$DEPLOY_ROOT/config/deployment.env"
    --env-file "$release_file"
    --env-file "$images_file"
    -f "$COMPOSE_FILE"
  )
  profile="$(read_config_value COMPOSE_PROFILES || true)"
  if [ "$profile" = chatwoot ]; then
    compose_args+=(--profile chatwoot)
  fi
  docker compose "${compose_args[@]}" "$@"
}

verify_runtime_images() {
  local release_file="$DEPLOY_ROOT/state/current-release.env"
  local images_file="$DEPLOY_ROOT/config/images.env"
  local profile name reference
  local -a names=(XIANYU_IMAGE MYSQL_IMAGE REDIS_IMAGE)

  [ -f "$release_file" ] || fail "尚未安装版本包"
  [ -f "$images_file" ] || fail "尚未准备官方依赖镜像"
  profile="$(read_config_value COMPOSE_PROFILES || true)"
  if [ "$profile" = chatwoot ]; then
    names+=(CHATWOOT_IMAGE CHATWOOT_POSTGRES_IMAGE CHATWOOT_REDIS_IMAGE)
  fi

  for name in "${names[@]}"; do
    if [ "$name" = XIANYU_IMAGE ]; then
      reference="$(sed -n "s/^${name}=//p" "$release_file" | tail -n 1)"
    else
      reference="$(sed -n "s/^${name}=//p" "$images_file" | tail -n 1)"
    fi
    [ -n "$reference" ] || fail "镜像配置缺少 $name"
    docker image inspect "$reference" >/dev/null 2>&1 ||
      fail "本地镜像不可用：$reference；请先导入版本包或运行“官方依赖镜像管理”"
  done
}

refresh_combined_ca() {
  local target="$DEPLOY_ROOT/certificates/trust/combined-ca.pem"
  : > "$target.tmp.$$"
  if [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    cp /etc/ssl/certs/ca-certificates.crt "$target.tmp.$$"
  elif [ -f /etc/pki/tls/certs/ca-bundle.crt ]; then
    cp /etc/pki/tls/certs/ca-bundle.crt "$target.tmp.$$"
  fi
  if [ -f "$DEPLOY_ROOT/certificates/trust/internal-root.crt" ]; then
    printf '\n' >> "$target.tmp.$$"
    sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' \
      "$DEPLOY_ROOT/certificates/trust/internal-root.crt" >> "$target.tmp.$$"
  fi
  grep -q 'BEGIN CERTIFICATE' "$target.tmp.$$" || fail "无法生成容器信任链"
  chmod 644 "$target.tmp.$$"
  mv -f "$target.tmp.$$" "$target"
}

certificate_public_key_digest() {
  openssl x509 -in "$1" -pubkey -noout 2>/dev/null |
    openssl pkey -pubin -outform DER 2>/dev/null |
    sha256sum | awk '{print $1}'
}

private_key_digest() {
  openssl pkey -in "$1" -pubout -outform DER 2>/dev/null |
    sha256sum | awk '{print $1}'
}

validate_site_certificate() {
  local fullchain="$1" key="$2"
  openssl x509 -in "$fullchain" -noout >/dev/null 2>&1 || fail "无法读取网站证书：$fullchain"
  openssl pkey -in "$key" -noout >/dev/null 2>&1 || fail "无法读取网站私钥：$key"
  [ "$(certificate_public_key_digest "$fullchain")" = "$(private_key_digest "$key")" ] ||
    fail "网站证书和私钥不匹配"
  openssl x509 -in "$fullchain" -checkend 86400 -noout >/dev/null 2>&1 ||
    fail "网站证书已过期或将在 24 小时内过期"
  if [ -s "$DEPLOY_ROOT/certificates/trust/combined-ca.pem" ]; then
    openssl verify \
      -CAfile "$DEPLOY_ROOT/certificates/trust/combined-ca.pem" \
      -untrusted "$fullchain" "$fullchain" >/dev/null 2>&1 ||
      fail "网站证书链无法通过当前根证书/系统 CA 验证"
  fi
}

install_site_certificate() {
  local service="$1" fullchain="$2" key="$3" target
  validate_site_certificate "$fullchain" "$key"
  target="$DEPLOY_ROOT/certificates/$service"
  mkdir -p "$target"
  install -m 644 "$fullchain" "$target/fullchain.pem.new"
  install -m 600 "$key" "$target/privkey.pem.new"
  mv -f "$target/fullchain.pem.new" "$target/fullchain.pem"
  mv -f "$target/privkey.pem.new" "$target/privkey.pem"
  success "$service 网站证书已安装"
}

import_root_certificate() {
  local source="$1" target="$DEPLOY_ROOT/certificates/trust/internal-root.crt" details
  openssl x509 -in "$source" -noout >/dev/null 2>&1 || fail "根证书格式无效"
  details="$(openssl x509 -in "$source" -noout -text 2>/dev/null)"
  grep -q 'CA:TRUE' <<< "$details" || fail "导入的证书不是 CA 根证书"
  install -m 644 "$source" "$target.new"
  mv -f "$target.new" "$target"
  refresh_combined_ca
  success "根证书已导入容器信任目录"
}

san_extension() {
  local values="$1" item index=1
  IFS=',' read -r -a SAN_VALUES <<< "$values"
  for item in "${SAN_VALUES[@]}"; do
    item="${item//[[:space:]]/}"
    [ -n "$item" ] || continue
    if [[ "$item" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || [[ "$item" == *:* ]]; then
      printf 'IP.%d = %s\n' "$index" "$item"
    elif [[ "$item" =~ ^[A-Za-z0-9*.-]+$ ]]; then
      printf 'DNS.%d = %s\n' "$index" "$item"
    else
      fail "证书 SAN 无效：$item"
    fi
    index=$((index + 1))
  done
  [ "$index" -gt 1 ] || fail "至少需要一个 IP 或域名 SAN"
}

generate_certificates() {
  local ca_dir="$DEPLOY_ROOT/certificates/ca" work common_name sans years days serial
  common_name="$(prompt_value '根证书名称（CN）' 'Xianyu Offline Root CA')"
  case "$common_name" in
    ''|*'/'*|*$'\n'*) fail "根证书名称不能留空，也不能包含 / 或换行" ;;
  esac
  read -r -p '网站证书包含的 IP/域名（多个使用英文逗号分隔）: ' sans
  [ -n "$sans" ] || fail "必须提供证书 IP 或域名"
  years="$(prompt_value '网站证书有效期（1、3、5 或 10 年）' '10')"
  case "$years" in
    1) days=365 ;;
    3) days=1095 ;;
    5) days=1825 ;;
    10) days=3650 ;;
    *) fail "网站证书有效期只支持 1、3、5、10 年，最长 10 年" ;;
  esac
  local x509_help
  x509_help="$(openssl x509 -help 2>&1 || true)"
  grep -q -- '-not_after' <<< "$x509_help" ||
    fail "当前 OpenSSL 不支持精确设置 9999 年根证书，请升级 OpenSSL 3.x"
  if [ -s "$ca_dir/private/root-ca.key" ]; then
    confirm "现有内部 CA 将被替换，是否继续？" || return 0
  fi

  work="$(mktemp -d "${TMPDIR:-/tmp}/xianyu-cert.XXXXXX")"
  trap 'rm -rf -- "$work"' RETURN
  umask 077
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out "$work/root-ca.key"
  openssl req -new -sha384 -key "$work/root-ca.key" -out "$work/root-ca.csr" \
    -subj "/CN=$common_name"
  cat > "$work/root.ext" <<'EOF'
[root_ca]
basicConstraints = critical, CA:true
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
EOF
  openssl x509 -req -sha384 -in "$work/root-ca.csr" \
    -signkey "$work/root-ca.key" -set_serial 0x01 \
    -not_after 99991231235959Z -extfile "$work/root.ext" -extensions root_ca \
    -out "$work/root-ca.crt"

  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out "$work/intermediate-ca.key"
  openssl req -new -sha384 -key "$work/intermediate-ca.key" \
    -out "$work/intermediate-ca.csr" -subj "/CN=$common_name Intermediate CA"
  cat > "$work/intermediate.ext" <<'EOF'
[intermediate_ca]
basicConstraints = critical, CA:true, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
EOF
  serial="0x$(openssl rand -hex 16)"
  openssl x509 -req -sha384 -in "$work/intermediate-ca.csr" \
    -CA "$work/root-ca.crt" -CAkey "$work/root-ca.key" -set_serial "$serial" \
    -days 7300 -extfile "$work/intermediate.ext" -extensions intermediate_ca \
    -out "$work/intermediate-ca.crt"

  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$work/site.key"
  openssl req -new -sha256 -key "$work/site.key" -out "$work/site.csr" \
    -subj "/CN=${sans%%,*}"
  {
    printf '[server_cert]\n'
    printf 'basicConstraints = critical, CA:false\n'
    printf 'keyUsage = critical, digitalSignature, keyEncipherment\n'
    printf 'extendedKeyUsage = serverAuth\n'
    printf 'subjectKeyIdentifier = hash\n'
    printf 'authorityKeyIdentifier = keyid,issuer\n'
    printf 'subjectAltName = @alt_names\n\n[alt_names]\n'
    san_extension "$sans"
  } > "$work/site.ext"
  serial="0x$(openssl rand -hex 16)"
  openssl x509 -req -sha256 -in "$work/site.csr" \
    -CA "$work/intermediate-ca.crt" -CAkey "$work/intermediate-ca.key" \
    -set_serial "$serial" -days "$days" \
    -extfile "$work/site.ext" -extensions server_cert -out "$work/site.crt"
  cat "$work/site.crt" "$work/intermediate-ca.crt" > "$work/fullchain.pem"
  openssl verify -CAfile "$work/root-ca.crt" -untrusted "$work/intermediate-ca.crt" \
    "$work/site.crt" >/dev/null || fail "生成的网站证书链验证失败"

  install -m 600 "$work/root-ca.key" "$ca_dir/private/root-ca.key"
  install -m 600 "$work/intermediate-ca.key" "$ca_dir/private/intermediate-ca.key"
  install -m 644 "$work/root-ca.crt" "$ca_dir/certs/root-ca.crt"
  install -m 644 "$work/intermediate-ca.crt" "$ca_dir/certs/intermediate-ca.crt"
  import_root_certificate "$work/root-ca.crt"
  install_site_certificate xianyu "$work/fullchain.pem" "$work/site.key"
  install_site_certificate chatwoot "$work/fullchain.pem" "$work/site.key"
  rm -rf -- "$work"
  trap - RETURN
  success "证书已生成：根证书固定到 9999-12-31，网站证书为 $years 年"
  warn "根 CA 私钥只保存在 $ca_dir/private，未挂载到任何容器，请离线备份。"
}

prompt_existing_file() {
  local prompt="$1" value
  read -r -p "$prompt: " value
  [ -f "$value" ] || fail "文件不存在：$value"
  printf '%s\n' "$value"
}

manual_certificate_import() {
  local root fullchain key choice
  if confirm "是否导入内部根证书供容器信任？"; then
    root="$(prompt_existing_file '根证书 PEM/CRT 路径')"
    import_root_certificate "$root"
  else
    refresh_combined_ca
  fi
  printf '  1) 同一张网站证书同时用于闲鱼平台和 Chatwoot\n'
  printf '  2) 两个站点分别导入证书\n'
  read -r -p '请选择 [1]: ' choice
  choice="${choice:-1}"
  if [ "$choice" = 1 ]; then
    fullchain="$(prompt_existing_file '网站完整证书链 fullchain.pem 路径')"
    key="$(prompt_existing_file '网站私钥 privkey.pem 路径')"
    install_site_certificate xianyu "$fullchain" "$key"
    install_site_certificate chatwoot "$fullchain" "$key"
  elif [ "$choice" = 2 ]; then
    fullchain="$(prompt_existing_file '闲鱼平台 fullchain.pem 路径')"
    key="$(prompt_existing_file '闲鱼平台 privkey.pem 路径')"
    install_site_certificate xianyu "$fullchain" "$key"
    fullchain="$(prompt_existing_file 'Chatwoot fullchain.pem 路径')"
    key="$(prompt_existing_file 'Chatwoot privkey.pem 路径')"
    install_site_certificate chatwoot "$fullchain" "$key"
  else
    fail "选择无效"
  fi
}

certificate_ready() {
  [ -s "$DEPLOY_ROOT/certificates/xianyu/fullchain.pem" ] &&
    [ -s "$DEPLOY_ROOT/certificates/xianyu/privkey.pem" ] &&
    [ -s "$DEPLOY_ROOT/certificates/chatwoot/fullchain.pem" ] &&
    [ -s "$DEPLOY_ROOT/certificates/chatwoot/privkey.pem" ] &&
    [ -s "$DEPLOY_ROOT/certificates/trust/combined-ca.pem" ]
}

initial_certificate_setup() {
  local choice
  printf '\n证书配置：\n'
  printf '  1) 使用 OpenSSL 自动生成内部 CA 和网站证书\n'
  printf '  2) 手动导入根证书和网站证书\n'
  read -r -p '请选择 [1]: ' choice
  case "${choice:-1}" in
    1) generate_certificates ;;
    2) manual_certificate_import ;;
    *) fail "选择无效" ;;
  esac
}

certificate_management() {
  local choice root fullchain key
  ensure_layout
  printf '\n证书管理：\n'
  printf '  1) 自动生成并替换内部 CA/网站证书\n'
  printf '  2) 单独导入根证书\n'
  printf '  3) 单独更新闲鱼平台网站证书\n'
  printf '  4) 单独更新 Chatwoot 网站证书\n'
  printf '  5) 查看证书有效期和 SAN\n'
  printf '  0) 返回\n'
  read -r -p '请选择: ' choice
  case "$choice" in
    1) generate_certificates ;;
    2)
      root="$(prompt_existing_file '根证书 PEM/CRT 路径')"
      import_root_certificate "$root"
      ;;
    3)
      fullchain="$(prompt_existing_file '闲鱼平台 fullchain.pem 路径')"
      key="$(prompt_existing_file '闲鱼平台 privkey.pem 路径')"
      install_site_certificate xianyu "$fullchain" "$key"
      ;;
    4)
      fullchain="$(prompt_existing_file 'Chatwoot fullchain.pem 路径')"
      key="$(prompt_existing_file 'Chatwoot privkey.pem 路径')"
      install_site_certificate chatwoot "$fullchain" "$key"
      ;;
    5)
      for fullchain in "$DEPLOY_ROOT/certificates/xianyu/fullchain.pem" \
        "$DEPLOY_ROOT/certificates/chatwoot/fullchain.pem" \
        "$DEPLOY_ROOT/certificates/trust/internal-root.crt"; do
        if [ -f "$fullchain" ]; then
          printf '\n%s\n' "$fullchain"
          openssl x509 -in "$fullchain" -noout -subject -issuer -dates -ext subjectAltName 2>/dev/null || true
        fi
      done
      ;;
    0) return 0 ;;
    *) fail "选择无效" ;;
  esac
  if [ -n "$(current_version)" ] && compose ps --status running -q 2>/dev/null | grep -q .; then
    if confirm "证书已更新，是否立即重启 HTTPS 网关？"; then
      compose restart gateway
      if [ "$(read_config_value COMPOSE_PROFILES || true)" = chatwoot ]; then
        compose restart chatwoot-gateway
      fi
    fi
  fi
}

start_stack() {
  certificate_ready || fail "证书配置不完整，请先进入“证书管理”"
  ensure_chatwoot_secrets
  verify_runtime_images
  info "正在启动当前版本；Compose 只使用脚本已准备好的本地镜像"
  compose up -d --wait --remove-orphans
  success "服务已启动"
  printf '闲鱼管理平台：%s\n' "$(read_config_value XIANYU_PUBLIC_BASE_URL)"
  if [ "$(read_config_value COMPOSE_PROFILES)" = chatwoot ]; then
    printf 'Chatwoot：%s\n' "$(read_config_value CHATWOOT_PUBLIC_BASE_URL)"
  fi
}

stop_stack() {
  compose --profile chatwoot stop
  success "服务已停止，数据和配置均已保留"
}

upgrade_stack() {
  local package before after
  package="$(select_package)"
  before="$(current_version)"
  printf '当前版本：%s\n' "${before:-未安装}"
  printf '选择文件：%s\n' "$(basename -- "$package")"
  confirm "确认导入并切换到此版本？现有数据、配置、证书和密钥不会被修改。" || return 0
  import_package "$package" true
  after="$(current_version)"
  if [ -f "$DEPLOY_ROOT/config/deployment.env" ] && certificate_ready; then
    ensure_chatwoot_secrets
    verify_runtime_images
    compose up -d --wait --remove-orphans
    success "已从 ${before:-未安装} 升级到 $after"
  else
    success "版本 $after 已安装；完成配置和证书后即可启动"
  fi
}

import_only() {
  local package
  package="$(select_package)"
  confirm "只导入镜像和版本文件，不切换当前运行版本？" || return 0
  import_package "$package" false
}

first_deployment() {
  local package
  [ -z "$(current_version)" ] || fail "已经存在部署，请使用“安装/升级版本包”"
  printf '\n首次部署会在脚本同级创建 XIANYU_DATA，导入本项目镜像并启动服务。\n'
  printf '官方依赖镜像可选择在线拉取或从本地官方镜像包导入。\n'
  printf 'Compose 项目和容器统一使用固定的 xianyu 名称。\n\n'
  printf '数据目录：%s\n' "$DEPLOY_ROOT"
  confirm "确认开始首次部署？" || return 0
  ensure_layout
  package="$(select_package)"
  import_package "$package" true
  configure_deployment
  prepare_dependency_images
  ensure_chatwoot_secrets
  initial_certificate_setup
  start_stack
}

dependency_image_management() {
  [ -f "$DEPLOY_ROOT/config/deployment.env" ] || fail "请先完成首次部署配置"
  prepare_dependency_images
  if [ -n "$(current_version)" ] && compose ps --status running -q 2>/dev/null | grep -q .; then
    if confirm "依赖镜像已更新，是否立即重建相关容器？"; then
      compose up -d --wait --remove-orphans
      success "官方依赖容器已更新"
    fi
  fi
}

show_status() {
  printf '部署目录：%s\n' "$DEPLOY_ROOT"
  printf '当前版本：%s\n' "$(current_version || true)"
  if [ -n "$(current_version)" ]; then
    compose ps
  fi
}

show_help() {
  cat <<'EOF'
用法：./开始部署.sh

将本脚本、compose.all.yml、本项目 Docker 镜像压缩包及其 .sha256 放在同一目录后执行。
数据固定保存在同级 XIANYU_DATA。官方依赖镜像支持在线拉取或本地归档导入。

可选参数：
  --help    显示帮助
  --check   检查脚本语法和版本包命名，不改动系统
EOF
}

self_check() {
  local package count=0
  bash -n "$0"
  while IFS= read -r package; do
    [ -n "$package" ] || continue
    count=$((count + 1))
    case "$(basename -- "$package")" in
      xianyu-admin-[A-Za-z0-9]*-linux-amd64.docker.tar.gz) ;;
      *) fail "版本包命名不正确：$package" ;;
    esac
  done < <(list_packages)
  success "脚本检查通过；同级目录发现 $count 个版本包"
}

main_menu() {
  local choice
  while true; do
    printf '\n========================================\n'
    printf ' 闲鱼管理平台 · Docker 部署\n'
    printf ' 数据目录：%s\n' "$DEPLOY_ROOT"
    printf ' 当前版本：%s\n' "$(current_version || true)"
    printf '========================================\n'
    printf '  1) 首次部署\n'
    printf '  2) 启动服务\n'
    printf '  3) 停止服务\n'
    printf '  4) 重启服务\n'
    printf '  5) 查看状态\n'
    printf '  6) 查看日志\n'
    printf '  7) 安装/升级版本包\n'
    printf '  8) 只导入版本包\n'
    printf '  9) 修改端口和 URL 配置\n'
    printf ' 10) 证书管理\n'
    printf ' 11) 官方依赖镜像管理\n'
    printf '  0) 退出\n'
    read -r -p '请选择: ' choice
    case "$choice" in
      1) first_deployment ;;
      2) start_stack ;;
      3) stop_stack ;;
      4) compose restart && success "服务已重启" ;;
      5) show_status ;;
      6) compose logs -f --tail=200 ;;
      7) ensure_layout; upgrade_stack ;;
      8) ensure_layout; import_only ;;
      9) ensure_layout; configure_deployment ;;
      10) certificate_management ;;
      11) ensure_layout; dependency_image_management ;;
      0) exit 0 ;;
      *) warn "选择无效" ;;
    esac
    pause
  done
}

case "${1:-}" in
  --help|-h) show_help; exit 0 ;;
  --check) self_check; exit 0 ;;
  '') ;;
  *) show_help; exit 2 ;;
esac

ensure_dependencies
main_menu
