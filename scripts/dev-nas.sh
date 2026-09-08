#!/usr/bin/env bash
# NAS 二次开发启动：独立 data_dir，端口与生产 8800 分离
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/root/app/nodejs/bin:${HOME}/.local/bin:/usr/local/bin:${PATH}"
export http_proxy="${http_proxy:-http://192.168.31.220:7890}"
export https_proxy="${https_proxy:-http://192.168.31.220:7890}"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="${no_proxy:-127.0.0.1,localhost}"
export NO_PROXY="$no_proxy"
# 勿 export AMANE_HOST/AMANE_PORT：ColdSettings 会拒绝未知 AMANE_* 键
cd "$ROOT"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

mkdir -p /root/sharedfolder/appdata/amane-dev

echo "[dev-nas] data_dir=/root/sharedfolder/appdata/amane-dev"
echo "[dev-nas] API  http://192.168.31.220:${API_PORT}"
echo "[dev-nas] Web  http://192.168.31.220:${WEB_PORT}"
echo "[dev-nas] token: cat /root/sharedfolder/appdata/amane-dev/token"

uv run uvicorn amane.api.app:create_app --factory --reload --host 0.0.0.0 --port "$API_PORT" &
API_PID=$!
(cd web && pnpm exec vite --host 0.0.0.0 --port "$WEB_PORT") &
WEB_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait
