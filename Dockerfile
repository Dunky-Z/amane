# syntax=docker/dockerfile:1
# Amane 元数据管理服务
# 本机构建默认走国内包源; BuildKit / compose 注入 HTTP(S)_PROXY 拉取基础镜像与外网资源.

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1,::1,mirrors.aliyun.com,registry.npmmirror.com,cdn.npmmirror.com,pypi.tuna.tsinghua.edu.cn,mirrors.cloud.tencent.com
ARG APT_MIRROR=mirrors.aliyun.com
ARG NPM_REGISTRY=https://registry.npmmirror.com
# 清华源在本机 NO_PROXY 直连常超时; 阿里云可直连且 wheel 路径与 PyPI 一致
ARG UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG UV_FILES_MIRROR=https://mirrors.aliyun.com/pypi

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
ARG UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG UV_FILES_MIRROR=https://mirrors.aliyun.com/pypi
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
# 不依赖 ghcr.io（本机代理拉 ghcr 常 reset）; 用阿里云 PyPI 装 uv
RUN pip install --no-cache-dir -i "${UV_INDEX_URL}" uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# uv.lock 写死 files.pythonhosted.org; --frozen 会直拉该 URL, 经代理易超时
RUN sed -i "s|https://files.pythonhosted.org|${UV_FILES_MIRROR}|g" uv.lock \
    && uv sync --no-dev --frozen --no-editable

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
# libgomp1: 超分二进制的运行时依赖, Real-ESRGAN 与 waifu2x 都动态链接 libgomp.
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
    && apt-get install -y --no-install-recommends libgomp1 postgresql-client \
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
