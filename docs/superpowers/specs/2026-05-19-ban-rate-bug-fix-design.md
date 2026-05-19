# BAN率バグ修正 — 設計ドキュメント

作成日: 2026-05-19

---

## 背景・目的

`/lol` コマンドのカウンター提案画面にBAN率を表示しているが、常に 0% になっている。
原因は `data_collector.py` の `_process_match` で `upsert_ban_stats` が一度も呼ばれていないこと。
加えて、既存の `ban_stats` スキーマに `lane` 列があるが、Riot API の BAN データはレーン情報を持たないため設計上のミスマッチがある。

BAN率はゲーム開始前に決まるグローバルな指標であり、レーン別に管理する必要はない。

---

## 変更スコープ

| ファイル | 変更内容 |
|---|---|
| `database.py` | スキーマ変更・関数シグネチャ変更・クエリ修正 |
| `data_collector.py` | `_process_match` にBANデータ収集ロジック追加 |
| `tests/test_database.py` | BAN関連テスト更新 |

---

## 設計詳細

### 1. スキーマ変更（`database.py`）

**新スキーマ:**
```sql
CREATE TABLE IF NOT EXISTS ban_stats (
    champion_id  INTEGER PRIMARY KEY,
    ban_count    INTEGER DEFAULT 0,
    total_games  INTEGER DEFAULT 0,
    updated_at   TEXT
);
```

**移行処理（`init_db` 内に追加）:**
```python
async with db.execute("PRAGMA table_info(ban_stats)") as cursor:
    columns = [row[1] for row in await cursor.fetchall()]
if "lane" in columns:
    await db.execute("DROP TABLE ban_stats")
    await db.commit()
# この後に CREATE TABLE IF NOT EXISTS が走る
```

既存の `ban_stats` データは全て 0 のため、DROP してもデータロスなし。

---

### 2. 関数シグネチャ変更（`database.py`）

**`upsert_ban_stats`:**
```python
# 変更前
async def upsert_ban_stats(db_path, champion_id, lane, ban_count, total_games)

# 変更後
async def upsert_ban_stats(db_path, champion_id, total_games)
# ban_count は常に1（呼び出し側で1試合1カウント）
```

**`get_ban_rate`:**
```python
# 変更前
async def get_ban_rate(db_path, champion_id, lane) -> float

# 変更後
async def get_ban_rate(db_path, champion_id) -> float
```

---

### 3. `get_counters` クエリ修正（`database.py`）

```sql
-- 変更前
LEFT JOIN ban_stats bs ON m.champion_id = bs.champion_id AND bs.lane = m.lane

-- 変更後
LEFT JOIN ban_stats bs ON m.champion_id = bs.champion_id
```

---

### 4. BANデータ収集（`data_collector.py` — `_process_match`）

Riot API の BAN データ構造:
```json
info.teams[].bans = [{"championId": 123, "pickTurn": 1}, ...]
```
1試合最大10チャンピオンがBAN（各チーム5体）。`championId=-1` はBANなしを意味する。

追加コード（participants ループの後）:
```python
teams = info.get("teams", [])
for team in teams:
    for ban in team.get("bans", []):
        banned_id = ban.get("championId")
        if banned_id and banned_id > 0:
            await database.upsert_ban_stats(db_path, banned_id, 1)
```

---

### 5. テスト更新（`tests/test_database.py`）

- `upsert_ban_stats` / `get_ban_rate` の `lane` 引数を削除
- 追加テスト:
  - `championId=-1` をスキップすることの確認
  - 複数試合で `ban_count` / `total_games` が正しく加算されることの確認

---

## 検証方法

1. `pytest tests/ -v` で全テストがパスすることを確認
2. Bot 起動後 `/lol <チャンピオン>` を実行し、BAN率が 0% 以外の値を示すことを確認（データ再収集後）
3. データ再収集: `python data_collector.py --test` でKR・5人・5試合の小規模収集を実行し、BAN率がDBに書き込まれることを確認
