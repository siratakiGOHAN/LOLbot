# BAN率バグ修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ban_stats` テーブルからレーン列を除去し、`_process_match` で BAN データを収集することで BAN 率が常に 0% になるバグを修正する。

**Architecture:** `ban_stats` を `(champion_id, ban_count)` のみに簡略化。BAN 率の分母は既存の `champion_lane_stats.games` を流用する。`data_collector._process_match` で `info.teams[].bans[]` を走査して `upsert_ban_stats` を呼ぶ。

**Tech Stack:** Python 3.13, aiosqlite, pytest, pytest-asyncio

---

## File Map

| ファイル | 変更内容 |
|---|---|
| `database.py` | `init_db` 移行処理追加・スキーマ変更・`upsert_ban_stats` 簡略化・`get_counters` クエリ修正・`get_ban_rate` 削除 |
| `data_collector.py` | `_process_match` に BAN 収集ロジック追加 |
| `tests/seed_test_db.py` | `BAN_STATS` を `(champion_id, ban_count)` 形式に更新 |
| `tests/test_database.py` | BAN 関連テスト更新・加算テスト追加 |

---

### Task 1: テストとシードデータを新スキーマ向けに更新（TDD: 先に失敗するテストを書く）

**Files:**
- Modify: `tests/seed_test_db.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: `seed_test_db.py` の `BAN_STATS` を更新する**

`tests/seed_test_db.py` の以下の箇所を変更する。

変更前:
```python
# BAN統計 (champion_id, lane, ban_count, total_games)
BAN_STATS = [
    (266, "top", 280, 1000),
    (122, "top", 320, 1000),
    (114, "top", 200, 1000),
    (39,  "top", 350, 1000),
    (86,  "top",  50, 1000),
    (24,  "top", 100, 1000),
]
```

変更後:
```python
# BAN統計 (champion_id, ban_count)
BAN_STATS = [
    (266, 280),
    (122, 320),
    (114, 200),
    (39,  350),
    (86,   50),
    (24,  100),
]
```

- [ ] **Step 2: `seed_test_db.py` の `seed()` 内の `upsert_ban_stats` 呼び出しを更新する**

変更前:
```python
    # BAN統計
    for champ_id, lane, ban_count, total_games in BAN_STATS:
        await database.upsert_ban_stats(db, champ_id, lane, ban_count, total_games)
```

変更後:
```python
    # BAN統計
    for champ_id, ban_count in BAN_STATS:
        await database.upsert_ban_stats(db, champ_id, ban_count)
```

- [ ] **Step 3: `test_database.py` の `test_ban_rate_calculation` を新テストに書き換える**

`test_database.py` の `test_ban_rate_calculation` を削除し、以下の2テストを追加する。

```python
@pytest.mark.asyncio
async def test_ban_count_in_counters():
    """get_counters の結果に ban_count と ban_total_games が含まれる。"""
    counters = await database.get_counters(TEST_DB, 266, "top", limit=5)
    darius = next(c for c in counters if c["champion_id"] == 122)
    # seed: Darius ban_count=320, lane_games=800 (champion_lane_stats)
    assert darius["ban_count"] == 320
    assert darius["ban_total_games"] == 800


