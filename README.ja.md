<div align="center">

# 🛡️ Telegramの风纪委员

**シンプルで実用的な Telegram 入室認証 Bot**

[![Telegram](https://img.shields.io/badge/Telegram-@Shirai__Kuroko__Bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/Shirai_Kuroko_Bot)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Kurigram](https://img.shields.io/badge/Kurigram-MTProto-26A5E4?logo=telegram&logoColor=white)](https://github.com/KurimuzonAkuma/kurigram)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yaml)
[![License](https://img.shields.io/github/license/z-mio/judgment-bot)](LICENSE)

[简体中文](README.md) · [English](README.en.md) · **日本語** · [Русский](README.ru.md)

</div>

---

> [!NOTE]
> Bot の返信は中国語です。認証メッセージのみ中国語と英語の 2 言語表示です。

## ✨ 機能

- 🧩 **入室認証**：新メンバーはまずミュートされ、🥵 が 😀 に変わってからクリックすると認証完了。タイムアウトや早押しの場合は 1 分間キックされます。管理者は ✅ / ❎ で手動処理も可能
- 🏷️ **失敗マーク**：認証に失敗またはタイムアウトしたユーザーは 30 日間マークされ、再認証に通るまで投稿は自動削除されます
- 🔨 **メンバーによるキック**：参加から 30 日以上のメンバーは `/kick` で新規参加のスパムアカウントを処理できます。Bot は対象を BAN し、直近 100 件の中からその投稿を削除します
- 🚨 **荒らし対策モード**：異常な参加を検知すると自動で有効化。新メンバーは無言でキックされ、認証メッセージでチャットが埋まるのを防ぎます
- 🧹 **自動クリーンアップ**：入退室のサービスメッセージとゲスト Bot のメッセージを自動削除
- 💾 **状態の永続化**：認証セッションは Redis に保存され、再起動後も途中の認証を続行します

## 📖 コマンド

| コマンド | 使用者 | 説明 |
| --- | --- | --- |
| `/kick` | メンバー / 管理者 | スパムメッセージに返信して送信者をキック。チャンネルのメッセージに返信するとそのチャンネルを BAN（管理者のみ） |
| `/unban <@ユーザー名 \| ID>` | 管理者 | BAN を解除し、本人に個別チャットで通知 |
| `/raid [on \| off]` | 管理者 | 荒らし対策モードの状態と統計を表示 / 手動で有効化 / 無効化 |
| `/start` · `/help` | 全員 | コマンド一覧を表示 |

<details>
<summary><b>🔨 /kick の制限</b></summary>

<br>

- 実行者は参加から 30 日以上、対象は参加から 30 日未満である必要があります
- クールダウンは実行者の参加日数で決まり、長いほど短くなります：

  | 実行者の参加日数 | クールダウン |
  | --- | --- |
  | ≥ 90 日 | 1 分 |
  | ≥ 60 日 | 30 分 |
  | ≥ 30 日 | 1 時間 |

- 管理者はこれらの制限を受けず、直接キックできます

</details>

<details>
<summary><b>🚨 荒らし対策モードのルール</b></summary>

<br>

| | 条件 |
| --- | --- |
| **自動で有効化** | 5 分間に 15 人以上が参加し、結果が出た 10 人以上の通過率が 20% 以下、**または** 1 分間に 20 人以上が参加 |
| **有効中** | 新メンバーを 1 分間無言でキックし、進行中の認証を片付けます。有効化時にグループへ通知を 1 件投稿 |
| **自動で無効化** | 有効化から 10 分以上経過し、直近 5 分間の参加が 5 人未満 |
| **手動モード** | `/raid on` で有効化した場合は自動で無効にならず、`/raid off` で無効化します |

</details>

## 🚀 クイックスタート

**1. Bot を作成**：[@BotFather](https://t.me/BotFather) で Bot を作成して `BOT_TOKEN` を取得し、[my.telegram.org](https://my.telegram.org) で `API_ID` と `API_HASH` を取得

**2. グループに追加して権限を付与**：Bot を管理者にし、少なくとも **ユーザーの BAN** と **メッセージの削除** の権限を与えます

**3. 設定して起動**

```shell
cp .env.example .env   # 下記の設定を記入
docker compose up -d
```

<details>
<summary>Docker を使わない場合（ソースから実行）</summary>

<br>

Python 3.12+、[uv](https://docs.astral.sh/uv/)、稼働中の Redis が必要です

```shell
uv sync
uv run bot.py
```

</details>

## ⚙️ 設定

| 変数 | 説明 | デフォルト |
| --- | --- | --- |
| `API_ID` | Telegram API ID | **必須** |
| `API_HASH` | Telegram API Hash | **必須** |
| `BOT_TOKEN` | BotFather で発行した Bot Token | **必須** |
| `ADMINS` | 管理者のユーザー ID、複数の場合は半角カンマ区切り | 空 |
| `BOT_PROXY` | プロキシ URL、海外サーバーでは通常不要 | 空 |
| `REDIS_HOST` | Redis のホスト | `localhost` |
| `REDIS_PORT` | Redis のポート | `6379` |
| `REDIS_PASSWORD` | Redis のパスワード | 空 |
| `DEBUG` | `true` でデバッグログを出力 | `false` |

> [!TIP]
> `docker compose` でデプロイする場合、Redis の設定は自動で注入されるため通常は変更不要です。

## 💬 FAQ

<details>
<summary><b>なぜもっと厳しい認証にしないのですか？</b></summary>

<br>

どれだけ厳しくしても人間のスパマーは防げません。一方、スパム Bot はシンプルな認証で十分に防げます。

</details>

<details>
<summary><b>なぜ投稿内容の審査をしないのですか？</b></summary>

<br>

内容の審査は普通のメンバーを巻き込みやすく、特にネタや文脈に依存するメッセージで誤判定が起きがちです。

</details>

<details>
<summary><b>スパムが多すぎて対応しきれない場合は？</b></summary>

<br>

参加から 30 日以上のメンバーが `/kick` で手伝えます。大量参加による荒らしには荒らし対策モードが自動で有効になります。

</details>

## 📄 License

[MIT](LICENSE) © 梓澪
