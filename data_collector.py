"""
Riot API からハイレート試合データを収集してDBへ保存するモジュール。
/lol コマンドとは完全に独立しており、手動または定期バッチで実行する。

実行例:
  python data_collector.py --test          # KRのみ・5人・5試合（動作確認用）
  python data_collector.py --regions kr jp1 --players 20 --matches 10
  python data_collector.py                 # フル収集（全11リージョン）
"""
import asyncio
import aiohttp
from datetime import datetime, timezone
from pathlib import Path

import database

ALL_REGIONS = ["kr", "na1", "euw1", "jp1", "eun1", "br1", "la1", "la2", "oc1", "tr1", "ru"]
MATCH_REGIONS = {
    "kr": "asia", "jp1": "asia",
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "oc1": "sea",
}
DEFAULT_PLAYERS_PER_REGION = 30
DEFAULT_MATCHES_PER_PLAYER = 10
REQUEST_INTERVAL = 2.0
MAX_RETRIES = 5


async def _get(session: aiohttp.ClientSession, url: str, params: dict | None = None) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    print(f"[data_collector] レートリミット: {retry_after}秒待機")
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status in (401, 403):
                    print(f"[data_collector] エラー{resp.status}: APIキーが無効または期限切れです。.env の RIOT_API_KEY を確認してください")
                    return None
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as e:
            if attempt == MAX_RETRIES - 1:
                print(f"[data_collector] 通信エラー: {e}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None


async def collect_high_elo_data(
    riot_key: str,
    db_path: str,
    regions: list[str] | None = None,
    players_per_region: int = DEFAULT_PLAYERS_PER_REGION,
    matches_per_player: int = DEFAULT_MATCHES_PER_PLAYER,
) -> None:
    """
    Master以上のプレイヤーの試合データを収集してDBに保存する。

    Args:
        riot_key:            Riot API キー
        db_path:             SQLite DBのパス
        regions:             収集対象リージョンのリスト（None で全リージョン）
        players_per_region:  1リージョンあたりの収集プレイヤー数
        matches_per_player:  1プレイヤーあたりの収集試合数
    """
    target_regions = regions or ALL_REGIONS
    headers = {"X-Riot-Token": riot_key}

    total_api_estimate = (
        len(target_regions)                              # Masterリーグ取得
        + len(target_regions) * players_per_region       # Summoner PUUID
        + len(target_regions) * players_per_region       # 試合ID
        + len(target_regions) * players_per_region * matches_per_player  # 試合詳細（重複除去前）
    )
    eta_min = total_api_estimate * REQUEST_INTERVAL / 60
    print(f"[data_collector] 開始: {target_regions}")
    print(f"[data_collector] 設定: {players_per_region}人/リージョン × {matches_per_player}試合")
    print(f"[data_collector] 推定APIコール: 約{total_api_estimate}回 / 推定時間: 約{eta_min:.0f}分")

    await database.init_db(db_path)

    async with aiohttp.ClientSession(headers=headers) as session:
        all_puuids: list[tuple[str, str]] = []

        # フェーズ1: 各リージョンのMasterリーグからPUUID収集
        for region in target_regions:
            print(f"[data_collector] [{region}] Masterリーグ取得中...")
            url = f"https://{region}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/RANKED_SOLO_5x5"
            data = await _get(session, url)
            if data is None:
                print(f"[data_collector] [{region}] スキップ")
                continue
            entries = data.get("entries", [])[:players_per_region]
            for entry in entries:
                # 新API: LeagueItemDTO に puuid が直接含まれる場合
                puuid = entry.get("puuid")
                if not puuid:
                    # 旧API: summonerId 経由で puuid を取得
                    summoner_id = entry.get("summonerId")
                    if not summoner_id:
                        continue
                    summoner_url = (
                        f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
                    )
                    summoner = await _get(session, summoner_url)
                    if summoner:
                        puuid = summoner.get("puuid")
                    await asyncio.sleep(REQUEST_INTERVAL)
                if puuid:
                    all_puuids.append((puuid, region))
            print(f"[data_collector] [{region}] {len(entries)}人のPUUID取得完了")

        print(f"[data_collector] 合計 {len(all_puuids)} 人のPUUID収集完了")

        # フェーズ2: 試合IDの収集
        all_match_ids: set[str] = set()
        for i, (puuid, region) in enumerate(all_puuids):
            match_region = MATCH_REGIONS.get(region, "asia")
            url = f"https://{match_region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            params = {"queue": 420, "count": matches_per_player}
            match_ids = await _get(session, url, params)
            if match_ids:
                all_match_ids.update(match_ids)
            if (i + 1) % 50 == 0:
                print(f"[data_collector] 試合ID収集: {i + 1}/{len(all_puuids)}人処理済み")
            await asyncio.sleep(REQUEST_INTERVAL)

        print(f"[data_collector] ユニーク試合ID: {len(all_match_ids)}件")
        print("[data_collector] レートリミットウィンドウをリセット中（120秒待機）...")
        await asyncio.sleep(120)

        # フェーズ3: 試合データの解析とDB保存
        processed = 0
        skipped = 0
        for match_id in all_match_ids:
            if await database.is_match_processed(db_path, match_id):
                skipped += 1
                continue

            region_prefix = match_id.split("_")[0].lower()
            match_region = next(
                (MATCH_REGIONS[r] for r in ALL_REGIONS if r.upper() == region_prefix),
                "asia",
            )
            url = f"https://{match_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_data = await _get(session, url)
            if match_data is None:
                skipped += 1
                continue

            await _process_match(db_path, match_data)
            await database.mark_match_processed(db_path, match_id)
            processed += 1
            if processed % 50 == 0:
                print(f"[data_collector] {processed}/{len(all_match_ids)} 試合処理済み")
            await asyncio.sleep(REQUEST_INTERVAL)

    print(f"[data_collector] 完了: {processed} 試合処理 / {skipped} スキップ")
    print(f"[data_collector] 終了時刻: {datetime.now(timezone.utc).isoformat()}")


async def _process_match(db_path: str, match_data: dict) -> None:
    """1試合のデータを解析してDBにupsertする。"""
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


async def sync_champion_names(db_path: str) -> None:
    """
    Data Dragon キャッシュを使って champions テーブルの名前を更新する。
    data_collector.py 実行後に呼ぶことで ID のみの仮登録を正式名に置き換える。
    """
    import core
    cache = await core.load_champion_cache()
    for champ_id_str, data in cache.items():
        await database.upsert_champion(
            db_path,
            data["champion_id"],
            data["name_en"],
            data["name_ja"],
        )
    print(f"[data_collector] チャンピオン名を {len(cache)} 件同期しました")


if __name__ == "__main__":
    import argparse
    import os
    import sys
    from dotenv import load_dotenv

    _here = Path(__file__).parent
    load_dotenv(_here / ".env")

    riot_key = os.environ.get("RIOT_API_KEY", "")
    if not riot_key:
        print("エラー: .env に RIOT_API_KEY が設定されていません")
        sys.exit(1)

    _db_raw = os.getenv("DB_PATH", "lolbot.db")
    db_path = str(_here / _db_raw) if not Path(_db_raw).is_absolute() else _db_raw

    parser = argparse.ArgumentParser(description="LoL ハイレート試合データ収集")
    parser.add_argument(
        "--test", action="store_true",
        help="テストモード: KRのみ・5人・5試合（約75コール / 約2分）"
    )
    parser.add_argument("--regions", nargs="+", default=None, help="収集リージョン (例: kr jp1 na1)")
    parser.add_argument("--players", type=int, default=None, help="1リージョンあたりのプレイヤー数")
    parser.add_argument("--matches", type=int, default=None, help="1プレイヤーあたりの試合数")
    parser.add_argument("--sync-names-only", action="store_true", help="試合収集せずチャンピオン名の同期のみ実行")
    args = parser.parse_args()

    if args.sync_names_only:
        asyncio.run(sync_champion_names(db_path))
        sys.exit(0)

    if args.test:
        regions = ["kr"]
        players = 5
        matches = 5
    else:
        regions = args.regions
        players = args.players or DEFAULT_PLAYERS_PER_REGION
        matches = args.matches or DEFAULT_MATCHES_PER_PLAYER

    async def _main() -> None:
        await collect_high_elo_data(riot_key, db_path, regions, players, matches)
        await sync_champion_names(db_path)

    asyncio.run(_main())
