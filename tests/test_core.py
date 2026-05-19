import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import core

# テスト用のチャンピオンキャッシュをモックとして注入
MOCK_CACHE = {
    "266": {"champion_id": 266, "name_en": "Aatrox",   "name_ja": "エイトロックス", "key": "Aatrox"},
    "122": {"champion_id": 122, "name_en": "Darius",   "name_ja": "ダリウス",       "key": "Darius"},
    "64":  {"champion_id": 64,  "name_en": "LeeSin",   "name_ja": "リー・シン",     "key": "LeeSin"},
    "39":  {"champion_id": 39,  "name_en": "Irelia",   "name_ja": "イレリア",       "key": "Irelia"},
}


MOCK_ITEM_CACHE = {
    "3071": {"name": "ブラック・クリーバー", "version": "15.1.1"},
    "3053": {"name": "スティールワーカーズ・エッジ", "version": "15.1.1"},
    "6333": {"name": "デスダンス", "version": "15.1.1"},
}

MOCK_RUNE_CACHE = {
    "8010": {"name": "コンカラー", "icon": "perk-images/Styles/Precision/Conqueror/Conqueror.png"},
    "8128": {"name": "ダークハーベスト", "icon": "perk-images/Styles/Domination/DarkHarvest/DarkHarvest.png"},
    "8214": {"name": "サモンアエリー", "icon": "perk-images/Styles/Sorcery/SummonAery/SummonAery.png"},
}


@pytest.fixture(autouse=True)
def inject_cache():
    core._champion_cache = MOCK_CACHE
    core._item_cache = MOCK_ITEM_CACHE
    core._rune_cache = MOCK_RUNE_CACHE
    yield
    core._champion_cache = None
    core._item_cache = None
    core._rune_cache = None


def test_resolve_champion_english():
    """英語名でチャンピオンが正しく解決される。"""
    result = core.resolve_champion("Aatrox")
    assert result == (266, "Aatrox", "エイトロックス")


def test_resolve_champion_japanese():
    """日本語名でチャンピオンが正しく解決される。"""
    result = core.resolve_champion("エイトロックス")
    assert result == (266, "Aatrox", "エイトロックス")


def test_resolve_champion_fuzzy():
    """小文字・表記ゆれでもあいまい検索で解決される。"""
    result = core.resolve_champion("aatrox")
    assert result is not None
    assert result[0] == 266


def test_resolve_champion_japanese_with_dot():
    """リー・シン（中黒付き）が正しく解決される。"""
    result = core.resolve_champion("リー・シン")
    assert result is not None
    assert result[0] == 64


def test_resolve_champion_unknown():
    """存在しないチャンピオン名は None を返す。"""
    result = core.resolve_champion("xyz123nonexistent")
    assert result is None


def test_cdimage_champion_url():
    """cDragon チャンピオンアイコン URL が正しく生成される。"""
    url = core.cdimage_champion(266)
    assert "266" in url
    assert url.startswith("https://raw.communitydragon.org")
    assert url.endswith(".png")


def test_resolve_item_name_known():
    """既知のアイテムIDが日本語名に変換される。"""
    assert core.resolve_item_name("3071") == "ブラック・クリーバー"
    assert core.resolve_item_name(3053) == "スティールワーカーズ・エッジ"


def test_resolve_item_name_unknown():
    """未知のアイテムIDはIDをそのまま返す。"""
    assert core.resolve_item_name("9999") == "9999"


def test_ddragon_item_image_url():
    """Data Dragon アイテム画像 URL が正しく生成される。"""
    url = core.ddragon_item_image("3071")
    assert url is not None
    assert "3071" in url
    assert "ddragon.leagueoflegends.com" in url
    assert url.endswith(".png")


def test_ddragon_item_image_unknown():
    """未知のアイテムIDは None を返す。"""
    assert core.ddragon_item_image("9999") is None


def test_resolve_rune_name_known():
    """既知のルーンIDが日本語名に変換される。"""
    assert core.resolve_rune_name("8010") == "コンカラー"
    assert core.resolve_rune_name(8128) == "ダークハーベスト"


def test_resolve_rune_name_unknown():
    """未知のルーンIDはIDをそのまま返す。"""
    assert core.resolve_rune_name("9999") == "9999"


def test_ddragon_rune_image_url():
    """Data Dragon ルーン画像 URL が正しく生成される。"""
    url = core.ddragon_rune_image("8010")
    assert url is not None
    assert "ddragon.leagueoflegends.com" in url
    assert "Conqueror" in url
    assert url.endswith(".png")


def test_ddragon_rune_image_unknown():
    """未知のルーンIDは None を返す。"""
    assert core.ddragon_rune_image("9999") is None
