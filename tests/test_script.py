import sys
from pathlib import Path
from urllib.parse import unquote_plus, urlparse, parse_qs

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import script


def test_youtube_url_format():
    """YouTube URL にクエリパラメータが正しく含まれる。"""
    url = script.youtube_url("Aatrox", "Darius", "TOP")
    assert url.startswith("https://www.youtube.com/results")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    query = unquote_plus(params["search_query"][0])
    assert "Aatrox" in query
    assert "Darius" in query
    assert "TOP" in query
    assert "High Elo" in query


def test_format_winrate_normal():
    """50/100 → 50.0% になる。"""
    assert script.format_winrate(50, 100) == "50.0%"


def test_format_winrate_zero_games():
    """試合数0のときは N/A になる。"""
    assert script.format_winrate(0, 0) == "N/A"


def test_format_winrate_precision():
    """小数点1桁で切り捨てられる。"""
    assert script.format_winrate(1, 3) == "33.3%"


def test_format_stats_field_structure():
    """format_stats_field が (str, str) タプルを返す。"""
    counter = {
        "champion_id": 122,
        "name_en": "Darius",
        "name_ja": "ダリウス",
        "wins": 65,
        "games": 100,
        "win_rate": 0.65,
        "pick_count": 800,
        "total_lane_games": 1000,
        "ban_count": 320,
        "ban_total_games": 1000,
    }
    name, value = script.format_stats_field(counter, rank=1)
    assert "ダリウス" in name
    assert "Darius" in name
    assert "1." in name
    assert "65.0%" in value
    assert "80.0%" in value   # ピック率
    assert "32.0%" in value   # BAN率


def test_lane_display_known():
    """既知レーンが正しく表示名に変換される。"""
    assert script.lane_display("top") == "TOP"
    assert script.lane_display("jungle") == "JG"
    assert script.lane_display("mid") == "MID"
    assert script.lane_display("adc") == "ADC"
    assert script.lane_display("support") == "SUP"


def test_lane_display_unknown():
    """未知レーンは大文字変換される。"""
    assert script.lane_display("foo") == "FOO"
