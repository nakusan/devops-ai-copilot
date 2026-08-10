# 多阶段构建：uv 同步依赖 → 精简 Python 运行时（Phase 6 / W12）
#
# 同一镜像两种用途（Compose 用 command 覆盖）：
# - HTTP：uvicorn app.main:app
# - Worker：python -m app.worker
# 避免维护两份镜像，符合「API + Worker 同代码不同进程」业界形态。
# 注：不写 # syntax=docker/dockerfile:1，避免构建时强制拉取
# docker.io/docker/dockerfile（国内/受限网络常超时）。

# ---------- build ----------
FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv

WORKDIR /app

# 编译期可能需要（部分 wheel 无 manylinux 预编译时）
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# 先锁文件再装依赖，最大化层缓存
COPY pyproject.toml uv.lock README.md ./
# hatchling 打包需要 app/ 存在；先装依赖再装项目本身
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# curl：可选探活；MCP stdio Mock 只需 python 本进程
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/app /app/app
COPY --from=build /app/pyproject.toml /app/README.md /app/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# 默认跑 HTTP；Worker 服务在 compose 里覆盖 command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
