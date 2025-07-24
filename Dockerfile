FROM python:3.12-slim

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

WORKDIR /app

ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y \
    tzdata \
    gcc \
    python3-dev \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo "$TZ" > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

RUN uv venv && uv sync --frozen

CMD ["uv", "run", "bot.py"]
