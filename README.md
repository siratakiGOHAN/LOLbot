# MetaVisionBOT — League of Legends マッチアップ統計 Discord Bot

ハイレートプレイヤー（Master以上）の試合データをもとに、チャンピオンごとのマッチアップ統計を提供する Discord Bot です。勝率・ピック率・BAN率・よく使われるビルドを確認することで、プレイヤー自身がメタを理解し、チャンピオンプールを改善するための参考情報として活用できます。

## 💡 開発背景と目的

趣味である『League of Legends』の戦術分析を、より手軽にDiscord上で行いたいと考え開発しました。

ただPythonの文法を学ぶだけでなく、**「実際の外部API（Riot API）との連携」「非同期処理による効率的なデータ収集」「データベースを用いた統計管理」「Dockerによるコンテナ化」**など、実戦的なバックエンド開発のスキルを習得・証明するためのポートフォリオとして制作しています。

## 機能

- **`/lol <チャンピオン> [レーン]`** — 指定チャンピオンに対するマッチアップ統計データを表示
  - マッチアップ勝率・ピック率・BAN率
  - よく使われるビルド（アイテム・キーストーンルーン）画像
  - YouTube 実際のマッチアップの動画へのリンク
- **チャンピオン名オートコンプリート** — 日本語・英語両対応
- **`/lolupdate`** — 管理者用：最新データに手動更新
- **`/lolpatch`** — 管理者用：パッチ後のキャッシュリセット

## スクリーンショット

### コマンド入力（オートコンプリート対応）
![command](https://raw.githubusercontent.com/siratakiGOHAN/LOLbot/main/docs/images/screenshot_command.png)

### マッチアップ統計一覧
![counter](https://raw.githubusercontent.com/siratakiGOHAN/LOLbot/main/docs/images/screenshot_counter.png)

### ビルド詳細（アイテム画像・キーストーン・勝率）
![build](https://raw.githubusercontent.com/siratakiGOHAN/LOLbot/main/docs/images/screenshot_build.png)

![build2](https://raw.githubusercontent.com/siratakiGOHAN/LOLbot/main/docs/images/screenshot_build2.png)

## 技術スタック

- Python 3.13
- discord.py v2.0（slash commands）
- aiohttp / aiosqlite
- Pillow（ビルド画像生成）
- Riot API v4/v5（League-V4, Match-V5, Summoner-V4）
- Data Dragon / CommunityDragon
- Docker / Docker Compose

## セットアップ

### 必要環境

- Docker & Docker Compose（推奨）または Python 3.13+
- Discord Bot Token
- Riot API Key

### 設定

`.env` ファイルをプロジェクトルートに作成：

```
DISCORD_BOT_TOKEN=your_discord_bot_token
RIOT_API_KEY=your_riot_api_key
```

### Docker で起動（推奨）

```bash
git clone https://github.com/siratakiGOHAN/LOLbot.git
cd LOLbot
# .env を作成後
docker compose up -d --build
```

ログ確認：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

データは `db/` と `data/` ディレクトリにボリューム保存されるため、コンテナを削除しても失われません。

### Python で直接起動（Docker を使わない場合）

```bash
git clone https://github.com/siratakiGOHAN/LOLbot.git
cd LOLbot
pip install -r requirements.txt
```

`.env` に `DB_PATH=lolbot.db` を追加後：

```bash
python main.py
```

### データ収集（手動実行する場合）

Docker 起動時は毎日自動で収集されます。手動で実行する場合：

```bash
# テスト収集（KR・5人・5試合）
python data_collector.py --test

# 本番収集（主要リージョン）
python data_collector.py --regions kr euw1 na1 jp1 --players 50 --matches 20
```

## データソース

Master以上のランクプレイヤーの試合データをRiot APIから収集し、SQLiteデータベースに蓄積します。データは毎日自動更新されます。

## プライバシーポリシー

本Botが収集するデータは、Riot APIから取得した公開試合統計（チャンピオンID・勝敗・アイテム・ルーン）のみです。Discord ユーザーの個人情報は一切収集・保存しません。

## ライセンス

League of Legends マッチアップ統計 Discord Bot isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

> MetaVisionBOT was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.
