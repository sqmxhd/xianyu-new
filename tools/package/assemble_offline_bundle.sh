#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
release_version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
release_commit="${RELEASE_COMMIT:?RELEASE_COMMIT is required}"
image_archive_dir="${IMAGE_ARCHIVE_DIR:?IMAGE_ARCHIVE_DIR is required}"
output_dir="${OUTPUT_DIR:?OUTPUT_DIR is required}"

case "$release_version" in
  ''|[.-]*|*[!A-Za-z0-9_.-]*)
    printf 'Invalid release version: %s\n' "$release_version" >&2
    exit 1
    ;;
esac
[ "${#release_version}" -le 128 ] || {
  printf 'Release version is longer than 128 characters\n' >&2
  exit 1
}

required_images=(
  XIANYU_IMAGE
  MYSQL_IMAGE
  REDIS_IMAGE
  CHATWOOT_IMAGE
  CHATWOOT_POSTGRES_IMAGE
  CHATWOOT_REDIS_IMAGE
)
for name in "${required_images[@]}"; do
  [ -n "${!name:-}" ] || {
    printf '%s is required\n' "$name" >&2
    exit 1
  }
done

shopt -s nullglob
archives=("$image_archive_dir"/*.docker.tar.gz)
shopt -u nullglob
[ "${#archives[@]}" -eq 5 ] || {
  printf 'Expected 5 unique image archives, found %s\n' "${#archives[@]}" >&2
  exit 1
}

work="$(mktemp -d "${TMPDIR:-/tmp}/xianyu-bundle.XXXXXX")"
cleanup() {
  [ -n "${work:-}" ] && [ -d "$work" ] && rm -rf -- "$work"
}
trap cleanup EXIT
mkdir -p "$work/images" "$output_dir"
cp "$repo_root/compose.all.yml" "$work/compose.all.yml"
cp "${archives[@]}" "$work/images/"

{
  printf '# Machine-readable Compose environment; contains no deployment secrets.\n'
  printf 'PACKAGE_FORMAT=1\n'
  printf 'RELEASE_VERSION=%s\n' "$release_version"
  printf 'RELEASE_ARCH=linux-amd64\n'
  for name in "${required_images[@]}"; do
    printf '%s=%s\n' "$name" "${!name}"
  done
} > "$work/release.env"

cat > "$work/manifest.json" <<EOF
{
  "format": 1,
  "product": "xianyu",
  "version": "$release_version",
  "commit": "$release_commit",
  "architecture": "linux-amd64",
  "images": {
    "xianyu": "$XIANYU_IMAGE",
    "mysql": "$MYSQL_IMAGE",
    "redis": "$REDIS_IMAGE",
    "chatwoot": "$CHATWOOT_IMAGE",
    "chatwoot_postgres": "$CHATWOOT_POSTGRES_IMAGE",
    "chatwoot_redis": "$CHATWOOT_REDIS_IMAGE"
  }
}
EOF

(
  cd "$work"
  sha256sum compose.all.yml release.env manifest.json images/*.docker.tar.gz > SHA256SUMS
)

archive="$output_dir/xianyu-$release_version-linux-amd64.tar.gz"
tar -czf "$archive" -C "$work" \
  compose.all.yml release.env manifest.json SHA256SUMS images
(
  cd "$output_dir"
  sha256sum "$(basename -- "$archive")" > "$(basename -- "$archive").sha256"
)
install -m 755 "$repo_root/开始部署.sh" "$output_dir/开始部署.sh"
printf 'Created %s\n' "$archive"
