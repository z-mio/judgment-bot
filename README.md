<div align="center">

# 🛡️ Telegramの风纪委员

**简单实用的 Telegram 入群验证 Bot**

[![Telegram](https://img.shields.io/badge/Telegram-@Shirai__Kuroko__Bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/Shirai_Kuroko_Bot)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Kurigram](https://img.shields.io/badge/Kurigram-MTProto-26A5E4?logo=telegram&logoColor=white)](https://github.com/KurimuzonAkuma/kurigram)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yaml)
[![License](https://img.shields.io/github/license/z-mio/judgment-bot)](LICENSE)

**简体中文** · [English](README.en.md) · [日本語](README.ja.md) · [Русский](README.ru.md)

</div>

---

## ✨ 功能

- 🧩 **入群验证**: 新成员先被禁言, 等 🥵 变成 😀 后点击完成验证; 超时或点错会被临时踢出 1 分钟, 管理员也可以点 ✅ / ❎ 手动处理
- 🏷️ **失败标记**: 验证失败或超时的用户会被标记 30 天, 期间发的消息会被自动删除, 直到重新验证通过
- 🔨 **群友协助击落**: 入群满 30 天的成员可以用 `/kick` 处理新进群的广告号, Bot 会封禁对方, 并清理最近 100 条消息里该用户发的内容
- 🚨 **防轰炸模式**: 检测到异常入群时自动开启, 期间新成员会被静默踢出, 不再发验证消息刷屏
- 🧹 **自动清理**: 自动删除入群 / 退群的服务消息和游客 Bot 的消息
- 💾 **状态持久化**: 验证会话存在 Redis 里, Bot 重启后会继续未完成的验证

## 📖 指令

| 指令 | 使用者 | 说明 |
| --- | --- | --- |
| `/kick` | 群友 / 管理员 | 回复广告消息使用, 击落发送者; 回复频道消息时封禁该频道（仅管理员） |
| `/unban <@用户名 \| ID>` | 管理员 | 解封用户, 并私聊通知对方 |
| `/raid [on \| off]` | 管理员 | 查看防轰炸模式状态和统计 / 手动开启 / 关闭 |
| `/start` · `/help` | 所有人 | 查看指令列表 |

<details>
<summary><b>🔨 /kick 使用限制</b></summary>

<br>

- 发起人需要入群满 30 天, 目标需要入群未满 30 天
- 冷却时间按发起人的入群天数分档, 入群越久冷却越短: 

  | 发起人入群天数 | 冷却时间 |
  | --- | --- |
  | ≥ 90 天 | 1 分钟 |
  | ≥ 60 天 | 30 分钟 |
  | ≥ 30 天 | 1 小时 |

- 管理员不受以上限制, 可以直接击落

</details>

<details>
<summary><b>🚨 防轰炸模式规则</b></summary>

<br>

| | 条件 |
| --- | --- |
| **自动开启** | 5 分钟内进群 ≥ 15 人, 且已出结果的 ≥ 10 人中通过率 ≤ 20%; **或** 1 分钟内进群 ≥ 20 人 |
| **开启期间** | 新成员被静默临时踢出 1 分钟, 并清理进行中的验证; 开启时群内发一条提示 |
| **自动关闭** | 已开启 ≥ 10 分钟, 且 5 分钟内进群 < 5 人 |
| **手动模式** | `/raid on` 开启后不会自动关闭, 需要 `/raid off` 手动关闭 |

</details>

## 🚀 快速开始

**1. 创建 Bot**: 通过 [@BotFather](https://t.me/BotFather) 创建 Bot, 拿到 `BOT_TOKEN`; 在 [my.telegram.org](https://my.telegram.org) 获取 `API_ID` 和 `API_HASH`

**2. 拉进群并授权**: 把 Bot 设为管理员, 至少给 **封禁用户** 和 **删除消息** 两项权限

**3. 配置并启动**

```shell
cp .env.example .env   # 填写配置, 见下方说明
docker compose up -d
```

<details>
<summary>不用 Docker? 从源码运行</summary>

<br>

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/), 以及一个可用的 Redis

```shell
uv sync
uv run bot.py
```

</details>

## ⚙️ 配置

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `API_ID` | Telegram API ID | **必填** |
| `API_HASH` | Telegram API Hash | **必填** |
| `BOT_TOKEN` | BotFather 给的 Bot Token | **必填** |
| `BOT_PROXY` | 代理地址, 海外服务器一般不用填 | 空 |
| `REDIS_HOST` | Redis 地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密码 | 空 |
| `DEBUG` | 设为 `true` 输出调试日志 | `false` |

> [!TIP]
> 用 `docker compose` 部署时, Redis 配置会自动注入, 一般不需要改

## 💬 FAQ

<details>
<summary><b>为什么不用更严格的入群验证?</b></summary>

<br>

再严格的验证也拦不住真人广告号; 而机器人广告号, 用简单的验证就能有效拦住

</details>

<details>
<summary><b>为什么不做聊天内容审查?</b></summary>

<br>

内容审查容易误伤正常群友, 尤其是玩梗、抽象或者语境复杂的消息

</details>

<details>
<summary><b>广告号太多处理不过来怎么办?</b></summary>

<br>

入群满 30 天的群友可以用 `/kick` 帮忙处理; 遇到批量进群刷屏, 防轰炸模式会自动开启

</details>

## 📄 License

[MIT](LICENSE) © 梓澪
