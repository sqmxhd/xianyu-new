#!/usr/bin/env bash

set -Eeuo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
project_root="$(cd "$(dirname "$script_path")/.." && pwd)"
runtime_dir="${XIANYU_SERVICE_RUNTIME_DIR:-$project_root/data/service-runtime}"
log_dir="${XIANYU_SERVICE_LOG_DIR:-$project_root/data/logs}"
lock_file="$runtime_dir/services.lock"
health_url="${XIANYU_SERVICE_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
health_interval="${XIANYU_SERVICE_HEALTH_INTERVAL_SECONDS:-10}"
health_timeout="${XIANYU_SERVICE_HEALTH_TIMEOUT_SECONDS:-3}"
health_failures_before_restart="${XIANYU_SERVICE_HEALTH_FAILURES_BEFORE_RESTART:-3}"
api_start_grace="${XIANYU_SERVICE_API_START_GRACE_SECONDS:-45}"
stop_timeout="${XIANYU_SERVICE_STOP_TIMEOUT_SECONDS:-20}"
log_max_bytes="${XIANYU_SERVICE_LOG_MAX_BYTES:-20971520}"
log_keep_files="${XIANYU_SERVICE_LOG_KEEP_FILES:-5}"

mkdir -p "$runtime_dir" "$log_dir"

usage() {
  cat <<'EOF'
usage: tools/manage_services.sh COMMAND [SERVICE]

Commands:
  start                 Start API, worker, and the health watchdog.
  stop                  Stop the watchdog, API, and worker.
  restart               Restart all managed services.
  status                Show process and API liveness status.
  start-one SERVICE     Start api, worker, or watchdog.
  stop-one SERVICE      Stop api, worker, or watchdog.
  restart-one SERVICE   Restart api, worker, or watchdog.
  watchdog-loop         Internal watchdog loop.
  watchdog-check        Run one internal health and log-rotation check.
EOF
}

require_service_name() {
  case "${1:-}" in
    api | worker | watchdog) ;;
    *)
      printf 'unknown service: %s\n' "${1:-<missing>}" >&2
      exit 2
      ;;
  esac
}

pid_file_for() {
  printf '%s/%s.pid\n' "$runtime_dir" "$1"
}

started_file_for() {
  printf '%s/%s.started\n' "$runtime_dir" "$1"
}

failure_file_for() {
  printf '%s/%s.health-failures\n' "$runtime_dir" "$1"
}

log_file_for() {
  printf '%s/%s.log\n' "$log_dir" "$1"
}

read_service_pid() {
  local service="$1"
  local pid_file
  local pid
  pid_file="$(pid_file_for "$service")"
  [[ -r "$pid_file" ]] || return 1
  read -r pid <"$pid_file" || return 1
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  printf '%s\n' "$pid"
}

expected_command_fragment() {
  case "$1" in
    api) printf '%s\n' 'npm run start:api' ;;
    worker) printf '%s\n' 'npm run start:worker' ;;
    watchdog) printf '%s\n' 'manage_services.sh watchdog-loop' ;;
  esac
}

service_is_running() {
  local service="$1"
  local pid
  local command_line
  local expected
  pid="$(read_service_pid "$service" 2>/dev/null)" || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  expected="$(expected_command_fragment "$service")"
  [[ "$command_line" == *"$expected"* ]]
}

log_event() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

rotate_log_locked() {
  local service="$1"
  local log_file
  local size
  local index
  log_file="$(log_file_for "$service")"
  [[ -f "$log_file" ]] || return 0
  size="$(stat -c '%s' "$log_file" 2>/dev/null || printf '0')"
  [[ "$size" =~ ^[0-9]+$ ]] || return 0
  (( size >= log_max_bytes )) || return 0

  rm -f "$log_file.$log_keep_files.gz"
  for ((index = log_keep_files - 1; index >= 1; index--)); do
    if [[ -f "$log_file.$index.gz" ]]; then
      mv "$log_file.$index.gz" "$log_file.$((index + 1)).gz"
    fi
  done
  cp --preserve=mode,timestamps "$log_file" "$log_file.1"
  truncate -s 0 "$log_file"
  gzip -f "$log_file.1"
  log_event "rotated $service log at $size bytes"
}

start_service_locked() {
  local service="$1"
  local pid_file
  local started_file
  local log_file
  local pid
  local launcher_pid
  local -a command
  require_service_name "$service"

  if service_is_running "$service"; then
    printf '%s already running (pid %s)\n' "$service" "$(read_service_pid "$service")"
    return 0
  fi

  pid_file="$(pid_file_for "$service")"
  started_file="$(started_file_for "$service")"
  log_file="$(log_file_for "$service")"
  rm -f "$pid_file" "$started_file" "$(failure_file_for "$service")"
  rotate_log_locked "$service"

  case "$service" in
    api)
      command=(npm run start:api)
      ;;
    worker)
      command=(npm run start:worker)
      ;;
    watchdog)
      command=(bash "$script_path" watchdog-loop)
      ;;
  esac

  (
    cd "$project_root"
    umask 027
    exec nohup setsid bash -c '
      pid_file="$1"
      shift
      printf "%s\n" "$$" >"$pid_file"
      exec env PYTHONUNBUFFERED=1 "$@"
    ' xianyu-service-launcher "$pid_file" "${command[@]}"
  ) 9>&- </dev/null >>"$log_file" 2>&1 &
  launcher_pid=$!

  for _ in $(seq 1 20); do
    [[ -s "$pid_file" ]] && break
    kill -0 "$launcher_pid" 2>/dev/null || break
    sleep 0.05
  done
  pid="$(read_service_pid "$service" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    printf 'failed to record %s pid; inspect %s\n' "$service" "$log_file" >&2
    return 1
  fi
  date +%s >"$started_file"
  for _ in $(seq 1 50); do
    service_is_running "$service" && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  if ! service_is_running "$service"; then
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file" "$started_file"
    printf 'failed to start %s; inspect %s\n' "$service" "$log_file" >&2
    return 1
  fi
  printf '%s started (pid %s, log %s)\n' "$service" "$pid" "$log_file"
}