@pytest.mark.asyncio
async def test_upsert_ban_stats_accumulates(tmp_path):
    """upsert_ban_stats を複数回呼ぶと ban_count が加算される。"""
    tmp_db = str(tmp_path / "test_ban.db")
    await database.init_db(tmp_db)
    await database.upsert_ban_stats(tmp_db, 999)          # +1
    await database.upsert_ban_stats(tmp_db, 999)          # +1
    await database.upsert_ban_stats(tmp_db, 999, ban_count=3)  # +3
    async with aiosqlite.connect(tmp_db) as db:
        async with db.execute(
            "SELECT ban_count FROM ban_stats WHERE champion_id = 999"
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 5
```

`test_database.py` の先頭に `import aiosqlite` を追記する（`tmp_path` 使用のため）。

- [ ] **Step 4: テストを実行して失敗することを確認する**

```
pytest tests/test_database.py -v
```

期待される結果: `test_ban_count_in_counters` と `test_upsert_ban_stats_accumulates` が **FAIL** (関数シグネチャ不一致またはスキーマ不一致)

---

### Task 2: `database.py` を更新して新スキーマを実装する

**Files:**
- Modify: `database.py`

- [ ] **Step 1: `init_db` に移行処理と新スキーマを実装する**

`database.py` の `init_db` 関数全体を以下に置き換える:

```python
async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        # ban_stats 旧スキーマ移行（lane 列があれば DROP して再作成）
        async with db.execute("PRAGMA table_info(ban_stats)") as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
        if "lane" in cols:
            await db.execute("DROP TABLE IF EXISTS ban_stats")
            await db.commit()

        await db.executescript("""
            CREATE TABLE IF NOT EXISTS champions (
                champion_id   INTEGER PRIMARY KEY,
                name_en       TEXT NOT NULL,
                name_ja       TEXT,
                updated_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS champion_lane_stats (
                champion_id   INTEGER,
                lane          TEXT,
                wins          INTEGER DEFAULT 0,
                games         INTEGER DEFAULT 0,
                pick_count    INTEGER DEFAULT 0,
                updated_at    TEXT,
                PRIMARY KEY (champion_id, lane)
            );

            CREATE TABLE IF NOT EXISTS matchups (
                champion_id   INTEGER,
                enemy_id      INTEGER,
                lane          TEXT,
                wins          INTEGER DEFAULT 0,
                games         INTEGER DEFAULT 0,
                updated_at    TEXT,
                PRIMARY KEY (champion_id, enemy_id, lane)
            );

            CREATE TABLE IF NOT EXISTS builds (
                champion_id   INTEGER,
                enemy_id      INTEGER,
                lane          TEXT,
                item_ids      TEXT,
                keystone_id   INTEGER,
                wins          INTEGER DEFAULT 0,
                games         INTEGER DEFAULT 0,
                updated_at    TEXT,
                PRIMARY KEY (champion_id, enemy_id, lane)
            );

            CREATE TABLE IF NOT EXISTS ban_stats (
                champion_id   INTEGER PRIMARY KEY,
                ban_count     INTEGER DEFAULT 0,
                updated_at    TEXT
            );
        """)
        await db.commit()
```

- [ ] **Step 2: `get_counters` クエリを更新する**

`database.py` の `get_counters` 内の SQL を以下に置き換える:

```python
        async with db.execute(
            """
            SELECT
                m.champion_id,
                c.name_en,
                c.name_ja,
                m.wins,
                m.games,
                CAST(m.wins AS REAL) / m.games AS win_rate,
                COALESCE(cls.pick_count, 0) AS pick_count,
                COALESCE(cls.games, 0) AS total_lane_games,
                COALESCE(bs.ban_count, 0) AS ban_count,
                COALESCE(cls.games, 0) AS ban_total_games
            FROM matchups m
            JOIN champions c ON m.champion_id = c.champion_id
            LEFT JOIN champion_lane_stats cls
                ON m.champion_id = cls.champion_id AND cls.lane = m.lane
            LEFT JOIN ban_stats bs
                ON m.champion_id = bs.champion_id
            WHERE m.enemy_id = ? AND m.lane = ? AND m.games >= 3
            ORDER BY win_rate DESC
            LIMIT ?
            """,
            (champion_id, lane, limit),
        ) as cursor:
```

変更点:
- `LEFT JOIN ban_stats bs ON ... AND bs.lane = m.lane` → `AND bs.lane = m.lane` を削除
- `COALESCE(bs.total_games, 0) AS ban_total_games` → `COALESCE(cls.games, 0) AS ban_total_games`

- [ ] **Step 3: `upsert_ban_stats` を新シグネチャに置き換える**

`database.py` の `upsert_ban_stats` 関数全体を以下に置き換える:

```python
async def upsert_ban_stats(
    db_path: str,
    champion_id: int,
    ban_count: int = 1,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO ban_stats (champion_id, ban_count, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(champion_id) DO UPDATE SET
                ban_count  = ban_count + excluded.ban_count,
                updated_at = excluded.updated_at
            """,
            (champion_id, ban_count, now),
        )
        await db.commit()
```

- [ ] **Step 4: `get_ban_rate` 関数を削除する**

`database.py` から `get_ban_rate` 関数（約10行）を削除する。この関数は本番コード（`ui.py`・`core.py`）からは呼ばれていない。

- [ ] **Step 5: テストを実行して全件パスすることを確認する**

```
pytest tests/test_database.py -v
```

期待される結果: 全テスト **PASS**

- [ ] **Step 6: 全テストを実行してリグレッションがないことを確認する**

```
pytest tests/ -v
```

期待される結果: 全35件（＋新規2件）**PASS**

- [ ] **Step 7: コミットする**

```
git add database.py tests/seed_test_db.py tests/test_database.py
git commit -m "fix: ban_stats からレーン列を除去し BAN 率計算を修正"
```

---

### Task 3: `data_collector.py` に BAN データ収集を追加する

**Files:**
- Modify: `data_collector.py:160-205`

- [ ] **Step 1: `_process_match` に BAN 収集ロジックを追加する**

`data_collector.py` の `_process_match` 関数末尾（`for enemy in participants` ループの外）に以下を追記する。

追記箇所は `async def _process_match` 内、`for participant in participants:` ループの**後**（インデント: 関数レベル、`for participant` と同じ深さ）。

```python
    # BAN データ収集
    teams = info.get("teams", [])
    for team in teams:
        for ban in team.get("bans", []):
            banned_id = ban.get("championId")
            if banned_id and banned_id > 0:  # -1 は BAN なしを意味する
                await database.upsert_ban_stats(db_path, banned_id)
```

- [ ] **Step 2: 追記後の `_process_match` 全体を確認する**

`_process_match` の最終形が以下になっていることを確認する:

```python
async def _process_match(db_path: str, match_data: dict) -> None:
    info = match_data.get("info", {})
    participants = info.get("participants", [])
    if len(participants) != 10:
        return

    lane_map = {
        "top": "top", "jungle": "jungle",
        "middle": "mid", "bottom": "adc", "utility": "support",
    }

    for participant in participants:
        champ_id = participant.get("championId")
        lane = lane_map.get(participant.get("teamPosition", "").lower())
        if champ_id is None or lane is None:
            continue

        won = int(participant.get("win", False))
        items = [
            str(participant[f"item{i}"])
            for i in range(6)
            if participant.get(f"item{i}")
        ]
        keystone_id = (
            participant.get("perks", {})
            .get("styles", [{}])[0]
            .get("selections", [{}])[0]
            .get("perk", 0)
        )

        await database.upsert_champion(db_path, champ_id, str(champ_id))
        await database.upsert_lane_stats(db_path, champ_id, lane, won, 1, 1)

        for enemy in participants:
            if enemy["teamId"] == participant["teamId"]:
                continue
            enemy_lane = lane_map.get(enemy.get("teamPosition", "").lower())
            if enemy_lane != lane:
                continue
            enemy_champ_id = enemy.get("championId")
            if enemy_champ_id is None:
                continue
            await database.upsert_matchup(db_path, champ_id, enemy_champ_id, lane, won, 1)
            await database.upsert_build(db_path, champ_id, enemy_champ_id, lane, items, keystone_id, won, 1)
            break

    # BAN データ収集
    teams = info.get("teams", [])
    for team in teams:
        for ban in team.get("bans", []):
            banned_id = ban.get("championId")
            if banned_id and banned_id > 0:
                await database.upsert_ban_stats(db_path, banned_id)
```

- [ ] **Step 3: 全テストを実行してリグレッションがないことを確認する**

```
pytest tests/ -v
```

期待される結果: 全テスト **PASS**

- [ ] **Step 4: コミットする**

```
git add data_collector.py
git commit -m "feat: _process_match で BAN データを収集するよう修正"
```

---

### Task 4: 動作確認

- [ ] **Step 1: テストモードでデータ収集を実行して BAN データが書き込まれるか確認する**

```
python data_collector.py --test
```

期待される出力:
```
[data_collector] 開始: ['kr']
[data_collector] 設定: 5人/リージョン × 5試合
...
[data_collector] 完了: XX 試合処理 / XX スキップ
```

- [ ] **Step 2: DB に ban_stats データが書き込まれたか確認する**

```
python -c "
import asyncio, aiosqlite
async def check():
    async with aiosqlite.connect('lolbot.db') as db:
        async with db.execute('SELECT champion_id, ban_count FROM ban_stats ORDER BY ban_count DESC LIMIT 10') as c:
            rows = await c.fetchall()
    for r in rows:
        print(r)
asyncio.run(check())
"
```

期待される結果: `ban_count > 0` の行が存在する

- [ ] **Step 3: `docs/progress.md` を更新する**

`docs/progress.md` の「既知のバグ」セクションから BAN 率バグの項目を「修正済み ✅」に変更する。
