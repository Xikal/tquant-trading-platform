#!/usr/bin/env bash

set -euo pipefail

cloud_build_ssh_opts() {
  CLOUD_SSH_OPTS=(
    -o StrictHostKeyChecking=no
    -o ConnectTimeout="${CLOUD_SSH_CONNECT_TIMEOUT:-10}"
    -o ServerAliveInterval=30
  )
  if [[ -n "${CLOUD_SSH_KEY:-}" ]]; then
    CLOUD_SSH_OPTS+=(-i "$CLOUD_SSH_KEY")
  fi
}

cloud_ssh_target() {
  printf '%s@%s' "${CLOUD_USER:-ubuntu}" "${CLOUD_HOST:?CLOUD_HOST is required}"
}

cloud_ssh() {
  local target
  target="$(cloud_ssh_target)"
  local -a CLOUD_SSH_OPTS
  cloud_build_ssh_opts
  if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
    command -v expect >/dev/null || {
      echo "CLOUD_PASSWORD requires expect. Install expect or use CLOUD_SSH_KEY." >&2
      return 1
    }
    local remote_cmd="$*"
    CLOUD_EXPECT_TARGET="$target" CLOUD_EXPECT_CMD="$remote_cmd" CLOUD_EXPECT_OPTS="${CLOUD_SSH_OPTS[*]}" expect <<'EOF'
set timeout [expr {[info exists env(CLOUD_SSH_TIMEOUT)] ? $env(CLOUD_SSH_TIMEOUT) : 900}]
set argv [concat [split $env(CLOUD_EXPECT_OPTS)] [list $env(CLOUD_EXPECT_TARGET) $env(CLOUD_EXPECT_CMD)]]
spawn ssh {*}$argv
expect {
  -re "(?i)password:" { send "$env(CLOUD_PASSWORD)\r"; exp_continue }
  eof
}
catch wait result
exit [lindex $result 3]
EOF
  else
    ssh "${CLOUD_SSH_OPTS[@]}" "$target" "$@"
  fi
}

cloud_scp_to() {
  local source="$1"
  local target_path="$2"
  local target
  target="$(cloud_ssh_target)"
  local -a CLOUD_SSH_OPTS
  cloud_build_ssh_opts
  if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
    command -v expect >/dev/null || {
      echo "CLOUD_PASSWORD requires expect. Install expect or use CLOUD_SSH_KEY." >&2
      return 1
    }
    CLOUD_EXPECT_SOURCE="$source" CLOUD_EXPECT_DEST="${target}:${target_path}" CLOUD_EXPECT_OPTS="${CLOUD_SSH_OPTS[*]}" expect <<'EOF'
set timeout [expr {[info exists env(CLOUD_SSH_TIMEOUT)] ? $env(CLOUD_SSH_TIMEOUT) : 300}]
set argv [concat [split $env(CLOUD_EXPECT_OPTS)] [list $env(CLOUD_EXPECT_SOURCE) $env(CLOUD_EXPECT_DEST)]]
spawn scp {*}$argv
expect {
  -re "(?i)password:" { send "$env(CLOUD_PASSWORD)\r"; exp_continue }
  eof
}
catch wait result
exit [lindex $result 3]
EOF
  else
    scp "${CLOUD_SSH_OPTS[@]}" "$source" "${target}:${target_path}"
  fi
}
