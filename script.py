from urllib.parse import quote_plus

LANE_DISPLAY_NAMES: dict[str, str] = {
    "top": "TOP",
    "jungle": "JG",
    "mid": "MID",
    "adc": "ADC",
    "support": "SUP",
}

MSG_TITLE = "{enemy} へのカウンター ({lane})"
MSG_DESCRIPTION = "勝率上位 {count} 体のカウンターチャンピオンです。"
MSG_NO_DATA = "このマッチアップのデータが不足しています。"
MSG_CHAMP_NOT_FOUND = "チャンピオン「{name}」が見つかりませんでした。日本語または英語で正確に入力してください。"
MSG_LANE_NOT_FOUND = "レーン「{lane}」は無効です。top / jungle / mid / adc / support のいずれかを指定してください。"
MSG_COUNTER_FIELD_TITLE = "{rank}. {name_ja}（{name_en}）"
MSG_UPDATE_STARTED = "データ更新を開始しました。完了後にこのチャンネルへ通知します。"
MSG_UPDATE_DONE = "データ更新が完了しました。"
MSG_UPDATE_ERROR = "データ更新中にエラーが発生しました: {error}"
MSG_PATCH_DONE = "パッチキャッシュをリセットしました。Data Dragon の最新データを取得済みです。"
MSG_PATCH_ERROR = "パッチリセット中にエラーが発生しました: {error}"
MSG_NO_PERMISSION = "このコマンドは管理者のみ実行できます。"
MSG_BUILD_TITLE = "おすすめビルド"
MSG_BUILD_IMAGE_BUTTON = "ビルド画像"
MSG_YOUTUBE_LABEL = "YouTube でマッチアップ動画を見る"


def youtube_url(my_champ: str, enemy_champ: str, lane: str) -> str:
    query = f"LoL {my_champ} vs {enemy_champ} {lane} High Elo"
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def format_winrate(wins: int, games: int) -> str:
    if games == 0:
        return "N/A"
    return f"{wins / games * 100:.1f}%"


def format_pick_rate(pick_count: int, total_games: int) -> str:
    if total_games == 0:
        return "N/A"
    return f"{pick_count / total_games * 100:.1f}%"


def format_ban_rate(ban_count: int, total_games: int) -> str:
    if total_games == 0:
        return "N/A"
    return f"{min(ban_count / total_games, 1.0) * 100:.1f}%"


def format_stats_field(counter: dict, rank: int) -> tuple[str, str]:
    """Embed フィールドの (name, value) タプルを返す。"""
    name_ja = counter.get("name_ja") or counter.get("name_en", "Unknown")
    name_en = counter.get("name_en", "Unknown")
    wins = counter.get("wins", 0)
    games = counter.get("games", 0)
    pick_count = counter.get("pick_count", 0)
    total_lane_games = counter.get("total_lane_games", 0)
    ban_count = counter.get("ban_count", 0)
    ban_total_games = counter.get("ban_total_games", 0)

    field_name = MSG_COUNTER_FIELD_TITLE.format(rank=rank, name_ja=name_ja, name_en=name_en)
    field_value = (
        f"勝率: **{format_winrate(wins, games)}** ({games} 試合)\n"
        f"ピック率: {format_pick_rate(pick_count, total_lane_games)}\n"
        f"BAN率: {format_ban_rate(ban_count, ban_total_games)}"
    )
    return field_name, field_value


def lane_display(lane: str) -> str:
    return LANE_DISPLAY_NAMES.get(lane.lower(), lane.upper())
