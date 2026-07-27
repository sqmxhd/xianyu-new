#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
chatwoot_version="${CHATWOOT_VERSION:-v4.16.0}"
image_name="${CHATWOOT_IMAGE:-xianyu/chatwoot:4.16.0-no-outbound-audio}"
build_dir="$(mktemp -d -t xianyu-chatwoot-build.XXXXXX)"

cleanup() {
  if [[ -n "${build_dir:-}" && "$build_dir" == /tmp/xianyu-chatwoot-build.* ]]; then
    rm -rf -- "$build_dir"
  fi
}
trap cleanup EXIT

git clone \
  --depth 1 \
  --branch "$chatwoot_version" \
  https://github.com/chatwoot/chatwoot.git \
  "$build_dir/chatwoot"

git -C "$build_dir/chatwoot" apply \
  "$script_dir/patches/0001-disable-api-inbox-outbound-audio.patch"
git -C "$build_dir/chatwoot" apply \
  "$script_dir/patches/0002-add-xianyu-message-recall.patch"

docker build \
  --file "$build_dir/chatwoot/docker/Dockerfile" \
  --tag "$image_name" \
  "$build_dir/chatwoot"

echo "Built $image_name"
