#!/usr/bin/env bash

set -euo pipefail

cloud_build_ssh_opts() {
  CLOUD_SSH_OPTS=(
    -o StrictHostKeyChecking=no
    -o ConnectTimeout="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"
    -o ConnectionAttempts="${CLOUD_SSH_CONNECTION_ATTEMPTS:-3}"
    -o ServerAliveInterval=30
    -o ServerAliveCountMax="${CLOUD_SSH_SERVER_ALIVE_COUNT_MAX:-120}"
  )
  if [[ -n "${CLOUD_SSH_KEY:-}" ]]; then
    CLOUD_SSH_OPTS+=(-i "$CLOUD_SSH_KEY")
  fi
}

cloud_ssh_target() {
  printf '%s@%s' "${CLOUD_USER:-ubuntu}" "${CLOUD_HOST:?CLOUD_HOST is required}"
}

cloud_ssh_transient_log() {
  local log_file="$1"
  grep -Eqi 'banner exchange|kex_exchange_identification|ssh_exchange_identification|Connection reset by peer|Connection closed|Connection timed out|Operation timed out|Broken pipe|No route to host|Network is unreachable' "$log_file"
}

cloud_ssh() {
  local target
  target="$(cloud_ssh_target)"
  local -a CLOUD_SSH_OPTS
  cloud_build_ssh_opts
  local attempts="${CLOUD_SSH_RETRY_ATTEMPTS:-6}"
  local retry_delay="${CLOUD_SSH_RETRY_DELAY_SECONDS:-5}"
  local attempt=1
  local status=0
  if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
    command -v expect >/dev/null || {
      echo "CLOUD_PASSWORD requires expect. Install expect or use CLOUD_SSH_KEY." >&2
      return 1
    }
  fi

  while (( attempt <= attempts )); do
    local log_file
    log_file="$(mktemp "/tmp/gupiao-ssh-retry-${attempt}.XXXXXX")"
    if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
      local remote_cmd="$*"
      if CLOUD_EXPECT_TARGET="$target" CLOUD_EXPECT_CMD="$remote_cmd" CLOUD_EXPECT_OPTS="${CLOUD_SSH_OPTS[*]}" expect >"$log_file" 2>&1 <<'EOF'
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
      then
        cat "$log_file"
        rm -f "$log_file"
        return 0
      fi
      status=$?
    elif ssh "${CLOUD_SSH_OPTS[@]}" "$target" "$@" >"$log_file" 2>&1; then
      cat "$log_file"
      rm -f "$log_file"
      return 0
    else
      status=$?
    fi

    cat "$log_file" >&2
    if (( attempt < attempts )) && cloud_ssh_transient_log "$log_file"; then
      echo "ssh transient connection failure; retrying attempt $((attempt + 1))/${attempts}" >&2
      rm -f "$log_file"
      sleep $((attempt * retry_delay))
      attempt=$((attempt + 1))
      continue
    fi
    rm -f "$log_file"
    return "$status"
  done
  return "$status"
}

cloud_scp_to() {
  local source="$1"
  local target_path="$2"
  local target
  target="$(cloud_ssh_target)"
  local -a CLOUD_SSH_OPTS
  cloud_build_ssh_opts
  local attempts="${CLOUD_SSH_RETRY_ATTEMPTS:-6}"
  local retry_delay="${CLOUD_SSH_RETRY_DELAY_SECONDS:-5}"
  local attempt=1
  local status=0
  if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
    command -v expect >/dev/null || {
      echo "CLOUD_PASSWORD requires expect. Install expect or use CLOUD_SSH_KEY." >&2
      return 1
    }
  fi

  while (( attempt <= attempts )); do
    local log_file
    log_file="$(mktemp "/tmp/gupiao-scp-retry-${attempt}.XXXXXX")"
    if [[ -n "${CLOUD_PASSWORD:-}" ]]; then
      if CLOUD_EXPECT_SOURCE="$source" CLOUD_EXPECT_DEST="${target}:${target_path}" CLOUD_EXPECT_OPTS="${CLOUD_SSH_OPTS[*]}" expect >"$log_file" 2>&1 <<'EOF'
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
      then
        cat "$log_file"
        rm -f "$log_file"
        return 0
      fi
      status=$?
    elif scp "${CLOUD_SSH_OPTS[@]}" "$source" "${target}:${target_path}" >"$log_file" 2>&1; then
      cat "$log_file"
      rm -f "$log_file"
      return 0
    else
      status=$?
    fi

    cat "$log_file" >&2
    if (( attempt < attempts )) && cloud_ssh_transient_log "$log_file"; then
      echo "ssh/scp transient connection failure; retrying attempt $((attempt + 1))/${attempts}" >&2
      rm -f "$log_file"
      sleep $((attempt * retry_delay))
      attempt=$((attempt + 1))
      continue
    fi
    rm -f "$log_file"
    return "$status"
  done
  return "$status"
}
