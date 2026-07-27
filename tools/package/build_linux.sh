#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"

if [[ ! -f apps/admin/dist/index.html ]]; then
  npm --prefix apps/admin ci
  npm --prefix apps/admin run build
fi

build_venv="$project_root/artifacts/.package-venv-linux"
python3 -m venv "$build_venv"
"$build_venv/bin/python" -m pip install --upgrade pip
"$build_venv/bin/python" -m pip install \
  -r apps/api/requirements.txt \
  -r integrations/xianyu_core/requirements.txt \
  -r tools/package/requirements.txt
"$build_venv/bin/python" tools/package/build.py --platform linux-x64
