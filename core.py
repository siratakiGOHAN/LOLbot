import json
import difflib
import aiohttp
from pathlib import Path

import database

_DATA_DIR = Path(__file__).parent / "data"
CHAMP_CACHE_PATH = _DATA_DIR / "champion_cache.json"
ITEM_CACHE_PATH  = _DATA_DIR / "item_cache.json"
RUNE_CACHE_PATH  = _DATA_DIR / "rune_cache.json"

DDRAGON_VERSIONS_URL  = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_RUNE_IMG_BASE = "https://ddragon.leagueoflegends.com/cdn/img/"
CDIMAGE_CHAMP_URL = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data"
    "/global/default/v1/champion-icons/{champion_id}.png"
)
DDRAGON_ITEM_IMG_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{item_id}.png"

_champion_cache: dict | None = None
_item_cache: dict | None = None   # {item_id_str: {"name": str, "version": str}}
_rune_cache: dict | None = None   # {rune_id_str: {"name": str, "icon": str}}


async def _latest_ddragon_version(session: aiohttp.ClientSession) -> str:
    async with session.get(DDRAGON_VERSIONS_URL) as resp:
        resp.raise_for_status()
        versions = await resp.json(content_type=None)
    return versions[0]


async def load_champion_cache(force: bool = False) -> dict:
    """Data Dragon から全チャンピオンデータを取得してキャッシュする。"""
    global _champion_cache

    if not force and _champion_cache is not None:
        return _champion_cache

    if not force and CHAMP_CACHE_PATH.exists():
        with open(CHAMP_CACHE_PATH, encoding="utf-8") as f:
            _champion_cache = json.load(f)
        return _champion_cache

    async with aiohttp.ClientSession() as session:
        version = await _latest_ddragon_version(session)
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/champion.json"
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

    cache: dict[str, dict] = {}
    for champ_key, champ_data in raw["data"].items():
        champ_id = int(champ_data["key"])
        name_en = champ_data["id"]
        name_ja = champ_data.get("name", name_en)
        cache[str(champ_id)] = {
            "champion_id": champ_id,
            "name_en": name_en,
            "name_ja": name_ja,
            "key": champ_key,
        }

    CHAMP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAMP_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    _champion_cache = cache
    return cache


async def load_item_cache(force: bool = False) -> dict:
    """Data Dragon から全アイテムデータを取得してキャッシュする。"""
    global _item_cache

    if not force and _item_cache is not None:
        return _item_cache

    if not force and ITEM_CACHE_PATH.exists():
        with open(ITEM_CACHE_PATH, encoding="utf-8") as f:
            _item_cache = json.load(f)
        return _item_cache

    async with aiohttp.ClientSession() as session:
        version = await _latest_ddragon_version(session)
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/item.json"
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

    cache: dict[str, dict] = {}
    for item_id, item_data in raw["data"].items():
        cache[item_id] = {
            "name": item_data.get("name", item_id),
            "version": version,
        }

    ITEM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ITEM_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    _item_cache = cache
    return cache


def _normalize(text: str) -> str:
    return text.lower().replace(" ", "").replace("・", "").replace("'", "").replace(".", "")


def resolve_champion(name_input: str) -> tuple[int, str, str] | None:
    """日本語・英語の表記ゆれを吸収して (champion_id, name_en, name_ja) を返す。キャッシュ未ロード時は None。"""
    if _champion_cache is None:
        return None

    norm_input = _normalize(name_input)

    # 完全一致（正規化後）を優先
    for champ in _champion_cache.values():
        if (
            _normalize(champ["name_en"]) == norm_input
            or _normalize(champ["name_ja"]) == norm_input
        ):
            return champ["champion_id"], champ["name_en"], champ["name_ja"]

    # あいまい検索（英語名）
    all_keys_en = {_normalize(c["name_en"]): c for c in _champion_cache.values()}
    all_keys_ja = {_normalize(c["name_ja"]): c for c in _champion_cache.values()}
    all_keys = {**all_keys_en, **all_keys_ja}

    matches = difflib.get_close_matches(norm_input, all_keys.keys(), n=1, cutoff=0.6)
    if matches:
        champ = all_keys[matches[0]]
        return champ["champion_id"], champ["name_en"], champ["name_ja"]

    return None


async def load_rune_cache(force: bool = False) -> dict:
    """Data Dragon からルーンデータを取得してキャッシュする。"""
    global _rune_cache

    if not force and _rune_cache is not None:
        return _rune_cache

    if not force and RUNE_CACHE_PATH.exists():
        with open(RUNE_CACHE_PATH, encoding="utf-8") as f:
            _rune_cache = json.load(f)
        return _rune_cache

    async with aiohttp.ClientSession() as session:
        version = await _latest_ddragon_version(session)
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/runesReforged.json"
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

    cache: dict[str, dict] = {}
    for tree in raw:
        for slot in tree.get("slots", []):
            for rune in slot.get("runes", []):
                cache[str(rune["id"])] = {
                    "name": rune.get("name", str(rune["id"])),
                    "icon": rune.get("icon", ""),
                }

    RUNE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    _rune_cache = cache
    return cache


def resolve_rune_name(rune_id: int | str) -> str:
    """ルーンIDを日本語名に変換する。キャッシュ未ロード時はIDをそのまま返す。"""
    if _rune_cache is None:
        return str(rune_id)
    entry = _rune_cache.get(str(rune_id))
    return entry["name"] if entry else str(rune_id)


def ddragon_rune_image(rune_id: int | str) -> str | None:
    """Data Dragon のルーン画像 URL を返す。"""
    if _rune_cache is None:
        return None
    entry = _rune_cache.get(str(rune_id))
    if entry is None or not entry.get("icon"):
        return None
    return DDRAGON_RUNE_IMG_BASE + entry["icon"]


def resolve_item_name(item_id: int | str) -> str:
    """アイテムIDを日本語名に変換する。キャッシュ未ロード時はIDをそのまま返す。"""
    if _item_cache is None:
        return str(item_id)
    entry = _item_cache.get(str(item_id))
    return entry["name"] if entry else str(item_id)


def ddragon_item_image(item_id: int | str) -> str | None:
    """Data Dragon のアイテム画像 URL を返す。バージョン情報がなければ None。"""
    if _item_cache is None:
        return None
    entry = _item_cache.get(str(item_id))
    if entry is None:
        return None
    return DDRAGON_ITEM_IMG_URL.format(version=entry["version"], item_id=item_id)


def cdimage_champion(champion_id: int) -> str:
    return CDIMAGE_CHAMP_URL.format(champion_id=champion_id)


async def detect_main_lane(db_path: str, champion_id: int) -> str | None:
    return await database.get_main_lane(db_path, champion_id)


async def get_counters(db_path: str, champion_id: int, lane: str, limit: int = 5) -> list[dict]:
    return await database.get_counters(db_path, champion_id, lane, limit)


async def get_build(db_path: str, champion_id: int, enemy_id: int, lane: str) -> dict | None:
    return await database.get_build(db_path, champion_id, enemy_id, lane)
