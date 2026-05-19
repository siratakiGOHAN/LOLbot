"""
テスト用モックデータを test_lolbot.db に投入するスクリプト。
python tests/seed_test_db.py で実行。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import database

TEST_DB = str(Path(__file__).parent / "test_lolbot.db")

CHAMPIONS = [
    (266,  "Aatrox",    "エイトロックス"),
    (122,  "Darius",    "ダリウス"),
    (114,  "Fiora",     "フィオラ"),
    (86,   "Garen",     "ガレン"),
    (39,   "Irelia",    "イレリア"),
    (24,   "Jax",       "ジャックス"),
    (54,   "Malphite",  "マルファイト"),
    (75,   "Nasus",     "ナサス"),
    (92,   "Riven",     "リヴェン"),
    (14,   "Sion",      "サイオン"),
]

# Aatrox(266) に対するカウンター（top レーン）勝率データ
# (counter_champ_id, wins, games)
AATROX_COUNTERS_TOP = [
    (122,  65, 100),  # Darius    65%
    (114,  62, 100),  # Fiora     62%
    (39,   60, 100),  # Irelia    60%
    (86,   55, 100),  # Garen     55%
    (24,   52, 100),  # Jax       52%
    (54,   48, 100),  # Malphite  48%  (← カウンターされない側)
]

# ビルドデータ (champion_id, enemy_id, lane, item_ids, keystone_id, wins, games)
# Darius vs Aatrox は3パターン用意（複数ビルドテスト用）
BUILDS = [
    (122, 266, "top", ["3071", "3053", "6333"], 8010, 65, 100),  # Darius パターン1: 勝率65%
    (122, 266, "top", ["3071", "6333", "3026"], 8010, 55, 100),  # Darius パターン2: 勝率55%
    (122, 266, "top", ["3053", "3026", "3143"], 8010, 45, 100),  # Darius パターン3: 勝率45%
    (114, 266, "top", ["3078", "3134", "6694"], 8128, 62, 100),  # Fiora  vs Aatrox
    (39,  266, "top", ["3003", "3115", "6655"], 8214, 60, 100),  # Irelia vs Aatrox
]

# レーンスタッツ (champion_id, lane, wins, games, pick_count)
LANE_STATS = [
    (266, "top",    420, 700, 700),
    (266, "mid",     30,  80,  80),
    (122, "top",    500, 800, 800),
    (114, "top",    480, 750, 750),
    (39,  "top",    460, 720, 720),
    (86,  "top",    400, 700, 700),
    (24,  "top",    380, 680, 680),
    (54,  "top",    350, 650, 650),
]

# BAN統計 (champion_id, ban_count)
BAN_STATS = [
    (266, 280),
    (122, 320),
    (114, 200),
    (39,  350),
    (86,   50),
    (24,  100),
]


async def seed() -> None:
    db = TEST_DB

    # 既存の DB を削除してクリーンな状態で開始
    db_path = Path(db)
    if db_path.exists():
        db_path.unlink()

    # テーブル初期化
    await database.init_db(db)

    # チャンピオン
    for champ_id, name_en, name_ja in CHAMPIONS:
        await database.upsert_champion(db, champ_id, name_en, name_ja)

    # マッチアップ
    for counter_id, wins, games in AATROX_COUNTERS_TOP:
        await database.upsert_matchup(db, counter_id, 266, "top", wins, games)

    # ビルド
    for champ_id, enemy_id, lane, item_ids, keystone_id, wins, games in BUILDS:
        await database.upsert_build(db, champ_id, enemy_id, lane, item_ids, keystone_id, wins, games)

    # レーンスタッツ
    for champ_id, lane, wins, games, pick_count in LANE_STATS:
        await database.upsert_lane_stats(db, champ_id, lane, wins, games, pick_count)

    # BAN統計
    for champ_id, ban_count in BAN_STATS:
        await database.upsert_ban_stats(db, champ_id, ban_count=ban_count)

    print(f"[seed] テストデータを {db} に投入しました")


if __name__ == "__main__":
    asyncio.run(seed())
