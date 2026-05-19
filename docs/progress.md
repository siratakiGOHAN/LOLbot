# LoL Bot v2 — 進捗ドキュメント

最終更新: 2026-05-20

---

## プロジェクト構成

```
LoLbot_v2/
├── main.py            # Bot エントリポイント・日次更新タスク
├── ui.py              # Discord コマンド・View・Embed
├── core.py            # キャッシュ管理・チャンピオン解決・URL生成
├── database.py        # SQLite CRUD（aiosqlite）
├── data_collector.py  # Riot API データ収集バッチ
├── image_builder.py   # Pillow ビルド画像生成
├── script.py          # メッセージ定数・フォーマット関数
├── data/              # キャッシュファイル（JSON・PNG）
├── tests/             # pytest 自動テスト（38件）
└── docs/              # このドキュメント
```

---

## 実装済み機能 ✅

| 機能 | ファイル | 備考 |
|---|---|---|
| `/lol <champion> [lane]` カウンター提案 | ui.py | 勝率・ピック率・BAN率・ビルド表示 |
| チャンピオンオートコンプリート | ui.py | 日本語・英語対応、最大25件 |
| カウンターチャンピオンアイコンリンク | ui.py | cDragon CDN |
| ビルドボタン（最大3パターン表示） | ui.py | 勝率降順・パターン1の画像付き |
| ビルド画像生成・キャッシュ | image_builder.py | ICON_SIZE=48, SEPARATOR=16 |
| `/lolupdate` 管理コマンド | ui.py | DBのみ更新、画像キャッシュ保持 |
| `/lolpatch` 管理コマンド | ui.py | 画像＋DataDragonキャッシュリセット |
| 日次自動データ更新（24h） | main.py | discord.ext.tasks |
| Riot API データ収集 | data_collector.py | Master以上、全11リージョン対応 |
| 重複試合収集の防止 | data_collector.py, database.py | processed_matches テーブルで処理済みIDを管理 |
| フェーズ2→3間クールダウン（120秒） | data_collector.py | レートリミットウィンドウのリセット待機 |
| 自動テスト | tests/ | 38件全パス |

---

## DBスキーマ

| テーブル | 主キー | 用途 |
|---|---|---|
| champions | champion_id | チャンピオン名（英/日） |
| champion_lane_stats | (champion_id, lane) | レーン別ピック数・勝率 |
| matchups | (champion_id, enemy_id, lane) | マッチアップ勝率 |
| builds | (champion_id, enemy_id, lane, item_ids) | アイテム・キーストーン（複数パターン対応） |
| ban_stats | champion_id | BANカウント（レーンなし・グローバル集計） |
| processed_matches | match_id | 処理済み試合ID（重複収集防止） |

---

## 既知のバグ・修正履歴

### ✅ BAN率バグ修正済み（2026-05-19）
- `ban_stats` スキーマからレーン列・total_games 列を除去
- `_process_match` で `info.teams[].bans[]` からBANデータを収集
- BAN率の分母は `champion_lane_stats.games`（表示上限100%キャップ付き）

### ✅ ビルド複数パターン対応（2026-05-20）
- `builds` テーブルのPKに `item_ids` を追加
- 異なるビルド構成が別行として蓄積される
- `get_builds` 関数で勝率降順上位3件を取得

### ✅ 重複収集防止（2026-05-20）
- `processed_matches` テーブルで処理済み `match_id` を管理
- 同じ試合を再処理することによる統計の歪みを防止

---

## 📋 未実装機能（バックログ）

| 機能 | 規模 | 備考 |
|---|---|---|
| 本番起動設定（NSSM） | 小 | PC再起動後の自動起動。データ収集継続性に直結 |
| BAN率の分母を正確な総試合数に改善 | 小 | 現在は champion_lane_stats.games を流用（近似値） |
| サブルーン・セカンダリルーン表示 | 小〜中 | data_collector + builds テーブル拡張が必要 |

---

## 運用メモ

- **初回データ投入**: `python data_collector.py --regions kr na1 euw1 jp1 --players 50 --matches 20`
- **本番運用**: `main.py` のみ起動すれば `daily_update` が24時間ごとに自動収集
- **DB競合リスク**: `data_collector.py` と `main.py` を同時起動しない
- **レートリミット**: Developer API（20/1s, 100/2min）のため大規模収集は時間がかかる
- **.env**: `DISCORD_BOT_TOKEN`, `RIOT_API_KEY`, `DB_PATH` が必要

---

## テスト実行

```bash
cd LoLbot_v2
pytest tests/ -v
```
