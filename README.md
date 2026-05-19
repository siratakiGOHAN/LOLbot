# LoL Bot — League of Legends カウンター分析 Discord Bot


ハイレートプレイヤー（Master以上）の試合データをもとに、チャンピオンごとのマッチアップ統計を提供する Discord Bot です。勝率・ピック率・BAN率・推奨ビルドを確認することで、プレイヤー自身がメタを理解し、チャンピオンプールを改善するための参考情報として活用できます。


## 💡 開発背景と目的

趣味である『League of Legends』の戦術分析を、より手軽にDiscord上で行いたいと考え開発しました。

ただPythonの文法を学ぶだけでなく、**「実際の外部API（Riot API）との連携」「非同期処理による効率的なデータ収集」「データベースを用いた統計管理」**など、実戦的なバックエンド開発のスキルを習得・証明するためのポートフォリオとして制作しています。

## 機能

- **`/lol <チャンピオン> [レーン]`** — 指定チャンピオンに対して有利なチャンピオンの統計を表示
  - マッチアップ勝率・ピック率・BAN率
  - 推奨ビルド（アイテム・キーストーンルーン）画像
  - YouTube 実際のマッチアップの動画へのリンク
- **チャンピオン名オートコンプリート** — 日本語・英語両対応
- **`/lolupdate`** — 管理者用：最新データに手動更新
- **`/lolpatch`** — 管理者用：パッチ後のキャッシュリセット

## スクリーンショット

![counter](https://raw.githubusercontent.com/siratakiGOHAN/LOLbot/main/docs/images/screenshot_counter.png)

## 技術スタック

- Python 3.13
- discord.py v2.0（slash commands）
- aiohttp / aiosqlite
- Pillow（ビルド画像生成）
- Riot API v4/v5（League-V4, Match-V5, Summoner-V4）
- Data Dragon / CommunityDragon

## セットアップ

### 必要環境

- Python 3.13+
- Discord Bot Token
- Riot API Key

### インストール

```bash
git clone https://github.com/siratakiGOHAN/LOLbot.git
cd LOLbot
pip install -r requirements.txt
```

### 設定

`.env` ファイルをプロジェクトルートに作成：

```
DISCORD_BOT_TOKEN=your_discord_bot_token
RIOT_API_KEY=your_riot_api_key
DB_PATH=lolbot.db
```

### データ収集

```bash
# テスト収集（KR・5人・5試合）
python data_collector.py --test

# 本番収集（主要リージョン）
python data_collector.py --regions kr euw1 na1 jp1 --players 50 --matches 20
```

### Bot 起動

```bash
python main.py
```

## データソース

Master以上のランクプレイヤーの試合データをRiot APIから収集し、SQLiteデータベースに蓄積します。データは毎日自動更新されます。

## プライバシーポリシー

本Botが収集するデータは、Riot APIから取得した公開試合統計（チャンピオンID・勝敗・アイテム・ルーン）のみです。Discord ユーザーの個人情報は一切収集・保存しません。

## ライセンス

League of Legends カウンター分析 Discord Bot isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

> LoL Bot was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.
