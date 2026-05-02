#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT_MESSAGE="${INITIAL_COMMIT_MESSAGE:-Initial commit: TQuant trading platform}"
GIT_USER_NAME="${GIT_USER_NAME:-TQuant Automation}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-automation@local}"

cd "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git 未安装，无法自动创建首次提交。" >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init
fi

if git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Git 仓库已有提交，跳过首次提交。"
  exit 0
fi

if ! git config user.name >/dev/null 2>&1; then
  git config user.name "$GIT_USER_NAME"
fi

if ! git config user.email >/dev/null 2>&1; then
  git config user.email "$GIT_USER_EMAIL"
fi

git add -A

if git diff --cached --quiet; then
  echo "没有可提交内容，跳过首次提交。"
  exit 0
fi

git commit -m "$COMMIT_MESSAGE"
echo "首次 Git commit 已创建。"
