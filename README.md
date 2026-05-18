# Telegramの风纪委员

**简单实用的 Telegram 入群验证 Bot**

**特点:** 入群大于 30 天的普通成员可以每小时使用一次 `/kick` 功能(只允许对入群小于 30 天的成员使用), 以防管理不在导致广告刷屏

**实例:** [@Shirai_Kuroko_Bot](https://t.me/Shirai_Kuroko_Bot)

**Q&A:**

> 为什么不使用更严格的入群验证?  
> 严格的入群验证也拦不住真人广告哥, 机器人广告哥用简单验证也能拦住。

> 为什么不加聊天记录审查?  
> 容易误封玩抽象的群友。

> 广告哥很多怎么办?  
> 群友可以使用 `/kick` 帮忙处理；Bot 会删除 Redis 最近消息缓存中该广告用户的消息。

## 环境变量

将 `.env.example` 文件复制为 `.env`，并按需填写：

| 名称               | 描述                         | 默认值         |
|------------------|----------------------------|-------------|
| `BOT_TOKEN`      | 在 BotFather 获取的 Bot Token |             |
| `ADMINS`         | 管理员用户 ID，多个用户用逗号分隔       |             |
| `BOT_PROXY`      | Bot 代理，海外服务器不用填           |             |
| `REDIS_HOST`     | Redis 服务器地址                | `localhost` |
| `REDIS_PORT`     | Redis 服务器端口                | `6379`      |
| `REDIS_PASSWORD` | Redis 密码（如果有设置）            |             |
| `DEBUG`          | 调试模式开关，设置为 `true` 启用调试日志 | `false`     |

使用 `docker-compose` 部署可以不填写 Redis 配置。

## 开始部署

### Docker（推荐）

在项目根目录运行：

```shell
docker compose up -d
```

### 直接运行

在项目根目录运行：

```shell
uv sync
uv run bot.py
```

## 使用

私聊 Bot 发送指令 `/menu` 即可自动设置菜单

将 Bot 拉入群内并授权 `封禁用户` `删除消息` 权限
