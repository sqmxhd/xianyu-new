#!/usr/bin/env bash

set -uo pipefail

if [[ $# -eq 0 ]]; then
  printf 'usage: %s command [args...]\n' "$0" >&2
  exit 2
fi

restart_delay="${XIANYU_RESTART_DELAY_SECONDS:-3}"
stopping=0
child_pid=0

stop_child() {
  stopping=1
  if (( child_pid > 0 )) && kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM -- "-$child_pid" 2>/dev/null || kill -TERM "$child_pid" 2>/dev/null || true
  fi
}

trap stop_child INT TERM HUP

while (( stopping == 0 )); do
  setsid "$@" &
  child_pid=$!
  wait "$child_pid"
  exit_code=$?
  child_pid=0

  if (( stopping != 0 )); then
    break
  fi

  printf 'process exited with code %s; restarting in %ss: %s\n' \
    "$exit_code" "$restart_delay" "$*" >&2
  setsid sleep "$restart_delay" &
  child_pid=$!
  wait "$child_pid" || true
  child_pid=0
done

exit 0
