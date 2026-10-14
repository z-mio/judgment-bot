<div align="center">

# 🛡️ Telegramの风纪委员

**A simple and practical join verification bot for Telegram groups**

[![Telegram](https://img.shields.io/badge/Telegram-@Shirai__Kuroko__Bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/Shirai_Kuroko_Bot)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Kurigram](https://img.shields.io/badge/Kurigram-MTProto-26A5E4?logo=telegram&logoColor=white)](https://github.com/KurimuzonAkuma/kurigram)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yaml)
[![License](https://img.shields.io/github/license/z-mio/judgment-bot)](LICENSE)

[简体中文](README.md) · **English** · [日本語](README.ja.md) · [Русский](README.ru.md)

</div>

---

> [!NOTE]
> Bot replies are in Chinese. The verification prompt is bilingual (Chinese / English).

## ✨ Features

- 🧩 **Join verification**: new members are muted and must click 😀 once 🥵 turns into it. Timing out or clicking too early gets them kicked for 1 minute. Admins can also approve or reject manually with ✅ / ❎
- 🏷️ **Failure mark**: users who fail or time out are marked for 30 days. Their messages are deleted automatically until they pass verification
- 🔨 **Community kicks**: members who joined at least 30 days ago can use `/kick` on newly joined spammers. The bot bans the target and removes their messages from the last 100 messages
- 🚨 **Anti-raid mode**: turns on automatically when unusual join activity is detected. New members are kicked silently, so the bot stops flooding the chat with verification prompts
- 🧹 **Auto cleanup**: join / leave service messages and guest bot messages are deleted automatically
- 💾 **Persistent state**: verification sessions are stored in Redis and resume after a restart

## 📖 Commands

| Command | Who | Description |
| --- | --- | --- |
| `/kick` | Members / admins | Reply to a spam message to kick its sender. Replying to a channel message bans the channel (admins only) |
| `/unban <@username \| ID>` | Admins | Unban a user and notify them in private chat |
| `/raid [on \| off]` | Admins | Show anti-raid status and stats / turn it on manually / turn it off |
| `/start` · `/help` | Everyone | Show the command list |

<details>
<summary><b>🔨 /kick limits</b></summary>

<br>

- The caller must have joined at least 30 days ago, and the target less than 30 days ago
- The cooldown depends on how long the caller has been in the group:

  | Caller joined | Cooldown |
  | --- | --- |
  | ≥ 90 days | 1 minute |
  | ≥ 60 days | 30 minutes |
  | ≥ 30 days | 1 hour |

- Admins are not subject to these limits and kick directly

</details>

<details>
<summary><b>🚨 Anti-raid rules</b></summary>

<br>

| | Condition |
| --- | --- |
| **Auto on** | ≥ 15 joins in 5 minutes and a pass rate ≤ 20% among ≥ 10 finished verifications, **or** ≥ 20 joins in 1 minute |
| **While on** | New members are silently kicked for 1 minute and pending verifications are cleared. One notice is posted in the group when it turns on |
| **Auto off** | On for ≥ 10 minutes and < 5 joins in the last 5 minutes |
| **Manual** | Turned on with `/raid on`, never turns off automatically, use `/raid off` |

</details>

## 🚀 Quick Start

**1. Create a bot**: create one with [@BotFather](https://t.me/BotFather) to get `BOT_TOKEN`, and get `API_ID` / `API_HASH` from [my.telegram.org](https://my.telegram.org)

**2. Add it to your group**: make the bot an admin with at least the **Ban users** and **Delete messages** permissions

**3. Configure and start**

```shell
cp .env.example .env   # fill in the settings below
docker compose up -d
```

<details>
<summary>Not using Docker? Run from source</summary>

<br>

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and a running Redis

```shell
uv sync
uv run bot.py
```

</details>

## ⚙️ Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `API_ID` | Telegram API ID | **Required** |
| `API_HASH` | Telegram API Hash | **Required** |
| `BOT_TOKEN` | Bot token from BotFather | **Required** |
| `ADMINS` | Admin user IDs, comma separated | Empty |
| `BOT_PROXY` | Proxy URL, usually not needed on overseas servers | Empty |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password | Empty |
| `DEBUG` | Set to `true` for debug logs | `false` |

> [!TIP]
> With `docker compose`, the Redis settings are injected automatically and usually don't need changes.

## 💬 FAQ

<details>
<summary><b>Why not use a stricter verification?</b></summary>

<br>

No verification can stop human spammers, while spam bots are already stopped by a simple one.

</details>

<details>
<summary><b>Why no content moderation?</b></summary>

<br>

Content moderation easily hits regular members, especially memes, absurd humor and messages that depend on context.

</details>

<details>
<summary><b>Too many spammers to handle?</b></summary>

<br>

Members who joined at least 30 days ago can help with `/kick`. If accounts flood in, anti-raid mode turns on automatically.

</details>

## 📄 License

[MIT](LICENSE) © 梓澪