stop_service_locked() {
  local service="$1"
  local pid
  local sid
  local deadline
  require_service_name "$service"

  if ! service_is_running "$service"; then
    rm -f "$(pid_file_for "$service")" "$(started_file_for "$service")" \
      "$(failure_file_for "$service")"
    printf '%s is not running\n' "$service"
    return 0
  fi

  pid="$(read_service_pid "$service")"
  sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
  if [[ "$sid" == "$pid" ]]; then
    kill -TERM -- "-$pid" 2>/dev/null || true
  else
    kill -TERM "$pid" 2>/dev/null || true
  fi

  deadline=$((SECONDS + stop_timeout))
  while kill -0 "$pid" 2>/dev/null && (( SECONDS < deadline )); do
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    log_event "$service did not stop within ${stop_timeout}s; sending SIGKILL"
    if [[ "$sid" == "$pid" ]]; then
      kill -KILL -- "-$pid" 2>/dev/null || true
    else
      kill -KILL "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$(pid_file_for "$service")" "$(started_file_for "$service")" \
    "$(failure_file_for "$service")"
  printf '%s stopped\n' "$service"
}

restart_service_locked() {
  local service="$1"
  stop_service_locked "$service"
  start_service_locked "$service"
}

start_all_locked() {
  start_service_locked api
  start_service_locked worker
  start_service_locked watchdog
}

stop_all_locked() {
  stop_service_locked watchdog
  stop_service_locked api
  stop_service_locked worker
}

restart_all_locked() {
  stop_service_locked watchdog
  stop_service_locked api
  stop_service_locked worker
  start_service_locked api
  start_service_locked worker
  start_service_locked watchdog
}

service_in_start_grace() {
  local service="$1"
  local started_file
  local started_at
  local now
  started_file="$(started_file_for "$service")"
  [[ -r "$started_file" ]] || return 1
  read -r started_at <"$started_file" || return 1
  [[ "$started_at" =~ ^[0-9]+$ ]] || return 1
  now="$(date +%s)"
  (( now - started_at < api_start_grace ))
}

record_api_health_success_locked() {
  printf '0\n' >"$(failure_file_for api)"
}

record_api_health_failure_locked() {
  local failure_file
  local failures=0
  failure_file="$(failure_file_for api)"
  if [[ -r "$failure_file" ]]; then
    read -r failures <"$failure_file" || failures=0
  fi
  [[ "$failures" =~ ^[0-9]+$ ]] || failures=0
  failures=$((failures + 1))
  printf '%s\n' "$failures" >"$failure_file"
  log_event "API liveness check failed ($failures/$health_failures_before_restart)"
  if (( failures >= health_failures_before_restart )); then
    log_event "API is unresponsive; restarting only the API service"
    restart_service_locked api
    record_api_health_success_locked
  fi
}

watchdog_check_locked() {
  local service

  if ! service_is_running api; then
    if service_in_start_grace api; then
      record_api_health_success_locked
    else
      log_event "API process is not running; starting it"
      start_service_locked api
    fi
  elif service_in_start_grace api; then
    record_api_health_success_locked
  elif curl --fail --silent --show-error \
    --connect-timeout 1 \
    --max-time "$health_timeout" \
    --output /dev/null \
    "$health_url"; then
    record_api_health_success_locked
  else
    record_api_health_failure_locked
  fi

  if ! service_is_running worker; then
    if ! service_in_start_grace worker; then
      log_event "worker process is not running; starting it"
      start_service_locked worker
    fi
  fi

  for service in api worker watchdog; do
    rotate_log_locked "$service"
  done
}

status_locked() {
  local service
  local unhealthy=0
  local pid
  for service in api worker watchdog; do
    if service_is_running "$service"; then
      pid="$(read_service_pid "$service")"
      printf '%-8s running pid=%s log=%s\n' "$service" "$pid" "$(log_file_for "$service")"
    else
      printf '%-8s stopped\n' "$service"
      unhealthy=1
    fi
  done
  if curl --fail --silent --show-error \
    --connect-timeout 1 \
    --max-time "$health_timeout" \
    --output /dev/null \
    "$health_url"; then
    printf 'api      healthy url=%s\n' "$health_url"
  else
    printf 'api      unhealthy url=%s\n' "$health_url"
    unhealthy=1
  fi
  return "$unhealthy"
}

with_lock() {
  (
    flock -x 9
    "$@"
  ) 9>"$lock_file"
}

command_name="${1:-}"
case "$command_name" in
  start)
    with_lock start_all_locked
    ;;
  stop)
    with_lock stop_all_locked
    ;;
  restart)
    with_lock restart_all_locked
    ;;
  status)
    with_lock status_locked
    ;;
  start-one)
    require_service_name "${2:-}"
    with_lock start_service_locked "$2"
    ;;
  stop-one)
    require_service_name "${2:-}"
    with_lock stop_service_locked "$2"
    ;;
  restart-one)
    require_service_name "${2:-}"
    with_lock restart_service_locked "$2"
    ;;
  watchdog-check)
    with_lock watchdog_check_locked
    ;;
  watchdog-loop)
    trap 'exit 0' INT TERM HUP
    log_event "service watchdog started interval=${health_interval}s threshold=$health_failures_before_restart"
    while true; do
      "$script_path" watchdog-check || true
      sleep "$health_interval" &
      wait $! || true
    done
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
