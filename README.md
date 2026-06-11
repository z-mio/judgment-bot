# 🛡️ Telegramの风纪委员

一个简单实用的 Telegram 入群验证 Bot, 用于降低广告用户进群刷屏带来的管理压力

**实例:** [@Shirai_Kuroko_Bot](https://t.me/Shirai_Kuroko_Bot)

---

## ✨ 功能简介

本项目主要解决两类问题:

### 1. 入群验证

- 对新入群用户进行基础验证
- 用简单验证拦截机器人广告号

### 2. 群友协助处理广告

- 入群超过 30 天的普通成员, 可以使用 `/kick` 协助处理广告用户
- `/kick` 每人每小时只能使用一次
- `/kick` 只能用于处理入群未满 30 天的新成员
- Bot 会删除最近 100 条消息中该用户发送的消息, 减少广告刷屏残留

---

## 🤔 为什么这样设计?

### 为什么不使用更严格的入群验证?

严格验证也很难拦住真人广告用户; 而机器人广告号通常用简单验证就能有效拦截

### 为什么不做聊天内容审查?

聊天内容审查容易误伤正常群友, 尤其是一些玩梗, 抽象或语境复杂的消息

### 广告用户很多怎么办?

入群超过 30 天的普通成员可以使用 `/kick` 协助处理; Bot 会封禁目标用户, 并删除最近 100 条消息中该用户发送的消息

---

## ⚙️ 使用前准备

### 1. 创建 Bot

在 Telegram 中通过 [@BotFather](https://t.me/BotFather) 创建 Bot, 并获取 `BOT_TOKEN`

### 2. 配置群权限

将 Bot 拉入群组后, 请授予以下权限:

- 封禁用户
- 删除消息

否则 Bot 无法正常处理广告用户或删除广告消息

### 3. 配置环境变量

复制 `.env.example` 为 `.env`:

```shell
cp .env.example .env
```

按需填写以下配置:

| 名称 | 描述 | 默认值 |
| --- | --- | --- |
| `API_ID` | Telegram API ID, 可在 my.telegram.org 获取 | 必填 |
| `API_HASH` | Telegram API Hash, 可在 my.telegram.org 获取 | 必填 |
| `BOT_TOKEN` | 在 BotFather 获取的 Bot Token | 必填 |
| `ADMINS` | 管理员用户 ID, 多个用户用英文逗号分隔 | 空 |
| `BOT_PROXY` | Bot 代理地址, 海外服务器通常不需要填写 | 空 |
| `REDIS_HOST` | Redis 服务器地址 | `localhost` |
| `REDIS_PORT` | Redis 服务器端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密码, 如果没有设置可以留空 | 空 |
| `DEBUG` | 调试模式, 设置为 `true` 启用调试日志 | `false` |

如果使用 `docker compose` 部署, 通常不需要手动填写 Redis 配置

---

## 🚀 运行方式

### Docker (推荐)

在项目根目录运行:

```shell
docker compose up -d
```

### 源码运行

在项目根目录中执行:

```shell
uv sync
uv run bot.py
```

---

## 📖 使用方式

### 设置菜单

私聊 Bot 发送: `/menu`

Bot 会自动设置指令菜单

### 处理广告用户

在群内对广告用户使用 `/kick` 指令

使用限制:

- 发起者必须是入群超过 30 天的普通成员
- 每个用户每小时只能使用一次
- 目标用户必须是入群未满 30 天的新成员
