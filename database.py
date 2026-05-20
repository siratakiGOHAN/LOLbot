import aiosqlite
from datetime import datetime, timezone


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        # ban_stats 旧スキーマ移行（lane 列があれば DROP して再作成）
        async with db.execute("PRAGMA table_info(ban_stats)") as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
        if "lane" in cols:
            await db.execute("DROP TABLE IF EXISTS ban_stats")
            await db.commit()

        # builds 旧スキーマ移行（item_ids が PK に含まれていなければ DROP して再作成）
        async with db.execute("PRAGMA table_info(builds)") as cursor:
            build_cols = {row[1]: row[5] for row in await cursor.fetchall()}
        if build_cols and build_cols.get("item_ids", 0) == 0:
            await db.execute("DROP TABLE IF EXISTS builds")
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
                PRIMARY KEY (champion_id, enemy_id, lane, item_ids)
            );

            CREATE TABLE IF NOT EXISTS ban_stats (
                champion_id   INTEGER PRIMARY KEY,
                ban_count     INTEGER DEFAULT 0,
                updated_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS processed_matches (
                match_id      TEXT PRIMARY KEY,
                processed_at  TEXT
            );
        """)
        await db.commit()


async def get_counters(db_path: str, champion_id: int, lane: str, limit: int = 5) -> list[dict]:
    """指定チャンピオン×レーンに対して勝率上位のカウンター一覧を返す。"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
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
                (SELECT COALESCE(SUM(games), 0) FROM champion_lane_stats WHERE lane = m.lane) AS total_lane_games,
                COALESCE(bs.ban_count, 0) AS ban_count,
                (SELECT COALESCE(COUNT(*), 0) FROM processed_matches) AS ban_total_games
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
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_builds(
    db_path: str,
    champion_id: int,
    enemy_id: int,
    lane: str,
    limit: int = 3,
) -> list[dict]:
    """チャンピオン×対面×レーンのビルドを勝率降順で最大 limit 件返す。"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT item_ids, keystone_id, wins, games
            FROM builds
            WHERE champion_id = ? AND enemy_id = ? AND lane = ?
            ORDER BY CASE WHEN games > 0 THEN CAST(wins AS REAL) / games ELSE 0 END DESC
            LIMIT ?
            """,
            (champion_id, enemy_id, lane, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["item_ids"] = r["item_ids"].split(",") if r["item_ids"] else []
        results.append(r)
    return results


async def get_build(db_path: str, champion_id: int, enemy_id: int, lane: str) -> dict | None:
    """後方互換: 勝率最上位のビルドを1件返す。"""
    builds = await get_builds(db_path, champion_id, enemy_id, lane, limit=1)
    return builds[0] if builds else None



async def get_main_lane(db_path: str, champion_id: int) -> str | None:
    """champion_lane_statsのpick_countが最多のレーンを返す。"""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT lane FROM champion_lane_stats
            WHERE champion_id = ?
            ORDER BY pick_count DESC
            LIMIT 1
            """,
            (champion_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def upsert_champion(db_path: str, champion_id: int, name_en: str, name_ja: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO champions (champion_id, name_en, name_ja, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(champion_id) DO UPDATE SET
                name_en = excluded.name_en,
                name_ja = excluded.name_ja,
                updated_at = excluded.updated_at
            """,
            (champion_id, name_en, name_ja, now),
        )
        await db.commit()


async def upsert_matchup(
    db_path: str,
    champion_id: int,
    enemy_id: int,
    lane: str,
    wins: int,
    games: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO matchups (champion_id, enemy_id, lane, wins, games, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(champion_id, enemy_id, lane) DO UPDATE SET
                wins = wins + excluded.wins,
                games = games + excluded.games,
                updated_at = excluded.updated_at
            """,
            (champion_id, enemy_id, lane, wins, games, now),
        )
        await db.commit()


async def upsert_build(
    db_path: str,
    champion_id: int,
    enemy_id: int,
    lane: str,
    item_ids: list[str],
    keystone_id: int,
    wins: int,
    games: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO builds (champion_id, enemy_id, lane, item_ids, keystone_id, wins, games, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(champion_id, enemy_id, lane, item_ids) DO UPDATE SET
                wins = wins + excluded.wins,
                games = games + excluded.games,
                updated_at = excluded.updated_at
            """,
            (champion_id, enemy_id, lane, ",".join(item_ids), keystone_id, wins, games, now),
        )
        await db.commit()


async def upsert_lane_stats(
    db_path: str,
    champion_id: int,
    lane: str,
    wins: int,
    games: int,
    pick_count: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO champion_lane_stats (champion_id, lane, wins, games, pick_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(champion_id, lane) DO UPDATE SET
                wins = wins + excluded.wins,
                games = games + excluded.games,
                pick_count = pick_count + excluded.pick_count,
                updated_at = excluded.updated_at
            """,
            (champion_id, lane, wins, games, pick_count, now),
        )
        await db.commit()


async def is_match_processed(db_path: str, match_id: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM processed_matches WHERE match_id = ?", (match_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def mark_match_processed(db_path: str, match_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO processed_matches (match_id, processed_at) VALUES (?, ?)",
            (match_id, now),
        )
        await db.commit()


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
