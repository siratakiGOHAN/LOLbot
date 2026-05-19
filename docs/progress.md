# LoL Bot v2 — 進捗ドキュメント

最終更新: 2026-05-19

---

## プロジェクト構成

```
LoLbot_v2/
├── main.py            # Bot エントリポイント・週次更新タスク
├── ui.py              # Discord コマンド・View・Embed
├── core.py            # キャッシュ管理・チャンピオン解決・URL生成
├── database.py        # SQLite CRUD（aiosqlite）
├── data_collector.py  # Riot API データ収集バッチ
├── image_builder.py   # Pillow ビルド画像生成
├── script.py          # メッセージ定数・フォーマット関数
├── data/              # キャッシュファイル（JSON・PNG）
├── tests/             # pytest 自動テスト（35件）
└── docs/              # このドキュメント
```

---

## 実装済み機能 ✅

| 機能 | ファイル | 備考 |
|---|---|---|
| `/lol <champion> [lane]` カウンター提案 | ui.py | 勝率・ピック率・BAN率・ビルド表示 |
| チャンピオンオートコンプリート | ui.py | 日本語・英語対応、最大25件 |
| カウンターチャンピオンアイコンリンク | ui.py | cDragon CDN |
| ビルドボタン（画像＋YouTube） | ui.py | キーストーン左・アイテム右 |
| ビルド画像生成・キャッシュ | image_builder.py | ICON_SIZE=48, SEPARATOR=16 |
| `/lolupdate` 管理コマンド | ui.py | DBのみ更新、画像キャッシュ保持 |
| `/lolpatch` 管理コマンド | ui.py | 画像＋DataDragonキャッシュリセット |
| 週次自動データ更新（168h） | main.py | discord.ext.tasks |
| Riot API データ収集 | data_collector.py | Master以上、全11リージョン対応 |
| 自動テスト | tests/ | 35件全パス |

---

## DBスキーマ

| テーブル | 主キー | 用途 |
|---|---|---|
| champions | champion_id | チャンピオン名（英/日） |
| champion_lane_stats | (champion_id, lane) | レーン別ピック数・勝率 |
| matchups | (champion_id, enemy_id, lane) | マッチアップ勝率 |
| builds | (champion_id, enemy_id, lane) | アイテム・キーストーン（1パターンのみ） |
| ban_stats | (champion_id) | BANカウント（レーンなし・グローバル集計） |

---

## 既知のバグ・未実装

### ✅ BAN率バグ修正済み（2026-05-19）
- `ban_stats` スキーマからレーン列・total_games 列を除去
- `_process_match` で `info.teams[].bans[]` からBANデータを収集
- BAN率の分母は `champion_lane_stats.games`（表示上限100%キャップ付き）

### 📋 未実装機能（バックログ）
| 機能 | 規模 | 備考 |
|---|---|---|
| BAN率の分母を正確な総試合数に改善 | 小 | 現在は champion_lane_stats.games を流用（近似値） |
| ビルド複数パターン対応 | 中〜大 | DBスキーマ変更（builds PKに pattern_rank 追加）が必要 |
| サブルーン・セカンダリルーン | 小〜中 | data_collector + builds テーブル拡張 |
| 本番起動設定（NSSM） | 小 | 設定ファイル作成のみ |

---

## 運用メモ

- **初回データ投入**: `python data_collector.py --regions kr na1 euw1 jp1 --players 50 --matches 20`
- **本番運用**: `main.py` のみ起動すれば weekly_update が自動収集
- **DB競合リスク**: `data_collector.py` と `main.py` を同時起動しない
- **.env**: `DISCORD_BOT_TOKEN`, `RIOT_API_KEY`, `DB_PATH` が必要

---

## テスト実行

```bash
cd LoLbot_v2
pytest tests/ -v
```
