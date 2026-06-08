#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

IMAGE_TAG="${IMAGE_TAG:-${GITHUB_SHA:-$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
PUSH_IMAGES=0
BUILD_GO_IMAGES=1
BUILD_APP_IMAGES=1
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.mysql.yml}"

log() {
  printf '[prebuilt-images] %s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage: scripts/build_prebuilt_images.sh [options]

Build local prebuilt images for cloud pull+restart deploys. It never deploys.

Options:
  --registry <prefix>   Registry/repository prefix, for example registry.example.com/tquant.
  --tag <tag>           Image tag. Defaults to GITHUB_SHA or local git short SHA.
  --push                Push tagged images after building. Default is local only.
  --app-only            Build only web and analytics images.
  --go-only             Build only Go service images.
  --compose-file <path> Compose file to use. Defaults to docker-compose.mysql.yml.
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      IMAGE_REGISTRY="${2:?missing registry prefix}"
      shift 2
      ;;
    --tag)
      IMAGE_TAG="${2:?missing image tag}"
      shift 2
      ;;
    --push)
      PUSH_IMAGES=1
      shift
      ;;
    --app-only)
      BUILD_APP_IMAGES=1
      BUILD_GO_IMAGES=0
      shift
      ;;
    --go-only)
      BUILD_APP_IMAGES=0
      BUILD_GO_IMAGES=1
      shift
      ;;
    --compose-file)
      COMPOSE_FILE="${2:?missing compose file}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      log "unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$IMAGE_REGISTRY" ]]; then
  log "IMAGE_REGISTRY or --registry is required"
  exit 2
fi

tag_image() {
  local local_image="$1"
  local remote_name="$2"
  local remote_ref="${IMAGE_REGISTRY}/${remote_name}:${IMAGE_TAG}"
  docker tag "$local_image" "$remote_ref"
  printf '%s=%s\n' "$3" "$remote_ref"
  if [[ "$PUSH_IMAGES" == "1" ]]; then
    docker push "$remote_ref"
  fi
}

cd "$ROOT_DIR"

if [[ "$BUILD_APP_IMAGES" == "1" ]]; then
  log "build app images"
  COMPOSE_BAKE=false docker compose -f "$COMPOSE_FILE" build app analytics-worker
  tag_image tquant-web:mysql tquant-web DEPLOY_PREBUILT_WEB_IMAGE_REF
  tag_image tquant-analytics:mysql tquant-analytics DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF
fi

if [[ "$BUILD_GO_IMAGES" == "1" ]]; then
  log "build go images"
  COMPOSE_BAKE=false docker compose -f "$COMPOSE_FILE" build go-bff-gateway go-market-read-service go-scan-worker
  tag_image tquant-go-bff:mysql tquant-go-bff DEPLOY_PREBUILT_GO_BFF_IMAGE_REF
  tag_image tquant-go-market-read:mysql tquant-go-market-read DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF
  tag_image tquant-go-scan-worker:mysql tquant-go-scan-worker DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF
fi

log "done push=${PUSH_IMAGES} tag=${IMAGE_TAG}"
