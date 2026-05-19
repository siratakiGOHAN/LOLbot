import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import image_builder


def _make_icon(path: Path, color=(255, 0, 0, 255)) -> None:
    """テスト用ダミーアイコンを作成する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (48, 48), color).save(path, "PNG")


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    """アイコン・ルーン・ビルド画像の出力先を一時ディレクトリに差し替える。"""
    icon_dir      = tmp_path / "item_icons"
    rune_icon_dir = tmp_path / "rune_icons"
    build_dir     = tmp_path / "build_images"
    monkeypatch.setattr(image_builder, "ICON_DIR",      icon_dir)
    monkeypatch.setattr(image_builder, "RUNE_ICON_DIR", rune_icon_dir)
    monkeypatch.setattr(image_builder, "BUILD_IMG_DIR", build_dir)
    return icon_dir, rune_icon_dir, build_dir


@pytest.mark.asyncio
async def test_get_build_image_creates_file(dirs):
    """合成画像が生成されファイルが作成される。"""
    icon_dir, _, _ = dirs
    _make_icon(icon_dir / "3071.png", (255, 0, 0, 255))
    _make_icon(icon_dir / "3053.png", (0, 255, 0, 255))
    _make_icon(icon_dir / "6333.png", (0, 0, 255, 255))

    result = await image_builder.get_build_image(
        ["3071", "3053", "6333"], {"3071": None, "3053": None, "6333": None}
    )
    assert result is not None
    assert result.exists()
    assert result.suffix == ".png"


@pytest.mark.asyncio
async def test_get_build_image_correct_size_no_keystone(dirs):
    """キーストーンなし: 幅 = ICON_SIZE*N + PADDING*(N-1)"""
    icon_dir, _, _ = dirs
    for item_id in ["3071", "3053", "6333"]:
        _make_icon(icon_dir / f"{item_id}.png")

    result = await image_builder.get_build_image(
        ["3071", "3053", "6333"], {i: None for i in ["3071", "3053", "6333"]}
    )
    img = Image.open(result)
    expected_w = image_builder.ICON_SIZE * 3 + image_builder.PADDING * 2
    assert img.size == (expected_w, image_builder.ICON_SIZE)


@pytest.mark.asyncio
async def test_get_build_image_correct_size_with_keystone(dirs):
    """キーストーンあり: 幅 = ICON_SIZE*N + PADDING*(N-1) + SEPARATOR + ICON_SIZE"""
    icon_dir, rune_icon_dir, _ = dirs
    for item_id in ["3071", "3053", "6333"]:
        _make_icon(icon_dir / f"{item_id}.png")
    _make_icon(rune_icon_dir / "8010.png", (255, 255, 0, 255))

    result = await image_builder.get_build_image(
        ["3071", "3053", "6333"],
        {i: None for i in ["3071", "3053", "6333"]},
        keystone_id="8010",
        keystone_url=None,
    )
    img = Image.open(result)
    expected_w = (
        image_builder.ICON_SIZE
        + image_builder.SEPARATOR
        + image_builder.ICON_SIZE * 3
        + image_builder.PADDING * 2
    )
    assert img.size == (expected_w, image_builder.ICON_SIZE)


@pytest.mark.asyncio
async def test_get_build_image_cache_key_differs_with_keystone(dirs):
    """キーストーンあり・なしで別ファイルにキャッシュされる。"""
    icon_dir, rune_icon_dir, _ = dirs
    _make_icon(icon_dir / "3071.png")
    _make_icon(rune_icon_dir / "8010.png")

    path_no_ks = await image_builder.get_build_image(["3071"], {"3071": None})
    path_with_ks = await image_builder.get_build_image(
        ["3071"], {"3071": None}, keystone_id="8010", keystone_url=None
    )
    assert path_no_ks != path_with_ks


@pytest.mark.asyncio
async def test_get_build_image_cache_reuse(dirs):
    """同じ組み合わせを2回呼ぶとキャッシュが返る（ファイル更新日時が変わらない）。"""
    icon_dir, _, _ = dirs
    _make_icon(icon_dir / "3071.png")

    path1 = await image_builder.get_build_image(["3071"], {"3071": None})
    mtime1 = path1.stat().st_mtime
    path2 = await image_builder.get_build_image(["3071"], {"3071": None})
    mtime2 = path2.stat().st_mtime

    assert path1 == path2
    assert mtime1 == mtime2


@pytest.mark.asyncio
async def test_get_build_image_empty_returns_none(dirs):
    """アイテムリストが空のときは None を返す。"""
    assert await image_builder.get_build_image([], {}) is None


@pytest.mark.asyncio
async def test_get_build_image_placeholder_on_missing_url(dirs):
    """URL が None でキャッシュもない場合はプレースホルダーで合成されクラッシュしない。"""
    result = await image_builder.get_build_image(["9999"], {"9999": None})
    assert result is not None
    assert result.exists()


def test_clear_image_cache(dirs):
    """clear_image_cache でアイコン・ルーン・ビルド画像が全削除される。"""
    icon_dir, rune_icon_dir, build_dir = dirs
    _make_icon(icon_dir / "3071.png")
    _make_icon(rune_icon_dir / "8010.png")
    _make_icon(build_dir / "3071_ks8010.png")

    image_builder.clear_image_cache()

    assert not any(icon_dir.glob("*.png"))
    assert not any(rune_icon_dir.glob("*.png"))
    assert not any(build_dir.glob("*.png"))
