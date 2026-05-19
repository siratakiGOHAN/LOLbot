import asyncio
import sys
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))
import database

TEST_DB = str(Path(__file__).parent / "test_lolbot.db")


@pytest.fixture(scope="session", autouse=True)
def seed_db():
    """テスト前にシードデータを投入する。"""
    from tests.seed_test_db import seed
    asyncio.get_event_loop().run_until_complete(seed())


@pytest.mark.asyncio
async def test_get_counters_returns_top5():
    """Aatrox(266) に対するカウンターが勝率降順で最大5体返る。"""
    counters = await database.get_counters(TEST_DB, 266, "top", limit=5)
    assert len(counters) == 5
    # 勝率降順チェック
    win_rates = [row["wins"] / row["games"] for row in counters]
    assert win_rates == sorted(win_rates, reverse=True)


@pytest.mark.asyncio
async def test_winrate_calculation():
    """wins/games から勝率が正しく計算される。"""
    counters = await database.get_counters(TEST_DB, 266, "top", limit=1)
    assert len(counters) == 1
    top = counters[0]
    expected = top["wins"] / top["games"]
    assert abs(top["win_rate"] - expected) < 1e-6


@pytest.mark.asyncio
async def test_get_main_lane():
    """Aatrox(266) のメインレーンが top として返る。"""
    lane = await database.get_main_lane(TEST_DB, 266)
    assert lane == "top"


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
    await database.upsert_ban_stats(tmp_db, 999)
    await database.upsert_ban_stats(tmp_db, 999)
    await database.upsert_ban_stats(tmp_db, 999, ban_count=3)
    async with aiosqlite.connect(tmp_db) as db:
        async with db.execute(
            "SELECT ban_count FROM ban_stats WHERE champion_id = 999"
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 5


@pytest.mark.asyncio
async def test_get_builds_returns_multiple():
    """get_builds が勝率降順で最大3件返る。"""
    builds = await database.get_builds(TEST_DB, 122, 266, "top")
    assert len(builds) == 3
    win_rates = [b["wins"] / b["games"] for b in builds]
    assert win_rates == sorted(win_rates, reverse=True)


@pytest.mark.asyncio
async def test_get_builds_item_ids_are_list():
    """get_builds の item_ids が list[str] で返る。"""
    builds = await database.get_builds(TEST_DB, 122, 266, "top")
    assert isinstance(builds[0]["item_ids"], list)
    assert builds[0]["item_ids"] == ["3071", "3053", "6333"]


@pytest.mark.asyncio
async def test_get_build_backward_compatible():
    """get_build（後方互換）が勝率最上位のビルドを1件返す。"""
    build = await database.get_build(TEST_DB, 122, 266, "top")
    assert build is not None
    # 新スキーマでは各ビルドパターンは独立している
    # 勝率が最高なのはパターン1: item_ids=["3071", "3053", "6333"], wins=65, games=100 (65%)
    assert build["item_ids"] == ["3071", "3053", "6333"]
    assert build["wins"] == 65
    assert build["games"] == 100


@pytest.mark.asyncio
async def test_upsert_matchup_increments():
    """同じキーに upsert すると wins/games が加算される。"""
    before = await database.get_counters(TEST_DB, 266, "top", limit=10)
    darius_before = next(r for r in before if r["champion_id"] == 122)
    wins_before = darius_before["wins"]
    games_before = darius_before["games"]

    # 追加 upsert
    await database.upsert_matchup(TEST_DB, 122, 266, "top", 10, 20)

    after = await database.get_counters(TEST_DB, 266, "top", limit=10)
    darius_after = next(r for r in after if r["champion_id"] == 122)

    assert darius_after["wins"] == wins_before + 10
    assert darius_after["games"] == games_before + 20
