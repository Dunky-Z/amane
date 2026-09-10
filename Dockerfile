# syntax=docker/dockerfile:1
# Amane 元数据管理服务
# 本机构建默认走国内包源; BuildKit / compose 注入 HTTP(S)_PROXY 拉取基础镜像与外网资源.

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1,::1,mirrors.aliyun.com,registry.npmmirror.com,cdn.npmmirror.com,pypi.tuna.tsinghua.edu.cn,mirrors.cloud.tencent.com
ARG APT_MIRROR=mirrors.aliyun.com
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# --- 前端构建阶段 ---
FROM node:26-slim AS web-builder
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG APT_MIRROR
ARG NPM_REGISTRY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    npm_config_registry=${NPM_REGISTRY}
WORKDIR /app/web
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list; \
    fi
RUN npm install -g pnpm@11
# pnpm-workspace.yaml 含 allowBuilds; 必须在 install 前拷入, 否则 ERR_PNPM_IGNORED_BUILDS
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ .
RUN pnpm build

# --- Python 依赖阶段 ---
FROM python:3.14-slim AS base
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG APT_MIRROR
ARG UV_INDEX_URL
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    UV_INDEX_URL=${UV_INDEX_URL} \
    UV_DEFAULT_INDEX=${UV_INDEX_URL}
WORKDIR /app
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list; \
    fi
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --no-dev --frozen --no-editable

# --- 最终镜像 ---
FROM base
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG APT_MIRROR
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}
# postgresql-client: r18.dev dump 导入走 psql -f 子进程 (见 docs/dev/crawlers.md). 不配 r18 时无害.
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY alembic.ini ./
COPY --from=web-builder /app/web/dist ./web/dist

EXPOSE 8000
VOLUME ["/data", "/media"]

ENV AMANE_DATA_DIR=/data
ENV AMANE_LOG_DIR=/data/logs
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_NO_SYNC=1
# 运行时不要继承构建代理
ENV HTTP_PROXY= \
    HTTPS_PROXY= \
    NO_PROXY= \
    http_proxy= \
    https_proxy= \
    no_proxy=

CMD ["python", "-m", "amane.server"]
