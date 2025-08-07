# Telegramの风纪委员

**简单实用的 Telegram 入群验证 Bot**

**特点:** 入群大于 30 天的普通成员可以每小时使用一次 `/kick` 功能(只允许对入群小于 30 天的成员使用), 以防管理不在导致广告刷屏

**实例:** [@Shirai_Kuroko_Bot](https://t.me/Shirai_Kuroko_Bot)

**Q&A:**

> 为什么不使用更严格的入群验证?  
> 严格的入群验证也拦不住真人广告哥, 机器人广告哥用简单验证也能拦住  

> 为什么不加聊天记录审查?  
> 容易误封玩抽象的群友  

> 1小时用一次, 广告哥很多怎么办?  
> 找其他群友帮忙砍一刀.  

## 环境变量

将 `.env.example` 文件重命名为 `.env`

| 名称               | 描述                            | 默认值         |
|------------------|-------------------------------|-------------|
| `API_ID`         | 登录 https://my.telegram.org 获取 |             |
| `API_HASH`       | 登录 https://my.telegram.org 获取 |             |
| `BOT_TOKEN`      | 在 https://t.me/BotFather 获取   |             |
| `ADMIN`          | 管理员用户ID，多个用户用逗号分隔             |             |
| `PROXY`          | Bot 代理, 海外服务器不用填              |             |
| `REDIS_HOST`     | Redis 服务器地址                   | `localhost` |
| `REDIS_PORT`     | Redis 服务器端口                   | `6379`      |
| `REDIS_PASSWORD` | Redis 密码（如果有设置）               |             |
| `DEBUG`          | 调试模式开关，设置为 `true` 启用调试日志      | `false`     |

使用 docker-compose 部署可以不填写 redis 配置

## 开始部署

#### Docker (推荐):

**在项目根目录运行:**

```shell
docker compose up -d
```

#### 直接运行:

**在项目根目录运行:**

```shell
# 安装依赖
apt install python3-pip -y
pip install uv --break-system-packages
uv venv --python 3.12
uv sync
# 运行 Bot
uv run bot.py 
```

## 使用

私聊 Bot 发送指令 `/menu` 即可自动设置菜单

将 Bot 拉入群内并授权 `封禁用户` `删除消息` 权限
