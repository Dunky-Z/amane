#!/usr/bin/env bash
# 一键构建生产镜像 amane-local:latest（源码 context = 本仓库根 Dockerfile）
#
# 用法:
#   ./scripts/build-docker.sh           # 仅构建
#   ./scripts/build-docker.sh --up      # 构建后 recreate 生产容器 amane
#   ./scripts/build-docker.sh --no-cache
#   ./scripts/build-docker.sh --up --no-cache
#
# 代理默认 http://192.168.31.220:7890；可用环境变量覆盖 HTTP_PROXY / HTTPS_PROXY / NO_PROXY。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="${COMPOSE_DIR:-/root/sharedfolder/docker-compose}"
IMAGE="${AMANE_IMAGE:-amane-local:latest}"
PROXY="${HTTP_PROXY:-${http_proxy:-http://192.168.31.220:7890}}"
DO_UP=0
BUILD_ARGS=()

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

for arg in "$@"; do
  case "$arg" in
    -h | --help) usage 0 ;;
    --up) DO_UP=1 ;;
    --no-cache) BUILD_ARGS+=(--no-cache) ;;
    *)
      echo "未知参数: $arg" >&2
      usage 1
      ;;
  esac
done

if [[ ! -f "$ROOT/Dockerfile" ]]; then
  echo "未找到 Dockerfile: $ROOT/Dockerfile" >&2
  exit 1
fi
if [[ ! -f "$COMPOSE_DIR/docker-compose.yml" ]]; then
  echo "未找到 compose: $COMPOSE_DIR/docker-compose.yml" >&2
  exit 1
fi

export HTTP_PROXY="$PROXY"
export HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-$PROXY}}"
export http_proxy="${http_proxy:-$HTTP_PROXY}"
export https_proxy="${https_proxy:-$HTTPS_PROXY}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1,mirrors.aliyun.com,registry.npmmirror.com,cdn.npmmirror.com,pypi.tuna.tsinghua.edu.cn,mirrors.cloud.tencent.com,docker.m.daocloud.io}"
export no_proxy="${no_proxy:-$NO_PROXY}"

echo "[build-docker] context=$ROOT"
echo "[build-docker] image=$IMAGE"
echo "[build-docker] proxy=$HTTP_PROXY"
echo "[build-docker] compose=$COMPOSE_DIR"

cd "$COMPOSE_DIR"
docker compose build "${BUILD_ARGS[@]}" amane

echo "[build-docker] 构建完成: $IMAGE"
docker image inspect "$IMAGE" --format 'Id={{.Id}} Created={{.Created}} Size={{.Size}}' 2>/dev/null \
  || docker images "$IMAGE" --format 'table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}'

if [[ "$DO_UP" -eq 1 ]]; then
  echo "[build-docker] recreate 容器 amane …"
  docker compose up -d --force-recreate --no-deps amane
  echo "[build-docker] Web: http://192.168.31.220:8800"
  echo "[build-docker] 健康检查: curl -sS http://127.0.0.1:8800/api/health"
  echo "[build-docker] 日志: docker logs -f amane"
else
  echo "[build-docker] 仅构建。若要替换运行中的生产容器:"
  echo "  $0 --up"
  echo "  或: cd $COMPOSE_DIR && docker compose up -d --force-recreate --no-deps amane"
fi
