"""
アイテム・ルーンアイコンのダウンロードキャッシュと合成ビルド画像の生成・キャッシュを担当するモジュール。

キャッシュ構造:
  data/item_icons/{item_id}.png              — アイテムアイコン
  data/rune_icons/{rune_id}.png              — ルーンアイコン
  data/build_images/{ids}_ks{rune_id}.png    — 合成済み画像

合成レイアウト:
  [item1][PADDING][item2][PADDING][item3][SEPARATOR][keystone]
"""
import aiohttp
from pathlib import Path
from PIL import Image

_HERE = Path(__file__).parent
ICON_DIR      = _HERE / "data" / "item_icons"
RUNE_ICON_DIR = _HERE / "data" / "rune_icons"
BUILD_IMG_DIR = _HERE / "data" / "build_images"

ICON_SIZE  = 48
PADDING    = 6
SEPARATOR  = 16   # アイテム群とキーストーンの間の余白


async def _fetch_image(url: str, save_path: Path) -> Path | None:
    """URL から画像をダウンロードして保存する。失敗時は None。"""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                save_path.write_bytes(await resp.read())
        return save_path
    except Exception:
        return None


async def _load_icon(icon_id: str, url: str | None, cache_dir: Path) -> Image.Image:
    """アイコン画像を返す。キャッシュなし・URLなし・DL失敗時はグレーのプレースホルダー。"""
    if url is not None:
        path = cache_dir / f"{icon_id}.png"
        if not path.exists():
            path = await _fetch_image(url, path)
        if path and path.exists():
            return Image.open(path).convert("RGBA").resize(
                (ICON_SIZE, ICON_SIZE), Image.LANCZOS
            )
    return Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (70, 70, 70, 255))


async def get_build_image(
    item_ids: list[str],
    icon_url_map: dict[str, str | None],
    keystone_id: str | None = None,
    keystone_url: str | None = None,
) -> Path | None:
    """
    合成ビルド画像を返す。キャッシュがあれば再利用、なければ生成して保存する。

    レイアウト: [item1][item2][item3] [keystone]
      - keystone_id が指定された場合、右端にセパレーター + キーストーンアイコンを追加

    Args:
        item_ids:     アイテムIDのリスト
        icon_url_map: {item_id: url_or_none}
        keystone_id:  キーストーンID（省略可）
        keystone_url: キーストーン画像URL（省略可）
    """
    if not item_ids:
        return None

    cache_key = "_".join(str(i) for i in item_ids)
    if keystone_id:
        cache_key += f"_ks{keystone_id}"
    BUILD_IMG_DIR.mkdir(parents=True, exist_ok=True)
    path = BUILD_IMG_DIR / f"{cache_key}.png"

    if path.exists():
        return path

    # アイテムアイコンをロード
    item_icons = [
        await _load_icon(str(item_id), icon_url_map.get(str(item_id)), ICON_DIR)
        for item_id in item_ids
    ]

    # キーストーンアイコンをロード（あれば）
    ks_icon: Image.Image | None = None
    if keystone_id:
        ks_icon = await _load_icon(str(keystone_id), keystone_url, RUNE_ICON_DIR)

    # キャンバスサイズ計算
    n = len(item_icons)
    total_w = ICON_SIZE * n + PADDING * (n - 1)
    if ks_icon:
        total_w += ICON_SIZE + SEPARATOR

    composite = Image.new("RGBA", (total_w, ICON_SIZE), (0, 0, 0, 0))

    # キーストーンアイコンを左端に貼り付け
    item_offset = 0
    if ks_icon:
        composite.paste(ks_icon, (0, 0), ks_icon)
        item_offset = ICON_SIZE + SEPARATOR

    # アイテムアイコンをキーストーンの右に貼り付け
    for i, icon in enumerate(item_icons):
        composite.paste(icon, (item_offset + i * (ICON_SIZE + PADDING), 0), icon)

    composite.save(path, "PNG", optimize=True)
    return path


def clear_image_cache() -> None:
    """パッチ更新時などにアイコン・合成画像のキャッシュを全削除する。"""
    for d in (ICON_DIR, RUNE_ICON_DIR, BUILD_IMG_DIR):
        for p in d.glob("*.png"):
            p.unlink(missing_ok=True)
